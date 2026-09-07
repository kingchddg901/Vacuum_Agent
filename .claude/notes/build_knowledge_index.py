"""One searchable index across ALL THREE places knowledge lives here.

Chris: "we keep rederiving things rediscovering things."

PROTOCOL-stop-rederiving.md measures five re-derivations in one session. Only ONE
was a missing INDEX.md row. Two were in a module header I had open all day, one was a
docstring in a fixture script, one was a pointer in a note I had already read.

The notes index covers `.claude/notes/`. Nothing covers the other two:

    custom_components/**/*.py        module docstrings - upkeep_catalog.py's first
                                     12 lines explain the reg-code platform rule that
                                     I re-derived from the corpus and then filed as a
                                     defect
    <fixture>/authoring/**/*.py      276 scripts in tools/ alone - ocr_scrambled.py's
                                     docstring names the ToUnicode/mojibake diagnosis
                                     verbatim, and its OUTPUT was already on disk for
                                     the exact files I re-diagnosed

This writes KNOWLEDGE-INDEX.md: every source with its own first documented line, so
ONE grep reaches all three. It is generated - never hand-edit it; re-run this instead.

It does not replace INDEX.md. That file is hand-written, carries rich "when to open
it / what must fire" hooks, and is the thing to read. This is the thing to SEARCH.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)) or "."
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FIXTURE = "C:/Users/CKing/Documents/durable/dreame-port-fixture"
OUT = os.path.join(HERE, "KNOWLEDGE-INDEX.md")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".claude", "dist", "build",
             "htmlcov", ".pytest_cache", "worktrees"}
# generated artefacts: huge, and their docstring says nothing a searcher wants
SKIP_FILES = re.compile(r"_composed\.py$|_generated\.py$|_translated\.py$|resources\.py$"
                        r"|upkeep_guides_i18n[/\\]", re.I)


def docstring(path):
    try:
        src = io.open(path, encoding="utf-8", errors="replace").read(6000)
    except Exception:
        return None
    m = re.match(r'\s*(?:#[^\n]*\n)*\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', src, re.S)
    if not m:
        return None
    body = m.group(1).strip()
    if not body:
        return None
    first = body.split("\n", 1)[0].strip()
    return first[:150] if first else None


def first_line_md(path):
    try:
        for line in io.open(path, encoding="utf-8", errors="replace"):
            s = line.strip().lstrip("#").strip()
            if s and not s.startswith("<!--"):
                return s[:150]
    except Exception:
        pass
    return ""


def walk(root, exts):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in sorted(filenames):
            if f.endswith(exts):
                p = os.path.join(dirpath, f)
                if SKIP_FILES.search(p.replace("\\", "/")):
                    continue
                yield p


def main():
    rows = {"notes": [], "module": [], "fixture": []}

    for f in sorted(os.listdir(HERE)):
        if f.endswith(".md") and f != "KNOWLEDGE-INDEX.md":
            rows["notes"].append((f, first_line_md(os.path.join(HERE, f))))

    cc = os.path.join(REPO, "custom_components")
    if os.path.isdir(cc):
        for p in walk(cc, (".py",)):
            d = docstring(p)
            if d:
                rows["module"].append((os.path.relpath(p, REPO).replace("\\", "/"), d))

    au = os.path.join(FIXTURE, "authoring")
    if os.path.isdir(au):
        for p in walk(au, (".py",)):
            d = docstring(p)
            if d:
                rows["fixture"].append((os.path.relpath(p, FIXTURE).replace("\\", "/"), d))

    with io.open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# Knowledge index — GENERATED, do not hand-edit\n\n")
        fh.write("Regenerate: `python .claude/notes/build_knowledge_index.py`\n\n")
        fh.write("One place to **search** for something already written down. "
                 "Read [INDEX.md](INDEX.md) instead — it carries the real hooks; "
                 "this carries the coverage.\n\n")
        fh.write("Knowledge here lives in three places and only the first was ever indexed. "
                 "See [PROTOCOL-stop-rederiving.md](PROTOCOL-stop-rederiving.md) for the five "
                 "re-derivations that motivated this and which of them an index would "
                 "actually have prevented (one of five).\n\n")
        for key, title in (("notes", "Notes  `.claude/notes/`"),
                           ("module", "Module docstrings  `custom_components/`"),
                           ("fixture", "Fixture tooling  `<fixture>/authoring/`")):
            fh.write("## %s — %d\n\n" % (title, len(rows[key])))
            fh.write("| file | first documented line |\n|---|---|\n")
            for p, d in rows[key]:
                fh.write("| `%s` | %s |\n" % (p, d.replace("|", "\\|")))
            fh.write("\n")
    for k in rows:
        print("%-8s %d" % (k, len(rows[k])))
    print("-> %s (%d KB)" % (OUT, os.path.getsize(OUT) // 1024))


if __name__ == "__main__":
    main()
