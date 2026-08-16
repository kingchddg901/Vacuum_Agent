# Notation Anchors

> **Status: SPECIFICATION — partially built.** `CN` in use (9 anchors), `IN` in use
> (1, indexed by [00b](../../00b-invariants.md)), `RN` in use (2, indexed by
> [00c](../../00c-replicas.md)). `SN`, `HN` and `PN` remain reserved and unused. Tooling: `scripts/doc_anchor.py`
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
PN  deep prose/design
IN  invariant
RN  replica set — one rule, several deliberate copies
```

`RN` was added 2026-08-16. Its shape differs from the others in one way worth stating: an
`RN` is inherently multi-site, but the scheme's rule is *definitions are unique, references
are many*. So an `RN` is declared once at the set's natural primary — the shared artifact
the copies revolve around, or the copy carrying the reasoning — and referenced from every
other member. The listing of sets lives in [00c](../../00c-replicas.md); the declaration
cannot, because declarations are scanned in source only.

This makes the prefix function as a small type system for repository knowledge rather than as a filing scheme.

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
