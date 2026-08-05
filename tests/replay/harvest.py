"""Harvest every retained run out of the recorder into ground-truth replay bundles.

WHY THIS EXISTS. live:PHASE-ATTR-1 was found by reading ONE run's counters off
the recorder and noticing the persisted job record disagreed with them. That
disagreement is measurable for every run the recorder still holds, and it is the
only source of truth we have that the integration did not itself write: the job
records are the thing under test, the recorder is the witness.

The recorder keeps ~10 days. Every run older than that is gone for good, so this
is a HARVEST, not a query - it copies the evidence out before it cycles.

WHAT A HARVESTED RUN IS. Three things, side by side:

  * ``bundle``  - the replayable state-change series (tests/replay/harness.py),
                  so a fix can be re-run against the real device behaviour
                  instead of a fixture someone wrote to match their expectation.
  * ``truth``   - what the COUNTERS say the run swept, measured from the series:
                  reset-aware progress totals, immune to where the integration
                  chose to put its baseline.
  * ``recorded``- what the integration WROTE into learning for that run.

``truth`` minus ``recorded`` is the finding. A run where they agree is a passing
case worth keeping too - a corpus of only failures cannot show a fix made things
worse somewhere else.

KNOWN LIMITS, stated rather than hidden:
  * states only, no attributes - the recorder's states table is what it is.
  * ``truth`` is only as good as the counter sensors. A run where the device
    never reported area yields area 0.0, which is honest, not a defect.
  * matching a job record to a recorder window is by TIMESTAMP. A record whose
    span the recorder no longer covers is skipped and counted, never guessed at.

THE OUTPUT IS LOCAL-ONLY AND MUST NOT BE COMMITTED. A harvested run is one
household's real device telemetry - room names, cleaning times, when the house
was occupied - and this repository is public and in the HACS default store. The
default destination below is inside .claude/notes/, which is git-ignored. Point
--out somewhere tracked and you are publishing someone's home.

USAGE (read-only against the live DB - opened immutable, so the running
recorder is never locked or copied):

    python -m tests.replay.harvest \\
        --db Z:/home-assistant_v2.db \\
        --config //192.168.4.104/config/eufy_vacuum \\
        --out .claude/notes/_frozen/replays/harvest
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any

UTC = dt.timezone.utc

#: ft2 -> m2. The Eufy area sensor publishes ft2 while the device counts WHOLE
#: square metres, so every raw value is an integer multiple of 1/0.09290304.
#: Measured, not assumed - see live:PHASE-ATTR-1.
FT2_TO_M2 = 0.09290304

#: Unit scales, keyed by the sensor's own ``unit_of_measurement``.
#:
#: The unit is NOT a property of the brand and must never be declared. It follows
#: the Home Assistant unit system, so the same integration reports ft2 on an
#: imperial install and m2 on a metric one, and a user flipping that setting
#: changes it underneath a running corpus. My first harvest pass hardcoded
#: "alfred=ft2, ivy=m2" from observation, which was right for this house on this
#: day and wrong as a rule - it divided every one of Ivy's runs by 10.76.
#:
#: It IS recoverable: the recorder keeps attributes in `state_attributes`, joined
#: from `states.attributes_id`, so the unit in force AT THE TIME OF EACH RUN can
#: be read back per run rather than assumed once.
_AREA_TO_M2 = {"m2": 1.0, "m²": 1.0, "ft2": FT2_TO_M2, "ft²": FT2_TO_M2}
_TIME_TO_S = {"s": 1.0, "sec": 1.0, "min": 60.0, "h": 3600.0}

#: Entity-id suffixes worth carrying. Deliberately NOT every entity the device
#: exposes: a full dump was 329 KB for a single 20-minute run, which across a
#: 10-day harvest is tens of megabytes of mostly-irrelevant maintenance counters.
#: These are the signals every timing/attribution question is answered from.
ROLE_SUFFIXES = (
    "_task_status", "_dock_status", "_cleaning_time", "_cleaning_area",
    "_active_cleaning_target", "_active_map", "_battery", "_water_level",
    "_work_mode", "_robot_position_x_raw", "_robot_position_y_raw",
    "_current_room", "_error", "_cleaning_intensity", "_charging", "_cleaning",
)


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _epoch(iso: str) -> float:
    return dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()


def _progress_total(values: list[float], floor: float | None = None) -> float:
    """Total advance of a counter that may reset, given its readings in order.

    The same reset-aware accumulation the integration now uses, reimplemented
    here ON PURPOSE. If the harvester imported the production helper, a bug in
    that helper would be invisible - truth and the thing under test would agree
    by construction. Two independent implementations disagreeing is a signal;
    one implementation agreeing with itself is not.

    ``floor`` is the counter's last reading from BEFORE the window, and passing
    it is not optional in practice. Without it the first in-window reading only
    establishes a baseline and contributes nothing - so a run whose area counter
    ticked once reported 0.0 m2 of truth. That is the SAME one-quantum loss this
    harvester exists to detect, reproduced inside the measurement; my first pass
    shipped it and produced 'truth 0.0 vs recorded 7.0' rows that were entirely
    my own error. With the floor supplied, the reset at run start is seen for
    what it is and the opening quantum is counted.
    """
    total = 0.0
    prev: float | None = floor
    for value in values:
        if prev is None:
            total = 0.0
        elif value < prev:
            total += max(0.0, value)   # reset: the new reading IS progress since it
        else:
            total += value - prev
        prev = value
    return total


_RETENTION: tuple[float | None, float | None] | None = None


def _retention_span(con: sqlite3.Connection) -> tuple[float | None, float | None]:
    """Oldest/newest state the recorder still holds, computed ONCE.

    MIN/MAX over `states` is a full scan of a multi-gigabyte table. Asking it per
    job record turned an 80-record harvest into minutes of rescanning the same
    2.7 GB for an answer that cannot change mid-run.
    """
    global _RETENTION
    if _RETENTION is None:
        _RETENTION = con.execute(
            "SELECT MIN(last_updated_ts), MAX(last_updated_ts) FROM states"
        ).fetchone()
    return _RETENTION


def _entities_for(con: sqlite3.Connection, vacuum: str) -> dict[int, str]:
    rows = con.execute(
        "SELECT metadata_id, entity_id FROM states_meta WHERE entity_id LIKE ?",
        (f"%{vacuum}%",),
    ).fetchall()
    keep: dict[int, str] = {}
    for mid, eid in rows:
        if eid == f"vacuum.{vacuum}" or any(eid.endswith(sfx) for sfx in ROLE_SUFFIXES):
            keep[mid] = eid
    return keep


def _series(
    con: sqlite3.Connection, mid: int, lo: float, hi: float
) -> list[tuple[float, str]]:
    return con.execute(
        "SELECT last_updated_ts, state FROM states WHERE metadata_id=? "
        "AND last_updated_ts BETWEEN ? AND ? ORDER BY last_updated_ts",
        (mid, lo, hi),
    ).fetchall()


def _numeric(rows: list[tuple[float, str]], scale: float = 1.0) -> list[float]:
    out: list[float] = []
    for _t, state in rows:
        try:
            out.append(float(state) * scale)
        except (TypeError, ValueError):
            continue          # unknown/unavailable is a gap, not a zero
    return out


def _unit_at(con: sqlite3.Connection, mid: int, at_ts: float) -> str | None:
    """The sensor's ``unit_of_measurement`` as of ``at_ts``, from the recorder.

    Looks backwards first - the unit in force when the run happened - and only
    falls forward if the sensor had never recorded attributes by then.
    """
    for order, cmp_op in (("DESC", "<="), ("ASC", ">")):
        row = con.execute(
            f"SELECT sa.shared_attrs FROM states s "
            f"JOIN state_attributes sa ON sa.attributes_id = s.attributes_id "
            f"WHERE s.metadata_id=? AND s.attributes_id IS NOT NULL "
            f"AND s.last_updated_ts {cmp_op} ? ORDER BY s.last_updated_ts {order} LIMIT 1",
            (mid, at_ts),
        ).fetchone()
        if row and row[0]:
            try:
                unit = json.loads(row[0]).get("unit_of_measurement")
            except (TypeError, ValueError):
                continue
            if unit:
                return str(unit).strip()
    return None


def _scale_for(unit: str | None, table: dict[str, float], fallback: float) -> tuple[float, str]:
    """Scale factor for ``unit``, plus how it was arrived at.

    An unrecognised or absent unit is NOT guessed at - it falls back to treating
    the reading as already canonical, the same policy as the production
    ``cleaning_area_to_m2``, and says so in the returned tag so a reader can see
    that the number rests on a fallback rather than a measurement.
    """
    key = str(unit or "").strip().lower()
    if key in table:
        return table[key], f"detected:{unit}"
    return fallback, ("absent" if not key else f"unrecognised:{unit}")


def _floor_before(con: sqlite3.Connection, mid: int, lo: float, scale: float) -> float | None:
    """The counter's last reading before the window opened, or None if it never reported."""
    row = con.execute(
        "SELECT state FROM states WHERE metadata_id=? AND last_updated_ts < ? "
        "ORDER BY last_updated_ts DESC LIMIT 1", (mid, lo),
    ).fetchone()
    if not row:
        return None
    try:
        return float(row[0]) * scale
    except (TypeError, ValueError):
        return None


def harvest_run(
    con: sqlite3.Connection,
    vacuum: str,
    record: dict[str, Any],
    pad_s: float = 120.0,
    area_unit_override: str | None = None,
) -> dict[str, Any] | None:
    """One job record -> its bundle, its counter truth, and what was recorded."""
    job = record.get("job") or {}
    started, ended = job.get("started_at"), job.get("ended_at")
    if not started or not ended:
        return None
    lo, hi = _epoch(started) - pad_s, _epoch(ended) + pad_s

    ents = _entities_for(con, vacuum)
    if not ents:
        return None
    span = _retention_span(con)
    if span[0] is None or lo < span[0] or hi > span[1]:
        return {"skipped": "outside_recorder_retention"}

    by_role = {eid: mid for mid, eid in ents.items()}
    ct_mid = by_role.get(f"sensor.{vacuum}_cleaning_time")
    ca_mid = by_role.get(f"sensor.{vacuum}_cleaning_area")

    truth: dict[str, Any] = {"cleaning_seconds": None, "area_m2": None}
    if ct_mid is not None:
        scale, how = _scale_for(
            area_unit_override or _unit_at(con, ct_mid, hi), _TIME_TO_S, 1.0
        )
        truth["time_unit"] = how
        truth["cleaning_seconds"] = round(
            _progress_total(_numeric(_series(con, ct_mid, lo, hi), scale),
                            _floor_before(con, ct_mid, lo, scale)), 1
        )
    if ca_mid is not None:
        scale, how = _scale_for(
            area_unit_override or _unit_at(con, ca_mid, hi), _AREA_TO_M2, 1.0
        )
        truth["area_unit"] = how
        truth["area_m2"] = round(
            _progress_total(_numeric(_series(con, ca_mid, lo, hi), scale),
                            _floor_before(con, ca_mid, lo, scale)), 3
        )

    initial: dict[str, str] = {}
    events: list[list[str]] = []
    for mid, eid in sorted(ents.items(), key=lambda kv: kv[1]):
        prior = con.execute(
            "SELECT state FROM states WHERE metadata_id=? AND last_updated_ts < ? "
            "ORDER BY last_updated_ts DESC LIMIT 1", (mid, lo),
        ).fetchone()
        if prior and prior[0] not in (None, "unknown", "unavailable"):
            initial[eid] = prior[0]
        for t, state in _series(con, mid, lo, hi):
            if state is not None:
                events.append([_iso(t), eid, state])
    events.sort()

    rooms = job.get("room_timings") or []
    # A PHASE-CHILD record leaves cleaning_area_m2 at 0.0 while its room rows
    # carry the real figures, so comparing truth against the job-level field
    # alone reported a fabricated -6 m2 gap on exactly the runs that mattered.
    _job_area = job.get("cleaning_area_m2")
    _room_area = round(sum(float(r.get("area_m2") or 0) for r in rooms), 3) if rooms else None
    recorded = {
        "cleaning_seconds": job.get("cleaning_time_seconds"),
        "area_m2": _room_area if (not _job_area and _room_area) else _job_area,
        "area_from": "room_rows" if (not _job_area and _room_area) else "job_field",
        "rooms": [
            {
                "slug": r.get("slug"), "room_id": r.get("room_id"),
                "cleaning_seconds": r.get("cleaning_seconds"),
                "area_m2": r.get("area_m2"),
                "wall_s": r.get("cleaning_wall_seconds"),
                "boundary": r.get("boundary"), "allocated": r.get("allocated"),
            }
            for r in rooms if isinstance(r, dict)
        ],
    }

    # FLAGS. A raw truth-minus-recorded gap is NOT automatically a defect, and
    # presenting it as one would be the harvester lying by omission:
    #
    #  * `recorded.area_m2` is sometimes an ESTIMATE BY DESIGN. phase_runner falls
    #    back to the room's LEARNED area when the within-phase cleaning_area delta
    #    is ~0 (a stale or flat sensor through the phase). job_2026-07-26T13-03-41
    #    is the worked example: a 2m40s run whose area counter never moved, truth
    #    correctly 0.0, recorded 7.0 - the learned value, doing its job. Reading
    #    that as "over-credited by 7 m2" would file a feature as a bug.
    #  * a run that never advanced either counter did not clean, so both figures
    #    are trivially 0 and the comparison says nothing.
    #  * a zero-second room row with allocated=False is the live:PHASE-ATTR-1
    #    signature - a fabricated observation admitted to learning as measured.
    flags: list[str] = []
    _t_truth = truth.get("cleaning_seconds") or 0.0
    _a_truth = truth.get("area_m2") or 0.0
    if _t_truth <= 0 and _a_truth <= 0:
        flags.append("run_never_advanced_counters")
    if _a_truth <= 0.01 and float(recorded["area_m2"] or 0) > 0.01:
        flags.append("area_likely_learned_fallback")
    if any(r.get("cleaning_seconds") in (0, None) and r.get("allocated") is False
           for r in recorded["rooms"]):
        flags.append("zero_second_observed_room")

    def _gap(a: Any, b: Any) -> float | None:
        if a is None or b is None:
            return None
        return round(float(a) - float(b), 3)

    return {
        "bundle": {
            "meta": {
                "source": "home-assistant_v2.db (recorder, immutable)",
                "vacuum": vacuum,
                "job_id": record.get("job_id"),
                "phased_job_id": record.get("phased_job_id"),
                "window": [_iso(lo), _iso(hi)],
                "run_span": [started, ended],
            },
            "initial": initial,
            "events": events,
        },
        "truth": truth,
        "recorded": recorded,
        "flags": flags,
        "delta": {
            "cleaning_seconds": _gap(truth["cleaning_seconds"], recorded["cleaning_seconds"]),
            "area_m2": _gap(truth["area_m2"], recorded["area_m2"]),
            "rooms_sum_seconds": _gap(
                recorded["cleaning_seconds"],
                sum(r["cleaning_seconds"] or 0 for r in recorded["rooms"]) if rooms else None,
            ),
            "rooms_sum_area": _gap(
                recorded["area_m2"],
                round(sum(r["area_m2"] or 0 for r in recorded["rooms"]), 3) if rooms else None,
            ),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--config", required=True, help="the eufy_vacuum config dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--vacuums", default="alfred,ivy")
    ap.add_argument(
        "--area-units", default="",
        help="LAST RESORT override, e.g. alfred=ft2. Units are DETECTED per run "
             "from the recorder's state_attributes; only use this for a sensor "
             "that never recorded attributes at all.",
    )
    args = ap.parse_args()
    units: dict[str, str] = {}
    for pair in (args.area_units or "").split(","):
        if "=" in pair:
            k, _, v = pair.partition("=")
            units[k.strip()] = v.strip()

    con = sqlite3.connect(f"file:{args.db}?immutable=1", uri=True)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    index: list[dict[str, Any]] = []
    skipped = 0

    for vacuum in [v.strip() for v in args.vacuums.split(",") if v.strip()]:
        jobs_dir = Path(args.config) / "learning" / vacuum / "jobs"
        if not jobs_dir.is_dir():
            continue
        vac_out = out_root / vacuum
        vac_out.mkdir(parents=True, exist_ok=True)
        for path in sorted(jobs_dir.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            got = harvest_run(con, vacuum, record,
                              area_unit_override=units.get(vacuum))
            if got is None:
                continue
            if got.get("skipped"):
                skipped += 1
                continue
            name = path.stem
            (vac_out / f"{name}.json").write_text(
                json.dumps(got["bundle"], indent=1, ensure_ascii=False), encoding="utf-8"
            )
            index.append({
                "vacuum": vacuum, "name": name, "flags": got["flags"],
                "bundle": f"{vacuum}/{name}.json",
                "events": len(got["bundle"]["events"]),
                "run_span": got["bundle"]["meta"]["run_span"],
                "truth": got["truth"], "recorded": {
                    k: v for k, v in got["recorded"].items() if k != "rooms"
                },
                "rooms": got["recorded"]["rooms"],
                "delta": got["delta"],
            })

    con.close()
    (out_root / "index.json").write_text(
        json.dumps({
            "note": (
                "truth = measured from the recorder's counter series (reset-aware, "
                "independent implementation). recorded = what the integration wrote. "
                "delta.cleaning_seconds > 0 means the run swept MORE than was credited. "
                "READ THE FLAGS BEFORE THE DELTAS: area_likely_learned_fallback means "
                "the integration substituted a learned area on purpose (a flat sensor), "
                "and run_never_advanced_counters means the run did not clean at all. "
                "Neither is a defect. zero_second_observed_room IS the PHASE-ATTR-1 "
                "signature: a fabricated zero admitted to learning as an observation."
            ),
            "skipped_outside_retention": skipped,
            "runs": index,
        }, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"harvested {len(index)} runs, skipped {skipped} outside retention -> {out_root}")


if __name__ == "__main__":
    main()
