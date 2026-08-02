"""Proof RP-021a (RF-35 part 1; Q17) — a leading charge_wait is saved, shown, and never runs.

RP-021a's reproducer_script names four recipes. The all-blocked-plan IndexError is already
driven by `_proof_empty_phase_crash.py`; this drives the leading-break pair, which is
clause (1) and the one Q17 answered VERBATIM. The zone-first room_count and engine-envelope
recipes are NOT driven here — both need real brand dispatch rather than a stub, and
stubbing dispatch is exactly what would make them prove nothing.

The defect is the two halves disagreeing, so both are driven against real code:

  1. SAVE ACCEPTS IT. normalize_run_profile_steps validates and coerces every step, and has
     no opinion about a break arriving first. The profile stores
     [charge_wait, room_group] and the card renders both.

  2. BUILD SILENTLY DROPS IT. _build_steps_phases pops leading and trailing break phases
     (planning/run_plan.py:914-917) with no log and no note. Two steps in, one phase out,
     and nothing anywhere records that a step the user authored was discarded.

Net: the card shows a step that will never run, and no surface tells the user. Q17's answer
is that a leading break is UNSUPPORTED — reject it at SAVE with
ServiceValidationError(reason=leading_break_unsupported) rather than accept-then-drop. The
after-arm therefore pins a raise on the save half; case 2's after-arm pins that whatever
still reaches the builder is normalized WITH a record, never silently.

The legacy-stored normalization note (`normalized_steps` in the plan) is a second clause and
is NOT pinned here — it belongs with the plan-assembly caller, not with the phase list this
function returns.

_build_dispatch_phases is stubbed to one well-formed room phase. That is inert scaffolding:
it supplies a dispatch result so the trim has something to bracket. The trim under test is
real production code and is not simulated.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_plan_structure.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager   # noqa: E402
from custom_components.eufy_vacuum.profiles.manager import ProfileManager   # noqa: E402

LEADING = [
    {"type": "charge_wait", "target_battery_percent": 80},
    {"type": "room_group", "rooms": [{"room_id": 5}]},
]


def case_save_accepts_a_leading_break(proof: H.Proof) -> None:
    raised = None
    try:
        normalized = ProfileManager.normalize_run_profile_steps(LEADING)
    except Exception as err:      # the repaired behaviour
        normalized, raised = None, err

    kept_leading = bool(normalized) and normalized[0].get("type") == "charge_wait"
    reason = getattr(raised, "translation_key", None) or str(raised or "")

    proof.case(
        "saving a profile whose FIRST step is a charge_wait",
        before=raised is None and kept_leading,
        before_msg="accepted at save — the normalizer has no opinion about a break "
                   "arriving first, so the profile stores it and the card renders it",
        after=raised is not None and "leading_break_unsupported" in reason,
        after_msg="refused at save with leading_break_unsupported, per Q17 — a leading "
                  "break is unsupported, so it never gets stored to be dropped later",
        detail=f"raised={type(raised).__name__ if raised else None} · reason={reason!r} "
               f"· normalized={normalized!r}",
    )


def case_build_drops_it_without_a_trace(proof: H.Proof) -> None:
    planner = RunPlanManager.__new__(RunPlanManager)
    planner._manager = H.ManagerStub()
    # Inert: give the trim a real clean phase to bracket. The trim itself is production.
    planner._build_dispatch_phases = lambda **kw: [{
        "phase_type": "room_group", "room_count": 1,
        "resolved_rooms": [{"room_id": 5}], "queue_room_ids": [5],
        "queue_rooms": [], "payload": {},
    }]

    phases = planner._build_steps_phases(
        vacuum_entity_id=H.VAC, map_id=H.MAP,
        effective_rooms={"5": {"room_id": 5}}, included_room_ids={5},
        run_steps=LEADING, strict_order=False,
    )
    types = [p.get("phase_type") for p in phases]
    leading_survived = types[:1] == ["charge_wait"]
    # Any record at all that a user-authored step was removed.
    trace = any(
        "normaliz" in str(key).lower() or "dropped" in str(key).lower()
        for p in phases for key in p
    )

    proof.case(
        "building phases from [charge_wait, room_group]",
        before=not leading_survived and len(phases) == 1 and not trace,
        before_msg="silently dropped — two authored steps in, one phase out, and nothing "
                   "in the result records that the charge step was discarded; the card "
                   "keeps showing a step that will never run",
        after=trace or leading_survived,
        after_msg="the removal is recorded rather than silent (or the step is never "
                  "stored in the first place, per case 1)",
        detail=f"steps in={[s['type'] for s in LEADING]} · phases out={types} · "
               f"removal recorded anywhere={trace}",
    )


def main() -> None:
    proof = H.Proof("RP-021a", "a leading charge_wait is saved, shown, and never runs")
    case_save_accepts_a_leading_break(proof)
    case_build_drops_it_without_a_trace(proof)
    proof.finish()


H.run(main)
