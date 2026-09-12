# -*- coding: utf-8 -*-
"""Validate the manifest against the REGIME SCHEMA. Reads the CSV, writes nothing.

    mode: {vacuum, vacuum_mop}                      {SimuMop=cloth} {VibraRise=cloth}
    if vacuum_mop:
      mop_type: {cloth, pad, roller, track}
      edge_mop: bool                                {Edgewise} - roborock only, so far
    dock: {charge, auto_empty, auto_wash, auto_empty_auto_wash}
    if dock washes (auto_wash | auto_empty_auto_wash):
      water_system: {tanks, plumbed}                REQUIRED — must be declared
      mop_swap:     {swap, no_swap}
    if dock does not wash (charge | auto_empty):
      water_system                                  MUST BE ABSENT — declaring one is an error

ONE ENUM, NOT TWO BOOLEANS. Four dock products, named as products. `auto_wash` on its own is a
real shape, not an oddity: the CN G10 washes the mop and has NO dust collection at all, which a
single wash+empty ladder made look like a lesser tier instead of a different one.

WHY THIS EXISTS. The CSV is three independent columns, so it can express 90 combinations of which
only 50 are legal and 17 occur. The 40 impossible ones are the SHAPE OF THE BUGS WE ACTUALLY HIT:
`tanks=plumbed` on a dock that never washes, `tanks=no` asked of a machine with no station. The
schema makes most of them untypeable by NESTING - a question is only asked where it has an answer.

BUT NESTING IS NOT ENOUGH, and Chris named the case: **mode=vacuum with auto_wash**. `dock` is a
sibling of `mode`, not a child, so a machine with no mop can still be given a dock that washes
one. That is a CROSS-FIELD rule and it has to be written down. It is the only one that is a law;
the rest below are correlations, reported as WARN so a genuine new shape is not blocked by a
pattern that merely held so far.

Run:  python scripts/check-regime-schema.py
"""
import csv
import io
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CSV = ("C:/Users/CKing/Documents/durable/dreame-port-fixture/derived/manifest_table.csv")
MOP_ALIAS = {"SimuMop": "cloth", "VibraRise": "cloth"}
MOPS = {"cloth", "pad", "roller", "track"}
# CSV dock_tier -> (schema dock, mop_swap)
DOCK = {
    "charge_only":     ("charge",                "no_swap"),
    "auto_empty":      ("auto_empty",            "no_swap"),
    "wash_only":       ("auto_wash",             "no_swap"),   # washes, never empties — the G10
    "wash+empty":      ("auto_empty_auto_wash",  "no_swap"),
    "wash+empty+swap": ("auto_empty_auto_wash",  "swap"),
}
WASHES = {"auto_wash", "auto_empty_auto_wash"}
# CSV VALUE -> SCHEMA VALUE. The column is spelled `tanks` and its value is `yes`; the schema
# calls the FIELD water_system and the VALUE `tanks`. Forgetting this mapping made the checker
# report 484 errors on data that was already clean — a probe lying toward a finding. Red on the
# first run is the probe, not the code.
WATER = {"yes": "tanks", "plumbed": "plumbed"}


def check(row):
    """-> (errors, warnings) for one row."""
    err, warn = [], []
    mid, name = row[KEY], row["name"]
    raw_mop, dt, tanks = row["mop_type"], row["dock_tier"], row["tanks"]

    if dt not in DOCK:
        return ["dock_tier %r is not a known dock shape" % dt], warn
    dock, swap = DOCK[dt]
    auto_wash = dock in WASHES
    mode = "vacuum" if raw_mop == "none" else "vacuum_mop"
    mop = None if mode == "vacuum" else MOP_ALIAS.get(raw_mop, raw_mop)

    # ── the shape ───────────────────────────────────────────────────────────────────────────
    if mop is not None and mop not in MOPS:
        err.append("mop_type %r is outside {cloth, pad, roller, track} and has no alias" % raw_mop)

    # ── THE LAW: a dock cannot wash a mop the machine does not have ────────────────────────
    if mode == "vacuum" and auto_wash:
        err.append("mode=vacuum but dock=%s — there is no mop for it to wash" % dock)
    if mode == "vacuum" and swap == "swap":
        err.append("mode=vacuum but the dock SWAPS mops — there are none to swap")

    # ── water_system is only asked where it has an answer ──────────────────────────────────
    if auto_wash:
        if tanks not in WATER:
            err.append("dock=%s MUST declare a water_system, got tanks=%r "
                       "(expected yes(=tanks) or plumbed)" % (dock, tanks))
    else:
        if tanks != "no":
            err.append("dock=%s does not wash, so a water_system must be ABSENT — but "
                       "tanks=%r" % (dock, tanks))

    # ── correlations, not laws ──────────────────────────────────────────────────────────────
    # ⛔ WHY NOTHING BELOW IS AN ERROR. Chris: **"roborock disproves cloth=!wash for its set."**
    # Measured:
    #     DREAME    cloth  129 no-wash ·  0 wash     <- 129/129, indistinguishable from a law
    #     ROBOROCK  cloth   17 no-wash · 17 wash     <- exactly half
    # Every VibraRise machine (S7 · S7 MaxV · both S7 Ultras · S8 · S8 Pro Ultra · S8 MaxV Ultra ·
    # Saros 10), the whole Qrevo line and all three G10s is a CLOTH mop on a WASHING station. A
    # correlation that holds 129/129 on the biggest brand is false one brand over.
    #
    # THE ROLLER/TRACK RULE BELOW IS THE SAME SHAPE OF INFERENCE. It rests on Dreame (114) and
    # Eufy (2); Roborock contributes ZERO evidence because it ships no roller or track mop. So it
    # has never been tested by a brand that might do it differently — which is precisely the
    # position `cloth=!wash` was in before Roborock was measured. It stays a WARN for that reason,
    # and if a brand ships a dockless roller the right response is to delete this line, not the row.
    # SWAP OFF THE FULL-SERVICE TIER — Chris: "not wrong but very very odd". The Matrix10 dock
    # parks spare mop assemblies and rotates them by room type; that is a super-premium mechanism
    # and it sits on a station that also empties and washes. Bolted to a lesser dock it would be
    # storing dirty mops it cannot clean. Not impossible — so a FLAG, not a refusal.
    if swap == "swap" and dock != "auto_empty_auto_wash":
        warn.append("dock=%s SWAPS mop assemblies but is not the full-service tier — a premium "
                    "mechanism on a station that cannot wash what it stores" % dock)

    if mop in ("roller", "track") and not auto_wash:
        warn.append("a %s mop with no washing station — true of nothing shipped so far" % mop)
    return err, warn


rows = list(csv.DictReader(io.open(CSV, encoding="utf-8-sig", newline="")))
KEY = list(rows[0].keys())[0]
errors, warnings, states = [], [], Counter()
for r in rows:
    e, w = check(r)
    for m in e:
        errors.append((r[KEY], r["name"], m))
    for m in w:
        warnings.append((r[KEY], r["name"], m))
    if not e:
        dt = DOCK.get(r["dock_tier"])
        if dt:
            dk, sw = dt
            aw = dk in WASHES
            mo = "vacuum" if r["mop_type"] == "none" else "vacuum_mop"
            states[(mo, MOP_ALIAS.get(r["mop_type"], r["mop_type"]) if mo == "vacuum_mop" else None,
                    dk, sw if aw else None, WATER.get(r["tanks"]) if aw else None)] += 1

print("manifest: %d rows, %d platforms" % (len(rows), len(set(r["upstream_platform"] for r in rows))))
print("legal states observed: %d" % len(states))
print()
if errors:
    print("ERRORS: %d" % len(errors))
    for mid, name, m in errors[:40]:
        print("   %-24s %-34s %s" % (mid[:24], name[:34], m))
else:
    print("ERRORS: none")
print()
if warnings:
    print("WARNINGS: %d  (shapes nothing has shipped — check, do not assume broken)" % len(warnings))
    for mid, name, m in warnings[:20]:
        print("   %-24s %-34s %s" % (mid[:24], name[:34], m))
else:
    print("WARNINGS: none")
sys.exit(1 if errors else 0)
