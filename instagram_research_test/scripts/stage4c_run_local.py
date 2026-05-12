import subprocess
import sys
from pathlib import Path

BASE    = Path(__file__).parent.parent
SCRIPTS = Path(__file__).parent

STEPS = [
    ("stage4c_check_inputs",        SCRIPTS / "stage4c_check_inputs.py"),
    ("stage4c_synthesize_highlight", SCRIPTS / "stage4c_synthesize_highlight.py"),
    ("stage4c_synthesize_account",   SCRIPTS / "stage4c_synthesize_account.py"),
    ("stage4c_create_final_report",  SCRIPTS / "stage4c_create_final_report.py"),
]

print("=" * 60)
print("Stage 4C — Local Synthesis + Final One-Account Report")
print("No OpenAI calls. No media downloads. Local only.")
print("=" * 60)

for step_name, script_path in STEPS:
    print(f"\n── {step_name} ──")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(BASE),
    )
    if result.returncode != 0:
        print(f"\nERROR: {step_name} exited with code {result.returncode}. Stopping.")
        sys.exit(result.returncode)

print("\n" + "=" * 60)
print("Stage 4C complete.")
print("=" * 60)
print("\nOutput files:")
print("  data/normalized/stage4c_inputs_check.json")
print("  analysis/stage4c/highlight_summary.json")
print("  analysis/stage4c/account_summary.json")
print("  report/final_one_account_analysis_vlada_kliuiko.md")
print("\nNext steps:")
print("  cat report/final_one_account_analysis_vlada_kliuiko.md")
print("  cat analysis/stage4c/highlight_summary.json")
print("  cat analysis/stage4c/account_summary.json")
