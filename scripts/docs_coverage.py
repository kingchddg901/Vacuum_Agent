#!/usr/bin/env python3
"""What the NOW corpus covers of the backend tree, and what is still unwritten.

    python scripts/docs_coverage.py              # the burn-down
    python scripts/docs_coverage.py --unwritten  # only what has no document

WHY THIS EXISTS
---------------
The corpus is being rewritten subsystem by subsystem, and "what is still unwritten" gets
asked at the start of every session. Derived by hand it was wrong twice in one afternoon,
both times in the direction that reads as PROGRESS.

WHY OWNERSHIP IS DECLARED AND NOT INFERRED
------------------------------------------
Three inference schemes were tried. All three over-reported coverage:

  1. Counting `path/file.py` citations measures citation FORM, not coverage. It called
     `clean_order` unmentioned while seven retired docs mention it, and called `dock`
     barely covered when `14-dock-manager.md` is about nothing else.
  2. "The document that mentions the package most" made `00b-invariants.md` the owner of
     nine subsystems and reported 89% written against eight documents. Registries cite
     everything in the tree — that is what a registry is.
  3. Excluding the registries still handed `adapters/` (17k lines) to the battery
     document, because stem-matching counts `adapter`, `registry` and `eufy` wherever they
     appear, and every document discusses adapter-declared values.

A mention is not a subject. So ownership is STATED in `OWNERSHIP` below and the tree is
what audits it: a package in the tree and not in the map is reported unwritten, and a
package in the map and not in the tree is reported stale. The list is typed; its errors
are generated.

There is a fourth failure this cannot catch and it is worth naming: a package listed here
with a document that does not actually explain it. Coverage is not correctness. Truth is
`check_doc_citations.py` and the claim-verification pass.

DECLARED BLIND SPOTS
--------------------
- Line count is a scoping prompt, never a difficulty estimate. A 300-line module with five
  storage keys can outweigh a 3,000-line one that is mostly plumbing.
- A package may deserve more than one document, or several may deserve one between them.
  Shape is decided by storage-key coupling, not by this table.
- A CROSS-CUTTING document owns no package and is therefore INVISIBLE here. 100% means every
  line has an owning document; it does NOT mean the corpus is complete. Two such documents were
  dropped and only found because Chris asked: an ARCHITECTURE OVERVIEW and a DATA MODEL. They were
  the two most-cited missing link targets (19 inbound), because orienting docs get cited most.
  The cause is in `docs/dev/README.md`'s own scoping line, "scope the remaining work from the
  tree, not from the retired file list" — that finds every package and cannot find a document
  about the system. See CROSS_CUTTING below; it is a hand-kept list, and nothing checks it.
- Frontend (`src/`) is out of scope; it has its own hub under `docs/dev/frontend/`.
- Import counts are reported, never decisive. `config_flow.py` has none because Home
  Assistant discovers it by convention, not by import.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "custom_components" / "eufy_vacuum"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: Below this many lines a module is not worth a coverage row of its own.
MIN_LINES = 80

#: Directories holding TRANSLATED or GENERATED DATA, not logic. Counted separately and excluded
#: from the denominator, because a line of translated guide prose does not need a document and
#: including it makes the campaign look further from done than it is.
#:
#: `upkeep_guides_i18n` is 6,324 lines across 36 files — one per locale, both brands. It inflated
#: `adapters/` from a real logic surface of 11,144 to a reported 17,468, which is 57% overstatement
#: on the largest single subsystem. Chris's ruling 2026-08-23: the guides need the PATTERN
#: explained — translation keys feeding the card, identical for any brand — and nothing more.
DATA_DIRS = {"upkeep_guides_i18n"}

#: Shape rulings, carried into the generated list so they survive the session that made them.
#: These are Chris's calls, not inferences from the tree.
#: Documents the tree cannot ask for. Hand-kept: nothing derives or verifies this.
CROSS_CUTTING = [
    ("architecture overview", "WRITTEN → 01-architecture-overview.md", "retired/dev/01-architecture-overview.md"),
    ("data model", "WRITTEN → 03-data-model.md", "retired/dev/03-data-model.md"),
    ("HA surface / the 11 outbound events", "WRITTEN → 02-ha-integration.md", "retired/dev/02-ha-integration.md"),
]


RULINGS = [
    ("`adapters/`", "at least three documents — one for the CONTRACT, then one per brand as an "
     "IMPLEMENTATION of that contract. Ruled 2026-08-23."),
    ("upkeep guides", "**not** exhaustively documented. Explain what they are for and how the "
     "pattern works — translation keys that feed the card — and stop. It is the same pattern for "
     "every brand. Ruled 2026-08-23."),
    ("doc passes", "stay clean of code edits. Findings are recorded and deferred; see "
     "`REPAIR-BACKLOG.md`. Ruled 2026-08-22."),
    ("a TUNED subsystem", "documents its PREMISE and what retuning it means — never its constants, "
     "and never a stage-by-stage walk of the algorithm. `eufy/segmentor.py` is the case and the "
     "shape of it is: **the algorithm is ordinary CV — HSV clustering, median filter, morphology, "
     "connected components — and that is not the interesting part.** What makes it work is that it "
     "is tuned hard against real Eufy maps, which the module docstring says five times ('tuned for "
     "Eufy map colour palettes', 'calibrated on Eufy map images', 'tuned to Eufy map "
     "characteristics'). Walking the stages dignifies the least interesting half and enumerating "
     "the thresholds is the DR-level restatement `00 §8` repudiates — those numbers are in source "
     "and they rot.\n"
     "  What earns a place is the world fact the tuning rests on, which source never states: "
     "**Eufy renders each room in a DISTINCT HUE**, so a hue bin corresponds to a room (salvage "
     "#4). Without it, choosing hue as the clustering space reads as generic computer vision "
     "rather than a bet on one vendor's renderer.\n"
     "  **The rejected alternative is a vision model, and the reason is not what the code implies** "
     "(Chris, 2026-08-23; recorded nowhere in the tree — see salvage #6). It was rejected because "
     "the LLM pipeline received a LOW-GRADE IMAGE rather than the full-quality PNG, so the "
     "comparison was never against the real input. That is an input-plumbing blocker, not a "
     "judgement about model capability — a NOT-YET wearing the clothes of a never. Anyone reading "
     "1,606 lines of hand-tuned HSV clustering will otherwise infer that someone judged CV the "
     "better technique, and that is not what happened.\n"
     "  The maintenance action IS in source, in the docstring's 'Porting a new brand' section: "
     "copy the mask builder and scoring heuristics as a template and RETUNE the thresholds. "
     "Ruled 2026-08-23."),
]

#: package (or loose module) -> the document(s) that explain it. Add a row when a doc lands.
OWNERSHIP: dict[str, str] = {
    "jobs":     "05-run-live · 06-run-end",
    "planning": "05-run-live",
    "queue":    "05-run-live",
    "mapping":  "11-map-stored-state … 15-stall-capture-image",
    "battery":  "16-battery-record",
    "rooms":    "17-room-identity · 18-access-graph",
    "listeners": "19-event-ingress",
    "profiles": "20-room-profiles · 21-run-profiles",
    "learning":  "26-record-store … 30-external-runs",
    "setup":     "31-setup-layer",
    "core":      "32-the-store … 35-the-fault-tracker",
    "services":  "36-the-service-layer",
    "sensor":    "37-the-entity-surface",
    "themes":    "38-the-theme-library",
    "__init__.py": "39-the-entry-point",
    "diagnostics.py": "40-diagnostics-and-evidence",
    "debug_capture.py": "40-diagnostics-and-evidence",
    "decision_log.py": "40-diagnostics-and-evidence",
    "receipts":   "40-diagnostics-and-evidence",
    "maintenance": "41-maintenance-and-the-dock",
    "dock":      "41-maintenance-and-the-dock",
    "dispatch":  "42-the-send-side",
    "clean_order": "42-the-send-side",
    "step_types.py": "42-the-send-side",
    "counter_segmentation.py": "43-observing-a-run",
    "job_active_signal.py": "43-observing-a-run",
    "pose_store.py": "43-observing-a-run",
    "live_refresh": "43-observing-a-run",
    "onboarding": "44-onboarding-and-first-run",
    "config_flow.py": "44-onboarding-and-first-run",
    "panels.py": "44-onboarding-and-first-run",
    "const.py":  "45-the-shared-layer",
    "models":    "45-the-shared-layer",
    "maps":      "45-the-shared-layer",
    "user_fonts.py": "45-the-shared-layer",
    "room_entities.py": "37-the-entity-surface",
    "entity_helpers.py": "37-the-entity-surface",
    "button.py": "37-the-entity-surface",
    "number.py": "37-the-entity-surface",
    "binary_sensor.py": "37-the-entity-surface",
    "switch.py": "37-the-entity-surface",
    "select.py": "37-the-entity-surface",
    "adapters": "22-adapter-contract · 23-eufy · 24-roborock · 25-segmentor",
}


def inventory() -> tuple[collections.Counter, collections.Counter]:
    """Package -> logic lines, and package -> translated/generated DATA lines."""
    size: collections.Counter = collections.Counter()
    data: collections.Counter = collections.Counter()
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC)
        key = rel.parts[0] if len(rel.parts) > 1 else str(rel)
        n = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        if DATA_DIRS & set(rel.parts):
            data[key] += n
        else:
            size[key] += n
    return size, data


def importers(module_key: str) -> int:
    """How many files outside the module import it. Reported, never decisive."""
    base = module_key[:-3] if module_key.endswith(".py") else module_key
    esc = re.escape(base)
    pat = re.compile(rf"(from\s+\.*{esc}\s+import|import\s+\.*{esc}\b|\.{esc}\.)")
    count = 0
    for path in SRC.rglob("*.py"):
        rel = str(path.relative_to(SRC)).replace("\\", "/")
        if rel.startswith(base):
            continue
        if pat.search(path.read_text(encoding="utf-8", errors="replace")):
            count += 1
    return count


#: The running list, regenerated rather than maintained by hand.
#:
#: Run `--write` after landing each document, in the same breath as adding its OWNERSHIP row.
#: A hand-kept burn-down drifts in the one direction that flatters — a subject gets written and
#: nobody strikes it, or a package is added to the tree and nobody adds a row. Regenerating from
#: the tree makes both impossible.
REMAINING = ROOT / ".claude" / "notes" / "DOC-CAMPAIGN-REMAINING.md"


def write_remaining(rows, done, total, left, data) -> None:
    pct = 100 * done / max(total, 1)
    out = [
        "# Documentation campaign — what is left",
        "",
        "> **GENERATED — do not hand-edit.** Regenerate after each document lands:",
        "> `python scripts/docs_coverage.py --write`",
        ">",
        "> Ownership is declared in `scripts/docs_coverage.py::OWNERSHIP`; the tree audits it.",
        "> A package in the tree and not in that map shows here as unwritten. A package in the map",
        "> and not in the tree is reported as STALE when the script runs.",
        "",
        f"**{done:,} of {total:,} backend lines have a document ({pct:.0f}%).**",
        "",
        "⚠ **That is LINE coverage, not corpus completeness.** A document about the SYSTEM owns "
        "no package and cannot appear in the table above. Known cross-cutting gaps:",
    ] + [f"- **{name}** — {state} (ancestor: `{anc}`)" for name, state, anc in CROSS_CUTTING] + [
        f"**{len(left)} subjects unwritten, {sum(v for _, v in left):,} lines.**",
        "",
        "Line count is a scoping prompt, never a difficulty estimate — a 300-line module with five",
        "storage keys can outweigh a 3,000-line one that is mostly plumbing.",
        "",
        "---",
        "",
        "## Shape rulings",
        "",
        "Chris's calls. Not inferences from the tree, and not for an agent to revisit.",
        "",
    ] + [f"- **{who}** — {what}" for who, what in RULINGS] + [
        "",
        "---",
        "",
        "## Unwritten",
        "",
        "| package | lines | importers |",
        "|---|---|---|",
    ]
    for key, lines, owner in rows:
        if not owner:
            out.append(f"| `{key}` | {lines:,} | {importers(key)} |")
    out += ["", "---", "", "## Written", "", "| package | lines | document |", "|---|---|---|"]
    for key, lines, owner in rows:
        if owner:
            out.append(f"| `{key}` | {lines:,} | {owner} |")
    out += [
        "",
        "---",
        "",
        "## Known blind spots in this table",
        "",
        "- **Package granularity.** `mapping` counts as written, but a module inside it may not be",
        "  covered by any of its five documents. This table cannot see that.",
        "- **Coverage is not correctness.** A package listed as written may have a document that",
        "  does not explain it. Truth is `check_doc_citations.py` plus a claim-verification pass —",
        "  the one over the first seven documents found 27 real defects.",
        "- **Frontend (`src/`) is out of scope here.** It has its own hub under `docs/dev/frontend/`.",
        "",
    ]
    if data:
        out += ["---", "",
                "## Excluded as translated / generated data", "",
                f"**{sum(data.values()):,} lines**, counted separately because a line of translated",
                "prose does not need a document. Including it made `adapters/` read as 17,468 lines",
                "against a real logic surface of 11,144.", "",
                "| package | data lines |", "|---|---|"]
        out += [f"| `{k}` | {v:,} |" for k, v in data.most_common()]
        out += [""]
    REMAINING.parent.mkdir(parents=True, exist_ok=True)
    REMAINING.write_text("\n".join(out), encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unwritten", action="store_true", help="only what has no document")
    ap.add_argument("--write", action="store_true",
                    help="regenerate .claude/notes/DOC-CAMPAIGN-REMAINING.md")
    args = ap.parse_args()

    size, data = inventory()
    tree = {k for k, v in size.items() if v >= MIN_LINES}
    known = set(OWNERSHIP)

    stale = known - set(size)
    if stale:
        print("  STALE — named in OWNERSHIP, absent from the tree: " + ", ".join(sorted(stale)))

    rows = [(k, size[k], OWNERSHIP.get(k, "")) for k in sorted(tree, key=lambda k: -size[k])]
    if args.unwritten:
        rows = [r for r in rows if not r[2]]

    print("")
    print("NOW-corpus coverage of custom_components/eufy_vacuum")
    print("")
    print(f"  {'package':<26}{'lines':>7}{'importers':>11}  document")
    print("  " + "-" * 88)
    for key, lines, owner in rows:
        print(f"  {key:<26}{lines:>7}{importers(key):>11}  {owner or '— UNWRITTEN'}")
    print("  " + "-" * 88)

    done = sum(size[k] for k in tree & known)
    total = sum(size[k] for k in tree)
    left = sorted(((k, size[k]) for k in tree - known), key=lambda t: -t[1])
    pct = 100 * done / max(total, 1)
    print("")
    print(f"  {done:,} of {total:,} lines have a document ({pct:.0f}%).")
    for name, state, _anc in CROSS_CUTTING:
        print(f"  cross-cutting: {name} — {state}")
    print(f"  {len(left)} subjects unwritten, {sum(v for _, v in left):,} lines.")
    if data:
        print("")
        print(f"  excluded as translated/generated DATA ({sum(data.values()):,} lines):")
        for k, v in data.most_common():
            print(f"    {k:<26}{v:>7}")
    if left and not args.unwritten:
        print("")
        print("  Largest unwritten:")
        for k, v in left[:8]:
            print(f"    {k:<26}{v:>7}")

    if args.write:
        # rows must be the FULL set here, not the --unwritten filter, or the written
        # half silently empties and the file reports a campaign that covered nothing.
        allrows = [(k, size[k], OWNERSHIP.get(k, "")) for k in sorted(tree, key=lambda k: -size[k])]
        write_remaining(allrows, done, total, left, data)
        print("")
        print(f"  wrote {REMAINING.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
