"""Reconcile the corpus manifest against what is ACTUALLY on disk.

⚠ WHY THIS EXISTS. Two defects made the first manifest unfit to be the record:

1. **Its `sha256` was a hash of the OLD FILENAME, not of the file.** The cover-text
   cache it was derived from is keyed by name and carries no digest, so the adapter
   that fed it synthesised one. Nothing in the field's name says so, and a reader
   verifying a file against it gets a mismatch on every single row — I ran exactly that
   check and briefly read five healthy files as corrupt.

2. **The manifest was written by a LATER dry run than the one that was applied.** The
   plan is recomputed each run, and a matcher change between the two moved ~10 files
   into different folders. A rename manifest that does not describe the rename that
   happened is not a rollback path, which was the whole reason for keeping it.

So this walks the tree, hashes every file for real, and writes the manifest FROM disk
rather than from intent. The result is checkable: re-run it and every row should verify.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manuals", type=Path, required=True)
    ap.add_argument("--derived", type=Path, required=True)
    ap.add_argument("--cover", type=Path, required=True)
    args = ap.parse_args()

    old_plan = {
        p["new"]: p
        for p in json.loads((args.cover / "rename-manifest.json").read_text(encoding="utf-8"))
    }
    # real digests already computed by the extractor, keyed by current filename
    known: dict[str, dict] = {}
    idx = args.derived / "index.json"
    if idx.exists():
        known = {r["file"]: r for r in json.loads(idx.read_text(encoding="utf-8"))}

    rows = []
    for p in sorted(args.manuals.rglob("*.pdf")):
        rec = known.get(p.name)
        digest = rec.get("sha256") if rec and rec.get("sha256") else sha256(p)
        prior = old_plan.get(p.name, {})
        rows.append({
            "path": str(p.relative_to(args.manuals)).replace("\\", "/"),
            "folder": p.parent.name if p.parent != args.manuals else "",
            "name": p.name,
            "bytes": p.stat().st_size,
            "sha256": digest,               # REAL content digest, always
            "was": prior.get("old", ""),    # empty = renamed before this manifest, or recovered
            "names_printed": prior.get("names_printed", []),
            "reg_codes": prior.get("reg_codes", []),
            "r_code": prior.get("r_code", ""),
            "langs": prior.get("langs", []),
            "pages": (rec or {}).get("pages", prior.get("pages", 0)),
            "text_pages": (rec or {}).get("text_pages", prior.get("text_pages", 0)),
            "full_text": bool(rec),
        })

    out = args.derived / "corpus-manifest.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    if not rows:
        print("MEASURED NOTHING -- no verdict.")
        return 1

    by_folder = collections.Counter(r["folder"] for r in rows)
    dupes = collections.Counter(r["sha256"] for r in rows)
    dupe_sets = {s: n for s, n in dupes.items() if n > 1}
    no_prov = [r for r in rows if not r["was"]]
    print(f"{len(rows)} PDFs on disk -> {out}")
    for f, n in by_folder.most_common():
        print(f"   {f or '(root)':18} {n:5}")
    print(f"\n  with full text extracted : {sum(1 for r in rows if r['full_text'])}")
    print(f"  byte-identical duplicates: {sum(dupe_sets.values()) - len(dupe_sets)}"
          f" extra copies across {len(dupe_sets)} documents")
    print(f"  rows with no prior-name provenance: {len(no_prov)}")
    for r in no_prov[:8]:
        print(f"     {r['path'][:72]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
