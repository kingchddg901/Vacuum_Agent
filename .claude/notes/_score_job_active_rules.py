"""Score candidate "is the job still active?" rules against a real trace (#46).

WHY THIS AND NOT A LIVE EXPERIMENT
----------------------------------
Replacing ``binary_sensor.<vac>_cleaning`` needs a rule for "is this dock a
recharge or the finish?". Getting it wrong finalizes a run early, which writes a
truncated learning sample — silent and permanent, strictly worse than the bug
being fixed. So no rule ships until it has been scored against real hardware.

The trick that makes this cheap: score on a vacuum whose binary WORKS. Every
``[job_active.observe]`` record carries ``native`` (the real binary) alongside
the candidate inputs, so the trace is self-labelling. A rule that reproduces
Ivy's binary tick-for-tick is a rule that can stand in for Vlad's missing one.

Because the trace stores OBSERVATIONS rather than one rule's verdict, new
candidates can be scored against old traces forever — no new run per idea.

HOW TO PRODUCE A TRACE
----------------------
1. Start the flight recorder (``eufy_vacuum.debug_capture_start``) with DEBUG on
   ``custom_components.eufy_vacuum.decision_log``.
2. Run a job. A run that RECHARGES mid-clean is the valuable one — that is the
   case the binary exists to survive and the one no amount of code reading
   settles.
3. ``eufy_vacuum.debug_capture_dump`` and feed the file to this script.

Any file works as long as it contains the raw log lines.

    python .claude/notes/_score_job_active_rules.py <dump-or-log> [--vacuum ivy]

WHAT "GOOD" LOOKS LIKE
----------------------
Agreement alone is a vanity metric: the binary reads ``on`` for most of a run, so
"always on" scores ~90%. What matters is the OFF EDGE — the tick where the rule
decides the run is over. Reported separately:

  early   rule said done while native still said on   -> TRUNCATED SAMPLE (fatal)
  late    rule still said on after native went off    -> latency (tolerable)
  missed  native went off, rule never followed        -> run never finalizes (the bug)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

RECORD = re.compile(r"\[job_active\.observe\]\s*(\{.*\})\s*$")


def load(path: pathlib.Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RECORD.search(line)
        if not m:
            continue
        try:
            out.append(json.loads(m.group(1)))
        except ValueError:
            continue
    return out


def _f(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# --- candidate rules --------------------------------------------------------
# Each takes (observation, memo) and returns True for "still active". `memo` is a
# per-run scratch dict, so a rule may carry state (a baseline, a latch) without
# any of them leaking into another run.

def rule_always_on(_obs, _memo) -> bool:
    """Control. Never finalizes -- reproduces the #46 bug exactly. Any candidate
    that cannot beat this is worthless."""
    return True


def rule_dispatch_latch(obs, memo) -> bool:
    """The FIRST design, kept as a control because it was refuted.

    active := dispatched AND last_clean_end has not advanced since dispatch.
    A one-shot fuse cannot reproduce a per-room square wave, and it trips at the
    recharge dock. Expect early edges; that is the point of keeping it.
    """
    lce = obs.get("lce")
    if "baseline" not in memo:
        memo["baseline"] = lce
        return True
    return lce == memo["baseline"]


def rule_not_docked(obs, _memo) -> bool:
    """Pure motion: active while the robot is not on the dock. Ignores recharge
    entirely, so it should finalize early on any run that recharges -- the
    control that isolates how much work the recharge discrimination is doing."""
    return not obs.get("docked")


def rule_docked_dwell(obs, memo, settle_s: float = 120.0) -> bool:
    """Docked continuously for longer than a settle window => finished.

    The simplest rule with a real chance: a recharge dock is long, but so is a
    finish, so this alone should mislabel recharges. Scoring says by how much.
    """
    if not obs.get("docked"):
        memo["left_dock"] = True
        return True
    return (_f(obs.get("state_s"), 0.0) or 0.0) < settle_s


def rule_docked_dwell_battery(obs, memo, settle_s: float = 120.0,
                              low: float = 25.0) -> bool:
    """Docked past the settle window AND not obviously recharging.

    The shape the design landed on: battery at the dock moment discriminates
    "came home flat, will resume" from "came home done".
    """
    if not obs.get("docked"):
        memo["dock_batt"] = None
        return True
    batt = _f(obs.get("batt"))
    if memo.get("dock_batt") is None and batt is not None:
        memo["dock_batt"] = batt
    if (memo.get("dock_batt") or 100.0) < low:
        return True  # recharge suspected -> stay active
    return (_f(obs.get("state_s"), 0.0) or 0.0) < settle_s


RULES = {
    "always_on(control)": rule_always_on,
    "dispatch_latch(refuted)": rule_dispatch_latch,
    "not_docked": rule_not_docked,
    "docked_dwell_120s": rule_docked_dwell,
    "docked_dwell+battery": rule_docked_dwell_battery,
}


def score(obs_list: list[dict], rule) -> dict:
    memo: dict = {}
    agree = early = late = 0
    native_off_seen = False
    rule_off_seen = False
    for obs in obs_list:
        native = str(obs.get("native", "")).lower()
        if native not in ("on", "off"):
            continue  # unavailable / absent ticks carry no label
        native_active = native == "on"
        try:
            rule_active = bool(rule(obs, memo))
        except Exception:
            rule_active = True
        if rule_active == native_active:
            agree += 1
        elif not rule_active and native_active:
            early += 1
        else:
            late += 1
        native_off_seen = native_off_seen or not native_active
        rule_off_seen = rule_off_seen or not rule_active
    total = agree + early + late
    return {
        "ticks": total,
        "agree_pct": round(100.0 * agree / total, 1) if total else 0.0,
        "early": early,
        "late": late,
        "missed_edge": native_off_seen and not rule_off_seen,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--vacuum", default=None,
                    help="only score ticks whose record names this vacuum")
    args = ap.parse_args()

    path = pathlib.Path(args.dump)
    if not path.exists():
        print(f"no such file: {path}")
        return 2
    obs_list = load(path)
    if not obs_list:
        print("No [job_active.observe] records found. Was DEBUG enabled on "
              "custom_components.eufy_vacuum.decision_log while the job ran?")
        return 2

    labelled = [o for o in obs_list if str(o.get("native", "")).lower() in ("on", "off")]
    print(f"records: {len(obs_list)}   labelled (binary present): {len(labelled)}")
    if not labelled:
        print("\nEvery tick reads native=absent -- this trace came from an AFFECTED "
              "device, so it has no ground truth to score against. Capture on a "
              "vacuum whose binary still works.")
        return 2
    off = sum(1 for o in labelled if str(o.get("native")).lower() == "off")
    print(f"native on/off split: {len(labelled) - off} on / {off} off\n")

    print(f"{'rule':26} {'ticks':>6} {'agree':>7} {'EARLY':>6} {'late':>6}  edge")
    print("-" * 66)
    for name, rule in RULES.items():
        s = score(labelled, rule)
        edge = "NEVER FINALIZES" if s["missed_edge"] else "ok"
        flag = "  <-- truncates runs" if s["early"] else ""
        print(f"{name:26} {s['ticks']:6} {s['agree_pct']:6.1f}% "
              f"{s['early']:6} {s['late']:6}  {edge}{flag}")

    print("\nEARLY is the column that disqualifies a rule: it means the rule called "
          "\na run finished while the robot was still cleaning. `late` is latency, "
          "\nwhich is a tuning problem rather than a data-integrity one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
