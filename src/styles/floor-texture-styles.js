/**
 * ============================================================
 * STYLES: FLOOR TEXTURES
 * ============================================================
 *
 * PURPOSE
 * -------
 * CSS for floor texture overlays on room cards and the SVG
 * map view.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Card layer: absolute-positioned div inside .evcc-room-card
 * (which is already position:relative; overflow:hidden).
 *
 * The container div (.evcc-room-texture-layer) is a transparent
 * wrapper — it carries no background color so the card's own
 * surface color shows through.
 *
 * Each child span (.evcc-ftx-layer) represents one texture
 * mask.  background-color sets the layer tint; mask-image +
 * mask-mode:luminance makes white areas of the 512 px PNG
 * reveal that color and black areas fully transparent.  Layers
 * stack via CSS absolute positioning.
 *
 * Span opacity gates on both the global enabled token and the
 * per-layer weight set inline via --layer-opacity.  When
 * disabled (enabled=0) all spans collapse to opacity:0 and the
 * card shows its normal surface color.
 *
 * Map layer: <polygon> elements overlaid on the SVG map, filled
 * with a <pattern> containing the primary texture image.
 *
 * ============================================================
 */

export const floorTextureStyles = `

  /* =========================================================
     CARD TEXTURE CONTAINER
     ========================================================= */

  .evcc-room-texture-layer {
    position:       absolute;
    inset:          0;
    pointer-events: none;
    z-index:        0;
  }

  /* Higher-specificity override: rooms.js sets
     .evcc-room-card > * { position:relative; z-index:1 }
     which would lift the texture layer above z-index:0.
     Re-declare here so the texture stays behind content. */
  .evcc-room-card > .evcc-room-texture-layer {
    position: absolute;
    z-index:  0;
    inset:    0;
  }

  /* =========================================================
     MASK LAYER SPANS
     ========================================================= */

  .evcc-ftx-layer {
    display:                block;
    position:               absolute;
    inset:                  0;
    mask-repeat:            no-repeat;
    mask-size:              cover;
    mask-position:          var(--floor-position-card, center);
    mask-mode:              luminance;
    -webkit-mask-repeat:    no-repeat;
    -webkit-mask-size:      cover;
    -webkit-mask-position:  var(--floor-position-card, center);
    -webkit-mask-mode:      luminance;
    opacity: calc(
      var(--evcc-floor-textures-card-enabled, 1) *
      var(--floor-opacity-card, 0.85) *
      var(--layer-opacity, 1)
    );
  }

  /* =========================================================
     MAP TEXTURE OVERLAY POLYGON
     ========================================================= */

  .evcc-map-texture-polygon {
    pointer-events: none;
    opacity: calc(
      var(--evcc-floor-texture-opacity-map,  0.15) *
      var(--evcc-floor-textures-map-enabled, 1)
    );
  }
`;
