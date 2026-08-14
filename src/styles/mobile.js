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
    /* Reserve room on the right so the vacuum name/status never run under the
       language globe (absolutely positioned top-right below). */
    padding-inline-end: 52px;
    border-bottom: 1px solid var(--evcc-border-subtle);
    background:  var(--evcc-surface-panel);
    position:    sticky;
    top:         0;
    z-index:     9;
  }

  /* Switch Map picker row in the mobile header (below the vacuum name). */
  .evcc-mobile-header-mapswitch {
    margin-top: 6px;
  }

  /* Language globe — pinned to the top-right of the sticky mobile header. The
     header is the positioned ancestor; the dropdown/backdrop stack within the
     header's z-index:9 context, above the view-stage. */
  .evcc-mobile-header-lang {
    position: absolute;
    top:      8px;
    inset-inline-end:    10px;
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
    margin-inline-start: auto;
    font-weight: 500;
    color:       var(--evcc-text-primary);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;   /* "Battery 100%" must not wrap between label and value */
  }

  /* Same bands as the desktop header (.evcc-battery.low/.critical). Missing here
     meant a critical battery read exactly like a full one on mobile. */
  .evcc-mobile-battery.low      { color: var(--evcc-sem-warning); }
  .evcc-mobile-battery.critical { color: var(--evcc-sem-error); }

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
    background:   var(--evcc-surface-overlay, rgba(0, 0, 0, 0.45));
    pointer-events: auto;
    animation:    evcc-mobile-fade-in 150ms ease-out both;
  }

  .evcc-mobile-more-sheet {
    position:     absolute;
    inset-inline-start:         0;
    inset-inline-end:        0;
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
    text-align: start;
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

  /* Mobile reorder uses the Move button (opens the position picker
     modal). The drag handle is hidden because HTML5 native drag
     (draggable=true + dragstart) does not fire from touch events,
     so the handle would be dead weight on touch devices. Earlier
     version had this backwards — handle visible, Move hidden — which
     left mobile users with no working reorder path. */
  .evcc-shell[data-viewport="mobile"] .evcc-room-card
    .evcc-order-drag-handle {
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

  /* The row already wraps — that lives on the base rule in styles/map.js,
     deliberately NOT here, because a narrow host the shell still calls desktop
     needs it just as much as a phone does. This only widens the row gap to
     match the thumb-sized buttons set just below, and gives the wrapped rows
     the same breathing room horizontally and vertically.

     Why it has to wrap at all: at the 44px thumb minimum below, the map view's
     eight controls — six icons plus the Configure button's text label and the
     mascot group — come to roughly 500px against a ~390px viewport. The buttons
     cannot shrink, since that minimum is the whole point, so before wrapping the
     surplus simply left the screen and took the last controls with it. */
  .evcc-shell[data-viewport="mobile"] .evcc-rooms-view-toggle {
    gap:     6px;
    row-gap: 6px;
  }

  /* Configure goes icon-only here. It is the one text-width control in the row,
     and at phone width that width is enough to push it onto a wrap row by
     itself — a whole row spent on one word, with the mascot group pushed down
     to a third. Dropped to a square icon it rejoins the first row and the bar
     settles at two. The button keeps its title and aria-label, so the name is
     still there for anyone who needs it; only the painted text goes. */
  .evcc-shell[data-viewport="mobile"] .evcc-rooms-view-toggle-btn-label {
    display: none;
  }

  /* ...and without the label it must stop reserving label-sized box. The base
     rule gives this button width:auto and side padding for its text; square it
     back up so it matches the icons it now sits beside. */
  .evcc-shell[data-viewport="mobile"] .evcc-rooms-view-toggle-btn--configure {
    width:   44px;
    padding: 8px;
    gap:     0;
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

  /* ===========================================================
     MAP CONFIG VIEW — mobile layout
     -----------------------------------------------------------
     Desktop:  header (back btn + title)
               body  = [ map | side-panel 220px ]   horizontal split
               panel (image variants section)

     Mobile:   header (compact)
               body  = stacked vertical
                       [ map (60vh-ish) ]
                       [ side-panel full-width below ]
               panel (image variants — tighter)

     The map gets a fixed-ish viewport-relative height so it
     stays visible while the user reaches the adjustment buttons
     below. The side-panel becomes a scrollable region below the
     map. Vertex/edge nudge buttons grow to 44px touch targets.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-header {
    padding: 8px 10px;
    gap:     8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-back {
    /* Touch target — bump to 44px effective height via padding. */
    padding:    8px 12px 8px 8px;
    font-size:  0.9rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-title {
    font-size:  0.95rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-body {
    /* Was horizontal split — stack vertical on mobile. */
    flex-direction: column;
    min-height:     0;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-body
    > .evcc-map-container--config {
    /* Map fills the available width and gets ~55% of vertical
       space so the side-panel below is reachable without
       scrolling the whole card. */
    width:        100%;
    min-height:   0;
    flex:         0 0 55vh;
    position:     relative;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-side-panel {
    /* Was a 220px right column. Full width below the map now;
       scrolls internally if section content overflows. */
    width:          100%;
    border-inline-start:    none;
    border-top:     1px solid var(--evcc-border-subtle);
    flex:           1 1 auto;
    min-height:     0;
    max-height:     45vh;
    padding-bottom: 8px;
  }

  /* ===========================================================
     NUDGE BUTTONS — touch sizing
     -----------------------------------------------------------
     Desktop: 36x36 directional, 28x28 edge. Mobile bumps both to
     44px so thumb taps land reliably.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-pad {
    /* Center the pad horizontally on mobile — desktop floats it
       to flex-start which looks lost on a full-width column. */
    align-self: center;
    gap:        6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-row {
    gap: 6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-btn {
    width:      44px;
    height:     44px;
    font-size:  1.1rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-btn--edge {
    width:      44px;
    height:     44px;
    font-size:  1.1rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-btn--reset {
    font-size:  1rem;
  }

  /* Edge-grid rows: align label / value / +/- buttons across the
     wider mobile width. */
  .evcc-shell[data-viewport="mobile"] .evcc-map-edge-grid {
    gap: 6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-edge-row {
    gap: 8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-edge-label {
    width:     60px;
    font-size: 0.85rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-edge-val {
    min-width: 36px;
    font-size: 0.85rem;
  }

  /* Vertex chips — make them tappable. */
  .evcc-shell[data-viewport="mobile"] .evcc-map-vertex-chips {
    gap: 6px;
  }

  /* ===========================================================
     CONFIG SECTIONS (sections inside the side panel)
     -----------------------------------------------------------
     Tighten padding on mobile but keep enough vertical
     separation that successive sections look like distinct
     control groups.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-section {
    padding: 12px 12px;
    gap:     12px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-section--hint {
    /* The "click a segment" placeholder gets dramatically tighter. */
    padding:    24px 16px;
    text-align: center;
  }

  /* ===========================================================
     CONFIG BOTTOM PANEL (Image Variants section)
     -----------------------------------------------------------
     Desktop renders this as the final row of the config view.
     On mobile that's still fine, just tighter.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-panel {
    border-top: 1px solid var(--evcc-border-subtle);
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-analyze-row {
    flex-wrap: wrap;
    gap:       8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-btn {
    min-height: 44px;
    padding:    10px 14px;
    font-size:  0.92rem;
  }

  /* ===========================================================
     ZOOM TOOLBAR (used by both Rooms map view and Config map)
     -----------------------------------------------------------
     Desktop sizes are fine for mouse but mobile needs bigger
     buttons. Also reposition to a thumb-reachable area when on
     a narrow viewport — bottom-right of the map container,
     not too far from where the thumb naturally rests.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-zoom-toolbar {
    /* Same corner as desktop, but more clearance from the edge
       and bigger touch targets. */
    inset-inline-end:   12px;
    bottom:  12px;
    padding: 6px 8px;
    gap:     6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-zoom-btn {
    width:     40px;
    height:    40px;
    font-size: 18px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-zoom-readout {
    min-width: 48px;
    font-size: 13px;
  }

  /* ===========================================================
     CARD-LIKE PANEL VIEWS (Maintenance, Base Station, Metrics,
     Learning Review, Mapping Review)
     -----------------------------------------------------------
     All of these share a common structural pattern: a vertical
     .evcc-{view}-view container with a grid of panels using
     repeat(auto-fit, minmax(180px, 1fr)). At <360px the grids
     naturally collapse to 1fr, so structural CSS already works.

     What needs adjustment on mobile:
       - Panel padding: 16px → 12px (saves 8px horizontal real
         estate, which matters at 360px viewport)
       - Inter-panel gap: 12px → 10px
       - Stat / value font sizes: tighter
       - Buttons within panels: bump to 44px touch targets
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-base-station-panel,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-panel,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-panel,
  .evcc-shell[data-viewport="mobile"] .evcc-review-panel {
    padding: 12px;
    gap:     10px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-base-station-view,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-view,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-view,
  .evcc-shell[data-viewport="mobile"] .evcc-review-view {
    gap: 10px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-base-station-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-review-grid {
    gap: 10px;
  }

  /* Force single-column on inner grids that use minmax(180px, 1fr).
     At 360px-12px-12px=336px available, a single 336px column wins
     over two ~160px ones for readability. */
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-stats,
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-activity-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-action-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-card-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-stats,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-card-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-window-grid {
    /* Two columns — most stats fit fine pair-wise on mobile,
       saves vertical space. */
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-base-station-stat,
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-activity-card,
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-action-card,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-card,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-stat,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-card {
    padding: 10px;
    gap:     4px;
  }

  /* ===========================================================
     TABLES — horizontal scroll on overflow
     -----------------------------------------------------------
     The Metrics view uses <table> elements that have many
     columns and overflow on phones. Wrap them in an
     overflow-x:auto container by styling the table's parent.
     For tables without a dedicated wrapper, also tighten
     padding so they wrap less aggressively.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table {
    font-size: 0.78rem;
    /* If the table itself overflows the panel, the parent panel's
       overflow:hidden would clip. Let it scroll within the panel. */
    display:     block;
    overflow-x:  auto;
    white-space: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table thead,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table tbody,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table tr {
    /* Required when table itself is display:block. */
    display: table;
    width:   100%;
    table-layout: auto;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table th,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table td {
    padding: 5px 8px;
  }

  /* ===========================================================
     ROOM RULES + THEME + SETUP — generic touch-target pass
     -----------------------------------------------------------
     These views are less table-heavy but include lots of
     buttons / form controls that default to ~32px on desktop.
     Generic 44px bump for any button inside a content view
     stage on mobile, except inside the bottom-tab nav (which
     has its own sizing).
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-view-stage button:not(
    .evcc-mobile-nav-tab,
    .evcc-mobile-more-item,
    .evcc-chip,
    .evcc-map-nudge-btn,
    .evcc-map-zoom-btn,
    .evcc-rooms-view-toggle-btn,
    .evcc-room-card *,
    .evcc-order-controls *
  ) {
    min-height: 44px;
  }

  /* Form inputs in modals / sidebar drawers — touch-sized. */
  .evcc-shell[data-viewport="mobile"] .evcc-view-stage input[type="text"],
  .evcc-shell[data-viewport="mobile"] .evcc-view-stage input[type="number"],
  .evcc-shell[data-viewport="mobile"] .evcc-view-stage input[type="search"],
  .evcc-shell[data-viewport="mobile"] .evcc-view-stage select {
    min-height: 44px;
    font-size:  1rem;     /* avoid iOS auto-zoom on focus */
  }

  /* ===========================================================
     MODALS / SHEETS
     -----------------------------------------------------------
     Mobile modal styling lives in src/styles/index.js inside
     MODAL_HOST_STYLES under a @media (max-width: 600px) block,
     not here. The modal host is mounted on document.body (so the
     shell can be cleanly destroyed without ripping open modals),
     which means shell-data-attribute selectors here can't reach
     it across the document tree boundary. The viewport media
     query inside MODAL_HOST_STYLES is the right hook.
     =========================================================== */

  /* ===========================================================
     TEST BUILD (2026-08-10) — COMPACT CHROME FOR THE THEME VIEW
     -----------------------------------------------------------
     Paired with MOBILE_TOKEN_EDITOR (renderers/theme.js). The
     token editor is a long scrolling list inside its own
     .evcc-theme-editor-scrollbox, so the scarce resource on a
     phone is VERTICAL BUDGET, not layout. Both chrome bands are
     trimmed on this view only — every other view is untouched.

     Header: the vacuum/dock/battery status rows say nothing
     useful while you are editing colours. Dropped entirely; the
     name and the language control stay. This is the bigger
     reclaim and it costs no touch target.

     Nav: labels go and the icon shrinks, but min-height only
     drops 56 -> 48px. Tappability at the SHIPPED size was
     verified on-device by hand; 44px is the accepted floor and
     going under it would spend a win already banked. Shrink the
     ink, keep the hit area.
     =========================================================== */

  .evcc-mobile-header--compact {
    padding-block: 6px;
  }

  .evcc-mobile-header--compact .evcc-mobile-vacuum-status {
    display: none;
  }

  .evcc-mobile-nav--compact .evcc-mobile-nav-tab {
    min-height: 48px;   /* >= the 44px touch floor; see note above */
    gap:        0;
    padding:    4px;
  }

  .evcc-mobile-nav--compact .evcc-mobile-nav-label {
    display: none;
  }

  .evcc-mobile-nav--compact .evcc-mobile-nav-icon {
    width:  20px;
    height: 20px;
  }

  /* ===========================================================
     THIRD CHROME BAND — THE THEME FOOTER
     -----------------------------------------------------------
     Header and nav were trimmed above. The footer is the band
     that was left, and once .evcc-view-footer was allowed to
     wrap (styles/theme.js) it stopped overflowing and started
     COSTING instead: ten controls at desktop padding settle into
     five rows, 130px of a 760px shell.

     Trim the ink, not the hit area — the same rule the nav note
     states. These are .evcc-chip buttons whose target is set by
     padding, so the reduction is deliberately modest; the win
     comes from more chips fitting per row, which removes whole
     ROWS rather than shaving each one.

     Scoped to the theme stage: every other view's footer, and
     the same chips outside the footer, are untouched.
     =========================================================== */

  @media (max-width: 600px), (max-height: 500px) {
    .evcc-view-stage[data-view="theme"] .evcc-view-footer {
      gap: 6px;
      padding-top: 2px;
    }

    .evcc-view-stage[data-view="theme"] .footer-left,
    .evcc-view-stage[data-view="theme"] .footer-right {
      gap: 6px;
    }

    .evcc-view-stage[data-view="theme"] .evcc-view-footer .evcc-chip {
      padding: 7px 10px;
      font-size: 0.78rem;
    }

    /* ICON-ONLY CHIPS — the footer's import/export four AND the per-token
       reset, which becomes an undo glyph (Chris, 2026-08-11: "reset could
       swap to a smaller target with an undo button").

       Scoped to the whole theme VIEW rather than the footer, because the
       reset lives inside a token row. The selector below is compound
       (--iconable AND .evcc-chip) deliberately: that ties the footer's
       generic chip rule above on specificity, so source order decides and
       this wins. Written as the bare modifier alone it would LOSE to that
       rule and the footer chips would keep their text padding.
       (No backticks in this comment — JS template literal.)

       Labels go; the hit area does not. 44px is the floor the nav note
       already banked, and aria-label carries the accessible name once the
       text is display:none. */
    .evcc-view-stage[data-view="theme"] .evcc-chip--iconable .evcc-chip-label {
      display: none;
    }

    .evcc-view-stage[data-view="theme"] .evcc-chip--iconable .evcc-chip-icon {
      display: block;
    }

    .evcc-view-stage[data-view="theme"] .evcc-chip--iconable.evcc-chip {
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    /* FOOTER ICONS ARE PILLS, NOT CIRCLES — and the six controls share ONE
       row (Chris, 2026-08-11: "make the bottom round chips pills and they
       look like they could fit in the bottom row").

       Both asks resolve to the same number. At 44x44 the icons were square,
       so the theme's pill radius rendered them as CIRCLES next to the 28.5px
       pills of Discard / Save Changes — two shape languages in one band. And
       six controls measured 368.7px against 340px of usable footer at 360px
       wide, which is why they wrapped on-device (at 390 they already fit).

       36x28 is oblong, so the same radius now reads as a pill, it matches the
       neighbours' height exactly, and the row totals ~331px — inside 340 with
       room to spare. Height matches Discard / Save deliberately: those ship
       at 28.5px today, so this is the band's existing target size, not a new
       reduction. Narrower phones still wrap, which is the correct fallback. */
    /* EXPLICIT width/height, not a content-derived one. box-sizing is
       border-box here, so 36 - 12 padding - 2 border leaves a 22px content
       box around a 20px glyph. Sized rather than derived because the
       content-based flex basis resolved ~5px wider than the icon plus padding
       accounts for, and that surplus multiplied by four chips was enough to
       push this band back onto a second row. A fixed box makes the one-row
       budget arithmetic that the note below depends on actually hold. */
    .evcc-view-stage[data-view="theme"] .evcc-view-footer .evcc-chip--iconable.evcc-chip {
      width: 36px;
      min-width: 36px;
      height: 28px;
      min-height: 28px;
      padding: 4px 6px;
    }

    /* LONGER LOCALES TAKE A SECOND ROW HERE. ACCEPTED, AND IT IS A WRAP.
       The band is sized so all six controls fit ONE row in English down to
       320px. German ("Speichern" / "Verwerfen"), Dutch and French exceed that
       and wrap — verified on-device: Spanish holds one row, French takes two.
       A two-row footer is a fine outcome; nothing is lost.

       Do not buy that row back with height. The vertical budget is what took
       this view from ZERO visible token rows to two, and the footer is only
       30px of it. Fixes that stay inside the trade cost no height: a shorter
       label (theme.save_changes -> common.save did exactly this, 96px -> 47px)
       or moving a control out of the band.

       The band that genuinely CLIPS is .token-hint, not this one — its own
       rule in styles/theme.js carries that note. */

    /* THE PER-TOKEN RESET IS THE EXCEPTION TO THE 44px FLOOR ABOVE.
       It sits INSIDE a token row, not in a chrome band, so the floor works
       against the thing this pass exists for: measured at 44 it took a
       modified row from 133px to 165px — the icon made the row TALLER than
       the text chip it replaced (which was 38x18). At 32 the row stays tight
       and the target is still nearly double the 18px height the text chip
       actually offered, so tappability goes up and height goes down.
       Chrome bands keep 44; only the in-row control is reduced. */
    .evcc-view-stage[data-view="theme"] .token-top-strip .evcc-chip--iconable.evcc-chip,
    .evcc-view-stage[data-view="theme"] .token-head-actions .evcc-chip--iconable.evcc-chip {
      min-width: 32px;
      min-height: 32px;
      padding: 5px;
    }

    /* The in-row glyph is 18px, so the SPAN must match it — see the note on
       .evcc-chip-icon in styles/theme.js: the box is sized explicitly because
       the svg contributes no intrinsic size, and the two must move together
       or the icon overflows its own box again. */
    .evcc-view-stage[data-view="theme"] .token-top-strip .evcc-chip-icon,
    .evcc-view-stage[data-view="theme"] .token-head-actions .evcc-chip-icon,
    .evcc-view-stage[data-view="theme"] .token-top-strip .evcc-chip-icon svg,
    .evcc-view-stage[data-view="theme"] .token-head-actions .evcc-chip-icon svg {
      width: 18px;
      height: 18px;
    }

    /* FLOOR-TEXTURE CONTROLS — not on a phone (Chris, 2026-08-11: "download
       floor feels odd, as well as the floor selector; they can go away in
       mobile, same for marble presets").

       Icons alone were not enough: they took the footer from five rows to
       four, because shrinking four of TEN controls cannot remove a row while
       the other six still wrap. These four are the ones that earn least on a
       phone — picking a floor material and applying a marble preset is
       desk work — so dropping them is what actually buys the rows back.

       display:none also removes them from the accessibility tree, which is
       correct here: the control is gone at this width, not merely invisible.
       Both selects share .evcc-floor-scope-select, so one selector covers the
       floor scope AND the marble preset. */
    .evcc-view-stage[data-view="theme"] .evcc-view-footer .evcc-floor-scope-select,
    .evcc-view-stage[data-view="theme"] .evcc-view-footer [data-action="download-floor-theme"],
    .evcc-view-stage[data-view="theme"] .evcc-view-footer [data-action="apply-floor-preset"] {
      display: none;
    }

    /* TOKEN ROWS — drop the redundant text field, keep the only-input case.
       (Chris, 2026-08-11: "mobile can drop the text input and display for
       values unless that is their only input".)

       Row height is the binding constraint once the chrome is dealt with:
       ~174px per row over 402 rows, so a phone shows one or two at a time.
       These two fields are the redundant ones —

         --color    the hex field restates what the rail already shows in
                    colour; the rail edits it, and the strip's hint teaches
                    the gesture. Only the INPUT is hidden — the strip also
                    carries the conditional Reset button, which stays.
         --numeric  the number field duplicates the slider, whose bubble
                    already reads the value out while dragging.

       Deliberately NOT touched, because there the text IS the only input:
         --color-mix  .token-colormix-swatch is a plain div, background only
         --text / font presets  no other control exists at all */
    .evcc-view-stage[data-view="theme"] .evcc-token-row--color .token-input--hex,
    .evcc-view-stage[data-view="theme"] .evcc-token-row--numeric .token-control-row--number {
      display: none;
    }
  }

  /* ===========================================================
     LANDSCAPE — AUTO-HIDING SHELL CHROME
     -----------------------------------------------------------
     Measured at 772x360: the status pane is 33px and the nav 56px, so 89px —
     25% of the viewport — goes to chrome that is mostly not being read. Both
     are already in their --compact variants, so that is the floor without
     hiding them.

     The attribute is set by main.js on scroll direction: down hides, up
     reveals, and near the top it always shows. This stylesheet owns what the
     attribute MEANS, so the behaviour and the layout cannot drift apart.

     WHY BOTH max-height AND transform. .evcc-mobile-nav is position:static, so
     translating it alone would slide it away and leave its 56px hole behind —
     the space would not be reclaimed, which is the entire point. Collapsing
     max-height reclaims it; the transform is what makes that read as a slide
     instead of a snap. They transition together.

     Chrome-only: this changes whether two panes are drawn, never what is in
     them or what is reachable, so the worst case is cosmetic. If it reads as
     jank on a device, the whole thing reverts as one commit.
     =========================================================== */

  /* EVERY RULE BELOW IS INSIDE (max-height: 500px), and that is load-bearing.

     The base rule sets overflow:hidden and max-height on the chrome so it can
     be collapsed. Left unscoped it applied to ALL mobile, including PORTRAIT,
     where nothing ever auto-hides — so portrait carried clipping machinery it
     had no use for. overflow:hidden on the header clips the language dropdown
     that lives inside it, which is the third time tonight that dropdown has
     been collateral damage from a rule aimed at something else.

     Rule of thumb this earned: styling that exists to serve a behaviour should
     be scoped to where that behaviour runs. It is not free elsewhere; it is
     just not obviously broken yet. */
  @media (max-height: 500px) {

  /* NOT THE ONE IN THE PREVIEW.

     The theme editor's App Shell preview renders the REAL mobile header as a
     specimen, so there are TWO .evcc-mobile-header elements inside the shell
     and a descendant selector hits both. Hiding the chrome therefore collapsed
     the specimen too and left the preview pane empty — measured on the live
     card: preview shell-frame h=1, its header maxH=0.

     This is the same defect as the z-index one fixed earlier by isolating the
     preview frames: a preview that renders the real component inherits every
     rule aimed at the real component. Any future rule targeting shell chrome
     needs this guard too. */
  .evcc-shell[data-viewport="mobile"] .evcc-mobile-header:not(.evcc-theme-preview-shell-frame *),
  .evcc-shell[data-viewport="mobile"] .evcc-mobile-nav:not(.evcc-theme-preview-shell-frame *) {
    max-height: 200px;
    overflow: hidden;
    transition:
      max-height 180ms ease,
      padding-block 180ms ease,
      transform 180ms ease,
      opacity 140ms ease;
  }

  /* padding-block goes too, or max-height:0 still leaves the box its padding —
     measured 12px of a supposedly hidden pane, which is 12px not reclaimed.

     :not([data-chrome-pin-status]) rather than a second rule restoring the
     values: the first version put the padding back by hand and guessed 10px,
     which is the base padding and NOT the --compact one, so a pinned header
     rendered 41px against its natural 33. A rule that never matches cannot
     restore the wrong thing. */
  .evcc-shell[data-viewport="mobile"][data-chrome-hidden]:not([data-chrome-pin-status])
    .evcc-mobile-header:not(.evcc-theme-preview-shell-frame *) {
    max-height: 0;
    padding-block: 0;
    transform: translateY(-100%);
    opacity: 0;
    border-bottom-width: 0;
  }

  .evcc-shell[data-viewport="mobile"][data-chrome-hidden] .evcc-mobile-nav:not(.evcc-theme-preview-shell-frame *) {
    max-height: 0;
    padding-block: 0;
    transform: translateY(100%);
    opacity: 0;
  }

  /* PINNED WHILE A JOB IS IN FLIGHT — handled by the :not() above, which simply
     does not hide it. The 33px is worth paying exactly when the numbers behind
     it are moving; a running or paused job is when a user wants status on
     screen without going looking for it. The nav still hides: navigation is not
     live information. */

  }
  /* end @media (max-height: 500px) — the auto-hide exists only in landscape */

  /* Someone who has asked not to see motion gets the space back without the
     slide — the reclaim is the feature, the animation is decoration. Outside
     the block above on purpose: nesting two media queries would need @media
     (max-height: 500px) and (prefers-reduced-motion: reduce), and this reads
     more plainly as "never animate this chrome" — which is also true in
     portrait, where there is now no transition to cancel anyway. */
  @media (prefers-reduced-motion: reduce) {
    .evcc-shell[data-viewport="mobile"] .evcc-mobile-header,
    .evcc-shell[data-viewport="mobile"] .evcc-mobile-nav {
      transition: none;
    }
  }
`;
