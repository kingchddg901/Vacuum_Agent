# Theme System

The eufy_vacuum Lovelace card ships a fully independent per-card theming layer. Themes are not HA global themes — they are token dictionaries stored in the integration and applied directly to the card's shadow DOM.

Every token in the registry is a CSS custom property. When a theme is active the card injects each property as an inline style on the card host element. The integration is always the source of truth: the card never persists theme state itself.

---

## 1. Overview

### What the theme system is

The theme system provides per-vacuum, per-card visual theming that is completely independent of Home Assistant's own theme mechanism. Themes are stored in integration persistent storage and surfaced to the card through a dedicated HA sensor. The card reads from that sensor, resolves the effective token values, and applies them as CSS custom properties to its own shadow DOM.

### Why it exists

HA global themes apply to the whole UI and cannot target individual custom elements inside a shadow root. The eufy_vacuum card needs precise visual control — surface layers, floor texture tuning, semantic status colors, modal overlays — without polluting the global HA palette. The `--evcc-` CSS custom property namespace keeps every variable isolated to the card and prevents collisions with HA or other cards.

### The working draft / active theme model

At any given time, each vacuum has:

- An **active theme** — the persisted, named theme entry in the library that is the current baseline.
- A **working draft** — a per-vacuum overlay of token overrides sitting on top of the active theme. The draft exists in memory and in storage but has no name and has not been promoted to the library.

The card renders using the _resolved_ result of merging active theme + working draft. The draft is cleared when the user saves, reverts, or switches themes.

---

## 2. Token Architecture

### The 18 token groups

Groups are editor-only metadata. They organize the token editor UI and have no effect on backend persistence, which remains a flat dictionary.

| Group | Purpose |
|---|---|
| **App Shell & Typography** | Top-level accent, primary/secondary/muted text, and global border color |
| **Cards & Surfaces** | Background and surface layer colors for the main card and its panels |
| **Borders & Shadows** | Border colors at three strengths (subtle / default / strong) and box shadows |
| **Chips** | Background and text colors for the chip/badge controls |
| **Room Cards** | Background, text, and accent colors specific to the room card components |
| **Floor Textures** | Global master enable (0/1) and global opacity for card and map texture rendering |
| **Floor Textures — Tile** | Per-material color and per-layer opacity for the tile texture |
| **Floor Textures — Wood** | Per-material color and per-layer opacity for the wood texture |
| **Floor Textures — Marble** | Marble color/opacity plus a two-tier vein system: a master vein opacity/blur that rides both tiers, per-tier (major/minor) opacity + blur offsets that preserve the delta, and minor-vein color deltas (lighten / saturation / hue) for an atmospheric recede |
| **Floor Textures — Concrete** | Per-material color and per-layer opacity for the concrete texture |
| **Floor Textures — Carpet Low** | Per-material color and per-layer opacity for the low-pile carpet texture |
| **Floor Textures — Carpet High** | Per-material color and per-layer opacity for the high-pile carpet texture |
| **Floor Textures — Granite** | Per-material color and per-layer opacity for the granite texture |
| **Queue & Ordering** | Colors for the room-queue priority and ordering UI |
| **Status, Confidence & Alerts** | Semantic colors (success / warning / error / info) and confidence indicator fills |
| **Learning & Metrics** | Background gradients for the learning confidence tiles (high / medium / low / neutral) |
| **Modals & Overlays** | Background, border, backdrop, and padding values for the modal layer |
| **Shared Foundations** | Spacing, radius, typography, and motion primitives shared across all components |

### Token object shape

Every token in the registry has these four required fields:

```js
{
  key:   "--evcc-accent",   // CSS custom property name (string, always --evcc- prefixed)
  label: "Accent",          // Human-readable name shown in the editor (string)
  group: "App Shell & Typography", // Editor group (string, must be a THEME_GROUPS entry)
  type:  "color",           // Token type (string, see below)
}
```

`key`, `label`, `group`, and `type` are the stable required fields. Bounded-scalar tokens also carry **optional editor-only `min` / `max` / `step`** range metadata (see "Bounded-scalar ranges" below). These are *not* persisted — only token values persist, flat — and one definition drives both the editor slider and the import clamp. The search system also looks at `aliases`, `usage`, and `affects` arrays if they are present, but those are schema-forward placeholders not yet populated.

Labels are auto-derived from the key by `makeTokenLabel()` (strips `--evcc-`, converts hyphens to spaces, title-cases) unless an explicit label string is passed to the factory.

### Token types

The full type vocabulary, defined in `helpers.js`:

| Type | What it controls |
|---|---|
| `color` | A color value — hex, CSS color-mix expression, named color, or var() reference. Rendered as a color picker + text input pair with an alpha slider. |
| `text` | An arbitrary CSS text value — used for spacing shorthands like `--evcc-space-sm`. Rendered as a plain text input. |
| `shadow` | A CSS box-shadow value. Rendered as a text input. |
| `size` | A dimensional value with a unit (px, rem, em, %, etc.). Rendered as a range slider + text input pair. |
| `number` | A unitless number (e.g. `0.985` for press scale, `0` or `1` for texture enable flags). Rendered as a range slider + number input pair. |
| `duration` | A CSS time value (ms or s) for animation durations. Rendered as a range slider + text input pair. |
| `motion` | A CSS translate/transform value (e.g. `-1px` for hover lift). Rendered as a text input. |
| `typography` | A CSS font-family string. Rendered as a text input. |
| `easing` | A CSS timing function string. Rendered as a text input. |

The editor routes each token to the correct control widget based on its `type`. The `_isScalarThemeType()` binding helper treats `size`, `number`, and `duration` as numeric types that need unit-aware formatting.

### Bounded-scalar ranges (semantic methods)

A bounded scalar's valid range is a property of its KIND, declared once by a semantic helper method rather than hand-authored on every token. Alongside the type methods, `makeTypedGroupToken` (in `helpers.js`) exposes:

| Method | Range | Step | For |
|---|---|---|---|
| `.unit` | 0 … 1 | 0.01 | opacities, alpha, any 0–1 ratio |
| `.blur` | 0 … 8 px | 0.5 | blur radii (never via `.unit` — that would cap blur at 1px) |
| `.angle` | −180 … 180 | 1 | hue shift |
| `.signed` | −1 … 1 | 0.01 | signed deltas (lighten, offset-from-master) |

Each is sugar over `type:"number"` plus the kind's `min`/`max`/`step` (the exported `SCALAR_RANGES` table), and accepts an optional per-token override (a spread-merge of `{min?, max?, step?}`) for the rare exception — e.g. `gm.unit(key, label, { max: 2 })` for a 0–2 multiplier, or `gm.signed(key, label, { min: -8, max: 8, step: 0.5 })` for a px-scaled offset. Bare `.number` stays **rangeless** on purpose: the escape hatch for genuinely unbounded values.

**Single source.** The same `min`/`max` drives the editor slider (`_renderThemeNumericTokenRow` prefers `token.min/max/step` over the per-group `SLIDER_CONFIG` fallback) *and* the import clamp (`clampThemeScalars`), so the editor can never emit a value its own importer would reject. `THEME_TOKEN_TYPES` is unchanged — the methods add no persisted type.

### The `colors` vs `tokens` split

Theme entries — and the working draft — carry two separate dictionaries:

- **`colors`** — stores the raw hex (or CSS expression) value for every color-type token, without any alpha multiplier applied. Example: `"--evcc-accent": "#6AA7FF"`.
- **`tokens`** — the CSS-ready resolved value for every token. For color tokens, this is the hex value with the alpha channel baked in as an 8-character hex string. For non-color tokens, this is the final CSS value string. `tokens` is a superset of `colors`.

**Why two arrays?**

Alpha multipliers are stored as a third separate bucket (`alpha`) as floating-point numbers in the range 0–1. When `resolvedTheme()` runs, it combines `colors[key]` and `alpha[key]` using `_hexWithAlpha()` to produce the final 8-char hex written into `tokens[key]`. Keeping them separate prevents an alpha-only draft change from accidentally overwriting a stored hex color with a computed value that loses precision on round-trip.

**Merge rule:** `tokens` always wins for final CSS application. The `colors` bucket exists so the editor can read back the un-alpha'd hex for a color picker input without having to strip the alpha channel from `tokens`.

**Canonical duplication at save time:** `_build_preloaded_theme_entry()` (and every save path) always writes a color's value into both `colors` and `tokens` so consumers can read from either bucket safely.

### The `--evcc-` prefix convention

Every token key begins with `--evcc-`. This is enforced by convention, not validation. The prefix ensures:

1. No collision with HA's own `--primary-color` / `--card-background-color` / etc. variables.
2. No collision with any other Lovelace card's variables.
3. A clear namespace that the card's CSS uses consistently.

CSS usage in the card's stylesheets references these as `var(--evcc-accent)`, `var(--evcc-surface-base)`, etc. The card provides no fallback to HA global theme variables except where explicitly defined in `MODAL_HOST_STYLES` (see section 4).

### Floor texture sub-groups and nesting

The floor texture tokens are split into eight groups:

- `"Floor Textures"` — the parent group, containing four global master controls (card enable, map enable, card opacity, map opacity).
- `"Floor Textures — Tile"`, `"Floor Textures — Wood"`, etc. — one sub-group per material, each containing color tokens and per-layer opacity tokens for that material.

The `" — "` (em-dash with spaces) separator is meaningful: the group filter logic in `filteredThemeTokens()` uses `group.startsWith(selectedGroupFilter + " — ")` to include sub-groups when the parent group filter is active. Selecting "Floor Textures" in the editor shows all eight sub-groups as a unit.

---

## 3. Backend Storage

### Where themes live in `eufy_vacuum.storage`

Themes are stored inside the integration's persistent storage file (`eufy_vacuum.storage`) under the key path:

```
data.theme
```

The full `theme` object shape:

```json
{
  "library": {
    "<theme_id>": { ... }
  },
  "default_theme_id": "theme_follow_ha",
  "vacuums": {
    "vacuum.alfred": {
      "active_theme_id": "theme_core_slate",
      "working_draft": { "tokens": {}, "colors": {}, "alpha": {} },
      "draft_dirty": false,
      "editor_mode": "live"
    }
  }
}
```

### Theme entry shape

Each entry in `data.theme.library` has this shape:

```json
{
  "id": "theme_20240612T103045123456",
  "name": "My Custom Theme",
  "colors": {
    "--evcc-accent": "#6AA7FF",
    "--evcc-surface-base": "#1B2129"
  },
  "tokens": {
    "--evcc-accent": "#6AA7FFFF",
    "--evcc-surface-base": "#1B2129FF",
    "--evcc-radius-card": "14px",
    "--evcc-font-family": "\"Segoe UI\", system-ui, sans-serif"
  },
  "alpha": {
    "--evcc-accent": 1.0
  }
}
```

User-created themes also carry an `alpha` bucket. Preloaded themes are written with `alpha: {}` because their color tokens already have the full alpha value baked into the 8-char hex in `tokens`.

There is no `created_at` field on theme entries. Theme IDs are timestamp-based (`theme_YYYYMMDDTHHMMSSffffff`) so they sort chronologically by creation time without a separate field.

### Built-in (preloaded) themes vs user-saved themes

Preloaded themes are defined in `PRELOADED_THEME_SPECS` in `themes/preloaded.py` and seeded into storage once during `ThemeManager.__init__()` by `ensure_preloaded_theme_library()`. The current built-in themes are:

| ID | Name |
|---|---|
| `theme_follow_ha` | Follow HA Theme |
| `theme_core_slate` | Core Slate |
| `theme_forest_night` | Forest Night |
| `theme_soft_carbon` | Soft Carbon |
| `theme_warm_light` | Warm Light |
| `theme_high_contrast` | High Contrast |
| `theme_signal` | Signal |

**How they're distinguished:** Preloaded theme IDs use the `theme_` prefix followed by a short slug (e.g. `theme_core_slate`). User-saved themes use the `theme_` prefix followed by a timestamp (e.g. `theme_20240612T103045123456`). There is no explicit `is_preloaded` flag.

**Why preloaded themes can't be deleted or overwritten in the normal workflow:** The seeding logic in `ensure_preloaded_theme_library()` only adds an entry if the ID is not already present. If a user deletes or overwrites `theme_core_slate` through the service layer (there is no guard in `delete_theme()` preventing it), the original value will be gone until the next HA restart re-seeds it. The card UI should prevent this at the UI layer, but the backend does not enforce it.

**The `theme_follow_ha` default:** If `default_theme_id` is missing or points to a nonexistent entry, it is reset to `theme_follow_ha` at seeding time. `theme_follow_ha` has empty `colors` and `tokens`, which means no `--evcc-` variables are injected — the card's CSS falls through to its static defaults.

### The working draft

The working draft is stored per-vacuum at `data.theme.vacuums.<vacuum_entity_id>.working_draft`:

```json
{
  "tokens": { "--evcc-accent": "#FF7B5A" },
  "colors": { "--evcc-accent": "#FF7B5A" },
  "alpha": { "--evcc-accent": 0.9 }
}
```

The draft uses the same three-bucket shape as a theme entry. Null or empty-string values in the draft mean "remove this override, fall back to the active theme value". The manager's `update_working_draft()` method applies these as a patch-merge: `None` or `""` values pop the key from the bucket, non-null values set it.

`draft_dirty` is `True` when any of the three buckets is non-empty.

### `resolvedTheme()` — the merge algorithm

The card's `resolvedTheme()` method in `state/theme.js` builds the final token map used for CSS injection:

1. **Base — active theme:** iterate `activeTheme.colors` → populate `colorMap`; iterate `activeTheme.alpha` → populate `alphaMap`; iterate `activeTheme.tokens` → populate `tokens`. All sources tagged `"theme"`.

2. **Overlay — working draft:** iterate `workingDraft.colors` → overwrite `colorMap`; iterate `workingDraft.alpha` → overwrite `alphaMap`; iterate `workingDraft.tokens` → overwrite `tokens`. All sources tagged `"draft"`.

3. **Combine color + alpha:** for every key in `colorMap`, call `_hexWithAlpha(colorHex, alphaMap[key])`. The result (an 8-char hex or the original value unchanged if it is not a valid hex) is written back into `tokens[key]`, overwriting any pre-baked value from step 1 or 2. This ensures an alpha-only draft change reflects correctly even when the color came from the theme base.

Return value: `{ tokens, sources }` where `sources[key]` is `"theme"`, `"draft"`, or absent (key not in any bucket).

The `sources` map is used by the editor to mark tokens as draft-modified (the "modified" badge and filter chip).

---

## 4. CSS Bridge

### `applyThemeToCard()`

`applyThemeToCard(card)` in `src/styles/apply-theme.js` is the outermost bridge. It:

1. Calls `card._state.resolvedTheme()` to get the current merged token map.
2. Calls `applyDynamicTheme(card, resolved)` to write the variables onto the card host element.
3. If `card._modalHost` exists and is still attached to the document body, calls `applyDynamicTheme(card._modalHost, resolved)` to bridge the same variables onto the external modal host node.

This function is called from every place that could change the visible theme: token edits, alpha edits, color-mix edits, preset activation, draft revert, group resets, and the backend refresh helper.

### `applyDynamicTheme()`

`applyDynamicTheme(target, resolvedTheme)` in `src/styles/index.js` does the actual DOM mutation:

1. Iterates `THEME_TOKEN_REGISTRY` and calls `host.style.removeProperty(token.key)` for any token whose key is absent, null, undefined, or empty-string in `resolvedTheme.tokens`. This ensures stale values from a previous draft do not persist after a reset.
2. Iterates `Object.entries(resolvedTheme.tokens)` and calls `host.style.setProperty(property, value)` for every non-empty value.

The target is the element itself (`host.style`), not the shadow root's stylesheet. This works because `--evcc-` variables declared on the host element cascade into the shadow root — shadow DOM inherits custom properties from the host.

### Shadow DOM isolation and `MODAL_HOST_STYLES`

The card renders inside a shadow root. Shadow DOM inherits CSS custom properties from the host element through the cascade, which is why injecting `--evcc-*` onto the card host element is sufficient for everything inside the shadow root.

Modals are a special case. They render in a `div` appended to `document.body` outside any shadow root, so they cannot inherit from the card host. Two things address this:

**1. `applyDynamicTheme()` on the modal host.** `applyThemeToCard()` also calls `applyDynamicTheme(card._modalHost, resolved)` so the same set of `--evcc-*` inline properties is declared on the modal host `div`. The modal's own content inherits from that host `div`.

**2. `MODAL_HOST_STYLES`.** The modal host has its own `<style>` element with `MODAL_HOST_STYLES` injected. This stylesheet declares every CSS rule the modal content needs (resets, button normalization, layout, typography) without relying on shadow root encapsulation. It also references `--evcc-*` properties via `var()` so those rules pick up the token values injected by `applyDynamicTheme()`. The style block also provides sensible hardcoded fallback values for cases where a token has no override (e.g. `var(--evcc-modal-bg, #1c2127)`).

The split is: `MODAL_HOST_STYLES` provides the structure and fallbacks; `applyDynamicTheme()` provides the live, theme-controlled values on top.

---

## 5. Working Draft Lifecycle

**Created:** A working draft begins empty (`{tokens:{}, colors:{}, alpha:{}}`). It gains content the first time the user changes any token in the editor, at which point an `update_working_draft` service call merges the first override in.

**Persisted:** Every token change from the editor calls `updateWorkingDraft()` in `actions/theme.js` → `eufy_vacuum.update_working_draft` service → `manager.update_working_draft()` → patch-merged into `data.theme.vacuums.<id>.working_draft` → `async_save()`. The draft is written to storage on every individual change.

**Applied visually (optimistic):** The card does not wait for the backend to confirm before updating the DOM. The flow in the binding handlers is:
1. Compute the payload.
2. Kick off the backend service call (async, not awaited for visual update).
3. Call `card._state.applyThemeDraftPatch(payload)` to merge the change into the in-memory draft immediately.
4. Call `applyThemeToCard(card)` to push the new resolved values to CSS.

The result is that the UI updates on every keypress / slider drag pixel without visual lag from the HA service round-trip. Range sliders optimize further — the `input` event only updates local state and CSS; the `change` event (fired when the thumb releases) is the first point where the backend service is called.

**Discarded:** `revertDraft()` in `actions/theme.js` → `eufy_vacuum.revert_draft` service → clears `working_draft` to empty, sets `draft_dirty: False`. The card calls `applyThemeActivation(activeThemeId, { clearDraft: true })` optimistically and then refreshes the library from the backend.

**Promoted:** Two paths:
- `saveThemeAsNew()` — resolves the current active theme + working draft into a new library entry with a given name, clears the draft, and sets the new theme as active for that vacuum.
- `setActiveTheme()` — switches to an existing library theme, clears the draft. When used after `overwriteTheme()`, the draft's values have already been merged into the named entry.

---

## 6. Theme Sensor (`EufyVacuumThemeStateSensor`)

### What it exposes

`EufyVacuumThemeStateSensor` in `sensor/theme.py` is a `SensorEntity` with `_attr_should_poll = False` (it fires on push from manager callbacks).

**State value:** the active theme's `name`, or `"none"` if no theme is selected.

**`extra_state_attributes`:**

| Attribute | Type | Description |
|---|---|---|
| `active_theme_id` | `str \| null` | ID of the currently active theme for this vacuum |
| `working_draft` | `dict` | Current draft with `tokens`, `colors`, and `alpha` buckets |
| `draft_dirty` | `bool` | True when the draft contains at least one override |
| `editor_mode` | `str` | Always `"live"` in current implementation |
| `vacuum_entity_id` | `str` | The vacuum entity this sensor belongs to |
| `library_count` | `int` | Total number of themes in the library |
| `library_summary` | `list` | Array of `{id, theme_id, name}` objects for all library entries |
| `default_theme_id` | `str \| null` | The global default theme ID |

### How the card discovers it (`_findThemeSensor`)

The card calls `_findThemeSensor(hass)` in `main.js` on every `hass` setter invocation:

1. **Primary lookup:** construct `sensor.{objectId}_theme_state` from the vacuum's entity ID and check `hass.states` directly. This is the fast path and works in virtually all cases.

2. **Fallback scan:** if the primary ID is absent (HA appended a collision suffix like `_2`), scan all of `Object.values(hass.states)` and find the first entity whose `attributes.vacuum_entity_id` matches the configured vacuum entity ID.

The sensor entity name is built by `build_entity_name(vacuum_entity_id, "Theme State")` which produces names like `Alfred Theme State`, and the unique ID uses the pattern `{vacuum_entity_id_with_underscores}_theme_state`, so the slug is predictable in the normal case.

### How state changes propagate to the card

The `ThemeManager` keeps a list of theme update callbacks (`_update_callbacks`). Callbacks are registered via `register_update_callback(cb)`. After every mutation (`update_working_draft`, `set_active_theme`, `save_theme_as_new`, etc.) the manager calls `_notify_updated()`, which fires all registered callbacks with the affected `vacuum_entity_id` (or `None` for library-wide mutations). The theme sensor registers one such callback: it calls `self.async_write_ha_state()` to push its updated attributes to HA immediately without waiting for a poll cycle.

On the card side, every time HA delivers a new `hass` object through the `set hass(value)` setter, `main.js` reads the theme sensor:

```js
const sensor = this._findThemeSensor(hass);
if (sensor?.attributes) {
  this._state.setBackendThemeState?.(sensor.attributes);
}
```

`setBackendThemeState()` in `state/theme.js` overwrites the card's mirrored copies of `active_theme_id`, `working_draft`, `draft_dirty`, and `editor_mode`. This is the synchronization point between backend truth and card render state.

---

## 7. Import / Export

There are two surfaces: **whole-theme** (clipboard or file) and **targeted per-floor-type** (file or built-in preset). Both share one portable envelope:

```json
{ "ok": true, "version": 1, "exported_at": "...",
  "scope": ["marble"], "name": "Carrara",
  "theme": { "name": "...", "tokens": {}, "colors": {}, "alpha": {} } }
```

`scope` is the discriminator: a **non-empty list** of floor-type names ⇒ targeted; `"full"` or **absent** ⇒ whole-theme (legacy-safe).

### Whole-theme export / import

- **Export** (clipboard): `exportTheme(themeId)` → `eufy_vacuum.export_theme` → `manager.export_theme()` returns the full envelope; the card writes `JSON.stringify` to the clipboard.
- **Download** (file): the same envelope saved as `evcc-theme-{name}-{date}.json` via a temp-anchor Blob download.
- **Import** / **Upload**: paste (or pick a `.json` file) → `importTheme(payload)` → `manager.import_theme()` validates (`payload` dict, non-empty `name`, dict `tokens`/`colors`/`alpha`) and adds a **new library theme** (name de-duped with `" (imported)"`). Failure → `{"ok": false, "reason": ...}`, nothing stored.

### Targeted (per-floor-type) export

A floor type's scope unit is its whole token namespace — every `--evcc-floor-{type}-*` key across **tokens, colors, and alpha**. The valid type list is registry-driven (`floorTypeNames()` from `FLOOR_TEXTURE_REGISTRY`, `_`→`-`); names are matched **whole** by prefix, never dash-split, so `carpet-low` ≠ `carpet`.

- **Download Floor** (`floor-scope.js: sliceThemeByTypes`) slices the full export to the chosen type's keys across all three sections, stamps `scope:[type]`, and downloads `evcc-floor-{type}-{name}-{date}.json`.

### Targeted import — REPLACE, not patch

Uploading a scoped file (or applying a built-in preset) runs the shared scoped path (`_applyScopedThemeImport`):

1. `detectFloorScope()` partitions the file's floor types into **known** (in this build's registry) and **unknown** (e.g. a `terrazzo` preset on an older version → surfaced as "skipped — unsupported," never dropped silently).
2. A confirm lists the exact types under the word **"Replace"** — the visible blast radius.
3. `clampThemeScalars()` clamps every scalar to its token `min`/`max` (colors pass through; out-of-range edits can't invert behavior), reporting "N values corrected."
4. `importTheme(payload, vacuumEntityId)` → `manager.import_theme(payload, vacuum_entity_id)`. With a list `scope`, `_import_scoped()` runs **clear-then-apply** on the vacuum's **active theme**: for each type, delete every `--evcc-floor-{type}-*` key across tokens/colors/alpha on the active entry, apply the file's keys, and drop matching working-draft overrides. Clear-then-apply (not patch) makes the result deterministic regardless of the target's prior state — no stale override survives.

It REPLACES the namespace on the active theme **in place**; it does not create a standalone theme. Guards: no `vacuum_entity_id` → `missing_vacuum`; no active theme → `no_active_theme`.

### Built-in floor presets

`floor-presets.js` ships named marble looks — **Carrara** (minor-only), **Portoro** (both tiers), **Calacatta** (major-forward) — as `scope:["marble"]` envelopes with a human-readable `name`. The editor's **Apply Preset** picker runs the *same* `_applyScopedThemeImport` path, so presets REPLACE the marble namespace on the active theme rather than acting as standalone themes. Custom presets are just `Download Floor` files re-applied via `Upload`.

---

## 8. Extending the Theme System

### How to add a new token

1. **Choose the group file.** Open the appropriate file in `src/theme-tokens/` (e.g. `surfaces.js` for a new surface color).

2. **Add the token entry** using the group's typed helper:
   ```js
   surfaceToken.color("--evcc-surface-new-thing", "New Thing"),
   ```
   The key must start with `--evcc-` and must be unique across all group files (a duplicate key throws at module load time via `assertUniqueTokenKeys()`).

3. **Use the CSS variable** in the card's stylesheets wherever the new token should apply:
   ```css
   .my-component { background: var(--evcc-surface-new-thing); }
   ```

4. **Provide a default** in every built-in theme's token set (in `manager.py`, update `_build_release_theme_tokens()` or the `BASE_PRELOADED_THEME_SPEC`) so the token has a sensible value out of the box. For tokens that should fall back gracefully when absent, add a CSS fallback in the `var()` call: `var(--evcc-surface-new-thing, #1c2127)`.

No schema migration is needed — the flat storage format means new tokens simply appear as absent keys in existing saved themes, and `applyDynamicTheme()` skips absent tokens rather than injecting them.

### How to add a new token group

1. **Add the group name** to `THEME_GROUPS` in `src/theme-tokens/groups.js`. Order in this array determines the order groups appear in the editor.

2. **Create the group file** (e.g. `src/theme-tokens/my-group.js`). Import a typed helper from `helpers.js` or create one with `makeTypedGroupToken("My Group Name", "color")`. Export a constant array of token entries.

3. **Register in `index.js`:** import the exported array and add it to `GROUPED_TOKEN_SETS`.

4. **Add a section in the token editor template** so the new group renders in the UI (the editor iterates `THEME_GROUPS` and renders a collapsible section per group).

The group name string must match exactly between `THEME_GROUPS`, the `group` field on each token, and any group-filter chip data attributes in the template.

### How to add a new built-in theme

1. Open `custom_components/eufy_vacuum/themes/preloaded.py`.

2. Add a new spec to `PRELOADED_THEME_SPECS`:
   ```python
   {
       "id": "theme_my_new_theme",
       "name": "My New Theme",
       "colors": _build_release_theme_colors(
           accent="#...",
           surface_base="#...",
           # ... all required color parameters
       ),
       "tokens": _build_release_theme_tokens(BASE_PRELOADED_THEME_SPEC),
   },
   ```

3. The `id` must start with `theme_` and be unique. Use a short stable slug, not a timestamp, so it behaves as a preloaded entry (readable, not sortable with user themes).

4. `ensure_preloaded_theme_library()` only seeds an entry if the ID does not already exist in storage. A new built-in theme will appear for users on their next HA restart (or integration reload).

5. `BASE_PRELOADED_THEME_SPEC` contains all the non-color layout/typography/motion token values. Override individual keys in the `tokens` dict if a theme needs different spacing or radius values.

---

## 9. Theme-driven assets (`animal-svg`)

A standalone web component ships **inside** the integration at `custom_components/eufy_vacuum/frontend/animal-svg/` (served `/eufy_vacuum/frontend/animal-svg/`) for use as a future theme element on the map view. It is a self-registering free-standing resource that the card can `import` and drive from vacuum state.

Files:

```
custom_components/eufy_vacuum/frontend/animal-svg/
├── animal-svg.js     custom element + registry + shared keyframes
├── manifest.js       loads animal-svg.js then each animal file
├── animals/
│   ├── cat.js
│   ├── dog.js
│   ├── raccoon.js
│   ├── parrot.js
│   └── snake.js
└── demo.html         open in a browser to verify everything works
```

Usage from the card (or anywhere in HA):

```html
<animal-svg animal="cat" pose="walking"></animal-svg>
```

**Attributes (observed):** `animal`, `pose`, `width`, `height`. Poses: `animating | standing | curled | alert | walking | warning`. Adding a new animal = a self-registering JS file in `animals/` plus a line in `manifest.js`.

**Why it's a separate resource:** the component is a self-registering standalone module rather than part of the card bundle, so adding an animal (a new file in `animals/` plus a line in `manifest.js`) does not force a card rebuild. It ships under the integration's `frontend/` directory and is served at `/eufy_vacuum/frontend/animal-svg/`.

### Wiring it into a theme (planned, not yet implemented)

Future direction:

1. Add a `mascot` token to `theme-tokens/groups.js` — value is one of the registered animal names.
2. In `applyDynamicTheme`, render `<animal-svg animal="${mascot}" pose="${derived_pose}">` in the map view.
3. Derive `pose` from vacuum state — e.g. `docked → curled`, `cleaning → walking`, `error → warning`.
4. The pose mapping itself becomes a theme-token (`mascot_pose_map`), letting different themes drive different mascot behaviours from the same state.

The integration side is unaffected — this is purely a card concern. The animal-svg resource and the theme system are otherwise decoupled.
