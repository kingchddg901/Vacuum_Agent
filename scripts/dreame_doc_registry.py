"""Build the model equivalence table from Dreame's Declaration-of-Conformity index.

⚠ THIS IS THE INSTRUMENT THE CORPUS NOTES KEPT ASKING FOR AND NEVER BUILT. Coverage has
always been measured as "does a manual's text print this name", which answers *do we
hold this document* — not *do we know how to maintain this machine*. Those differ,
because one certified machine is sold under several marketing names: `RLX85CE` is
GoVac 800, X50, X50 Ultra and X50 Ultra Complete all at once. Hold any one of those
manuals and you hold the maintenance procedure for all four.

The blocker was always that a regulatory code can only be read off a manual, and a
MISSING name is missing precisely because we have no manual to read. Dreame's public
DoC index breaks that circle: every entry is a PDF whose FILENAME carries all three
identifiers at once —

    DoC_English-R9515-RLX86DE_X60_Ultra_<uuid>.pdf
                 ^r-code  ^reg code ^marketing name

so it maps name -> certified machine for models we hold nothing for.

⚠ AND IT IS STILL A FILENAME. The corpus's oldest rule applies unchanged: a filename is
a CLAIM, not evidence. What this earns is the right to say "the vendor's own conformity
index says these two names are one certified machine", which is a citable claim about a
regulatory document — not a reading of one. Anything it asserts about a machine we can
check against a held manual IS checked, and the agreement rate is reported, because an
instrument that has never been shown able to disagree is not an instrument.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dreame_corpus_name import build_matcher  # noqa: E402
from dreame_target_models import (  # noqa: E402
    classify,
    load_device_info,
    load_names,
)

#: Regulatory ("certified machine") code: RLX85CE, RLF41GD, RLD35GD, RLX85CE-4.
REG = re.compile(r"\bR[A-Z]{2,3}\d{2,4}[A-Z]{0,2}(?:-\d+)?\b")
#: Dreame's internal product code: R9515, R5048, R502K.
RCODE = re.compile(r"\bR\d{3,5}[A-Z]?\b")
#: Shopify appends a uuid to most filenames; it is noise.
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def parse(fname: str) -> dict:
    """Pull (r-codes, reg-codes, residual name text) out of one DoC filename."""
    stem = fname.rsplit(".", 1)[0]
    stem = UUID.sub(" ", stem)
    regs = REG.findall(stem)
    # An r-code is a strict subset pattern of nothing else here, but a reg code can
    # start with R too — strip the reg codes FIRST so they are not re-read as r-codes.
    residual = stem
    for r in regs:
        residual = residual.replace(r, " ")
    rcodes = RCODE.findall(residual)
    for r in rcodes:
        residual = residual.replace(r, " ")
    residual = re.sub(r"(?i)\b(doc|declaration|of|conformity|english|en|new|\d{2})\b", " ", residual)
    residual = re.sub(r"[_\-]+", " ", residual)
    return {
        "file": fname,
        "reg_codes": sorted(set(regs)),
        "r_codes": sorted(set(rcodes)),
        "name_text": re.sub(r"\s+", " ", residual).strip(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--devices", type=Path, required=True)
    ap.add_argument("--const", type=Path, required=True)
    ap.add_argument("--links", type=Path, required=True)
    ap.add_argument("--corpus", type=Path, required=True,
                    help="derived dir holding rename-manifest.json + coverage.json")
    ap.add_argument("--facts", type=Path,
                    help="doc_facts.json from dreame_doc_fetch.py — the code read out "
                         "of the PDF BODY, which most filenames omit")
    args = ap.parse_args()

    devs, capsets, _k, index = load_device_info(args.const)
    names = load_names(args.devices)
    target, keys_of_name = set(), collections.defaultdict(set)
    for key, name in names.items():
        bucket, _kind, _why = classify(key, name, devs, capsets, index)
        keys_of_name[name].add(key)
        if bucket in ("TARGET_CONFIRMED", "TARGET_LIKELY"):
            target.add(name)
    find = build_matcher(target)

    links = json.loads(args.links.read_text(encoding="utf-8"))
    entries = [parse(u.rsplit("/", 1)[-1]) for u in links]

    # ⚠ ONLY ROBOT ENTRIES MAY CONTRIBUTE. Two thirds of this index is hair dryers,
    # shavers and floor washers, and a trade name matched off a filename has already
    # credited a Dazzle hair dryer as a D20 robot once in this corpus. The PDF states
    # its own product class, so the filter is a reading rather than a guess.
    facts = {}
    if args.facts and args.facts.exists():
        facts = json.loads(args.facts.read_text(encoding="utf-8"))
    robot = non_robot = unclassified = 0
    for e in entries:
        f = facts.get(e["file"], {})
        cls = (f.get("product") or "").lower()
        e["product"] = f.get("product", "")
        e["body_model"] = f.get("model", "")
        if "robot" in cls:
            e["is_robot"] = True
            robot += 1
            if e["body_model"]:
                e["reg_codes"] = sorted(set(e["reg_codes"]) | {e["body_model"]})
        elif cls:
            e["is_robot"] = False
            non_robot += 1
        else:
            e["is_robot"] = None  # class unknown — excluded, never assumed
            unclassified += 1
    if facts:
        print(f"DoC product class from the PDF body: robot {robot} | "
              f"other {non_robot} | unstated {unclassified} (excluded)")
    entries = [e for e in entries if e.get("is_robot")] if facts else entries
    if not entries:
        print("MEASURED NOTHING -- no verdict.")
        return 1

    # name -> reg codes, straight from the vendor's conformity index
    doc_name_regs: dict[str, set[str]] = collections.defaultdict(set)
    doc_name_rcodes: dict[str, set[str]] = collections.defaultdict(set)
    matched = 0
    for e in entries:
        hit = find(e["name_text"], loose=True)
        if hit:
            matched += 1
        for n in hit:
            doc_name_regs[n].update(e["reg_codes"])
            doc_name_rcodes[n].update(e["r_codes"])

    print(f"DoC entries parsed        : {len(entries)}")
    print(f"  naming a TARGET model   : {matched}")
    print(f"  distinct target names   : {len(doc_name_regs)} of {len(target)}")

    cov = json.loads((args.corpus / "coverage.json").read_text(encoding="utf-8"))
    covered, missing = set(cov["covered"]), set(cov["missing"])
    plan = json.loads((args.corpus / "rename-manifest.json").read_text(encoding="utf-8"))

    # reg codes we can actually READ off a manual in hand, and the names on it
    held_regs: dict[str, set[str]] = collections.defaultdict(set)
    for p in plan:
        for c in p["reg_codes"]:
            for n in p["names_printed"]:
                held_regs[c].add(n)

    # ⚠ ABLATION FIRST. Where the DoC and a held manual BOTH give a name a code, do they
    # agree? An index that cannot be caught disagreeing is not evidence of anything.
    # ⚠ BOTH MUST ACTUALLY HAVE A CODE. The first cut scored "the DoC gave no code" as a
    # DISAGREEMENT, which reported 17% agreement and read exactly like a broken
    # instrument — when the truth was that most DoC filenames simply omit the code.
    # An absent measurement is not a conflicting one; conflating them turns silence
    # into evidence against yourself.
    name_held: dict[str, set[str]] = collections.defaultdict(set)
    for c, ns in held_regs.items():
        for n in ns:
            name_held[n].add(c)
    both = [n for n in doc_name_regs
            if doc_name_regs[n] and name_held.get(n)]
    silent = [n for n in doc_name_regs if not doc_name_regs[n] and name_held.get(n)]
    agree = sum(1 for n in both if doc_name_regs[n] & name_held[n])
    dis = len(both) - agree
    print(f"\nABLATION -- names where BOTH sides actually give a code: {len(both)}")
    print(f"   agree    : {agree}")
    print(f"   disagree : {dis}"
          f"   ({100 * agree / max(len(both), 1):.0f}% agreement)")
    print(f"   (a further {len(silent)} names matched a DoC entry that prints NO code —"
          " absent, not conflicting)")
    if not both:
        print("   ⚠ NOTHING TO CHECK AGAINST -- treat every claim below as unverified.")

    # THE PAYOFF: a MISSING name whose DoC code is one we already hold a manual for.
    rescued = {}
    for n in missing:
        for c in doc_name_regs.get(n, ()):
            if c in held_regs:
                rescued.setdefault(n, {"code": c, "via": sorted(held_regs[c])})
    keys = sum(len(keys_of_name[n]) for n in rescued)
    print(f"\nMISSING names whose CERTIFIED MACHINE we already hold a manual for:")
    print(f"   {len(rescued)} names / {keys} keys")
    for n, v in sorted(rescued.items(), key=lambda kv: -len(keys_of_name[kv[0]])):
        print(f"   {len(keys_of_name[n]):2}k  {n:30} = {v['code']:10} = {', '.join(v['via'])}")

    (args.corpus / "doc-registry.json").write_text(json.dumps({
        "entries": entries,
        "name_to_reg": {k: sorted(v) for k, v in doc_name_regs.items()},
        "name_to_rcode": {k: sorted(v) for k, v in doc_name_rcodes.items()},
        "rescued": rescued,
        "ablation": {"checked": len(both), "agree": agree, "disagree": dis},
    }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
