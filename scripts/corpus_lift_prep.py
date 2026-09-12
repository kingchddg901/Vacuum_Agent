"""Prepare i18n LIFT tasks: align each model's English care structure to its foreign-language
manual editions, so real per-language care strings can be LIFTED (not AI-translated) from the
parallel manuals.

Input: the per-brand English care corpus (structured components/steps/notes/frequencies) and
the language-tagged full-text cache built by corpus_text_extract.py.

Output (per brand, under --out):
    lift_inventory.json   deduped English source strings (the translation-memory KEYS), each
                          tagged with kind + the (model, component) provenance.
    lift_tasks.json       per anchor (model): the ordered English care TEMPLATE + a map
                          {lang: cached-text path} of the foreign editions to align against.

Anchor models are chosen to maximise language spread x component richness, so a bounded set of
alignments covers the bulk of the reused inventory before the long tail of model-specific rows.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TARGET_LANGS = ["en", "ar", "cs", "de", "es", "fr", "he", "id", "it", "ja", "ko",
                "nl", "pl", "pt", "ru", "tr", "zh-Hans", "zh-Hant"]


def strip_marker(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"^[①-⑳]\s*", "", s)      # circled 1-20
    s = re.sub(r"^\(?\d{1,2}[.)]\s*", "", s)        # 1.  1)  (1)
    s = re.sub(r"^[•●\-\*]\s*", "", s)     # bullets
    return re.sub(r"\s+", " ", s).strip()


def norm_model(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"(?i)\broborock\b|\brobovac\b|\beufy\b|\bclean\b|\bseries\b", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def model_aliases(model: str) -> set[str]:
    out = {norm_model(model)}
    for g in re.findall(r"global model:\s*([^;)]+)", model, re.I):
        out.add(norm_model(g))
    return {a for a in out if a}


def clean_edition(r: dict) -> bool:
    return (not r.get("error")) and r.get("text_pages", 0) >= 3 and r.get("garbled_pages", 0) == 0


# Non-vacuum products that name-search dragged into the eufy corpus (breast pump T8D04, solar
# light T81A0/S120). Editions whose text is one of these must never be a lift source.
NONVAC_MARKERS = re.compile(r"breast pump|wearable pump|milk|duckbill|solar wall|floodlight", re.I)


def build(brand: str, corpus_dir: Path, out: Path, anchors: int) -> None:
    care = [c for c in json.loads((corpus_dir / f"{brand}_care_corpus.json").read_text(encoding="utf-8"))
            if c.get("found")]
    idx = json.loads((corpus_dir / "text-cache" / "index.json").read_text(encoding="utf-8"))
    tc = corpus_dir / "text-cache" / "text"

    # deduped inventory + per-model ordered template
    inventory: dict[str, dict] = {}
    templates: dict[str, list[dict]] = {}
    for m in care:
        model = m["model"]
        tpl: list[dict] = []
        for c in (m.get("components") or []):
            name = strip_marker(c.get("component") or c.get("name") or "")
            if name:
                tpl.append({"kind": "name", "key": name})
                inventory.setdefault(name, {"kind": "name", "in": []})["in"].append(model)
            for s in (c.get("steps") or []):
                k = strip_marker(s)
                if k:
                    tpl.append({"kind": "step", "key": k})
                    inventory.setdefault(k, {"kind": "step", "in": []})["in"].append(model)
            for n in (c.get("notes") or []):
                k = strip_marker(n)
                if k:
                    tpl.append({"kind": "note", "key": k})
                    inventory.setdefault(k, {"kind": "note", "in": []})["in"].append(model)
        for f in (m.get("frequencies") or []):
            for fk in ("clean_frequency", "replace_frequency", "frequency"):
                if f.get(fk):
                    k = strip_marker(f[fk])
                    if k and k != "-":
                        inventory.setdefault(k, {"kind": "freq", "in": []})["in"].append(model)
        templates[model] = tpl

    # model -> {lang: best clean edition path}, excluding non-vacuum editions
    alias_to_model: dict[str, str] = {}
    for m in care:
        for a in model_aliases(m["model"]):
            alias_to_model.setdefault(a, m["model"])
    editions: dict[str, dict[str, tuple]] = {m["model"]: {} for m in care}
    for r in idx:
        if not clean_edition(r):
            continue
        path = tc / f"{r['sha256'][:12]}.txt"
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4000]
        except Exception:
            continue
        if NONVAC_MARKERS.search(head):
            continue
        langs = set([r.get("lang", "")]) | set(r.get("bundle_langs") or [])
        for im in (r.get("models") or []):
            tgt = alias_to_model.get(norm_model(im))
            if not tgt:
                continue
            for L in langs:
                if L not in TARGET_LANGS:
                    continue
                prev = editions[tgt].get(L)
                if not prev or r.get("chars", 0) > prev[0]:
                    editions[tgt][L] = (r.get("chars", 0), str(path).replace("\\", "/"))

    # anchor score = languages x components
    scored = sorted(
        care,
        key=lambda m: len(editions[m["model"]]) * len(templates[m["model"]]),
        reverse=True,
    )
    anchor_models = [m["model"] for m in scored[:anchors]]

    out.mkdir(parents=True, exist_ok=True)
    (out / "lift_inventory.json").write_text(
        json.dumps({"brand": brand, "count": len(inventory), "strings": inventory},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    tasks = []
    for model in anchor_models:
        langs = {L: p for L, (_, p) in editions[model].items() if L != "en"}
        tasks.append({"brand": brand, "model": model,
                      "components": sum(1 for t in templates[model] if t["kind"] == "name"),
                      "template": templates[model],
                      "editions": langs})
    (out / "lift_tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[{brand}] inventory={len(inventory)} unique strings")
    print(f"[{brand}] anchors ({anchors}) by lang-spread x richness:")
    for m in anchor_models:
        ls = sorted(L for L in editions[m] if L != "en")
        print(f"   {m[:34]:34s} tpl={len(templates[m]):3d} langs({len(ls)}): {ls}")
    # coverage: how many target langs get >=1 anchor edition
    covered = {}
    for m in anchor_models:
        for L in editions[m]:
            if L != "en":
                covered.setdefault(L, 0)
                covered[L] += 1
    print(f"[{brand}] target langs reachable via anchors: {sorted(covered)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--anchors", type=int, default=4)
    args = ap.parse_args()
    build(args.brand, args.corpus, args.out, args.anchors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
