# AB-07 — ablation round, doc 07 (queue engine)

First FAN-OUT round after the CAL-23 calibration. Full DISCOVERY loop (Chris,
2026-08-07), not the lighter trim+single-build: doc 32 §3 measures the atom as
adapter + dispatch + queue + rooms + spine + active_job, so dispatch/queue is the
first behavioral, invariant-dense section after the adapter.

## Base revisions (hardening rule 13)

| artifact | path | blob at trim time |
|---|---|---|
| DR section | `docs/dev/07-queue-engine.md` | `7d50709` |
| target source | `custom_components/eufy_vacuum/queue/queue_engine.py` | `1998538` |

Recompute both at apply time. Doc hash changed -> apply BLOCKED pending
three-way reconciliation. Target hash changed -> closure PROVISIONAL.
Net-shrink (rule 1) is measured against the LIVE file at apply time, not against
the 744-line snapshot.

## Apparatus (checked before the round, per the CAL-23 lesson)

CAL-23's examination suite was 81% white-box (35/43), which forced certification
onto 8 behavioral tests plus tester-authored pins. This one is materially
healthier:

| suite | tests | touch a `_private` name |
|---|---|---|
| `tests/unit/test_queue_engine.py` | 21 | 9 (43%) |
| `tests/integration/test_manager_queue.py` | 18 | 5 (28%) |

~25 behavioral tests, plus `test_manager_queue_breaks.py` and
`test_services_queue.py`. The examination can stand on the behavioral subset
without a special ruling.

## Budget

Trim budget N=3 (rule 6). B-repair cap 2 (rule 7). Discovery rounds need 2-of-2
fresh builders (rule 3); a clean first-pass trim may close on one.
