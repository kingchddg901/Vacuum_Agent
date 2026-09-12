"""Extract the full text of every eufy / roborock manual into a durable per-brand cache.

Mirrors dreame_corpus_extract.py -- SHA-keyed dedup (the same document under a new name is
the same document), NUL-wrapped PAGE_SEP (exact per-page reconstruction; a bare form-feed
inflated Dreame page counts 1.8%), per-page char counts, a DERIVED text-empty verdict,
resumable index, never-raises-per-file -- and adds the two signals the eufy/roborock
downstream needs that the Dreame pipeline did not:

  1. LANGUAGE tag per file, joined by basename from the brand manifest. i18n LIFTING must
     know which language edition each file is (478 DE, 289 FR, 119 multi-lang CE bundles).

  2. Per-page GARBLE signal. pypdf/pymupdf return NON-EMPTY mojibake for a CID-outlined
     font (the d20_pro_plus trap): it reads as "has text" but is unusable for provenance
     or lifting. We record a per-page letter ratio so the OCR queue is DERIVED from a real
     garble measure, not the empty-text measure that missed d20_pro_plus. `alpha_ratio` is
     cross-language: real text in ANY script (latin/CJK/Cyrillic/Arabic) is mostly letters;
     CID mojibake is mostly symbols/private-use/replacement chars -> low alpha.

Extraction is pymupdf primary; a page that comes back empty OR garbled is retried with
pypdf (different font handling) before it is queued for OCR. OCR itself is a SEPARATE pass
(--ocr) so the fast text-layer sweep over the whole corpus lands first and the expensive
render+tesseract only touches the measured remainder.

    tesseract here has ONLY eng+osd tessdata (measured 2026-08-31). OCR of a non-latin
    edition is therefore degraded until the matching pack is installed; the OCR pass RECORDS
    the language it could not properly OCR rather than emitting silent garbage.

Output layout (under --out):
    text/<sha12>.txt        text-layer full text, PAGE_SEP separated per page
    text/<sha12>.ocr.txt    OCR text (only for files the OCR pass touched)
    index.json              one record per PDF: file, sha, lang, pages, per-page chars+alpha
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

#: Page delimiter. NUL cannot occur in extracted PDF text; form-feed can.
PAGE_SEP = "\x00\f\x00"

#: A page with at least this many chars is "has content" for the text-empty verdict.
CONTENT_CHARS = 100
#: Below this letter fraction, a content page is GARBLED (mojibake), not real text.
GARBLE_ALPHA = 0.35

TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Per-brand manifest wiring: (manifest filename, language field). First match by basename
# wins, so list the authoritative manifest first. locale strings (en-us) normalise to lang.
_BRANDS: dict[str, list[tuple[str, str]]] = {
    "eufy": [("eufy_manual_manifest.json", "language")],
    "roborock": [
        ("roborock_manual_manifest_v2.json", "lang"),
        ("roborock_manual_manifest.json", "locale"),
    ],
}


def _norm_lang(value: str) -> str:
    """en-us -> en, ko-kr -> ko; keep zh-Hans/zh-Hant and bare codes as-is."""
    v = (value or "").strip()
    if not v:
        return ""
    if v.lower().startswith("zh"):
        return v
    return v.split("-")[0].split("_")[0].lower()


def load_lang_map(corpus_parent: Path, brand: str) -> dict[str, dict]:
    """basename -> {lang, bundle_langs, models} from the brand's manifest(s)."""
    out: dict[str, dict] = {}
    for fname, field in _BRANDS[brand]:
        mpath = corpus_parent / fname
        if not mpath.exists():
            continue
        for e in json.loads(mpath.read_text(encoding="utf-8")):
            base = os.path.basename(str(e.get("file", "")).replace("\\", "/"))
            if not base or base in out:
                continue
            out[base] = {
                "lang": _norm_lang(e.get(field, "")),
                "bundle_langs": e.get("bundle_langs") or [],
                "models": e.get("models") or ([e["model"]] if e.get("model") else []),
            }
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _alpha_ratio(text: str) -> float:
    """Fraction of chars that are letters (any script). Robust cross-language garble
    detector: real prose is mostly letters; CID mojibake is mostly symbols/PUA/\\ufffd."""
    n = len(text)
    if n == 0:
        return 0.0
    return round(sum(1 for c in text if c.isalpha()) / n, 3)


def _extract_pymupdf(src: str) -> list[str] | None:
    try:
        import pymupdf
    except Exception:
        return None
    try:
        doc = pymupdf.open(src)
    except Exception:
        return None
    out: list[str] = []
    for i in range(doc.page_count):
        try:
            out.append(doc[i].get_text("text") or "")
        except Exception:
            out.append("")
    doc.close()
    return out


def _retry_pypdf(src: str, want: list[int]) -> dict[int, str]:
    """Re-extract only the page indices in `want` with pypdf (different font handling)."""
    if not want:
        return {}
    try:
        from pypdf import PdfReader

        reader = PdfReader(src)
        fixed: dict[int, str] = {}
        for i in want:
            try:
                t = reader.pages[i].extract_text() or ""
            except Exception:
                t = ""
            if t:
                fixed[i] = t
        return fixed
    except Exception:
        return {}


def extract_one(args: tuple[str, str]) -> dict:
    """Worker: never raises -- a failure is a RECORD, not a crash."""
    src, outdir = args
    path = Path(src)
    rec: dict = {"file": path.name, "size": path.stat().st_size}
    try:
        rec["sha256"] = _sha256(path)
    except Exception as err:
        rec["error"] = f"sha:{type(err).__name__}"
        return rec

    txt_path = Path(outdir) / "text" / f"{rec['sha256'][:12]}.txt"

    pages = _extract_pymupdf(src)
    if pages is None:
        rec["error"] = "pdf:open"
        return rec

    # Retry the pages that pymupdf left empty OR garbled, with pypdf, before OCR.
    weak = [
        i for i, t in enumerate(pages)
        if len(t) < CONTENT_CHARS or _alpha_ratio(t) < GARBLE_ALPHA
    ]
    for i, t in _retry_pypdf(src, weak).items():
        # keep whichever attempt reads as real text (higher alpha on a content page)
        if _alpha_ratio(t) >= _alpha_ratio(pages[i]):
            pages[i] = t

    per_chars = [len(t) for t in pages]
    per_alpha = [_alpha_ratio(t) for t in pages]
    rec["pages"] = len(pages)
    rec["page_chars"] = per_chars
    rec["page_alpha"] = per_alpha
    rec["chars"] = sum(per_chars)
    # DERIVED, never assumed.
    rec["text_pages"] = sum(1 for n in per_chars if n >= CONTENT_CHARS)
    rec["garbled_pages"] = sum(
        1 for n, a in zip(per_chars, per_alpha)
        if n >= CONTENT_CHARS and a < GARBLE_ALPHA
    )
    try:
        txt_path.write_text(PAGE_SEP.join(pages), encoding="utf-8", errors="replace")
    except Exception as err:
        rec["error"] = f"write:{type(err).__name__}"
    return rec


def _ocr_file(src: str, outdir: str, sha12: str, dpi: int = 300) -> dict:
    """Render every page at `dpi` and OCR with tesseract (eng). Records raw OCR text."""
    import pymupdf

    rec = {"sha12": sha12, "ocr_pages": 0, "ocr_chars": 0}
    try:
        doc = pymupdf.open(src)
    except Exception as err:
        rec["error"] = f"open:{type(err).__name__}"
        return rec
    chunks: list[str] = []
    tmp = Path(outdir) / "text" / f".{sha12}.ocrpage.png"
    for i in range(doc.page_count):
        try:
            pix = doc[i].get_pixmap(dpi=dpi)
            pix.save(str(tmp))
            proc = subprocess.run(
                [TESSERACT, str(tmp), "stdout", "-l", "eng"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            t = proc.stdout or ""
        except Exception:
            t = ""
        chunks.append(t)
        if len(t) >= CONTENT_CHARS:
            rec["ocr_pages"] += 1
    doc.close()
    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass
    rec["ocr_chars"] = sum(len(c) for c in chunks)
    (Path(outdir) / "text" / f"{sha12}.ocr.txt").write_text(
        PAGE_SEP.join(chunks), encoding="utf-8", errors="replace"
    )
    return rec


def run_textlayer(corpus: Path, out: Path, lang_map: dict, workers: int) -> list[dict]:
    (out / "text").mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in corpus.rglob("*.pdf"))
    print(f"{len(files)} PDFs under {corpus}", flush=True)

    index_path = out / "index.json"
    done: dict[str, dict] = {}
    if index_path.exists():
        done = {r["file"]: r for r in json.loads(index_path.read_text(encoding="utf-8"))}
        print(f"  resuming: {len(done)} already indexed", flush=True)
    todo = [str(p) for p in files if p.name not in done]
    print(f"  {len(todo)} to extract", flush=True)

    results = list(done.values())
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        for i, rec in enumerate(
            pool.map(extract_one, ((f, str(out)) for f in todo), chunksize=4), 1
        ):
            results.append(rec)
            if i % 50 == 0:
                print(f"   ...{i}/{len(todo)}", flush=True)
                index_path.write_text(json.dumps(results), encoding="utf-8")

    # attach language + models from the manifest (by basename), non-destructive
    for r in results:
        meta = lang_map.get(r["file"])
        if meta:
            r.setdefault("lang", meta["lang"])
            r.setdefault("bundle_langs", meta["bundle_langs"])
            r.setdefault("models", meta["models"])
    index_path.write_text(json.dumps(results), encoding="utf-8")
    return results


def run_ocr(corpus: Path, out: Path, workers: int) -> None:
    """OCR every file the text-layer pass flagged: no text at all, or any garbled page."""
    index_path = out / "index.json"
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    by_sha = {}
    for r in idx:
        if r.get("error"):
            continue
        empty = r.get("text_pages", 0) == 0
        garbled = r.get("garbled_pages", 0) > 0
        if empty or garbled:
            by_sha.setdefault(r["sha256"][:12], r["file"])
    # resolve one physical path per sha
    name_to_path = {p.name: p for p in corpus.rglob("*.pdf")}
    todo = [(str(name_to_path[f]), str(out), sha) for sha, f in by_sha.items() if f in name_to_path]
    print(f"OCR queue: {len(todo)} files (empty or garbled)", flush=True)
    ocr_recs = []
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        for i, rec in enumerate(pool.map(_ocr_star, todo, chunksize=1), 1):
            ocr_recs.append(rec)
            if i % 10 == 0:
                print(f"   ocr {i}/{len(todo)}", flush=True)
    (out / "ocr_index.json").write_text(json.dumps(ocr_recs), encoding="utf-8")
    print(f"OCR done: {sum(x.get('ocr_pages',0) for x in ocr_recs)} pages", flush=True)


def _ocr_star(t: tuple[str, str, str]) -> dict:
    return _ocr_file(t[0], t[1], t[2])


def summarize(results: list[dict]) -> None:
    if not results:
        print("MEASURED NOTHING -- no verdict.")
        return
    import collections

    failed = [r for r in results if r.get("error")]
    empty = [r for r in results if not r.get("error") and r.get("text_pages", 0) == 0]
    garb = [r for r in results if not r.get("error") and r.get("garbled_pages", 0) > 0]
    pages = sum(r.get("pages", 0) for r in results)
    print(f"\nindexed {len(results)} files, {pages} pages")
    print(f"  failed to open       : {len(failed)}")
    print(f"  NO text layer at all : {len(empty)}   <- OCR queue")
    print(f"  has garbled page(s)  : {len(garb)}   <- OCR queue (mojibake, d20_pro_plus class)")
    langs = collections.Counter(r.get("lang", "?") for r in results if not r.get("error"))
    print("  by language:", dict(langs.most_common()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True, choices=sorted(_BRANDS))
    ap.add_argument("--corpus", type=Path, required=True, help="dir of PDFs (recursed)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--ocr", action="store_true", help="run the OCR pass over the flagged remainder")
    args = ap.parse_args()

    corpus_parent = args.corpus if (args.corpus / _BRANDS[args.brand][0][0]).exists() else args.corpus.parent
    lang_map = load_lang_map(corpus_parent, args.brand)
    print(f"lang map: {len(lang_map)} filenames tagged", flush=True)

    if args.ocr:
        run_ocr(args.corpus, args.out, args.workers)
        return 0

    results = run_textlayer(args.corpus, args.out, lang_map, args.workers)
    summarize(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
