# HANDOFF → Opus session: the group phase "won't advance" — stop debugging, execute RP-047

**Written 2026-08-02 (Fable session, live diagnosis with Chris). You were trying to get the
live queue to advance Entryway → Home Office during run `pj_2026-08-02T23-04-45`. There is no
bug to find in the advance path. Read this before touching it again.**

## The ruling (it is already yours)

`a193eae`'s own commit message states the mechanism: **"The mechanism is not a bug in the
advance; it is that there is nothing to advance."** A group phase is ONE dispatch. No per-room
rollover signal exists on Eufy: `record_completed_room` never fires mid-group,
`completed_room_ids` stays `[]`, and the card's live derivation (first resolved room not in
per-phase completed ids) pins to room[0] for the phase's whole duration. Pose samples
(`active_job.py:1897`) buffer for FINALIZE-time attribution only — deliberately not wired to
claim live completions; synthesizing an "Entryway done" boundary is the same invention the
RP-013c REVIEW pin forbids, and the packet text forbids it explicitly.

## Why it looked like a regression: RP-047 was never executed

`git show --stat a193eae` → **only** `SYNTH-12-packets-battery.md` (+72 lines). It is the
packet SPEC with an `RP-047:` subject. `git grep current_room_ids -- custom_components/` →
zero hits. Live deploy == repo working tree (hashes checked), so this is not a stale deploy
either. Every ledger that said "RP-047 landed" was fooled by the subject line — corrected in
the audit-2 charter (`671a5c9`) and central memory. Verify landings with `git show --stat`
showing code files changed, never by subject.

## Live evidence snapshot (2026-08-02 ~23:16 local)

`.storage/eufy_vacuum.storage` → `active_jobs."vacuum.alfred"."12"`:
- `phased_job_id pj_2026-08-02T23-04-45`, `current_phase_index 2` of 3 — phases 0 (Kitchen,
  child-finalized) and 1 (wait 1 min) advanced ON TIME; phase advancement itself is healthy.
- Phase 2 payload carries BOTH rooms 8+9 in one dispatch; `completed_room_ids []`;
  `current_room_id 8` pinned while the robot was visibly in room 9 on the map.
- Card showed "Entryway 99% · ~0 min · Low" — that ETA is Entryway-solo math applied to a
  two-room phase; it becomes phase-level with the same fix.

## What to do

1. **Execute RP-047 as specced** (spec: SYNTH-12-packets-battery.md, RP-047 block + the
   a193eae commit message): snapshot exposes `current_room_ids` (list) + a `current_phase`
   block; `current_room_id` keeps its meaning as the map anchor. Card renders a group phase
   as ONE active entry via `Intl.ListFormat` (conjunction is locale grammar — no hardcoded
   " + "; i18n at creation per standing rule).
2. **Write the named proof** `_proof_group_live_progress.py` — the single missing proof in
   the campaign (`_gen_repro_status.py` confirms). Flip criterion: a 2-room group phase's
   live snapshot must present the phase, not room[0].
3. Optional, Chris's call, NOT part of RP-047: a display-only "robot is currently in X"
   indicator driven by pose containment — allowed only if it never marks a room completed.

Boundary note: the Fable session changed NO code — jobs/, queue/, learning/ untouched; the
run record was read as evidence only. Your in-flight working tree was left alone.
