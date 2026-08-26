"""Adjudicate an external assistant's rebadge claims against the integration's own data.

Farming the manual hunt out to Gemini/GPT/etc. is good for RETRIEVAL — they can search
the web and we cannot do it at that breadth. It is not good for ADJUDICATION. The first
reply we got asserted twelve model equivalences, found zero manuals, and wrote notes
like *"secondary firmware token matching the flagship X50 architecture"* — there is no
such thing as a firmware token here; r-codes are platform ids. Fluent mechanism-
invention wrapped around a guess reads exactly like knowledge.

So: never believe a claim, check it. Two signals, both from the vendor's own blob:

  PLATFORM  two names sharing an r-code are the same hardware. Proof, not inference.
  PROFILE   two names sharing a capability-set index have an identical declared
            profile. Strong evidence.

⚠ AND KNOW WHAT THE INSTRUMENT CANNOT SEE. Measured against 93 model names that appear
under MORE THAN ONE r-code — same product by construction — profile-matching detects
the relationship only **28%** of the time. So `UNVERIFIABLE` genuinely means "we cannot
tell", NOT "false". A claim this tool cannot confirm is not thereby refuted, and
treating it as refuted would be the same error in the opposite direction.

    python scripts/verify_rebadge_claims.py reply.json \\
        --devices supported_devices.md --const dreame_dev_const.py

Exit code is 1 if anything CONFLICTS, so this can gate an ingest.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dreame_target_models import load_device_info, load_names  # noqa: E402


def platform(key: str) -> str | None:
    m = re.match(r"(r\d+)", key)
    return m.group(1) if m else None


def build_indexes(devs, capsets, index, names):
    by_platform: dict[str, set[str]] = collections.defaultdict(set)
    by_profile: dict[int, set[str]] = collections.defaultdict(set)
    for key, name in names.items():
        p = platform(key)
        if p:
            by_platform[p].add(name)
        if key in index:
            by_profile[devs[index[key]][2]].add(name)
    return by_platform, by_profile


def adjudicate(r_code, claim, names, devs, index, by_platform, by_profile):
    """(verdict, evidence) for one claimed equivalence."""
    keys = [k for k in names if platform(k) == r_code]
    if not keys:
        return "UNKNOWN_RCODE", "no model key uses this r-code"

    siblings = {n for n in by_platform.get(r_code, set())}
    profiles = {devs[index[k]][2] for k in keys if k in index}
    profile_sibs = {n for p in profiles for n in by_profile[p]}
    pool = siblings | profile_sibs
    # A GoVac claim is about what the GoVac IS, so its own name is not evidence.
    others = sorted(n for n in pool if not n.lower().startswith(r_code[:0] or "govac"))

    claimed = [t.strip().lower() for t in re.split(r"\s*/\s*", claim) if t.strip()]
    pool_l = {n.lower() for n in pool}
    if any(any(c in p or p in c for p in pool_l) for c in claimed):
        return "AGREES", ", ".join(others)[:60]
    if others:
        return "CONFLICT", ", ".join(others)[:60]
    return "UNVERIFIABLE", "nothing shares this platform or profile"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reply", type=Path, help="JSON the external assistant returned")
    ap.add_argument("--devices", type=Path, required=True)
    ap.add_argument("--const", type=Path, required=True)
    args = ap.parse_args()

    devs, capsets, _keys, index = load_device_info(args.const)
    names = load_names(args.devices)
    by_platform, by_profile = build_indexes(devs, capsets, index, names)

    data = json.loads(args.reply.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [{"r_code": k, "equivalent_dreame_model": v} for k, v in data.items()]

    tally: collections.Counter = collections.Counter()
    urls = 0
    print(f"{'r-code':10} {'verdict':14} claim -> what our data shows")
    print("-" * 92)
    for row in data:
        rc = str(row.get("r_code", "")).strip()
        claim = str(row.get("equivalent_dreame_model") or "").strip()
        urls += len(row.get("manual_urls") or [])
        if not claim:
            tally["NO_CLAIM"] += 1
            print(f"{rc:10} {'NO CLAIM':14} (no equivalence offered)")
            continue
        verdict, evidence = adjudicate(rc, claim, names, devs, index,
                                       by_platform, by_profile)
        tally[verdict] += 1
        print(f"{rc:10} {verdict:14} {claim[:26]:28} -> {evidence}")

    total = sum(tally.values())
    print(f"\n  {total} claim(s): " + "  ".join(f"{k} {v}" for k, v in tally.most_common()))
    print(f"  manual URLs actually supplied: {urls}")
    if not urls:
        print("  ⚠ ZERO manuals returned — the retrieval task produced nothing; these are "
              "assertions only")
    if tally["UNVERIFIABLE"]:
        print(f"  ⚠ {tally['UNVERIFIABLE']} UNVERIFIABLE means WE CANNOT TELL, not false — "
              "profile-matching misses ~72% of known rebadges")
    return 1 if tally["CONFLICT"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
