"""Stage 5A-2D: Visual/OCR for "Хук / первый экран" across 3 pinned posts.

Reads data/normalized/stage5a2b_pinned_posts_details.json.
Downloads the first-frame image for each pinned post, sends it to OpenAI Vision,
and extracts the hook (text or visual description).

Usage:
    python3 scripts/stage5a2d_pinned_hooks_visual.py --dry-run
    python3 scripts/stage5a2d_pinned_hooks_visual.py
    python3 scripts/stage5a2d_pinned_hooks_visual.py --position 1
"""

import argparse
import base64
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("[ERROR] Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

BASE      = Path(__file__).parent.parent
NORM_DIR  = BASE / "data" / "normalized"

INPUT_PATH  = NORM_DIR / "stage5a2b_pinned_posts_details.json"
OUTPUT_PATH = NORM_DIR / "stage5a2d_pinned_hooks.json"

ACCOUNT        = "vlada_kliuiko"
STAGE          = "stage5a2d"
PROMPT_VERSION = "v2"
DEFAULT_MODEL  = "gpt-4o"
MAX_TOKENS     = 400
IMAGE_DETAIL   = "low"
MAX_LONG_SIDE  = 512
JPEG_QUALITY   = 85

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36"
    )
}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Ты — аналитик Instagram-контента. Тебе показывают первый кадр поста из Instagram.
Твоя задача — извлечь хук в формате: [текст с обложки] → [маркетинговая интерпретация].

ПРАВИЛА:
1. Левая часть (до →): дословный текст с кадра. Если текста много — бери первые 2-3 ключевые строки. Если текста нет — краткое описание визуала одним предложением.
2. Правая часть (после →): что это говорит аудитории — боль, интрига, обещание. Если хука нет — пиши "нет явного хука".
3. Не додумывай содержание поста. Только то, что видно на этом кадре.
4. Отвечай строго в JSON, без текста вне JSON.

Примеры:
- Текст "Как я вырос до 40к за 3 месяца" → value: "Как я вырос до 40к за 3 месяца → обещание быстрого результата"
- Фото человека без текста → value: "портретное фото автора → нет явного хука"
- Текст "услуги агентства" → value: "услуги агентства → нет явного хука, просто заголовок"
- Длинный текст из 5 строк → взять первые 2-3 ключевые строки → интерпретация

ФОРМАТ ОТВЕТА (строго JSON):
{
  "hook": {
    "value": "...",
    "data_status": "ok|not_found",
    "notes": "1 предложение — что именно видно на кадре"
  }
}"""


def build_user_prompt(position: int, post_type: str) -> str:
    return (
        f"Закреп №{position} (тип: {post_type}).\n"
        "Извлеки хук — что человек видит первым на этом кадре.\n"
        "Отвечай только JSON."
    )


# ---------------------------------------------------------------------------
# Input loader
# ---------------------------------------------------------------------------

def load_posts() -> tuple[list, str | None]:
    if not INPUT_PATH.exists():
        return [], f"{INPUT_PATH.relative_to(BASE)} not found"
    try:
        data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return [], f"Failed to parse input: {e}"
    posts = data.get("posts", [])
    if not posts:
        return [], "No posts found in input file"
    return posts, None


# ---------------------------------------------------------------------------
# Image selection
# ---------------------------------------------------------------------------

def select_image_info(post: dict) -> dict:
    """Return dict with image_source, displayUrl_used."""
    position   = post.get("position", "?")
    post_type  = post.get("media_type", "")
    carousel   = post.get("carousel_items") or []

    if post_type == "Sidecar" and carousel:
        url = carousel[0].get("display_url", "")
        print(f"[INFO] Post {position}: Sidecar — using first carousel item")
        return {"image_source": "carousel_first", "displayUrl_used": url}

    url = post.get("display_url", "")
    if post_type == "Video":
        print(f"[INFO] Post {position}: Video — using thumbnail (display_url)")
    return {"image_source": "displayUrl", "displayUrl_used": url}


# ---------------------------------------------------------------------------
# Image download + resize
# ---------------------------------------------------------------------------

def download_and_encode(url: str, position: int) -> tuple[str | None, str | None]:
    """Download image, resize, return base64 data URI or (None, skip_reason)."""
    import requests

    try:
        resp = requests.get(url, timeout=10, headers=_HEADERS)
    except Exception as e:
        print(f"[WARN] Post {position}: download error — {e}")
        return None, f"download_error: {e}"

    if resp.status_code != 200:
        print(f"[WARN] Post {position}: HTTP {resp.status_code} for image URL")
        return None, f"http_{resp.status_code}"

    ct = resp.headers.get("Content-Type", "")
    if not ct.startswith("image/"):
        print(f"[WARN] Post {position}: unexpected Content-Type '{ct}'")
        return None, f"unexpected_content_type: {ct}"

    try:
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        if max(w, h) > MAX_LONG_SIDE:
            scale = MAX_LONG_SIDE / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}", None
    except Exception as e:
        print(f"[WARN] Post {position}: image processing error — {e}")
        return None, f"processing_error: {e}"


# ---------------------------------------------------------------------------
# JSON parse helper
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> tuple[dict | None, str | None]:
    clean = raw.strip()
    if clean.startswith("```"):
        if clean.count("```") >= 2:
            clean = clean.split("```", 2)[1]
        if clean.startswith("json"):
            clean = clean[4:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
    try:
        return json.loads(clean), None
    except json.JSONDecodeError as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

def _call_vision(client, data_uri: str, position: int, post_type: str, model: str) -> dict:
    user_prompt = build_user_prompt(position, post_type)
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri, "detail": IMAGE_DETAIL},
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
        )
        raw = response.choices[0].message.content or ""
        parsed, err = _parse_json(raw)
        if err:
            return {
                "status":       "parse_error",
                "parse_error":  True,
                "raw_response": raw[:300],
                "tokens_used":  getattr(response.usage, "total_tokens", None),
            }
        hook = parsed.get("hook") or {}
        return {
            "status":      "ok",
            "hook":        hook,
            "tokens_used": getattr(response.usage, "total_tokens", None),
        }
    except Exception as e:
        return {"status": "openai_error", "error": str(e)}


# ---------------------------------------------------------------------------
# Single-post processing
# ---------------------------------------------------------------------------

def _process_post(post: dict, client, model: str) -> dict:
    position  = post.get("position", 0)
    post_type = post.get("media_type", "")
    img_info  = select_image_info(post)
    url       = img_info["displayUrl_used"]

    base_record = {
        "position":        position,
        "post_type":       post_type,
        "image_source":    img_info["image_source"],
        "displayUrl_used": url,
        "skipped":         False,
    }

    if not url:
        print(f"[WARN] Post {position}: no displayUrl available — skipping")
        return {**base_record, "skipped": True, "skip_reason": "no_url"}

    data_uri, skip_reason = download_and_encode(url, position)
    if data_uri is None:
        return {**base_record, "skipped": True, "skip_reason": skip_reason}

    print(f"[INFO] Post {position}: calling Vision ({model})...")
    result = _call_vision(client, data_uri, position, post_type, model)

    if result["status"] == "ok":
        return {**base_record, "hook": result["hook"], "tokens_used": result.get("tokens_used")}
    if result.get("parse_error"):
        return {
            **base_record,
            "parse_error":  True,
            "raw_response": result.get("raw_response", ""),
            "tokens_used":  result.get("tokens_used"),
        }
    return {**base_record, "skipped": True, "skip_reason": result.get("error", "openai_error")}


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(position_filter: int | None):
    print("[DRY-RUN] No images downloaded. OpenAI not called. No files will be written.\n")

    # Always attempt to load the real input file in dry-run
    posts, err = load_posts()
    if err:
        print(f"[DRY-RUN] Input file not available: {err}")
        print("[DRY-RUN] Post data cannot be shown — file absent.\n")
        posts = []
    else:
        print(f"[DRY-RUN] Loaded {len(posts)} posts from {INPUT_PATH.relative_to(BASE)}\n")

    target_posts = [p for p in posts if position_filter is None or p.get("position") == position_filter]

    if target_posts:
        for post in target_posts:
            position  = post.get("position", "?")
            post_type = post.get("media_type", "")
            img_info  = select_image_info(post)
            print("=" * 60)
            print(f"POST {position}:")
            print(f"  post_type:       {post_type}")
            print(f"  image_source:    {img_info['image_source']}")
            print(f"  displayUrl_used: {img_info['displayUrl_used']}")
            print()
    else:
        if not posts:
            print("[DRY-RUN] No posts available — showing example prompts only.\n")
        else:
            print(f"[DRY-RUN] No posts match position filter: {position_filter}\n")

    print("=" * 60)
    print("SYSTEM PROMPT (будет отправлен в OpenAI):")
    print("=" * 60)
    print(SYSTEM_PROMPT)
    print()

    if target_posts:
        for post in target_posts:
            position  = post.get("position", "?")
            post_type = post.get("media_type", "")
            print("=" * 60)
            print(f"USER PROMPT — Post {position} (будет отправлен в OpenAI):")
            print("=" * 60)
            print(build_user_prompt(position, post_type))
            print()
    else:
        print("=" * 60)
        print("USER PROMPT — пример для Post 1 / Image (будет отправлен в OpenAI):")
        print("=" * 60)
        print(build_user_prompt(1, "Image"))
        print()

    print(f"Model:          {DEFAULT_MODEL}")
    print(f"max_tokens:     {MAX_TOKENS}")
    print(f"detail:         {IMAGE_DETAIL}")
    print(f"Prompt version: {PROMPT_VERSION}")
    print(f"Output path:    {OUTPUT_PATH.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5A-2D: Visual/OCR hook extraction for pinned posts"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show image selection and prompts; do NOT download images, call OpenAI, or write output",
    )
    parser.add_argument(
        "--position", type=int, choices=[1, 2, 3],
        help="Analyze only a single pinned post by position (1, 2, or 3)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"OpenAI model to use (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    if args.dry_run:
        run_dry_run(args.position)
        return

    posts, err = load_posts()
    if err:
        print(f"[ERROR] {err}")
        sys.exit(1)

    # Load API key
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=BASE / ".env", override=True)
    except ImportError:
        pass

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY not set. Add it to .env or environment.")
        sys.exit(1)
    if not api_key.startswith("sk-"):
        print("[ERROR] OPENAI_API_KEY looks invalid (must start with sk-).")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("openai not installed — run: pip install openai")

    client = OpenAI(api_key=api_key)

    target_posts = [p for p in posts if args.position is None or p.get("position") == args.position]
    if not target_posts:
        print(f"[ERROR] No posts match position filter: {args.position}")
        sys.exit(1)

    results = []
    for post in target_posts:
        record = _process_post(post, client, args.model)
        results.append(record)
        status = "SKIPPED" if record.get("skipped") else ("PARSE_ERROR" if record.get("parse_error") else "OK")
        print(f"  Post {record['position']}: {status}")

    output = {
        "account":        ACCOUNT,
        "stage":          STAGE,
        "prompt_version": PROMPT_VERSION,
        "model":          args.model,
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "posts":          results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Written: {OUTPUT_PATH.relative_to(BASE)}")

    print("\n=== Hook Summary ===")
    for rec in results:
        pos = rec["position"]
        if rec.get("skipped"):
            print(f"  Post {pos}: SKIPPED ({rec.get('skip_reason', '?')})")
        elif rec.get("parse_error"):
            print(f"  Post {pos}: PARSE_ERROR — {rec.get('raw_response', '')[:80]}")
        else:
            hook  = rec.get("hook") or {}
            htype = hook.get("type", "?")
            val   = (hook.get("value") or "")[:80] or "(empty)"
            print(f"  Post {pos}: [{htype}] {val}")


if __name__ == "__main__":
    main()
