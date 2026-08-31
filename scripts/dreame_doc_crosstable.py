"""Build the document -> supported-models cross-table.

Chris's scope, 2026-08-27: extract each manual, identify it by what it DECLARES,
then look up what that identity supports. Deliberately NOT fancy - a document that
resolves to nothing is a purge candidate, not a problem to solve here.

Runs over the WHOLE corpus, not the robot folders. Foldering is cosmetic and this
pass found 17 robots sitting in `unclassified` (mova lb10/pf10/nutripal10, X50
Master, L20 Ultra, D10 Plus Gen 2, L40 Ultra).

THREE IDENTITY SIGNALS, ranked by how first-party they are:

  base_codes    the document's own regulatory code. One code is one certified
                machine, and it is the only signal that survives a corpus rename.
  cover         the product name printed on the cover. Dreame uses THREE cover
                grammars and the name sits in a different place in each:
                  "D10 Plus Auto-Empty Robot Vacuum and Mop User Manual"  name first
                  "DreameTech Robot Vacuum D9 NA Version User Manual"     name after
                  "Dreame Aqua10 Ultra Track User Manual Series"          name after
  names_printed the catalogue cross-check the corpus was NAMED by. Kept as an
                attribute, never the key: it can only return names the catalogue
                already declares, which is what made "0 corpus names outside the
                list" a tautology rather than a finding.

⚠ THE COVER EXTRACTOR IS ABLATED, NOT TRUSTED. Documents sharing a reg code must
yield the same cover name - the extractor never sees the code, so agreement is an
independent check. v1 scored 37% agreement and its disagreements were its own
defects (`US-A00` and `EU-A00` are EDITION markers; `Auto-Empty` is half a category
phrase). After cleaning junk from BOTH ends it reached 67%, and every residual
disagreement is a genuine regional rename - GoVac 800 / X50, Matrix10 Ultra /
X50 Ultra MatriX - which is signal the table must keep, not noise to remove.

⚠ ORDER MATTERS INSIDE clean(). The "1 EN" tail is a two-column page artefact, so a
digit is only junk when the EN marker follows it. Stripping bare digits first turned
"GoVac 300" into "GoVac" and "Gen 2" into "Gen" - silently truncating real names,
which is worse than the rubbish it fixed.

The code closure (a document declaring only RLX85CE inherits every name a sibling
with that code prints) gains NAMES for 172 documents but only 2 models. Kept because
per-document identity is the deliverable; do not oversell it as coverage.
"""

import argparse
import csv
import collections
import json
import os
import re
from pathlib import Path

D = r'C:\Users\CKing\Documents\durable\dreame-port-fixture\derived'
SP = os.path.dirname(__file__)
man = json.load(open(D + r'\corpus-manifest.json', encoding='utf-8'))
cache = json.load(open(D + r'\manual_text_cache.json', encoding='utf-8'))

BOILER = re.compile(
    r'The illustrations in this manual are for reference only\.?\s*'
    r'(?:Please refer to the actual product\.?)?', re.I)

CATEGORY = (r'(?:Auto-Empty\s+)?(?:Robot\s+Vacuum(?:\s+Cleaner)?(?:\s+and\s+Mop)?|'
            r'Vacuum\s+and\s+Mop)')

# Ordered most-reliable first. The brand anchor is the strongest because Dreame only
# writes it on a cover; the bare "<NAME> User Manual" form is dropped entirely - it
# was the sole source of the US-A00 / EU-A00 rubbish.
PATTERNS = [
    re.compile(r'Dreame(?:Tech|bot)?\s+' + CATEGORY + r'\s+([A-Z][\w\'\+\-]*(?:\s+[\w\'\+\-]+){0,5}?)\s+User Manual'),
    re.compile(r'Dreame(?:Tech|bot)?\s+([A-Z][\w\'\+\-]*(?:\s+[\w\'\+\-]+){0,5}?)\s+(?:User Manual|Series\b)'),
    re.compile(r'([A-Z][\w\'\+\-]*(?:\s+[\w\'\+\-]+){0,5}?)\s+' + CATEGORY + r'\s+(?:with[^.]{0,70}?\s+)?User Manual'),
]

# A candidate that is only category/edition/legal vocabulary is not a product name.
JUNK_WORDS = {'auto', 'empty', 'auto-empty', 'robot', 'vacuum', 'mop', 'and', 'with',
              'user', 'manual', 'series', 'cleaner', 'version', 'the', 'read', 'this',
              'contents', 'website', 'manufactured', 'by', 'made', 'in', 'china', 'dreame', 'dreametech',
              'innovation', 'technology', 'trading', 'suzhou', 'tianjin', 'co', 'ltd'}
RE_EDITION = re.compile(r'^(?:[A-Z]{2}|US|EU|UK|NA|CN)[-_][A-Z]?\d{2,3}$', re.I)


def clean(cand: str) -> str:
    """Strip everything that is not the product name, in the order that matters.

    The "1 EN" / "1 ENContents" tail is a two-column page artefact, so the DIGIT is
    only junk when the EN marker follows it. Removing EN tokens first destroyed that
    evidence and turned "GoVac 300" into "GoVac" and "Gen 2" into "Gen" - a worse
    error than the one it fixed, because it silently truncates real names.
    """
    words = [w for w in re.split(r"\s+", cand.strip(" -+_")) if w]

    # 1. drop "<digits> EN..." PAIRS while both halves are still visible
    out = []
    i = 0
    while i < len(words):
        if (re.fullmatch(r"\d+", words[i]) and i + 1 < len(words)
                and re.fullmatch(r"EN|ENContents|Contents", words[i + 1], re.I)):
            i += 2
            continue
        out.append(words[i])
        i += 1
    words = out

    # 2. drop edition markers, reg codes and stray markers wherever they sit
    words = [w for w in words
             if not RE_EDITION.match(w)
             and not re.fullmatch(r"RL[A-Z]\d{1,2}[A-Z]{2,4}(?:-[A-Z0-9]+)*", w)
             and not re.fullmatch(r"EN|ENContents|Contents", w, re.I)]

    # 3. trim junk vocabulary from BOTH ends (never the middle: "Ultra Roller Kit")
    while words and words[0].lower().strip("-") in JUNK_WORDS:
        words.pop(0)
    while words and words[-1].lower().strip("-") in JUNK_WORDS:
        words.pop()

    res = " ".join(words).strip(" -+_")
    if len(res) < 2 or RE_EDITION.match(res):
        return ""
    return res


def cover_name(text: str) -> str:
    head = ' '.join(BOILER.sub(' ', text[:2000]).split())
    for rx in PATTERNS:
        for m in rx.finditer(head):
            c = clean(m.group(1))
            if c:
                return c
    return ''


RE_ROBOT = re.compile(r"\bRL[A-Z]\d{1,2}[A-Z]{2,4}(?:-\d+)?\b")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derived", type=Path, required=True)
    ap.add_argument("--devices", type=Path, required=True)
    args = ap.parse_args()

    man = json.loads((args.derived / "corpus-manifest.json").read_text(encoding="utf-8"))
    cache = json.loads((args.derived / "manual_text_cache.json").read_text(encoding="utf-8"))

    norm = lambda t: re.sub(r"[^a-z0-9]", "", str(t).lower())
    byname: dict[str, set] = {}
    for n, m in re.findall(r"^\|\s*([^|]+?)\s*\|\s*([a-z]+\.vacuum\.[a-z0-9_]+)\s*\|",
                           args.devices.read_text(encoding="utf-8"), re.M):
        byname.setdefault(norm(n), set()).add(m)
    all_models = {m for s_ in byname.values() for m in s_}

    docs = []
    for x in man:
        t = cache.get(x.get("was") or "", {}).get("text", "")
        ok = bool(t and len(t) > 200)
        docs.append({
            "file": x["name"], "folder": x.get("folder"), "pages": x.get("pages"),
            "has_text": ok,
            "base_codes": sorted({re.sub(r"-\d+$", "", c) for c in RE_ROBOT.findall(t)}) if ok else [],
            "sku_codes": sorted(set(RE_ROBOT.findall(t))) if ok else [],
            "cover": cover_name(t) if ok else "",
            "names_printed": x.get("names_printed", []),
            "r_code": x.get("r_code", ""),
        })

    # A code carries every name any sibling document prints for it.
    code_names: dict[str, set] = collections.defaultdict(set)
    for d in docs:
        nm = {n for n in ({d["cover"]} | set(d["names_printed"])) if n and norm(n) in byname}
        for c in d["base_codes"]:
            code_names[c] |= nm

    for d in docs:
        direct = {n for n in ({d["cover"]} | set(d["names_printed"])) if n and norm(n) in byname}
        via = set().union(*(code_names[c] for c in d["base_codes"])) if d["base_codes"] else set()
        d["names_resolved"] = sorted(direct | via)
        d["models"] = sorted({m for n in d["names_resolved"] for m in byname[norm(n)]})

    res = [d for d in docs if d["models"]]
    sig = [d for d in docs if d["base_codes"] or d["cover"] or d["names_printed"]]
    noid = [d for d in docs if d["has_text"] and not (d["base_codes"] or d["cover"] or d["names_printed"])]
    print(f"documents              {len(docs)}")
    print(f"  usable text          {sum(1 for d in docs if d['has_text'])}")
    print(f"  any identity signal  {len(sig)}")
    print(f"  resolve to a model   {len(res)}")
    print(f"  text but no identity {len(noid)}   <- purge candidates")
    print(f"  no usable text       {sum(1 for d in docs if not d['has_text'])}   <- extraction backlog")
    print(f"  model reach          {len({m for d in docs for m in d['models']})}/{len(all_models)}")

    (args.derived / "doc_model_crosstable.json").write_text(
        json.dumps(docs, indent=1, ensure_ascii=False), encoding="utf-8")
    with (args.derived / "doc_model_crosstable.tsv").open(
            "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter='\t', lineterminator='\n')
        w.writerow(["file", "folder", "base_codes", "sku_codes", "cover",
                    "names_resolved", "n_models", "models"])
        for d in docs:
            w.writerow([d["file"], d.get("folder") or "",
                        ",".join(d["base_codes"]), ",".join(d["sku_codes"]),
                        d["cover"], "; ".join(d["names_resolved"]),
                        len(d["models"]), ",".join(d["models"])])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
