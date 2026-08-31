"""Give every manual a logical name, and say which target models still have none.

THREE THINGS, ONE PASS, because they share the only sound join:

  1. what each manual IS      -> the marketing names its TEXT prints
  2. what it should be CALLED -> a filename built from that
  3. what is MISSING          -> target names no manual prints

⚠ THE FILENAME IS NEVER THE EVIDENCE. Dreame names its PDFs by r-code, so joining on
that code looks obviously right and is not: of 63 codes across the Dreame-named files
only 31 are exactly a model key, and the r-stem that would rescue the rest is ambiguous
(77 stems carry more than one product; ``r9524`` is GoVac 200, D15 Plus AND F10 Plus).
Exact matching throws away half the corpus, stem matching credits a manual to every
sibling. So the name written ONTO the file here is a convenience for humans, and the
manifest -- which records every name the text printed -- is the measurement. Renaming a
file must never be able to change a coverage number.

⚠ LONGEST MATCH WINS, AND NOTHING ELSE SURVIVES THIS CATALOGUE. 181 of 389 declared
names are a prefix of another name; ``S30 Pro`` is a prefix of nine. Four earlier
matchers died here: bare substring (``e10`` inside ``shin-e10``), single-token equality
(broke ``GoVac 205 Plus``), contiguous token run (``E30 Pro`` inside ``e30-pro-PLUS``),
and a verifier that reproduced the prefix bug an hour after it was fixed elsewhere.

⚠ THREE COVERAGE STATES, NOT TWO.
    COVERED   a manual's TEXT names the model            -- real
    ATTESTED  only a FILENAME claims it                  -- held out of the hunt, NOT counted
    MISSING   neither                                    -- the hunting list
  A filename is the same class of claim that made a eufy manual look like a Dreame E20.

⚠ FOLDERING IS COSMETIC. The robot / other / render-queue split below is a keyword
heuristic so a human can find things. It never feeds the coverage arithmetic.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dreame_target_models import (  # noqa: E402
    classify,
    load_device_info,
    load_names,
)

#: Regulatory model code as printed on a Specifications page (RLX85CE, RLD35GD).
#: This is the ONE CERTIFIED MACHINE identifier -- two names sharing it are one robot.
REG_CODE = re.compile(r"\b(R[A-Z]{2,3}\d{2,3}[A-Z]{0,2}(?:-\d+)?)\b")
#: Dreame's own PDF code, as it appears in filenames only.
R_CODE = re.compile(r"\bR(\d{3,5})([A-Z]{0,2})\b", re.I)

#: Language tokens Dreame stamps into its own filenames. This list is the ABLATION for
#: any language claim: a detector is trustworthy only when it recovers these.
LANG = re.compile(
    r"\b(EN|DE|FR|IT|ES|ESLA|PL|NL|NO|SV|EL|PT|BR|HE|AR|TR|VI|VN|TH|ID|FIL|MS|BM|KM|"
    r"RU|UA|JA|KO|FI|DA|DK|KK|UZ|CZ|CS|HU|SL|SK|SR|LT|LV|RO|ET|HR|BG|ZH-HK|ZH-TW|"
    r"ZH-HANT|ZH-HANS|CN|UK)\b",
    re.I,
)

#: ⚠ LONGEST-MATCH-WINS ONLY PROTECTS AGAINST NAMES THE CATALOGUE KNOWS. `X60 Ultra
#: Complete` is a real retail name that the integration never declares, so `X60 Ultra`
#: matched inside it with a clean space boundary and was silently credited — the prefix
#: bug, reappearing through the one door longest-match cannot close.
#:
#: What decides it is the corpus's own measurement of the naming convention: a
#: regulatory code is ONE CERTIFIED MACHINE, and across the manuals that print one,
#: `Complete` appeared with the SAME code 5 times out of 5 and `Heat` 1 of 1 — those
#: words change the box or the firmware, not the robot. `Pro` (1 same / 8 different),
#: `Ultra` (1/3), `Plus` (0/3) and `Master` (0/1) change the hardware.
#:
#: So a trailing word that only re-packages INHERITS the base name, and one that
#: re-engineers it REJECTS the match. Sample sizes are small (5 pairs, 8 pairs) and
#: this is the asymmetry the note flagged: same-code-same-machine is strong,
#: different-code-different-maintenance is weak. Erring toward REJECT only ever
#: leaves a name on the hunting list, which is the recoverable direction.
INHERITS = {"complete", "heat"}
HARDWARE_TIER = {"pro", "ultra", "plus", "master", "max", "gen", "roller", "track",
                 "disc", "mix", "prime", "ae", "ce", "s"}

#: Foldering only. Positive words decide "robot"; negative words decide "other".
ROBOT_WORDS = ("robot vacuum", "vacuum-mop", "robotic vacuum", "docking station",
               "self-cleaning base", "mop pad", "lds", "lidar", "auto-empty")
OTHER_WORDS = ("hair dryer", "straightener", "toothbrush", "air purifier", "air fryer",
               "curling", "shaver", "humidifier", "lawn mower", "robotic mower",
               "hair removal", "styler", "cordless vacuum cleaner", "wet and dry")


#: A "tight" join: characters that glue tokens into ONE identifier (`shin-e10`,
#: `e30_pro_plus`) as opposed to a space, which separates words in prose.
TIGHT = "\x01"


def norm(s: str) -> str:
    """Normalise, PRESERVING whether each gap was a space or a hyphen/underscore.

    ⚠ COLLAPSING BOTH TO A SPACE IS THE `shin-e10` BUG, AND I SHIPPED IT ONCE HERE.
    Flattening `-` to a space turns an intra-identifier position into a word boundary,
    so `E10` matches inside `shin-e10` — a Shine 10 hair styler credited as a robot
    vacuum. But hyphens cannot simply be barriers either: `e30-pro-PLUS` IS `E30 Pro
    Plus`. The gap is not noise, so it is not discarded: a name may SPAN a tight join,
    it may not START or END against one.

    ⚠ THE ALPHABET IS UNICODE, AND AN ASCII-ONLY CLASS IS CATASTROPHIC HERE. An
    `[^a-z0-9]` filter deletes the CJK characters from the catalogue's Chinese names,
    so `免洗10` becomes the pattern `10` and `澄净 Pro` becomes `pro`. Those two matched
    1396 and 433 of 1998 manuals — 79% of the corpus read as "robot vacuum" and the
    number looked like wonderful coverage. A name must never normalise to a fragment
    of itself.

    ⚠ `+` IS PART OF THE NAME, NOT PUNCTUATION. `S10+` and `S10` are different
    products; stripping the plus collapses them into one key and silently drops
    whichever the dict happens to see second.
    """
    s = re.sub(r"[\-_]+", TIGHT, s.lower())
    s = re.sub(rf"[^\w+{TIGHT}]+", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


#: Channel prefixes this corpus was harvested under. Stripping them is safe: the
#: channel is recorded in the manifest, and it is not what the document IS.
CHANNEL = re.compile(r"^(DR|MV|CK\d?|ZD|SD|DZ|MOVA)[-_]([a-z]{2,6}[-_])?", re.I)


def clean_stem(fname: str, langs: list[str]) -> str:
    """Fall back to the ORIGINAL name, tidied — never to a bare hash.

    ⚠ A RENAME MUST NOT LOSE WHAT THE OLD NAME KNEW. The first cut sent every file
    with no target-name match to `<sha8>.pdf`, which turned
    `DR-global-User_Manual-H11_Core-VN_PT_GE_UZ.pdf` into `bea00bde.pdf` — 666 hair
    dryers and air purifiers made permanently unsearchable to a human, and a corpus
    where two thirds of the filenames say nothing is worse than the mess it replaced.
    Products outside our catalogue are still documents somebody may need to find.
    """
    stem = fname.rsplit(".", 1)[0]
    stem = CHANNEL.sub("", stem)
    if langs:  # the language tail is carried separately; drop it from the stem
        stem = re.sub(r"[-_]?\b(" + "|".join(re.escape(x) for x in langs) + r")\b",
                      "", stem, flags=re.I)
    stem = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{20,}\b", "", stem)  # embedded UUIDs
    stem = re.sub(r"\b\d{8,}\b", "", stem)  # date/serial runs
    return slug(stem)[:48].strip("-")


def build_matcher(target_names: set[str]):
    """Longest-match-wins finder over a normalised text stream.

    Normalisation collapses every non-alphanumeric run to one space on BOTH sides --
    the bug that nearly produced "the namespaces are completely disjoint" was a
    transform applied to one side of a comparison only.
    """
    # ⚠ ONE ALTERNATION, NOT 339 SCANS. Scanning each name separately is 339 passes over
    # every manual — ~40 GB of regex across this corpus, tens of minutes. A single
    # alternation makes it one pass, and it is not merely an optimisation: Python's
    # alternation is LEFTMOST-FIRST, so ordering the branches longest-first gives
    # longest-match-wins for free at every position. "L40 Ultra" can no longer win
    # where "L40 Ultra Gen 2" is what the page actually says.
    # ⚠ COLLISIONS ARE REPORTED, NEVER SILENTLY DROPPED. Three declared names differ
    # only by case, and extracted text cannot tell such a pair apart — that is a real
    # limit of the evidence, so it is printed rather than resolved by dict ordering.
    by_norm: dict[str, list[str]] = collections.defaultdict(list)
    for n in target_names:
        by_norm[norm(n)].append(n)
    collisions = {k: v for k, v in by_norm.items() if len(v) > 1}
    if collisions:
        print(f"⚠ {len(collisions)} name(s) indistinguishable after normalisation "
              f"(credited to the first): "
              + "; ".join("/".join(sorted(v)) for v in list(collisions.values())[:5]))
    ordered = sorted(((k, sorted(v)[0]) for k, v in by_norm.items()),
                     key=lambda kv: len(kv[0]), reverse=True)
    # A name's own internal gaps may appear as either a space or a tight join in the
    # wild (`E30 Pro Plus` prints as `e30-pro-plus` in a URL), so match either.
    branches = [re.escape(k).replace("\\ ", f"[ {TIGHT}]") for k, _ in ordered]
    # Gapless key, first-wins: `ordered` is longest-first, and a plain dict
    # comprehension would let a shorter colliding name overwrite the longer one —
    # silently reinstating the prefix bug at the lookup step instead of the match step.
    lookup: dict[str, str] = {}
    for k, v in ordered:
        lookup.setdefault(k.replace(" ", ""), v)
    # Boundaries must use the SAME unicode alphabet as norm(), or a Chinese name would
    # be allowed to start mid-word exactly where the ASCII class stopped looking.
    big = re.compile(
        rf"(?<![\w+{TIGHT}])(" + "|".join(branches) + rf")(?![\w+{TIGHT}])",
        re.UNICODE,
    )

    def find(text: str, loose: bool = False) -> list[str]:
        """loose=True treats `-`/`_` as SPACES rather than joins.

        ⚠ USE IT ON FILENAMES ONLY, AND NEVER FOR COVERAGE. Dreame writes filenames as
        `D20_Plus_R2564_EN_DE`, where `_` is a word space — under the strict rule that
        whole string is one identifier and matches nothing, which silently emptied the
        ATTESTED bucket from 19 names to 0. But loose matching is exactly what let
        `E10` match `shin-e10`, so what it produces is a HINT, not evidence: it may
        only ever ANNOTATE a missing name, never mark one covered.
        """
        hay = norm(text)
        if loose:
            hay = hay.replace(TIGHT, " ")
        seen: dict[str, None] = {}
        for m in big.finditer(hay):
            nxt = re.match(rf"[ {TIGHT}]([a-z0-9]+)", hay[m.end():])
            if nxt and nxt.group(1) in HARDWARE_TIER:
                continue  # a longer product the catalogue does not declare
            key = re.sub(rf"[ {TIGHT}]", "", m.group(1))
            seen.setdefault(lookup[key], None)
        return list(seen)

    return find


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--devices", type=Path, required=True)
    ap.add_argument("--const", type=Path, required=True)
    ap.add_argument("--derived", type=Path, required=True,
                    help="dir holding index.json + text/")
    ap.add_argument("--manuals", type=Path, required=True)
    ap.add_argument("--apply", action="store_true", help="actually rename on disk")
    args = ap.parse_args()

    devs, capsets, _keys, index = load_device_info(args.const)
    names = load_names(args.devices)

    target_names: set[str] = set()
    keys_of_name: dict[str, set[str]] = collections.defaultdict(set)
    for key, name in names.items():
        bucket, _kind, _why = classify(key, name, devs, capsets, index)
        keys_of_name[name].add(key)
        if bucket in ("TARGET_CONFIRMED", "TARGET_LIKELY"):
            target_names.add(name)
    target_keys = {k for n in target_names for k in keys_of_name[n]}
    print(f"denominator: {len(target_names)} target names carrying {len(target_keys)} keys")

    records = json.loads((args.derived / "index.json").read_text(encoding="utf-8"))
    print(f"corpus: {len(records)} indexed files")
    if not records:
        print("MEASURED NOTHING -- no verdict.")
        return 1
    find = build_matcher(target_names)

    plan = []
    covered: dict[str, set[str]] = collections.defaultdict(set)
    attested: dict[str, set[str]] = collections.defaultdict(set)
    for rec in records:
        fname = rec["file"]
        sha = rec.get("sha256", "")
        txt = ""
        tp = args.derived / "text" / f"{sha[:12]}.txt"
        if tp.exists():
            txt = tp.read_text(encoding="utf-8", errors="replace")

        printed = find(txt) if txt else []
        from_name = find(fname, loose=True)
        for n in printed:
            covered[n].add(fname)
        for n in from_name:
            if n not in printed:
                attested[n].add(fname)

        reg = sorted({m.group(1).upper()
                      for m in REG_CODE.finditer(" ".join(txt.split()))})
        rm = R_CODE.search(fname)
        rcode = f"R{rm.group(1)}{rm.group(2).upper()}" if rm else ""
        langs = sorted({t.upper() for t in LANG.findall(fname)})

        low = txt[:20000].lower()
        if printed:
            folder = "robot"
        elif rec.get("text_pages", 0) == 0:
            folder = "render-queue"
        elif any(w in low for w in OTHER_WORDS) and not any(w in low for w in ROBOT_WORDS):
            folder = "other"
        elif any(w in low for w in ROBOT_WORDS):
            folder = "robot-unmatched"
        else:
            folder = "unclassified"

        # Naming may lean on the filename hint even though coverage may not: a manual
        # with no text layer has nothing else, and `govac-205-plus_R95279.pdf` beats
        # `DZ-GoVac-205-Plus.pdf` for a human even when the evidence is only a filename.
        # The `~` marks it as hinted, so the weaker claim stays visible on the disk.
        primary = max(printed, key=len) if printed else ""
        hinted = not primary and from_name
        if hinted:
            primary = max(from_name, key=len)
        head = slug(primary) if primary else (clean_stem(fname, langs) or sha[:8])
        parts = [head]
        if hinted:
            parts[0] = "~" + parts[0]
        if len(printed) > 1:
            parts[0] += f"+{len(printed) - 1}"
        # don't repeat the code the head already carries (`r5042_R5042_EN`)
        if rcode and rcode.lower() not in head.lower().replace("-", ""):
            parts.append(rcode)
        if reg and not rcode:
            parts.append(reg[0])
        if langs:
            parts.append("-".join(langs[:6]) + ("plus" if len(langs) > 6 else ""))
        newname = "_".join(p for p in parts if p)[:110] + ".pdf"

        plan.append({
            "old": fname,
            "sha256": sha,
            "folder": folder,
            "new": newname,
            "names_printed": printed,
            "names_in_filename_only": [n for n in from_name if n not in printed],
            "reg_codes": reg[:8],
            "r_code": rcode,
            "langs": langs,
            "pages": rec.get("pages", 0),
            "text_pages": rec.get("text_pages", 0),
        })

    # collisions -> disambiguate with sha, never by dropping a file
    seen: collections.Counter = collections.Counter()
    for p in plan:
        kk = (p["folder"], p["new"])
        seen[kk] += 1
        if seen[kk] > 1:
            p["new"] = p["new"][:-4] + f"_{p['sha256'][:8]}.pdf"

    (args.derived / "rename-manifest.json").write_text(
        json.dumps(plan, indent=1), encoding="utf-8")

    by_folder = collections.Counter(p["folder"] for p in plan)
    print("\nFOLDERING (cosmetic -- never feeds coverage):")
    for f, n in by_folder.most_common():
        print(f"   {f:18} {n:5}")

    # ⚠ A HINT ANNOTATES, IT DOES NOT EXCLUDE. The earlier scheme subtracted attested
    # names from the hunting list, so a filename — the same class of claim that made a
    # eufy manual look like a Dreame E20 — could remove a model from the work queue
    # with nothing ever having read the document.
    not_covered = target_names - set(covered)
    missing = sorted(not_covered)
    only_attested = sorted(n for n in not_covered if attested.get(n))
    print("\nCOVERAGE by NAME (the unit of work):")
    print(f"   COVERED  (a manual's TEXT names it)   {len(covered):4} / {len(target_names)}")
    print(f"   NOT COVERED (the hunting list)        {len(missing):4}")
    print(f"     ...of those, filename-HINTED        {len(only_attested):4}"
          "   <- probably on disk already; verify, do not count")
    ck = {k for n in covered for k in keys_of_name.get(n, ())}
    print(f"   keys reached by COVERED names: {len(ck)} / {len(target_keys)}"
          f"  ({100 * len(ck) / len(target_keys):.1f}%)")

    # The gap list, ordered by what it BUYS: a name carrying eight keys is eight
    # devices, and hunting it first is worth more than a name carrying one.
    ranked = sorted(missing, key=lambda n: (-len(keys_of_name.get(n, ())), n))
    hinted_missing = {n: sorted(attested[n]) for n in missing if attested.get(n)}
    lines = ["# Dreame manual gaps — target names with no manual", ""]
    lines.append(f"{len(missing)} of {len(target_names)} target names are unheld, "
                 f"carrying {sum(len(keys_of_name.get(n, ())) for n in missing)} keys.")
    lines.append("")
    lines.append("| target name | keys | filename hint (weak — verify by rendering) |")
    lines.append("|---|---:|---|")
    for n in ranked:
        hint = hinted_missing.get(n, [])
        lines.append(f"| {n} | {len(keys_of_name.get(n, ()))} | "
                     f"{hint[0][:60] if hint else ''} |")
    (args.derived / "GAPS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"   of the missing, {len(hinted_missing)} have a FILENAME HINT "
          "(likely already on disk, unreadable as text)")

    (args.derived / "coverage.json").write_text(json.dumps({
        "target_names": sorted(target_names),
        "covered": {k: sorted(v) for k, v in covered.items()},
        "attested_only": {k: sorted(attested[k]) for k in only_attested},
        "missing": missing,
        "keys_of_name": {k: sorted(v) for k, v in keys_of_name.items()},
    }, indent=1), encoding="utf-8")

    if args.apply:
        moved = 0
        for p in plan:
            src = args.manuals / p["old"]
            if not src.exists():
                continue
            dst = args.manuals / p["folder"] / p["new"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                continue
            src.rename(dst)
            moved += 1
        print(f"\nrenamed {moved} files (reversible from rename-manifest.json)")
    else:
        print("\nDRY RUN -- pass --apply to rename. Manifest written either way.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
