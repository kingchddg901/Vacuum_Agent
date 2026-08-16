# 00c — Replica Sets

> **Scope:** every rule this codebase implements in more than one place **on purpose**, so
> that changing one copy sends you to the others. A listing, not an argument — the
> reasoning lives at the anchor site.

---

## Why this exists rather than a helper

The obvious fix for duplicated logic is to unify it. That is often wrong here: roughly
half the divergence in this repo is deliberate — each copy feeds a different consumer, or
derives its inputs differently, and forcing agreement would force it in cases where the
copies *should* differ. The ladder is `constant > derived > helper > inline exception`,
and the usual target is a helper — but "usual" is not "always".

So a replica set is **coordination without unification**. It does not merge the copies. It
records that they exist, and makes the others findable from any one of them.

**The failure it exists to prevent is specific and has already happened.** A fix landed in
two of three copies of the `translation_key` rescue; **4381 tests passed**, because each
copy carries its own passing tests and a green suite proves only that every copy is
self-consistent with itself. The third was caught by renaming a live vacuum's entities to
German — not by any gate.

> **A green suite cannot see a missing copy.** That is the whole argument for this file.

---

## How a set is recorded

An `RN` notation anchor ([design/shipped/notation-anchors.md](design/shipped/notation-anchors.md))
is **declared once** at the set's natural primary — the shared artifact the copies revolve
around, or the copy whose comment carries the reasoning — and **referenced** from every
other member.

```
# anchor: RNxxxxxx  <what the rule is> — the replica set     ← exactly one
# REPLICA RNxxxxxx — <the twin lives at …>                   ← one per other copy
```

`python scripts/doc_anchor.py --show RNxxxxxx` lists every site. `--check` enforces that
the declaration is unique.

> ⚠ **The declaration must live in SOURCE, not here.** `doc_anchor.py` scans
> `custom_components/`, `scripts/`, `src/` and `harness/` for declarations; documents can
> only *reference*. This file is therefore an index over anchors that live in code — the
> same relationship [00b](00b-invariants.md) has with its invariants.

Mint with `python scripts/doc_anchor.py --mint RN`.

---

## The sets

### `RNF2RCXP` — `translation_key` rescue · **3 copies**

The rescue function is shared; **the decision to call it is written out three times**, and
that decision is what must agree.

| Copy | Feeds |
|---|---|
| `entity_resolve.resolve_declared_entities` | the adapter's declared `entities` map |
| `capabilities._rescue_maintenance_source` | maintenance sources |
| `capabilities.augment_candidates_from_device` | the roles `detect_capabilities` probes |

Not unified because each takes its wanted-key from a different place and feeds a different
consumer. **Declared at** `adapters/entity_resolve.py::rescue_by_translation_key`.

*History: `ef810519` fixed two; `35ce560f` fixed the third, ten hours later.*

### `RNZM4AYY` — longest-suffix ownership test · **2 copies**

The rule that the longest declared suffix claims a sibling exclusively, so `_cleaning_area`
cannot swallow `_total_cleaning_area`.

| Copy | Applies to |
|---|---|
| `entity_resolve.py` (inside `resolve_declared_entities`) | the declared entity map |
| `capabilities.py` (inside `augment_candidates_from_device`) | the probe candidate lists |

If they disagree, a role resolves one way through the declared map and another through the
probe — and the wrong one binds a **lifetime counter** where a per-run value belongs. On
live hardware that is 2.9 m² against 11,814 m², and nothing throws.

**Declared at** `adapters/entity_resolve.py` (the copy whose comment carries the reasoning).

---

## Candidates — not yet recorded

Suspected replica sets. Each needs confirming as *deliberate* before it earns an anchor;
an accidental duplicate wants a helper, not an entry here.

- **`reserved_suffixes` at the capability probe** — both adapters pass `ALL_SUFFIXES`
  (`CN2X0DN6` Eufy, `CNXD5V8Q` Roborock). Two anchors already, and no link between them:
  the sibling problem surviving inside the scheme meant to fix it.
- **Brand vocabulary tables** — every adapter declares its own state sets. Almost certainly
  correct divergence rather than a replica set, but unverified.

Adding one is cheap. Leaving one here is also fine — a listed candidate is honest; an
anchored set nobody verified is not.
