#!/usr/bin/env bash
set -euo pipefail
REPO="$HOME/zohansberg-instagram-test"
PFX="instagram_research_test"
TIER="${TIER:-0}"
TAG="pre-cleanup-$(date +%Y%m%d-%H%M%S)"
cd "$REPO"
echo "=== CLEANUP DEAD STAGES TIER=$TIER (root=$REPO) ==="
if ! git rev-parse --git-dir >/dev/null 2>&1; then echo "[STOP] not a git repo"; exit 1; fi
if [ -n "$(git status --porcelain | grep -vE '^\?\?')" ]; then echo "[STOP] working tree NOT clean (tracked changes):"; git status --short | grep -vE '^\?\?'; echo "Commit or stash first."; exit 1; fi
echo "[OK] working tree clean (untracked ignored)"
T1=$(git ls-files "$PFX/scripts/stage3*" "$PFX/scripts/stage4*")
T2C=$(git ls-files "$PFX/scripts/stage5c_analyze_stories.py" "$PFX/scripts/stage5c_run_local.py" "$PFX/scripts/stage5c_create_report.py" || true)
T2B=$(git ls-files "$PFX/scripts/stage5b_auto_*" || true)
T3=$(git ls-files "$PFX/scripts/stage5a0_actor_profile_schema_check.py" "$PFX/scripts/stage5a2a_*" "$PFX/scripts/stage5b0_check_highlight_id_compatibility.py" || true)
DC=$(git ls-files "$PFX/report/stage_5c_*" || true)
DB=$(git ls-files "$PFX/report/stage_5b_auto_*" || true)
T=""
[ "$TIER" -ge 1 ] && T="$T $T1"
[ "$TIER" -ge 2 ] && T="$T $T2C $T2B $DC $DB"
[ "$TIER" -ge 3 ] && T="$T $T3"
TARGETS=$(echo "$T" | tr ' ' '\n' | grep -v '^$' | sort -u)
echo "=== FILES TO DELETE (TIER=$TIER) ==="
if [ -z "$TARGETS" ]; then echo "(empty - normal for TIER=0)"; else echo "$TARGETS"; echo "--- total: $(echo "$TARGETS" | wc -l | tr -d ' ') ---"; fi
if [ "$TIER" -eq 0 ]; then echo "[DRY] TIER=0 preview only. Nothing deleted."; echo "If OK run: TIER=1 bash cleanup_v2.sh"; exit 0; fi
echo "Backup tag: $TAG  (rollback: git reset --hard $TAG)"
printf "Continue? [yes/NO]: "
read -r ANS
if [ "$ANS" != "yes" ]; then echo "Cancelled."; exit 0; fi
git tag -a "$TAG" -m "Snapshot before cleanup TIER=$TIER"
echo "[OK] tag $TAG"
echo "$TARGETS" | while read -r f; do [ -z "$f" ] && continue; git rm -q "$f"; echo "  removed: $f"; done
echo "DONE. Next: python3 $PFX/scripts/run_pipeline.py --account vlada_kliuiko --dry-run --skip-apify ; then git commit"
