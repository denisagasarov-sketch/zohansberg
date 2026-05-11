import subprocess
import sys
from pathlib import Path

BASE    = Path(__file__).parent.parent
SCRIPTS = Path(__file__).parent

STEPS = [
    ("stage4a_check_inputs",    SCRIPTS / "stage4a_check_inputs.py"),
    ("stage4a_prepare_media",   SCRIPTS / "stage4a_prepare_media.py"),
    ("stage4a_create_openai_plan", SCRIPTS / "stage4a_create_openai_plan.py"),
    ("stage4a_create_report",   SCRIPTS / "stage4a_create_report.py"),
]

print("=" * 60)
print("Stage 4A — Full Media Preparation & OpenAI Plan")
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
print("Stage 4A complete.")
print("=" * 60)
print("\nOutput files:")
print("  data/normalized/stage4a_inputs_check.json")
print("  data/normalized/stage4a_media_manifest.json")
print("  data/normalized/stage4a_media_errors.json")
print("  data/normalized/stage4a_openai_plan.json")
print("  report/stage_4a_media_and_openai_plan.md")
print("\nNext: review report/stage_4a_media_and_openai_plan.md")
print("      then run Stage 4B when ready.")
