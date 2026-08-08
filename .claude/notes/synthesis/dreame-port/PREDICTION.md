# Pre-registered prediction — written BEFORE the blind builders returned

Chris, 2026-08-07, while the run was in flight:

> "reading the adapers would not help them and would give them away i think not
> much wil survive this time"

Recorded now, unmodified, so the outcome cannot be retrofitted into "about what
we expected". Three separable claims:

**P1 — reading the existing adapters would not have helped.**
Partly true and worth splitting. VALUES would not transfer: Dreame's wire shape
is `columns` (positional parallel arrays), unlike Eufy's `rows` and Roborock's
`flat ids + batch scalar`, and its suction/water integer encodings are its own.
But STRUCTURE would transfer — which config blocks exist, what a filled-in one
looks like, the shape of a vocabulary declaration. A working example is far
easier to follow than a reference table, and that gap between example and
reference is precisely what this run measures. So P1 holds for the brand facts
and NOT for the framework scaffolding, which is the half under test.

**P2 — reading them would give the builder away.**
Agreed, and it is checkable rather than assumed. Hardening rule 11 names
INCIDENTAL SIMILARITY as the measurable smoking gun: a reconstruction matching
the original's incidental choices — key ordering, helper naming, comment
phrasing, structure the contract does not force — beyond chance is carrying
smuggled answers whatever the prose looks like. Two independent builders make
this sharper: agreement on CONTRACT-FORCED content is expected; agreement on
incidental choices that also match a shipped adapter is not.
ACTION: run that comparison on both outputs before trusting either.

**P3 — "not much will survive this time."** Chris expects the guide to fail
substantially: many gaps, ambiguities, or inferred values.

## How P3 gets scored, decided in advance

Not by gap COUNT, which rewards nitpicking. By whether a gap BLOCKED a
contract-valid config:

| outcome | reading |
|---|---|
| both builders produce contract-valid configs, gaps are cosmetic | guide is SUFFICIENT; P3 refuted |
| both fail at the SAME point | guide DEFECT at that point; P3 confirmed, and located |
| they diverge on a value the docs do specify | READER defect, not a guide defect (protocol verdict A) |
| either falls back to reading `config_schema.py` | doc 22 is not load-bearing where it claims to be — a partial P3 confirmation regardless of whether the build succeeded |

The last row is the one to watch. A build can succeed while the DOC fails, if the
builder got there by reading code the doc was supposed to summarise.

## P2 scoring, made mechanical (Chris, 2026-08-07, still pre-results)

> "names should not survive but ideas should i think"

This replaces "beyond chance" with a lookup, and it is now protocol rule 11.
Convergent IDEAS are the target signature — two builders against the same
contract should land in the same concept, and penalising that would punish the
docs for working. Convergent NAMES have no innocent excuse: nothing forces a
particular helper name, key ordering or comment phrasing.

**The cutoff: a name shared with a shipped adapter that does NOT appear anywhere
in the permitted reading set is a smuggle signal. A name that DOES appear there
is legitimate vocabulary.**

So the comparison to run on the two outputs, before trusting either:

1. builder-1 vs builder-2 — do the IDEAS converge? (docs carried the concept)
2. builder-N vs adapters/eufy + adapters/roborock — do any NAMES match?
3. for each matching name, is it present in the porting guide, doc 21, doc 22,
   the contract harness, or the Dreame provider source? Present = clean.
   Absent = a source that is not the docs.

Divergent ideas is NOT dishonesty — it is a specification gap, and the most
interesting result available short of a smuggle.
