/**
 * Mobile shell styles.
 *
 * Activated when the outer .evcc-shell has data-viewport="mobile".
 * Reshapes the layout from desktop's stacked-with-top-nav to
 * mobile's stacked-with-bottom-nav, plus styles the overflow sheet.
 *
 * The shell frame DOM is shared between viewports — these styles only
 * select the mobile-only slots (`[data-evcc-bottom-nav-root]`,
 * `[data-evcc-mobile-overlay-root]`) plus override a handful of
 * shared elements via the `[data-viewport="mobile"]` attribute on
 * the shell.
 *
 * Why declarative attribute selectors and not classes: the shell
 * frame is built once and persisted across renders. Toggling a
 * data-attribute on the existing shell element is cheaper than
 * reflowing the class list.
 */

export const MOBILE_STYLES = `

  /* ===========================================================
     SHELL LAYOUT — mobile branch
     -----------------------------------------------------------
     Desktop shell flow:   header(nav) > view-stage > [empty] > [empty]
     Mobile shell flow:    header(no nav) > view-stage > bottom-nav > overlay

     The shell is already display:flex / flex-direction:column with
     height:100% (see shell.js). We just need:
       - Header: shrink to content (already correct)
       - View stage: flex:1, scrolls internally (already correct)
       - Bottom nav: shrink to content, sits at the bottom of the
         flex column naturally — no sticky/fixed required
       - Overlay: absolute, covers the whole shell when visible

     Earlier drafts used position:sticky on the bottom nav with a
     padding-bottom hack on the shell. That fights HA card height
     constraints in panel mode and leaves the nav floating mid-page
     when content is short. The flex-in-flow approach below is
     stable across all panel sizes.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] {
    position: relative;
    /* shell.js already sets height:100% and flex column on .evcc-shell;
       no overrides needed beyond making sure the host actually has
       full height. ha-card and the panel host take care of this in
       panel mode; for grid-card mode we still get a sensible result. */
  }

  /* On mobile, the regular desktop .evcc-nav inside the header is
     suppressed by replacing the header HTML — but the .evcc-nav
     fallback rule below makes sure no stale top nav ever leaks
     visually. */
  .evcc-shell[data-viewport="mobile"] .evcc-nav {
    display: none;
  }

  /* ===========================================================
     MOBILE HEADER
     ----------------------------------------------------------- */

  .evcc-mobile-header {
    display:     flex;
    flex-direction: column;
    gap:         2px;
    padding:     10px 14px;
    border-bottom: 1px solid var(--evcc-border-subtle);
    background:  var(--evcc-surface-panel);
    position:    sticky;
    top:         0;
    z-index:     9;
  }

  .evcc-mobile-vacuum-name {
    font-size:   1.05rem;
    font-weight: 600;
    color:       var(--evcc-text-primary);
    line-height: 1.2;
    overflow:    hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .evcc-mobile-vacuum-status {
    display:     flex;
    align-items: center;
    gap:         6px;
    font-size:   0.78rem;
    color:       var(--evcc-text-secondary);
  }

  .evcc-mobile-vacuum-status-label {
    text-transform: capitalize;
  }

  .evcc-mobile-battery {
    margin-left: auto;
    font-weight: 500;
    color:       var(--evcc-text-primary);
    font-variant-numeric: tabular-nums;
  }

  /* ===========================================================
     BOTTOM NAV
     -----------------------------------------------------------
     The shell is a flex column; this root is the last flex item
     and shrinks to its content height. View stage (flex:1) above
     consumes remaining space. No sticky/fixed positioning needed.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] [data-evcc-bottom-nav-root] {
    flex:         0 0 auto;        /* don't grow, don't shrink, size to content */
    z-index:      9;
    background:   var(--evcc-surface-panel);
    border-top:   1px solid var(--evcc-border-subtle);
    /* iOS notch / Android gesture bar inset. Padding is applied to
       the inner .evcc-mobile-nav so the border-top sits flush. */
  }

  /* On desktop the slot stays present but empty. flex:0 keeps it
     from claiming space. */
  .evcc-shell[data-viewport="desktop"] [data-evcc-bottom-nav-root] {
    display: none;
  }

  .evcc-mobile-nav {
    display:     flex;
    align-items: stretch;
    justify-content: space-around;
    padding:     4px 0;
    padding-bottom: max(4px, env(safe-area-inset-bottom));
  }

  .evcc-mobile-nav-tab {
    flex:        1 1 0;
    display:     flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap:         3px;
    padding:     6px 4px;
    min-height:  56px;                /* touch target */
    background:  transparent;
    border:      none;
    color:       var(--evcc-text-secondary);
    font-size:   0.7rem;
    font-weight: 500;
    cursor:      pointer;
    transition:  color 150ms ease;
  }

  .evcc-mobile-nav-tab:active {
    background:  var(--evcc-surface-raised);
  }

  .evcc-mobile-nav-tab.active {
    color:       var(--evcc-accent);
  }

  .evcc-mobile-nav-icon {
    width:       24px;
    height:      24px;
    display:     inline-flex;
    align-items: center;
    justify-content: center;
  }

  .evcc-mobile-nav-icon svg {
    width:       100%;
    height:      100%;
  }

  .evcc-mobile-nav-label {
    line-height: 1;
  }

  /* ===========================================================
     OVERFLOW SHEET ("More")
     -----------------------------------------------------------
     Bottom sheet that slides up over the bottom nav when the
     user taps the More tab. Backdrop is a full-card overlay
     that dismisses on tap.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] [data-evcc-mobile-overlay-root] {
    /* Container for sheet + backdrop. Absolute within the
       position:relative shell so backdrop dims the whole card.
       Empty when _mobileMoreOpen is false (renderer returns "");
       pointer-events:none on the container so an empty overlay
       never blocks the card. */
    position: absolute;
    inset:    0;
    pointer-events: none;
    z-index:  10;
  }

  /* Hidden on desktop. */
  .evcc-shell[data-viewport="desktop"] [data-evcc-mobile-overlay-root] {
    display: none;
  }

  .evcc-mobile-more-backdrop {
    position:     absolute;
    inset:        0;
    background:   rgba(0, 0, 0, 0.45);
    pointer-events: auto;
    animation:    evcc-mobile-fade-in 150ms ease-out both;
  }

  .evcc-mobile-more-sheet {
    position:     absolute;
    left:         0;
    right:        0;
    /* Sit above the bottom nav. The nav's height is dynamic
       (label + icon + padding + safe-area), so we use bottom:100%
       on a virtual reference. Concretely: the overlay container
       is the full shell, so we anchor to the same bottom as the
       shell — i.e. flush with the bottom nav above it. */
    bottom:       0;
    margin-bottom: 56px;      /* approx nav height; tighter than 64 */
    background:   var(--evcc-surface-panel);
    border-top:   1px solid var(--evcc-border-subtle);
    border-top-left-radius:  14px;
    border-top-right-radius: 14px;
    padding:      8px 0 max(8px, env(safe-area-inset-bottom));
    box-shadow:   0 -4px 24px rgba(0, 0, 0, 0.35);
    pointer-events: auto;
    animation:    evcc-mobile-slide-up 180ms ease-out both;
  }

  .evcc-mobile-more-handle {
    width:        38px;
    height:       4px;
    background:   var(--evcc-border-subtle);
    border-radius: 2px;
    margin:       4px auto 12px;
  }

  .evcc-mobile-more-item {
    display:      block;
    width:        100%;
    padding:      14px 20px;
    background:   transparent;
    border:       none;
    color:        var(--evcc-text-primary);
    font-size:    0.95rem;
    text-align:   left;
    cursor:       pointer;
    transition:   background-color 120ms ease;
  }

  .evcc-mobile-more-item:active {
    background:   var(--evcc-surface-raised);
  }

  .evcc-mobile-more-item.active {
    color:        var(--evcc-accent);
    font-weight:  600;
    background:   color-mix(in srgb, var(--evcc-accent) 10%, transparent);
  }

  @keyframes evcc-mobile-fade-in {
    from { opacity: 0; }
    to   { opacity: 1; }
  }

  @keyframes evcc-mobile-slide-up {
    from { transform: translateY(100%); }
    to   { transform: translateY(0); }
  }

  /* ===========================================================
     VIEW STAGE PADDING
     -----------------------------------------------------------
     Desktop has 20-24px of viewport padding via .evcc-view-stage.
     On mobile that eats too much horizontal real estate; tighten.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-view-stage {
    padding: 12px 10px;
  }

  /* ===========================================================
     ROOMS VIEW — mobile layout
     -----------------------------------------------------------
     Desktop is a side-by-side workspace: rooms grid on the left,
     Run Profiles aside on the right. On mobile both columns
     have to stack into a single scroll lane.

     Action bar: chips wrap; primary action chip claims full
     width so the Start button is the visually dominant target.

     Room card: order controls + gear shrink, name and chips
     remain readable; touch targets stay >=44px.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-workspace {
    /* Was a grid/flex split. Stack vertical. */
    display:        flex;
    flex-direction: column;
    gap:            14px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-main {
    width: 100%;
  }

  /* Force single-column room grid even at sizes above 720px
     when the card is rendered in mobile shell (e.g. landscape
     phones in a constrained panel). The existing
     @media (max-width: 720px) rule in rooms styles covers
     portrait; this is the belt-and-suspenders. */
  .evcc-shell[data-viewport="mobile"] .evcc-room-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  /* Action bar — top row stacks vertically, chip group wraps. */
  .evcc-shell[data-viewport="mobile"] .evcc-rooms-action-bar {
    padding: 10px;
    gap:     8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-bar-top {
    flex-direction: column;
    align-items:    stretch;
    gap:            10px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-queue-summary {
    font-size: 0.9rem;
  }

  /* Primary action gets full width; secondary chips wrap below. */
  .evcc-shell[data-viewport="mobile"] .evcc-rooms-action-bar .evcc-chips {
    display:         flex;
    flex-wrap:       wrap;
    gap:             8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-action-bar
    .evcc-chip[data-action="primary-room-action"] {
    flex:        1 1 100%;
    min-height:  48px;
    font-size:   1rem;
    font-weight: 600;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-action-bar
    .evcc-chip:not([data-action="primary-room-action"]) {
    /* Secondary chips: roughly half-width each so two fit per row,
       respecting the wrap when more than two exist. */
    flex:       1 1 calc(50% - 4px);
    min-height: 40px;
  }

  /* Room card tightening for narrow viewport. */
  .evcc-shell[data-viewport="mobile"] .evcc-room-card {
    padding: 10px 12px;
    /* Make sure tap-to-toggle target stays generous. */
    min-height: 88px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card .evcc-room-row-1 {
    /* Order controls + settings gear inline at top. */
    gap: 6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card .evcc-order-controls {
    gap: 4px;
  }

  /* Slim down the Move button on mobile — the drag handle covers
     the same affordance and saves a tap target's worth of width. */
  .evcc-shell[data-viewport="mobile"] .evcc-room-card
    .evcc-order-move-button {
    display: none;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card .evcc-room-name {
    font-size:   1rem;
    line-height: 1.2;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card
    .evcc-room-setting-chips {
    gap:        4px;
    flex-wrap:  wrap;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card
    .evcc-room-setting-chip {
    font-size: 0.72rem;
    padding:   2px 6px;
  }

  /* ===========================================================
     RUN PROFILES PANEL — mobile layout
     -----------------------------------------------------------
     Desktop renders it as a right-hand aside. On mobile, drop it
     below the room grid and lay the saved profiles out as a
     horizontal scroll strip so the user can swipe through and
     tap one without losing the room grid above.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-run-profiles-panel {
    width:        100%;
    margin-top:   4px;
    border-radius: 10px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-run-profiles-list {
    display:           flex;
    flex-direction:    row;
    flex-wrap:         nowrap;
    overflow-x:        auto;
    scroll-snap-type:  x mandatory;
    gap:               8px;
    padding-bottom:    4px;
    /* Hide horizontal scrollbar visually — feels native. */
    scrollbar-width:   none;
  }
  .evcc-shell[data-viewport="mobile"] .evcc-run-profiles-list::-webkit-scrollbar {
    display: none;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-run-profiles-list > * {
    flex:            0 0 auto;
    scroll-snap-align: start;
    min-width:       42vw;     /* roughly 2.2 profiles visible per screen */
  }

  /* ===========================================================
     LEARNING SUMMARY + BANNERS
     -----------------------------------------------------------
     Compact on mobile; tighter padding, smaller font for the
     metadata rows. Banners stay full-width.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-learning-summary,
  .evcc-shell[data-viewport="mobile"] .evcc-learning-prejob-panel,
  .evcc-shell[data-viewport="mobile"] .evcc-learning-live-banner,
  .evcc-shell[data-viewport="mobile"] .evcc-incomplete-run-banner {
    padding:       10px 12px;
    font-size:     0.86rem;
    border-radius: 8px;
  }

  /* ===========================================================
     VIEW TOGGLE (list / map)
     -----------------------------------------------------------
     Buttons are tiny icon buttons. Bump them to thumb-friendly
     size on mobile.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-view-toggle {
    gap: 6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-view-toggle-btn {
    min-width:  44px;
    min-height: 44px;
    padding:    8px;
  }
  .evcc-shell[data-viewport="mobile"] .evcc-rooms-view-toggle-btn svg {
    width:  20px;
    height: 20px;
  }
`;
