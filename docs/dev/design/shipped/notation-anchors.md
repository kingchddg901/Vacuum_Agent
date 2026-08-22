# Notation Anchors

> **Status: SPECIFICATION — partially built.** `CN` in use (9 anchors), `IN` in use
> (1, indexed by [00b](../../00b-invariants.md)), `RN` in use (2, indexed by
> [00c](../../00c-replicas.md)). `BN` added 2026-08-21, no anchors minted yet.
> `SN`, `HN` and `PN` remain reserved and unused. Tooling: `scripts/doc_anchor.py`
> (`--mint` / `--check` / `--show` / `--orphans`), enforced by `ANC-1..3` in
> `tests/unit/test_generated_doc_gate.py`.

Vacuum Agent needs references that survive refactors.

Line numbers do not. Descriptive rule names do better, but they still carry meaning that can become stale as a system evolves. A rule named `ENT-13` may later move out of entity resolution entirely while remaining the same conceptual lineage.

Notation anchors separate **identity from meaning**.

## Identifier format

A notation anchor is exactly eight characters:

```text
PPXXXXXX
```

Where:

- `PP` is a two-letter notation-class prefix.
- `XXXXXX` is a six-character opaque random identifier drawn from Crockford Base32.
- Prefixes use letters only.
- The random suffix carries **no semantic information**.
- IDs are minted with a cryptographically strong random generator such as `secrets.choice()`.
- A collision during minting causes another candidate to be generated.
- An already-assigned identifier is never regenerated automatically.

With Crockford's 22 unambiguous letters available for the two-letter prefix, the scheme provides **484 notation namespaces**. Each prefix then has `32^6`, or **1,073,741,824**, possible opaque identities.

Namespace exhaustion is therefore deliberately not a practical concern.

## Identity is permanent

The anchor identifies a lineage, not its current wording, file, subsystem, or implementation.

For example:

```text
IN7K3M9Q
```

may initially identify an entity-resolution invariant. That invariant may later move to another module, acquire a different descriptive rule name, or become part of a more general subsystem.

The anchor remains:

```text
IN7K3M9Q
```

Meaning is allowed to evolve. Identity is not.

Existing descriptive identifiers such as `ENT-13` may coexist with notation anchors. They serve different purposes:

```text
ENT-13       current human taxonomy
IN7K3M9Q     permanent identity
```

## Initial notation classes

The prefix defines **why a link exists**, not which subsystem owns it.

### `CN` — Code Notation

Stable identity for an implementation concept or significant code site.

Used when documentation, tests, audit material, or other code needs a durable reference to a specific implementation lineage.

Example:

```text
CN4D8W2P
```

### `SN` — Semantic Notation

Stable identity for the semantic translation layer used by runtime diagnostics, debug notices, receipts, and related observability surfaces.

An `SN` key lets a runtime observation say, in effect:

> This message represents this semantic event or interpretation.

It provides a durable bridge from emitted diagnostic evidence back to the definition that explains its meaning.

Example:

```text
SN6Q3T9K
```

### `HN` — Historical Notation

Stable identity for historical provenance.

Used where the important link is not merely what the system does now, but how or why a behavior, decision, migration, repair, or architectural constraint came to exist.

Historical meaning can accumulate without requiring the implementation anchor itself to encode chronology.

Example:

```text
HN8M2R5C
```

### `PN` — Prose Notation

Stable link into the deep design/documentation system.

A `PN` reference indicates that a local implementation, short explanation, or operational document has a deeper canonical explanation elsewhere.

It allows concise material to say:

> The full reasoning for this exists here.

without embedding a fragile filename, section number, or line number as the identity of that reasoning.

Example:

```text
PN3W7F6D
```

### `IN` — Invariant Notation

Stable identity for a behavioral or architectural invariant.

An invariant describes something the system must continue to preserve regardless of refactoring.

Its implementations, tests, enforcement points, and prose explanations may all move independently while continuing to reference the same invariant anchor.

Example:

```text
IN5C9V2R
```

### `EN` — Enforcement Notation

Added 2026-08-22. **`IN`'s twin: a rule that binds a PERSON, not the program.**

An `EN` is a genuine obligation whose enforcement lives outside the code — *never edit
`.storage` directly*, *a service call moves real hardware*. It can never have a bite,
because nothing in the repository can be made to go red when it is broken.

**The discriminator is one question: WHO BREAKS IT?**

> A person doing something → `EN`.  The program doing something → `IN`.

That test is positive and decidable. The class was previously distinguished by *"why this
can never be an `IN`"* — defined by what it lacks — and a negative definition loses the
first time somebody argues that a bite exists after all, promoting a row that was never
an invariant.

**Why it is not just an `IN` with a footnote.** `IN`'s whole discipline is *name the input
that makes it red*. An `IN` that cannot bite corrupts the class: you can no longer tell an
enforced rule from an aspirational one by looking at its prefix. Splitting these out
protects `IN`'s meaning, the same argument that gave `BN` its own namespace rather than
diluting `CN`.

**Where it declares.** In prose, like `PN` and unlike everything else — its reasoning IS the
artifact, so the registry holding that reasoning is the declaration site. Declaring it in
source would pin it to a file that does not enforce it, which reads as a guard and is not
one. The integrity question therefore inverts: for an `IN` ask *is it declared at a site?*;
for an `EN` ask *does anything cite it?*

Example (illustrative, deliberately NOT a minted token — the `PN` section above does the
same. A worked example that uses a REAL anchor becomes a live citation of it, which
silently satisfies `[RR-4]`'s liveness rule and makes the check decorative):

```text
EN7K3M2Q
```

⚠ **`EN` did not exist until 2026-08-22, and three rules were filed under `PN` in the
meantime** — `PN` is a *pointer to a deeper explanation*, which is not what those three
are. They were re-minted, not re-prefixed, so the old
tokens do not survive looking well-formed — the mapping is recorded in `00b-invariants.md`,
not here, so this specification does not become a citation of the rules it describes.
`doc_anchor.py`'s prose-declaration comment had
drifted the same way and is corrected. Dated records keep the old tokens.
### `BN` — Break Notation

Added 2026-08-21. **Every other class anchors a claim. `BN` anchors a place.**

A break says *section one ends, section two begins*. It asserts nothing about what
either section means, which is why it can never be wrong — only stale. A document
citing a `BN` is pointing at a **region of a file**, not at a rule.

```python
# ---------------------------------------------------------------------------
# anchor: BN7T3K9W
# saved-zones — create / rename / delete / clean stored rects
# ---------------------------------------------------------------------------
```

⚠ **The marker word is `anchor:`, the same as every other class — this example said
`section:` until 2026-08-22 and that form is INVISIBLE to the tooling.** `doc_anchor.py`
and `check_bn_boundaries.py` both scan for `anchor:`; a `section:` line declares nothing,
and because the token is still *present* the gate reports it as an UNDECLARED token —
verified by running both regexes against the old form.

⚠ **The NAME goes on its own line BENEATH the token, not appended to it.** `check_bn_boundaries.py`
requires it (*"a token with no NAME line beneath it is an address to nowhere"*), and the reason is
the gate's headline property: a BN pass **adds comment lines and deletes nothing**, which is
mechanically provable. Appending the name to the token line REWRITES an existing line, so the
diff stops being purely additive and the gate rejects it. This example was wrong in BOTH ways
until 2026-08-22 — marker word and layout — and a 175-marker pass written to it failed on
both counts, caught by running the gate rather than by reading it. (Token above is illustrative
and deliberately unminted, as in the `PN` and `EN` sections: a worked example using a real
anchor becomes a live citation of it.)

Cited from prose in the ordinary form — path, `#`, token:

```text
mapping/mapping_services.py#BN7T3K9W
```

**The name is what people read; the token is what survives renaming the name.**

**Why sections get a namespace instead of reusing `CN`.** A large module holds dozens of
dividers. Minting a code-notation token for each would dilute `CN` until an anchor
stopped signalling *worth pointing at* — the scarcity is the signal. Keeping breaks in
their own class means `BN` can be dense without costing `CN` anything.

**What this is FOR, and it is the load-bearing part:** a `BN` lets prose address a region
of a file **without the file being split**. `mapping/mapping_services.py` holds five
service domains sharing 7% of their code; each can own a document today, at 3,224 lines
and unmoved, because a `BN` gives the document something stable to point at. If the file
is ever split, the breaks are the cut lines — already placed, already agreed, already
cited — and the anchor travels with its section, so the prose does not change.

## Prefixes are types, not folders

A prefix should only be introduced when the referenced relationship is meaningfully different.

Do not create prefixes for subsystems:

```text
EU  Eufy
RB  Roborock
DG  diagnostics
UI  frontend
```

Those meanings belong in code and prose and will evolve with the architecture.

The notation class should instead describe the **kind of relationship being traversed**:

```text
CN  implementation
SN  runtime semantic translation
HN  historical provenance
PN  deep prose/design — a POINTER to where the canonical explanation lives
IN  invariant — the program must preserve it, and a test can go red
EN  enforcement note — a rule that binds a PERSON; no bite is possible
RN  replica set — one rule, several deliberate copies
BN  section break — a place in a file, not a claim
```

`RN` was added 2026-08-16. Its shape differs from the others in one way worth stating: an
`RN` is inherently multi-site, but the scheme's rule is *definitions are unique, references
are many*. So an `RN` is declared once at the set's natural primary — the shared artifact
the copies revolve around, or the copy carrying the reasoning — and referenced from every
other member. The listing of sets lives in [00c](../../00c-replicas.md); the declaration
cannot, because declarations are scanned in source only.

This makes the prefix function as a small type system for repository knowledge rather than as a filing scheme.

### What `RN` is actually for — INVISIBILITY, not file boundaries

Recorded 2026-08-21 after a measurement that used the wrong axis.

An `RN` earns its keep when a reader editing one copy **cannot see the others**. File
boundaries are one cause of that and not the interesting one. Chris: *"relational notes do
do something in the same file, if they span enough distance, or the connection isn't
obvious."*

**Two independent triggers, either sufficient:**

**DISTANCE.** This repo's median module is 209 lines. Two sites further apart than that are
as hidden from one another as two sites in different files — you cannot hold both ends at
once either way. Measured: `RNJB6JXD` puts its two sites **1,271 lines apart inside a single
file** (`jobs/phase_runner.py`), and `RNF2RCXP` spans 473 lines inside `core/capabilities.py`
*as well as* reaching four files.

**NON-OBVIOUSNESS.** Two things that look unrelated and must nevertheless agree are invisible
at any distance, including twelve lines. This is not measurable — no tool can score whether a
relationship reads as obvious — so it is found only by reading, and an `RN` is the only place
it can be written down once found.

⚠ **Do not classify an `RN` by how many files it touches.** A single-file `RN` is not weak;
a single-file `RN` whose sites are adjacent *and* whose connection is self-evident might be.
Only the second of those is checkable.

**Why this class carries more weight than `IN`.** An invariant fails LOUD — a defended one
has a test that goes red. A replica fails SILENT: change one copy, its own tests still pass,
and the two now disagree with everything green. Nine of the thirty `RN`s span the
Python↔JavaScript boundary (e.g. `profiles/manager.py` ↔ `src/state/run-profiles.js`), where
there is no shared import, no shared type, no shared test and no compiler. For those, the
anchor is not documentation of the constraint — **it is the only mechanism that knows the
constraint exists.**

**And it is the tax on small files.** One-thing-per-file shrinks the mental model at each
site by pushing shared rules outward, converting a local problem you can see into a
distributed one you cannot. `RN` is what makes that trade payable.

## Definitions and references

A notation has one authoritative definition and may have arbitrarily many references.

For example:

```text
# definition
# anchor: IN5C9V2R
```

may be cited from several places:

```text
docs/design/entity-resolution.md -> manager.py#IN5C9V2R
docs/testing/resolution.md        -> manager.py#IN5C9V2R
tests/...                         -> IN5C9V2R
```

Multiple references are expected.

Multiple **definitions** of the same anchor are an error.

The distinction is fundamental:

> **Definitions are unique; references are many.**

## Citation form

Where location matters, a citation may include both path and anchor:

```text
path/to/file.py#IN5C9V2R
```

The path is useful routing information. The anchor is identity.

This allows the checker to distinguish different failures.

If the anchor no longer exists anywhere:

```text
BROKEN: path/to/file.py#IN5C9V2R
```

If the anchor still exists but moved:

```text
MOVED:
  path/to/old_file.py#IN5C9V2R
  -> path/to/new_file.py#IN5C9V2R
```

Movement is therefore **not semantic breakage**, but the citation is still stale and should be repaired.

The checker must not silently resolve the moved anchor and declare the original citation valid. The path asserted something that is no longer true.

## Validation rules

At minimum, tooling should enforce:

- every definition has a valid eight-character identifier;
- notation prefixes are registered classes;
- every defined anchor is globally unique;
- duplicate definitions are hard failures;
- referenced anchors exist;
- references containing a path point to the file currently defining that anchor;
- anchors found elsewhere are reported as `MOVED`, including the new location;
- truly absent anchors are reported as broken/orphaned;
- minting retries collisions;
- validation never changes an existing identifier.

Individual notation classes may later impose stronger rules.

For example, an `IN` anchor may eventually require both prose describing the invariant and at least one enforcement or test site. An `SN` anchor may require an entry in the semantic trace catalog. A `PN` anchor may require exactly one canonical design definition.

Those constraints belong to the notation type, not to the opaque suffix.

## Grep remains the primitive

The notation system must remain useful even if all supporting tooling disappears.

Given:

```text
IN5C9V2R
```

the universal recovery operation is simply:

```bash
rg IN5C9V2R
```

That should reveal the definition and every textual reference.

Tooling may make this more convenient:

```bash
python scripts/doc_anchor.py --show IN5C9V2R
```

could display the authoritative definition, citations, and surrounding context together.

But `--show` is convenience.

**The literal identifier is the infrastructure.**

## Drift-review purpose

Notation anchors create a cheap semantic comparison seam.

An auditor can search one identifier and place beside each other:

- the current code;
- the current design prose;
- the invariant it claims to preserve;
- runtime semantic traces;
- historical explanations;
- tests and enforcement sites.

The anchor does not claim those artifacts still agree.

It makes disagreement easy to discover.

That distinction is intentional.

```text
prefix             = relationship type
opaque suffix      = permanent identity
descriptive name   = current taxonomy
prose              = claimed meaning
code               = current implementation
tests              = enforced expectation
history            = why it became this way
```

A descriptive name can become obsolete while still sounding authoritative.

An opaque notation cannot.

It can only continue to point at the lineage it was assigned to, making semantic drift something that can be inspected rather than rediscovered.
