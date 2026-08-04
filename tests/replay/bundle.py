"""Recorder-save bundles — extract a real run window from a recorder CSV export.

A bundle is the replayable form of one run from the frozen corpus
(.claude/notes/_frozen/replays/): the last-known state of every entity BEFORE the
window opens ("initial"), plus the ordered in-window state changes ("events").
Replaying it through tests/replay/harness.py drives the PRODUCTION listener layer
via the public state-change seam — no mocks describing what the device was
expected to do; the device's own recorded behavior is the stimulus.

Known limitation, inherited from the history-UI CSV export: states only — no
attributes, and entities that never changed in the export window are absent
entirely. A test may pass ``supplement`` states for static context the CSV could
not carry (e.g. the active-map sensor that sat unchanged on "12" for weeks);
every supplement is an explicit, visible assumption rather than a hidden fixture.

Mint a fixture bundle from the corpus:

    python -m tests.replay.bundle <history.csv> <startISO> <endISO> <out.json>
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def extract_bundle(
    csv_path: str | Path,
    start_iso: str,
    end_iso: str,
    *,
    meta: dict | None = None,
) -> dict:
    """Build a bundle dict for [start_iso, end_iso] from a recorder CSV export.

    ISO strings compare lexicographically (the export is uniform UTC "Z"
    timestamps), so the window filter needs no datetime parsing.
    """
    rows: list[tuple[str, str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # entity_id, state, last_changed
        for row in reader:
            if len(row) >= 3:
                rows.append((row[2], row[0], row[1]))  # (t, entity_id, state)
    rows.sort()

    initial: dict[str, str] = {}
    events: list[list[str]] = []
    for t, entity_id, state in rows:
        if t < start_iso:
            initial[entity_id] = state
        elif t <= end_iso:
            events.append([t, entity_id, state])

    return {
        "meta": {
            "source": str(Path(csv_path).name),
            "window": [start_iso, end_iso],
            **(meta or {}),
        },
        "initial": initial,
        "events": events,
    }


def load_bundle(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_bundle(bundle: dict, path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 5:
        raise SystemExit("usage: python -m tests.replay.bundle <csv> <startISO> <endISO> <out.json>")
    _, csv_in, start, end, out = sys.argv
    b = extract_bundle(csv_in, start, end)
    save_bundle(b, out)
    print(f"{out}: {len(b['initial'])} initial states, {len(b['events'])} events")
