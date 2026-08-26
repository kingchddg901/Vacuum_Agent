"""Which Dreame hardware would Vacuum Agent actually accept as a supported target?

A coverage percentage is only as good as its denominator, and "how many of the 587
model keys look like vacuums?" is the wrong question — it invites naming heuristics and
they eventually betray you. The question this answers is positive and three-part:

  1. is it a ROBOT vacuum / vacuum-mop?   (not stick, handheld, purifier, mower)
  2. does it produce a usable PERSISTENT MAP?
  3. does that map carry ADDRESSABLE ROOMS/SEGMENTS we can target?

⚠ THERE IS NO "HAS MAP" FLAG TO FIND, AND LOOKING FOR ONE IS THE MISTAKE. In the
upstream integration almost every capability is decided at RUNTIME from live device
properties — ``self.customized_cleaning = bool(get_property(CUSTOMIZED_CLEANING) is not
None)``. The static ``DEVICE_INFO`` blob carries only two things this can stand on:

  * the product class and ``robot_type``, which ARE static, and
  * a SPARSE capability overlay of ``[DeviceCapability_id, min_firmware]`` pairs.

⚠ THE OVERLAY IS SPARSE, SO ABSENCE PROVES NOTHING. A device on this network reports
detergent status live while carrying no DETERGENT entry in its record. Presence of a
segment capability is therefore evidence FOR rooms; its absence is evidence of nothing
at all. That asymmetry is why this classifies into four buckets rather than two.

  TARGET_CONFIRMED  robot + map + room/segment addressing, positively evidenced
  TARGET_LIKELY     certainly a robot vacuum with lidar mapping, room semantics unproven
  EXCLUDED          not the robot-vacuum product line, or a class that cannot address rooms
  UNKNOWN           the record does not say enough — a RESEARCH QUEUE, not a failure

⚠ UNKNOWN MUST NOT COUNT AGAINST COVERAGE. Folding "we do not know" into "not
supported" quietly converts ignorance into a decision, and the number then looks
finished when it is merely unexamined.

    python scripts/dreame_target_models.py --devices supported_devices.md \\
        --const dreame_dev_const.py [--manuals DIR]
"""

from __future__ import annotations

import argparse
import ast
import base64
import collections
import gzip
import json
import re
from pathlib import Path

#: DEVICE_INFO device record = [product_class, robot_type, capability_index, key_index?]
#: `robot_type` values are the upstream `RobotType` enum, read from its own source —
#: not inferred from model names, which is the assumption that eventually betrays you.
ROBOT_TYPE = {0: "LIDAR", 1: "VSLAM", 2: "MOPPING", 3: "SWEEPING_AND_MOPPING"}

#: ⚠ ``robot_type`` IS ONLY TRUSTWORTHY ON DREAME-BRANDED KEYS. Within brand 0 it varies
#: (526/28/19/10 across the four values) and lines up with what the models are. On every
#: OTHER brand it equals the brand id exactly — all 102 Mova keys read "2", all 12
#: trouver read "3" — which is too perfect to be a robot classification. Treat a
#: non-dreame ``robot_type`` as unproven rather than as a class, and let the segment
#: capability carry the decision there.
BRAND_OF = {0: "dreame", 1: "xiaomi", 2: "mova", 3: "trouver"}

#: Capabilities that can only mean "this map has addressable rooms". Any ONE of these in
#: a model's static overlay proves room semantics; none of them proves nothing.
SEGMENT_CAPS = {
    12: "SEGMENT_VISIBILITY",
    19: "SEGMENT_SLOW_CLEAN_ROUTE",
    31: "AUTO_RENAME_SEGMENT",
    40: "SEGMENT_MOPPING_SETTINGS",
    41: "SEGMENT_MOPPING_TYPE",
}
#: Capabilities that evidence a persistent, editable map (necessary, not sufficient).
MAP_CAPS = {119: "MAP_V2", 144: "FLOOR_PLAN", 147: "MAP_EDIT_WHILE_RUNNING",
            148: "QUICK_MAP_RECOVERY", 149: "QUICK_MAP_RECOVERY_V2"}


def load_device_info(const_path: Path):
    src = const_path.read_text(encoding="utf-8", errors="replace")
    blob = None
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "DEVICE_INFO":
            blob = ast.literal_eval(node.value)
    if blob is None:
        raise SystemExit(f"no DEVICE_INFO in {const_path}")
    if isinstance(blob, tuple):
        blob = "".join(blob)
    # gzip, not zlib — the header is 1f8b and zlib.decompress fails with a header error.
    return json.loads(gzip.decompress(base64.b64decode(blob)).decode())


def load_names(devices_path: Path) -> dict[str, str]:
    """model suffix -> marketing name, across EVERY vendor prefix the list declares.

    ⚠ DO NOT HARD-CODE ``dreame.vacuum.``. The first cut did, and silently dropped 154
    keys — the integration also declares ``mova.`` (102), ``xiaomi.`` (25),
    ``trouver.`` (13), ``ijai.`` (11), ``deerma.`` (2) and ``szkj.`` (1). That made
    every coverage percentage in the session 21% too generous, and nothing in the
    output looked wrong: a denominator that is quietly too small reads exactly like
    good progress.

    They are NOT duplicates. All 741 suffixes are distinct and no suffix appears under
    two prefixes, so these are additional devices rather than rebadges of dreame keys —
    measured, because "Mova is just rebadged Dreame" was the plausible assumption and it
    is false at the key level.
    """
    out = {}
    for line in devices_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\|\s*(.+?)\s*\|\s*([a-z]+)\.vacuum\.([a-z0-9]+)\s*\|", line)
        if m:
            out[m.group(3)] = m.group(1)
    return out


def classify(key, name, devs, capsets, index):
    """(bucket, robot_type, why) for one model key."""
    if key not in index:
        return "UNKNOWN", None, "no DEVICE_INFO record for this key"
    rec = devs[index[key]]
    brand_id, rtype = rec[0], rec[1]
    # ⚠ field[0] IS THE BRAND, NOT A PRODUCT CLASS, AND READING IT AS ONE EXCLUDED 118
    # REAL ROBOT VACUUMS. It maps 1:1 onto the model prefix — dreame 0, xiaomi 1,
    # mova 2, trouver 3 — and Mova's 102 keys carry segment capabilities on 99 of them,
    # so they address rooms exactly like the Dreame-branded ones. The tell was that the
    # excluded count landed on precisely the non-dreame prefixes; a filter whose output
    # equals a category you already had is not filtering, it is renaming.
    _ = brand_id
    kind = ROBOT_TYPE.get(rtype, f"type{rtype}")
    caps = {c[0] for c in capsets[rec[2]]} if rec[2] < len(capsets) else set()
    seg = sorted(SEGMENT_CAPS[c] for c in caps & set(SEGMENT_CAPS))
    mp = sorted(MAP_CAPS[c] for c in caps & set(MAP_CAPS))

    if brand_id != 0:
        # robot_type is unreliable off-brand (see BRAND_OF); the capability overlay is
        # the only signal here that means what it says.
        if seg:
            return ("TARGET_CONFIRMED", f"{BRAND_OF.get(brand_id, brand_id)} rebadge",
                    f"segment capability {seg[0]}")
        return ("UNKNOWN", f"{BRAND_OF.get(brand_id, brand_id)} rebadge",
                "rebadged brand with no segment evidence")
    if kind == "LIDAR":
        if seg:
            return "TARGET_CONFIRMED", kind, f"lidar + {seg[0]}"
        # Lidar navigation IS persistent mapping; what is unproven is room addressing,
        # and the overlay's silence is not evidence either way.
        return "TARGET_LIKELY", kind, "lidar mapping; no segment capability in overlay"
    if kind in ("VSLAM", "SWEEPING_AND_MOPPING"):
        if seg:
            return "TARGET_CONFIRMED", kind, f"{kind} + {seg[0]}"
        return "UNKNOWN", kind, f"{kind}; no segment evidence — needs a live check"
    if kind == "MOPPING":
        if seg:
            return "TARGET_CONFIRMED", kind, f"mop robot + {seg[0]}"
        return "UNKNOWN", kind, "mop-only class; room support unevidenced"
    return "UNKNOWN", kind, f"unrecognised robot_type {rtype}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--devices", type=Path, required=True)
    ap.add_argument("--const", type=Path, required=True)
    ap.add_argument("--manuals", type=Path)
    ap.add_argument("--show", type=int, default=12)
    args = ap.parse_args()

    devs, capsets, _keys, index = load_device_info(args.const)
    names = load_names(args.devices)

    buckets = collections.defaultdict(list)
    by_name = collections.defaultdict(set)
    for key, name in names.items():
        bucket, kind, why = classify(key, name, devs, capsets, index)
        buckets[bucket].append((key, name, kind, why))
        by_name[bucket].add(name)

    total = len(names)
    print(f"{total} model keys declared by the integration\n")
    for b in ("TARGET_CONFIRMED", "TARGET_LIKELY", "EXCLUDED", "UNKNOWN"):
        rows = buckets[b]
        print(f"  {b:17} {len(rows):4} keys  {len(by_name[b]):3} names   "
              f"{len(rows)/total:5.1%}")
    target = len(buckets["TARGET_CONFIRMED"]) + len(buckets["TARGET_LIKELY"])
    print(f"\n  SUPPORTED TARGET (confirmed + likely) = {target} keys"
          f"  <- the only honest denominator")
    print(f"  UNKNOWN is a research queue of {len(buckets['UNKNOWN'])} keys and does "
          "NOT count against coverage")

    for b in ("EXCLUDED", "UNKNOWN"):
        kinds = collections.Counter(r[3].split(" —")[0].split(";")[0] for r in buckets[b])
        print(f"\n  {b} breakdown:")
        for reason, n in kinds.most_common(6):
            print(f"     {n:4}  {reason}")
        sample = sorted({r[1] for r in buckets[b]})[: args.show]
        print(f"     e.g. {', '.join(sample)[:150]}")

    if args.manuals:
        held = set()
        for f in args.manuals.glob("*.pdf"):
            up = f.stem.upper()
            for c in re.findall(r"\bR(\d{3,4})", up):
                held.add("r" + c.lower())
        covered = {n for _k, n, _t, _w in buckets["TARGET_CONFIRMED"] + buckets["TARGET_LIKELY"]
                   if any(re.match(r"(r\d+)", k).group(1) in held
                          for k, nn, _t2, _w2 in
                          buckets["TARGET_CONFIRMED"] + buckets["TARGET_LIKELY"]
                          if nn == n and re.match(r"(r\d+)", k))}
        missing = sorted(by_name["TARGET_CONFIRMED"] | by_name["TARGET_LIKELY"] - covered)
        print(f"\n  manuals in hand cover {len(covered)} target names; "
              f"{len(missing)} target names still unmanualled")
        print(f"     e.g. {', '.join(missing[: args.show])[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
