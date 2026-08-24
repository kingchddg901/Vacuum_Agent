# 45 — The Shared Layer

**Scope.** The four modules almost everything else imports: the constants, the data shapes, the map
bucket helpers, and the one surface a user can extend by dropping files on disk. Three of them are
the oldest code in the tree, and §4 measures how much of it never moved.

---

## 1. `const.py` is imported by fifty-eight modules and re-exports a brand's

`const.py` holds around 140 names — the domain, the runtime data keys, and the service-name
constants every handler and every test refers to. Fifty-eight modules import it, which makes it the
single widest dependency in the tree.

⚠ **It does not define the integration's identity. It re-exports it from the Eufy package.** The
domain, product name, version, default title and the tested-model default all come from
`adapters/eufy/const.py`, on the original reasoning that porting to another ecosystem would mean
changing one file.

[23 §2](23-eufy-adapter.md) covers what that costs from the adapter side — six constants that are
the *integration's* identity filed under a brand folder, one of which is the config flow's default
on a Roborock-only install. What is worth adding here is the **blast radius**: this is the module
fifty-eight others import, so the brand's name reaches almost everything by a path no import-graph
check would flag as brand coupling. The file's own note says this will be addressed in a later
pass, and it is still the arrangement.

---

## 2. Two shape vocabularies, split by age

`models/models.py` carries both frozen dataclasses and TypedDicts, and the split is chronological
rather than principled:

| shape | used for |
|---|---|
| dataclasses — `models/models.py::RoomConfig`, `models/models.py::MapConfig`, `models/models.py::VacuumRuntimeState` | the original room and map model |
| TypedDicts — `models/models.py::RoomRecord`, `models/models.py::RuleDefinition`, the theme and rule entries | everything added since |

The dataclasses come from the first integration and describe objects the code constructs. The
TypedDicts describe **shapes that already exist in the store** and are annotated after the fact —
which is the right tool for a dict that was persisted before it was typed, and the wrong tool for a
value you want validated on construction.

A reader should not infer a design rule from which one a shape uses. The question to ask is whether
anything constructs it.

---

## 3. `ensure` and `require`, the distinction arrived at four times

`maps/map_manager.py::ensure_map_bucket` creates the bucket if it is missing.
`maps/map_manager.py::require_map_bucket` returns the existing one or **nothing**.

The second exists because the first is the wrong primitive for an **addressed write**. A mapping
service handler that writes against a caller-supplied map id — rename a saved zone, delete custom
segments — must refuse an unknown address rather than mint a phantom durable bucket for it.
`ensure`'s unconditional create means a typo'd or never-discovered map id silently becomes a real,
persisted bucket.

**This is the fourth independent arrival at the same rule**, and the pattern is worth naming
because each site found it separately:

| site | the phantom |
|---|---|
| [36 §3](36-the-service-layer.md) | a write for a vacuum this integration does not manage |
| [38 §5](38-the-theme-library.md) | per-vacuum theme draft state for any well-formed entity id |
| [44 §2](44-onboarding-and-first-run.md) | an onboarding read that created the record it reported |
| here | a map bucket for a map id nobody ever discovered |

The general rule: **a create-if-missing accessor is correct for state you own and wrong for state
the caller addresses.** When the identifier comes from outside, existence is a question, and an
accessor that cannot answer *no* has removed the question rather than answered it.

`maps/map_manager.py::known_map_ids` and `maps/map_manager.py::map_ids_with_rooms` are the read-side
counterparts — enumerating what exists rather than asking about one address.

---

## 4. What survived

These two modules are direct descendants of the first integration, and the comparison against that
snapshot is the closest thing to a verdict on its data model.

| | then | now | survived |
|---|---|---|---|
| `maps/map_manager.py` | 5 functions | 8 | **all five original names** |
| `models/models.py` | 4 dataclasses | 3 + 8 TypedDicts | **three of four** |

Every function the first map manager had is still called by its original name 143 days later, and
the three additions are all read-side or refusal helpers rather than replacements. The one model
class that did not survive is the capability record — and it did not die, it **moved**: capability
detection became `core/capabilities.py` and returns a dict shaped by the probe rather than a
dataclass shaped in advance ([34](34-capability-detection.md)).

That is the useful reading of the whole comparison. The shapes that describe **stored user data**
were right the first night and have not needed to change. The shape that described a **derived
answer** was replaced the moment the derivation got interesting.

---

## 5. Drop-in fonts: the one surface a user extends with files

`user_fonts.py::build_catalog` scans a fonts directory where each subdirectory holds a descriptor
beside its woff2 files — and its licence, which travels with the font rather than being catalogued
separately.

`user_fonts.py::validate_descriptor` checks the descriptor, but the interesting step is
`user_fonts.py::locale_char_requirements` and the codepoint read beside it: which locales a font can
actually render is **derived from the font's own character map**, compared against the codepoints
the shipped locale files actually use.

That is the difference between a font *claiming* to support a language and a font *containing* the
characters that language needs. A declared list would be a promise the author makes; a cmap
intersection is a measurement — and it is checked against the strings this product actually ships,
not against the language in general, so a font passes if it can render what will be asked of it.

For an accessibility font in particular, the failure mode this prevents is silent: a missing glyph
renders as a fallback box in one language and nowhere else, on someone else's install.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| `const.py` defines the integration's identity | it re-exports it from the brand package, to fifty-eight importers — §1 |
| the dataclass/TypedDict split is a design rule | it is chronological: constructed objects versus shapes annotated after the fact — §2 |
| `ensure_map_bucket` is the accessor to use | for a caller-supplied map id it mints a phantom; `require_map_bucket` is the addressed-write form — §3 |
| the original data model was provisional | every map-manager function name and three of four model classes are still here — §4 |
| the capability dataclass was dropped | it moved to a probe that returns a dict, because the answer became derived — §4 |
| a font declares which languages it supports | support is measured from its character map against the strings this product ships — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
