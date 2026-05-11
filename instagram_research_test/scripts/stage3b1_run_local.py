import subprocess
import sys
from pathlib import Path

BASE    = Path(__file__).parent.parent
SCRIPTS = Path(__file__).parent

print("Stage 3B-1: Prepare OpenAI inputs")
print("OpenAI API will NOT be called at this stage.")
print("=" * 60)

result = subprocess.run(
    [sys.executable, str(SCRIPTS / "stage3b1_prepare_openai_inputs.py")],
    cwd=BASE,
)

if result.returncode != 0:
    print(f"\n[STOPPED] stage3b1_prepare_openai_inputs.py exited with code {result.returncode}")
    sys.exit(result.returncode)

print("\n" + "=" * 60)
print("Stage 3B-1 complete.")
print(f"Preview JSON : data/normalized/stage3b1_openai_input_preview.json")
print(f"Preview report: report/stage_3b1_openai_input_preview.md")
print("=" * 60)
