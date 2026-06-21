"""Dev tool — mint a SAMPLES-BEARING (schema v2) synthetic external pending record.

The on-disk v1 synthetic (no embedded samples) cannot exercise the new server-side
re-segmentation (room count / split-here). This fabricates a realistic 8-room
counter-sample stream, runs the REAL ``build_pending_record`` over it, and prints
the v2 record (with embedded samples + the full candidate pool) as JSON to stdout.

Run inside the test image (HA deps available) and write the output to the live box:

    docker run --rm -v "<repo>:/workspace" -w /workspace eufy-vacuum-test \\
        python scripts/make_synthetic_v2.py > out.json
    # then copy out.json to Z:\\eufy_vacuum\\learning\\alfred\\external_jobs\\ (no BOM)

The run mixes confident cuts (long wash plateaus + a couple of settings flips) with
plain area-jumps that default OFF — so the wizard opens at the confident count and
the count stepper / "Split here" reveal the rest (the under-split recovery path).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from custom_components.eufy_vacuum.learning.external_ingest import build_pending_record

_BASE = datetime(2026, 6, 9, 0, 0, 0)


def _iso(sec: int) -> str:
    return (_BASE + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


# (name, area_m2, active_s) in cleaning order, then the inter-room gaps (seconds).
# Two gaps > 90 s are wash plateaus (confident); the rest are area-jumps that are
# confident only where the settings flip across them.
_ROOMS_RUN = [
    ("Heidi", 8.0, 600), ("Entryway", 2.0, 60), ("Hallway", 2.0, 150),
    ("Office", 6.0, 420), ("Bryan", 10.0, 600), ("Living", 8.0, 300),
    ("Kitchen", 7.0, 120), ("Dining", 8.0, 570),
]
_GAPS = [95, 50, 50, 100, 50, 50, 85]  # 7 gaps between the 8 rooms

# Settings flips (by room index they START at) → those boundaries become confident.
_FLIP_AT = {3: {"clean_mode": "vacuum_mop"}, 6: {"clean_mode": "vacuum"}}

# Map-6 room config (slugs) so the shortlist is realistic; see project_room_ids.
_ROOMS = {
    "1": {"slug": "heidi", "name": "Heidi and Chris", "floor_type": "carpet_low_pile", "clean_mode": "vacuum"},
    "2": {"slug": "bathroom", "name": "Bathroom", "floor_type": "tile", "clean_mode": "vacuum_mop"},
    "3": {"slug": "bryan", "name": "Bryan", "floor_type": "carpet_low_pile", "clean_mode": "vacuum"},
    "4": {"slug": "hallway", "name": "Hallway", "floor_type": "hardwood", "clean_mode": "vacuum"},
    "5": {"slug": "kitchen", "name": "Kitchen", "floor_type": "tile", "clean_mode": "vacuum_mop"},
    "6": {"slug": "entryway", "name": "Entryway", "floor_type": "tile", "clean_mode": "vacuum_mop"},
    "7": {"slug": "living", "name": "Living Room", "floor_type": "hardwood", "clean_mode": "vacuum"},
    "8": {"slug": "dining", "name": "Dining Room", "floor_type": "hardwood", "clean_mode": "vacuum"},
    "9": {"slug": "office", "name": "Office", "floor_type": "hardwood", "clean_mode": "vacuum"},
    "11": {"slug": "cat_room", "name": "Cat Room", "floor_type": "tile", "clean_mode": "vacuum_mop"},
}


def build() -> dict:
    counter = [{"t": _iso(0), "cleaning_time": 0, "cleaning_area": 0.0, "battery": 100}]
    settings = []
    cur_settings = {"clean_mode": "vacuum", "fan_speed": "Standard",
                    "clean_intensity": "Normal", "water_level": "Medium"}
    settings.append({"t": _iso(0), "settings": dict(cur_settings)})

    t = 0
    ct = 0
    ca = 0.0
    batt = 100
    for i, (_name, area, active) in enumerate(_ROOMS_RUN):
        if i in _FLIP_AT:
            cur_settings = {**cur_settings, **_FLIP_AT[i]}
            settings.append({"t": _iso(t + 1), "settings": dict(cur_settings)})
        nticks = max(1, round(active / 30))
        per = area / nticks
        for k in range(nticks):
            t += 30
            ct += 30
            ca += per
            if (ct // 30) % 4 == 0 and batt > 1:
                batt -= 1
            counter.append({"t": _iso(t), "cleaning_time": ct,
                            "cleaning_area": round(ca, 2), "battery": batt})
        if i < len(_GAPS):
            t += _GAPS[i]  # inter-room gap: no tick (the blip)

    record = build_pending_record(
        detection_ts=_iso(0),
        map_id="6",
        counter_samples=counter,
        settings_samples=settings,
        rooms=_ROOMS,
        baselines=[],
    )
    if record is None:
        raise SystemExit("build_pending_record returned None (no signal)")
    return record


if __name__ == "__main__":
    print(json.dumps(build()))
