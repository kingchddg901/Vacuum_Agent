// CSS styles for the Theme editor view: preset grid, token editor groups, color controls, and sliders.

export const themeStyles = `
  /* =========================================================
     THEME VIEW LAYOUT
     ========================================================= */

  .evcc-view--theme {
    display: flex;
    flex-direction: column;
    flex: 1;
    height: 100%;
    gap: var(--evcc-space-md, 16px);
    min-height: 0;
    overflow: hidden;
  }

  .evcc-view--theme .evcc-view-content {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-space-md, 16px);
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  /* =========================================================
     HEADER
     ========================================================= */

  .evcc-theme-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 0 4px;
    flex-shrink: 0;
    /* Search box + "Modified Only" contribute 392px of min-content, and the
       12px gap makes 404 — more than a 390px phone can show. Wrapping engages
       only under that pressure, so the row is unchanged at >= 500px. */
    flex-wrap: wrap;
  }

  .evcc-search-box {
    position: relative;
    flex: 1;
    display: flex;
    align-items: center;
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    border-radius: var(--evcc-radius-inner, 12px);
    padding: 0 12px;
    height: 38px;
    transition: var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-search-box:focus-within {
    border-color: var(--evcc-accent, #3b82f6);
    background: var(--evcc-surface-panel, #1c2127);
  }

  .evcc-search-box ha-icon {
    --mdc-icon-size: 18px;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    margin-inline-end: 8px;
    flex-shrink: 0;
  }

  .evcc-search-box input {
    flex: 1;
    background: none;
    border: none;
    color: var(--evcc-text-primary, #f0f2f5);
    font-size: 0.9rem;
    outline: none;
    width: 100%;
    min-width: 0;
  }

  .evcc-search-box input::placeholder {
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
  }

  .evcc-modified-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
    cursor: pointer;
    white-space: nowrap;
    user-select: none;
  }

  .evcc-theme-tabs {
    margin-bottom: 4px;
    flex-shrink: 0;
  }

  /* THE CHIP ROW MUST NOT DRIVE THE EDITOR'S SIZE.
     It sits above .evcc-theme-editor-scrollbox, which is flex: 1 1 auto — so
     whatever height these chips happen to need, the editor gets the remainder.
     That was tolerable when the row was a constant 162px and intolerable once
     disclosure made it VARY: 108px at the top level, 36px inside a branch, so
     the editor jumped 72px every time you navigated. Bounding the band trades
     that for a fixed frame the editor can rely on.

     Deliberately just PAST two rows, so a third peeks when there is one — a
     clipped chip is the only scroll affordance a touch device gets, and a band
     that ends flush reads as complete. Nothing becomes unreachable: everything
     the level offers is still here, one scroll away. */
  .evcc-theme-filters {
    margin-bottom: 4px;
    flex-shrink: 0;
    height: 4.6rem;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    scrollbar-gutter: stable;
  }

  /* The step-up chip. It sits in the same row as the category chips but does a
     different thing — it navigates rather than filters — so it reads quieter and
     is set off from its siblings. The chevron alone was carrying that distinction
     and a chevron is easy to miss on a phone. */
  .evcc-chip--back {
    color: var(--evcc-text-secondary);
    background: transparent;
    margin-inline-end: 6px;
  }

  /* =========================================================
     THEME MODE (follow system vs this device only)
     ========================================================= */

  .evcc-theme-mode {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    flex: none;
  }

  .evcc-theme-mode-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .evcc-theme-mode-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    margin-inline-end: 2px;
  }

  .evcc-theme-mode-detail {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border-radius: var(--evcc-radius-inner, 10px);
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-accent, #3b82f6) 30%, transparent);
  }

  .evcc-theme-mode-state {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 18px;
    font-size: 0.85rem;
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-theme-mode-state .k {
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-inline-end: 5px;
  }

  .evcc-theme-mode-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .evcc-theme-mode-note {
    margin: 0;
    font-size: 0.78rem;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
  }

  /* =========================================================
     PRESET (THEME) FACET FILTER + SEARCH
     ========================================================= */

  .evcc-preset-filters {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 10px;
    flex: none; /* fixed band; the grid below scrolls */
  }

  /* The theme grid scrolls so every preset is reachable under the fixed filter
     band (the view-content itself is overflow:hidden, like the token editor). */
  .evcc-preset-scroll {
    flex: 1 1 auto;
    height: 0;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    scrollbar-gutter: stable;
    padding-inline-end: 4px;
  }

  .evcc-preset-filters-top {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .evcc-preset-filters-toggle {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    text-transform: none;
  }

  .evcc-preset-filters-toggle ha-icon {
    --mdc-icon-size: 15px;
  }

  .evcc-preset-filters-caret {
    transition: transform 150ms ease;
  }

  .evcc-preset-filters-toggle.active .evcc-preset-filters-caret {
    transform: rotate(180deg);
  }

  .evcc-preset-search {
    flex: 1;
    min-width: 160px;
    height: 34px;
  }

  .evcc-preset-clear {
    flex-shrink: 0;
  }

  .evcc-preset-gallery-link {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin-inline-start: auto;
    flex-shrink: 0;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--evcc-accent, #3b82f6);
    text-decoration: none;
    padding: 6px 10px;
    border-radius: var(--evcc-radius-inner, 10px);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    transition: var(--evcc-transition-normal, 150ms ease);
    white-space: nowrap;
  }

  .evcc-preset-gallery-link:hover {
    border-color: var(--evcc-accent, #3b82f6);
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 12%, transparent);
  }

  .evcc-preset-gallery-link ha-icon {
    --mdc-icon-size: 15px;
  }

  .evcc-preset-facets {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-preset-facet {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 5px;
  }

  .evcc-preset-facet-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    width: 64px;
    flex: none;
  }

  .evcc-preset-facet-chip {
    text-transform: capitalize;
    font-size: 0.74rem;
  }

  /* =========================================================
     PRESETS
     ========================================================= */

  .evcc-preset-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 12px;
    padding-bottom: 16px;
  }

  .evcc-preset-card {
    background: var(--evcc-surface-card, #242b33);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    border-radius: var(--evcc-radius-card, 16px);
    padding: 8px;
    cursor: pointer;
    transition: all 200ms ease;
    display: flex;
    flex-direction: column;
    gap: 8px;
    position: relative;
  }

  .evcc-preset-card:hover {
    border-color: var(--evcc-border-strong, rgba(255, 255, 255, 0.2));
    transform: translateY(-2px);
  }

  .evcc-preset-card.active {
    border-color: var(--evcc-accent, #3b82f6);
    background: color-mix(
      in srgb,
      var(--evcc-accent, #3b82f6) 10%,
      var(--evcc-surface-card, #242b33)
    );
  }

  .evcc-preset-delete {
    position: absolute;
    top: 6px;
    inset-inline-end: 6px;
    border: none;
    background: none;
    color: var(--evcc-text-muted, rgba(255,255,255,0.6));
    cursor: pointer;
    padding: 2px;
  }

  .evcc-preset-preview {
    aspect-ratio: 16 / 9;
    border-radius: var(--evcc-radius-inner, 8px);
    background: var(--evcc-surface-base, #10161f);
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(0, 0, 0, 0.2);  /* theme-lint-ignore: subtle dark frame on the preview swatch — theme-independent edge */
  }

  .preview-swatch {
    position: absolute;
    width: 30%;
    height: 30%;
    border-radius: 50%;
  }

  .preview-swatch.accent {
    background: var(--evcc-accent, #3b82f6);
    top: 20%;
    inset-inline-start: 20%;
  }

  .preview-swatch.surface {
    background: var(--evcc-surface-panel, #1c2127);
    bottom: 20%;
    inset-inline-end: 20%;
  }

  .evcc-preset-label {
    font-size: 0.8rem;
    font-weight: 600;
    text-align: center;
    color: var(--evcc-text-primary, #f0f2f5);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .evcc-preset-tags {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 4px;
  }

  .evcc-preset-tag {
    font-size: 0.62rem;
    line-height: 1;
    padding: 3px 6px;
    border-radius: 999px;
    text-transform: capitalize;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    white-space: nowrap;
  }

  /* colorblind-safe is system-verified — tint it with the success semantic. */
  .evcc-preset-tag[data-facet="a11y"] {
    color: var(--evcc-sem-success, #4caf6e);
    border-color: color-mix(in srgb, var(--evcc-sem-success, #4caf6e) 45%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-success, #4caf6e) 12%, transparent);
  }

  .evcc-preset-tag[data-facet="source"] {
    color: var(--evcc-accent, #3b82f6);
    border-color: color-mix(in srgb, var(--evcc-accent, #3b82f6) 45%, transparent);
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 12%, transparent);
  }

  /* --- Inline vibe-tag editor --- */
  .evcc-preset-tag-edit {
    position: absolute;
    top: 6px;
    inset-inline-start: 6px;
    z-index: 2;
    border: none;
    background: none;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.6));
    cursor: pointer;
    padding: 2px;
    opacity: 0.65;
    --mdc-icon-size: 16px;
  }

  .evcc-preset-tag-edit:hover,
  .evcc-preset-tag-edit.active {
    color: var(--evcc-accent, #3b82f6);
    opacity: 1;
  }

  .evcc-preset-card.editing {
    border-color: var(--evcc-accent, #3b82f6);
  }

  .evcc-preset-tag-editor {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 2px;
    padding-top: 6px;
    border-top: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
  }

  .evcc-preset-vibe-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .evcc-preset-vibe-chip {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    font-size: 0.66rem;
    line-height: 1;
    padding: 3px 4px 3px 7px;
    border-radius: 999px;
    text-transform: capitalize;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
  }

  .evcc-preset-vibe-remove {
    border: none;
    background: none;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    cursor: pointer;
    font-size: 0.85rem;
    line-height: 1;
    padding: 0 1px;
  }

  .evcc-preset-vibe-remove:hover {
    color: var(--evcc-sem-error, #e05252);
  }

  .evcc-preset-tag-add {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .evcc-preset-tag-input {
    flex: 1;
    min-width: 0;
    font: inherit;
    font-size: 0.72rem;
    padding: 4px 7px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-preset-tag-input:focus {
    outline: none;
    border-color: var(--evcc-accent, #3b82f6);
  }

  .evcc-preset-tag-done {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    background: none;
    color: var(--evcc-accent, #3b82f6);
    border-radius: var(--evcc-radius-inner, 8px);
    cursor: pointer;
    padding: 3px;
    --mdc-icon-size: 16px;
  }

  .evcc-preset-tag-done:hover {
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 12%, transparent);
  }

  /* =========================================================
     TOKEN EDITOR GROUPS
     ========================================================= */

  .evcc-token-editor {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
  }

  .evcc-theme-editor-main {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    min-width: 0;
    overflow: hidden;
  }

  .evcc-theme-editor-main--palette {
    gap: 12px;
  }

  .evcc-theme-editor-scrollbox {
    flex: 1 1 auto;
    height: 0;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    scrollbar-gutter: stable;
    padding: 12px;
    padding-inline-end: 16px;
    background: color-mix(
      in srgb,
      var(--evcc-surface-panel, #1c2127) 88%,
      transparent
    );
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: var(--evcc-radius-card, 16px);
  }

  .evcc-token-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-bottom: 20px;
  }

  .evcc-token-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: color-mix(
      in srgb,
      var(--evcc-surface-panel, #1c2127) 82%,
      transparent
    );
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: var(--evcc-radius-card, 16px);
    padding: 10px 12px 12px;
  }

  .evcc-token-group-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    cursor: pointer;
    user-select: none;
  }

  .group-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--evcc-text-primary, #f0f2f5);
    min-width: 0;
  }

  .group-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .group-toggle {
    color: var(--evcc-text-muted, rgba(255,255,255,0.6));
    font-size: 0.95rem;
    min-width: 14px;
    text-align: center;
  }

  .evcc-token-group-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .evcc-token-group-search input {
    width: 100%;
    background: var(--evcc-surface-input, rgba(255,255,255,0.05));
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
    border-radius: 10px;
    color: var(--evcc-text-primary, #f0f2f5);
    padding: 8px 10px;
    font-size: 0.8rem;
    outline: none;
  }

  .evcc-token-group-search input:focus {
    border-color: var(--evcc-accent, #3b82f6);
  }

  /* Nested sub-groups rendered inside a parent group's body */
  .evcc-token-group--child {
    background: transparent;
    border-color: var(--evcc-border-subtle, rgba(255, 255, 255, 0.06));
    border-radius: var(--evcc-radius-card, 12px);
    padding: 8px 10px 10px;
    margin: 0;
  }

  .evcc-token-group--child .group-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.72));
  }

  /* =========================================================
     TOKEN ROWS (STACKED DESKTOP MODEL)
     ========================================================= */

  .evcc-token-row {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    background: var(--evcc-surface-panel, #1c2127);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: var(--evcc-radius-inner, 12px);
  }

  .evcc-token-row.is-draft {
    border-color: var(--evcc-accent, #3b82f6);
    background: color-mix(
      in srgb,
      var(--evcc-accent, #3b82f6) 4%,
      var(--evcc-surface-panel, #1c2127)
    );
  }

  .token-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .token-label {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--evcc-text-primary, #f0f2f5);
    min-width: 0;
    flex: 1;
  }

  .token-head-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  /* =========================================================
     TOP STRIP (HEX + RESET + HINT)
     ========================================================= */

  .token-top-strip {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .token-input--hex {
    width: 110px;
    min-width: 110px;
    max-width: 110px;
  }

  /* ACCEPTED TRADE — THIS LINE CLIPS IN LONGER LOCALES AT PHONE WIDTH.
     nowrap plus the shell's overflow:hidden means the tail is cut rather than
     wrapped: English fits, French and Spanish do not ("Double-appui pour la
     co...", "Doble toque para colo..."). It is the one band in this view that
     TRULY overflows; the footer merely wraps to a second row.

     Letting it wrap is a one-line change and the wrong one. The hint renders
     once per COLOUR token -- 303 rows -- so a second line costs ~14px on every
     one of them, which is precisely the vertical budget that took the mobile
     editor from ZERO visible token rows to two. A clipped tail on a
     discoverability hint is cheaper than an editor with nothing in it.

     If it must read in full, shorten the STRING for that locale. Do not
     remove the nowrap. */
  .token-hint {
    margin-inline-start: auto;
    font-size: 0.7rem;
    color: var(--evcc-text-muted, rgba(255,255,255,0.6));
    opacity: 0.8;
    white-space: nowrap;
  }

  /* =========================================================
     TOKEN CONTROL ROWS
     ========================================================= */

  .token-control-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
  }

  .token-control-row--number {
    width: 120px;
  }

  .token-control-row--text {
    width: 100%;
  }

  /* Font Family preset chips — each previews ITSELF via the custom property
     the renderer sets inline (the sanctioned data->CSS escape hatch). The
     text input below them stays the free-form escape hatch. */
  .token-control-row--font-presets {
    display:   flex;
    flex-wrap: wrap;
    gap:       6px;
    width:     100%;
  }

  .evcc-font-preset {
    font-family: var(--evcc-font-preview, inherit);
    cursor:      pointer;
  }

  .evcc-font-preset.is-active {
    background:  color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    color:       var(--evcc-accent);
    font-weight: 600;
  }

  /* =========================================================
     UNIFIED COLOR CONTROL
     ========================================================= */

  .token-control-row--color {
    width: 100%;
  }

  .token-color-combined-control {
    width: 100%;
    min-width: 0;
  }

  /* RTL: theme sliders are spatial color/scalar EDITORS, not reading-order
     controls. Native <input type=range> auto-reverses under dir=rtl, but the
     JS-positioned markers/bubbles (physical inline percent offsets), gradient tracks, and the A/B
     colormix swatches do NOT — so a flipped slider desyncs the handle, fill, and
     value. Decision (2026-07-25): pin ALL theme sliders direction:ltr, same
     rationale as the map ([[project_rtl_support]]) — they read like a color-picker
     panel. Labels/hints AROUND them (token-head, token-hint) sit outside these
     wrappers and still flip. direction:ltr is not a physical-direction property,
     so the RTL lint does not flag it. (No backticks in here — JS template.) */
  .token-alpha-shell,
  .token-colormix-colors,
  .token-colormix-slider-row,
  .slider-wrap {
    direction: ltr;
  }

  .token-alpha-shell {
    position: relative;
    width: 100%;
    min-width: 0;
    padding-top: 0;
  }

  .token-alpha-rail {
    position: relative;
    width: 100%;
    height: 58px;
    min-width: 0;
    overflow: hidden;
    border-radius: 16px;
    background: var(--evcc-surface-input, rgba(255,255,255,0.05));
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
    cursor: ew-resize;
  }

  .token-alpha-rail-fill {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      to right,
      transparent 0%,
      var(--rail-color, var(--evcc-accent, #3b82f6)) 100%
    );
    z-index: 1;
    pointer-events: none;
  }

  .token-alpha-rail-track {
    position: absolute;
    inset: 0;
    z-index: 2;
    pointer-events: none;
  }

  .token-alpha-input {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    opacity: 0;
    z-index: 3;
    cursor: ew-resize;
    -webkit-appearance: none;
    appearance: none;
    background: transparent;
  }

  .token-alpha-input::-webkit-slider-runnable-track {
    height: 58px;
    background: transparent;
    border: none;
  }

  .token-alpha-input::-moz-range-track {
    height: 58px;
    background: transparent;
    border: none;
  }

  .token-alpha-input::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    margin-top: 21px;
    width: 1px;
    height: 1px;
    opacity: 0;
    border: none;
    box-shadow: none;
    cursor: ew-resize;
  }

  .token-alpha-input::-moz-range-thumb {
    width: 1px;
    height: 1px;
    opacity: 0;
    border: none;
    box-shadow: none;
    cursor: ew-resize;
  }

  .token-alpha-indicator {
    position: absolute;
    top: 6px;
    bottom: 6px;
    width: 2px;
    transform: translateX(-50%);
    background: #ffffff;  /* theme-lint-ignore: mix-blend-mode:difference marker MUST be #fff to invert against any background */
    mix-blend-mode: difference;
    opacity: 0.95;
    box-shadow: 0 0 4px rgba(255, 255, 255, 0.35);
    z-index: 4;
    pointer-events: none;
  }

  .hidden-color-input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
  }

  .token-slider-bubble {
    position: absolute;
    top: 0;
    inset-inline-start: 50%;
    transform: translateX(-50%);
    background: var(--evcc-surface-card, #242b33);
    color: var(--evcc-text-primary, #f0f2f5);
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
    padding: 2px 6px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-family: monospace;
    white-space: nowrap;
    pointer-events: none;
  }

  /* THE % BUBBLE LIVES INSIDE THE RAIL.
     It tracks the VALUE horizontally, so at one end of the range it lands on
     .token-label, which shared the line above the rail at top:-28px. In LTR
     that collision is at the 0% end; in RTL the label flips and it becomes
     the 100% end — where most tokens sit, which is why it showed up
     immediately in Arabic. ONE defect at two ends, so it is fixed for both
     directions rather than patched for the one that reported it.

     Centring it in the rail removes the shared line entirely and costs no row
     height. The colours are deliberately theme-INDEPENDENT: the rail is
     whatever colour the token happens to be, so a themed surface would vanish
     against some of them. A fixed dark pill with light text reads over every
     colour the rail can take, which is the exact case check-styles names as a
     legitimate theme-lint-ignore ("a fixed dark pill").

     JS drives position via an inline style.left in px against the shell width
     and never sets transform, so the transform below is safe to own here. */
  .token-slider-bubble--alpha {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 5;
    pointer-events: none;
    background: rgba(0, 0, 0, 0.72); /* theme-lint-ignore */
    color: #f5f7fa; /* theme-lint-ignore */
    border: 1px solid rgba(255, 255, 255, 0.24); /* theme-lint-ignore */
  }

  /* =========================================================
     COLOR-MIX CONTROL
     ========================================================= */

  .token-colormix-colors {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .token-colormix-slot {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 0;
  }

  .token-colormix-swatch {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    flex-shrink: 0;
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
  }

  .token-colormix-color {
    flex: 1;
    min-width: 0;
    font-size: 0.75rem;
  }

  .token-colormix-ratio-label {
    flex-shrink: 0;
    font-size: 0.75rem;
    font-family: monospace;
    color: var(--evcc-text-secondary, rgba(255,255,255,0.7));
    min-width: 36px;
    text-align: center;
  }

  .token-colormix-slider-row {
    position: relative;
    width: 100%;
  }

  .token-colormix-ratio-input {
    width: 100%;
    height: 8px;
    appearance: none;
    -webkit-appearance: none;
    border: none;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
    outline: none;
    cursor: pointer;
  }

  .token-colormix-ratio-input::-webkit-slider-runnable-track {
    height: 8px;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
  }

  .token-colormix-ratio-input::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    margin-top: -4px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--evcc-surface-base, #10161f);
    box-shadow:
      0 0 0 2px var(--evcc-accent, #3b82f6),
      0 0 0 4px var(--evcc-surface-base, #10161f);
    cursor: pointer;
    border: none;
  }

  .token-colormix-ratio-input::-moz-range-track {
    height: 8px;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
    border: none;
  }

  .token-colormix-ratio-input::-moz-range-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--evcc-surface-base, #10161f);
    box-shadow:
      0 0 0 2px var(--evcc-accent, #3b82f6),
      0 0 0 4px var(--evcc-surface-base, #10161f);
    border: none;
    cursor: pointer;
  }

  .token-colormix-preview {
    width: 100%;
    height: 32px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
  }

  /* =========================================================
     NUMERIC CONTROL
     ========================================================= */

  .token-control-row--slider {
    width: 100%;
  }

  .slider-wrap {
    position: relative;
    width: 100%;
    padding-top: 16px;
  }

  .token-input--slider {
    width: 100%;
    height: 8px;
    appearance: none;
    -webkit-appearance: none;
    border: none;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
    outline: none;
    cursor: pointer;
  }

  .token-input--slider::-webkit-slider-runnable-track {
    height: 8px;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
  }

  .token-input--slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    margin-top: -4px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--evcc-surface-base, #10161f);
    box-shadow:
      0 0 0 2px var(--evcc-accent, #3b82f6),
      0 0 0 4px var(--evcc-surface-base, #10161f);
    cursor: pointer;
    border: none;
  }

  .token-input--slider::-moz-range-track {
    height: 8px;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
    border: none;
  }

  .token-input--slider::-moz-range-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--evcc-surface-base, #10161f);
    box-shadow:
      0 0 0 2px var(--evcc-accent, #3b82f6),
      0 0 0 4px var(--evcc-surface-base, #10161f);
    border: none;
    cursor: pointer;
  }

  /* =========================================================
     INPUTS
     ========================================================= */

  .token-input {
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    border-radius: 8px;
    padding: 6px 8px;
    color: var(--evcc-text-primary, #f0f2f5);
    font-size: 0.8rem;
    font-family: monospace;
    outline: none;
    min-width: 0;
  }

  .token-input:focus {
    border-color: var(--evcc-accent, #3b82f6);
  }

  .token-input--number {
    width: 100%;
  }

  /* =========================================================
     FOOTER
     ========================================================= */

  .evcc-view-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 4px;
    flex-shrink: 0;
    /* .footer-left / .footer-right already wrap INTERNALLY (below) — but this
       PARENT was nowrap, so the two halves could never break onto separate
       lines: 303 + 97 + 12px gap = 412, the widest floor in the view and the
       one that set the whole subtree's width. Checking the children and
       concluding "the footer already wraps" is one level too deep. */
    flex-wrap: wrap;
  }

  .footer-left,
  .footer-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  /* The four import/export chips ship an icon AND a label at every width, and
     CSS chooses between them — the same contract .evcc-mobile-nav-label uses.
     Desktop keeps the words; the icons only earn their place where vertical
     budget is scarce, so the reveal lives in mobile.js. */
  .evcc-chip-icon {
    display: none;
    /* SIZE THE BOX EXPLICITLY — do not let it derive one. This span is a flex
       ITEM of .evcc-chip wrapping an <svg> that has a viewBox but no
       width/height ATTRIBUTES, so it contributes no intrinsic size to its
       parent's content-based sizing: the span resolved to 12.5px around a
       20px glyph and the icon overflowed its own box. flex:0 0 auto alone did
       NOT fix it — shrink:0 cannot help when the flex BASE resolves small.
       Invisible on screen, since overflow is visible; caught only by the
       layout gate. Keep width/height here in step with the svg rule below. */
    flex: 0 0 auto;
    line-height: 0;
    width: 20px;
    height: 20px;
  }

  .evcc-chip-icon svg {
    display: block;
    width: 20px;
    height: 20px;
  }

  /* =========================================================
     EMPTY STATE
     ========================================================= */

  .evcc-empty {
    color: var(--evcc-text-muted, rgba(255,255,255,0.6));
    padding: 8px 4px;
    font-size: 0.85rem;
  }
`;
