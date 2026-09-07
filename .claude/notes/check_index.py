"""Report notes that INDEX.md does not list. An unindexed note is one you re-derive.

Chris: "we have too many reference files we need an index."

The cost is not hypothetical. On 2026-09-07 I re-derived the three-dock rule
(基础水箱版 / 上下水版 / 超薄上下水版 - "the parenthesised descriptors are DOCK
configurations, not robots") from the manual corpus, and then found it already
written in STATE-dreame-manual-corpus.md - a note that is NOT in INDEX.md. Same for
the CCC platform findings (S60 Disk = S50 Pro) and the reg-code rule. I found them by
grepping, which only works if you already suspect they exist.

This is the notes analogue of the memory integrity check's third defect: "f/ or u/
memory missing from this index - a rule that can never fire."

DEFECTS REPORTED
  1 UNINDEXED   a note file with no row in INDEX.md
  2 DANGLING    an INDEX.md row pointing at a file that does not exist
  3 UNLINKED    a note nothing else references and the index does not list - the
                most invisible state a note can be in

Exit code is the count of unindexed notes, so it can gate a commit if wanted.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)) or "."
INDEX = os.path.join(HERE, "INDEX.md")

# Not notes: the index itself, this checker, and the session handoff which is
# deliberately a moving scratch surface rather than a reference.
EXCLUDE = {"INDEX.md", "SESSION_HANDOFF.md", "REPAIR-BACKLOG.md"}


def main():
    idx = io.open(INDEX, encoding="utf-8").read()
    listed = set(re.findall(r"\]\((?!http)([^)]+\.md)\)", idx))
    listed |= set(re.findall(r"\[\[([^\]]+)\]\]", idx))
    listed |= {l + ".md" for l in re.findall(r"\[\[([^\]]+)\]\]", idx)}

    files = sorted(f for f in os.listdir(HERE)
                   if f.endswith(".md") and f not in EXCLUDE)
    unindexed = [f for f in files if f not in listed]
    dangling = sorted(t for t in listed
                      if t.endswith(".md") and not os.path.exists(os.path.join(HERE, t)))

    # cross-references between notes
    refs = {}
    for f in files:
        t = io.open(os.path.join(HERE, f), encoding="utf-8", errors="replace").read()
        refs[f] = set(re.findall(r"\]\((?!http)([^)]+\.md)\)", t)) | \
            {x + ".md" for x in re.findall(r"\[\[([^\]]+)\]\]", t)}
    referenced = set()
    for v in refs.values():
        referenced |= v
    unlinked = [f for f in unindexed if f not in referenced]

    print("notes: %d   INDEX rows: %d" % (len(files), len(re.findall(r"^- ", idx, re.M))))
    print()
    print("UNINDEXED  (no row in INDEX.md): %d" % len(unindexed))
    for f in unindexed:
        first = ""
        try:
            for line in io.open(os.path.join(HERE, f), encoding="utf-8", errors="replace"):
                s = line.strip().lstrip("# ").strip()
                if s:
                    first = s
                    break
        except Exception:
            pass
        mark = "  <- and nothing links it either" if f in unlinked else ""
        print("   %-56s %s%s" % (f, first[:56], mark))
    print()
    print("DANGLING   (row points at a missing file): %d" % len(dangling))
    for t in dangling:
        print("   %s" % t)
    print()
    print("UNLINKED   (not indexed AND not referenced by any note): %d" % len(unlinked))
    print()
    if unindexed:
        print("An unindexed note is one you re-derive. STATE-dreame-manual-corpus.md held")
        print("the three-dock rule and the CCC platform findings, was not indexed, and was")
        print("re-derived from the manual corpus before being found by grep.")
    return len(unindexed)


if __name__ == "__main__":
    sys.exit(main())
