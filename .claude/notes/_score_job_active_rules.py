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


def load_history_csv(path: pathlib.Path, vacuum: str) -> list[dict]:
    """Reconstruct observation records from an HA History CSV export.

    Lets a rule be scored against ANY window already in the recorder, not only
    against a run captured after the observation trace shipped. That matters for
    the recharge case specifically: a recharge is slow and awkward to stage on
    purpose, but if one ever occurred in a retained window, the export scores
    exactly like a live trace.

    HA's export is sparse (one row per state CHANGE), so states are forward
    filled onto a shared timeline — which is what the live tick would have seen.
    """
    import csv
    import datetime as dt

    rows = list(csv.DictReader(
        open(path, newline="", encoding="utf-8-sig")))
    want = {
        "native": f"binary_sensor.{vacuum}_cleaning",
        "vac": f"vacuum.{vacuum}",
        "task": f"sensor.{vacuum}_status",
        "batt": f"sensor.{vacuum}_battery",
        "area": f"sensor.{vacuum}_cleaning_area",
        "ctime": f"sensor.{vacuum}_cleaning_time",
        "lce": f"sensor.{vacuum}_last_clean_end",
        "count": f"sensor.{vacuum}_total_cleaning_count",
    }
    by_entity = {v: k for k, v in want.items()}

    events = []
    for r in rows:
        eid = r.get("entity_id")
        if eid not in by_entity:
            continue
        try:
            when = dt.datetime.fromisoformat(
                str(r["last_changed"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        events.append((when, by_entity[eid], str(r.get("state", "")).strip()))
    events.sort()

    docked_states = {"docked", "returning", "returning_to_dock"}
    blank = {"", "unknown", "unavailable", "none", "null"}
    cur: dict = {}
    vac_since: dt.datetime | None = None
    out: list[dict] = []
    for when, field, value in events:
        if field == "vac" and value != cur.get("vac"):
            vac_since = when
        cur[field] = value
        obs = {k: (None if str(v).lower() in blank else v) for k, v in cur.items()}
        obs["native"] = (cur.get("native") or "absent")
        vac = (cur.get("vac") or "").lower()
        obs["docked"] = vac in docked_states
        obs["state_s"] = (
            round((when - vac_since).total_seconds(), 1) if vac_since else None
        )
        obs["_t"] = when.isoformat()
        obs["_when"] = when
        out.append(obs)
    return out


def restrict_to_job_windows(obs_list: list[dict], vacuum: str) -> list[dict]:
    """Keep only ticks that fall inside a real run, per the stored job records.

    WHY THIS IS NOT OPTIONAL. The live observation trace is emitted from inside
    the lifecycle listener's active-job loop, so it only ever contains ticks
    while a job is live. A raw History export contains everything -- including
    overnight docked stretches many hours long. Scoring a rule over those is
    scoring it on input it will never be given, and it is not a small effect:
    the idle ticks outnumber the in-run ticks and every rule's numbers are
    dominated by them.

    Job windows come from the learning store's own records, which are
    independent of every signal under test.
    """
    import datetime as dt
    import json

    jobs_dir = pathlib.Path(
        f"//192.168.4.104/config/eufy_vacuum/learning/{vacuum}/jobs")
    windows: list[tuple] = []
    if jobs_dir.exists():
        for p in sorted(jobs_dir.glob("job_*.json")):
            try:
                job = (json.loads(p.read_text(encoding="utf-8",
                                              errors="replace")).get("job") or {})
                s, e = job.get("started_at"), job.get("ended_at")
                if s and e:
                    windows.append((
                        dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")),
                        dt.datetime.fromisoformat(str(e).replace("Z", "+00:00")),
                    ))
            except Exception:
                continue
    if not windows:
        return obs_list, []

    kept = [o for o in obs_list
            if o.get("_when") and any(s <= o["_when"] <= e for s, e in windows)]
    return kept, windows


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


def rule_left_dock_then_dwell(obs, memo, settle_s: float = 120.0) -> bool:
    """Dwell, but only AFTER the robot has actually left the dock once.

    Found by running this scorer: at dispatch the robot is still parked and
    carrying HOURS of accumulated dwell from sitting overnight, so any bare
    "docked longer than N => finished" rule fires on the very first tick of the
    job. `state_s` measures time since the last vacuum-state change, which before
    a job has started is time spent idle -- not evidence about the run at all.

    Requiring a departure first makes the dwell mean "came home AFTER cleaning".
    """
    vac = str(obs.get("vac") or "").lower()
    if "clean" in vac or vac in ("returning", "returning_to_dock"):
        memo["left"] = True
        return True
    if not memo.get("left"):
        return True                      # never moved yet: cannot be finished
    if not obs.get("docked"):
        return True
    return (_f(obs.get("state_s"), 0.0) or 0.0) < settle_s


RULES = {
    "always_on(control)": rule_always_on,
    "dispatch_latch(refuted)": rule_dispatch_latch,
    "not_docked": rule_not_docked,
    "docked_dwell_120s": rule_docked_dwell,
    "docked_dwell+battery": rule_docked_dwell_battery,
    "left_dock+dwell_120s": rule_left_dock_then_dwell,
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


def has_recharge_evidence(obs_list: list[dict]) -> tuple[bool, str]:
    """Does this trace contain the case the binary EXISTS to survive?

    A recharge episode is: docked, battery climbing, and the binary still ON --
    i.e. the device came home mid-job and intends to resume. Without one in the
    trace, every rule that differs ONLY in how it treats a recharge dock scores
    identically, and the simplest rule wins by default. That is the trap this
    guard exists to stop: a recharge-free trace makes `not_docked` look perfect.

    A first version of this test fired on any docked tick with the binary ON, and
    duly reported PRESENT on a trace containing no recharge at all: `docked` is
    true for `returning` too, so an ordinary end-of-room drive home tripped it. A
    guard against over-claiming that itself over-claims is worse than no guard,
    so the test is now the full shape -- clean, come home, battery RISES, clean
    again, all inside one unbroken stretch of native=on.
    """
    episodes: list[list[dict]] = []
    current: list[dict] = []
    for obs in obs_list:
        if str(obs.get("native", "")).lower() == "on":
            current.append(obs)
        else:
            if current:
                episodes.append(current)
            current = []
    if current:
        episodes.append(current)

    for episode in episodes:
        phase = "before"          # before -> parked -> resumed
        park_batt: float | None = None
        for obs in episode:
            vac = str(obs.get("vac") or "").lower()
            batt = _f(obs.get("batt"))
            cleaning = "clean" in vac
            parked = vac == "docked"
            if phase == "before" and cleaning:
                phase = "cleaning"
            elif phase == "cleaning" and parked:
                phase, park_batt = "parked", batt
            elif phase == "parked":
                if parked and batt is not None and park_batt is not None:
                    if batt - park_batt >= 2.0:
                        phase = "charged"
                elif cleaning:
                    phase = "cleaning"   # left the dock without charging
            elif phase == "charged" and cleaning:
                return True, ("a clean -> dock -> battery rose -> clean cycle "
                              "occurred with the binary held ON throughout")
    return False, ("no clean -> dock -> battery-rise -> clean cycle with the "
                   "binary held ON; the robot never recharged mid-job here")


def trace_facts(obs_list: list[dict]) -> list[str]:
    """Structural questions a BASIC (no-recharge) run settles on its own.

    These need no rule and no recharge — they are properties of the device's
    reporting, and each one kills or spares a whole family of candidate rules.
    """
    facts = []

    # 1. binary cycles: per-run or per-room?
    edges, prev = 0, None
    for obs in obs_list:
        cur = str(obs.get("native", "")).lower()
        if cur in ("on", "off"):
            if prev == "on" and cur == "off":
                edges += 1
            prev = cur
    facts.append(
        f"binary OFF edges in trace: {edges}"
        + ("  -> MULTIPLE, so an off-edge does NOT mean 'job over'; any rule that "
           "finalizes on the first one truncates multi-room runs" if edges > 1
           else "  -> single edge (single-room run, or the wave is per-job)")
    )

    # 2. does last_clean_end advance more than once? (per-room vs per-job)
    seen, order = set(), []
    for obs in obs_list:
        lce = obs.get("lce")
        if lce and lce not in seen:
            seen.add(lce)
            order.append(lce)
    facts.append(
        f"distinct last_clean_end values: {len(order)}"
        + ("  -> advances MORE THAN ONCE per trace: it stamps a clean SUMMARY, not "
           "a job end, so 'lce advanced => job done' is false" if len(order) > 2
           else "  -> stable enough to mark a boundary")
    )

    # 3. does total_cleaning_count increment per room?
    counts = [_f(o.get("count")) for o in obs_list]
    counts = [c for c in counts if c is not None]
    incs = sum(1 for a, b in zip(counts, counts[1:]) if b > a)
    facts.append(
        f"total_cleaning_count increments: {incs}"
        + ("  -> increments more than once per run; it counts CLEANS, not JOBS"
           if incs > 1 else "")
    )

    # 4. is the dwell signal even usable?
    dwell = [_f(o.get("state_s")) for o in obs_list if o.get("docked")]
    dwell = [d for d in dwell if d is not None]
    if dwell:
        facts.append(f"docked dwell observed: {len(dwell)} ticks, "
                     f"max {max(dwell):.0f}s — dwell-based rules are measurable here")
    else:
        facts.append("NO docked ticks captured — dwell-based rules cannot be "
                     "evaluated at all from this trace")
    return facts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--vacuum", default=None,
                    help="vacuum slug (required with --from-history-csv)")
    ap.add_argument("--from-history-csv", action="store_true",
                    help="input is an HA History CSV export, not a debug dump")
    args = ap.parse_args()

    path = pathlib.Path(args.dump)
    if not path.exists():
        print(f"no such file: {path}")
        return 2
    if args.from_history_csv:
        if not args.vacuum:
            print("--from-history-csv needs --vacuum <slug>")
            return 2
        obs_list = load_history_csv(path, args.vacuum)
        obs_list, windows = restrict_to_job_windows(obs_list, args.vacuum)
        if windows:
            print(f"restricted to {len(windows)} recorded job window(s) — a live "
                  f"trace only emits while a job is active, so idle ticks are "
                  f"not input the rule would ever see")
        else:
            print("WARNING: no job records found; scoring the WHOLE export, "
                  "including idle. Numbers below are not comparable to a live trace.")
    else:
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

    print("WHAT THIS TRACE SETTLES ON ITS OWN (no rule, no recharge needed)")
    print("-" * 66)
    for fact in trace_facts(labelled):
        print(f"  {fact}")
    print()

    print(f"{'rule':26} {'ticks':>6} {'agree':>7} {'EARLY':>6} {'late':>6}  edge")
    print("-" * 66)
    results = {}
    for name, rule in RULES.items():
        s = score(labelled, rule)
        results[name] = s
        edge = "NEVER FINALIZES" if s["missed_edge"] else "ok"
        flag = "  <-- truncates runs" if s["early"] else ""
        print(f"{name:26} {s['ticks']:6} {s['agree_pct']:6.1f}% "
              f"{s['early']:6} {s['late']:6}  {edge}{flag}")

    print("\nEARLY is the column that disqualifies a rule: it means the rule called "
          "\na run finished while the robot was still cleaning. `late` is latency, "
          "\nwhich is a tuning problem rather than a data-integrity one.")

    # THE GUARD. A recharge-free trace cannot rank rules that differ only in how
    # they treat a recharge dock -- and it flatters the naive ones, because the
    # case they get wrong simply is not present. Say so loudly rather than
    # letting a clean-looking table read as validation.
    has_recharge, why = has_recharge_evidence(labelled)
    print("\n" + "=" * 66)
    if has_recharge:
        print(f"RECHARGE EVIDENCE: PRESENT ({why}).")
        print("Rules can be ranked against each other on this trace.")
        return 0

    survivors = sorted(
        n for n, s in results.items()
        if s["early"] == 0 and not s["missed_edge"]
    )
    print(f"RECHARGE EVIDENCE: ABSENT - {why}.")
    if not survivors:
        print("\nBut no candidate needed one: EVERY rule above already truncates a"
              "\nrun on this trace (EARLY > 0), which disqualifies it without any"
              "\nrecharge being involved. A recharge only matters for separating"
              "\nrules that are otherwise clean, and there are none.")
        return 1
    print("\nThis trace cannot rank the following; they are separated ONLY by what"
          "\nthey do at a recharge dock, which never happened here:")
    for name in survivors:
        print(f"    {name}")
    print("\nA clean sweep is NOT validation. Treat this as confirming the"
          "\nINSTRUMENT (fields populated, edges captured) and the structural"
          "\nfacts at the top - not as choosing a rule.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
