"""Fetch every Declaration of Conformity and read the certified machine out of it.

The DoC index gives a TRADE NAME in each filename; the PDF gives the CERTIFIED MODEL
inside ("Product: Robotic Vacuum Cleaner / Model: RLX85CE-6 / Charging Base: RCXE0109").
Neither half alone is the equivalence table — together they are, and the PDF supplies a
code for the many entries whose filename omits one.

⚠ THE PDF IS THE EVIDENCE, THE FILENAME IS THE CLAIM. Where they both speak they have
agreed 11 times out of 11 so far, but that is a small sample and the asymmetry stands:
a code read out of the document body is a reading, a code read off a filename is a
claim. Both are recorded separately here so a later join can choose.

⚠ AND `Product:` IS THE PRODUCT CLASS, WHICH IS WHY IT IS CAPTURED. Roughly two thirds
of this index is hair dryers, toothbrushes and air fryers; the class line is what keeps
a Dazzle hair dryer from being credited as a D20 robot, which is a mistake this corpus
has already made once from a filename.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (compatible; manual-corpus/1.0)"}
FIELD = {
    "product": re.compile(r"Product:\s*(.{3,60}?)\s+(?:Model|Type|Apparatus)", re.I),
    "model": re.compile(r"(?<!Base\s)(?<!Station\s)Model:\s*([A-Z0-9\-+/ ]{3,40}?)\s+(?:Charging|Software|Packaging|Manufacturer|Base)", re.I),
    "base": re.compile(r"(?:Charging Base|Base Station)[^:]{0,20}:\s*([A-Z0-9\-+/ ]{3,40}?)\s+(?:Software|Packaging|Manufacturer)", re.I),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--delay", type=float, default=0.25)
    args = ap.parse_args()

    pdf_dir = args.out / "doc_pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    links = json.loads(args.links.read_text(encoding="utf-8"))
    out_path = args.out / "doc_facts.json"
    facts = {}
    if out_path.exists():
        facts = json.loads(out_path.read_text(encoding="utf-8"))

    from pypdf import PdfReader

    ok = fail = cached = 0
    for i, url in enumerate(links, 1):
        fname = url.rsplit("/", 1)[-1]
        if fname in facts:
            cached += 1
            continue
        local = pdf_dir / fname[:120]
        try:
            if local.exists():
                blob = local.read_bytes()
            else:
                req = urllib.request.Request(url, headers=UA)
                blob = urllib.request.urlopen(req, timeout=90).read()
                local.write_bytes(blob)
                time.sleep(args.delay)
            reader = PdfReader(io.BytesIO(blob))
            # the declaration block is on page 1; reading 48 pages per file is waste
            text = " ".join(" ".join((reader.pages[p].extract_text() or "").split())
                            for p in range(min(2, len(reader.pages))))
            rec = {"file": fname, "pages": len(reader.pages), "chars": len(text)}
            for key, pat in FIELD.items():
                m = pat.search(text)
                rec[key] = m.group(1).strip() if m else ""
            facts[fname] = rec
            ok += 1
        except Exception as err:
            facts[fname] = {"file": fname, "error": f"{type(err).__name__}"}
            fail += 1
        if i % 25 == 0:
            out_path.write_text(json.dumps(facts, indent=1), encoding="utf-8")
            print(f"   ...{i}/{len(links)}  ok={ok} fail={fail}", flush=True)

    out_path.write_text(json.dumps(facts, indent=1), encoding="utf-8")
    if not facts:
        print("MEASURED NOTHING -- no verdict.")
        return 1
    got = [f for f in facts.values() if f.get("model")]
    print(f"\nfetched {ok} (cached {cached}, failed {fail}) of {len(links)}")
    print(f"  entries stating a certified Model: {len(got)}")
    classes: dict[str, int] = {}
    for f in facts.values():
        classes[f.get("product", "") or "(none)"] = classes.get(f.get("product", "") or "(none)", 0) + 1
    for c, n in sorted(classes.items(), key=lambda kv: -kv[1])[:12]:
        print(f"     {n:4}  {c[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
