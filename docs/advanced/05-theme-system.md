# Theme System

The theme system gives you per-card visual customization through CSS custom properties called design tokens. This is separate from Home Assistant's global theme system — your card theme has no effect on the rest of your dashboard, and HA global themes do not override the card's own token values.

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

All groups are open by default on first visit. Clicking a group header collapses or expands it, and that state is remembered for the rest of the session.

---

## Token controls

Each token row uses a control appropriate to its type:

- **Color tokens** — a horizontal alpha rail that you drag to set opacity, combined with a hidden color picker. Drag the rail to adjust the opacity of the current color. Double-tap the rail to open the native color picker and change the hue. The hex value is also editable directly as text.
- **Color-mix tokens** — tokens whose current value is a `color-mix(in srgb, ...)` expression get a dedicated ratio slider and two text inputs for the two color references. Dragging the slider adjusts the blend ratio live; a preview swatch shows the resolved result.
- **Numeric tokens** (size, number, duration) — a range slider paired with a number input. The slider range comes from the token itself where defined — opacities run 0–1, a blur runs 0–8 px, a hue shift runs −180–180, a saturation multiplier 0–2 — falling back to a per-group default (e.g. radii/gaps at 0–32 or 0–64 px) for tokens without an explicit range. The same bounds gate what an import will accept, so the slider can never show a value its own importer would reject.
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

## Accessibility — Colorblind Safe

One built-in preset, **Colorblind Safe**, is designed for color-vision
deficiency. Its status palette — success, warning, error, info (reference), and
muted — is validated to stay distinguishable under simulated protanopia,
deuteranopia, and tritanopia (CIEDE2000 ≥ 15 on every pair), so the
red/amber/green states that collapse in a typical palette stay readable. Select
it like any other preset card.

Color is never the only cue. The mapping-bounds badges (OK / Likely / No-bounds /
Outlier / Excluded / Baseline) each carry a distinct **shape mark** —
✓ ◐ ! ✕ – ◆ — that reads in flat grayscale, so the states are identifiable
without relying on hue. The marks are always on, in every theme.

How the palette is validated (the CVD simulation matrices, the ΔE separation
gate, and the shape-mark grayscale check) is covered in
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

Calls `export_theme` for the currently active theme and copies the resulting JSON to your clipboard. If clipboard access is unavailable, the JSON is printed to the browser console instead. When there is no active theme, the button shows an alert and does nothing.

### Import (clipboard)

Opens a browser prompt where you paste JSON. If the JSON parses successfully, the card calls `import_theme` with the parsed payload and then refreshes the theme library. If the JSON is invalid, you see an error alert.

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
