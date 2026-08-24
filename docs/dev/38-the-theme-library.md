# 38 — The Theme Library

**Scope.** The backend half of theming: the one subtree it owns outright, the notification channel
that carries two scopes in one argument, why deleting a bundled theme needs a tombstone, and which
tags are stored versus derived. The card's token system and authoring UI are under
[frontend/](frontend/theme-system.md).

`themes/manager.py::ThemeManager` is one of the three subsystems constructed without a reference to
the manager ([33 §1](33-the-orchestrator.md)) — it receives the root data dict and reads and writes
its own subtree in place, with no storage handle of its own. That narrow construction is why it
also owns its own callback list rather than borrowing the manager's.

---

## 1. One callback, two scopes, distinguished by nullability

Subscribers register through `themes/manager.py::register_update_callback` with a callable taking a
single `vacuum_entity_id` argument, and the **argument's nullability is the scope**:

| value | means | examples |
|---|---|---|
| `None` | a library-wide mutation | rename, delete, import |
| a vacuum id | a per-vacuum mutation | save-as-new, set-active, update-draft, revert |

One channel serving both avoids the alternative — two lists, two registrations, and a subscriber
that must remember to join both to stay correct. The cost is that every subscriber has to handle
`None`, which is visible in the signature rather than buried in a convention.

The sensor platform uses this to push state writes rather than poll.

---

## 2. Preloaded themes are re-seeded on every construction, so a delete needs a tombstone

`themes/preloaded.py::ensure_preloaded_theme_library` runs at construction and adds every built-in
spec id not currently in the library. That is what makes a new built-in theme appear on upgrade
without a migration.

It is also what made deleting one impossible. A user removing a bundled theme saw it go — and it
came back on the next restart, because the seeder could not distinguish *never installed* from
*deliberately removed*.

`themes/manager.py::delete_theme` therefore records a **tombstone** for a bundled theme, which the
seeder consults. The general shape is worth carrying: **any seeder that fills gaps needs to know
the difference between a gap and a decision**, and absence alone cannot carry that.

A user-created theme needs no tombstone — nothing would re-add it.

---

## 3. Stored tags and derived tags

Only the **user-owned vibe tags** live in the library entry. The facet tags — mode, accent and the
rest — along with colorblind-safety, are **derived from the palette** and verified by the card, and
never stored at all.

That split is a security property as much as a design one: a derived facet cannot be hand-set or
spoofed by writing it into storage, because nothing reads it from there. A theme claiming to be
colorblind-safe is checked against its own colours every time it is displayed, not trusted from a
field somebody could set.

---

## 4. The cleaner is format-only, and the vocabulary lives in the card

`themes/manager.py::_clean_theme_tags` trims, lowercases, de-duplicates and caps. It does **not**
strip system words like *dark* or *core*.

That is deliberate: the system vocabulary lives in the card, so stripping here would put a second
copy of it in the backend, and the two would drift. A stored system word is simply **ignored at
display time rather than rejected at write time** — which keeps the vocabulary single-sourced and
means adding a system word does not require a migration over stored tags.

The general rule: when a vocabulary belongs to the display layer, validate *format* at the
boundary and let *meaning* be resolved where the vocabulary lives.

---

## 5. The cleaner discards silently and still reports success

`_clean_theme_tags` drops a tag that is empty, duplicate, or longer than the length limit, and used
to stop entirely once the count limit was reached. `themes/manager.py::set_theme_tags` then returned
a success response that said nothing about any of it.

A caller submitting twenty tags and a caller submitting sixteen got **byte-identical responses**.
There was no field for what was dropped, so the card could not tell the user their last four tags
did not save, and an automation could not detect it at all. This is the shape
[36 §3](36-the-service-layer.md) names as the bug in its three-way choice: *a mutation either
refuses with a reason or succeeds carrying what it applied*, and quietly applying a subset is the
third thing.

The limits stay — they exist to keep stored entries small and clean, and they are defensible. What
was missing was the report, so the response now carries it:
`themes/manager.py::_clean_theme_tags_with_report` returns the dropped tags alongside the kept ones,
and `set_theme_tags` publishes `tags` (what was applied) plus `dropped_tags`, each entry naming the
offending value and a reason — `limit_reached`, `too_long`, `duplicate`, `empty`. Four different
things to tell a user, so they stay four different slugs.

Two details are deliberate. The reasons are **slugs, not prose**: the caller formats them, so this
adds no user-facing string and no new key to the eighteen locale files. And `dropped_tags` is
**absent** rather than empty on a clean submission, so its presence is a reliable signal — a field
that is always there and usually empty gets read as noise and stops being checked. The cleaner also
no longer stops at the cap; it keeps walking so it can report the remainder, which is the whole
point of *you sent twenty and sixteen were kept*.

The related phantom-draft finding on this subsystem **has** been closed, and closed in the right
place: per-vacuum draft state used to be created for any well-formed entity id, so a theme service
would return success for a vacuum that did not exist and persist a record nothing could reach.
`themes/services.py` now calls `services/_common.py::require_managed_vacuum` at six sites. The
accessor still creates defaults when absent — correctly, since the guard belongs at the boundary
rather than in every reader.

> The invariant block in this module is explicit that its entries record which **rule** a finding
> produced and say nothing about whether it is fixed. Both findings above were re-checked against
> the code rather than read off that list.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| theme callbacks need a vacuum | `None` is the library-wide scope and every subscriber must handle it — §1 |
| deleting a built-in theme removes it | without a tombstone the seeder re-adds it on the next restart — §2 |
| a theme's facet tags are stored | they are derived from the palette every time and cannot be spoofed — §3 |
| the backend validates tag vocabulary | it validates format only; meaning is resolved in the card — §4 |
| a successful tag write saved every tag | over-limit and duplicate tags are dropped silently — §5 |
| the invariant block's entries are closed findings | it says outright that it records rules, not closure — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
