"""Concordance check: frozen recorder episodes vs the learned job dataset.

The frozen replay corpus (.claude/notes/_frozen/replays/) captures what the DEVICE did;
the learning archive (eufy_vacuum/learning/<slug>/{jobs,phased_jobs,phases}) captures what
the SYSTEM recorded about it. On 2026-08-04 they concorded perfectly:

    BASELINE: 57/57 Alfred + 11/11 Ivy episodes matched, ZERO true orphans in either
    direction; room-boundary deltas (episode start vs learned room cleaning_start):
    Ivy max 1s, Alfred max 138s (first-room transit included; all worst cases are the
    run's first room).

RUN THIS AFTER ANY LIFECYCLE / RECORD-SCHEMA / FINALIZER CHANGE (audit-2 charter §4
delta 12). The frozen window never changes, so any loss of concordance — an episode
losing its job, a job losing its episode, a boundary delta blowing past the profile —
means the change destabilized lifecycle/finalize behavior or broke old records in a
migration, even if the whole pytest suite stays green.

Usage:
    python .claude/notes/_crossmatch_replays.py --check          # exit 1 on regression
    python .claude/notes/_crossmatch_replays.py --update         # rewrite inventory annotations
    ... [--learning-root PATH]   default: //192.168.4.104/config/eufy_vacuum/learning

Thresholds (baseline + headroom): unmatched episodes >=1min: 0 · true orphans: 0 ·
boundary delta: Ivy <=5s, Alfred <=180s.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
INVENTORY = os.path.join(HERE, "_frozen", "replays", "RUN-INVENTORY.json")
DEFAULT_LEARNING_ROOT = "//192.168.4.104/config/eufy_vacuum/learning"
TOL = timedelta(seconds=120)
DELTA_LIMIT_S = {"alfred": 180, "ivy": 5}


def _t(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def _find_key(o, key):
    """First truthy value for key anywhere in a nested record (records nest under 'job')."""
    if isinstance(o, dict):
        if o.get(key):
            return o[key]
        for v in o.values():
            r = _find_key(v, key)
            if r:
                return r
    return None


def load_jobs(root, slug):
    out = []
    for sub in ("jobs", "phased_jobs", "phases"):
        for p in sorted(glob.glob(f"{root}/{slug}/{sub}/*.json")):
            try:
                rec = json.load(open(p, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rec, dict):
                continue
            start = _t(_find_key(rec, "started_at") or _find_key(rec, "opened_at"))
            end = _t(_find_key(rec, "ended_at") or rec.get("finalized_at"))
            if not start:
                continue
            rts = _find_key(rec, "room_timings") or []
            windows = [
                {"slug": r.get("slug"), "start": _t(r.get("cleaning_start")), "end": _t(r.get("cleaning_end"))}
                for r in rts
                if isinstance(r, dict)
            ]
            outc = rec.get("outcome") or {}
            out.append(
                {
                    "file": f"{sub}/{os.path.basename(p)}",
                    "start": start,
                    "end": end or start + timedelta(minutes=30),
                    "windows": windows,
                    "status": outc.get("status") or rec.get("status"),
                    "learn": outc.get("used_for_learning"),
                    "external": os.path.basename(p).startswith("ext-"),
                }
            )
    return out


def crossmatch(inv, root, update):
    failures = []
    for slug in ("alfred", "ivy"):
        jobs = load_jobs(root, slug)
        eps = inv[slug]
        matched_any = set()
        for run in eps:
            rs, re_ = _t(run["start"]), _t(run["end"])
            best = None
            for j in jobs:
                if j["start"] - TOL <= re_ and j["end"] + TOL >= rs:
                    ov = (min(re_, j["end"]) - max(rs, j["start"])).total_seconds()
                    if best is None or ov > best[0]:
                        best = (ov, j)
            if best is None:
                if run["minutes"] >= 1.0:
                    failures.append(f"{slug}: episode {run['start']} ({run['minutes']}min) has NO learned job")
                continue
            j = best[1]
            matched_any.add(j["file"])
            roomlab = delta_s = None
            for w in j["windows"]:
                if w["start"] and w["start"] - TOL <= re_ and (w["end"] or w["start"]) + TOL >= rs:
                    d = abs((w["start"] - rs).total_seconds())
                    if delta_s is None or d < delta_s:
                        roomlab, delta_s = w["slug"], d
            if delta_s is not None and delta_s > DELTA_LIMIT_S[slug]:
                failures.append(
                    f"{slug}: boundary delta {delta_s:.0f}s > {DELTA_LIMIT_S[slug]}s "
                    f"(episode {run['start']} room {roomlab} job {j['file']})"
                )
            if update:
                run["matched_job"] = j["file"]
                run["job_status"] = j["status"]
                run["used_for_learning"] = j["learn"]
                if roomlab:
                    run["room_window"] = roomlab
                    run["boundary_delta_s"] = round(delta_s)
                if not run.get("label"):
                    kind = "EXTERNAL" if j["external"] else "dispatched"
                    run["label"] = (
                        f"[auto] {kind} {os.path.basename(j['file']).rsplit('.json', 1)[0]} "
                        f"status={j['status']} learn={j['learn']}"
                    )
        # true orphans: in-window jobs no episode overlaps AT ALL (parent/child of a
        # matched run overlap their run's episodes, so they are naturally not orphans)
        win_lo = min(_t(r["start"]) for r in eps)
        for j in jobs:
            if j["start"] < win_lo - TOL:
                continue
            if not any(_t(r["start"]) - TOL <= j["end"] and _t(r["end"]) + TOL >= j["start"] for r in eps):
                failures.append(f"{slug}: learned job {j['file']} ({j['start'].isoformat()}) has NO episode")
    return failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--learning-root", default=DEFAULT_LEARNING_ROOT)
    args = ap.parse_args()

    inv = json.load(open(INVENTORY, encoding="utf-8"))
    failures = crossmatch(inv, args.learning_root, update=args.update)
    if args.update:
        json.dump(inv, open(INVENTORY, "w", encoding="utf-8"), indent=1)
        print(f"inventory annotations rewritten: {INVENTORY}")

    if failures:
        print(f"CONCORDANCE BROKEN — {len(failures)} failure(s):")
        for f in failures:
            print("  ", f)
        sys.exit(1)
    print("concordance holds: every episode<->job matched, deltas within profile")
    sys.exit(0)


if __name__ == "__main__":
    main()
