# REPRODUCER STATUS -- generated, do not hand-edit

Regenerate: `python .claude/notes/_gen_repro_status.py`. Every number here is
derived from the packet blocks and the files on disk. **Do not copy these counts
into prose elsewhere** -- link to this file instead. The handoff doc used to
hardcode a reproducer count and it drifted badly enough to misscope a stage.

| | |
|---|---|
| Packets parsed | 60 across 9 docs |
| Distinct proofs named by packets | 44 |
| Proof files on disk | 49 (incl. `_proof_harness.py`, which is scaffolding, not a proof) |
| Packets with every named proof present | 38 |
| Packets missing a named proof | **11** |
| Packets naming no proof at all | 11 |
| Distinct proof files still to write | **10** |

**Every landed packet has its named reproducer present.** Nothing shipped
without evidence; the outstanding files all belong to unexecuted packets.

---

## Outstanding -- named by a packet, absent from disk

| packet | doc | missing proof | packet landed? |
|---|---|---|---|
| RP-021a | SYNTH-08-packets-wave4.md | `_proof_plan_structure.py` | no |
| RP-026 | SYNTH-09-packets-wave5.md | `_proof_map_identity.py` | no |
| RP-030 | SYNTH-09-packets-wave5.md | `_proof_mapping_batch.py` | no |
| RP-031 | SYNTH-10-packets-wave6.md | `_proof_service_contract.py` | no |
| RP-034 | SYNTH-10-packets-wave6.md | `_proof_theme_semantics.py` | no |
| RP-035 | SYNTH-10-packets-wave6.md | `_proof_platform_batch.py` | no |
| RP-037 | SYNTH-10-packets-wave6.md | `_proof_loop_hygiene.py` | no |
| RP-042 | SYNTH-12-packets-battery.md | `_proof_battery_unknown.py` | no |
| RP-043 | SYNTH-12-packets-battery.md | `_proof_charge_eta.py` | no |
| RP-044 | SYNTH-12-packets-battery.md | `_proof_charge_eta.py` | no |
| RP-045 | SYNTH-12-packets-battery.md | `_proof_battery_health.py` | no |

## Orphans -- on disk, named by no packet

Not a defect. These are direct-read and ad-hoc investigations, plus NAMING DRIFT:
a packet naming `_proof_map_identity.py` may already be served by
`_proof_map_source_identity.py`. **Check this list before writing a missing proof**
-- the work may exist under another name, in which case fix the packet's text.

- `_proof_battery.py`
- `_proof_debug.py`
- `_proof_diagnostics_redaction.py`
- `_proof_empty_phase_crash.py`
- `_proof_ensure_dirs_memo.py`
- `_proof_flip_y_disagreement.py`
- `_proof_map_source_identity.py`
- `_proof_onboarding.py`
- `_proof_overlays_availability.py`
- `_proof_reject_rooms_map_scope.py`
- `_proof_run_errors_index.py`
- `_proof_service_refusal_ordering.py`
- `_proof_theme_overwrite_source.py`
- `_proof_wipe_guard.py`

