/**
 * MODAL HOST styles — the document.body portal host.
 *
 * MOVED OUT OF `styles/index.js` 2026-08-21. It lived there because it is NOT a member of
 * the `STYLES` array: that array is the shadow-root cascade, and this host is a sibling of
 * the card in `document.body`, injected separately by `main.js::_updateModalHost`. Having
 * no slot in the aggregation pattern, it stayed in the aggregator — 797 lines, 75% of a
 * file whose job is to be 61 lines of index.
 *
 * `styles/index.js` re-exports this so every existing import keeps working.
 */

import { sharedChipStyles } from "./foundation.js";
import { fontTokenRules } from "./fonts.js";
import { roomAccessStyles } from "./room-access.js";
import { roomEstimateStyles } from "./room-estimate.js";
import { maintenanceModalHostStyles } from "./maintenance.js";
import { externalWizardModalStyles } from "./external-jobs.js";
import { dialogModalStyles } from "./dialog.js";
import { jobSummaryStyles } from "./job-summary.js";

/* =========================================================
   MODAL HOST STYLES
   =========================================================
   Applied to the separate document.body modal host div.
   Uses fixed positioning freely since the host is a direct
   child of body with no transform ancestors.
   ========================================================= */
export const MODAL_HOST_STYLES = `

  /* TYPEFACE — this host cannot inherit --evcc-font-family, which is declared on
     :host([data-evcc-font]) inside the card's shadow tree. main.js stamps the same
     attribute here (_applyFontAttributeTo), so the token is re-declared for this
     branch of the document. The @font-face itself is registered document-wide, so
     only the token needs restating, not the face. Without this the card switches
     typeface and its modals do not. */
  /* anchor: CND49ARX */
  ${fontTokenRules((id) => `.evcc-modal-host[data-evcc-font="${id}"]`)}
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  button {
    background: none;
    border: none;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }

  /* Form controls default to the UA font — inherit the host's (typeface-aware)
     family instead; feature rules with their own font still win. */
  input, textarea, select {
    font-family: inherit;
  }

  /* =========================================================
     MODAL TOKEN DERIVATION  (canonical -> modal family)
     =========================================================
     The modal host is mounted on document.body (and, in the render
     harness, as a shadow sibling) — DETACHED from the card's :host
     cascade, so it does NOT inherit the canonical --evcc-* seeds from
     foundation.js. Historically every --evcc-modal-* token therefore
     fell back to a HARD-CODED dark literal, which meant a theme that
     set only canonical tokens (surfaces / text / accent) left the
     modal stuck on the default palette.

     This block derives the whole modal colour family from the
     canonical tokens — the same mapping _build_release_theme_colors()
     bakes into every preloaded theme (themes/preloaded.py) — so ANY
     theme, hand- or AI-authored, themes its modals for free.

     Layering contract (why this is safe):
       - A theme writes --evcc-modal-* INLINE on .evcc-modal-host
         (apply-theme.js -> applyDynamicTheme(card._modalHost)). An
         inline declaration outranks these stylesheet rules, so an
         explicit modal override still wins.
       - Otherwise we chain to the canonical token (a theme sets those
         on the same host), so canonical-only themes flow through.
       - The final literal is the floor for a themeless body host
         (real-card default / Follow-HA, where no canonical reaches
         document.body). Floors reproduce the historical themeless render,
         except a few sub-perceptual cases that instead follow the coherent
         preloaded mapping (warning / accent-border opacities) — these appear
         in no visual baseline and differ only when NO theme is applied.
         modal-bg deliberately keeps the raw surface-base (preloaded's inline
         8% black darken still applies for the preloaded themes themselves),
         to keep the themeless default visually stable. A light companion of
         this block lives in the @media (prefers-color-scheme: light) rule
         below and supplies light floors for a themeless light-OS host.
     Size / shadow tokens are intentionally omitted — they are literal
     spec values, not canonical-derived colours.
     ========================================================= */
  /* anchor: CNMFXWX4 */
  .evcc-modal-host {
    /* Shell */
    --evcc-modal-bg:             var(--evcc-surface-base, #1c2127);
    --evcc-modal-backdrop-bg:    var(--evcc-surface-overlay, rgba(0, 0, 0, 0.72));
    --evcc-modal-border:         var(--evcc-border-default, rgba(255, 255, 255, 0.18));
    --evcc-modal-border-default: var(--evcc-border-default, rgba(255, 255, 255, 0.10));
    --evcc-modal-border-strong:  var(--evcc-border-strong, rgba(255, 255, 255, 0.18));
    --evcc-modal-border-subtle:  var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));

    /* Surfaces */
    --evcc-modal-surface-panel:   var(--evcc-surface-panel, #1c2127);
    --evcc-modal-surface-input:   var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    --evcc-modal-surface-section: var(--evcc-surface-raised, rgba(255, 255, 255, 0.04));
    --evcc-modal-input-bg:        var(--evcc-surface-input, rgba(255, 255, 255, 0.06));

    /* Header / footer fills — transparent by default, so the floor
       collapses to transparent when no canonical surface is present. */
    --evcc-modal-header-bg: color-mix(in srgb, var(--evcc-surface-panel, transparent) 86%, transparent);
    --evcc-modal-footer-bg: color-mix(in srgb, var(--evcc-surface-panel, transparent) 80%, transparent);

    /* Text */
    --evcc-modal-text-primary:   var(--evcc-text-primary, #f0f2f5);
    --evcc-modal-text-secondary: var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    --evcc-modal-text-muted:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));

    /* Accent */
    --evcc-modal-accent:        var(--evcc-accent, #3b82f6);
    --evcc-modal-accent-text:   var(--evcc-accent, #3b82f6);
    --evcc-modal-accent-bg:     color-mix(in srgb, var(--evcc-accent, #3b82f6) 22%, transparent);
    --evcc-modal-accent-border: color-mix(in srgb, var(--evcc-accent, #3b82f6) 42%, transparent);

    /* Chips */
    --evcc-modal-chip-bg:           var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    --evcc-modal-chip-border:       var(--evcc-border-default, rgba(255, 255, 255, 0.10));
    --evcc-modal-chip-text:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    --evcc-modal-chip-hover-bg:     var(--evcc-surface-panel, #1c2127);
    --evcc-modal-chip-hover-border: var(--evcc-border-strong, rgba(255, 255, 255, 0.18));
    --evcc-modal-chip-hover-text:   var(--evcc-text-primary, #f0f2f5);
    --evcc-modal-chip-active-bg:     var(--evcc-modal-accent-bg);
    --evcc-modal-chip-active-border: var(--evcc-modal-accent-border);
    --evcc-modal-chip-active-text:   var(--evcc-modal-accent-text);

    /* Warning (room-editor carpet notice) */
    --evcc-modal-warning-bg:     color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 16%, transparent);
    --evcc-modal-warning-border: color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 34%, transparent);
    --evcc-modal-warning-text:   color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 82%, white 18%);
  }

  .evcc-modal-backdrop {
    position: fixed;
    inset: 0;

    background:
      var(--evcc-modal-backdrop-bg,
      rgba(0, 0, 0, 0.72));

    backdrop-filter:
      blur(var(--evcc-modal-backdrop-blur, 8px));

    display:         flex;
    align-items:     center;
    justify-content: center;
    padding:         16px;
    /* anchor: CNJT36DZ */
    z-index:         9999;

    font-family: var(--evcc-a11y-font-family, var(--evcc-font-family, var(--paper-font-body1_-_font-family, sans-serif)));
    font-size:   14px;
    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary, #f0f2f5));
  }

  .evcc-modal {
    width:         100%;
    max-width:     480px;
    max-height:    85vh;
    display:       flex;
    flex-direction: column;
    overflow:      hidden;

    background:
      var(--evcc-modal-bg,
      #1c2127);

    border:
      1px solid var(--evcc-modal-border,
      rgba(255, 255, 255, 0.18));

    border-radius:
      var(--evcc-modal-radius, 18px);

    box-shadow:
      var(--evcc-modal-shadow,
      0 20px 60px rgba(0, 0, 0, 0.60));

    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary, #f0f2f5));

    /* =========================================================
       MODAL-LOCAL TOKEN BRIDGE
       =========================================================
       Re-declare canonical tokens as modal-prefixed fallbacks so
       all child components resolve to the modal surface rather
       than the card surface when rendered inside a modal host.
       ========================================================= */

    --evcc-surface-input:
      var(--evcc-modal-input-bg,
      var(--evcc-modal-surface-input,
      rgba(255, 255, 255, 0.06)));

    --evcc-surface-panel:
      var(--evcc-modal-surface-panel,
      #1c2127);

    --evcc-border-default:
      var(--evcc-modal-border-default,
      rgba(255, 255, 255, 0.10));

    --evcc-border-subtle:
      var(--evcc-modal-border-subtle,
      rgba(255, 255, 255, 0.08));

    --evcc-border-strong:
      var(--evcc-modal-border-strong,
      rgba(255, 255, 255, 0.18));

    --evcc-text-primary:
      var(--evcc-modal-text-primary,
      #f0f2f5);

    --evcc-text-secondary:
      var(--evcc-modal-text-secondary,
      rgba(240, 242, 245, 0.72));

    --evcc-text-muted:
      var(--evcc-modal-text-muted,
      rgba(240, 242, 245, 0.48));

    --evcc-accent:
      var(--evcc-modal-accent,
      var(--evcc-accent, #3b82f6));

    --evcc-transition-normal:
      var(--evcc-transition-normal, 150ms ease);

    --evcc-chip-height:
      var(--evcc-chip-height, 24px);

    --evcc-chip-padding:
      var(--evcc-chip-padding, 5px 14px);

    --evcc-chip-radius:
      var(--evcc-chip-radius, 999px);

    /* Map labels — pill behind centroid room names. The alpha keeps text
       legible over any backdrop (dark CV map or custom photo); dial it per map. */
    --evcc-map-label-bg:
      var(--evcc-map-label-bg, rgba(15, 18, 22, 0.60));

    --evcc-map-label-text:
      var(--evcc-map-label-text, #ffffff);

    --evcc-map-label-text-selected:
      var(--evcc-map-label-text-selected, #ffffff);

    --evcc-map-label-order-text:
      var(--evcc-map-label-order-text, #ffffff);

    --evcc-map-tooltip-bg:
      var(--evcc-map-tooltip-bg, rgba(15, 18, 22, 0.88));

    --evcc-map-tooltip-border:
      var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.12));

    --evcc-map-tooltip-text:
      var(--evcc-map-tooltip-text, #f0f2f5);

    --evcc-map-tooltip-hint:
      var(--evcc-map-tooltip-hint, rgba(240, 242, 245, 0.55));

    --evcc-map-compose-selected-stroke:
      var(--evcc-map-compose-selected-stroke, #ffffff);

    --evcc-map-compose-cut-fill:
      var(--evcc-map-compose-cut-fill, rgba(255, 92, 92, 0.12));

    --evcc-map-compose-cut-selected-fill:
      var(--evcc-map-compose-cut-selected-fill, rgba(255, 92, 92, 0.20));

    --evcc-map-vertex-selected-glow:
      var(--evcc-map-vertex-selected-glow, rgba(255, 221, 0, 0.9));

    /* Map_state_source overlay layers (Wave 3c). Defaults chosen to read over a
       live-map backdrop; tune per theme in the Theme editor's "Map" group. */
    --evcc-map-ov-current:
      var(--evcc-map-ov-current, rgba(0, 229, 255, 0.85));
    --evcc-map-ov-nogo:
      var(--evcc-map-ov-nogo, rgba(255, 59, 48, 0.85));
    --evcc-map-ov-nomop:
      var(--evcc-map-ov-nomop, rgba(10, 132, 255, 0.85));
    --evcc-map-ov-wall:
      var(--evcc-map-ov-wall, rgba(255, 214, 10, 0.9));
    --evcc-map-ov-zone:
      var(--evcc-map-ov-zone, rgba(52, 211, 153, 0.85));
    --evcc-map-ov-path:
      var(--evcc-map-ov-path, rgba(255, 255, 255, 0.8));
    --evcc-map-ov-robot:
      var(--evcc-map-ov-robot, #00e5ff);
    --evcc-map-ov-dock:
      var(--evcc-map-ov-dock, #a3e635);
    --evcc-map-ov-obstacle:
      var(--evcc-map-ov-obstacle, rgba(251, 191, 36, 0.95));
    /* Saved zones shipped after this block was written and their overlay colour
       was referenced but never declared, so it always fell back and never showed
       up in the Theme editor beside its siblings. Values are the fallbacks that
       were already rendering, so defining them changes nothing on screen. */
    --evcc-map-ov-savedzone:
      var(--evcc-map-ov-savedzone, rgba(167, 139, 250, 0.85));
    --evcc-map-ov-savedzone-text:
      var(--evcc-map-ov-savedzone-text, #ffffff);
    --evcc-map-ov-area-text:
      var(--evcc-map-ov-area-text, #ffffff);

    --evcc-chip-border:
      var(--evcc-modal-chip-border,
      var(--evcc-border-default));

    --evcc-chip-bg:
      var(--evcc-modal-chip-bg,
      var(--evcc-surface-input));

    --evcc-chip-text:
      var(--evcc-modal-chip-text,
      var(--evcc-text-secondary));

    --evcc-chip-font-size:
      var(--evcc-chip-font-size, 0.82rem);

    --evcc-chip-font-weight:
      var(--evcc-chip-font-weight, 500);

    --evcc-chip-hover-bg:
      var(--evcc-modal-chip-hover-bg,
      var(--evcc-surface-panel));

    --evcc-chip-hover-text:
      var(--evcc-modal-chip-hover-text,
      var(--evcc-text-primary));

    --evcc-chip-hover-border:
      var(--evcc-modal-chip-hover-border,
      var(--evcc-border-strong));

    --evcc-chip-icon-height:
      var(--evcc-chip-icon-height, 24px);

    --evcc-chip-icon-padding:
      var(--evcc-chip-icon-padding, 4px 8px);

    --evcc-chip-icon-size:
      var(--evcc-chip-icon-size, 0.8rem);
  }

  .evcc-modal-header {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    padding:         var(--evcc-modal-padding, 14px 16px 12px);
    border-bottom:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-subtle));
    flex-shrink:     0;
    gap:             12px;
    background:
      var(--evcc-modal-header-bg,
      transparent);
  }

  .evcc-modal-title {
    font-size:      1rem;
    font-weight:    700;
    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary));
    overflow:       hidden;
    text-overflow:  ellipsis;
    white-space:    nowrap;
  }

  .evcc-room-editor-fields,
  .evcc-editor-field-groups,
  .evcc-modal-body {
    flex:           1;
    min-height:     0;       /* Required for flex children to actually
                                shrink-and-scroll instead of growing
                                past their parent's max-height. */
    overflow-y:     auto;
    padding:        var(--evcc-modal-padding, 20px);
    display:        flex;
    flex-direction: column;
    gap:            var(--evcc-modal-section-gap, 28px);
  }

  /* Export / Import theme-JSON modal — wider, with a monospace text area.
     Canonical tokens resolve to the modal-derived family inside .evcc-modal. */
  .evcc-modal--theme-json { max-width: 600px; }

  .evcc-modal--theme-json .evcc-modal-body { gap: 10px; }

  .evcc-theme-json-hint {
    margin: 0;
    font-size: 0.85rem;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
  }

  .evcc-theme-json-area {
    width: 100%;
    min-height: 240px;
    max-height: 48vh;
    resize: vertical;
    font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--evcc-text-primary, #f0f2f5);
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.16));
    border-radius: var(--evcc-radius-inner, 10px);
    padding: 10px 12px;
    white-space: pre;
    overflow: auto;
  }

  .evcc-theme-json-area:focus {
    outline: none;
    border-color: var(--evcc-accent, #3b82f6);
  }

  .evcc-theme-json-error {
    margin: 0;
    font-size: 0.82rem;
    color: var(--evcc-sem-error, #e05252);
  }

  .evcc-editor-field-group {
    display:        flex;
    flex-direction: column;
    gap:            12px;
  }

  .evcc-field-label {
    font-size:      0.72rem;
    font-weight:    600;
    color:
      var(--evcc-modal-text-muted,
      var(--evcc-text-muted));
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding-top:    4px;
  }

  /* anchor: CN0EX0CH */
  ${sharedChipStyles}

  .evcc-chip--save {
    background:
      var(--evcc-modal-chip-active-bg,
      var(--evcc-modal-accent-bg,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 22%, transparent)));

    color:
      var(--evcc-modal-chip-active-text,
      var(--evcc-modal-accent-text,
      var(--evcc-modal-accent, var(--evcc-accent))));

    border-color:
      var(--evcc-modal-chip-active-border,
      var(--evcc-modal-accent-border,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 45%, transparent)));

    font-weight: 600;
  }

  .evcc-chip--custom {
    background:
      var(--evcc-modal-chip-bg,
      color-mix(in srgb, var(--evcc-modal-text-muted, var(--evcc-text-muted)) 18%, transparent));

    color:
      var(--evcc-modal-chip-text,
      var(--evcc-modal-warning-text,
      var(--evcc-text-secondary)));

    border-color:
      var(--evcc-modal-chip-border,
      var(--evcc-modal-warning-border,
      var(--evcc-border-strong)));

    font-style: italic;
    cursor:     default;
  }

  /* anchor: CNE5BJEK */
  ${maintenanceModalHostStyles}
  ${roomAccessStyles}
  ${roomEstimateStyles}
  ${jobSummaryStyles}
  ${externalWizardModalStyles}
  ${dialogModalStyles}

  .evcc-modal-footer {
    display:         flex;
    align-items:     center;
    justify-content: flex-end;
    gap:             8px;
    padding:         var(--evcc-modal-padding, 12px 16px 14px);
    border-top:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-subtle));
    flex-shrink:     0;
    background:
      var(--evcc-modal-footer-bg,
      transparent);
  }

  .evcc-room-editor-include-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             12px;
    padding:         12px 20px;
    border-bottom:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-subtle));
    flex-shrink:     0;
  }

  .evcc-room-editor-include-label {
    font-size: 0.88rem;
    color:
      var(--evcc-modal-text-secondary,
      var(--evcc-text-secondary));
  }

  .evcc-room-profile-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-room-profile-meta {
    font-size: 0.80rem;
    color:
      var(--evcc-modal-text-muted,
      var(--evcc-text-muted));
    line-height: 1.45;
  }

  .evcc-chip--toggle-include {
    flex-shrink: 0;
  }

  .evcc-chip--toggle-include.active {
    background:
      var(--evcc-chip-included-bg,
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 18%, transparent));

    color:
      var(--evcc-chip-included-text,
      var(--evcc-sem-success, #22c55e));

    border-color:
      var(--evcc-chip-included-border,
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 40%, transparent));
  }

  .evcc-room-editor-carpet-notice {
    margin:        0 16px;
    padding:       8px 12px;
    border-radius: 6px;
    background:
      var(--evcc-modal-warning-bg,
      color-mix(in srgb, var(--evcc-modal-warning-text, var(--evcc-sem-warning, #f59e0b)) 12%, transparent));

    border:
      1px solid var(--evcc-modal-warning-border,
      color-mix(in srgb, var(--evcc-modal-warning-text, var(--evcc-sem-warning, #f59e0b)) 30%, transparent));

    color:
      var(--evcc-modal-warning-text,
      var(--evcc-sem-warning, #f59e0b));

    font-size:   0.82rem;
    font-weight: 500;
    flex-shrink: 0;
  }

  /* anchor: CN0M3MW9 */
  @media (prefers-color-scheme: light) {
    /* Light companion to the .evcc-modal-host derivation block above. The body
       modal host is detached from :host, so when themeless the canonical-derived
       defaults resolve to their DARK floors — which would shadow this media
       query's light fallbacks and leave a light-OS Follow-HA user with a dark
       modal. Re-derive the surface/text/border family here with LIGHT floors.
       A theme still wins (it sets --evcc-modal-* / canonical inline on the host,
       and the canonical chain is honoured in either scheme); the light literals
       only apply to a genuinely themeless light-OS host. Accent / warning /
       chip-active tokens are scheme-neutral and inherit the block above. */
    /* anchor: CNR1K8KC */
    .evcc-modal-host {
      --evcc-modal-bg:             var(--evcc-surface-base, #ffffff);
      --evcc-modal-backdrop-bg:    var(--evcc-surface-overlay, rgba(15, 23, 42, 0.28));
      --evcc-modal-border:         var(--evcc-border-default, rgba(15, 23, 42, 0.12));
      --evcc-modal-border-default: var(--evcc-border-default, rgba(15, 23, 42, 0.10));
      --evcc-modal-border-strong:  var(--evcc-border-strong, rgba(15, 23, 42, 0.16));
      --evcc-modal-border-subtle:  var(--evcc-border-subtle, rgba(15, 23, 42, 0.06));

      --evcc-modal-surface-panel:   var(--evcc-surface-panel, #ffffff);
      --evcc-modal-surface-input:   var(--evcc-surface-input, rgba(15, 23, 42, 0.05));
      --evcc-modal-surface-section: var(--evcc-surface-raised, rgba(15, 23, 42, 0.03));
      --evcc-modal-input-bg:        var(--evcc-surface-input, rgba(15, 23, 42, 0.05));

      --evcc-modal-header-bg: color-mix(in srgb, var(--evcc-surface-panel, transparent) 86%, transparent);
      --evcc-modal-footer-bg: color-mix(in srgb, var(--evcc-surface-panel, transparent) 80%, transparent);

      --evcc-modal-text-primary:   var(--evcc-text-primary, #0f172a);
      --evcc-modal-text-secondary: var(--evcc-text-secondary, rgba(15, 23, 42, 0.74));
      --evcc-modal-text-muted:     var(--evcc-text-muted, rgba(15, 23, 42, 0.50));

      --evcc-modal-chip-bg:           var(--evcc-surface-input, rgba(15, 23, 42, 0.05));
      --evcc-modal-chip-border:       var(--evcc-border-default, rgba(15, 23, 42, 0.10));
      --evcc-modal-chip-text:         var(--evcc-text-secondary, rgba(15, 23, 42, 0.74));
      --evcc-modal-chip-hover-bg:     var(--evcc-surface-panel, #ffffff);
      --evcc-modal-chip-hover-border: var(--evcc-border-strong, rgba(15, 23, 42, 0.16));
      --evcc-modal-chip-hover-text:   var(--evcc-text-primary, #0f172a);
    }

    .evcc-modal {
      background:
        var(--evcc-modal-bg,
        #ffffff);

      border:
        1px solid var(--evcc-modal-border,
        rgba(15, 23, 42, 0.12));

      box-shadow:
        var(--evcc-modal-shadow,
        0 20px 60px rgba(0, 0, 0, 0.22));

      color:
        var(--evcc-modal-text-primary,
        #0f172a);

      --evcc-surface-panel:
        var(--evcc-modal-surface-panel,
        #ffffff);

      --evcc-surface-input:
        var(--evcc-modal-input-bg,
        var(--evcc-modal-surface-input,
        rgba(15, 23, 42, 0.05)));

      --evcc-border-default:
        var(--evcc-modal-border-default,
        rgba(15, 23, 42, 0.10));

      --evcc-border-subtle:
        var(--evcc-modal-border-subtle,
        rgba(15, 23, 42, 0.06));

      --evcc-border-strong:
        var(--evcc-modal-border-strong,
        rgba(15, 23, 42, 0.16));

      --evcc-text-primary:
        var(--evcc-modal-text-primary,
        #0f172a);

      --evcc-text-secondary:
        var(--evcc-modal-text-secondary,
        rgba(15, 23, 42, 0.74));

      --evcc-text-muted:
        var(--evcc-modal-text-muted,
        rgba(15, 23, 42, 0.50));
    }

    .evcc-modal-backdrop {
      background:
        var(--evcc-modal-backdrop-bg,
        rgba(15, 23, 42, 0.28));
    }
  }

  /* =========================================================
     MOBILE — bottom-sheet layout
     =========================================================
     At phone widths the centered desktop modal wastes vertical
     space and crops content that exceeds 85vh without an obvious
     scroll affordance. Switch to a bottom-sheet pattern:
     full-width, pinned to bottom, drag handle, sticky header +
     footer so the user always sees where they are.

     The @media query lives inside MODAL_HOST_STYLES rather than
     in mobile.js because the modal host is mounted on document.body
     (not inside the card shadow root), so the shell-data-attribute
     selectors in mobile.js never reach it.
     ========================================================= */
  @media (max-width: 600px), (max-height: 500px) {
    .evcc-modal-backdrop {
      /* Pin to bottom — modal rises from the edge of the screen.
         Zero padding so the sheet can use the full width and
         extend to viewport bottom for a true bottom-sheet feel. */
      align-items: flex-end;
      padding: 0;
    }

    .evcc-modal {
      max-width:    100%;
      width:        100%;
      max-height:   92vh;
      border-radius: 16px 16px 0 0;
      border-bottom-left-radius:  0;
      border-bottom-right-radius: 0;
      border-bottom-width: 0;
      box-shadow:   0 -8px 32px rgba(0, 0, 0, 0.55);
      /* Pad bottom for iOS home-indicator safe area. */
      padding-bottom: env(safe-area-inset-bottom, 0px);
    }

    /* No drag handle. An earlier version drew a pill at the top
       of the sheet to signal "this is dismissible" but swipe-to-
       dismiss was never wired, so the affordance promised a
       gesture that didn't exist. Removed entirely; the X button
       in the header is the canonical close path. Add back when /
       if a real swipe gesture handler ships. */

    /* Sticky header — title + close button stay visible while
       the body scrolls. Background matches modal so scrolled
       content doesn't bleed through. */
    .evcc-modal-header {
      position:  sticky;
      top:       0;
      z-index:   2;
      background: var(--evcc-modal-bg, #1c2127);
    }

    /* Sticky footer — action buttons stay reachable without
       scrolling down. Top border separates from scrolled content. */
    .evcc-modal-footer {
      position:  sticky;
      bottom:    0;
      z-index:   2;
      background: var(--evcc-modal-bg, #1c2127);
      border-top:
        1px solid var(--evcc-modal-border-subtle,
        var(--evcc-border-default, rgba(255, 255, 255, 0.12)));
    }

    /* Body: a touch of extra bottom padding so the last row of
       content doesn't sit flush against the sticky footer when
       scrolled to the bottom. */
    .evcc-modal-body {
      padding-bottom: 20px;
    }
  }

  /* =========================================================
     REORDER MODAL — current order + preview chip rows
     =========================================================
     "Currently" / "After move" sections in the position selector
     modal show every item in the list as a small chip with its
     position number. Active item is filled with the accent color
     so the user can spot it instantly in both rows.

     Rules live here (not in styles/order.js) because the modal
     host is body-attached, outside the card shadow root.
     ========================================================= */

  .evcc-order-preview-row {
    display:        flex;
    flex-wrap:      wrap;
    gap:            6px;
  }

  .evcc-order-preview-chip {
    display:        inline-flex;
    align-items:    center;
    gap:            6px;
    padding:        4px 10px 4px 4px;
    border-radius:  999px;
    font-size:      0.8rem;
    line-height:    1.2;
    background:     var(--evcc-surface-subtle, rgba(255,255,255,0.04));
    border:         1px solid var(--evcc-border-subtle, rgba(255,255,255,0.10));
    color:          var(--evcc-text-secondary);
  }

  .evcc-order-preview-chip-pos {
    display:        inline-flex;
    align-items:    center;
    justify-content: center;
    min-width:      18px;
    height:         18px;
    padding:        0 5px;
    border-radius:  999px;
    font-size:      0.72rem;
    font-weight:    700;
    background:     var(--evcc-surface-subtle, rgba(255,255,255,0.08));
    color:          var(--evcc-text-muted);
  }

  .evcc-order-preview-chip--active {
    background:     color-mix(in srgb, var(--evcc-accent, #60a5fa) 18%, transparent);
    border-color:   color-mix(in srgb, var(--evcc-accent, #60a5fa) 60%, transparent);
    color:          var(--evcc-text-primary);
    font-weight:    600;
  }

  .evcc-order-preview-chip--active .evcc-order-preview-chip-pos {
    background:     var(--evcc-accent, #60a5fa);
    color:          var(--evcc-text-on-accent, #ffffff);
  }
`;
