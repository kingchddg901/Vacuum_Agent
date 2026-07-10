// CSS styles for the Room Rules tab: sub-tabs, rule list cards, rule editor form, and footer.

export const roomRulesStyles = `

/* ============================================================
   ROOM RULES VIEW
   ============================================================ */

.evcc-room-rules-view {
  display:        flex;
  flex-direction: column;
  gap:            0;
  min-height:     0;
}

/* =========================================================
   SUB-TABS
   ========================================================= */

.evcc-room-rules-subtabs {
  display:              flex;
  gap:                  4px;
  overflow-x:           auto;
  padding:              12px 16px 0;
  scrollbar-width:      none;
  flex-shrink:          0;
  border-bottom:        1px solid var(--evcc-border-subtle, rgba(255,255,255,0.06));
}

.evcc-room-rules-subtabs::-webkit-scrollbar {
  display: none;
}

.evcc-room-rules-subtab {
  display:         flex;
  align-items:     center;
  gap:             6px;
  padding:         6px 14px;
  border-radius:   8px 8px 0 0;
  font-size:       0.82rem;
  font-weight:     500;
  color:           var(--evcc-text-secondary, rgba(240,242,245,0.72));
  background:      transparent;
  border:          1px solid transparent;
  border-bottom:   none;
  cursor:          pointer;
  white-space:     nowrap;
  transition:      background 120ms ease, color 120ms ease;
}

.evcc-room-rules-subtab:hover {
  background: var(--evcc-surface-input, rgba(255,255,255,0.06));
  color:      var(--evcc-text-primary, #f0f2f5);
}

.evcc-room-rules-subtab.active {
  background:   var(--evcc-surface-input, rgba(255,255,255,0.08));
  color:        var(--evcc-text-primary, #f0f2f5);
  border-color: var(--evcc-border-default, rgba(255,255,255,0.10));
  font-weight:  600;
}

.evcc-room-rules-subtab-count {
  display:          inline-flex;
  align-items:      center;
  justify-content:  center;
  min-width:        18px;
  height:           18px;
  padding:          0 5px;
  border-radius:    999px;
  font-size:        0.72rem;
  font-weight:      700;
  background:       color-mix(in srgb, var(--evcc-accent, #3b82f6) 20%, transparent);
  color:            var(--evcc-accent, #3b82f6);
}

/* =========================================================
   CONTENT AREA
   ========================================================= */

.evcc-room-rules-content {
  padding:    16px;
  flex:       1;
  min-height: 0;
  overflow-y: auto;
}

/* ============================================================
   RULE LIST
   ============================================================ */

.evcc-rule-list {
  display:        flex;
  flex-direction: column;
  gap:            8px;
}

.evcc-rule-list-empty {
  font-size: 0.88rem;
  color:     var(--evcc-text-muted, rgba(240,242,245,0.48));
  padding:   8px 0;
}

.evcc-rule-list-actions {
  padding-top: 4px;
}

/* =========================================================
   RULE CARD
   ========================================================= */

.evcc-rule-card {
  display:        flex;
  flex-direction: column;
  gap:            8px;
  padding:        10px 12px;
  border-radius:  10px;
  border:         1px solid var(--evcc-border-default, rgba(255,255,255,0.10));
  background:     var(--evcc-surface-input, rgba(255,255,255,0.04));
}

.evcc-rule-card--disabled {
  opacity: 0.55;
}

.evcc-rule-card-body {
  display:     flex;
  align-items: flex-start;
  gap:         10px;
}

.evcc-rule-card-actions {
  display:     flex;
  gap:         6px;
  justify-content: flex-end;
}

.evcc-rule-kind-badge {
  flex-shrink:   0;
  padding:       2px 8px;
  border-radius: 999px;
  font-size:     0.68rem;
  font-weight:   700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.evcc-rule-kind-badge--blocker {
  background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 18%, transparent);
  color:      var(--evcc-sem-error, #ef4444);
  border:     1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 35%, transparent);
}

.evcc-rule-kind-badge--modifier {
  background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 18%, transparent);
  color:      var(--evcc-accent, #3b82f6);
  border:     1px solid color-mix(in srgb, var(--evcc-accent, #3b82f6) 35%, transparent);
}

.evcc-rule-info {
  flex:    1;
  display: flex;
  flex-direction: column;
  gap:     2px;
  min-width: 0;
}

.evcc-rule-label {
  font-size:   0.88rem;
  font-weight: 600;
  color:       var(--evcc-text-primary, #f0f2f5);
  overflow:    hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evcc-rule-entity {
  font-size: 0.78rem;
  color:     var(--evcc-text-muted, rgba(240,242,245,0.48));
  overflow:  hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evcc-rule-condition {
  font-size:  0.80rem;
  color:      var(--evcc-text-secondary, rgba(240,242,245,0.72));
  margin-top: 2px;
}

.evcc-rule-effect {
  font-size: 0.78rem;
  color:     var(--evcc-text-muted, rgba(240,242,245,0.48));
}

/* Rule fan-out badge on the rule card — small "→ also affects N rooms"
   line under the effect summary so users can spot fan-out rules in the
   list without opening the editor. */
.evcc-rule-fan-out {
  font-size:    0.74rem;
  color:        var(--evcc-accent, #60a5fa);
  margin-top:   2px;
}

.evcc-rule-disabled-tag {
  flex-shrink:   0;
  align-self:    center;
  padding:       2px 7px;
  border-radius: 999px;
  font-size:     0.68rem;
  font-weight:   600;
  background:    var(--evcc-surface-input, rgba(255,255,255,0.06));
  color:         var(--evcc-text-muted, rgba(240,242,245,0.48));
  border:        1px solid var(--evcc-border-subtle, rgba(255,255,255,0.08));
}

.evcc-chip--danger {
  color:        var(--evcc-sem-error, #ef4444);
  border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 35%, transparent);
}

.evcc-chip--danger:hover {
  background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
  border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 50%, transparent);
}

/* ============================================================
   RULE EDITOR FORM
   ============================================================ */

.evcc-rule-editor {
  display:        flex;
  flex-direction: column;
  gap:            0;
  border-radius:  12px;
  border:         1px solid var(--evcc-border-default, rgba(255,255,255,0.10));
  background:     var(--evcc-surface-input, rgba(255,255,255,0.03));
  overflow:       hidden;
}

.evcc-rule-editor-header {
  padding:       12px 16px;
  border-bottom: 1px solid var(--evcc-border-subtle, rgba(255,255,255,0.06));
  flex-shrink:   0;
}

.evcc-rule-editor-title {
  font-size:   0.95rem;
  font-weight: 700;
  color:       var(--evcc-text-primary, #f0f2f5);
}

.evcc-rule-editor-body {
  display:        flex;
  flex-direction: column;
  gap:            20px;
  padding:        16px;
  overflow-y:     auto;
}

.evcc-rule-editor-section {
  display:        flex;
  flex-direction: column;
  gap:            8px;
}

.evcc-rule-editor-help {
  font-size: 0.78rem;
  color:     var(--evcc-text-muted, rgba(240,242,245,0.48));
  line-height: 1.5;
}

.evcc-rule-entity-search {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  overflow-y: auto;
  padding: 8px;
  border-radius: 10px;
  border: 1px solid var(--evcc-border-subtle, rgba(255,255,255,0.08));
  background: var(--evcc-surface-panel, rgba(255,255,255,0.02));
}

.evcc-rule-entity-search-result {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--evcc-border-subtle, rgba(255,255,255,0.08));
  background: transparent;
  text-align: left;
  transition: background 120ms ease, border-color 120ms ease;
}

.evcc-rule-entity-search-result:hover {
  background: var(--evcc-surface-input, rgba(255,255,255,0.05));
  border-color: var(--evcc-border-default, rgba(255,255,255,0.12));
}

.evcc-rule-entity-search-result.active {
  background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 10%, transparent);
  border-color: color-mix(in srgb, var(--evcc-accent, #3b82f6) 30%, transparent);
}

.evcc-rule-entity-search-title {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--evcc-text-primary, #f0f2f5);
}

.evcc-rule-entity-search-meta,
.evcc-rule-entity-search-empty {
  font-size: 0.75rem;
  color: var(--evcc-text-muted, rgba(240,242,245,0.48));
}

.evcc-rule-entity-search-empty {
  padding: 8px 0;
}

.evcc-rule-editor-optional {
  font-size:   0.72rem;
  font-weight: 400;
  color:       var(--evcc-text-muted, rgba(240,242,245,0.48));
}

.evcc-rule-editor-input {
  width:        100%;
  padding:      7px 10px;
  border-radius: 6px;
  border:       1px solid var(--evcc-border-default, rgba(255,255,255,0.10));
  background:   var(--evcc-surface-input, rgba(255,255,255,0.06));
  color:        var(--evcc-text-primary, #f0f2f5);
  font-size:    0.88rem;
  font-family:  inherit;
  outline:      none;
  transition:   border-color 120ms ease;
}

.evcc-rule-editor-input:focus {
  border-color: var(--evcc-accent, #3b82f6);
}

.evcc-rule-editor-input--error {
  border-color: var(--evcc-sem-error, #ef4444);
}

.evcc-rule-operator-group {
  display:        flex;
  flex-direction: column;
  gap:            4px;
}

.evcc-rule-operator-group-label {
  font-size:  0.72rem;
  font-weight: 500;
  color:      var(--evcc-text-muted, rgba(240,242,245,0.48));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* =========================================================
   MODIFIER CHANGES
   ========================================================= */

.evcc-rule-change-row {
  display:        flex;
  flex-direction: column;
  gap:            6px;
}

.evcc-rule-change-label {
  font-size:   0.78rem;
  font-weight: 500;
  color:       var(--evcc-text-secondary, rgba(240,242,245,0.72));
}

.evcc-chip--muted {
  opacity: 0.55;
}

.evcc-chip--muted.active {
  opacity: 1;
  background: var(--evcc-surface-input, rgba(255,255,255,0.08));
  color:      var(--evcc-text-muted, rgba(240,242,245,0.48));
  border-color: var(--evcc-border-default, rgba(255,255,255,0.10));
}

/* =========================================================
   FOOTER
   ========================================================= */

.evcc-rule-editor-save-error {
  margin:       0 16px;
  padding:      8px 12px;
  border-radius: 6px;
  font-size:    0.82rem;
  font-weight:  500;
  background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
  border:       1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 30%, transparent);
  color:        var(--evcc-sem-error, #ef4444);
}

.evcc-rule-editor-footer {
  display:         flex;
  align-items:     center;
  justify-content: flex-end;
  gap:             8px;
  padding:         12px 16px;
  border-top:      1px solid var(--evcc-border-subtle, rgba(255,255,255,0.06));
  flex-shrink:     0;
}

/* ============================================================
   LIGHT MODE OVERRIDES
   ============================================================ */

@media (prefers-color-scheme: light) {
  .evcc-room-rules-subtab.active {
    background: rgba(15,23,42,0.05);  /* theme-lint-ignore: prefers-color-scheme:light override (design decision, outside the token system) */
    color:      #0f172a;  /* theme-lint-ignore: light-mode override */
  }

  .evcc-rule-card {
    background: rgba(15,23,42,0.03);  /* theme-lint-ignore: light-mode override */
    border-color: rgba(15,23,42,0.10);  /* theme-lint-ignore: light-mode override */
  }

  .evcc-rule-editor {
    background: rgba(15,23,42,0.02);  /* theme-lint-ignore: light-mode override */
    border-color: rgba(15,23,42,0.10);  /* theme-lint-ignore: light-mode override */
  }

  .evcc-rule-editor-input {
    background:   rgba(15,23,42,0.05);  /* theme-lint-ignore: light-mode override */
    border-color: rgba(15,23,42,0.10);  /* theme-lint-ignore: light-mode override */
    color:        #0f172a;  /* theme-lint-ignore: light-mode override */
  }
}
`;
