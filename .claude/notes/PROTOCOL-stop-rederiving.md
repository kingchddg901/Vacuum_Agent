# We keep re-deriving things. Here is where each one was already written.

**Status:** MEASURED from a single session, 2026-09-07. Chris: *"we keep rederiving things
rediscovering things"* and *"we have too many reference files we need an index."*

An index is part of the fix and only part. Of five re-derivations in one day, **an index would
have caught one.** The other four were in files I had already opened, or already read.

## The five, and what would actually have caught each

| # | what I re-derived | where it already was | why the index would NOT have helped |
|---|---|---|---|
| 1 | the **three-dock rule** — 基础水箱版 / 上下水版 / 超薄上下水版, "the parenthesised descriptors are DOCK configurations, not robots" | `STATE-dreame-manual-corpus.md` | ⬅ **the one an index fixes.** That note is UNINDEXED and unreferenced. I found it by grepping a term I only guessed at after re-deriving the rule from manuals. |
| 2 | **mojibake = a broken ToUnicode CMap on a subsetted Identity-H font**, fix by OCR | `authoring/ocr_scrambled.py`'s docstring says it verbatim — and `ocr_raw/` already held OCR output for the exact three files | not a note at all. Fixture SCRIPT knowledge, indexed nowhere, searched by nobody. |
| 3 | "families holding multiple product names" filed as a **defect** | `upkeep_catalog.py`'s first 12 lines explain it as DESIGN, with the reg-code rule and three worked examples | I had been querying that file with regex **all day** and never read its header. |
| 4 | **reg-code platform matching** ("two names sharing an r-code are the same hardware, proof not inference") | the same 12 lines | same |
| 5 | that a **per-model capability table exists** | `PARKED-dreame-consumable-declaration.md` §3 names `DEVICE_INFO` and says "the RIGHT long-term source... when it is decoded" | **I read that note earlier the same session** and did not carry the pointer forward. |

## So the failure is four different things

1. **Unindexed** (1 case) — 50 notes have no INDEX.md row; **45 of those are referenced by no
   other note either**, which is the most invisible state a file can be in. `check_index.py`
   now reports all three defects and exits non-zero on unindexed count.
2. **Un-indexable location** (1 case) — the knowledge was a docstring in a fixture script. The
   notes index does not cover `authoring/compose/tools/` (276 scripts) or `authoring/` at all.
3. **Header not read** (2 cases) — I queried a file's DATA all day without reading its DOC. This
   is the cheapest miss to fix and the most embarrassing: the answer was in the first 12 lines
   of the file already open.
4. **Read and dropped** (1 case) — the pointer was in a note I read that session. Reading is not
   retaining; a "not yet done" line in a note is a TODO addressed to whoever next needs it.

## The rules that follow

> **Before deriving a fact ABOUT an artifact, read that artifact's own header.**
> If you are regexing a file, you have already opened it. Read its docstring first — it is
> cheaper than every measurement you are about to take, and it is written by someone who knew.

> **A note saying "X is not yet decoded / not yet done" is a POINTER, not a status.**
> When you find yourself needing X, that note is the first place to look, not a historical record.

> **Knowledge lives in three places here, and only one is indexed:** `.claude/notes/`,
> module docstrings in `custom_components/`, and script docstrings in the fixture's `authoring/`.
> A search that covers one of the three will keep missing two thirds of what is already known.

## The standing gate this reinforces

`CLAUDE.md` already says **SCAN THE DOCS BEFORE SCOPING**, and names `docs/dev/`. Every one of
today's five misses was **outside** `docs/dev/` — in notes, in a module header, in a fixture
script. The rule was right and its stated scope was too narrow.
