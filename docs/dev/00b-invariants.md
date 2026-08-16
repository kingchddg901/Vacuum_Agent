# 00b — Invariant Registry

> **Scope:** every system-wide rule that must remain true, in the shortest form that
> answers *"does my change violate something?"* — and nothing more. The explanation lives
> elsewhere and is linked.

---

## What this is for

During a review or an audit you do not want three pages of subsystem history to find out
whether a change crosses a line. You want **the rule first**, in a sentence. Only if the
change gets near that boundary do you follow the pointer and load the expensive context.

So this file and the design docs are **not competing documents**. They are two indexes into
the same truth at different levels of abstraction — the distinction [00 §8](00-documentation-standard.md)
draws between duplicate *truth* and duplicate *cognition*:

| | Answers | Cost to read |
|---|---|---|
| **This registry** | *What must remain true?* | Seconds |
| **The linked design / subsystem section** | *Why does this rule exist, what failure created it, what breaks without it?* | Minutes |
| **The enforcement site in source** | *Where is it actually held?* | Whatever it takes |

This is deliberate duplication and it is allowed, because the second representation buys
comprehension rather than repeating it. A registry entry that tries to teach the whole
system has failed at its one job.

---

## How an entry works

Each invariant owns a **notation anchor** (`IN` + six Crockford characters — see
[design/shipped/notation-anchors.md](design/shipped/notation-anchors.md)). The anchor is a
permanent identity that carries no meaning, so the rule's wording, its explanation, and its
enforcement sites can all move underneath it without the identity changing.

```
IN<token> — <the rule, in one sentence, with its consequence>
   Why:      <link to the design or subsystem section that explains it>
   Enforced: <the site(s) that hold it>
   Cite:     any code site that takes the same dependency
```

Mint with `python scripts/doc_anchor.py --mint IN`. `--check` verifies every cited anchor
resolves; `--orphans` finds anchors nothing references.

> **An invariant states a rule AND its consequence** — "do this, or this happens"
> ([00 §1.2](00-documentation-standard.md)). If you cannot name what goes wrong, you have a
> convention, not an invariant, and it does not belong here.

---

## The registry

### `INKR1TW7` — an operation that reads another integration's entities must not assume they exist during setup

Defer it to `async_at_started`, or tolerate late availability. Otherwise it reads an empty
registry and a stateless vacuum, **caches that answer, and never looks again** — so a
restart repeats the race rather than repairing it.

- **Why:** [02 — HA integration](02-ha-integration.md); the failure is recorded at the
  anchor site itself in `custom_components/eufy_vacuum/__init__.py#INKR1TW7`.
- **Enforced:** the post-start re-detection hook in `__init__.py`, which re-runs brand
  registration and `refresh_vacuum_capabilities` once HA has started, writing only on change.
- **Cite `INKR1TW7`** from any site taking the same dependency.

> The instructive part is that **nobody lacked the knowledge**.
> `_schedule_vocabulary_migration` in the same file states the constraint correctly — that
> adapters "are registered from vacuum entities owned by OTHER integrations" which "on a
> cold boot often have not" set up. That was true of adapter registration itself and was
> never applied to it. A local comment is not a system property. This registry is what
> makes it one; before it existed, the anchor was a comment with an ID.

---

## Not yet registered

Rules that behave like invariants and are currently held only in prose or in a single
subsystem doc. Each needs a consequence stated before it earns an entry.

- **Eufy is not the default.** Core owns keys, never a brand's words; a fallback yielding a
  brand's vocabulary is the bug. Partly enforced since brand identity became data
  ([21 §6.1](21-adapter-system.md)), but `EufyBrandFacts` still names a brand in core.
- **Never edit `.storage` directly** — HA rewrites it on shutdown and the change becomes a
  `.corrupt` backup.
- **A service call moves real hardware.** Anything reachable from a doc, a test, or an
  agent must not dispatch one incidentally.
- **The card is a glance surface**; deep analysis belongs in the CSV export.

Adding one is cheap: mint an anchor, write the rule and its consequence, link the
explanation, name the enforcement site. Leaving one here is also fine — an unregistered
rule is honest; a registered rule with no consequence is not.
