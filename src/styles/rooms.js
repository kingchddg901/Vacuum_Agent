/**
 * ============================================================
 * STYLES: ROOMS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Visual styles for the Rooms view.
 *
 * Design matches the original card's room card language:
 * - rounded room cards
 * - three-row header structure
 * - labeled detail rows
 * - status pills at bottom
 * - gradient enabled state with glow shadow
 *
 * IMPORTANT
 * ---------
 * This file is fully committed to the normalized EVCC token
 * system.
 *
 * That means:
 * - no direct Home Assistant semantic colors here
 * - no direct warning/success/accent color usage
 * - no ad-hoc surface tokens
 *
 * All visuals resolve through:
 * - component tokens
 * - semantic tokens
 * - foundation tokens
 *
 * This keeps the Rooms surface aligned with the future theme
 * editor, queue system, estimate system, and modal system.
 *
 * ============================================================
 */

export const roomStyles = `

  /* =========================================================
     ACTION BAR
     ========================================================= */

  .evcc-rooms-action-bar {
    display:        flex;
    flex-direction: column;
    gap:            var(--evcc-section-gap, 10px);
    padding-bottom: var(--evcc-space-md, 12px);
    border-bottom:  1px solid var(--evcc-border-default);
    margin-bottom:  var(--evcc-space-md, 12px);
  }

  .evcc-rooms-bar-top {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             var(--evcc-space-md, 12px);
    flex-wrap:       wrap;
  }

  .evcc-rooms-queue-summary {
    display:     flex;
    align-items: baseline;
    gap:         5px;
  }

  .evcc-rooms-queue-count {
    font-size:   1rem;
    font-weight: 600;
    color:       var(--evcc-text-primary);
  }

  .evcc-rooms-queue-label {
    font-size: 0.8rem;
    color:     var(--evcc-text-muted);
  }

  /* =========================================================
     ACTION CHIPS
     ========================================================= */

  .evcc-chip--start:not([disabled]) {
    background:   var(--evcc-chip-success-bg,
                    color-mix(in srgb, var(--evcc-sem-success) 36%, transparent));
    color:        var(--evcc-chip-success-text, var(--evcc-text-primary));
    border-color: var(--evcc-chip-success-border,
                    color-mix(in srgb, var(--evcc-sem-success) 55%, transparent));
    font-weight:  600;
  }

  .evcc-chip--start:not([disabled]):hover {
    background:   color-mix(in srgb, var(--evcc-sem-success) 50%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-success) 70%, transparent);
  }

  .evcc-chip--start-warn {
    background:   var(--evcc-chip-warning-bg,
                    color-mix(in srgb, var(--evcc-sem-warning) 26%, transparent));
    color:        var(--evcc-chip-warning-text, var(--evcc-sem-warning));
    border-color: var(--evcc-chip-warning-border,
                    color-mix(in srgb, var(--evcc-sem-warning) 42%, transparent));
    font-weight:  600;
  }

  .evcc-chip--start-warn:hover {
    background:   color-mix(in srgb, var(--evcc-sem-warning) 34%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 56%, transparent);
  }

  .evcc-chip--cancel-run {
    background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 18%, transparent);
    color:        var(--evcc-sem-error, #ef4444);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 42%, transparent);
    font-weight:  600;
  }

  .evcc-chip--cancel-run:hover {
    background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 26%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 58%, transparent);
  }

  .evcc-chip--confirm-flash {
    animation: evcc-room-confirm-pulse 1.25s ease-in-out infinite;
  }

  .evcc-rooms-block-reason {
    font-size: 0.8rem;
    color:     var(--evcc-sem-warning);
  }

  /* Inline banner shown while the cancel-run two-tap confirmation
     is in flight. Pairs with the pulsing "Confirm Cancel" chip. */
  .evcc-rooms-cancel-warning {
    margin-top: 6px;
    padding: 8px 10px;
    border-radius: var(--evcc-radius-inner, 8px);
    background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 38%, transparent);
    color: var(--evcc-text-primary);
    font-size: 0.82rem;
    line-height: 1.35;
  }

  .evcc-rooms-inline-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .evcc-start-preflight-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    border-radius: var(--evcc-radius-panel, 14px);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-warning) 38%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-warning) 10%, transparent);
  }

  .evcc-start-preflight-header {
    font-size: 0.86rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-start-preflight-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-start-preflight-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-start-preflight-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-muted);
  }

  .evcc-start-preflight-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-start-preflight-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
    font-size: 0.78rem;
  }

  .evcc-start-preflight-room {
    font-weight: 600;
    color: var(--evcc-text-primary);
  }

  .evcc-start-preflight-reason {
    color: var(--evcc-text-secondary);
    text-align: right;
  }

  .evcc-queue-empty {
    font-size: 0.8rem;
    color:     var(--evcc-text-muted);
  }

  /* =========================================================
     ACTIVE JOB
     ========================================================= */

  .evcc-active-job {
    display:        flex;
    flex-direction: column;
    gap:            8px;
    padding:        10px 12px;
    margin-bottom:  var(--evcc-space-md, 12px);
    border-radius:  var(--evcc-radius-panel, 14px);
    border:         1px solid var(--evcc-status-cleaning-border,
                    color-mix(in srgb, var(--evcc-sem-success) 35%, transparent));
    background:     var(--evcc-status-cleaning-bg,
                    color-mix(in srgb, var(--evcc-sem-success) 10%, transparent));
  }

  .evcc-active-job-header {
    display:     flex;
    align-items: center;
    gap:         8px;
  }

  .evcc-active-job-label {
    font-size:   0.82rem;
    font-weight: 600;
    color:       var(--evcc-status-cleaning-text, var(--evcc-sem-success));
  }

  .evcc-active-job-pulse {
    width:         8px;
    height:        8px;
    border-radius: 50%;
    background:    var(--evcc-status-dot-cleaning, var(--evcc-sem-success));
    box-shadow:    0 0 0 0 color-mix(in srgb, var(--evcc-status-dot-cleaning, var(--evcc-sem-success)) 55%, transparent);
    animation:     evccPulse var(--evcc-status-pulse-duration, 1.6s) infinite;
  }

  @keyframes evccPulse {
    0%   { box-shadow: 0 0 0 0 color-mix(in srgb, var(--evcc-status-dot-cleaning, var(--evcc-sem-success)) 45%, transparent); }
    70%  { box-shadow: 0 0 0 10px transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
  }

  @keyframes evcc-room-confirm-pulse {
    0%, 100% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--evcc-sem-warning) 0%, transparent);
    }

    50% {
      box-shadow: 0 0 0 4px color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent);
    }
  }

  /* =========================================================
     ROOM CARD
     ========================================================= */

  .evcc-room-card {
    position:        relative;
    isolation:       isolate;   /* stacking context: lets the texture sit at z-index:-1, beneath the progress fill */
    overflow:        hidden;
    display:         flex;
    flex-direction:  column;
    gap:             var(--evcc-card-gap, 10px);
    min-height:      var(--evcc-card-min-height, 120px);
    padding:         var(--evcc-card-padding, 12px);
    border-radius:   var(--evcc-radius-card, 18px);
    border:          1px solid var(--evcc-border-default);
    background:      color-mix(in srgb, var(--evcc-surface-card) 84%, white 16%);
    box-shadow:      var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
    transition:
      transform      var(--evcc-transition-normal, 150ms ease),
      border-color   var(--evcc-transition-normal, 150ms ease),
      box-shadow     var(--evcc-transition-normal, 150ms ease),
      background     var(--evcc-transition-normal, 150ms ease);
    cursor:          pointer;
  }

  .evcc-room-card.is-enabled {
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--evcc-accent) 14%, transparent),
        color-mix(in srgb, var(--evcc-surface-card) 84%, white 16%)
      );
    box-shadow:
      0 0 0 1px color-mix(in srgb, var(--evcc-accent) 16%, transparent),
      var(--evcc-shadow-hover, 0 10px 20px rgba(0, 0, 0, 0.18));
  }

  .evcc-room-card:hover {
    transform:    translateY(calc(-1 * var(--evcc-hover-lift, 1px)));
    border-color: var(--evcc-border-strong);
  }

  .evcc-room-card:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--evcc-accent) 65%, transparent);
    outline-offset: 2px;
  }

  .evcc-room-card.is-enabled:hover {
    border-color: color-mix(in srgb, var(--evcc-accent) 52%, transparent);
  }

  .evcc-room-row {
    display: flex;
    align-items: center;
    width: 100%;
  }

  .evcc-room-row-1 {
    justify-content: flex-end;
  }

  .evcc-room-row-2 {
    justify-content: flex-start;
  }

  .evcc-room-controls {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .evcc-room-settings-hit-target {
    appearance: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    margin: -4px;
    border: none;
    background: transparent;
    color: inherit;
    cursor: pointer;
    border-radius: 999px;
    position: relative;
    z-index: 2;
  }

  .evcc-room-settings-hit-target:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--evcc-accent) 65%, transparent);
    outline-offset: 2px;
  }

  .evcc-room-settings-button {
    pointer-events: none;
  }

  .evcc-room-name {
    font-size:     0.95rem;
    font-weight:   700;
    color:         var(--evcc-text-primary);
    line-height:   1.2;
    min-width:     0;
    overflow:      hidden;
    text-overflow: ellipsis;
    white-space:   nowrap;
  }

  /* =========================================================
     ROOM DETAILS
     ========================================================= */

  .evcc-room-details {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-room-detail-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             10px;
    flex-wrap:       wrap;
  }

  .evcc-room-detail-label {
    font-size:   0.74rem;
    font-weight: 700;
    color:       var(--evcc-text-muted);
    min-width:   0;
  }

  /* =========================================================
     ROOM SETTING CHIPS
     ========================================================= */

  .evcc-room-setting-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       var(--evcc-chip-gap, 5px);
  }

  .evcc-room-setting-chip {
    --evcc-chip-height:      24px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.73rem;
    --evcc-chip-font-weight: 500;
    --evcc-chip-bg:          var(--evcc-room-chip-bg, rgba(255, 255, 255, 0.06));
    --evcc-chip-border:      var(--evcc-room-chip-border, rgba(255, 255, 255, 0.10));
    --evcc-chip-text:        var(--evcc-room-chip-text, var(--evcc-text-secondary));
  }

  .evcc-room-setting-chip--profile {
    --evcc-chip-bg:     var(--evcc-profile-chip-bg, rgba(255, 255, 255, 0.08));
    --evcc-chip-border: var(--evcc-profile-chip-border, rgba(255, 255, 255, 0.14));
    --evcc-chip-text:   var(--evcc-profile-chip-text, var(--evcc-text-primary));
    font-weight: 600;
  }

  .evcc-room-setting-chip--profile.is-custom {
    --evcc-chip-bg:     var(--evcc-profile-chip-custom-bg,
                          color-mix(in srgb, var(--evcc-sem-warning) 14%, transparent));
    --evcc-chip-border: var(--evcc-profile-chip-custom-border,
                          color-mix(in srgb, var(--evcc-sem-warning) 30%, transparent));
    --evcc-chip-text:   var(--evcc-profile-chip-custom-text, var(--evcc-sem-warning));
  }

  .evcc-room-card.is-enabled .evcc-room-setting-chip {
    --evcc-chip-bg:     var(--evcc-room-chip-bg, rgba(255, 255, 255, 0.08));
    --evcc-chip-border: var(--evcc-room-chip-border, rgba(255, 255, 255, 0.14));
  }

  /* =========================================================
     FLOOR-TEXTURE LEGIBILITY
     ---------------------------------------------------------
     The floor texture is a variable-luminance layer painted
     BEHIND card content. The status / setting chips and the room
     name are translucent (they rely on the dark card showing
     through), so over a bright or same-hue texture they lose
     contrast — red on gold, amber on pale marble, the white name
     on a light floor, the muted "ago" chip on anything light.
     CSS cannot sample an image's luminance to pick a contrasting
     color, so rather than tune any single color we composite each
     chip OVER AN OPAQUE SURFACE: legibility becomes independent of
     whatever texture sits behind — for any chip color and any
     floor. Texture stays fully visible everywhere else.
     ========================================================= */

  /* Token-system chips (mode pills + status): their tint is a
     background-COLOR, so re-emit it as an image layer stacked on
     top of an opaque surface base (hue/intensity unchanged). */
  .evcc-room-card .evcc-room-status,
  .evcc-room-card .evcc-room-setting-chip {
    background:
      linear-gradient(
        var(--evcc-chip-bg, var(--evcc-surface-input)),
        var(--evcc-chip-bg, var(--evcc-surface-input))
      ),
      var(--evcc-surface-card);
  }

  /* Confidence chips: their tint is already a gradient IMAGE, so
     an opaque background-color beneath it is enough (the variant
     gradient still renders on top). */
  .evcc-room-card .evcc-learning-chip {
    background-color: var(--evcc-surface-card);
  }

  /* Action-row controls (Move / drag handle / settings gear) are .evcc-chip with
     a translucent resting bg, so they vanish on a light texture. Give them the
     same opaque surface backing. Hover/active already resolve to opaque surfaces
     (surface-panel / accent), so only the resting state needs this. */
  .evcc-room-card .evcc-chip {
    background:
      linear-gradient(
        var(--evcc-chip-bg, var(--evcc-surface-input)),
        var(--evcc-chip-bg, var(--evcc-surface-input))
      ),
      var(--evcc-surface-card);
  }

  /* Bare text — order number (#N) + room name — gets a surface-colored halo so
     light text survives a light texture (invisible over dark ones). */
  .evcc-room-card .evcc-order-chip,
  .evcc-room-card .evcc-room-name {
    text-shadow:
      0 0 2px var(--evcc-surface-card),
      0 1px 3px var(--evcc-surface-card),
      0 0 6px var(--evcc-surface-card);
  }

  /* Estimate notes (e.g. the warning-variant "intensity mismatch") are bare
     colored text — back them as self-hugging pills so the tint reads on any
     texture (rare notes that weren't on screen for the first pass). */
  .evcc-room-card .evcc-room-note {
    align-self:       flex-start;
    padding:          2px 8px;
    border-radius:    var(--evcc-radius-chip, 999px);
    background-color: var(--evcc-surface-card);
  }

  /* =========================================================
     STATUS CHIPS
     ========================================================= */

  .evcc-room-chip-row {
    display:    flex;
    gap:        8px;
    flex-wrap:  wrap;
    margin-top: auto;
  }

  .evcc-room-status {
    --evcc-chip-height:      24px;
    --evcc-chip-padding:     2px 10px;
    --evcc-chip-font-size:   0.74rem;
    --evcc-chip-font-weight: 700;
    cursor:                  default;
  }

  .evcc-room-status.is-included {
    --evcc-chip-bg:     var(--evcc-chip-included-bg,
                          color-mix(in srgb, var(--evcc-sem-success) 30%, transparent));
    --evcc-chip-text:   var(--evcc-chip-included-text, var(--evcc-sem-success));
    --evcc-chip-border: var(--evcc-chip-included-border,
                          color-mix(in srgb, var(--evcc-sem-success) 60%, transparent));
  }

  .evcc-room-status.is-excluded {
    --evcc-chip-bg:     var(--evcc-chip-excluded-bg,
                          color-mix(in srgb, var(--evcc-text-muted) 20%, transparent));
    --evcc-chip-text:   var(--evcc-chip-excluded-text, var(--evcc-text-secondary));
    --evcc-chip-border: var(--evcc-chip-excluded-border, var(--evcc-border-default));
  }

  .evcc-room-status.is-carpet {
    --evcc-chip-bg:     color-mix(in srgb, var(--evcc-accent) 22%, transparent);
    --evcc-chip-text:   var(--evcc-accent);
    --evcc-chip-border: color-mix(in srgb, var(--evcc-accent) 60%, transparent);
    cursor:             default;
  }

  /* =========================================================
     QUEUE CHIPS
     ========================================================= */

  .evcc-queue-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       var(--evcc-queue-chip-gap, 6px);
  }

  .evcc-queue-chip {
    all: unset;
    box-sizing: border-box;
    position:     relative;
    overflow:     hidden;

    display:       inline-flex;
    align-items:   center;
    gap:           6px;
    padding:       4px 10px;
    border-radius: 999px;

    background:    var(--evcc-queue-chip-bg, var(--evcc-surface-input));
    border:        1px solid var(--evcc-queue-chip-border, var(--evcc-border-default));
    color:         var(--evcc-queue-chip-text, var(--evcc-text-secondary));

    font-size:     0.78rem;
    white-space:   nowrap;
    cursor:        pointer;
    user-select:   none;
    touch-action:  manipulation;

    transition:
      transform    var(--evcc-transition-normal, 120ms ease),
      box-shadow   var(--evcc-transition-normal, 120ms ease),
      border-color var(--evcc-transition-normal, 120ms ease),
      background   var(--evcc-transition-normal, 120ms ease),
      color        var(--evcc-transition-normal, 120ms ease),
      opacity      var(--evcc-transition-normal, 120ms ease);
  }

  .evcc-queue-chip:hover {
    transform:    translateY(calc(-1 * var(--evcc-hover-lift, 1px)));
    background:   var(--evcc-queue-hover-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-hover-border,
                    color-mix(in srgb, var(--evcc-accent) 40%, transparent));
    color:        var(--evcc-queue-hover-text, var(--evcc-queue-chip-text, var(--evcc-text-secondary)));
    box-shadow:   var(--evcc-shadow-hover, 0 6px 14px rgba(0, 0, 0, 0.18));
  }

  .evcc-queue-chip:active,
  .evcc-queue-chip.is-pressing {
    transform: scale(var(--evcc-press-scale, 0.97));
  }

  .evcc-queue-chip.is-long-pressing {
    background:   var(--evcc-chip-warning-bg,
                    color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent));
    border-color: var(--evcc-chip-warning-border,
                    color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent));
    color:        var(--evcc-chip-warning-text, var(--evcc-sem-warning));
  }

  .evcc-queue-chip--active {
    background:   var(--evcc-queue-current-bg,
                    color-mix(in srgb, var(--evcc-sem-success) 16%, transparent));
    border-color: var(--evcc-queue-current-border,
                    color-mix(in srgb, var(--evcc-sem-success) 32%, transparent));
    color:        var(--evcc-queue-current-text, var(--evcc-sem-success));
  }

  .evcc-queue-chip.is-pending {
    background:   var(--evcc-queue-pending-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-pending-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-pending-text, var(--evcc-queue-chip-text, var(--evcc-text-secondary)));
    opacity:      var(--evcc-queue-pending-opacity, 1);
  }

  .evcc-queue-chip.is-current {
    background:   var(--evcc-queue-current-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-current-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-current-text, var(--evcc-queue-chip-text, var(--evcc-text-primary)));
    box-shadow:   var(--evcc-queue-current-glow, none);
  }

  .evcc-queue-chip.is-inferred {
    background:   var(--evcc-queue-inferred-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-inferred-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-inferred-text, var(--evcc-queue-chip-text, var(--evcc-text-primary)));
    box-shadow:   var(--evcc-queue-inferred-glow, none);
  }

  .evcc-queue-chip.is-completed {
    background:   var(--evcc-queue-completed-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-completed-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-completed-text, var(--evcc-queue-chip-text, var(--evcc-text-secondary)));
    opacity:      var(--evcc-queue-completed-opacity, 0.8);
  }

  .evcc-queue-chip.is-skipped {
    background:   var(--evcc-queue-skipped-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-skipped-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-skipped-text, var(--evcc-queue-chip-text, var(--evcc-text-secondary)));
  }

  .evcc-queue-chip-order {
    display:         inline-flex;
    align-items:     center;
    justify-content: center;
    min-width:       18px;
    height:          18px;
    padding:         0 5px;
    border-radius:   999px;
    background:      var(--evcc-queue-order-bg, rgba(255, 255, 255, 0.10));
    border:          1px solid var(--evcc-queue-order-border, transparent);
    font-size:       0.7rem;
    font-weight:     700;
    color:           var(--evcc-queue-order-text, currentColor);
  }

  .evcc-queue-chip-label {
    font-weight: 600;
    white-space: nowrap;
  }

  /* =========================================================
     EMPTY
     ========================================================= */

  .evcc-empty {
    padding:       24px;
    border-radius: var(--evcc-radius-panel, 16px);
    text-align:    center;
    color:         var(--evcc-text-muted);
    border:        1px dashed var(--evcc-border-default);
    background:    color-mix(in srgb, var(--evcc-surface-input) 50%, transparent);
  }

  /* =========================================================
     ROOM ESTIMATE TOKEN BRIDGE
     ========================================================= */

  :host {
    --evcc-estimate-learned-bg:
      color-mix(in srgb, var(--evcc-accent) 14%, transparent);
    --evcc-estimate-learned-border:
      color-mix(in srgb, var(--evcc-accent) 30%, transparent);
    --evcc-estimate-learned-text:
      var(--evcc-text-primary);

    --evcc-estimate-default-bg:
      color-mix(in srgb, var(--evcc-text-muted) 12%, transparent);
    --evcc-estimate-default-border:
      var(--evcc-border-default);
    --evcc-estimate-default-text:
      var(--evcc-text-secondary);

    --evcc-learning-note-text:
      var(--evcc-text-muted);
    --evcc-learning-warning-text:
      var(--evcc-sem-warning);
  }

  /* =========================================================
     ROOM ESTIMATE CHIP
     ========================================================= */

  .evcc-room-status--estimate {
    border-style: solid;
  }

  .evcc-room-status--estimate-learned {
    background: var(--evcc-estimate-learned-bg);
    border-color: var(--evcc-estimate-learned-border);
    color: var(--evcc-estimate-learned-text);
  }

  .evcc-room-status--estimate-default {
    background: var(--evcc-estimate-default-bg);
    border-color: var(--evcc-estimate-default-border);
    color: var(--evcc-estimate-default-text);
    font-style: italic;
    opacity: 0.9;
  }

  /* "Last cleaned ~Nd ago" pill, sourced from room_history. */
  .evcc-room-status--last-cleaned {
    color: var(--evcc-text-muted);
    background: var(--evcc-surface-subtle, rgba(255, 255, 255, 0.04));
    border-color: var(--evcc-border-subtle, rgba(255, 255, 255, 0.06));
    opacity: 0.85;
  }

  /* =========================================================
     ROOM NOTES
     ========================================================= */

  .evcc-room-notes {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: var(--evcc-space-sm, 8px);
  }

  .evcc-room-note {
    font-size: 0.74rem;
    line-height: 1.25;
  }

  .evcc-room-note--muted {
    color: var(--evcc-learning-note-text);
  }

  .evcc-room-note--warning {
    color: var(--evcc-learning-warning-text);
    font-weight: 600;
  }
  
  /* =========================================================
     QUEUE CHIP CONFIDENCE TINT
     =========================================================
     Confidence is secondary to execution state.
     These classes should lightly tint queue chips without
     overpowering current/completed/remaining state styling.
     ========================================================= */

  .evcc-queue-chip--confidence-high {
    background:
      color-mix(in srgb, var(--evcc-confidence-high-bg) 30%, var(--evcc-surface-input));
    border-color: color-mix(in srgb, var(--evcc-confidence-high-border) 70%, var(--evcc-border-default));
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--evcc-confidence-high-bg) 45%, transparent);
  }

  .evcc-queue-chip--confidence-medium {
    background:
      color-mix(in srgb, var(--evcc-confidence-medium-bg) 30%, var(--evcc-surface-input));
    border-color: color-mix(in srgb, var(--evcc-confidence-medium-border) 70%, var(--evcc-border-default));
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--evcc-confidence-medium-bg) 45%, transparent);
  }

  .evcc-queue-chip--confidence-low {
    background:
      color-mix(in srgb, var(--evcc-confidence-low-bg) 30%, var(--evcc-surface-input));
    border-color: color-mix(in srgb, var(--evcc-confidence-low-border) 70%, var(--evcc-border-default));
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--evcc-confidence-low-bg) 45%, transparent);
  }

  /* =========================================================
     QUEUE CHIP TIME
     ========================================================= */

  .evcc-queue-chip-time {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
    white-space: nowrap;
  }

  /* =========================================================
     QUEUE EXECUTION STATES
     ========================================================= */

  .evcc-queue-chip--queued {
    opacity: 0.95;
  }

  .evcc-queue-chip--remaining {
    opacity: 0.92;
  }

  .evcc-queue-chip--current {
    border-color: color-mix(in srgb, var(--evcc-accent) 45%, transparent);
    background: color-mix(in srgb, var(--evcc-accent) 12%, transparent);
    color: var(--evcc-text-primary);
  }

  .evcc-queue-chip--completed {
    opacity: 0.72;
  }

  .evcc-queue-chip--completed .evcc-queue-chip-label,
  .evcc-queue-chip--completed .evcc-queue-chip-time {
    text-decoration: line-through;
  }

  /* =========================================================
     ROOM CARD CONFIDENCE LAYOUT
     ========================================================= */

  .evcc-room-chip-row .evcc-learning-chip {
    flex-shrink: 0;
  }

  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 480px) {
    .evcc-rooms-bar-top {
      align-items: stretch;
    }

    .evcc-room-card {
      padding:       10px;
      border-radius: 16px;
    }

    .evcc-room-name {
      font-size: 0.88rem;
    }

    .evcc-room-status {
      --evcc-chip-height:    22px;
      --evcc-chip-padding:   2px 8px;
      --evcc-chip-font-size: 0.7rem;
    }
  }
  
  /* =========================================================
     QUEUE CHIP FILL
     ========================================================= */

  .evcc-queue-chip::before {
    content: "";
    position: absolute;
    inset: 0;
    width: var(--job-progress, 0%);
    background: var(
      --evcc-progress-fill,
      color-mix(in srgb, var(--evcc-accent) 25%, transparent)
    );
    transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 0;
  }

  .evcc-queue-chip > * {
    position: relative;
    z-index: 1;
  }

  /* =========================================================
     ROOM CARD FILL
     ========================================================= */

  .evcc-room-card::before {
    content: "";
    position: absolute;
    inset: 0;
    width: var(--room-progress, 0%);
    background: var(
      --evcc-progress-fill,
      color-mix(in srgb, var(--evcc-accent) 15%, transparent)
    );
    transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 0;
    opacity: var(--evcc-room-fill-opacity, 1);
  }

  .evcc-room-card > * {
    position: relative;
    z-index: 1;
  }

  /* =========================================================
     CURRENT ROOM ACTIVE GLOW / SHEEN
     ========================================================= */

  .evcc-room-card--queue-current::before {
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--evcc-accent) 20%, transparent),
      color-mix(in srgb, var(--evcc-accent) 35%, transparent)
    );
    animation: evcc-progress-pulse 2s ease-in-out infinite;
    will-change: opacity;
  }

  .evcc-room-card--queue-current::after,
  .evcc-queue-chip--current::after {
    content: "";
    position: absolute;
    inset: 0;
    background:
      linear-gradient(
        110deg,
        transparent 0%,
        color-mix(in srgb, white 28%, transparent) 45%,
        transparent 70%
      );
    transform: translateX(-130%);
    animation: evcc-progress-sheen 2.4s linear infinite;
    pointer-events: none;
    z-index: 0;
  }

  @keyframes evcc-progress-pulse {
    0% { opacity: 0.6; }
    50% { opacity: 1; }
    100% { opacity: 0.6; }
  }

  @keyframes evcc-progress-sheen {
    0%   { transform: translateX(-130%); }
    100% { transform: translateX(130%); }
  }

  .evcc-queue-chip--current::before {
    animation: evcc-progress-pulse 2s ease-in-out infinite;
  }

  /* =========================================================
     COMPLETED STATE + SWEEP
     ========================================================= */

  .evcc-room-card--queue-completed::before {
    width: 100%;
    background: var(
      --evcc-progress-complete,
      color-mix(in srgb, var(--evcc-sem-success) 30%, transparent)
    );
  }

  .evcc-queue-chip--completed::before {
    width: 100%;
    background: var(
      --evcc-progress-complete,
      color-mix(in srgb, var(--evcc-sem-success) 35%, transparent)
    );
  }

  .evcc-room-card--queue-completed::after,
  .evcc-queue-chip--completed::after {
    content: "";
    position: absolute;
    inset: 0;
    background:
      linear-gradient(
        100deg,
        transparent 0%,
        color-mix(in srgb, white 35%, transparent) 48%,
        transparent 75%
      );
    transform: translateX(-140%);
    animation: evcc-progress-complete-sweep 800ms ease-out 1;
    pointer-events: none;
    z-index: 0;
  }

  @keyframes evcc-progress-complete-sweep {
    0%   { transform: translateX(-140%); opacity: 0; }
    15%  { opacity: 1; }
    100% { transform: translateX(140%); opacity: 0; }
  }

  /* =========================================================
     REMAINING FAINT TINT STATE
     ========================================================= */
   
  .evcc-room-card--queue-remaining::before {
    background: color-mix(in srgb, var(--evcc-accent) 6%, transparent);
  }

  /* =========================================================
     CONFIDENCE-AWARE FILL INTENSITY
     ========================================================= */

  .evcc-room-card--confidence-high {
    --evcc-room-fill-opacity: 1;
  }

  .evcc-room-card--confidence-medium {
    --evcc-room-fill-opacity: 0.82;
  }

  .evcc-room-card--confidence-low {
    --evcc-room-fill-opacity: 0.66;
  }

  /* =========================================================
     LIVE PROGRESS MICRO TEXT
     ========================================================= */

  .evcc-room-progress-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 4px;
  }

  .evcc-room-progress-chip {
    --evcc-chip-height:      22px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.7rem;
    --evcc-chip-font-weight: 700;
    --evcc-chip-bg:          color-mix(in srgb, var(--evcc-accent) 14%, transparent);
    --evcc-chip-border:      color-mix(in srgb, var(--evcc-accent) 30%, transparent);
    --evcc-chip-text:        var(--evcc-text-primary);
  }

  .evcc-room-progress-chip--remaining {
    --evcc-chip-bg:     color-mix(in srgb, var(--evcc-text-muted) 14%, transparent);
    --evcc-chip-border: color-mix(in srgb, var(--evcc-text-muted) 28%, transparent);
    --evcc-chip-text:   var(--evcc-text-secondary);
  }

  /* =========================================================
     REDUCED MOTION
     ========================================================= */

  @media (prefers-reduced-motion: reduce) {
    .evcc-room-card,
    .evcc-queue-chip,
    .evcc-room-card::before,
    .evcc-queue-chip::before {
      transition-duration: 0.01ms !important;
    }

    .evcc-room-card--queue-current::before,
    .evcc-queue-chip--current::before,
    .evcc-room-card--queue-current::after,
    .evcc-queue-chip--current::after,
    .evcc-room-card--queue-completed::after,
    .evcc-queue-chip--completed::after,
    .evcc-active-job-pulse {
      animation: none !important;
    }
  }

  /* =========================================================
     ORPHANED ROOMS PANEL
     ========================================================= */

  .evcc-orphaned-rooms-panel {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--evcc-space-sm, 8px);
    padding: 8px 10px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid color-mix(in srgb, var(--evcc-text-muted) 25%, transparent);
    background: color-mix(in srgb, var(--evcc-text-muted) 8%, transparent);
    margin-bottom: var(--evcc-space-md, 12px);
  }

  .evcc-orphaned-rooms-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--evcc-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .evcc-orphaned-rooms-chips {
    gap: 6px;
    flex: 1;
  }

  .evcc-orphaned-rooms-chip {
    font-size: 0.78rem;
    color: var(--evcc-text-muted);
    border-color: color-mix(in srgb, var(--evcc-text-muted) 30%, transparent);
    background: transparent;
    cursor: default;
    pointer-events: none;
  }
`;
