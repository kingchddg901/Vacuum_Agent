/**
 * ============================================================
 * STYLES: MODALS  ⚠️ DEPRECATED — DO NOT EDIT
 * ============================================================
 *
 * STATUS
 * ------
 * This file is bundled into the shadow-root stylesheet (STYLES) but
 * its rules never match anything. All modal markup is mounted to
 * document.body via _renderModals() in main.js, so styles that live
 * in the card's shadow root can't reach them.
 *
 * The LIVE modal styles are MODAL_HOST_STYLES in src/styles/index.js,
 * injected into the body-mounted modal host directly. If you're trying
 * to fix a modal styling bug, edit THAT file, not this one.
 *
 * This file is kept for one release cycle so anything that turns out
 * to depend on it (theme override targeting a specific selector via
 * the wrong stylesheet, etc.) can be caught. Delete in v0.10.0+ along
 * with the import in src/styles/index.js.
 *
 * ============================================================
 *
 * Historical PURPOSE (no longer accurate)
 * ---------------------------------------
 * Styles for all modal overlays in the card.
 *
 * This file owns:
 * - .evcc-modal-backdrop     — full-card dark overlay
 * - .evcc-modal              — modal card shell
 * - .evcc-modal-header       — title + close button row
 * - .evcc-modal-body         — scrollable content area
 * - .evcc-modal-footer       — action buttons row
 * - .evcc-editor-field-group — labelled field group
 * - Room editor specifics    — carpet notice, custom chip
 *
 *
 * WHAT THIS FILE SHOULD NOT CONTAIN
 * ----------------------------------
 * - room card styles (rooms.js)
 * - maintenance styles (maintenance.js)
 * - theme editor styles (theme.js)
 *
 *
 * IMPORTANT
 * ---------
 * This file is fully modal-authoritative.
 *
 * That means:
 * - modal tokens resolve first
 * - foundation tokens are only fallbacks
 * - no direct Home Assistant theme variables appear here
 *
 *
 * DEFAULT MODAL HARDENING
 * -----------------------
 * Cards may inherit translucency from HA themes, but modals
 * should remain readable and visually separated by default.
 *
 * For that reason, the modal shell uses a solid fallback base
 * instead of deriving from potentially translucent card tokens.
 *
 * ============================================================
 */

export const modalStyles = `

  /* =========================================================
     BACKDROP
     ========================================================= */

  .evcc-modal-backdrop {
    position: absolute;
    inset:    0;

    background:
      var(--evcc-modal-backdrop-bg,
      rgba(0, 0, 0, 0.72));

    backdrop-filter:
      blur(var(--evcc-modal-backdrop-blur, 8px));

    display:         flex;
    align-items:     flex-start;
    justify-content: center;
    padding:         60px 16px 16px;
    z-index:         999;
  }

  /* =========================================================
     MODAL SHELL
     ========================================================= */

  .evcc-modal {
    background:
      var(--evcc-modal-bg,
      #1c2127);

    border:
      1px solid var(--evcc-modal-border,
      rgba(255, 255, 255, 0.18));

    border-radius: var(--evcc-modal-radius, 18px);

    box-shadow:
      var(--evcc-modal-shadow,
      0 20px 60px rgba(0, 0, 0, 0.60));

    width:         100%;
    max-width:     480px;
    max-height:    calc(100% - 76px);
    display:       flex;
    flex-direction: column;
    overflow:      hidden;

    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary));
  }

  /* =========================================================
     HEADER
     ========================================================= */

  .evcc-modal-header {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    padding:         var(--evcc-modal-padding, 14px 16px 12px);
    border-bottom:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-default));
    flex-shrink:     0;
    gap:             12px;
    background:
      var(--evcc-modal-header-bg,
      transparent);
  }

  .evcc-modal-title {
    font-size:      1rem;
    font-weight:    600;
    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary));
    min-width:      0;
    overflow:       hidden;
    text-overflow:  ellipsis;
    white-space:    nowrap;
  }

  /* =========================================================
     BODY
     ========================================================= */

  .evcc-modal-body {
    flex:           1;
    min-height:     0;
    overflow-y:     auto;
    padding:        var(--evcc-modal-padding, 14px 16px);
    display:        flex;
    flex-direction: column;
    gap:            var(--evcc-modal-section-gap, 16px);
    background:
      var(--evcc-modal-surface-section,
      transparent);
  }

  /* =========================================================
     FOOTER
     ========================================================= */

  .evcc-modal-footer {
    display:         flex;
    align-items:     center;
    justify-content: flex-end;
    gap:             8px;
    padding:         var(--evcc-modal-padding, 12px 16px 14px);
    border-top:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-default));
    flex-shrink:     0;
    background:
      var(--evcc-modal-footer-bg,
      transparent);
  }

  /* =========================================================
     SAVE CHIP (MODAL ACTION)
     ========================================================= */

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

  .evcc-chip--save:hover {
    background:
      var(--evcc-modal-chip-hover-bg,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 34%, transparent));

    color:
      var(--evcc-modal-chip-hover-text,
      var(--evcc-modal-accent-text,
      var(--evcc-modal-accent, var(--evcc-accent))));

    border-color:
      var(--evcc-modal-chip-hover-border,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 60%, transparent));
  }

  /* =========================================================
     FIELD GROUPS
     ========================================================= */

  .evcc-editor-field-group {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-field-label {
    font-size:      0.75rem;
    font-weight:    600;
    color:
      var(--evcc-modal-text-muted,
      var(--evcc-text-muted));
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* =========================================================
     ROOM EDITOR SPECIFICS
     ========================================================= */

  .evcc-room-editor-carpet-notice {
    display:       flex;
    align-items:   center;
    gap:           8px;
    padding:       8px 12px;
    border-radius: 10px;

    background:
      var(--evcc-modal-warning-bg,
      color-mix(in srgb, var(--evcc-modal-warning-text, var(--evcc-sem-warning)) 14%, transparent));

    border:
      1px solid var(--evcc-modal-warning-border,
      color-mix(in srgb, var(--evcc-modal-warning-text, var(--evcc-sem-warning)) 35%, transparent));

    color:
      var(--evcc-modal-warning-text,
      var(--evcc-sem-warning));

    font-size:   0.8rem;
    font-weight: 500;
  }

  .evcc-room-editor-transition-callout {
    padding:       7px 11px;
    border-radius: 8px;
    background:    color-mix(in srgb, var(--evcc-text-muted) 10%, transparent);
    border:        1px solid color-mix(in srgb, var(--evcc-text-muted) 22%, transparent);
    color:         var(--evcc-text-muted);
    font-size:     0.78rem;
    line-height:   1.4;
    margin-bottom: 6px;
  }

  /* Read-only mop-state indicator (tank-driven brands, e.g. Roborock). */
  .evcc-room-editor-mopstate {
    padding:       8px 11px;
    border-radius: 8px;
    font-size:     0.82rem;
    font-weight:   600;
    line-height:   1.3;
  }

  .evcc-room-editor-mopstate.mopping {
    background: color-mix(in srgb, var(--evcc-accent, #3b9eff) 16%, transparent);
    border:    1px solid color-mix(in srgb, var(--evcc-accent, #3b9eff) 34%, transparent);
    color:     var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-room-editor-mopstate.vacuum {
    background: color-mix(in srgb, var(--evcc-text-muted) 10%, transparent);
    border:    1px solid color-mix(in srgb, var(--evcc-text-muted) 22%, transparent);
    color:     var(--evcc-text-muted);
  }

  /* Muted helper note under a field (e.g. whole-run passes on Roborock). */
  .evcc-room-editor-field-note {
    margin-top:  6px;
    color:       var(--evcc-text-muted);
    font-size:   0.74rem;
    line-height: 1.4;
  }

  .evcc-chip--custom {
    background:
      var(--evcc-modal-chip-bg,
      color-mix(in srgb, var(--evcc-modal-text-muted, var(--evcc-text-muted)) 14%, transparent));

    color:
      var(--evcc-modal-chip-text,
      var(--evcc-modal-text-secondary, var(--evcc-text-secondary)));

    border-color:
      var(--evcc-modal-chip-border,
      var(--evcc-modal-border-strong, var(--evcc-border-strong)));

    font-style: italic;
    cursor:     default;
    opacity:    1;
  }

  /* =========================================================
     LIGHT THEME HARDENING
     =========================================================
     Keep default modal shells visually solid even when the HA
     theme is very light. Custom modal themes can still
     override everything through modal tokens.
     ========================================================= */

  @media (prefers-color-scheme: light) {
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
    }

    .evcc-modal-backdrop {
      background:
        var(--evcc-modal-backdrop-bg,
        rgba(15, 23, 42, 0.28));
    }
  }

  /* =========================================================
     MOBILE
     ========================================================= */

  @media (max-width: 480px) {
    .evcc-modal {
      max-height:    calc(100% - 16px);
      border-radius: var(--evcc-modal-radius, 16px);
    }

    .evcc-modal-backdrop {
      padding:     8px;
      align-items: flex-end;
    }
  }
`;