import subprocess
import sys
from pathlib import Path

BASE    = Path(__file__).parent.parent
SCRIPTS = Path(__file__).parent

print("Stage 3B-2: OpenAI analysis call")
print("Uses model: gpt-4.1-mini")
print("=" * 60)

result = subprocess.run(
    [sys.executable, str(SCRIPTS / "stage3b2_analyze_with_openai.py")],
    cwd=BASE,
)

if result.returncode != 0:
    print(f"\n[STOPPED] stage3b2_analyze_with_openai.py exited with code {result.returncode}")
    sys.exit(result.returncode)

print("\n" + "=" * 60)
print("Stage 3B-2 complete.")
print(f"Report: report/stage_3b2_openai_analysis_test_report.md")
print(f"Analysis files:")
print(f"  analysis/content_analysis_test.json")
print(f"  analysis/highlights_analysis_test.json")
print(f"  analysis/openai_responses/post_analysis_response.json")
print(f"  analysis/openai_responses/highlight_analysis_response.json")
print("=" * 60)
