"""RECEIPT GATE — the catalog and the call sites must agree, in BOTH directions.

Run locally (review-notes item 3, "keep CI lean, sole-maintainer discipline"):

    python scripts/check_receipts.py

MIRRORS `check:i18n` PART B, which fails FATALLY when a key is used in `src/` but missing
from `en.js` — an orphan there renders the raw key in the UI. Item 3(a) already decided the
same rule for receipts: any emission without a catalog key fails locally.

AND MAKES THE OTHER DIRECTION FATAL. Key-used -> key-exists catches the loud failure.
Entry-exists -> entry-still-emitted catches the SILENT one: a catalog entry whose emitter
moved or vanished keeps asserting a cause that no longer happens, and nobody notices until
someone reads it and believes it describes live code. Same one-way rot as an index written
at APPROVED and never rewritten at LANDED. The system's value rests on the catalog being
trustworthy, so it is checked from both ends.

⚠ was: "AND ADDS THE DIRECTION `check:i18n` DOES NOT HAVE." Refuted, and INHERITED rather
than invented — the same overstatement sits in the source doc this docstring was written
from, `.claude/notes/synthesis/PROTOCOL-semantic-flight-recorder.md`, so correcting it here
does not correct it there. `check-i18n.mjs` HAS the declared-to-used direction: it builds a
`dead` list of `en.js` keys that no literal, data value or template can reach, and prints
every one. It prints them under a `⚠` and never calls `fail()`, so a dead key cannot turn
that gate red. The novelty here is FATALITY, not direction.

⚠ AND "BOTH DIRECTIONS" IS NARROWER THAN THE FIRST LINE READS. It holds for CATALOG keys
(the `for key in CATALOG` loop) and for a key's declared OUTCOMES (direction 2b). It holds
for NO vocabulary. `STATIONS` and `PROVENANCE` are policed emitted-to-declared only, and
`PROVENANCE` only when `prov=` is a literal keyword argument. `DECLINE_REASONS` and
`READABILITY` are policed in neither direction: their values ride in `*facts`, and this
gate keeps only the fact COUNT. What the vocabularies do have is tidiness — a
duplicate-members check covering `OUTCOMES`, `DECLINE_REASONS`, `PROVENANCE` and
`READABILITY` (not `STATIONS`), plus the transmit-as-yourself check for `STATIONS` alone.
Real checks, which is why the block reads as covered. None runs declared-to-emitted, so a
declared member that nothing emits can never fail this gate.

MEASURED ON THIS TREE, while the gate prints "OK — catalog and call sites agree in both
directions": of the seven declared `STATIONS` only `listeners.stall_capture` and
`services.stall_capture` ever transmit; `ANY` and `mapping.map_source` appear only as
addressees; `core`, `pose_store` and `mapping.stall_capture_render` appear in neither
position. `replay` occurs nowhere in the package outside its own declaration, and `no_map`
occurs nowhere as a receipt fact. Closing that direction is a code change, not a wording
one — see the vocabulary section at the end of `main()`.

AST, NOT REGEX. A grep for `receipts.emit("` matches a docstring, a comment or a fixture,
and would then pass because the key it found happens to exist. The gate has to be about what
the code DOES.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "eufy_vacuum"
sys.path.insert(0, str(ROOT))

from custom_components.eufy_vacuum.receipts import (  # noqa: E402
    DECLINE_REASONS, OUTCOMES, PROVENANCE, READABILITY, STATIONS,
)
from custom_components.eufy_vacuum.receipts.catalog import CATALOG, TYPES  # noqa: E402

VOCABS = {
    "enum:decline_reason": DECLINE_REASONS,
    "enum:readability": READABILITY,
}


class _Emits(ast.NodeVisitor):
    """Collect every real `receipts.emit(...)` call as a SEVEN-tuple:

        (key, to, frm, outcome, n_facts, line, prov)

    which is the exact order `main()` unpacks in `for key, to, frm, outcome, n_facts,
    line, prov in v.found`. `n_facts` is a COUNT, not the values — see the vocabulary
    section at the end of `main()` for what that costs.

    ⚠ was: two stale descriptions of one structure, in one file — this docstring said
    `(key, outcome, n_facts, line)` (4 fields) and the `self.found` comment below said
    `(key, to, frm, outcome, n_facts, line)` (6). The first predates the `to`/`frm`
    station pair, the second predates the `prov` keyword; both were left behind when the
    tuple grew, and either would send a reader unpacking the wrong arity.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        # (key, to, frm, outcome, n_facts, line, prov) — see the class docstring.
        self.found: list[tuple] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "emit" and isinstance(f.value, ast.Name) \
                and f.value.id == "receipts":
            args = node.args

            def _lit(i):
                return args[i].value if len(args) > i and isinstance(args[i], ast.Constant) else None

            prov = None
            for kw in node.keywords:
                if kw.arg == "prov" and isinstance(kw.value, ast.Constant):
                    prov = kw.value.value
            self.found.append((_lit(0), _lit(1), _lit(2), _lit(3),
                               max(0, len(args) - 4), node.lineno, prov))
        self.generic_visit(node)


def main() -> int:
    problems: list[str] = []

    # --- the catalog itself must be well-formed before anything is checked against it ---
    for key, entry in CATALOG.items():
        for req in ("meaning", "outcomes", "fields", "en", "dr"):
            if req not in entry:
                problems.append(f"catalog[{key}]: missing required '{req}'")
        for oc in entry.get("outcomes", ()):
            if oc not in OUTCOMES:
                problems.append(f"catalog[{key}]: outcome {oc!r} not in OUTCOMES")
        for field in entry.get("fields", ()):
            # (name, type, unit) — all THREE stated. `unit=None` is legitimate and means
            # dimensionless, but it must be SAID, for the same reason provenance states
            # `live` rather than assuming it. A 2-tuple is an undeclared unit, which is the
            # defect class behind cleaning_area's ft^2-vs-m^2.
            if not isinstance(field, tuple) or len(field) != 3:
                problems.append(f"catalog[{key}]: field {field!r} is not (name, type, unit)")
                continue
            if field[1] not in TYPES:
                problems.append(f"catalog[{key}]: field {field[0]!r} has unknown type {field[1]!r}")
        named = [f[0] for f in entry.get("fields", ()) if isinstance(f, tuple) and f]
        for token in named:
            if "{" + token + "}" not in entry.get("en", ""):
                problems.append(
                    f"catalog[{key}]: field {token!r} never appears in the English prose — "
                    "a fact nobody can read is a fact nobody checks"
                )

    # --- direction 1: every emitted key exists (the loud failure) ---------------------
    emitted: dict[str, list[tuple[Path, int]]] = {}
    emitted_outcomes: dict[str, set[str]] = {}
    for path in sorted(PKG.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            problems.append(f"{path.relative_to(ROOT)}: unparseable ({exc})")
            continue
        v = _Emits(path)
        v.visit(tree)
        # THE STATION A FILE IS ALLOWED TO SPEAK AS — its own module path. This check only
        # exists because the three naming layers (file, variable, station) were made to
        # AGREE. With arbitrary station names all you can verify is membership in a list,
        # which catches typos and nothing else; alignment catches the copy-pasted receipt
        # that kept the wrong callsign, which is the failure that actually happens.
        #
        # ⚠ THE COROLLARY THIS NEVER STATED: deriving the callsign from the path makes a
        # declared station whose name NO file's module path can produce unsatisfiable by
        # construction — and this gate structurally cannot report it, because it only ever
        # inspects stations that were actually emitted. `"core"` is the live case: the hub
        # is `core/manager.py`, so `own_station` is `core.manager`. Emitting `frm="core"`
        # fails the alignment check below ("may only transmit as itself"); emitting
        # `frm="core.manager"` fails the membership check above ("not declared in
        # STATIONS"). It is impossible on the TRANSMIT side only — the alignment check is
        # applied to `frm` alone, so `to="core"` would pass. Nothing addresses it either
        # (the only non-broadcast `to=` in the tree is `mapping.map_source`), so the
        # declaration is inert rather than wrong. Adding a station that no module path can
        # spell is the mistake this note exists to warn about.
        rel = path.relative_to(PKG).with_suffix("")
        own_station = ".".join(rel.parts)

        for key, to, frm, outcome, n_facts, line, prov in v.found:
            where = path.relative_to(ROOT)
            if key is None:
                problems.append(f"{where}:{line}: emit() with a non-literal key — unscannable")
                continue
            for label, station in (("to", to), ("from", frm)):
                if station is None:
                    problems.append(f"{where}:{line}: {key!r} has a non-literal {label} station")
                elif station not in STATIONS:
                    problems.append(
                        f"{where}:{line}: {key!r} names station {station!r} ({label}), which is "
                        "not declared in STATIONS"
                    )
            if prov is not None and prov not in PROVENANCE:
                # Validated HERE, at author time, and never at runtime: emit() records an
                # odd value rather than dropping it, because losing evidence to a validation
                # error is the wrong trade in the middle of an incident.
                problems.append(
                    f"{where}:{line}: {key!r} declares provenance {prov!r}, not in {PROVENANCE}"
                )
            if frm is not None and frm != own_station:
                # A station may only speak AS ITSELF. Emitting `from=mapping.map_source` out
                # of the listener is the capture putting words in an uninstrumented station's
                # mouth — §20's confident liar, and it makes a ONE-party edge look two-party,
                # which is the pass-through problem wearing the protocol's clothes.
                problems.append(
                    f"{where}:{line}: {key!r} claims to speak as {frm!r}, but this module is "
                    f"{own_station!r} — a station may only transmit as itself"
                )
            emitted.setdefault(key, []).append((where, line))
            if outcome is not None:
                emitted_outcomes.setdefault(key, set()).add(outcome)
            entry = CATALOG.get(key)
            if entry is None:
                problems.append(f"{where}:{line}: emits {key!r}, which is NOT in the catalog")
                continue
            if outcome is not None and outcome not in entry["outcomes"]:
                problems.append(
                    f"{where}:{line}: {key!r} emits outcome {outcome!r}, catalog declares "
                    f"{entry['outcomes']}"
                )
            want = len(entry["fields"])
            if n_facts != want:
                problems.append(
                    f"{where}:{line}: {key!r} passes {n_facts} fact(s), catalog declares {want}"
                )

    # --- direction 2b: every DECLARED OUTCOME is actually emitted --------------------
    # The same rot one level down. `rendered` and `written` both declared F and neither
    # could produce it, so the catalog advertised a failure report that did not exist —
    # and a reader trusting the catalog would wait for a signal that never comes.
    for key, outs in emitted_outcomes.items():
        entry = CATALOG.get(key)
        if entry is None:
            continue
        dead = sorted(set(entry["outcomes"]) - outs)
        if dead:
            problems.append(
                f"catalog[{key}]: declares outcome(s) {dead} that no call site emits"
            )

    # --- direction 2: every catalog entry is still emitted (the SILENT failure) -------
    for key in CATALOG:
        if key not in emitted:
            problems.append(
                f"catalog[{key}]: declared but NEVER EMITTED — a dead entry keeps asserting "
                "a cause that no longer happens"
            )

    # --- vocabulary hygiene: no duplicate members, no empty enum ------------------------
    #
    # ⚠ was headed "vocabularies are closed". They are not closed BY THIS GATE, and the
    # heading promised an enforcement these two loops do not perform. Nothing below
    # compares an EMITTED value against its vocabulary, and nothing asks whether a
    # declared member is emitted at all.
    #
    # WHY IT CANNOT: `DECLINE_REASONS` and `READABILITY` values ride in `emit()`'s
    # positional `*facts`, and `_Emits` records those only as a COUNT
    # (`max(0, len(args) - 4)`) — the values never reach this file, so no comparison is
    # possible. Structural consequence: removing a member that a live site still emits
    # cannot turn this gate red, because no check anywhere reads emitted fact values.
    #
    # The empty-enum check goes red only when a vocabulary is declared with NO members —
    # a preference about how the file is written, not a claim about the tree. Real closure
    # is a CODE change: capture the fact VALUES in `_Emits`, then check them against
    # `VOCABS` in both directions. `VOCABS` exists already but is used only for the catalog
    # FIELD TYPE lookup below, never against an emitted value. Until that lands, this
    # section is hygiene. The "Closed vocabularies" block in `receipts/__init__.py` carries
    # the matching per-vocabulary breakdown of what this gate does and does not police —
    # keep the two in step.
    for name, vocab in (("OUTCOMES", OUTCOMES), ("DECLINE_REASONS", DECLINE_REASONS),
                        ("PROVENANCE", PROVENANCE), ("READABILITY", READABILITY)):
        if len(set(vocab)) != len(vocab):
            problems.append(f"{name}: duplicate members")
    for key, entry in CATALOG.items():
        for field in entry.get("fields", ()):
            if isinstance(field, tuple) and len(field) == 3 and field[1] in VOCABS:
                if not VOCABS[field[1]]:
                    problems.append(f"catalog[{key}]: field {field[0]!r} enum is empty")

    print(f"catalog: {len(CATALOG)} entries | emitted keys found: {len(emitted)}")
    if problems:
        print(f"\nFAIL — {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK — catalog and call sites agree in both directions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
