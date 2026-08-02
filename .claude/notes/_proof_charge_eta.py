"""Proof RP-043 + RP-044 (RF-36 parts 2 and 3) — what the charge ETA divides by.

compute_time_to_target_pct PREFERS the learned baseline and treats the live zone rate
as the degraded fallback. Empirically that precedence is backwards for this consumer:

  RP-043 case 1. FROZEN BASELINE WINS. _update_health anchors cc/cv_min_per_pct only
    when they are None and NEVER re-anchors, so the baseline is fixed at whatever the
    first qualifying session measured — for alfred, one session on 2026-06-08. Every
    alfred ETA since has divided by a two-month-old rate and will keep doing so as the
    cell ages. A live zone rate sitting in the same record, measured minutes ago, is
    ignored.

  RP-043 case 2. AND IT CANNOT CONVERGE. Move the live rate as far as you like — the
    answer does not budge, because the baseline branch returns before the rate is ever
    read. The preferred path cannot converge at all, while the fallback converged in
    ONE sample on live hardware ("the first live sample overwrote
    rate_high_zone_per_min and the estimate became very very close").

  RP-044 case 3. THE FIRST ETA OF A CHARGE IS THE WORST ONE. With no baseline the
    zone_rate path divides by rate_high_zone_per_min left over from a PREVIOUS,
    unrelated charge. Ivy's stored value was 1.0004 %/min from a 1-minute 99->100
    blip. The user's first number is systematically the least trustworthy on screen
    and nothing distinguishes it from the accurate ones that follow.

The fix is a PRECEDENCE change, not a re-anchoring one. RP-043's prohibited_changes is
explicit: the baseline must stay fixed because it is also the "when new" reference that
cc/cv_charge_speed_pct are measured against, and that cannot be recovered once lost.
One field serving two masters with opposite requirements; the ETA is the one that must
give way. So case 1's after-check asserts the ETA stops using the baseline while a
fresh rate exists — NOT that the baseline changed.

Case 3's after-check is `minutes is None`. That is the documented cold-start contract:
the card shows a live wall-clock instead of a fabricated number. RP-044 says to reuse
that path and explicitly not to invent a "provisional" state, so the proof pins None
rather than any new third value.

Live evidence, 2026-08-01 (RP-043 evidence_live): ivy has no baseline (cc/cv null,
session_count 0 after 50 sessions — it never runs below 50%, so nothing qualifies), so
its ETA took the zone_rate fallback. First paint quoted a carried-over rate and was
well off; the first live sample of the current charge fixed it.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_charge_eta.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.battery.manager import (   # noqa: E402
    BatteryHealthManager,
)

VAC = "vacuum.alfred"


def _manager(*, baseline: dict, stats: dict, current_session=None) -> BatteryHealthManager:
    """A manager whose get_record returns exactly the record under test."""
    mgr = BatteryHealthManager.__new__(BatteryHealthManager)
    mgr._hass = None
    mgr._config_dir = "/tmp"
    mgr._save_cb = lambda: None
    mgr._listeners = []
    mgr._pending_post_job = {}
    mgr._notify = lambda v: None
    mgr._schedule_save = lambda: None
    record = {
        "stats": dict(stats),
        "baseline": dict(baseline),
        "session_history_recent": [],
        "current_session": current_session,
        "last_charging": current_session is not None,
    }
    mgr._data = {"battery": {"vacuums": {VAC: record}}}
    mgr.ensure_record = lambda vacuum_entity_id: record   # type: ignore[method-assign]
    mgr._record = record
    return mgr


def _eta(mgr, cur=85, tgt=100) -> dict:
    return mgr.compute_time_to_target_pct(
        vacuum_entity_id=VAC, current_pct=cur, target_pct=tgt
    )


# alfred's real anchor, 2026-06-08. min_per_pct, so BIGGER = slower.
FROZEN = {"cc_min_per_pct": 2.6214, "cv_min_per_pct": 2.6262,
          "session_count": 1, "anchored_at": "2026-06-08T04:00:00Z"}
# A live rate measured during THIS charge: 0.55 %/min == 1.82 min/pct, notably
# faster than the two-month-old anchor.
FRESH_RATE = {"rate_high_zone_per_min": 0.55, "rate_low_zone_per_min": 0.55,
              "rate_overall_per_min": 0.55}


def case_frozen_baseline_beats_a_live_rate(proof: H.Proof) -> None:
    mgr = _manager(baseline=FROZEN, stats=FRESH_RATE)
    got = _eta(mgr)
    from_baseline = round(15 * 2.6262, 1)     # 39.4 min
    from_live = round(15 / 0.55, 1)           # 27.3 min

    proof.case(
        "a two-month-old baseline and a rate measured during THIS charge disagree",
        before=got["source"] == "baseline" and abs(got["minutes"] - from_baseline) < 0.2,
        before_msg="eta from frozen baseline — the anchor from 2026-06-08 wins over a "
                   "rate measured minutes ago, and it will keep winning as the cell ages",
        after=got["source"] != "baseline" and abs(got["minutes"] - from_live) < 0.2,
        after_msg="eta prefers the fresh zone rate; the baseline stays fixed and keeps "
                  "feeding battery health, which is the role it must not lose",
        detail=f"eta={got} · baseline would give {from_baseline} min · "
               f"live rate would give {from_live} min",
    )


def case_eta_cannot_converge(proof: H.Proof) -> None:
    """Move the live rate a long way and see whether the answer notices."""
    slow = _eta(_manager(baseline=FROZEN, stats={"rate_high_zone_per_min": 0.30,
                                                 "rate_overall_per_min": 0.30}))
    fast = _eta(_manager(baseline=FROZEN, stats={"rate_high_zone_per_min": 0.90,
                                                 "rate_overall_per_min": 0.90}))

    proof.case(
        "the live zone rate triples (0.30 -> 0.90 %/min) mid-charge",
        before=slow["minutes"] == fast["minutes"],
        before_msg="eta unchanged as live rate moves — the baseline branch returns "
                   "before the rate is read, so the preferred path cannot converge "
                   "while the fallback converges in one sample",
        after=slow["minutes"] != fast["minutes"] and fast["minutes"] < slow["minutes"],
        after_msg="eta tracks the observed rate — a faster charge reports fewer minutes",
        detail=f"at 0.30 %/min -> {slow} · at 0.90 %/min -> {fast}",
    )


def case_first_eta_uses_a_previous_charges_rate(proof: H.Proof) -> None:
    """RP-044 — no baseline, and the only rate on record belongs to another session."""
    # ivy's real stored value: 1.0004 %/min, left over from a 1-minute 99->100 blip.
    stale = {"rate_high_zone_per_min": 1.0004, "rate_low_zone_per_min": 1.0004,
             "rate_overall_per_min": 1.0004}
    # A charge that has just opened: the session exists but has produced no rate yet.
    just_opened = {"start_ts": "2026-08-01T22:00:00Z", "start_battery": 85,
                   "samples": 1, "rate_sum": 0.0, "rate_min": None, "rate_max": None,
                   "kind": "dock"}
    got = _eta(_manager(baseline={}, stats=stale, current_session=just_opened))
    session_has_no_sample_of_its_own = not just_opened["rate_sum"]

    proof.case(
        "first paint of a new charge; the only rate on record is a previous session's "
        "1-minute 99->100 blip",
        before=session_has_no_sample_of_its_own and got["minutes"] is not None
        and got["source"] == "zone_rate",
        before_msg="first eta from the previous session's rate — the number the user "
                   "sees first is the one least entitled to be believed, and nothing "
                   "marks it as different from the accurate ones that follow",
        after=session_has_no_sample_of_its_own and got["minutes"] is None
        and got["source"] is None,
        after_msg="first eta None -> the card's documented wall-clock cold-start, then "
                  "a live number once THIS session has sampled its own rate",
        detail=f"eta={got} · carried rate=1.0004 %/min · this session's rate_sum="
               f"{just_opened['rate_sum']} (no sample of its own yet)",
    )


def main() -> None:
    proof = H.Proof("RP-043/044", "what the charge ETA divides by")
    case_frozen_baseline_beats_a_live_rate(proof)
    case_eta_cannot_converge(proof)
    case_first_eta_uses_a_previous_charges_rate(proof)
    proof.finish()


H.run(main)
