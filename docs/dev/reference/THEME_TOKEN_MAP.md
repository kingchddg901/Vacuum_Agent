<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Source of truth: src/theme-tokens/ (the editor registry) + the card CSS.
     Regenerate after any token add/remove/rename:  node scripts/gen-theme-token-docs.mjs -->

# Theme Token Map

> Generated reference — part of the [Theme System](../20-theme-system.md) docs. Companion: [Theme Token CSS-Usage Trace](THEME_TOKEN_USAGE.md).

The themeable control-surface tokens exposed in the theme editor: **399 tokens** across **25 groups**. Each is a `--evcc-*` CSS custom property; **Controls** is the editor label (what it styles); **Type** is the input kind; bounded scalars list their slider range.

The 5 companion sub-groups share one identical 14-token shape — only **Cat** is listed in full; Dog, Raccoon, Parrot, Snake repeat it with their own `-<animal>-` key segment.

---

## App Shell & Typography  ·  7

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-accent` | Accent | color |  |
| `--evcc-accent-soft` | Accent Soft | color |  |
| `--evcc-text-muted` | Text Muted | color |  |
| `--evcc-text-on-accent` | Text On Accent | color |  |
| `--evcc-text-primary` | Text Primary | color |  |
| `--evcc-text-secondary` | Text Secondary | color |  |
| `--evcc-text-strong` | Text Strong | color |  |

## Cards & Surfaces  ·  18

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-bg-input` | BG Input | color |  |
| `--evcc-card-bg` | Card BG | color |  |
| `--evcc-card-gap` | Card Gap | size |  |
| `--evcc-card-min-height` | Card Min Height | size |  |
| `--evcc-card-padding` | Card Padding | size |  |
| `--evcc-panel-bg` | Panel BG | color |  |
| `--evcc-surface-action` | Surface Action | color |  |
| `--evcc-surface-action-hover` | Surface Action Hover | color |  |
| `--evcc-surface-base` | Surface Base | color |  |
| `--evcc-surface-card` | Surface Card | color |  |
| `--evcc-surface-chip` | Surface Chip | color |  |
| `--evcc-surface-input` | Surface Input | color |  |
| `--evcc-surface-overlay` | Surface Overlay | color |  |
| `--evcc-surface-panel` | Surface Panel | color |  |
| `--evcc-surface-raised` | Surface Raised | color |  |
| `--evcc-surface-subtle` | Surface Subtle | color |  |
| `--evcc-surface-sunken` | Surface Sunken | color |  |
| `--evcc-surface-warning` | Surface Warning | color |  |

## Borders & Shadows  ·  6

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-border-default` | Border Default | color |  |
| `--evcc-border-strong` | Border Strong | color |  |
| `--evcc-border-subtle` | Border Subtle | color |  |
| `--evcc-border-warning` | Border Warning | color |  |
| `--evcc-shadow-card` | Shadow Card | shadow |  |
| `--evcc-shadow-hover` | Shadow Hover | shadow |  |

## Chips  ·  31

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-chip-active-bg` | Chip Active BG | color |  |
| `--evcc-chip-active-border` | Chip Active Border | color |  |
| `--evcc-chip-active-text` | Chip Active Text | color |  |
| `--evcc-chip-bg` | Chip BG | color |  |
| `--evcc-chip-border` | Chip Border | color |  |
| `--evcc-chip-excluded-bg` | Chip Excluded BG | color |  |
| `--evcc-chip-excluded-border` | Chip Excluded Border | color |  |
| `--evcc-chip-excluded-text` | Chip Excluded Text | color |  |
| `--evcc-chip-font-size` | Chip Font Size | size |  |
| `--evcc-chip-font-weight` | Chip Font Weight | typography |  |
| `--evcc-chip-gap` | Chip Gap | size |  |
| `--evcc-chip-height` | Chip Height | size |  |
| `--evcc-chip-hover-bg` | Chip Hover BG | color |  |
| `--evcc-chip-hover-border` | Chip Hover Border | color |  |
| `--evcc-chip-hover-text` | Chip Hover Text | color |  |
| `--evcc-chip-icon-height` | Chip Icon Height | size |  |
| `--evcc-chip-icon-padding` | Chip Icon Padding | size |  |
| `--evcc-chip-icon-size` | Chip Icon Size | size |  |
| `--evcc-chip-included-bg` | Chip Included BG | color |  |
| `--evcc-chip-included-border` | Chip Included Border | color |  |
| `--evcc-chip-included-text` | Chip Included Text | color |  |
| `--evcc-chip-neutral-bg` | Chip Neutral BG | color |  |
| `--evcc-chip-padding` | Chip Padding | size |  |
| `--evcc-chip-radius` | Chip Radius | size |  |
| `--evcc-chip-success-bg` | Chip Success BG | color |  |
| `--evcc-chip-success-border` | Chip Success Border | color |  |
| `--evcc-chip-success-text` | Chip Success Text | color |  |
| `--evcc-chip-text` | Chip Text | color |  |
| `--evcc-chip-warning-bg` | Chip Warning BG | color |  |
| `--evcc-chip-warning-border` | Chip Warning Border | color |  |
| `--evcc-chip-warning-text` | Chip Warning Text | color |  |

## Room Cards  ·  13

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-profile-chip-bg` | Profile Chip BG | color |  |
| `--evcc-profile-chip-border` | Profile Chip Border | color |  |
| `--evcc-profile-chip-custom-bg` | Profile Chip Custom BG | color |  |
| `--evcc-profile-chip-custom-border` | Profile Chip Custom Border | color |  |
| `--evcc-profile-chip-custom-text` | Profile Chip Custom Text | color |  |
| `--evcc-profile-chip-text` | Profile Chip Text | color |  |
| `--evcc-room-chip-bg` | Room Chip BG | color |  |
| `--evcc-room-chip-border` | Room Chip Border | color |  |
| `--evcc-room-chip-text` | Room Chip Text | color |  |
| `--evcc-room-fill-opacity` | Room Card Opacity | number |  |
| `--evcc-room-grid-columns` | Room Grid Columns | size |  |
| `--evcc-room-grid-gap` | Room Grid Gap | size |  |
| `--evcc-room-grid-min` | Room Grid Min | size |  |

## Map  ·  34

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-map-label-bg` | Map Label Background | color |  |
| `--evcc-map-label-text` | Map Label Text | color |  |
| `--evcc-map-label-text-selected` | Map Label Text (Selected) | color |  |
| `--evcc-map-label-order-text` | Map Order Badge Text | color |  |
| `--evcc-map-tooltip-bg` | Map Tooltip Background | color |  |
| `--evcc-map-tooltip-border` | Map Tooltip Border | color |  |
| `--evcc-map-tooltip-text` | Map Tooltip Text | color |  |
| `--evcc-map-tooltip-hint` | Map Tooltip Hint Text | color |  |
| `--evcc-map-compose-selected-stroke` | Composer Selected Outline | color |  |
| `--evcc-map-compose-cut-fill` | Composer Cutout Fill | color |  |
| `--evcc-map-compose-cut-selected-fill` | Composer Cutout Fill (Selected) | color |  |
| `--evcc-map-vertex-selected-glow` | Composer Selected Vertex Glow | color |  |
| `--evcc-map-ov-current` | Overlay: Current Room | color |  |
| `--evcc-map-ov-nogo` | Overlay: No-Go Zone | color |  |
| `--evcc-map-ov-nomop` | Overlay: No-Mop Zone | color |  |
| `--evcc-map-ov-wall` | Overlay: Virtual Wall | color |  |
| `--evcc-map-ov-zone` | Overlay: Saved Zone | color |  |
| `--evcc-map-ov-path` | Overlay: Cleaning Path | color |  |
| `--evcc-map-ov-robot` | Overlay: Robot Marker | color |  |
| `--evcc-map-ov-dock` | Overlay: Dock Marker | color |  |
| `--evcc-map-ov-obstacle` | Overlay: Obstacle Marker | color |  |
| `--evcc-map-ov-area-text` | Overlay: Area Label Text | color |  |
| `--evcc-room-fill-1` | Map Room Color 1 | color |  |
| `--evcc-room-fill-2` | Map Room Color 2 | color |  |
| `--evcc-room-fill-3` | Map Room Color 3 | color |  |
| `--evcc-room-fill-4` | Map Room Color 4 | color |  |
| `--evcc-room-fill-5` | Map Room Color 5 | color |  |
| `--evcc-room-fill-6` | Map Room Color 6 | color |  |
| `--evcc-room-fill-7` | Map Room Color 7 | color |  |
| `--evcc-room-fill-8` | Map Room Color 8 | color |  |
| `--evcc-room-fill-9` | Map Room Color 9 | color |  |
| `--evcc-room-fill-10` | Map Room Color 10 | color |  |
| `--evcc-room-fill-11` | Map Room Color 11 | color |  |
| `--evcc-room-fill-12` | Map Room Color 12 | color |  |

## Floor Textures  ·  4

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-floor-textures-card-enabled` | Card Textures Enabled (0/1) | number | 0–1 step 1 |
| `--evcc-floor-textures-map-enabled` | Map Textures Enabled (0/1) | number | 0–1 step 1 |
| `--evcc-floor-texture-opacity-card` | Card Texture Opacity (all) | number | 0–1 step 0.01 |
| `--evcc-floor-texture-opacity-map` | Map Texture Opacity (all) | number | 0–1 step 0.01 |

## Floor Textures — Tile  ·  7

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-floor-tile-base` | Tile Base Color | color |  |
| `--evcc-floor-tile-grout` | Tile Grout Color | color |  |
| `--evcc-floor-tile-accent` | Tile Grout Line Color | color |  |
| `--evcc-floor-tile-opacity-card` | Tile Card Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-tile-face-opacity` | Tile Base Layer Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-tile-grout-opacity` | Tile Grout Layer Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-tile-line-opacity` | Tile Grout Line Layer Opacity | number | 0–1 step 0.01 |

## Floor Textures — Wood  ·  6

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-floor-wood-base` | Wood Base Color | color |  |
| `--evcc-floor-wood-accent` | Wood Seam Color | color |  |
| `--evcc-floor-wood-opacity-card` | Wood Card Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-wood-depth-opacity` | Wood Depth Layer Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-wood-grain-opacity` | Wood Grain Layer Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-wood-seam-opacity` | Wood Seam Layer Opacity | number | 0–1 step 0.01 |

## Floor Textures — Marble  ·  15

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-floor-marble-base` | Marble Base Color | color |  |
| `--evcc-floor-marble-micro` | Marble Micro Color | color |  |
| `--evcc-floor-marble-accent` | Marble Vein Color | color |  |
| `--evcc-floor-marble-opacity-card` | Marble Card Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-marble-base-opacity` | Marble Base Layer Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-marble-micro-opacity` | Marble Micro Layer Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-marble-vein-opacity` | Marble Vein Opacity (master) | number | 0–1 step 0.01 |
| `--evcc-floor-marble-vein-blur` | Marble Vein Blur (master, px) | number | 0–8 step 0.5 |
| `--evcc-floor-marble-vein-major-opacity` | Marble Major Vein Opacity +/- | number | -1–1 step 0.01 |
| `--evcc-floor-marble-vein-minor-opacity` | Marble Minor Vein Opacity +/- | number | -1–1 step 0.01 |
| `--evcc-floor-marble-vein-major-blur` | Marble Major Vein Blur +/- (px) | number | -8–8 step 0.5 |
| `--evcc-floor-marble-vein-minor-blur` | Marble Minor Vein Blur +/- (px) | number | -8–8 step 0.5 |
| `--evcc-floor-marble-vein-minor-light` | Marble Minor Vein Lighten (L+) | number | -1–1 step 0.01 |
| `--evcc-floor-marble-vein-minor-chroma` | Marble Minor Vein Saturation (xC) | number | 0–2 step 0.01 |
| `--evcc-floor-marble-vein-minor-hue` | Marble Minor Vein Hue Shift (deg) | number | -180–180 step 1 |

## Floor Textures — Concrete  ·  5

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-floor-concrete-base` | Concrete Base Color | color |  |
| `--evcc-floor-concrete-accent` | Concrete Micro Color | color |  |
| `--evcc-floor-concrete-opacity-card` | Concrete Card Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-concrete-broad-opacity` | Concrete Base Layer Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-concrete-micro-opacity` | Concrete Micro Layer Opacity | number | 0–1 step 0.01 |

## Floor Textures — Carpet Low  ·  3

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-floor-carpet-low-base` | Carpet Low Base Color | color |  |
| `--evcc-floor-carpet-low-opacity-card` | Carpet Low Card Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-carpet-low-texture-opacity` | Carpet Low Texture Layer Opacity | number | 0–1 step 0.01 |

## Floor Textures — Carpet High  ·  3

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-floor-carpet-high-base` | Carpet High Base Color | color |  |
| `--evcc-floor-carpet-high-opacity-card` | Carpet High Card Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-carpet-high-texture-opacity` | Carpet High Texture Layer Opacity | number | 0–1 step 0.01 |

## Floor Textures — Granite  ·  3

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-floor-granite-light-base` | Granite Base Color | color |  |
| `--evcc-floor-granite-light-opacity-card` | Granite Card Opacity | number | 0–1 step 0.01 |
| `--evcc-floor-granite-light-texture-opacity` | Granite Texture Layer Opacity | number | 0–1 step 0.01 |

## Queue & Ordering  ·  41

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-drag-opacity` | Drag Opacity | number |  |
| `--evcc-drag-scale` | Drag Scale | number |  |
| `--evcc-drag-shadow` | Drag Shadow | shadow |  |
| `--evcc-order-chip-bg` | Order Chip BG | color |  |
| `--evcc-order-chip-border` | Order Chip Border | color |  |
| `--evcc-order-chip-text` | Order Chip Text | color |  |
| `--evcc-order-feedback-border` | Order Feedback Border | color |  |
| `--evcc-order-target-outline` | Order Target Outline | color |  |
| `--evcc-progress-complete` | Progress Complete | text |  |
| `--evcc-progress-fill` | Progress Fill | color |  |
| `--evcc-queue-chip-bg` | Queue Chip BG | color |  |
| `--evcc-queue-chip-border` | Queue Chip Border | color |  |
| `--evcc-queue-chip-gap` | Queue Chip Gap | size |  |
| `--evcc-queue-chip-text` | Queue Chip Text | color |  |
| `--evcc-queue-completed-bg` | Queue Completed BG | color |  |
| `--evcc-queue-completed-border` | Queue Completed Border | color |  |
| `--evcc-queue-completed-opacity` | Queue Completed Opacity | number |  |
| `--evcc-queue-completed-text` | Queue Completed Text | color |  |
| `--evcc-queue-current-bg` | Queue Current BG | color |  |
| `--evcc-queue-current-border` | Queue Current Border | color |  |
| `--evcc-queue-current-glow` | Queue Current Glow | shadow |  |
| `--evcc-queue-current-text` | Queue Current Text | color |  |
| `--evcc-queue-hover-bg` | Queue Hover BG | color |  |
| `--evcc-queue-hover-border` | Queue Hover Border | color |  |
| `--evcc-queue-hover-text` | Queue Hover Text | color |  |
| `--evcc-queue-inferred-bg` | Queue Inferred BG | color |  |
| `--evcc-queue-inferred-border` | Queue Inferred Border | color |  |
| `--evcc-queue-inferred-glow` | Queue Inferred Glow | shadow |  |
| `--evcc-queue-inferred-text` | Queue Inferred Text | color |  |
| `--evcc-queue-order-bg` | Queue Order BG | color |  |
| `--evcc-queue-order-border` | Queue Order Border | color |  |
| `--evcc-queue-order-text` | Queue Order Text | color |  |
| `--evcc-queue-pending-bg` | Queue Pending BG | color |  |
| `--evcc-queue-pending-border` | Queue Pending Border | color |  |
| `--evcc-queue-pending-opacity` | Queue Pending Opacity | number |  |
| `--evcc-queue-pending-text` | Queue Pending Text | color |  |
| `--evcc-queue-skipped-bg` | Queue Skipped BG | color |  |
| `--evcc-queue-skipped-border` | Queue Skipped Border | color |  |
| `--evcc-queue-skipped-text` | Queue Skipped Text | color |  |
| `--evcc-reorder-feedback-duration` | Reorder Feedback Duration | duration |  |
| `--evcc-reorder-flip-easing` | Reorder Flip Easing | easing |  |

## Status, Confidence & Alerts  ·  31

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-color-cleaning` | Color Cleaning | color |  |
| `--evcc-color-docked` | Color Docked | color |  |
| `--evcc-color-error` | Color Error | color |  |
| `--evcc-color-idle` | Color Idle | color |  |
| `--evcc-confidence-high-bg` | Confidence High BG | color |  |
| `--evcc-confidence-high-border` | Confidence High Border | color |  |
| `--evcc-confidence-high-text` | Confidence High Text | color |  |
| `--evcc-confidence-low-bg` | Confidence Low BG | color |  |
| `--evcc-confidence-low-border` | Confidence Low Border | color |  |
| `--evcc-confidence-low-text` | Confidence Low Text | color |  |
| `--evcc-confidence-medium-bg` | Confidence Medium BG | color |  |
| `--evcc-confidence-medium-border` | Confidence Medium Border | color |  |
| `--evcc-confidence-medium-text` | Confidence Medium Text | color |  |
| `--evcc-sem-error` | Sem Error | color |  |
| `--evcc-sem-info` | Sem Info | color |  |
| `--evcc-sem-success` | Sem Success | color |  |
| `--evcc-sem-warning` | Sem Warning | color |  |
| `--evcc-status-cleaning-bg` | Status Cleaning BG | color |  |
| `--evcc-status-cleaning-border` | Status Cleaning Border | color |  |
| `--evcc-status-cleaning-text` | Status Cleaning Text | color |  |
| `--evcc-status-dot-charging` | Status Dot Charging | color |  |
| `--evcc-status-dot-cleaning` | Status Dot Cleaning | color |  |
| `--evcc-status-dot-docked` | Status Dot Docked | color |  |
| `--evcc-status-dot-error` | Status Dot Error | color |  |
| `--evcc-status-dot-idle` | Status Dot Idle | color |  |
| `--evcc-status-dot-offline` | Status Dot Offline | color |  |
| `--evcc-status-dot-paused` | Status Dot Paused | color |  |
| `--evcc-status-dot-returning` | Status Dot Returning | color |  |
| `--evcc-status-dot-shadow` | Status Dot Shadow | shadow |  |
| `--evcc-status-dot-unavailable` | Status Dot Unavailable | color |  |
| `--evcc-status-pulse-duration` | Status Pulse Duration | duration |  |

## Learning & Metrics  ·  37

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-estimate-default-bg` | Estimate Default BG | color |  |
| `--evcc-estimate-default-border` | Estimate Default Border | color |  |
| `--evcc-estimate-default-text` | Estimate Default Text | color |  |
| `--evcc-estimate-learned-bg` | Estimate Learned BG | color |  |
| `--evcc-estimate-learned-border` | Estimate Learned Border | color |  |
| `--evcc-estimate-learned-text` | Estimate Learned Text | color |  |
| `--evcc-learning-anim-duration-fast` | Learning Anim Duration Fast | duration |  |
| `--evcc-learning-anim-duration-normal` | Learning Anim Duration Normal | duration |  |
| `--evcc-learning-anim-duration-slow` | Learning Anim Duration Slow | duration |  |
| `--evcc-learning-anim-ease` | Learning Anim Ease | text |  |
| `--evcc-learning-chip-font-size` | Learning Chip Font Size | size |  |
| `--evcc-learning-chip-font-weight` | Learning Chip Font Weight | typography |  |
| `--evcc-learning-chip-radius` | Learning Chip Radius | size |  |
| `--evcc-learning-confidence-high-bg` | Learning Confidence High BG | color |  |
| `--evcc-learning-confidence-high-border` | Learning Confidence High Border | color |  |
| `--evcc-learning-confidence-high-gradient` | Learning Confidence High Gradient | text |  |
| `--evcc-learning-confidence-high-text` | Learning Confidence High Text | color |  |
| `--evcc-learning-confidence-low-border` | Learning Confidence Low Border | color |  |
| `--evcc-learning-confidence-low-gradient` | Learning Confidence Low Gradient | text |  |
| `--evcc-learning-confidence-low-text` | Learning Confidence Low Text | color |  |
| `--evcc-learning-confidence-medium-bg` | Learning Confidence Medium BG | color |  |
| `--evcc-learning-confidence-medium-border` | Learning Confidence Medium Border | color |  |
| `--evcc-learning-confidence-medium-gradient` | Learning Confidence Medium Gradient | text |  |
| `--evcc-learning-confidence-medium-text` | Learning Confidence Medium Text | color |  |
| `--evcc-learning-confidence-neutral-border` | Learning Confidence Neutral Border | color |  |
| `--evcc-learning-confidence-neutral-gradient` | Learning Confidence Neutral Gradient | text |  |
| `--evcc-learning-confidence-neutral-text` | Learning Confidence Neutral Text | color |  |
| `--evcc-learning-note-text` | Learning Note Text | color |  |
| `--evcc-learning-panel-bg` | Learning Panel BG | color |  |
| `--evcc-learning-panel-border` | Learning Panel Border | color |  |
| `--evcc-learning-panel-shadow` | Learning Panel Shadow | shadow |  |
| `--evcc-learning-reanchor-border` | Learning Reanchor Border | color |  |
| `--evcc-learning-reanchor-highlight` | Learning Reanchor Highlight | color |  |
| `--evcc-learning-text-muted` | Learning Text Muted | color |  |
| `--evcc-learning-text-primary` | Learning Text Primary | color |  |
| `--evcc-learning-text-secondary` | Learning Text Secondary | color |  |
| `--evcc-learning-warning-text` | Learning Warning Text | color |  |

## Modals & Overlays  ·  36

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-modal-accent` | Modal Accent | color |  |
| `--evcc-modal-accent-bg` | Modal Accent BG | color |  |
| `--evcc-modal-accent-border` | Modal Accent Border | color |  |
| `--evcc-modal-accent-text` | Modal Accent Text | color |  |
| `--evcc-modal-backdrop-bg` | Modal Backdrop BG | color |  |
| `--evcc-modal-backdrop-blur` | Modal Backdrop Blur | number |  |
| `--evcc-modal-bg` | Modal BG | color |  |
| `--evcc-modal-border` | Modal Border | color |  |
| `--evcc-modal-border-default` | Modal Border Default | color |  |
| `--evcc-modal-border-strong` | Modal Border Strong | color |  |
| `--evcc-modal-border-subtle` | Modal Border Subtle | color |  |
| `--evcc-modal-chip-active-bg` | Modal Chip Active BG | color |  |
| `--evcc-modal-chip-active-border` | Modal Chip Active Border | color |  |
| `--evcc-modal-chip-active-text` | Modal Chip Active Text | color |  |
| `--evcc-modal-chip-bg` | Modal Chip BG | color |  |
| `--evcc-modal-chip-border` | Modal Chip Border | color |  |
| `--evcc-modal-chip-hover-bg` | Modal Chip Hover BG | color |  |
| `--evcc-modal-chip-hover-border` | Modal Chip Hover Border | color |  |
| `--evcc-modal-chip-hover-text` | Modal Chip Hover Text | color |  |
| `--evcc-modal-chip-text` | Modal Chip Text | color |  |
| `--evcc-modal-footer-bg` | Modal Footer BG | color |  |
| `--evcc-modal-header-bg` | Modal Header BG | color |  |
| `--evcc-modal-input-bg` | Modal Input BG | color |  |
| `--evcc-modal-padding` | Modal Padding | size |  |
| `--evcc-modal-radius` | Modal Radius | size |  |
| `--evcc-modal-section-gap` | Modal Section Gap | size |  |
| `--evcc-modal-shadow` | Modal Shadow | shadow |  |
| `--evcc-modal-surface-input` | Modal Surface Input | color |  |
| `--evcc-modal-surface-panel` | Modal Surface Panel | color |  |
| `--evcc-modal-surface-section` | Modal Surface Section | color |  |
| `--evcc-modal-text-muted` | Modal Text Muted | color |  |
| `--evcc-modal-text-primary` | Modal Text Primary | color |  |
| `--evcc-modal-text-secondary` | Modal Text Secondary | color |  |
| `--evcc-modal-warning-bg` | Modal Warning BG | color |  |
| `--evcc-modal-warning-border` | Modal Warning Border | color |  |
| `--evcc-modal-warning-text` | Modal Warning Text | color |  |

## Animal Companion  ·  14

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-animal-eye-good` | Eye — Good (>50% battery) | color |  |
| `--evcc-animal-eye-mid` | Eye — Mid (25–50%) | color |  |
| `--evcc-animal-eye-warn` | Eye — Warn (15–25%) | color |  |
| `--evcc-animal-eye-low` | Eye — Low (≤15%) | color |  |
| `--evcc-animal-eye-charging` | Eye — Charging (pulses) | color |  |
| `--evcc-animal-fur` | Fur (all animals) | color |  |
| `--evcc-animal-fur-shadow` | Fur Shadow (all) | color |  |
| `--evcc-animal-fur-highlight` | Fur Highlight (all) | color |  |
| `--evcc-animal-eye` | Eye Base (all) | color |  |
| `--evcc-animal-pupil` | Pupil (all) | color |  |
| `--evcc-animal-nose` | Nose (all) | color |  |
| `--evcc-animal-whisker` | Whisker (all) | color |  |
| `--evcc-animal-ear-inner` | Ear Inner (all) | color |  |
| `--evcc-animal-white-tip` | White Tip / Accent (all) | color |  |

## Animal Companion — Cat  ·  14

*(template — repeats per companion)*

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-animal-cat-eye-good` | Eye — Good | color |  |
| `--evcc-animal-cat-eye-mid` | Eye — Mid | color |  |
| `--evcc-animal-cat-eye-warn` | Eye — Warn | color |  |
| `--evcc-animal-cat-eye-low` | Eye — Low | color |  |
| `--evcc-animal-cat-eye-charging` | Eye — Charging | color |  |
| `--evcc-animal-cat-fur` | Fur | color |  |
| `--evcc-animal-cat-fur-shadow` | Fur Shadow | color |  |
| `--evcc-animal-cat-fur-highlight` | Fur Highlight | color |  |
| `--evcc-animal-cat-eye` | Eye Base | color |  |
| `--evcc-animal-cat-pupil` | Pupil | color |  |
| `--evcc-animal-cat-nose` | Nose | color |  |
| `--evcc-animal-cat-whisker` | Whisker | color |  |
| `--evcc-animal-cat-ear-inner` | Ear Inner | color |  |
| `--evcc-animal-cat-white-tip` | White Tip / Accent | color |  |

## Shared Foundations  ·  15

| Token | Controls | Type | Range |
|---|---|---|---|
| `--evcc-font-family` | Font Family | typography |  |
| `--evcc-gap` | Gap | size |  |
| `--evcc-grid-gap` | Grid Gap | size |  |
| `--evcc-hover-lift` | Hover Lift | motion |  |
| `--evcc-pad` | Pad | size |  |
| `--evcc-press-scale` | Press Scale | number |  |
| `--evcc-radius-card` | Radius Card | size |  |
| `--evcc-radius-chip` | Radius Chip | size |  |
| `--evcc-radius-inner` | Radius Inner | size |  |
| `--evcc-radius-panel` | Radius Panel | size |  |
| `--evcc-section-gap` | Section Gap | size |  |
| `--evcc-space-lg` | Space Lg | text |  |
| `--evcc-space-md` | Space Md | text |  |
| `--evcc-space-sm` | Space Sm | text |  |
| `--evcc-transition-normal` | Transition Normal | motion |  |

