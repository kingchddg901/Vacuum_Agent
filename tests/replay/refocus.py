"""Cut a FOCUSED recording out of the general harvest.

TWO TIERS, and the split is the whole point.

  1. ``harvest.py`` takes everything, once, while the recorder still has it. The
     recorder keeps ~10 days; that pass is the only chance. It is deliberately
     broad because you do not yet know what you will need.
  2. THIS re-harvests from that copy. It never touches the database, so a focus
     can be re-cut months later, argued with, and re-cut again — and getting the
     lens wrong costs nothing, because the general harvest is still there.

A focused recording answers ONE question with the signals that bear on it. A
bundle carrying every entity is not more rigorous, it is harder to read: the
row that matters sits between four hundred that do not, and a diff between two
runs is dominated by noise nobody is asking about.

WHAT A LENS IS. A named set of entity roles that are load-bearing for one kind
of question, plus what to do with everything else. The lenses below are not
guesses — each one is the set that was actually needed to answer a real
investigation, named in its comment. Add a lens when a new question needs a new
set; do not widen an existing one to avoid the argument.

DROPPING IS DECLARED, NEVER SILENT. Every cut prints what went and why, and the
output records its own lens. A focused bundle that does not say what it is
focused on is indistinguishable from a complete one that is missing data.

    python -m tests.replay.refocus \\
        --in .claude/notes/_frozen/replays/harvest \\
        --lens timing \\
        --out .claude/notes/_frozen/replays/focus-timing
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

#: LIFETIME ODOMETERS, which are NOT the per-run counters despite ending in the
#: same words. ``sensor.<area>_<vacuum>_total_cleaning_area`` ends with
#: "_cleaning_area", so any suffix match written for the per-run counter silently
#: swallows it — and it is a monotonic lifetime total in the thousands, so
#: summing the two together does not look obviously wrong, it just produces a
#: number 500x too large. I did exactly that while verifying this module.
#:
#: Excluded from every lens unless one names them explicitly. Harvest still
#: CARRIES them (they are real, and cheap); this stops them impersonating the
#: counter that answers a timing question.
ODOMETER_SUFFIXES = ("_total_cleaning_time", "_total_cleaning_area")

#: Roles every lens keeps. Without the vacuum's own state and its task_status
#: you cannot tell a run from a pause from a dock, which makes any other signal
#: uninterpretable — these are the frame, not a topic.
_ALWAYS = ("vacuum.", "_task_status")

#: lens -> (role suffixes, why this set and not another)
LENSES: dict[str, tuple[tuple[str, ...], str]] = {
    "timing": (
        ("_cleaning_time", "_cleaning_area", "_current_room",
         "_active_cleaning_target", "_dock_status"),
        "live:PHASE-ATTR-1. The counters ARE the measurement; current_room and "
        "active_cleaning_target say which room owns a delta; dock_status "
        "separates a break from a stall. Position was NOT needed — the defect "
        "was in arithmetic over counters, and pose would have been 100 entities "
        "of distraction.",
    ),
    "attribution": (
        ("_cleaning_time", "_cleaning_area", "_current_room",
         "_active_cleaning_target", "_robot_position_x_raw",
         "_robot_position_y_raw", "_dock_status"),
        "Which ROOM did this work belong to. Timing plus pose: when the counter "
        "delta and the room label disagree, position is the tiebreaker.",
    ),
    "battery": (
        ("_battery", "_charging", "_dock_status", "_cleaning_time"),
        "RF-36. Charge/discharge across a run; cleaning_time is kept because a "
        "battery delta is meaningless without knowing how long it was working.",
    ),
    "rules": (
        ("_rule_status", "_active_cleaning_target", "_current_room"),
        "Rule evaluation, when the vacuum's own state does NOT capture what is "
        "being tested. This is the lens that wants the chatty sensors — they "
        "are the subject here, not noise.",
    ),
    "errors": (
        ("_error", "_dock_status", "_current_room", "_cleaning_time"),
        "What the device reported when something went wrong, and what it was "
        "doing at the time.",
    ),
    "odometer": (
        ODOMETER_SUFFIXES,
        "The LIFETIME totals, on purpose. Separate from 'timing' because they "
        "answer a different question (wear, cumulative use) and because letting "
        "them sit alongside the per-run counters is how they get summed by "
        "mistake.",
    ),
    "everything": ((), "No filtering. Adapter bring-up, where the whole "
                       "question is what this brand's entities even are."),
}


def _keep(entity_id: str, suffixes: tuple[str, ...]) -> bool:
    explicit = any(entity_id.endswith(sfx) for sfx in suffixes)
    if any(entity_id.endswith(o) for o in ODOMETER_SUFFIXES) and not (
        explicit and any(o in suffixes for o in ODOMETER_SUFFIXES)
    ):
        return False
    if not suffixes:
        return True
    if any(entity_id.startswith(a) if a.endswith(".") else entity_id.endswith(a)
           for a in _ALWAYS):
        return True
    return any(entity_id.endswith(sfx) for sfx in suffixes)


def refocus(bundle: dict[str, Any], lens: str) -> dict[str, Any]:
    """Narrow a bundle to one lens, recording what was cut."""
    if lens not in LENSES:
        raise KeyError(f"unknown lens {lens!r}; have {sorted(LENSES)}")
    suffixes, why = LENSES[lens]

    events = [e for e in bundle.get("events", []) if _keep(e[1], suffixes)]
    kept_entities = {e[1] for e in events}

    # `initial` is context, not signal: an entity that never changed inside the
    # window still explains the ones that did. Keep it for entities the lens
    # cares about even when they produced no events — "it never moved" is an
    # observation, and dropping it turns a flat sensor into a missing one.
    initial = {
        k: v for k, v in (bundle.get("initial") or {}).items() if _keep(k, suffixes)
    }

    dropped_events = len(bundle.get("events", [])) - len(events)
    dropped_initial = len(bundle.get("initial") or {}) - len(initial)
    meta = dict(bundle.get("meta") or {})
    meta.update({
        "lens": lens,
        "lens_rationale": why,
        "lens_suffixes": list(suffixes),
        "refocused_from": meta.get("source"),
        "dropped_events": dropped_events,
        "dropped_initial_entities": dropped_initial,
        "kept_entities": sorted(kept_entities),
    })
    return {"meta": meta, "initial": initial, "events": events}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="src", required=True,
                    help="a harvest directory or a single bundle .json")
    ap.add_argument("--lens", required=True, choices=sorted(LENSES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--list-lenses", action="store_true")
    args = ap.parse_args()

    if args.list_lenses:
        for name, (sfx, why) in sorted(LENSES.items()):
            print(f"{name}: {', '.join(sfx) or '(no filter)'}\n    {why}\n")
        return

    src = Path(args.src)
    paths = (
        [src] if src.is_file()
        else [p for p in sorted(src.rglob("*.json")) if p.name != "index.json"]
    )
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    tot_in = tot_out = 0
    for path in paths:
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "events" not in bundle:
            continue
        focused = refocus(bundle, args.lens)
        rel = path.name if src.is_file() else str(path.relative_to(src)).replace("\\", "/")
        dest = out_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(focused, indent=1, ensure_ascii=False),
                        encoding="utf-8")
        tot_in += len(bundle["events"])
        tot_out += len(focused["events"])

    pct = (1 - tot_out / tot_in) * 100 if tot_in else 0.0
    print(f"lens '{args.lens}': {len(paths)} bundles, {tot_in} -> {tot_out} events "
          f"({pct:.1f}% cut) -> {out_root}")
    print(f"  {LENSES[args.lens][1]}")
    print("  The general harvest is untouched; re-cut with a different --lens "
          "any time.")


if __name__ == "__main__":
    main()
