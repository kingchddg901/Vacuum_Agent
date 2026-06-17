export const setupStyles = `
  /* =========================================================
     SETUP VIEW
     ========================================================= */

  .evcc-setup-view {
    padding:        20px;
    display:        flex;
    flex-direction: column;
    gap:            16px;
  }

  .evcc-setup-header {
    display:        flex;
    flex-direction: column;
    gap:            6px;
    margin-bottom:  4px;
  }

  .evcc-setup-title {
    font-size:   1.05rem;
    font-weight: 700;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-description {
    font-size:   0.86rem;
    color:       var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    line-height: 1.5;
  }

  /* =========================================================
     STEP CARD
     ========================================================= */

  .evcc-setup-step {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        14px 16px;
    border-radius:  10px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
  }

  .evcc-setup-step-header {
    display:     flex;
    align-items: center;
    gap:         10px;
  }

  .evcc-setup-step-badge {
    width:           24px;
    height:          24px;
    border-radius:   50%;
    background:      var(--evcc-accent, #3b82f6);
    color:           #fff;
    display:         flex;
    align-items:     center;
    justify-content: center;
    font-size:       0.76rem;
    font-weight:     700;
    flex-shrink:     0;
    transition:      background 200ms ease;
  }

  .evcc-setup-step-badge.done {
    background: var(--evcc-sem-success, #22c55e);
  }

  .evcc-setup-step-label {
    font-size:   0.92rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-step-body {
    font-size:   0.84rem;
    color:       var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    line-height: 1.45;
  }

  .evcc-setup-step-body.muted {
    opacity: 0.5;
  }

  .evcc-setup-entity-id {
    font-family:    monospace;
    font-size:      0.80rem;
    color:          var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    margin-top:     4px;
    word-break:     break-all;
  }

  /* =========================================================
     BUTTONS
     ========================================================= */

  .evcc-setup-btn {
    align-self:    flex-start;
    padding:       8px 18px;
    border-radius: 8px;
    background:    var(--evcc-accent, #3b82f6);
    color:         #fff;
    font-size:     0.86rem;
    font-weight:   600;
    border:        none;
    cursor:        pointer;
    transition:    opacity 150ms ease;
    line-height:   1;
  }

  .evcc-setup-btn:hover:not(:disabled) {
    opacity: 0.85;
  }

  .evcc-setup-btn:disabled {
    opacity: 0.45;
    cursor:  default;
  }

  .evcc-setup-btn.secondary {
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.08));
    color:      var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    border:     1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
  }

  /* =========================================================
     RESULT BANNERS
     ========================================================= */

  .evcc-setup-result {
    padding:       9px 13px;
    border-radius: 8px;
    font-size:     0.84rem;
    font-weight:   500;
    line-height:   1.4;
  }

  .evcc-setup-result.success {
    background:   color-mix(in srgb, var(--evcc-sem-success, #22c55e) 14%, transparent);
    border:       1px solid color-mix(in srgb, var(--evcc-sem-success, #22c55e) 32%, transparent);
    color:        var(--evcc-sem-success, #22c55e);
  }

  .evcc-setup-result.error {
    background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 14%, transparent);
    border:       1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 32%, transparent);
    color:        var(--evcc-sem-error, #ef4444);
  }

  .evcc-setup-result.info {
    background:   color-mix(in srgb, var(--evcc-accent, #3b82f6) 14%, transparent);
    border:       1px solid color-mix(in srgb, var(--evcc-accent, #3b82f6) 32%, transparent);
    color:        var(--evcc-accent, #3b82f6);
  }

  /* =========================================================
     READY STATE — ROOM SUMMARY
     ========================================================= */

  .evcc-setup-vacuum-list {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-setup-vacuum-entry {
    display:        flex;
    flex-direction: column;
    gap:            4px;
    padding:        10px 12px;
    border-radius:  8px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border:         1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.07));
  }

  .evcc-setup-vacuum-name {
    font-size:   0.88rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-vacuum-meta {
    font-size: 0.80rem;
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  /* =========================================================
     IMPORTED MAPS LIST
     ========================================================= */

  .evcc-setup-map-list {
    display:        flex;
    flex-direction: column;
    gap:            4px;
  }

  .evcc-setup-map-list-label {
    font-size:      0.74rem;
    font-weight:    600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color:          var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    margin-bottom:  2px;
  }

  .evcc-setup-map-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             12px;
    padding:         6px 10px;
    border-radius:   6px;
    background:      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 10%, transparent);
    border:          1px solid color-mix(in srgb, var(--evcc-sem-success, #22c55e) 24%, transparent);
  }

  .evcc-setup-map-name {
    font-size:   0.84rem;
    font-weight: 500;
    color:       var(--evcc-text-primary, #f0f2f5);
    overflow:    hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .evcc-setup-map-rooms {
    font-size:   0.78rem;
    color:       var(--evcc-sem-success, #22c55e);
    flex-shrink: 0;
  }

  /* =========================================================
     FOOTER ROW
     ========================================================= */

  .evcc-setup-footer {
    display:     flex;
    align-items: center;
    gap:         10px;
    margin-top:  4px;
  }

  /* =========================================================
     STEP 3 — MAP CONFIG ROWS
     ========================================================= */

  .evcc-setup-mapconfig-list {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-setup-mapconfig-row {
    display:        flex;
    flex-direction: column;
    gap:            0;
    border-radius:  8px;
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
    overflow:       hidden;
  }

  .evcc-setup-mapconfig-header {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             10px;
    padding:         10px 12px;
    background:      var(--evcc-surface-input, rgba(255, 255, 255, 0.04));
  }

  .evcc-setup-mapconfig-name {
    font-size:     0.86rem;
    font-weight:   600;
    color:         var(--evcc-text-primary, #f0f2f5);
    overflow:      hidden;
    text-overflow: ellipsis;
    white-space:   nowrap;
  }

  .evcc-setup-mapconfig-actions {
    display:     flex;
    align-items: center;
    gap:         8px;
    flex-shrink: 0;
  }

  .evcc-setup-configured-badge {
    font-size:   0.76rem;
    font-weight: 600;
    color:       var(--evcc-sem-success, #22c55e);
  }

  .evcc-setup-btn.small {
    padding:   5px 12px;
    font-size: 0.80rem;
  }

  /* =========================================================
     ROOM EDITOR — inline panel below map header
     ========================================================= */

  .evcc-setup-room-editor {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        12px;
    border-top:     1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
    background:     var(--evcc-surface-sunken, rgba(0, 0, 0, 0.18));
  }

  .evcc-setup-room-editor-hint {
    font-size:   0.80rem;
    color:       var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    line-height: 1.45;
  }

  .evcc-setup-room-list {
    display:        flex;
    flex-direction: column;
    gap:            6px;
  }

  /* =========================================================
     INDIVIDUAL ROOM ROW
     ========================================================= */

  .evcc-setup-room-row {
    display:        flex;
    flex-direction: column;
    gap:            6px;
    padding:        8px 10px;
    border-radius:  6px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border:         1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.07));
    transition:     opacity 150ms ease;
  }

  .evcc-setup-room-row.excluded {
    opacity: 0.45;
  }

  .evcc-setup-room-row-top {
    display:     flex;
    align-items: center;
    gap:         10px;
  }

  .evcc-setup-room-toggle {
    width:           26px;
    height:          26px;
    border-radius:   50%;
    border:          none;
    cursor:          pointer;
    font-size:       0.72rem;
    font-weight:     700;
    display:         flex;
    align-items:     center;
    justify-content: center;
    flex-shrink:     0;
    transition:      background 150ms ease, color 150ms ease;
  }

  .evcc-setup-room-toggle.on {
    background: var(--evcc-sem-success, #22c55e);
    color:      #fff;
  }

  .evcc-setup-room-toggle.off {
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.12));
    color:      var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  .evcc-setup-room-toggle:disabled {
    opacity: 0.45;
    cursor:  default;
  }

  .evcc-setup-room-name {
    font-size:   0.86rem;
    font-weight: 500;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  /* =========================================================
     FLOOR TYPE CHIPS
     ========================================================= */

  .evcc-setup-floor-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       5px;
    padding-left: 36px;
  }

  .evcc-setup-floor-chip {
    padding:       4px 10px;
    border-radius: 20px;
    font-size:     0.76rem;
    font-weight:   500;
    cursor:        pointer;
    border:        1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.14));
    background:    var(--evcc-surface-input, rgba(255, 255, 255, 0.07));
    color:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    transition:    background 120ms ease, border-color 120ms ease, color 120ms ease;
    white-space:   nowrap;
  }

  .evcc-setup-floor-chip.active {
    background:   color-mix(in srgb, var(--evcc-accent, #3b82f6) 22%, transparent);
    border-color: var(--evcc-accent, #3b82f6);
    color:        var(--evcc-accent, #3b82f6);
    font-weight:  600;
  }

  .evcc-setup-floor-chip:hover:not(:disabled):not(.active) {
    background: rgba(255, 255, 255, 0.12);
  }

  .evcc-setup-floor-chip:disabled {
    opacity: 0.45;
    cursor:  default;
  }

  /* =========================================================
     DESTRUCTIVE BUTTON VARIANTS
     ========================================================= */

  .evcc-setup-btn.destructive {
    background: var(--evcc-sem-error, #ef4444);
    color:      #fff;
    border:     none;
  }

  .evcc-setup-btn.destructive:hover:not(:disabled) {
    opacity: 0.85;
  }

  .evcc-setup-btn.destructive-ghost {
    background:   transparent;
    color:        var(--evcc-sem-error, #ef4444);
    border:       1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 40%, transparent);
    padding:      5px 12px;
    font-size:    0.80rem;
  }

  .evcc-setup-btn.destructive-ghost:hover:not(:disabled) {
    background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
  }

  /* =========================================================
     DELETE CONFIRMATION PANEL
     ========================================================= */

  .evcc-setup-delete-panel {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        12px;
    border-top:     1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 30%, transparent);
    background:     color-mix(in srgb, var(--evcc-sem-error, #ef4444) 6%, transparent);
  }

  .evcc-setup-delete-badges {
    display:   flex;
    flex-wrap: wrap;
    gap:       5px;
  }

  .evcc-setup-protection-badge {
    padding:       3px 9px;
    border-radius: 20px;
    font-size:     0.74rem;
    font-weight:   600;
    background:    color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 14%, transparent);
    border:        1px solid color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 32%, transparent);
    color:         color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 90%, white 10%);
    white-space:   nowrap;
  }

  .evcc-setup-delete-warning {
    font-size:   0.84rem;
    line-height: 1.5;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-delete-warning strong {
    color: var(--evcc-sem-error, #ef4444);
  }

  .evcc-setup-delete-typed {
    display:        flex;
    flex-direction: column;
    gap:            6px;
  }

  .evcc-setup-delete-typed-hint {
    font-size:   0.80rem;
    color:       var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    line-height: 1.45;
  }

  .evcc-setup-delete-typed-hint strong {
    color:       var(--evcc-text-primary, #f0f2f5);
    font-weight: 700;
  }

  .evcc-setup-delete-input {
    width:         100%;
    box-sizing:    border-box;
    padding:       7px 10px;
    border-radius: 6px;
    border:        1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 40%, transparent);
    background:    var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    color:         var(--evcc-text-primary, #f0f2f5);
    font-size:     0.86rem;
    outline:       none;
  }

  .evcc-setup-delete-input:focus {
    border-color: var(--evcc-sem-error, #ef4444);
  }

  .evcc-setup-delete-actions {
    display:     flex;
    align-items: center;
    gap:         8px;
  }

  /* =========================================================
     ROOM DRIFT PANEL — new / removed / transiently-missing rooms
     surfaced inside the save_rooms step when discovery shows
     the integration is out of sync with the vacuum's segments.
     ========================================================= */

  .evcc-setup-drift-panel {
    display:        flex;
    flex-direction: column;
    gap:            12px;
    margin-top:     12px;
    margin-bottom:  8px;
  }

  .evcc-setup-drift-section {
    border-radius: 8px;
    border:        1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    background:    var(--evcc-surface-subtle, rgba(255, 255, 255, 0.03));
    padding:       12px 14px;
    display:       flex;
    flex-direction: column;
    gap:           8px;
  }

  /* Section colour-coding mirrors the semantic meaning of each
     drift category — new rooms are an info/action prompt, removed
     rooms are warning-coloured because user action just lost data,
     transient is muted because no action is needed yet. */
  .evcc-setup-drift-section.new {
    border-color: color-mix(in srgb, var(--evcc-sem-info, #38bdf8) 35%, transparent);
  }
  .evcc-setup-drift-section.removed {
    border-color: color-mix(in srgb, var(--evcc-sem-warning, #fbbf24) 40%, transparent);
  }
  .evcc-setup-drift-section.transient {
    border-color: color-mix(in srgb, var(--evcc-text-muted, #94a3b8) 30%, transparent);
    opacity:      0.92;
  }

  .evcc-setup-drift-title {
    font-size:   0.92rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-drift-hint {
    font-size: 0.8rem;
    color:     var(--evcc-text-muted, #94a3b8);
    line-height: 1.4;
  }

  .evcc-setup-drift-list {
    display:        flex;
    flex-direction: column;
    gap:            6px;
    margin-top:     4px;
  }

  .evcc-setup-drift-row {
    display:         flex;
    align-items:     center;
    gap:             10px;
    padding:         6px 10px;
    border-radius:   6px;
    background:      var(--evcc-surface-subtle, rgba(255, 255, 255, 0.04));
  }

  .evcc-setup-drift-room-name {
    flex:        1 1 auto;
    font-size:   0.88rem;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-drift-room-map {
    font-size: 0.75rem;
    margin-right: 8px;
  }

  /* =========================================================
     PANEL RENAME
     ========================================================= */

  .evcc-setup-rename {
    display:        flex;
    flex-direction: column;
    gap:            8px;
    padding:        14px 16px;
    border-radius:  10px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
  }

  .evcc-setup-rename-title {
    font-size:   0.95rem;
    font-weight: 700;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-rename-row {
    display:     flex;
    align-items: center;
    gap:         8px;
  }

  .evcc-setup-rename-input {
    flex:          1 1 auto;
    min-width:     0;
    padding:       8px 10px;
    border-radius: 8px;
    background:    var(--evcc-surface-card, rgba(0, 0, 0, 0.20));
    border:        1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    color:         var(--evcc-text-primary, #f0f2f5);
    font-size:     0.9rem;
  }

  .evcc-setup-rename-input:focus {
    outline:      none;
    border-color: var(--evcc-accent, #3b9eff);
  }

  /* Live-map camera picker reuses the rename-input look; it's a <select>,
     so just add a pointer cursor (the native dropdown arrow stays). */
  .evcc-setup-map-camera-select {
    cursor: pointer;
  }

  /* =========================================================
     ADD ANOTHER VACUUM
     ========================================================= */

  .evcc-setup-add-other {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        14px 16px;
    border-radius:  10px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
  }

  .evcc-setup-add-other-title {
    font-size:   0.95rem;
    font-weight: 700;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-add-other-list {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-setup-add-other-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             12px;
    padding:         8px 10px;
    border-radius:   8px;
    background:      var(--evcc-surface-default, rgba(255, 255, 255, 0.04));
    border:          1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.06));
  }

  .evcc-setup-add-other-info {
    display:        flex;
    flex-direction: column;
    gap:            2px;
    min-width:      0;
  }

  .evcc-setup-add-other-name {
    font-size:   0.88rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }
`;
