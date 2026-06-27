# Proposal: context-scoped locale authoring (nested + fallback → flat runtime)

Status: **DRAFT for review** (pre-code). If approved this moves into `docs/dev/`.

## 1. Why — and what the data actually says

Measured against the live English source (`src/i18n/en.js`):

| Metric | Value |
|---|---|
| Total keys | 1373 (1336 string, 37 plural) |
| Distinct leaf names | 1219 |
| Key depth | 1237 at 2 segments, 96 at 3, 40 at 4 |
| Biggest sections | map 204, metrics 150, theme_preview 137, rooms 93, maintenance 78, learning 70 |
| **Exact-duplicate values** | 96 distinct values across 241 keys |
| **Collapsible surplus (dedup)** | **145 keys (~11%)**, of which **134 are cross-section** |

The most-repeated values are short nouns/labels: `Rooms` ×8, `Room` ×8, `Unknown` ×7, `Profile` ×6, `Excluded` ×5, `Vacuum`/`Water`/`Mode`/`Default`/`Status`/`Filters` ×3-4.

**The finding that reframes this:** the strings that dedupe are exactly the strings most likely to need *different* translations per context — `Room` (Raum vs Zimmer), `Filters` (dock part vs metrics control), `Mode`/`Default`/`Status` (gender/agreement). So:

- Pure dedup saves only ~11%, and concentrated in the **riskiest** strings to blindly share.
- Therefore the real value of this structure is **NOT** "less work." It is:
  1. **Organization** — translators work tab-by-tab; a nested `maintenance.*` view beats 78 alpha-sorted flat keys.
  2. **Clean per-context divergence** — make `Room` translate differently in each tab *on purpose*, safely.
  3. **The authoring format for drop-in + de-bundling** — the same nested shape feeds drop-in files and the eventual extraction of locales out of the minified bundle.
  
  Dedup is a real-but-secondary bonus.

This validates the earlier caveat: a commons + fallback model is correct **only because override exists**, and the high-frequency shared nouns are precisely why the fall-through must be **visible** to translators.

## 2. The format (authoring / file shape)

Nested by the existing prefixes; `commons` holds the true-shared leaves.

```jsonc
{
  "commons": {                     // "true commons" — shared leaves
    "save": "Save", "cancel": "Cancel", "room": "Room", "unknown": "Unknown"
  },
  "rooms": {                       // a tab (mirrors today's "rooms.*")
    "empty": "No rooms yet — …",   // section-scoped leaf
    "room": "Room"                 // OVERRIDE of commons.room for this tab (if a lang needs it)
  },
  "maintenance": {
    "schedule": {                  // a subtab/sub-scope
      "save": "Save schedule"      // overrides commons.save only inside maintenance.schedule
    }
  }
}
```

- A **section** is an object keyed by arbitrary names.
- A **leaf** value is a string, or — for a plural key — an object of CLDR forms.
- `commons` is just the top scope every leaf can fall back to.
- **Flat is a valid degenerate case** (no nesting, no commons) → existing flat locales keep loading unchanged. Backward compatible.

## 3. Resolution (flatten against the English manifest)

`en.js` stays **flat** and is the **manifest** (the complete key set + the final fallback). A nested locale is *flattened* to the flat catalog the runtime already uses. For each flat key `K = s1.s2…sL` (leaf `sL`):

```
1. Most-specific first: for depth i = L-1 … 1, look at the node reached by s1…si;
   if it has `sL` as a LEAF (string, or a plural-object), use it.
2. Else commons[sL] if present.
3. Else en[K]  (English — untranslated).
```

So a leaf placed at any ancestor scope applies to all descendants; `commons` is the global default; English is the floor. The flatten output is **exactly the en key set**, so `check-i18n` parity/orphan checks and `validateLocale` run on it unchanged. Orphan nested entries (no matching en key) are simply never hit.

Pipeline becomes: parse JSON → **flatten(nested, enManifest)** → `validateLocale` (whitelist + escape) → `registerLocale`. One new pre-step; everything downstream identical.

## 4. Plural disambiguation

At a node, `node[leaf]` can be a string (leaf), a **plural-object** (leaf), or a **section** (deeper scope). Rule:

> An object is a **plural leaf** iff every key ∈ {`zero`,`one`,`two`,`few`,`many`,`other`}. Otherwise it is a section.

Matches the existing plural detection. (Optional belt-and-suspenders: a reserved `"$plural": true` marker; not needed if the CLDR-key rule holds, which it does for all 37 current plural keys.)

## 5. Runtime is UNCHANGED

- `translate()` and all ~1336 call sites stay flat-keyed (`t("rooms.empty")`) — no context threading, no hot-path walk.
- Flatten runs at **author/build/load time**, not per-render.
- `en.js` is untouched (flat manifest).
- Bundled non-English locales + drop-in files may be authored nested; both flatten the same way.

This is the deliberate trade vs. runtime hierarchy-walk: we pay one flatten pass per locale load instead of a scope walk on every string, and we avoid editing 1336 call sites.

## 6. The fall-through guard (required, not optional)

Flatten emits a per-locale **coverage report** classifying every key as `explicit` / `inherited-from-commons` / `untranslated (en)`. The translation editor / a lint surfaces the **inherited** set so a translator SEES "`metrics.room` inherited commons 'Raum' — override?" — turning the high-risk shared nouns from a silent trap into a reviewed decision. Without this, dedup quietly degrades quality on exactly the words §1 flagged.

## 7. Migration

- **en**: stays flat. (Optionally also offered as a generated nested `en.template.json` so translators see the structure — ties to the template export already on the table.)
- **Existing bundled locales (de/fr/…)**: keep working as flat. A one-time codemod can *factor* them into nested-deduped form (pull values equal to commons up), but it's optional — flat is valid.
- **Initial nested skeleton**: auto-derived from the existing flat prefixes (group by `s1[.s2]`), so we don't hand-build the tree.
- **New translations** (the T1 set, drop-ins): authored nested from day one.

## 8. Scope / cost / recommendation

New code (all additive; runtime untouched):
1. `flattenLocale(nested, enManifest)` + plural rule + the coverage report — pure function, unit-tested.
2. Wire it into `loadLocale`/`loadDroppedLocales` (pre-step) and the build (for bundled).
3. A `build:locale-template` that emits the nested `en.template.json`.
4. The codemod (optional) + the editor/lint surfacing of `inherited`.

**Recommendation: adopt it — but sell it as organization + safe per-context divergence + the de-bundling/drop-in authoring format, not as a dedup play (dedup is ~11% and on the riskiest strings).** Keep runtime flat, flatten at author time, ship the fall-through report from day one. Decide now: we're about to translate ~1300 keys × several languages, and the file format should be settled before that investment — restructuring after is the expensive path.

**Open question for you:** do we also convert the *existing* bundled de/fr/es/nl/it/pt/ru to nested now (codemod), or leave them flat and only author *new* languages nested? (They interoperate either way.)
