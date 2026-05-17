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
| Floor Textures | Opacity and blend values shared across all floor texture types |
| Floor Textures — Tile | Tile-specific texture opacity tokens |
| Floor Textures — Wood | Wood-specific texture opacity tokens |
| Floor Textures — Marble | Marble-specific texture opacity tokens |
| Floor Textures — Concrete | Concrete-specific texture opacity tokens |
| Floor Textures — Carpet Low | Low-pile carpet texture opacity tokens |
| Floor Textures — Carpet High | High-pile carpet texture opacity tokens |
| Floor Textures — Granite | Granite texture opacity tokens |
| Queue & Ordering | Queue strip colors, drag card, drop target, order badge styling |
| Status, Confidence & Alerts | Status dot colors, confidence-level chip colors, alert surface colors |
| Learning & Metrics | Estimate badge styles, learning panel surfaces, confidence tiers |
| Modals & Overlays | Modal backdrop, modal surface, modal header and footer |
| Shared Foundations | Cross-cutting values: gap, radius, font scale, hover lift, transition speed |

The Floor Texture sub-groups (Tile, Wood, Marble, etc.) are nested visually under the parent Floor Textures group. Their headers display the sub-group name without the parent prefix, so "Floor Textures — Tile" appears as just "Tile" when expanded.

All groups are open by default on first visit. Clicking a group header collapses or expands it, and that state is remembered for the rest of the session.

---

## Token controls

Each token row uses a control appropriate to its type:

- **Color tokens** — a horizontal alpha rail that you drag to set opacity, combined with a hidden color picker. Drag the rail to adjust the opacity of the current color. Double-tap the rail to open the native color picker and change the hue. The hex value is also editable directly as text.
- **Color-mix tokens** — tokens whose current value is a `color-mix(in srgb, ...)` expression get a dedicated ratio slider and two text inputs for the two color references. Dragging the slider adjusts the blend ratio live; a preview swatch shows the resolved result.
- **Numeric tokens** (size, number, duration) — a range slider paired with a number input. The slider range is calibrated per group: floor texture opacity sliders run 0–1 in 0.01 steps; geometry tokens (radii, gaps, paddings) typically run 0–32 or 0–64 in 1–2 px steps.
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

---

## Floor textures and the theme system

Floor textures are rendered as layered CSS patterns on room cards. The texture groups in the token editor — Floor Textures and its seven sub-groups — control the opacity values for each texture layer. Numeric tokens in these groups run on a 0–1 scale in 0.01 steps, so you can fine-tune how prominent each texture pattern appears or set any layer to 0 to suppress it entirely.

When you expand a Floor Texture sub-group in the Tokens tab, the contextual preview renders actual room cards using that floor type so you can see the visual effect of your opacity changes before saving.
