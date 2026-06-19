// CSS styles for the map view, map config editor, selection bar, nudge pad, vertex/room-assignment controls, and animal companion.

export const mapStyles = `

  /* =========================================================
     VIEW TOGGLE STRIP
     ========================================================= */

  .evcc-rooms-view-toggle {
    display:     flex;
    gap:         4px;
    margin-left: auto;
    flex-shrink: 0;
  }

  .evcc-rooms-view-toggle-btn {
    display:         flex;
    align-items:     center;
    justify-content: center;
    width:           32px;
    height:          32px;
    padding:         0;
    border-radius:   8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:      transparent;
    color:
      var(--evcc-text-muted,
      rgba(240, 242, 245, 0.48));
    cursor:          pointer;
    transition:      background 150ms ease,
                     color 150ms ease,
                     border-color 150ms ease;
  }

  .evcc-rooms-view-toggle-btn:hover {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color:
      var(--evcc-text-secondary,
      rgba(240, 242, 245, 0.72));
  }

  .evcc-rooms-view-toggle-btn.active {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color:       var(--evcc-text-primary, #f0f2f5);
    border-color:
      var(--evcc-border-strong,
      rgba(255, 255, 255, 0.18));
  }

  /* =========================================================
     MAP VIEW CONTAINER
     ========================================================= */

  .evcc-map-view {
    display:        flex;
    flex-direction: column;
    flex:           1;
    min-height:     0;
  }

  .evcc-map-container {
    position:      relative;
    width:         100%;
    aspect-ratio:  1;
    min-height:    240px;
    overflow:      hidden;
    border-radius: var(--evcc-radius-card, 12px);
    background:    var(--evcc-surface-panel, #1c2127);
    isolation:     isolate;
  }

  .evcc-map-layers {
    position:         absolute;
    inset:            0;
    transform-origin: 0 0;
    will-change:      transform;
  }

  .evcc-map-image {
    display:            block;
    width:              100%;
    height:             100%;
    object-fit:         contain;
    user-select:        none;
    -webkit-user-drag:  none;
  }

  /* VA-rendered backdrop (Wave 1): the card draws the device room raster to this
     canvas. Shares .evcc-map-image (object-fit:contain → letterboxes the same as the
     live image, so the overlays align). Non-room pixels stay transparent → the
     container's themed background reads as floor. The canvas intrinsic size is set on
     draw (grid dims), so the contain ratio matches the device frame. */
  .evcc-map-render-canvas {
    image-rendering: auto;
  }

  /* Live-map rotation wrapper: turns the whole content layer (backdrop image +
     segment SVG + labels + mascot) TOGETHER so overlays stay registered at every
     90° step. Sits INSIDE .evcc-map-layers (which owns zoom/pan, origin 0 0) with
     its own centre origin, so rotation and pan/zoom never fight; the square map
     container keeps a 90° turn fully in frame. --evcc-map-rotation (set inline by
     the renderer) lets labels + mascot counter-rotate upright. */
  .evcc-map-content-rotator {
    position:         absolute;
    inset:            0;
    transform-origin: 50% 50%;
    will-change:      transform;
    transition:       transform 0.2s ease;
  }

  .evcc-map-svg {
    position:       absolute;
    inset:          0;
    width:          100%;
    height:         100%;
    pointer-events: none;
  }

  /* =========================================================
     ZOOM TOOLBAR
     =========================================================
     Floating control bar pinned to the bottom-right of the
     map container. Sits above all other map layers; pointer
     events enabled so the buttons are clickable. The buttons
     drive state.applyMapZoom / state.resetMapTransform; the
     readout reflects state.mapZoom() as a percentage.
     ========================================================= */

  .evcc-map-zoom-toolbar {
    position:        absolute;
    right:           10px;
    bottom:          10px;
    display:         flex;
    align-items:     center;
    gap:             4px;
    padding:         4px 6px;
    background:      var(--evcc-map-tooltip-bg, rgba(20, 30, 50, 0.85));
    border:          1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.15));
    border-radius:   6px;
    backdrop-filter: blur(4px);
    z-index:         10;
    pointer-events:  auto;
    user-select:     none;
  }

  .evcc-map-zoom-btn {
    width:           28px;
    height:          28px;
    line-height:     1;
    font-size:       16px;
    font-weight:     600;
    color:           var(--evcc-map-tooltip-text, #fff);
    background:      var(--evcc-surface-action, rgba(255, 255, 255, 0.08));
    border:          1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.15));
    border-radius:   4px;
    cursor:          pointer;
    display:         flex;
    align-items:     center;
    justify-content: center;
    transition:      background-color 0.15s ease, transform 0.05s ease;
  }
  .evcc-map-zoom-btn:hover {
    background:      var(--evcc-surface-action-hover, rgba(255, 255, 255, 0.18));
  }
  .evcc-map-zoom-btn:active {
    transform:       scale(0.93);
  }

  .evcc-map-zoom-readout {
    min-width:       42px;
    text-align:      center;
    font-size:       12px;
    color:           var(--evcc-map-tooltip-hint, rgba(255, 255, 255, 0.7));
    padding:         0 2px;
    font-variant-numeric: tabular-nums;
  }

  /* =========================================================
     ZONE CLEAN (ad-hoc draw-a-box → clean)
     ========================================================= */

  /* Toolbar toggle, active state. */
  .evcc-map-zoom-btn--on {
    background:   var(--evcc-accent, #3b82f6);
    border-color: var(--evcc-accent, #3b82f6);
    color:        #fff;
  }

  /* In draw mode: crosshair cursor; segment polygons + labels stop intercepting
     the press so the rubber-band handler owns the drag. */
  .evcc-map-container--zone,
  .evcc-map-container--hide { cursor: crosshair; }
  /* The segment polygons + companion set pointer-events:all, which stays hittable
     even under a parent svg's pointer-events:none — so suppress the ACTUAL targets
     (higher specificity wins) so the rubber-band owns the press. */
  .evcc-map-container--zone .evcc-map-svg,
  .evcc-map-container--zone .evcc-map-polygon,
  .evcc-map-container--zone .evcc-map-animal,
  .evcc-map-container--zone .evcc-map-label,
  .evcc-map-container--hide .evcc-map-svg,
  .evcc-map-container--hide .evcc-map-polygon,
  .evcc-map-container--hide .evcc-map-animal,
  .evcc-map-container--hide .evcc-map-label { pointer-events: none !important; }

  /* The in-progress drag box (dashed), positioned in pct of .evcc-map-layers. */
  .evcc-zone-draft {
    position:       absolute;
    box-sizing:     border-box;
    border:         2px dashed var(--evcc-accent, #3b82f6);
    background:     rgba(59, 130, 246, 0.18);
    border-radius:  2px;
    pointer-events: none;
    z-index:        4;
  }
  /* Committed zones (display-only; pointer-events off so more can be drawn over). */
  .evcc-zone-rect {
    position:       absolute;
    box-sizing:     border-box;
    border:         2px solid var(--evcc-accent, #3b82f6);
    background:     rgba(59, 130, 246, 0.12);
    border-radius:  2px;
    pointer-events: none;
    z-index:        3;
  }
  .evcc-zone-rect-num {
    position:      absolute;
    top:           1px;
    left:          2px;
    font-size:     10px;
    font-weight:   700;
    line-height:   1;
    color:         #fff;
    background:     var(--evcc-accent, #3b82f6);
    border-radius: 3px;
    padding:       1px 3px;
  }

  /* HIDDEN REGIONS — user-drawn masks covering map noise (a porch off a room). Opaque map-bg
     fill so the area reads as "not mapped"; z-index 5 (rendered after labels) keeps it above
     the static map + labels but below the live robot/dock markers (z-index 6). */
  .evcc-hidden-region {
    position:       absolute;
    box-sizing:     border-box;
    background:     var(--evcc-surface-panel, #1c2127);
    z-index:        5;
    pointer-events: none;
  }
  /* While editing: a translucent tinted box (so you see what's under + that it's editable). */
  .evcc-hidden-region--edit {
    background:     rgba(59, 130, 246, 0.20);
    border:         2px dashed var(--evcc-accent, #3b82f6);
    border-radius:  2px;
  }
  .evcc-hidden-region-del {
    position:        absolute;
    top:             -9px;
    right:           -9px;
    width:           18px;
    height:          18px;
    padding:         0;
    font-size:       13px;
    line-height:     1;
    border:          none;
    border-radius:   50%;
    background:      var(--evcc-accent, #3b82f6);
    color:           #fff;
    cursor:          pointer;
    pointer-events:  auto;       /* the × stays clickable even though the mask isn't */
    display:         flex;
    align-items:     center;
    justify-content: center;
  }
  /* In-progress hide-draw box (dashed), in pct of .evcc-map-layers like the zone draft. */
  .evcc-hide-draft {
    position:       absolute;
    box-sizing:     border-box;
    border:         2px dashed var(--evcc-accent, #3b82f6);
    background:     rgba(120, 120, 130, 0.35);
    border-radius:  2px;
    pointer-events: none;
    z-index:        6;
  }
  /* Hide-area tools row in the Map Layers panel. */
  .evcc-map-hide-tools {
    display:    flex;
    gap:        6px;
    margin-top: 8px;
  }
  .evcc-map-hide-btn {
    flex:          1;
    padding:       5px 8px;
    font-size:     12px;
    border:        1px solid var(--evcc-border, #2d333b);
    border-radius: 6px;
    background:    var(--evcc-surface-raised, #232a31);
    color:         var(--evcc-text, #e6edf3);
    cursor:        pointer;
  }
  .evcc-map-hide-btn--on {
    background:   var(--evcc-accent, #3b82f6);
    color:        #fff;
    border-color: var(--evcc-accent, #3b82f6);
  }
  .evcc-map-hide-btn--clear { flex: 0 0 auto; }

  /* Floating action bar over the map while drawing. */
  .evcc-zone-bar {
    position:      absolute;
    left:          50%;
    bottom:        10px;
    transform:     translateX(-50%);
    display:       flex;
    align-items:   center;
    gap:           8px;
    padding:       6px 10px;
    border-radius: 8px;
    background:    var(--evcc-surface-panel, rgba(20, 24, 30, 0.92));
    border:        1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.15));
    box-shadow:    0 2px 10px rgba(0, 0, 0, 0.35);
    z-index:       5;
    max-width:     calc(100% - 20px);
  }
  .evcc-zone-bar-hint {
    font-size:   12px;
    color:       var(--evcc-map-tooltip-hint, rgba(255, 255, 255, 0.7));
    white-space: nowrap;
  }
  .evcc-zone-bar-btn {
    font-size:     12px;
    font-weight:   600;
    padding:       5px 10px;
    border-radius: 6px;
    cursor:        pointer;
    color:         var(--evcc-map-tooltip-text, #fff);
    background:    var(--evcc-surface-action, rgba(255, 255, 255, 0.08));
    border:        1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.15));
  }
  .evcc-zone-bar-btn:hover {
    background:    var(--evcc-surface-action-hover, rgba(255, 255, 255, 0.18));
  }
  .evcc-zone-bar-btn--primary {
    background:    var(--evcc-accent, #3b82f6);
    border-color:  var(--evcc-accent, #3b82f6);
    color:         #fff;
  }
  .evcc-zone-bar-btn[disabled] {
    opacity: 0.45;
    cursor:  default;
  }

  /* Zone-clean panel lives in the right column under Run Profiles. The side column
     stacks the Run Profiles panel + the zone panel; the run-profiles panel keeps its
     natural height there (its workspace flex would otherwise stretch it vertically). */
  .evcc-rooms-sidecol {
    flex:           1 1 300px;
    min-width:      0;
    display:        flex;
    flex-direction: column;
    gap:            16px;
  }
  .evcc-rooms-sidecol > .evcc-run-profiles-panel {
    flex: 0 0 auto;
  }
  .evcc-zone-panel {
    box-sizing:     border-box;
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        12px;
    border-radius:  var(--evcc-radius-card, 12px);
    background:     var(--evcc-surface-panel, rgba(28, 33, 39, 0.92));
    border:         1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.12));
  }
  .evcc-zone-panel-title {
    font-size:   13px;
    font-weight: 700;
    color:       var(--evcc-map-tooltip-text, #fff);
  }
  .evcc-zone-panel-section {
    display:        flex;
    flex-direction: column;
    gap:            6px;
  }
  .evcc-zone-panel-section-title {
    font-size:      11px;
    font-weight:    600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color:          var(--evcc-map-tooltip-hint, rgba(255, 255, 255, 0.7));
  }
  .evcc-zone-panel-note {
    font-weight:    400;
    text-transform: none;
    letter-spacing: 0;
    opacity:        0.7;
  }
  .evcc-zone-panel-empty {
    font-size: 12px;
    color:     var(--evcc-map-tooltip-hint, rgba(255, 255, 255, 0.6));
  }
  .evcc-zone-setting {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             8px;
  }
  .evcc-zone-setting-label {
    font-size: 12px;
    color:     var(--evcc-map-tooltip-text, #fff);
  }
  .evcc-zone-setting-select {
    flex:          0 1 auto;
    max-width:     60%;
    font-size:     12px;
    padding:       3px 6px;
    border-radius: 6px;
    color:         var(--evcc-map-tooltip-text, #fff);
    background:    var(--evcc-surface-action, rgba(255, 255, 255, 0.08));
    border:        1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.15));
  }
  .evcc-zone-list {
    list-style:     none;
    margin:         0;
    padding:        0;
    display:        flex;
    flex-direction: column;
    gap:            3px;
    max-height:     160px;
    overflow-y:     auto;
  }
  .evcc-zone-list-item {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             8px;
    font-size:       12px;
    color:           var(--evcc-map-tooltip-text, #fff);
  }
  .evcc-zone-list-num {
    display:         inline-flex;
    align-items:     center;
    justify-content: center;
    min-width:       18px;
    height:          18px;
    font-size:       10px;
    font-weight:     700;
    color:           #fff;
    background:      var(--evcc-accent, #3b82f6);
    border-radius:   4px;
  }
  .evcc-zone-list-del {
    font-size:     12px;
    line-height:   1;
    cursor:        pointer;
    color:         var(--evcc-map-tooltip-hint, rgba(255, 255, 255, 0.7));
    background:    transparent;
    border:        none;
    padding:       2px 5px;
    border-radius: 4px;
  }
  .evcc-zone-list-del:hover {
    color:      #fff;
    background: var(--evcc-surface-action-hover, rgba(255, 255, 255, 0.18));
  }
  .evcc-zone-panel-actions {
    display:    flex;
    flex-wrap:  wrap;
    gap:        6px;
    margin-top: auto;
  }

  /* =========================================================
     ANIMAL SVG COMPANION
     =========================================================
     Positioned absolutely in .evcc-map-layers (same space as
     the labels and old presence dot).  The inner <animal-svg>
     handles its own shadow DOM; we just control the host box.
     ========================================================= */

  .evcc-map-animal {
    position:       absolute;
    /* width + height set inline by renderer (respects user scale) */
    /* Counter-rotate by the map rotation so the sprite stays upright while its
       anchor still rides the rotated map (var inherited from the content rotator). */
    transform:      translate(-50%, -50%) rotate(calc(-1 * var(--evcc-map-rotation, 0deg)));
    cursor:         grab;
    z-index:        10;
    pointer-events: all;
    touch-action:   none;   /* prevent scroll takeover during drag on touch */
    /* Drop shadow so the animal reads on any map colour */
    filter: drop-shadow(0 2px 6px rgba(0,0,0,0.65));
    transition:     filter 400ms ease, opacity 400ms ease;
  }

  /* Actively being dragged */
  .evcc-map-animal--dragging {
    cursor:     grabbing;
    transition: none;   /* suppress filter transition while moving */
  }

  /* Docked / charging — gentle luminance + alpha breath pulse */
  .evcc-map-animal--pulse {
    animation: evcc-animal-pulse 3.5s ease-in-out infinite;
  }

  @keyframes evcc-animal-pulse {
    0%, 100% {
      filter: drop-shadow(0 2px 6px rgba(0,0,0,0.65))
              brightness(0.75) opacity(0.65);
    }
    45% {
      filter: drop-shadow(0 2px 8px rgba(0,0,0,0.55))
              brightness(1.05) opacity(1);
    }
  }

  /* =========================================================
     POLYGONS
     ========================================================= */

  .evcc-map-polygon {
    fill:           transparent;
    stroke:         none;
    cursor:         pointer;
    pointer-events: all;
    transition:     fill-opacity 150ms ease;
  }

  .evcc-map-polygon--selected {
    fill:         var(--seg-color);
    fill-opacity: 0.25;
  }

  /* =========================================================
     MAP LABELS (centroid overlays)
     ========================================================= */

  .evcc-map-label {
    position:       absolute;
    /* Counter-rotate so label text stays upright while its centroid rides the
       rotated map (var inherited from the content rotator). */
    transform:      translate(-50%, -50%) rotate(calc(-1 * var(--evcc-map-rotation, 0deg)));
    display:        flex;
    flex-direction: column;
    align-items:    center;
    gap:            3px;
    pointer-events: none;
    z-index:        5;
  }

  .evcc-map-label-name {
    font-size:     0.82rem;
    font-weight:   700;
    color:         var(--evcc-map-label-text, #ffffff);
    /* Subtle dark pill behind the text: nearly invisible on the dark CV map
       (dark-on-dark), but a consistent bed for white text on light / photo
       custom backdrops (e.g. a near-white sky over green foliage). Both the
       background (alpha is the legibility knob) and the text colour are theme
       tokens — tune them in the Theme editor's "Map" group. The tight casing
       keeps edges crisp over busy mid-tones. */
    background:    var(--evcc-map-label-bg, rgba(15, 18, 22, 0.60));
    padding:       1px 7px;
    border-radius: 7px;
    text-shadow:   0 0 2px rgba(0, 0, 0, 0.85);
    white-space:   nowrap;
    line-height:   1.25;
    text-align:    center;
  }

  .evcc-map-label--selected .evcc-map-label-name {
    color: var(--evcc-map-label-text-selected, #ffffff);
  }

  .evcc-map-label-order {
    display:         flex;
    align-items:     center;
    justify-content: center;
    width:           16px;
    height:          16px;
    border-radius:   50%;
    background:      var(--evcc-accent, #3b82f6);
    color:           var(--evcc-map-label-order-text, #fff);
    font-size:       0.58rem;
    font-weight:     700;
    line-height:     1;
    box-shadow:      0 1px 4px rgba(0, 0, 0, 0.55);
  }

  /* =========================================================
     MAP_STATE_SOURCE DEVICE OVERLAYS (Wave 3c)
     ========================================================= */

  /* SVG layers — non-scaling-stroke keeps lines crisp under the 0–100 viewBox. */
  .evcc-map-ov-current {
    fill:          var(--evcc-map-ov-current, rgba(0, 229, 255, 0.85));
    fill-opacity:  0.18;
    stroke:        var(--evcc-map-ov-current, rgba(0, 229, 255, 0.85));
    stroke-width:  2;
    vector-effect: non-scaling-stroke;
    pointer-events: none;
  }
  .evcc-map-ov-nogo, .evcc-map-ov-nomop, .evcc-map-ov-zone {
    fill-opacity:  0.18;
    stroke-width:  1.5;
    vector-effect: non-scaling-stroke;
    pointer-events: none;
  }
  .evcc-map-ov-nogo {
    fill:   var(--evcc-map-ov-nogo, rgba(255, 59, 48, 0.85));
    stroke: var(--evcc-map-ov-nogo, rgba(255, 59, 48, 0.85));
  }
  .evcc-map-ov-nomop {
    fill:   var(--evcc-map-ov-nomop, rgba(10, 132, 255, 0.85));
    stroke: var(--evcc-map-ov-nomop, rgba(10, 132, 255, 0.85));
  }
  .evcc-map-ov-zone {
    fill:             var(--evcc-map-ov-zone, rgba(52, 211, 153, 0.85));
    stroke:           var(--evcc-map-ov-zone, rgba(52, 211, 153, 0.85));
    stroke-dasharray: 4 2;
  }
  .evcc-map-ov-wall {
    stroke:         var(--evcc-map-ov-wall, rgba(255, 214, 10, 0.9));
    stroke-width:   3;
    stroke-linecap: round;
    vector-effect:  non-scaling-stroke;
    pointer-events: none;
  }
  .evcc-map-ov-path {
    fill:            none;
    stroke:          var(--evcc-map-ov-path, rgba(255, 255, 255, 0.8));
    stroke-width:    1.5;
    stroke-linejoin: round;
    stroke-linecap:  round;
    opacity:         0.8;
    vector-effect:   non-scaling-stroke;
    pointer-events:  none;
  }

  /* HTML markers — absolutely positioned in the rotator (turn with the map). */
  .evcc-map-ov-robot, .evcc-map-ov-dock, .evcc-map-ov-obstacle {
    position:       absolute;
    transform:      translate(-50%, -50%);
    pointer-events: none;
    z-index:        6;
  }
  .evcc-map-ov-dock {
    width:         10px;
    height:        10px;
    border-radius: 3px;
    background:    var(--evcc-map-ov-dock, #a3e635);
    box-shadow:    0 0 0 2px rgba(0, 0, 0, 0.5);
  }
  .evcc-map-ov-robot {
    width:         14px;
    height:        14px;
    border-radius: 50%;
    background:    var(--evcc-map-ov-robot, #00e5ff);
    box-shadow:    0 0 0 2px rgba(0, 0, 0, 0.5);
  }
  /* Heading triangle: points up at heading 0; the inline transform rotates it. */
  .evcc-map-ov-robot-arrow {
    display:           block;
    width:             0;
    height:            0;
    margin:            -9px 0 0 -6px;
    border-left:       6px solid transparent;
    border-right:      6px solid transparent;
    border-bottom:     12px solid var(--evcc-map-ov-robot, #00e5ff);
    transform-origin:  50% 100%;
    filter:            drop-shadow(0 0 2px rgba(0, 0, 0, 0.8));
  }
  .evcc-map-ov-obstacle {
    width:         8px;
    height:        8px;
    border-radius: 50%;
    background:    var(--evcc-map-ov-obstacle, rgba(251, 191, 36, 0.95));
    box-shadow:    0 0 0 1.5px rgba(0, 0, 0, 0.6);
  }
  .evcc-map-ov-obstacle--photo {
    box-shadow: 0 0 0 1.5px #fff, 0 0 5px var(--evcc-map-ov-obstacle, rgba(251, 191, 36, 0.95));
  }
  /* Area chips counter-rotate (like room labels) so the text stays upright. */
  .evcc-map-ov-area {
    position:      absolute;
    transform:     translate(-50%, -50%) rotate(calc(-1 * var(--evcc-map-rotation, 0deg)));
    font-size:     0.66rem;
    font-weight:   600;
    color:         var(--evcc-map-ov-area-text, #ffffff);
    background:    var(--evcc-map-label-bg, rgba(15, 18, 22, 0.60));
    padding:       0 5px;
    border-radius: 6px;
    text-shadow:   0 0 2px rgba(0, 0, 0, 0.85);
    white-space:   nowrap;
    pointer-events: none;
    z-index:       5;
  }

  /* =========================================================
     MAP LAYERS PANEL (Wave 3c overlay visibility toggles)
     ========================================================= */

  .evcc-map-layers-panel {
    flex:           0 0 auto;
    box-sizing:     border-box;
    display:        flex;
    flex-direction: column;
    gap:            8px;
    padding:        12px;
    border-radius:  var(--evcc-radius-card, 12px);
    background:     var(--evcc-surface-panel, rgba(28, 33, 39, 0.92));
    border:         1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.12));
  }
  .evcc-map-layers-title {
    font-size:   13px;
    font-weight: 700;
    color:       var(--evcc-map-tooltip-text, #fff);
  }
  .evcc-map-layers-hint {
    font-size: 11px;
    color:     var(--evcc-map-tooltip-hint, rgba(255, 255, 255, 0.6));
  }
  .evcc-map-layers-list {
    display:        flex;
    flex-direction: column;
    gap:            6px;
  }
  .evcc-map-layers-row {
    display:     flex;
    align-items: center;
    gap:         8px;
    font-size:   12.5px;
    color:       var(--evcc-map-tooltip-text, #fff);
    cursor:      pointer;
  }
  .evcc-map-layers-row input { cursor: pointer; margin: 0; }

  /* =========================================================
     MAP TOOLTIP
     ========================================================= */

  .evcc-map-tooltip {
    position:       absolute;
    display:        none;
    flex-direction: column;
    gap:            2px;
    padding:        6px 10px;
    background:     var(--evcc-map-tooltip-bg, rgba(15, 18, 22, 0.88));
    backdrop-filter: blur(6px);
    border:         1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.12));
    border-radius:  8px;
    pointer-events: none;
    max-width:      180px;
    z-index:        10;
  }

  .evcc-map-tooltip--visible {
    display: flex;
  }

  .evcc-map-tooltip-label {
    font-size:   0.82rem;
    font-weight: 600;
    color:       var(--evcc-map-tooltip-text, #f0f2f5);
    white-space: nowrap;
  }

  .evcc-map-tooltip-hint {
    font-size: 0.72rem;
    color:     var(--evcc-map-tooltip-hint, rgba(240, 242, 245, 0.55));
    white-space: nowrap;
  }

  /* =========================================================
     UNAVAILABLE STATE
     ========================================================= */

  .evcc-map-unavailable {
    display:         flex;
    flex-direction:  column;
    align-items:     center;
    justify-content: center;
    gap:             8px;
    padding:         32px 20px;
    color:
      var(--evcc-text-secondary,
      rgba(240, 242, 245, 0.72));
    font-size:       0.88rem;
    text-align:      center;
  }

  .evcc-map-unavailable-hint {
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    font-size: 0.80rem;
  }

  /* =========================================================
     SELECTION BAR
     ========================================================= */

  .evcc-map-selection-bar {
    display:     flex;
    flex-wrap:   wrap;
    gap:         8px;
    padding:     10px 12px;
    background:  var(--evcc-surface-panel, #1c2127);
    border-top:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.08));
    flex-shrink: 0;
  }

  .evcc-map-chip {
    display:        flex;
    flex-direction: row;
    align-items:    center;
    gap:            8px;
    padding:        6px 12px;
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    border-radius: 8px;
    cursor:        pointer;
    user-select:   none;
    min-width:     68px;
    transition:    background 150ms ease, border-color 150ms ease;
    touch-action:  none;
  }

  .evcc-map-chip:hover {
    background:
      var(--evcc-surface-panel, #1c2127);
    border-color:
      var(--evcc-border-strong,
      rgba(255, 255, 255, 0.18));
  }

  .evcc-map-chip-order {
    display:         flex;
    align-items:     center;
    justify-content: center;
    width:           18px;
    height:          18px;
    border-radius:   50%;
    background:      var(--evcc-accent, #3b82f6);
    color:           var(--evcc-map-label-order-text, #fff);
    font-size:       0.68rem;
    font-weight:     700;
    flex-shrink:     0;
    line-height:     1;
  }

  .evcc-map-chip-body {
    display:        flex;
    flex-direction: column;
    gap:            2px;
    min-width:      0;
  }

  .evcc-map-chip-label {
    font-size:     0.82rem;
    font-weight:   600;
    color:         var(--evcc-text-primary, #f0f2f5);
    white-space:   nowrap;
    overflow:      hidden;
    text-overflow: ellipsis;
  }

  .evcc-map-chip-settings {
    font-size:   0.74rem;
    color:       var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    white-space: nowrap;
  }

  /* =========================================================
     MAP CONFIG VIEW
     ========================================================= */

  .evcc-map-config-view {
    display:        flex;
    flex-direction: column;
    flex:           1;
    min-height:     0;
    gap:            0;
  }

  .evcc-map-config-body {
    display:    flex;
    flex:       1;
    min-height: 0;
  }

  .evcc-map-config-side-panel {
    display:        flex;
    flex-direction: column;
    width:          220px;
    flex-shrink:    0;
    overflow-y:     auto;
    border-left:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.08));
  }

  .evcc-map-config-header {
    display:         flex;
    align-items:     center;
    gap:             12px;
    padding:         10px 12px 8px;
    flex-shrink:     0;
    border-bottom:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.08));
  }

  .evcc-map-config-back {
    display:      flex;
    align-items:  center;
    gap:          6px;
    padding:      4px 10px 4px 6px;
    border-radius: 8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:   transparent;
    color:        var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:    0.82rem;
    cursor:       pointer;
    transition:   background 150ms ease, color 150ms ease;
  }

  .evcc-map-config-back:hover {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-map-config-title {
    font-size:   0.88rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-map-polygon--config {
    cursor:         pointer;
    pointer-events: all;
    transition:     filter 120ms ease;
  }

  .evcc-map-polygon--config:hover {
    filter: brightness(1.35);
  }

  .evcc-map-vertex-dot {
    transition: r 120ms ease, filter 120ms ease;
  }

  .evcc-map-vertex-dot:hover {
    filter: brightness(1.4);
  }

  .evcc-map-vertex-dot--selected {
    filter: drop-shadow(0 0 1px var(--evcc-map-vertex-selected-glow, rgba(255, 221, 0, 0.9)));
  }

  /* =========================================================
     CONFIG PANEL
     ========================================================= */

  .evcc-map-config-panel {
    display:        flex;
    flex-direction: column;
    gap:            0;
    flex-shrink:    0;
    border-top:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.08));
  }

  .evcc-map-config-section {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        14px 12px;
    border-bottom:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.06));
  }

  .evcc-map-config-section--hint {
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    font-size: 0.82rem;
    align-items: center;
    padding: 12px;
  }

  .evcc-map-config-section-title {
    font-size:      0.72rem;
    font-weight:    600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color:          var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  .evcc-map-config-section-title em {
    font-style:     normal;
    font-weight:    700;
    color:          var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    text-transform: none;
    letter-spacing: normal;
  }

  /* CV / Custom layout picker (segmented control; wraps with many layouts) */
  .evcc-map-mode-toggle {
    display:   flex;
    flex-wrap: wrap;
    gap:       6px;
  }

  /* "Auto (CV) unavailable" note — shown when the optional science stack
     (numpy/Pillow/scipy) is missing, so Auto (CV) is hidden. */
  .evcc-map-cv-unavailable {
    margin-top:    8px;
    padding:       8px 10px;
    border-radius: 8px;
    border:        1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    background:    var(--evcc-surface-raised, rgba(255, 255, 255, 0.04));
    color:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:     0.8rem;
    line-height:   1.4;
  }
  .evcc-map-cv-unavailable a {
    color: var(--evcc-accent, #3b9eff);
  }

  /* Layout-name input (create / rename a custom layout) */
  .evcc-map-config-input {
    flex:          1 1 8rem;
    min-width:     0;
    padding:       5px 9px;
    border-radius: 7px;
    border:        1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.14));
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    color:         var(--evcc-text-primary, #eef1f5);
    font-size:     0.82rem;
  }

  .evcc-map-mode-btn {
    flex:          1;
    padding:       7px 10px;
    border-radius: 8px;
    border:        1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    background:    var(--evcc-surface-raised, rgba(255, 255, 255, 0.04));
    color:        var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:     0.82rem;
    font-weight:   600;
    cursor:        pointer;
    transition:    background 0.15s, border-color 0.15s, color 0.15s;
  }

  .evcc-map-mode-btn:hover {
    border-color: var(--evcc-accent, #00e5ff);
  }

  .evcc-map-mode-btn--active {
    background:   var(--evcc-accent-soft, rgba(0, 229, 255, 0.14));
    border-color: var(--evcc-accent, #00e5ff);
    color:        var(--evcc-text-primary, #f0f2f5);
  }

  /* Custom-segment composer */
  .evcc-compose-tools {
    display: flex;
    gap:     6px;
  }

  .evcc-compose-shape {
    /* Stroke uses --evcc-grp (injected only on merged groups) so shapes that
       share a room share an outline colour; un-merged shapes keep the accent. */
    fill:           var(--evcc-accent-soft, rgba(0, 229, 255, 0.16));
    stroke:         var(--evcc-grp, var(--evcc-accent, #00e5ff));
    stroke-width:   0.5;
    cursor:         pointer;
    pointer-events: all;
  }

  .evcc-compose-shape--selected {
    fill:          var(--evcc-accent-soft, rgba(0, 229, 255, 0.30));
    stroke:        var(--evcc-map-compose-selected-stroke, #ffffff);
    stroke-width:  3;
    vector-effect: non-scaling-stroke;
  }

  /* Black halo drawn under .evcc-compose-shape--selected (emitted as a sibling in
     map.js renderer). 5px non-scaling under the 3px selection stroke leaves 1px of
     black on each side, so the bright outline survives a light custom-photo backdrop
     (black reads on light) while the bright core still reads on a dark CV map. */
  .evcc-compose-shape-halo {
    fill:           none;
    stroke:         #000;
    stroke-width:   5;
    vector-effect:  non-scaling-stroke;
    pointer-events: none;
  }

  /* Cutout: this shape carves a hole out of its merged room. Dashed + a warning
     tint so it reads as "subtracted" rather than filled. */
  .evcc-compose-shape--cut {
    fill:             var(--evcc-map-compose-cut-fill, rgba(255, 92, 92, 0.12));
    stroke-dasharray: 2 1.4;
  }
  .evcc-compose-shape--cut.evcc-compose-shape--selected {
    fill: var(--evcc-map-compose-cut-selected-fill, rgba(255, 92, 92, 0.20));
  }

  /* Custom backdrop fills the square exactly like the 0-100 draw grid, so a
     traced shape lines up with the picture (CV maps stay object-fit: contain). */
  .evcc-map-image--fill {
    object-fit: fill;
  }

  /* =========================================================
     VARIANT ROWS
     ========================================================= */

  .evcc-map-variant-row {
    display:     flex;
    align-items: center;
    gap:         8px;
  }

  .evcc-map-variant-info {
    display:        flex;
    flex-direction: column;
    gap:            1px;
    flex:           1;
    min-width:      0;
  }

  .evcc-map-variant-label {
    font-size:  0.82rem;
    font-weight: 600;
    color:      var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-map-variant-hint {
    font-size: 0.72rem;
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    overflow:      hidden;
    text-overflow: ellipsis;
    white-space:   nowrap;
  }

  .evcc-map-variant-status {
    font-size:   0.74rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .evcc-map-variant-status--ok {
    color: var(--evcc-sem-success, #22c55e);
  }

  .evcc-map-variant-status--missing {
    color: var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  .evcc-map-config-analyze-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             8px;
    padding-top:     4px;
  }

  .evcc-map-config-seg-count {
    font-size: 0.80rem;
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  .evcc-map-config-btn {
    padding:       5px 12px;
    border-radius: 8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:    transparent;
    color:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:     0.80rem;
    cursor:        pointer;
    white-space:   nowrap;
    flex-shrink:   0;
    transition:    background 150ms ease, color 150ms ease;
  }

  .evcc-map-config-btn:hover {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-map-config-btn--primary {
    background:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 18%, transparent);
    color:
      var(--evcc-accent, #3b82f6);
    border-color:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 40%, transparent);
    font-weight: 600;
  }

  .evcc-map-config-btn--primary:hover {
    background:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 28%, transparent);
    color: var(--evcc-accent, #3b82f6);
  }

  .evcc-map-config-btn:disabled,
  .evcc-map-config-btn--busy {
    opacity: 0.55;
    cursor:  default;
  }

  /* Per-variant delete button — flatter, error-tinted treatment to
     keep the primary Upload button as the visual anchor of the row. */
  .evcc-map-config-btn--danger {
    background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
    color:      var(--evcc-sem-error, #ef4444);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 36%, transparent);
  }

  .evcc-map-config-btn--danger:hover {
    background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 22%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 56%, transparent);
  }

  /* Armed (second-click) state for the per-variant delete button.
     Solid error fill + pulse so the user can't mistake it for a
     primary action chip. Auto-clears after 5s (see bindings/map.js). */
  .evcc-map-config-btn--confirm {
    background:   var(--evcc-sem-error, #ef4444);
    color:        var(--evcc-text-on-accent, #fff);
    border-color: var(--evcc-sem-error, #ef4444);
    font-weight:  700;
    animation:    evcc-variant-delete-pulse 1.1s ease-in-out infinite;
  }

  @keyframes evcc-variant-delete-pulse {
    0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--evcc-sem-error, #ef4444) 55%, transparent); }
    50%      { box-shadow: 0 0 0 6px color-mix(in srgb, var(--evcc-sem-error, #ef4444) 0%, transparent); }
  }

  .evcc-map-action-status {
    font-size:   0.74rem;
    font-weight: 500;
    flex-shrink: 0;
  }

  .evcc-map-action-status--error {
    color: var(--evcc-sem-error, #ef4444);
  }

  /* =========================================================
     NUDGE PAD
     ========================================================= */

  .evcc-map-nudge-pad {
    display:        flex;
    flex-direction: column;
    align-items:    center;
    gap:            4px;
    align-self:     flex-start;
  }

  .evcc-map-nudge-row {
    display: flex;
    gap:     4px;
  }

  .evcc-map-nudge-btn {
    width:         36px;
    height:        36px;
    display:       flex;
    align-items:   center;
    justify-content: center;
    border-radius: 8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:    transparent;
    color:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:     1rem;
    cursor:        pointer;
    transition:    background 120ms ease;
  }

  .evcc-map-nudge-btn:hover {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.08));
  }

  .evcc-map-nudge-btn:active {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.14));
  }

  .evcc-map-nudge-btn--reset {
    color:        var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    border-color: transparent;
    font-size:    0.9rem;
  }

  .evcc-map-config-adj-meta {
    font-size: 0.74rem;
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  /* =========================================================
     EDGE ADJUST
     ========================================================= */

  .evcc-map-edge-grid {
    display:        flex;
    flex-direction: column;
    gap:            4px;
  }

  .evcc-map-edge-row {
    display:     flex;
    align-items: center;
    gap:         4px;
  }

  .evcc-map-edge-label {
    font-size:  0.72rem;
    color:      var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    width:      44px;
    flex-shrink: 0;
  }

  .evcc-map-edge-val {
    font-size:   0.72rem;
    color:       var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    min-width:   28px;
    text-align:  center;
    flex-shrink: 0;
  }

  .evcc-map-nudge-btn--edge {
    width:     28px;
    height:    28px;
    font-size: 1rem;
    flex-shrink: 0;
  }

  /* =========================================================
     VERTEX ADJUST
     ========================================================= */

  .evcc-map-vertex-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       4px;
  }

  .evcc-map-vertex-chip {
    min-width:     24px;
    height:        24px;
    padding:       0 6px;
    border-radius: 6px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:    transparent;
    color:         var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    font-size:     0.70rem;
    cursor:        pointer;
    transition:    background 120ms ease, color 120ms ease, border-color 120ms ease;
  }

  .evcc-map-vertex-chip:hover {
    background:
      var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    color: var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
  }

  .evcc-map-vertex-chip--selected {
    background:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 20%, transparent);
    color:        var(--evcc-accent, #3b82f6);
    border-color:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 45%, transparent);
    font-weight:  600;
  }

  .evcc-map-vertex-chip--adjusted {
    border-color:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 40%, transparent);
  }

  .evcc-map-vertex-chip--selected.evcc-map-vertex-chip--adjusted {
    background:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 20%, transparent);
    color:        var(--evcc-sem-success, #22c55e);
    border-color:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 45%, transparent);
  }

  /* =========================================================
     ROOM ASSIGNMENT CHIPS
     ========================================================= */

  .evcc-map-room-assign-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       6px;
  }

  .evcc-map-room-assign-chip {
    padding:       5px 12px;
    border-radius: 8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:    transparent;
    color:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:     0.80rem;
    cursor:        pointer;
    transition:    background 120ms ease, color 120ms ease, border-color 120ms ease;
  }

  .evcc-map-room-assign-chip:hover:not(:disabled) {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color:        var(--evcc-text-primary, #f0f2f5);
    border-color:
      var(--evcc-border-strong,
      rgba(255, 255, 255, 0.18));
  }

  .evcc-map-room-assign-chip--linked {
    background:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 16%, transparent);
    color:        var(--evcc-sem-success, #22c55e);
    border-color:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 38%, transparent);
    font-weight:  600;
  }

  .evcc-map-room-assign-chip--taken {
    opacity: 0.35;
    cursor:  default;
  }

  /* =========================================================
     CONFIGURE BUTTON IN INLINE MAP VIEW
     ========================================================= */

  .evcc-rooms-view-toggle-btn--configure {
    width:  auto;
    padding: 0 10px;
    gap:    6px;
    font-size: 0.76rem;
  }

  /* =========================================================
     ANIMAL SELECTOR IN MAP TOOLBAR
     ========================================================= */

  .evcc-rooms-animal-select {
    height:        32px;
    padding:       0 6px;
    border-radius: 8px;
    border:        1px solid var(--evcc-border-default, rgba(255,255,255,0.10));
    background:    transparent;
    color:         var(--evcc-text-secondary, rgba(240,242,245,0.72));
    font-size:     0.76rem;
    cursor:        pointer;
    outline:       none;
    flex-shrink:   0;
    /* Native <select> appearance for simplicity — themed via border/bg */
    -webkit-appearance: auto;
    appearance:    auto;
  }

  .evcc-rooms-animal-select:hover {
    border-color: var(--evcc-border-strong, rgba(255,255,255,0.18));
    color:        var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-rooms-animal-select option {
    background: var(--evcc-surface-panel, #1c2127);
    color:      var(--evcc-text-primary, #f0f2f5);
  }

  /* =========================================================
     ANIMAL SCALE SLIDER
     ========================================================= */

  .evcc-rooms-animal-scale {
    width:       72px;
    height:      32px;
    flex-shrink: 0;
    cursor:      pointer;
    accent-color: var(--evcc-accent, #6366f1);
    /* keep the range input vertically centred in the toolbar row */
    align-self:  center;
  }
`;
