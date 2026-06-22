# 05 — Theme System

The theme system gives you per-card visual customization through CSS custom properties called design tokens. This is separate from Home Assistant's global theme system — your card theme has no effect on the rest of your dashboard, and HA global themes do not override the card's own token values.

> **New to themes?** The [Theme system user guide](../user-guide/17-theme-system.md) is the friendly tour — picking, per-device, import/export, filters. This page is the token-by-token reference; to *build* a theme, see [Authoring a theme](../contributing/theme-authoring.md).

---

## How the theme system works

The card maintains a **theme library**: a named collection of themes stored in the backend integration. Each theme is a flat dictionary of CSS custom property values (colors, sizes, radii, durations, and so on). When a theme is active, those values are applied directly to the card's shadow root as inline CSS variables.

On top of whatever theme is active, the card keeps a **working draft** — a set of token overrides that you are editing right now but have not yet saved. The card's preview always reflects the combination of the active theme's values with any draft overrides layered on top. This means you can freely explore changes and see them live before committing anything to storage.

A draft override is removed — not zeroed out — when you reset it. The card falls back to the active theme's value for that token, which keeps the preview aligned with the actual backend state.

---

## Opening the theme editor

Navigate to the **Theme** view inside the card. The editor opens on the **Themes** tab by default. Two other tabs are available: **Palette** and **Tokens**. You switch between them using the chip row at the top of the editor.

---

## Tabs

### Themes tab

The Themes tab shows your saved theme library as a grid of preset cards. Each card displays a small swatch preview built from the theme's color tokens and labels the theme by name. The currently active theme is marked with an **Active** chip on its label.

To set a theme as active, click its preset card. The card calls the `set_active_theme` service, applies the result optimistically, and re-renders without waiting for the next sensor push.

Custom themes (anything other than the default built-in theme) show a delete button — a close-circle icon in the corner of the card. Clicking it asks for confirmation before calling `delete_theme`.

### Palette tab

The Palette tab gives you fast access to four key tokens that define the card's visual identity:

- `--evcc-accent` — the primary accent color
- `--evcc-surface-base` — the base background color
- `--evcc-text-primary` — the primary text color
- `--evcc-radius-card` — the card corner radius

These four tokens are intentionally separated from the full token editor so you can make high-level style decisions without scrolling through hundreds of tokens.

The Palette tab also shows the contextual preview pane (see below).

### Tokens tab

The Tokens tab is the full token editor. All tokens except the four Palette tokens appear here, organized into collapsible groups. This is where you make detailed adjustments to specific surfaces, components, or behaviors.

---

## Filtering and tagging presets

The Themes tab carries its own filter bar above the preset grid — distinct from the token search described later, and driven by the **same facet vocabulary the public gallery uses**. Both surfaces import the shared `FACETS` table (Mode, Accent, Temp, Surface, Contrast, Access, Best for, Source) from `src/theme-tags/`, so a filter you build here behaves identically to the one in the gallery.

### Preset search and facet filters

- **Search themes** — a search box matches a theme's name and any of its derived tags. Matching is case-insensitive substring.
- **Filters** — a toggle button opens a collapsible panel (collapsed by default, so the grid gets the room) with one labelled row per facet. Each row only offers chips for tags that actually occur in your library, so you never see a facet value that matches nothing. The toggle shows a count of how many facet chips you have selected.
- **Filter semantics** — **OR within a facet** (Accent: purple *or* cyan) and **AND across facets** (Accent: purple *and* Mode: dark), matching the gallery exactly.
- **Clear** — appears once any facet chip or search text is active, and resets both at once.

The facet tags themselves are **derived from each theme's palette**, not authored — the card computes them through the same `effectiveThemeTags` core as the gallery, caches the result per library, and rebuilds the cache whenever the library changes. `colorblind-safe` is only ever present when verification actually passes (see *Accessibility — Colorblind Safe*), and the theme's `source` (core / community / generated / manual) is added as a filterable token so the Source facet works.

### Browse gallery

A **Browse gallery ↗** link sits in the filter bar. It opens the public theme gallery in a new tab. It is a plain outbound link — nothing is downloaded or imported — so it pairs with the **Upload** / **Import** controls (and the submission flow described under *Share to the gallery*) when you want to bring a gallery theme back into your card.

### Inline vibe-tag editor

The facet tags above are derived and read-only, but each preset card also carries **free-text vibe tags** (cosmic, aurora, cozy, …) that you *can* edit in place. A tag button on the card toggles a small editor for that one theme (only one theme is editable at a time, to keep the grid uncluttered):

- Existing vibe tags show as removable chips. Add new ones with the text input — press Enter to commit — and a datalist (populated from `SUGGESTED_VIBE_TAGS`) offers curated suggestions without restricting you to them; you can type anything, up to 32 characters.
- New tags are normalised to lowercase and de-duplicated before they are stored. **System-owned words** (a derived facet value like `blue` or `dark`, plus `colorblind-safe` and `core`) are *not* treated as vibe tags: those facet/status tags are computed from the palette and verification, so a hand-typed copy is simply ignored when the card recomputes a theme's effective tags — it won't show up as its own chip or change what the facet filters match.
- Edits apply **optimistically**: the chip set updates immediately, then the change is persisted via the `set_theme_tags` service. If the service call fails, the card **reverts** to the prior tag set and shows an alert, so the grid never drifts out of sync with the backend.

Only your free-text vibe tags are stored on the theme this way; the facet and colorblind-safe tags remain derived/verified on every render.

---

## Token groups

Tokens are organized into the following groups, in this order:

| Group | What it covers |
|---|---|
| App Shell & Typography | Card shell colors, text hierarchy, accent, link styling |
| Cards & Surfaces | Card backgrounds, panel surfaces, input backgrounds, layered elevation |
| Borders & Shadows | Border widths, border colors, shadow depths |
| Chips | Chip height, padding, radius, colors for each chip state |
| Room Cards | Room card backgrounds, spacing, and state variants |
| Map | Map overlay colors — the room-name label pill, the segment tooltip, and the custom-segment composer (selection / cutout / vertex) |
| Floor Textures | Opacity and blend values shared across all floor texture types |
| Floor Textures — Tile | Tile-specific texture opacity tokens |
| Floor Textures — Wood | Wood-specific texture opacity tokens |
| Floor Textures — Marble | Marble colors, opacities, and a two-tier vein system (master + per-tier offsets + minor recede) |
| Floor Textures — Concrete | Concrete-specific texture opacity tokens |
| Floor Textures — Carpet Low | Low-pile carpet texture opacity tokens |
| Floor Textures — Carpet High | High-pile carpet texture opacity tokens |
| Floor Textures — Granite | Granite texture opacity tokens |
| Queue & Ordering | Queue strip colors, drag card, drop target, order badge styling |
| Status, Confidence & Alerts | Status dot colors, confidence-level chip colors, alert surface colors |
| Learning & Metrics | Estimate badge styles, learning panel surfaces, confidence tiers |
| Modals & Overlays | Modal backdrop, modal surface, modal header and footer |
| Animal Companion | Parent group of the map companion: global mascot tokens shared by every animal |
| Animal Companion — &lt;Name&gt; | One sub-group per registered animal (Cat, Dog, Raccoon, …) holding that animal's colors; generated from the registered animal list, not hand-listed |
| Shared Foundations | Cross-cutting values: gap, radius, font scale, hover lift, transition speed |

The Floor Texture sub-groups (Tile, Wood, Marble, etc.) are nested visually under the parent Floor Textures group. Their headers display the sub-group name without the parent prefix, so "Floor Textures — Tile" appears as just "Tile" when expanded. The Animal Companion sub-groups follow the same parent/sub-group nesting, and their list grows automatically as new mascot files are registered.

The complete per-token catalog — every token in each group, with its editor label, type, and
slider range — lives in the developer reference: **[Theme Token Map](../dev/reference/THEME_TOKEN_MAP.md)**.

All groups are open by default on first visit. Clicking a group header collapses or expands it, and that state is remembered for the rest of the session.

---

## Token controls

Each token row uses a control appropriate to its type:

- **Color tokens** — a horizontal alpha rail that you drag to set opacity, combined with a hidden color picker. Drag the rail to adjust the opacity of the current color. Double-tap the rail to open the native color picker and change the hue. The hex value is also editable directly as text.
- **Color-mix tokens** — tokens whose current value is a `color-mix(in srgb, ...)` expression get a dedicated ratio slider and two text inputs for the two color references. Dragging the slider adjusts the blend ratio live; a preview swatch shows the resolved result.
- **Numeric tokens** (size, number, duration) — a range slider paired with a number input. The slider range comes from the token itself where defined — opacities run 0–1, a blur runs 0–8 px, a hue shift runs −180–180, a saturation multiplier 0–2 — falling back to a per-group default (e.g. radii/gaps at 0–32 or 0–64 px) for tokens without an explicit range. These bounds shape the editor's controls; note that a **full** theme import stores values as-is and is *not* range-clamped, so a hand- or AI-authored theme should keep each scalar inside its token's range (a floor-scoped import, by contrast, does clamp).
- **Text tokens** — a plain text input for anything that does not fit the above types.

Any token that has been changed in the current draft shows a **Reset** button next to its label. Clicking Reset removes the draft override for that token, reverting the preview to the active theme's value for it.

Group headers show a **modified / total** count. When a group has any draft-modified tokens, a **Reset** button appears on the group header to clear all draft overrides for that group at once.

---

## Searching and filtering

A search box at the top of the editor filters tokens across all groups. Search matches against the token label, the CSS custom property key, the current value, and any alias, usage, or affects metadata defined on the token. Groups with at least one match are forced open automatically.

Within each expanded group, a per-group search input lets you narrow further without affecting sibling groups.

A **Modified Only** checkbox next to the search box restricts the view to tokens that are currently in the draft (changed from the theme base).

The filter chip row above the token list offers quick shortcuts:

- **All** — show all tokens (default)
- **Modified** — show only draft-modified tokens across all groups
- Any individual group name — show only that group's tokens

---

## Contextual preview pane

When you are in the Palette tab, or when you have a group expanded or a group filter active in the Tokens tab, the editor renders a **Contextual Preview** panel alongside the token controls. The preview renders the actual card component associated with the focused group — for example, expanding the Chips group shows a chip matrix, opening Room Cards shows two sample room card surfaces, and opening Floor Textures shows a grid of floor-type room cards.

The preview reacts to token edits in real time because it inherits the card's live CSS custom properties.

---

## Saving, overwriting, and managing themes

The footer bar at the bottom of the editor always shows the full set of save and discard actions.

### Save Changes / Save as New

The save button in the footer changes label depending on whether a theme is currently active:

- If an active theme is set, the button reads **Save Changes** and calls `overwrite_theme` to write the current draft back into that theme.
- If no theme is active (you are working against defaults without a named theme selected), the button reads **Save as New** and prompts you for a name. It then calls `save_theme_as_new` with that name.

After a successful save, the draft is cleared and the saved theme becomes the active theme.

### Rename

Renaming a theme uses the `rename_theme` service. There is no inline rename control in the preset grid — renaming is a service-level operation.

### Delete

Click the close-circle button on any custom preset card in the Themes tab. A browser confirmation prompt appears before the `delete_theme` service is called. The default theme cannot be deleted (it has no delete button).

### Discard

The **Discard** button in the footer calls `revert_draft`. This clears the working draft and reverts the live preview to the active theme's values. The button is disabled when there are no draft changes.

---

## Active theme

Clicking a preset card in the Themes tab sets that theme as active by calling `set_active_theme`. The card applies the result immediately without waiting for the next sensor round-trip. The active theme's tokens form the base layer; any subsequent edits create draft overrides on top.

Setting a new active theme clears the working draft if the service response indicates no draft is pending. If you had unsaved draft changes when you switched themes, those changes are discarded.

---

## Per-device theme selection

Everything covered so far — the theme library, your edits and drafts, imports, and which theme is marked **active** in the backend — is **shared**. It lives in the integration and is the same for every device and browser that views this vacuum's card. The one exception is *which theme this particular browser chooses to display*. That selection is **local**: it is the only per-browser piece of theme state.

At the top of the **Themes** tab is a **Theme mode** row with two buttons:

- **Follow system** — this browser shows whatever theme is active in the backend. Switch the active theme (from any device, or this one) and this browser follows it. This is the default.
- **This device only** — this browser pins a theme of its own and ignores later changes to the backend active theme. Switching into this mode with no prior pick pins whatever is showing right now, so the toggle is visually a no-op until you choose a different preset.

When **This device only** is selected, a detail block appears below the row showing:

- **Active theme** — the name of the theme this device is currently displaying.
- **Mode** — `this device only`.
- **Use everywhere** — promotes this device's pinned theme to the shared backend active theme (so every *Follow system* device picks it up), then drops this device's local pin so it goes back to **Follow system** too. If the backend call fails the pin is left untouched.
- **Clear device override** — drops the local pin and returns this browser to **Follow system**.

The block ends with the reminder that this whole feature turns on: *theme edits are shared; only the selected theme is local to this browser.* Editing tokens, saving, deleting, or importing while pinned still mutates the shared library — only your *choice of which theme to look at* stays on this device.

### Use case

Because the selection is per-browser and scoped per vacuum, one wall-mounted kiosk can sit on a high-contrast theme, a phone on a compact light theme, and a desktop on something richer — all at once, all viewing the same vacuum, without any of them disturbing the shared library or each other.

### Resolution and stale pins

The theme the card actually renders is resolved through a safe fallback chain:

1. If this device is in **This device only** mode and its pinned theme still exists in the library, that theme is used.
2. If the pinned theme has been deleted from the library, the pin is treated as stale: it is cleared automatically (and the local storage entry updated), and the card falls through.
3. Otherwise — and after a stale pin is cleared — the card uses the backend active theme.

A pin is only ever cleared once the library has actually loaded, so the very first render (which runs before the library resolves) never wipes a valid pin. The selection persists in `localStorage` under a key scoped to this vacuum, so a browser viewing several cards keeps each card's choice independent.

---

## Accessibility — Colorblind Safe

One built-in preset, **Colorblind Safe**, is designed for color-vision
deficiency. Its status palette — success, warning, error, info (reference), and
muted — is validated to stay distinguishable under simulated protanopia,
deuteranopia, and tritanopia (CIEDE2000 ≥ 15 across all ten group pairs,
including muted), so the red/amber/green states that collapse in a typical
palette stay readable. Select it like any other preset card.

Color is never the only cue. The mapping-bounds badges (OK / Likely / No-bounds /
Outlier / Excluded / Baseline) each carry a distinct **shape mark** —
✓ ◐ ! ✕ – ◆ — that reads in flat grayscale, so the states are identifiable
without relying on hue. The marks are always on, in every theme.

How the palette is validated (the CVD simulation matrices — Machado 2009
protan/deutan plus Brettel 1997 tritan — the CIEDE2000 ≥ 15 separation gate over
the ten group pairs, and the shape-mark grayscale check) is covered in
[dev/27-render-harness](../dev/27-render-harness.md).

---

## Import and export

Four buttons in the lower-left of the editor footer give you two
transport options (clipboard and file) for moving themes in and out:

| Button | Transport | Best for |
|--------|-----------|----------|
| **Export** | Clipboard | Quick one-session paste into a sibling tab or chat |
| **Import** | Clipboard | Pasting a theme JSON you copied from somewhere else |
| **Download** | File | Backing up a theme, sharing it as a file attachment, or migrating between Home Assistant installs |
| **Upload** | File | Loading a theme `.json` file someone shared, restoring a backup, or migrating from a previous install |

### Export (clipboard)

Calls `export_theme` for the currently active theme and opens a modal showing the JSON in a read-only text box. From there you **Copy** it to your clipboard, **Send to HA** (posts the JSON to a Home Assistant persistent notification — useful when the browser blocks clipboard access on a plain-HTTP LAN), or **Close**. There is no automatic clipboard write and no console fallback. When there is no active theme, the button shows an alert and does nothing.

### Import (clipboard)

Opens a modal with a paste box (not a browser prompt). Paste a theme JSON and confirm; if it parses, the card calls `import_theme` with the payload and refreshes the theme library, otherwise you see an error alert.

### Download (file)

Calls `export_theme` for the currently active theme, then triggers a browser file download of the JSON. The filename uses the theme name plus today's date — for example `evcc-theme-midnight-2026-05-17.json` — so you can tell different exports apart at a glance.

This is the recommended way to:

- **Share a theme** with someone else — post the file in a forum thread or attach it to a message
- **Back up a theme** before making risky edits, so you can restore it via Upload if things go wrong
- **Migrate a theme** to a different Home Assistant install (or to a future version of this integration)

### Upload (file)

Opens a file picker for `.json` files. After you pick one, the card reads the file, JSON-parses the contents, and calls `import_theme` with the result. On success you see a confirmation with the filename; on failure (invalid JSON, unsupported shape) you see an error alert with the filename for context.

Themes don't reference your specific entities, room IDs, or vacuum brand — they're pure visual styling data — so a theme exported on one install will work cleanly when uploaded on another.

### Floor presets — move or apply one floor type

Beyond whole themes, you can move a **single floor type's look** in isolation — handy for sharing "just my marble" without disturbing the rest of a theme:

- **Download Floor** — pick a floor type from the dropdown next to the button and download *only* that type's tokens as `evcc-floor-{type}-{name}-{date}.json`.
- **Upload** a floor file — the card recognises it as floor-scoped, asks you to confirm exactly which floor type(s) it will **Replace** on your active theme, then applies it. It *replaces* that floor's settings outright (it doesn't merge), so the result is predictable regardless of what you had before. Out-of-range values are clamped automatically, and a floor type your version doesn't recognise is skipped and reported rather than applied.
- **Apply Preset** — pick a built-in marble look (**Carrara**, **Portoro**, **Calacatta**) and apply it the same way. These replace just the marble namespace on your active theme — they are *not* separate themes to switch to. Treat them as starting points and tune from there; **Download Floor** then captures your tuned look as a new shareable file.

### Share to the gallery

Beyond passing a file around privately, there's a public **theme gallery** you
can publish to. In the gallery, click **+ Submit a theme** and paste your
**Download** export into the form; a bot validates it, renders a preview, and
opens a pull request for a maintainer to review and merge. See
[Sharing themes](../user-guide/15-sharing-themes.md) for the full walkthrough.

---

## Floor textures and the theme system

Floor textures are rendered as layered CSS patterns on room cards. The texture groups in the token editor — Floor Textures and its seven sub-groups — control each material's colors and per-layer opacities. Most are opacities on a 0–1 scale, but some have purpose-built ranges (see the marble veins below), so you can fine-tune how prominent each pattern appears or set a layer to 0 to suppress it entirely.

**Marble** carries the richest controls: a **two-tier vein system**. A master vein opacity (and blur) rides both tiers at once; per-tier **major** and **minor** offsets nudge each tier while preserving the gap between them; and the minor tier has color deltas (lighten / saturation / hue) so it can *recede* — softer, fainter, and cooler than the major veins, like atmospheric depth. The built-in Carrara / Portoro / Calacatta presets are quick starting points for that system.

When you expand a Floor Texture sub-group in the Tokens tab, the contextual preview renders actual room cards using that floor type so you can see the effect of your changes before saving.
