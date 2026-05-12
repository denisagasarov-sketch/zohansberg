import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
SCRIPTS = Path(__file__).parent

steps = [
    ("Check raw inputs",      SCRIPTS / "stage3a_check_raw_inputs.py"),
    ("Download media sample", SCRIPTS / "stage3a_download_media_sample.py"),
    ("Create report",         SCRIPTS / "stage3a_create_report.py"),
]

for label, script in steps:
    print(f"\n{'='*60}")
    print(f"Step: {label}")
    print('='*60)
    result = subprocess.run([sys.executable, str(script)], cwd=BASE)
    if result.returncode != 0:
        print(f"\n[STOPPED] {label} exited with code {result.returncode}")
        sys.exit(result.returncode)

print(f"\n{'='*60}")
print("Stage 3A complete.")
print(f"Report: report/stage_3a_media_download_test_report.md")
print('='*60)
