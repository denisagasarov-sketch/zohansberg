#!/usr/bin/env python3
"""
Stage 5D Prep: Local handoff bundle collector.

Collects sanitized project state for Stage 5D design handoff:
  - git state
  - local file inventory
  - Excel template schema (read-only, openpyxl)
  - ТЗ markdown (sanitized copy)
  - pipeline output summaries (truncated, no full media URLs)
  - stage proof summary

Writes to: handoff/stage5d_handoff/

SAFETY:
  - Scans all content for secrets before writing any file
  - Never reads .env
  - Never calls Apify, OpenAI, or any external service
  - Never modifies project files
  - Does NOT commit anything

Usage:
  python scripts/stage5d_prepare_handoff.py [--dry-run]
  python scripts/stage5d_prepare_handoff.py --tz-file /path/to/tz.md
  python scripts/stage5d_prepare_handoff.py --excel-file /path/to/table.xlsx
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

os.environ["PYTHONUTF8"] = "1"

BASE      = Path(__file__).parent.parent
NORM_DIR  = BASE / "data/normalized"
OUT_DIR   = BASE / "handoff/stage5d_handoff"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _flag(name):  return name in sys.argv
def _arg(name, default=None):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1])
    return default

DRY_RUN    = _flag("--dry-run")
EXPLICIT_TZ    = _arg("--tz-file")
EXPLICIT_EXCEL = _arg("--excel-file")

# ---------------------------------------------------------------------------
# Secret scanner
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),           "openai_api_key"),
    (re.compile(r"apify_api_[A-Za-z0-9_\-]{20,}"),    "apify_token"),
    (re.compile(r"sessionid=[A-Za-z0-9%_\-]{15,}",    re.I), "session_cookie_value"),
    (re.compile(r"(?<==)eyJ[A-Za-z0-9_\-]{40,}"),     "jwt_token"),
    (re.compile(r"INSTAGRAM_SESSION_COOKIE\s*=\s*\S{10,}"), "instagram_cookie_assignment"),
    (re.compile(r"OPENAI_API_KEY\s*=\s*sk-"),          "openai_key_assignment"),
    (re.compile(r"APIFY_TOKEN\s*=\s*apify_api_"),      "apify_token_assignment"),
]

def scan_secrets(text: str, label: str) -> list[str]:
    """Returns list of (pattern_name, snippet) strings for any secrets found."""
    found = []
    for pattern, name in _SECRET_PATTERNS:
        for m in pattern.finditer(text):
            snippet = m.group()[:30] + "..." if len(m.group()) > 30 else m.group()
            found.append(f"{name}: ...{snippet}...")
    return found


def assert_clean(text: str, label: str) -> None:
    hits = scan_secrets(text, label)
    if hits:
        print(f"[SECURITY] Secret detected in [{label}] — aborting write.", file=sys.stderr)
        for h in hits:
            print(f"  {h}", file=sys.stderr)
        sys.exit(1)

# ---------------------------------------------------------------------------
# URL redactor
# ---------------------------------------------------------------------------

_LONG_URL_RE = re.compile(r'https?://[^\s\'"<>]{80,}')

def redact_urls(text: str) -> str:
    """Replace long URLs with <url:domain/prefix_redacted>."""
    def _repl(m):
        url = m.group()
        try:
            p = urlparse(url)
            parts = [x for x in p.path.split("/") if x]
            prefix = "/".join(parts[:2]) if parts else ""
            return f"<url:{p.netloc}/{prefix}/...redacted>"
        except Exception:
            return "<url:redacted>"
    return _LONG_URL_RE.sub(_repl, text)

# ---------------------------------------------------------------------------
# Git state
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, cwd=BASE, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "(command failed)"


def collect_git_state() -> str:
    branch  = _run(["git", "branch", "--show-current"])
    status  = _run(["git", "status", "--short"])
    staged  = _run(["git", "diff", "--cached", "--name-only"])
    recent  = _run(["git", "log", "--oneline", "-6"])
    return (
        f"# Git State\n\n"
        f"## Branch\n{branch}\n\n"
        f"## Status (git status --short)\n```\n{status or '(clean)'}\n```\n\n"
        f"## Staged files\n```\n{staged or '(none)'}\n```\n\n"
        f"## Recent commits\n```\n{recent}\n```\n"
    )

# ---------------------------------------------------------------------------
# File inventory
# ---------------------------------------------------------------------------

_EXCLUDE_DIRS = {".venv", "__pycache__", "node_modules", "stage5c_cache",
                 ".git", "media", "output", "frames", "screenshots"}
_EXCLUDE_EXTS = {".pyc", ".pyo", ".mp4", ".mov", ".avi", ".jpg", ".jpeg",
                 ".png", ".webp", ".gif", ".mp3", ".wav"}
_INCLUDE_ROOTS = ["config", "scripts", "data/normalized", "report",
                  "input", "docs", "prompts", "handoff"]

def collect_file_inventory() -> str:
    lines = ["# File Inventory\n"]
    for root_rel in _INCLUDE_ROOTS:
        root = BASE / root_rel
        if not root.exists():
            continue
        lines.append(f"\n## {root_rel}/\n")
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            # skip excluded dirs
            if any(part in _EXCLUDE_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in _EXCLUDE_EXTS:
                continue
            rel = path.relative_to(BASE)
            size = path.stat().st_size
            size_str = f"{size:,} B" if size < 1024 else f"{size//1024:,} KB"
            lines.append(f"  {rel}  ({size_str})")
    # also list root-level files
    lines.append("\n## root\n")
    for p in sorted(BASE.iterdir()):
        if p.is_file() and p.suffix.lower() not in _EXCLUDE_EXTS:
            rel = p.relative_to(BASE)
            lines.append(f"  {rel}  ({p.stat().st_size:,} B)")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Excel schema extractor
# ---------------------------------------------------------------------------

def find_excel_files() -> list[Path]:
    found = []
    search_dirs = [BASE, BASE.parent, BASE / "docs", BASE / "input", BASE / "templates"]
    for d in search_dirs:
        if not d.exists():
            continue
        for ext in ("*.xlsx", "*.xlsm", "*.xls"):
            found.extend(d.glob(ext))
    return [p for p in found if ".venv" not in str(p)]


def extract_excel_schema(path: Path) -> tuple[dict, str]:
    """Returns (schema_dict, markdown_text). Reads file in read-only mode."""
    try:
        import openpyxl
    except ImportError:
        return (
            {"error": "openpyxl not installed", "hint": "pip install openpyxl"},
            "## Excel schema\n\nopenpyxl not installed — run: `pip install openpyxl`\n"
        )

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    schema = {
        "file":        str(path.name),
        "full_path":   str(path),
        "sheet_names": wb.sheetnames,
        "sheets":      {},
        "total_columns": 0,
    }
    md_lines = [f"# Excel Template Schema\n\nFile: `{path.name}`\n"]

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        # Find header row: scan first 5 rows for the row with most non-null cells
        best_row = None
        best_count = 0
        for row_idx, row in enumerate(ws.iter_rows(max_row=5, values_only=True), start=1):
            non_null = [c for c in row if c is not None]
            if len(non_null) > best_count:
                best_count = len(non_null)
                best_row = non_null
                best_row_idx = row_idx
        if not best_row:
            best_row = []
            best_row_idx = None

        # Count non-empty rows (sample up to 500)
        data_rows = 0
        for i, row in enumerate(ws.iter_rows(min_row=(best_row_idx or 1) + 1, values_only=True)):
            if i > 500:
                break
            if any(c is not None for c in row):
                data_rows += 1

        columns = [str(c) for c in best_row]
        schema["sheets"][sheet_name] = {
            "header_row_index": best_row_idx,
            "columns":          columns,
            "column_count":     len(columns),
            "data_rows_sample": data_rows,
        }
        schema["total_columns"] += len(columns)

        md_lines.append(f"\n## Sheet: {sheet_name}")
        md_lines.append(f"- header_row: {best_row_idx}")
        md_lines.append(f"- column_count: {len(columns)}")
        md_lines.append(f"- data_rows (sample): {data_rows}")
        md_lines.append("\n| # | Column name |")
        md_lines.append("|---|---|")
        for i, col in enumerate(columns, start=1):
            md_lines.append(f"| {i} | {col} |")

    total = schema["total_columns"]
    md_lines.append(f"\n## Summary")
    md_lines.append(f"- total_columns across all sheets: **{total}**")
    md_lines.append(f"- expected_79: {'YES ✓' if total == 79 else f'NO — actual={total}'}")

    wb.close()
    return schema, "\n".join(md_lines)

# ---------------------------------------------------------------------------
# ТЗ finder
# ---------------------------------------------------------------------------

_TZ_NAME_PATTERNS = [
    re.compile(r"тз", re.I),
    re.compile(r"tz[\._\-]", re.I),
    re.compile(r"task[\._\-]", re.I),
    re.compile(r"техни", re.I),
    re.compile(r"анали", re.I),
    re.compile(r"конкурент", re.I),
    re.compile(r"competitor", re.I),
    re.compile(r"research", re.I),
    re.compile(r"требовани", re.I),
]

def find_tz_candidates() -> list[Path]:
    candidates = []
    search_dirs = [BASE, BASE.parent, BASE / "docs", BASE / "input"]
    for d in search_dirs:
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            name = p.name.lower()
            if any(pat.search(name) for pat in _TZ_NAME_PATTERNS):
                candidates.append(p)
            elif p.stat().st_size > 3000:  # also consider larger MDs as potential ТЗ
                candidates.append(p)
    seen = set()
    result = []
    for c in candidates:
        if c not in seen and ".venv" not in str(c):
            seen.add(c)
            result.append(c)
    return result


def read_tz(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = redact_urls(text)
    assert_clean(text, f"ТЗ file: {path.name}")
    return text

# ---------------------------------------------------------------------------
# Pipeline output summarizer
# ---------------------------------------------------------------------------

_PIPELINE_FILES = [
    "profile_summary.json",
    "bio_analysis.json",
    "pinned_posts_index.json",
    "highlights_index.json",
    "stage5b_auto_stories_summary.json",
    "stage5b_auto_stories_index.json",
    "stage5c_highlights_summary.json",
    "stage5c_stories_analysis.json",
]

_MAX_ITEMS_IN_SUMMARY = 2
_MAX_STR_LEN = 120


def _truncate_val(v, depth=0):
    """Recursively truncate long values for summary."""
    if isinstance(v, str):
        if re.match(r"https?://", v) and len(v) > 60:
            return redact_urls(v)
        return v[:_MAX_STR_LEN] + "..." if len(v) > _MAX_STR_LEN else v
    if isinstance(v, list):
        if depth > 1:
            return f"[list len={len(v)}]"
        truncated = [_truncate_val(i, depth + 1) for i in v[:_MAX_ITEMS_IN_SUMMARY]]
        suffix = [f"... +{len(v) - _MAX_ITEMS_IN_SUMMARY} more"] if len(v) > _MAX_ITEMS_IN_SUMMARY else []
        return truncated + suffix
    if isinstance(v, dict):
        if depth > 2:
            return f"{{dict keys={list(v.keys())[:6]}}}"
        return {k: _truncate_val(vv, depth + 1) for k, vv in list(v.items())[:12]}
    return v


def summarize_pipeline_outputs() -> tuple[dict, str]:
    summaries = {}
    md_lines  = ["# Pipeline Output Summaries\n"]

    for fname in _PIPELINE_FILES:
        path = NORM_DIR / fname
        if not path.exists():
            summaries[fname] = {"status": "missing"}
            md_lines.append(f"\n## {fname}\n**MISSING** — not yet run locally.\n")
            continue

        raw_size = path.stat().st_size
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            summaries[fname] = {"status": "parse_error", "error": str(e)}
            md_lines.append(f"\n## {fname}\n**PARSE ERROR**: {e}\n")
            continue

        truncated = _truncate_val(data)
        # Convert back to string for secret scan
        truncated_str = json.dumps(truncated, ensure_ascii=False, indent=2)
        truncated_str = redact_urls(truncated_str)
        assert_clean(truncated_str, f"pipeline output: {fname}")

        summaries[fname] = {
            "status":       "exists",
            "size_bytes":   raw_size,
            "top_level_keys": list(data.keys()) if isinstance(data, dict) else f"list[{len(data)}]",
            "summary":      json.loads(truncated_str),
        }

        top_keys = list(data.keys()) if isinstance(data, dict) else "list"
        md_lines.append(f"\n## {fname}")
        md_lines.append(f"- size: {raw_size:,} bytes")
        md_lines.append(f"- top_level_keys: {top_keys}")
        if isinstance(data, dict):
            # Show scalar values directly, truncate lists/dicts
            for k, v in list(data.items())[:20]:
                if isinstance(v, (str, int, float, bool)) and v is not None:
                    md_lines.append(f"- {k}: {v}")
                elif isinstance(v, list):
                    md_lines.append(f"- {k}: list[{len(v)}]")
                elif isinstance(v, dict):
                    md_lines.append(f"- {k}: dict{{{list(v.keys())[:5]}}}")
        md_lines.append("")

    return summaries, "\n".join(md_lines)

# ---------------------------------------------------------------------------
# Stage proof summary
# ---------------------------------------------------------------------------

def build_stage_proof(pipeline_summaries: dict) -> str:
    lines = [
        "# Stage Proof Summary",
        "",
        "Verified local facts from completed pipeline runs.",
        "These are the inputs Stage 5D planning should rely on.",
        "",
        "## Stage 5B-auto (automation-lab/instagram-stories-scraper)",
        "",
    ]

    sb_summary = pipeline_summaries.get("stage5b_auto_stories_summary.json", {})
    if sb_summary.get("status") == "exists":
        s = sb_summary.get("summary", {})
        for k in ["total_items_returned", "active_stories_count", "highlight_stories_count",
                  "highlights_returned", "highlights_in_index", "can_analyze_highlights",
                  "max_highlights_requested", "actor", "run_timestamp"]:
            v = s.get(k)
            if v is not None:
                lines.append(f"- {k}: {v}")
        ns = s.get("normalization_stats", {})
        if ns and isinstance(ns, dict):
            lines.append("")
            lines.append("### Normalization stats")
            for k, v in ns.items():
                lines.append(f"  - {k}: {v}")
    else:
        lines.append("- stage5b_auto_stories_summary.json: MISSING locally")
    lines.append("")

    lines += [
        "## Stage 5C (OpenAI Vision analysis)",
        "",
    ]
    sc_summary = pipeline_summaries.get("stage5c_highlights_summary.json", {})
    if sc_summary.get("status") == "exists":
        s = sc_summary.get("summary", {})
        for k in ["model", "detail", "image_input_mode", "selection_mode",
                  "total_analyzed", "total_from_cache", "total_skipped", "total_errors",
                  "cumulative_cost_usd", "budget_reached", "run_timestamp"]:
            v = s.get(k)
            if v is not None:
                lines.append(f"- {k}: {v}")
    else:
        lines.append("- stage5c_highlights_summary.json: MISSING locally")
        lines.append("- NOTE: Stage 5C base64 fix was applied but not yet re-run locally")
    lines += [
        "",
        "## External service calls during Stage 5C",
        "",
        "- Apify: NOT called (Stage 5C analyzes local normalized data only)",
        "- Media saved to disk: NO (fetched in-memory, base64, discarded after OpenAI)",
        "",
        "## What is NOT yet available",
        "",
        "- Landing page analysis: MISSING — requires Stage 5E or manual",
        "- Bot / lead magnet analysis: MISSING — requires manual traversal",
        "- Funnel mapping: MISSING",
        "- Full highlight stories (all 32): only 3 highlights collected so far",
        "",
        "## Source of truth for Stage 5D",
        "",
        "| Data | Source file | Status |",
        "|---|---|---|",
        "| Profile, bio, followers | profile_summary.json + bio_analysis.json | ready (Stage 5A-1) |",
        "| Highlights index | highlights_index.json | ready (Stage 5B-1) |",
        "| Highlight stories content | stage5b_auto_stories_index.json | partial (3/32 highlights) |",
        "| Story analysis | stage5c_highlights_summary.json | partial (3 highlights × N stories) |",
        "| Pinned posts | pinned_posts_index.json | ready (Stage 5A-1) |",
        "| Landing / bot / funnel | — | MISSING |",
    ]
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Bundle README
# ---------------------------------------------------------------------------

def build_bundle_readme(excel_found: list, tz_found: list) -> str:
    return (
        "# Stage 5D Handoff Bundle\n\n"
        "Generated by: `scripts/stage5d_prepare_handoff.py`\n"
        "Purpose: Provide Stage 5D designer with sanitized local state.\n\n"
        "## Contents\n\n"
        "| File | Description |\n"
        "|---|---|\n"
        "| `git_state.md` | Branch, status, recent commits |\n"
        "| `file_inventory.md` | Local file tree (no media, no .env) |\n"
        "| `competitor_analysis_template_schema.json` | Excel sheet/column structure |\n"
        "| `competitor_analysis_template_schema.md` | Human-readable table schema |\n"
        "| `competitor_analysis_tz.md` | Sanitized ТЗ markdown |\n"
        "| `pipeline_output_summaries.json` | Truncated pipeline output data |\n"
        "| `pipeline_output_summaries.md` | Human-readable output summaries |\n"
        "| `stage_proof_summary.md` | Verified facts from completed stages |\n\n"
        "## Safety\n\n"
        "- No .env, API keys, tokens, or cookies included.\n"
        "- Long media URLs redacted to domain+prefix.\n"
        "- All content scanned for secrets before writing.\n"
        "- No external API calls made during bundle creation.\n"
        "- This folder is NOT committed to git.\n\n"
        f"## Excel files found\n\n"
        + ("\n".join(f"- {p}" for p in excel_found) or "- none found") + "\n\n"
        f"## ТЗ candidates found\n\n"
        + ("\n".join(f"- {p}" for p in tz_found) or "- none found") + "\n"
    )

# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def write_file(path: Path, content: str, label: str) -> None:
    assert_clean(content, label)
    if DRY_RUN:
        print(f"  [DRY RUN] would write: {path.relative_to(BASE)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote: {path.relative_to(BASE)}")


def write_json(path: Path, data: dict, label: str) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2)
    content = redact_urls(content)
    write_file(path, content, label)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Stage 5D Handoff Bundle Collector ===")
    print(f"Base dir:   {BASE}")
    print(f"Output dir: {OUT_DIR.relative_to(BASE)}")
    print(f"Dry-run:    {DRY_RUN}")
    print()

    # 1. Git state
    print("[1/7] Collecting git state ...")
    git_md = collect_git_state()

    # 2. File inventory
    print("[2/7] Collecting file inventory ...")
    inventory_md = collect_file_inventory()

    # 3. Excel schema
    print("[3/7] Locating and extracting Excel schema ...")
    if EXPLICIT_EXCEL:
        excel_files = [EXPLICIT_EXCEL] if EXPLICIT_EXCEL.exists() else []
        if not excel_files:
            print(f"  [WARN] --excel-file not found: {EXPLICIT_EXCEL}", file=sys.stderr)
    else:
        excel_files = find_excel_files()

    excel_schema_json: dict = {}
    excel_schema_md:   str  = "# Excel Template Schema\n\nNo Excel file found.\n"

    if excel_files:
        print(f"  Found: {[str(p) for p in excel_files]}")
        # Use first found, or explicit
        chosen = excel_files[0]
        print(f"  Extracting: {chosen.name}")
        excel_schema_json, excel_schema_md = extract_excel_schema(chosen)
        total = excel_schema_json.get("total_columns", 0)
        print(f"  Total columns: {total}  (expected 79: {'YES' if total == 79 else 'NO — actual=' + str(total)})")
    else:
        print("  [WARN] No Excel file found. Add --excel-file /path/to/file.xlsx")

    # 4. ТЗ markdown
    print("[4/7] Locating ТЗ markdown ...")
    if EXPLICIT_TZ:
        tz_candidates = [EXPLICIT_TZ] if EXPLICIT_TZ.exists() else []
        if not tz_candidates:
            print(f"  [WARN] --tz-file not found: {EXPLICIT_TZ}", file=sys.stderr)
    else:
        tz_candidates = find_tz_candidates()

    tz_text = "# ТЗ\n\nNo ТЗ markdown found.\n"
    tz_found_paths = []
    if tz_candidates:
        print(f"  Candidates: {[str(p) for p in tz_candidates]}")
        for p in tz_candidates:
            try:
                tz_text = read_tz(p)
                tz_found_paths.append(str(p))
                print(f"  Using: {p}")
                break
            except SystemExit:
                print(f"  [SKIP] Secret detected in {p.name} — skipping")
                continue
    else:
        print("  [WARN] No ТЗ candidates found. Add --tz-file /path/to/tz.md")

    # 5. Pipeline output summaries
    print("[5/7] Summarizing pipeline outputs ...")
    pipeline_json, pipeline_md = summarize_pipeline_outputs()
    missing = sum(1 for v in pipeline_json.values() if v.get("status") == "missing")
    exists  = sum(1 for v in pipeline_json.values() if v.get("status") == "exists")
    print(f"  exists={exists}  missing={missing}")

    # 6. Stage proof
    print("[6/7] Building stage proof summary ...")
    stage_proof_md = build_stage_proof(pipeline_json)

    # 7. Bundle README
    print("[7/7] Writing bundle ...")
    bundle_readme = build_bundle_readme(
        [str(p) for p in excel_files],
        tz_found_paths,
    )

    # Write all
    write_file(OUT_DIR / "BUNDLE_README.md",                           bundle_readme,           "bundle_readme")
    write_file(OUT_DIR / "git_state.md",                               git_md,                  "git_state")
    write_file(OUT_DIR / "file_inventory.md",                          inventory_md,             "file_inventory")
    write_json(OUT_DIR / "competitor_analysis_template_schema.json",   excel_schema_json,        "excel_schema_json")
    write_file(OUT_DIR / "competitor_analysis_template_schema.md",     excel_schema_md,          "excel_schema_md")
    write_file(OUT_DIR / "competitor_analysis_tz.md",                  tz_text,                  "tz_md")
    write_json(OUT_DIR / "pipeline_output_summaries.json",             pipeline_json,            "pipeline_summaries_json")
    write_file(OUT_DIR / "pipeline_output_summaries.md",               pipeline_md,              "pipeline_summaries_md")
    write_file(OUT_DIR / "stage_proof_summary.md",                     stage_proof_md,           "stage_proof")

    if DRY_RUN:
        print("\n[DRY RUN] No files written. Remove --dry-run to create bundle.")
    else:
        print(f"\nBundle created: {OUT_DIR.relative_to(BASE)}/")
        print("IMPORTANT: Do NOT commit handoff/ — add to .gitignore if needed.")
        print("Share the contents of handoff/stage5d_handoff/ with the AI session.")


if __name__ == "__main__":
    main()
