"""RECEIPT DECODER — turn a captured dump back into the execution story.

    python scripts/decode_receipts.py <dump.log> [--view raw|engineer|human] [--locale xx]

A LOCAL REPO TOOL, per review-notes item 5: sole maintainer, so this is not a CLI or a card
surface until more maintainers exist.

THREE VIEWS OF ONE CAPTURE (§8). Same evidence, different rendering — the raw wire, an
engineer's columns, and prose. Nothing is stored twice: the prose is resolved HERE, at replay,
from the same catalog entry the raw line points at.

THE FALLBACK LADDER (§9) is implemented and must never be short-circuited:

    requested locale -> base language -> English catalog prose -> RAW id + raw fields

A broken localisation must never destroy evidence, so the bottom rung is always readable. The
card already runs this exact ladder (`check:i18n` Part A tests it, including a hostile catalog
string that must come back neutralised) — this is the same shape against a different catalog.

AN UNKNOWN ID IS NOT AN ERROR. It renders as raw evidence with a marker. A decoder that
crashes on a key it has not seen would destroy the trace of exactly the change that
introduced it, which is the moment you most need to read it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from custom_components.eufy_vacuum.receipts import WIRE, unescape  # noqa: E402
from custom_components.eufy_vacuum.receipts.catalog import CATALOG  # noqa: E402

#: Locale catalogs would live here. Empty is the honest state today: the pilot ships English
#: only, and the ladder still has to work, because a ladder that is only exercised once it has
#: rungs is a ladder nobody has tested.
LOCALES: dict[str, dict[str, str]] = {}


def parse(text: str) -> list[dict[str, object]]:
    """Pull receipts out of a dump. Non-receipt lines are ignored, not errors."""
    out: list[dict[str, object]] = []
    for raw in text.splitlines():
        i = raw.find(WIRE + "|")
        if i < 0:
            continue
        parts = raw[i:].split("|")
        if len(parts) < 7:
            continue  # truncated line: skip, do not guess
        _, to, frm, msg, outcome, body, prov = parts[:7]
        out.append({
            "to": to, "from": frm, "msg": msg, "outcome": outcome,
            # unescape per TOKEN, after splitting — a fact containing a space arrives as
            # %20 precisely so the split cannot see it. Doing it in the other order would
            # reintroduce the bug this encoding exists to fix.
            "facts": [unescape(t) for t in body.split()] if body else [],
            "prov": prov.split("+") if prov else [],
            "line": raw.strip(),
        })
    return out


def render_prose(rec: dict[str, object], locale: str | None) -> str:
    """The ladder. Returns prose, or raw evidence — never nothing, never a crash."""
    msg = str(rec["msg"])
    entry = CATALOG.get(msg)
    if entry is None:
        return f"[unknown id {msg}] {' '.join(map(str, rec['facts']))}"

    template = None
    if locale:
        template = (LOCALES.get(locale, {}).get(msg)
                    or LOCALES.get(locale.split("-", 1)[0], {}).get(msg))
    template = template or entry.get("en")
    if not template:
        return f"[no prose for {msg}] {' '.join(map(str, rec['facts']))}"

    names = [f[0] for f in entry["fields"]]
    facts = list(map(str, rec["facts"]))
    values = dict(zip(names, facts))
    try:
        text = template.format(**values)
    except (KeyError, IndexError, ValueError):
        # A template that does not fit its own facts is a catalog bug; the gate catches it
        # at author time. At READ time the evidence still wins.
        return f"[prose failed for {msg}] {' '.join(facts)}"
    if len(facts) != len(names):
        text += f"  [arity mismatch: {len(facts)} facts, {len(names)} declared]"
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dump", type=Path)
    ap.add_argument("--view", choices=("raw", "engineer", "human"), default="human")
    ap.add_argument("--locale", default=None)
    args = ap.parse_args()

    recs = parse(args.dump.read_text(encoding="utf-8", errors="replace"))
    if not recs:
        print("no receipts found in that dump")
        return 1

    for r in recs:
        prov = "+".join(map(str, r["prov"]))
        # An ABSENT provenance section is evidence — §11 names where the marker can fall
        # off, and silence about it would be the very thing this design refuses.
        flag = "" if prov == "live" else f"  [{prov or 'PROVENANCE MISSING'}]"
        if args.view == "raw":
            print(r["line"])
        elif args.view == "engineer":
            print(f"{str(r['msg']):34s} {str(r['outcome']):2s} "
                  f"{str(r['from']):16s} -> {str(r['to']):16s} "
                  f"{' '.join(map(str, r['facts']))}{flag}")
        else:
            print(f"{render_prose(r, args.locale)}{flag}")

    unknown = sorted({str(r["msg"]) for r in recs if str(r["msg"]) not in CATALOG})
    if unknown:
        print(f"\n[{len(unknown)} id(s) not in this catalog generation: {', '.join(unknown)}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
