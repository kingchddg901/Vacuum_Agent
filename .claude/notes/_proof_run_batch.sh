# Run the Stage X execution-release proofs and print one verdict line each.
#   docker run --rm -v "<repo>:/workspace" -w /workspace -e PYTHONPATH=/workspace \
#     eufy-vacuum-test bash .claude/notes/_proof_run_batch.sh
# Pass proof names as args to run a different set; default is the Stage X five.
set -u
PROOFS="${*:-group_allocation job_cleaning_total recorder_scope phase_validity completed_evidence}"
rc_all=0
for p in $PROOFS; do
  out=$(python ".claude/notes/_proof_$p.py" 2>&1)
  rc=$?
  line=$(printf '%s\n' "$out" | grep -E '^=== .*cases')
  [ "$rc" -ne 0 ] && rc_all=1
  printf '[rc=%s] %s\n' "$rc" "${line:-NO VERDICT LINE — proof crashed}"
done
exit "$rc_all"
