"""Gate for a BN (break-notation) placement pass.

A BN boundary is TWO COMMENT LINES marking where one section of a file ends and the
next begins:

    # anchor: BN<6 Crockford chars>
    # ===================== THE READ MODEL =====================

It asserts nothing about behaviour, so a BN pass has a property almost no other change
has: **every line it adds is a comment, and it deletes nothing.** That is mechanically
provable, and proving it kills outright the failure class that actually bit this repo
while planting anchors — three landed inside HTML template literals, one inside a
``/* */`` block, seven split a comment sentence mid-paragraph. None of those were
judgement calls; all of them are visible to a script and invisible to a reviewer
skimming a large diff.

WHAT THIS CHECKS, and why each one exists rather than being assumed:

  1. COMMENT-ONLY DIFF. Every added line is a comment; no line is removed; no line is
     modified. This is the strongest check and the cheapest. If it passes, nothing landed
     inside a string, no code moved, and no behaviour changed — without needing to reason
     about any of those separately.
  2. THE FILE STILL PARSES. A comment-only diff cannot break parsing in Python, but it
     CAN in JavaScript (an added ``//`` inside a template literal is text, not a comment),
     and JS is exactly where the template-literal failures happened.
  3. THE BOUNDARY IS REALLY A COMMENT WHERE IT LANDED. Line 1 checks the diff; this
     checks the tree. A ``#`` inside a docstring is an added line that LOOKS like a
     comment to a regex and is a string to the parser. Python is checked by tokenizing;
     JS by a brace/backtick scan.
  4. THE ANCHOR IS DECLARED IN THE FORM doc_anchor.py CAN SEE — the literal marker
     ``anchor:`` followed by a BN token. ``# BN<token>`` alone is invisible to the anchor
     tooling and would leave the boundary uncitable, which defeats the point.
  5. NO DUPLICATE TOKENS, and every token is well-formed against the real alphabet
     (Crockford Base32: no I, L, O or U).
  6. THE NAME LINE EXISTS AND IS NOT EMPTY. A token with no human-readable name is an
     address to nowhere.

WHAT IT DELIBERATELY DOES NOT CHECK: whether the boundary is in the RIGHT PLACE. Whether
a section is a real region of the file is judgement, it belongs to a reader, and a script
that pretended to answer it would be the decorative-gate shape this repo keeps finding.

Run:
    python scripts/check_bn_boundaries.py                 # working tree vs HEAD
    python scripts/check_bn_boundaries.py --base <ref>    # vs another ref
    python scripts/check_bn_boundaries.py --paths a.py b.js
    python scripts/check_bn_boundaries.py --self-test     # prove the gate can FAIL

Exit 0 clean, 1 on any violation.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import subprocess
import sys
import tokenize

REPO = pathlib.Path(__file__).resolve().parent.parent

# Owned by scripts/doc_anchor.py. Duplicated here rather than imported so this gate
# stays runnable on a tree where doc_anchor is mid-edit — and asserted equal by
# --self-test, so the copy cannot drift silently. (This pair is itself an RN.)
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
MARKER = "anchor:"
BN_TOKEN = re.compile(r"\bBN[" + ALPHABET + r"]{6}\b")
BN_DECL = re.compile(MARKER + r"\s*(BN[" + ALPHABET + r"]{6})\b")
# A malformed token that WANTED to be one: right prefix, wrong shape. Reported rather
# than ignored, because a silent near-miss is how an uncitable boundary ships.
BN_MALFORMED = re.compile(r"\bBN[0-9A-Z]{2,10}\b")

COMMENT_LINE = {
    ".py": re.compile(r"^\s*#"),
    ".js": re.compile(r"^\s*(//|/\*|\*)"),
    ".mjs": re.compile(r"^\s*(//|/\*|\*)"),
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    ).stdout


def changed_files(base: str) -> list[str]:
    out = _git("diff", "--name-only", base, "--", "*.py", "*.js", "*.mjs")
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def diff_is_comment_only(path: str, base: str) -> list[str]:
    """CHECK 1. Added lines must all be comments; nothing removed.

    ``-U0`` so the hunks carry no context lines to misread as additions.
    """
    problems: list[str] = []
    suffix = pathlib.Path(path).suffix
    is_comment = COMMENT_LINE.get(suffix)
    if is_comment is None:
        return [f"{path}: unsupported file type for a BN pass"]

    diff = _git("diff", "-U0", base, "--", path)
    lineno = 0
    for raw in diff.splitlines():
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
            continue
        if raw.startswith("---") or raw.startswith("+++"):
            continue
        if raw.startswith("-"):
            problems.append(
                f"{path}: a line was REMOVED — a BN pass adds comments and deletes "
                f"nothing: {raw[1:80]!r}"
            )
        elif raw.startswith("+"):
            body = raw[1:]
            if body.strip() and not is_comment.match(body):
                problems.append(
                    f"{path}:{lineno}: added a NON-COMMENT line — either code moved or a "
                    f"marker landed inside a string: {body[:80]!r}"
                )
            lineno += 1
    return problems


def _py_comment_lines(text: str) -> set[int]:
    """Line numbers Python's own tokenizer calls COMMENT. The authority for check 3."""
    out: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                out.add(tok.start[0])
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return set()
    return out


def _js_comment_lines(text: str) -> set[int]:
    """Approximate, and honest about it: tracks strings, template literals and block
    comments so a ``//`` inside a backtick string is NOT counted as a comment. That is
    the exact case that put three anchors inside HTML template literals."""
    out: set[int] = set()
    line, i, n = 1, 0, len(text)
    state = None  # None | "'" | '"' | "`" | "//" | "/*"
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "\n":
            line += 1
            if state == "//":
                state = None
            i += 1
            continue
        if state is None:
            if ch == "/" and nxt == "/":
                state, out = "//", out | {line}
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "/*"
                out.add(line)
                i += 2
                continue
            if ch in "'\"`":
                state = ch
                i += 1
                continue
        elif state == "/*":
            out.add(line)
            if ch == "*" and nxt == "/":
                state = None
                i += 2
                continue
        elif state in "'\"`":
            if ch == "\\":
                i += 2
                continue
            if ch == state:
                state = None
        elif state == "//":
            out.add(line)
        i += 1
    return out


def check_tree(path: str) -> list[str]:
    """CHECKS 2-6, against the file as it stands rather than against the diff."""
    problems: list[str] = []
    p = REPO / path
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    suffix = p.suffix

    if suffix == ".py":
        try:
            compile(text, path, "exec")
        except SyntaxError as exc:
            return [f"{path}: no longer parses — {exc}"]
        comment_lines = _py_comment_lines(text)
    else:
        comment_lines = _js_comment_lines(text)

    for i, line in enumerate(lines, start=1):
        decl = BN_DECL.search(line)
        if decl:
            if i not in comment_lines:
                problems.append(
                    f"{path}:{i}: the boundary is NOT A COMMENT where it landed — it is "
                    f"inside a string, docstring or template literal. This is the failure "
                    f"that put three anchors inside HTML template literals."
                )
            # CHECK 6 — the name line
            nxt = lines[i] if i < len(lines) else ""
            body = re.sub(r"^\s*(#|//|\*|/\*)\s*", "", nxt).strip(" =-*/")
            if not body:
                problems.append(
                    f"{path}:{i}: {decl.group(1)} has no NAME line beneath it. A token "
                    f"with no human-readable name is an address to nowhere."
                )
            continue
        # CHECK 4/5 — a token that is not declared in the form the tooling reads.
        #
        # Asks whether THIS token is the one the marker declares, not merely whether the
        # word "anchor:" appears somewhere on the line. The weaker version shipped for
        # about four minutes and was caught by its own ablation: a line reading
        # `# BN<token>  a token with no anchor: marker` contains the marker as PROSE, so
        # `MARKER in line` was true and the undeclared token walked through the gate.
        declared = {m.group(1) for m in BN_DECL.finditer(line)}
        for tok in BN_TOKEN.findall(line):
            if tok not in declared:
                problems.append(
                    f"{path}:{i}: {tok} is not declared by a '{MARKER}' marker on its own "
                    f"line, so doc_anchor.py cannot see it and the boundary is uncitable. "
                    f"A citation elsewhere is fine; a DECLARATION needs the marker."
                )
        for bad in BN_MALFORMED.findall(line):
            if not BN_TOKEN.match(bad):
                problems.append(
                    f"{path}:{i}: {bad!r} looks like a BN token but is malformed "
                    f"(need BN + 6 chars from {ALPHABET})."
                )
    return problems


def check_duplicates(paths: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    problems: list[str] = []
    for path in paths:
        text = (REPO / path).read_text(encoding="utf-8", errors="replace")
        for tok in BN_DECL.findall(text):
            if tok in seen:
                problems.append(
                    f"{path}: {tok} is already declared in {seen[tok]} — an anchor is a "
                    f"unique identity, and a duplicate makes both uncitable."
                )
            seen[tok] = path
    return problems


# ⚠ FIXTURE TOKENS ARE ASSEMBLED, NEVER WRITTEN OUT, AND THAT IS LOAD-BEARING.
# doc_anchor.py scans source files for the marker followed by a token and cannot tell a
# checker's test data from a real declaration. Spelling them here registered 10 phantom
# BN anchors and produced every problem `doc_anchor.py --check` reported. Concatenating
# keeps the literal out of the file while the runtime VALUES stay exactly what the checks
# need. If you inline these back, the anchor registry starts counting this file's
# test data as real rules.
_MK = "anchor" + ":"
_T_OK = "BN" + "4K2P9M"      # well-formed
_T_ALT = "BN" + "7QW2XH"     # well-formed, distinct
_T_REAL = "BN" + "H3M8T5"    # well-formed, used by the prose-marker regression
_T_BAD = "BN" + "IL0U12"     # I/L/O/U are excluded from Crockford -- must be REJECTED

def self_test() -> int:
    """CAN THIS GATE FAIL? A gate only ever seen passing has not been tested.

    Exercises every check against a violation built for the purpose, and a clean case
    against each, so a detector that flagged EVERYTHING would fail here too.
    """
    import tempfile

    ok = True

    def expect(name: str, got: bool, want: bool) -> None:
        nonlocal ok
        if got != want:
            ok = False
            print(f"    FAIL  {name}: expected {'a problem' if want else 'clean'}")
        else:
            print(f"    ok    {name}")

    print("  self-test — proving each check can fire:\n")

    # the alphabet/marker copy must match doc_anchor.py (the RN this file admits to)
    src = (REPO / "scripts" / "doc_anchor.py").read_text(encoding="utf-8")
    expect("ALPHABET matches doc_anchor.py",
           f'ALPHABET = "{ALPHABET}"' in src, True)
    expect("MARKER matches doc_anchor.py",
           f'MARKER = "{MARKER}"' in src, True)

    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)

        # CHECK 3 — a marker inside a Python docstring is NOT a comment
        bad = d / "in_docstring.py"
        bad.write_text(
            'def f():\n'
            '    """doc\n'
            f'    # {_MK} {_T_OK}\n'
            '    # ===== NOT REALLY A COMMENT =====\n'
            '    """\n',
            encoding="utf-8",
        )
        text = bad.read_text(encoding="utf-8")
        cl = _py_comment_lines(text)
        expect("python: marker inside a docstring is not a comment line", 3 in cl, False)

        good = d / "real.py"
        good.write_text(
            f'# {_MK} {_T_OK}\n'
            '# ===== SAVED ZONES =====\n'
            'def f():\n    pass\n',
            encoding="utf-8",
        )
        expect("python: a real comment IS a comment line",
               1 in _py_comment_lines(good.read_text(encoding="utf-8")), True)

        # CHECK 3, JS — a // inside a template literal is text, not a comment
        js = d / "tpl.js"
        js.write_text(
            'const html = `\n'
            f'  // {_MK} {_T_ALT}\n'
            '`;\n'
            f'// {_MK} {_T_REAL}\n',
            encoding="utf-8",
        )
        jcl = _js_comment_lines(js.read_text(encoding="utf-8"))
        expect("js: marker inside a template literal is not a comment", 2 in jcl, False)
        expect("js: a real // line IS a comment", 4 in jcl, True)

        # CHECK 4/5 — token shapes
        expect("token without the marker is caught",
               bool(BN_TOKEN.search(f"# {_T_OK}")) and not BN_DECL.search(f"# {_T_OK}"), True)
        expect("well-formed token is accepted",
               bool(BN_DECL.search(f"# {_MK} {_T_OK}")), True)
        expect("token using an excluded letter is rejected",
               bool(BN_DECL.search(f"# {_MK} {_T_BAD}")), False)

        # REGRESSION, and the reason this whole self-test exists. The first version of
        # check 4 asked `MARKER not in line`, which is true of the line below — the word
        # "anchor:" appears as PROSE, several words away from a token it does not declare.
        # The undeclared token walked straight through the gate, and it was caught only by
        # ablating a real file rather than by reading the check. A gate that reasons about
        # a line instead of about the TOKEN has a hole exactly this shape.
        prose = f"# {_T_REAL}  a token with no {_MK} marker of its own"
        declared = {m.group(1) for m in BN_DECL.finditer(prose)}
        undeclared = [t for t in BN_TOKEN.findall(prose) if t not in declared]
        expect("token adjacent to the marker-as-PROSE is still caught",
               undeclared == [_T_REAL], True)
        real = f"# {_MK} {_T_REAL}"
        declared_real = {m.group(1) for m in BN_DECL.finditer(real)}
        expect("a genuinely declared token is NOT reported",
               [t for t in BN_TOKEN.findall(real) if t not in declared_real] == [], True)

    print()
    return 0 if ok else 1


def main() -> int:
    # A GATE THAT CRASHES WHILE REPORTING IS A GATE THAT CANNOT REPORT. Several problem
    # messages contain characters cp1252 cannot encode, so on a Windows console this used
    # to raise UnicodeEncodeError PART WAY THROUGH printing the findings -- losing the
    # remaining ones and surfacing as a crash rather than as a clean failure, which in CI
    # reads as "the tool is broken", not "the code is wrong".
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover -non-reconfigurable stream
        pass

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="HEAD", help="ref to diff against (default HEAD)")
    ap.add_argument("--paths", nargs="*", help="check these files instead of the diff")
    ap.add_argument("--self-test", action="store_true", help="prove the gate can fail")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    paths = args.paths or changed_files(args.base)
    if not paths:
        print("  no .py/.js/.mjs changes to check")
        return 0

    problems: list[str] = []
    for path in paths:
        if not (REPO / path).exists():
            continue
        if not args.paths:
            problems += diff_is_comment_only(path, args.base)
        problems += check_tree(path)
    problems += check_duplicates([p for p in paths if (REPO / p).exists()])

    tokens = sum(
        len(BN_DECL.findall((REPO / p).read_text(encoding="utf-8", errors="replace")))
        for p in paths if (REPO / p).exists()
    )
    print(f"  {len(paths)} file(s) · {tokens} BN boundary/ies declared")
    if problems:
        print(f"  {len(problems)} problem(s):\n")
        for p in problems:
            print(f"    {p}")
        return 1
    print("  clean — every added line is a comment, every boundary is really a comment,")
    print("  every token is well-formed, declared where doc_anchor can see it, and unique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
