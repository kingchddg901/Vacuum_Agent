# MATERIALIZATION-01 — the five new reproducers (REVIEW-04 Pass-6 rule 7)

**Materialized and executed by the main agent, 2026-08-01, against frozen source at
master `c61b3eb`.** Every proof observed to fail FOR THE INTENDED REASON. The Sonnet
assignment precondition is satisfied.

## Invocation

The packets' `reproducer_command` shorthand (`docker eufy-vacuum-test → python …`)
requires one addition: **`-e PYTHONPATH=/workspace`**. A plain `python <script>` puts
the *script's* directory on `sys.path`, not the workspace root, so
`custom_components` doesn't resolve (pytest runs don't hit this — pytest adds
rootdir). Canonical form:

```
docker run --rm -v "C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager:/workspace" `
  -w /workspace -e PYTHONPATH=/workspace eufy-vacuum-test `
  python .claude/notes/_proof_<name>.py
```

(Docker via PowerShell, per feedback_docker_workdir.)

## Results — expected_before contracts, all met

| proof | packet | observed (verbatim fragments) | exit |
|---|---|---|---|
| `_proof_finalize_window.py` | RP-001 (+RP-002 base) | `BODY RAN 2 TIMES` · 2 completed_job results · forbidden fragments (`finalize_in_flight`/`already_finalized`) ABSENT | 0 |
| `_proof_manager_reload.py` | RP-003 | `no shutdown seam on EufyVacuumManager (checked async_shutdown, shutdown, async_close, async_unload)` · `stale manager saved after unload` · write order `['B', 'A']` | 0 |
| `_proof_rmw_conflation.py` | RP-006 | `store file replaced by the RMW: True` · `trouble_rooms rooms after RMW: 1` (from 9) — **bonus: the run emitted the real production WARNING `Ignoring malformed JSON … Extra data`, the exact SMB corruption mode write_json's docstring names** | 0 |
| `_proof_stale_dispatch.py` | RP-007 | `total miss dispatched stored ids: [5, 7]` · `partial miss skipped B` (partial path correct pre-repair, as the packet states) | 0 |
| `_proof_blocker_unavailable.py` | RP-008 | `not_equals 'closed' vs unavailable -> matched=True` (and unknown) · `cancel fired on unavailable` | 0 |

## Validity traps honored

- **RP-001** (the REVIEW-04 trap): task B blocks on an event task A sets **after A has
  fully returned** — the claim is already released by A's `finally`, `finalized` not
  yet written (the caller writes it after lifecycle.py L334's executor hop). A body-
  concurrent B would only exercise the in-flight refusal and pass for the wrong
  reason. Verified in output: no refusal fragments appeared.
- **RP-003**: the stale write goes through the real `async_save` on a real
  `EufyVacuumManager`; the shutdown probe checks four candidate seam names so the
  script flips to `stale save suppressed` + `timers cancelled:` when RP-003's
  `async_shutdown`/`_closed` land.
- **RP-006**: corruption is *recoverable* (trailing garbage after valid JSON), so the
  post-repair path can honestly print `rooms after RMW: 9` by showing the store file
  was NOT replaced and its 9 rooms survive in the bytes.
- **RP-007**: drives the real `_resolve_live_dispatch_payload`; stubs only the room
  source (module-attribute patch — the function imports at call time). Repaired code
  raising on total miss is caught and printed as `total miss refused: <msg>`.
- **RP-008**: behavior half drives the real `_room_rule_matches`; the action half is a
  source assertion that `path_blockers._process` has no known-state re-check between a
  blocked report and `async_cancel_active_job` (it flips when the repair adds one, or
  when INDETERMINATE lands in the evaluator).

## Post-repair flip contracts (the same scripts, unedited)

Each script prints the packet's `expected_after` fragments when the repaired behavior
is observed, and exits 1 on any UNEXPECTED SHAPE — so Sonnet runs the identical
command before and after, and the output diff IS the closure evidence.

## Existing artifacts attached, not recreated

- `_proof_setup.py` → RP-005, RP-009 (DR-SETUP-1's proven harness)
- `_proof_debug.py` → RP-004 (the record's own executed repro)
- `_proof_battery.py` remains the cautionary example; nothing in tranche 1 touches it.
