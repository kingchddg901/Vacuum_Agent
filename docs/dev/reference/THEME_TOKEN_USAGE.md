<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Source of truth: src/theme-tokens/ (the editor registry) + the card CSS.
     Regenerate after any token add/remove/rename:  node scripts/gen-theme-token-docs.mjs -->

# Theme Token CSS-Usage Trace

> Generated reference — part of the [Theme System](../frontend/theme-system.md) docs. Companion: [Theme Token Map](THEME_TOKEN_MAP.md).

For each catalog token (`--evcc-*`): its **default** declaration, every real **consumer** `var()` (CSS property + file:line), and JS `setProperty` apply sites. Multiline-aware (handles `var(` wrapped across lines); scans `src/`, the `animal-svg/` module, and the Python preloaded themes. The self-referential seed (`--evcc-x: var(--evcc-x, fallback)`) is the default, not a use.

- Catalog **411** · consumer `var()` uses **2380**
- **277** with a STATIC consumer · **134** consumed DYNAMICALLY (constructed names, below) · **0** with no consumer at all
- `var()` → non-catalog tokens **12** · dynamic `var(--evcc-…${…})` sites **3**

> **A token with no STATIC consumer is not dead.** This tracer is a regex scan and cannot follow a `var()` whose name is built at runtime, so 134 live tokens would otherwise read as rot — and deleting them would break theming for every animal, every floor material and the whole room palette. The families that construct their names:
> - **84** `animal` — `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`
> - **38** `floor-material` — `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key
> - **12** `room-fill` — `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)
- **Token CSS coverage 98.8%** — 1435/1453 color declarations resolve through a token (18 deliberate `theme-lint-ignore`, **0 stray**); **100.0%** of colors that should be themed. Scope: `src/styles/*` (minus token defs) + the standalone cards; guarded by `scripts/check-styles.mjs`.

---

## App Shell & Typography  ·  10 static / 10

**`--evcc-accent`** — Accent · default `var(--accent-color, #3b82f6)` src/styles/foundation.js, src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/cards/_shared.js (color)
- src/cards/dashboard-card.js (--accent)
- src/cards/profile-card.js (--accent)
- src/room-card.js (--accent)
- src/styles/external-jobs.js
- src/styles/external-jobs.js (color)
- src/styles/foundation.js
- src/styles/foundation.js (--evcc-color-docked)
- src/styles/job-summary.js
- src/styles/learning.js
- src/styles/learning.js (color)
- src/styles/maintenance.js
- src/styles/maintenance.js (color)
- src/styles/map.js (background)
- src/styles/map.js (border-color)
- src/styles/map.js
- src/styles/map.js (color)
- src/styles/map.js (accent-color)
- src/styles/metrics.js (border-color)
- src/styles/mobile.js (color)
- src/styles/mobile.js
- src/styles/modal-host.js (--evcc-modal-accent)
- src/styles/modal-host.js (--evcc-modal-accent-text)
- src/styles/modal-host.js
- src/styles/modal-host.js (border-color)
- src/styles/modal-host.js (background)
- src/styles/modals.js
- src/styles/order.js
- src/styles/room-rules.js
- src/styles/room-rules.js (color)
- src/styles/room-rules.js (border-color)
- src/styles/rooms.js
- src/styles/rooms.js (--evcc-chip-text)
- src/styles/run-profiles.js
- src/styles/saved-zones.js
- src/styles/saved-zones.js (background)
- src/styles/saved-zones.js (border-color)
- src/styles/saved-zones.js (accent-color)
- src/styles/setup.js (background)
- src/styles/setup.js
- src/styles/setup.js (color)
- src/styles/setup.js (border-color)
- src/styles/shell.js
- src/styles/shell.js (color)
- src/styles/theme-preview.js
- src/styles/theme-preview.js (color)
- src/styles/theme.js
- src/styles/theme.js (color)
- src/styles/theme.js (border-color)
- src/styles/theme.js (background)
- src/styles/toast-host.js

**`--evcc-accent-soft`** — Accent Soft · default `rgba(0,229,255,0.16)` src/styles/foundation.js
- src/styles/map.js (background)
- src/styles/map.js (fill)

**`--evcc-tab-active-bg`** — Tab Active BG · default —
- src/styles/external-jobs.js (background)
- src/styles/foundation.js (background)
- src/styles/setup.js (background)
- src/styles/shell.js (background)

**`--evcc-tab-active-border`** — Tab Active Border · default —
- src/styles/external-jobs.js (border-color)
- src/styles/setup.js (border-color)

**`--evcc-tab-active-text`** — Tab Active Text · default —
- src/styles/external-jobs.js (color)
- src/styles/foundation.js (color)
- src/styles/setup.js (color)
- src/styles/shell.js (color)

**`--evcc-text-muted`** — Text Muted · default `rgba(240,242,245,0.48)` src/styles/foundation.js, src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/cards/_shared.js (color)
- src/cards/dashboard-card.js (--text-muted)
- src/cards/profile-card.js (--text-muted)
- src/cards/vacuum-map-host.js (color)
- src/room-card.js (--text-muted)
- src/styles/base-station.js (color)
- src/styles/learning.js (--evcc-learning-text-muted)
- src/styles/learning.js
- src/styles/learning.js (color)
- src/styles/maintenance.js (color)
- src/styles/map.js (color)
- src/styles/metrics.js (color)
- src/styles/mobile.js (color)
- src/styles/modal-host.js (--evcc-modal-text-muted)
- src/styles/modal-host.js
- src/styles/modal-host.js (color)
- src/styles/modals.js
- src/styles/modals.js (color)
- src/styles/review.js (color)
- src/styles/room-access.js (color)
- src/styles/room-rules.js (color)
- src/styles/rooms.js (color)
- src/styles/rooms.js
- src/styles/rooms.js (--evcc-learning-note-text)
- src/styles/run-profiles.js (color)
- src/styles/saved-zones.js (color)
- src/styles/setup.js (color)
- src/styles/setup.js
- src/styles/shell.js (color)
- src/styles/shell.js
- src/styles/theme-preview.js (color)
- src/styles/theme.js (color)
- src/styles/toast-host.js (color)

**`--evcc-text-on-accent`** — Text On Accent · default `#ffffff` src/styles/foundation.js
- src/cards/dashboard-card.js (color)
- src/cards/profile-card.js (--text-on-accent)
- src/room-card.js (--text-on-accent)
- src/styles/map.js (color)
- src/styles/modal-host.js (color)
- src/styles/saved-zones.js (color)
- src/styles/setup.js (color)

**`--evcc-text-primary`** — Text Primary · default `var(--primary-text-color, #f0f2f5)` src/styles/foundation.js, src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/cards/_shared.js (color)
- src/cards/dashboard-card.js (--text-primary)
- src/cards/profile-card.js (--text-primary)
- src/room-card.js (--text-primary)
- src/styles/base-station.js (color)
- src/styles/external-jobs.js (color)
- src/styles/foundation.js
- src/styles/foundation.js (color)
- src/styles/foundation.js (--evcc-chip-hover-text)
- src/styles/learning.js (--evcc-learning-text-primary)
- src/styles/learning.js (color)
- src/styles/maintenance.js (color)
- src/styles/maintenance.js
- src/styles/map.js (color)
- src/styles/metrics.js (color)
- src/styles/mobile.js (color)
- src/styles/modal-host.js (--evcc-modal-text-primary)
- src/styles/modal-host.js (--evcc-modal-chip-hover-text)
- src/styles/modal-host.js
- src/styles/modal-host.js (color)
- src/styles/modals.js
- src/styles/modals.js (color)
- src/styles/order.js
- src/styles/review.js (color)
- src/styles/room-estimate.js
- src/styles/room-rules.js (color)
- src/styles/rooms.js (color)
- src/styles/rooms.js
- src/styles/rooms.js (--evcc-estimate-learned-text)
- src/styles/rooms.js (--evcc-chip-text)
- src/styles/run-profiles.js (color)
- src/styles/saved-zones.js (color)
- src/styles/setup.js (color)
- src/styles/shell.js (color)
- src/styles/theme-preview.js (color)
- src/styles/theme-preview.js
- src/styles/theme.js (color)
- src/styles/toast-host.js (color)

**`--evcc-text-secondary`** — Text Secondary · default `var(--secondary-text-color, rgba(240,242,245,0.72))` src/styles/foundation.js, src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/base-station.js (color)
- src/styles/external-jobs.js (color)
- src/styles/foundation.js
- src/styles/foundation.js (--evcc-color-idle)
- src/styles/foundation.js (--evcc-chip-text)
- src/styles/foundation.js (color)
- src/styles/job-summary.js (color)
- src/styles/learning.js (--evcc-learning-text-secondary)
- src/styles/learning.js (--evcc-learning-confidence-neutral-text)
- src/styles/learning.js (color)
- src/styles/maintenance.js (color)
- src/styles/maintenance.js
- src/styles/map.js (color)
- src/styles/metrics.js (color)
- src/styles/mobile.js (color)
- src/styles/modal-host.js (--evcc-modal-text-secondary)
- src/styles/modal-host.js (--evcc-modal-chip-text)
- src/styles/modal-host.js
- src/styles/modal-host.js (color)
- src/styles/modals.js
- src/styles/order.js
- src/styles/review.js (color)
- src/styles/room-access.js (color)
- src/styles/room-estimate.js
- src/styles/room-rules.js (color)
- src/styles/rooms.js (--evcc-chip-active-text)
- src/styles/rooms.js (color)
- src/styles/rooms.js
- src/styles/rooms.js (--evcc-estimate-default-text)
- src/styles/rooms.js (--evcc-chip-text)
- src/styles/run-profiles.js (color)
- src/styles/saved-zones.js (color)
- src/styles/setup.js (color)
- src/styles/shell.js (color)
- src/styles/theme-preview.js (color)
- src/styles/theme-preview.js
- src/styles/theme.js (color)

**`--evcc-text-strong`** — Text Strong · default `var(--primary-text-color, #f0f2f5)` src/styles/foundation.js
- src/styles/learning.js (color)
- src/styles/metrics.js (color)

## Cards & Surfaces  ·  19 static / 19

**`--evcc-bg-input`** — BG Input · default `var(--evcc-surface-input)` src/styles/foundation.js
- src/styles/theme-preview.js

**`--evcc-card-bg`** — Card BG · default `var(--evcc-surface-card)` src/styles/foundation.js
- src/styles/theme-preview.js

**`--evcc-card-gap`** — Card Gap · default —
- src/styles/rooms.js (gap)

**`--evcc-card-min-height`** — Card Min Height · default —
- src/styles/rooms.js (min-height)
- src/styles/theme-preview.js (min-height)

**`--evcc-card-padding`** — Card Padding · default —
- src/styles/rooms.js (padding)
- src/styles/theme-preview.js (padding)

**`--evcc-panel-bg`** — Panel BG · default `var(--evcc-surface-panel)` src/styles/foundation.js
- src/styles/run-profiles.js
- src/styles/saved-zones.js
- src/styles/theme-preview.js

**`--evcc-surface-action`** — Surface Action · default `rgba(255,255,255,0.10)` src/styles/foundation.js
- src/styles/learning.js (background)
- src/styles/map.js (background)

**`--evcc-surface-action-hover`** — Surface Action Hover · default `rgba(255,255,255,0.18)` src/styles/foundation.js
- src/cards/_shared.js (background)
- src/cards/dashboard-card.js (background)
- src/room-card.js (background)
- src/styles/learning.js (background)
- src/styles/map.js (background)
- src/styles/setup.js (background)

**`--evcc-surface-base`** — Surface Base · default `var(--card-background-color, #1c2127)` src/styles/foundation.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/foundation.js (--evcc-surface-card)
- src/styles/foundation.js
- src/styles/modal-host.js (--evcc-modal-bg)
- src/styles/theme.js (background)
- src/styles/theme.js

**`--evcc-surface-card`** — Surface Card · default `var(--evcc-surface-base)` src/styles/foundation.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/cards/_shared.js (background)
- src/cards/dashboard-card.js (--surface)
- src/cards/profile-card.js (--surface)
- src/room-card.js (--surface)
- src/styles/foundation.js (--evcc-card-bg)
- src/styles/rooms.js
- src/styles/rooms.js (background-color)
- src/styles/setup.js (background)
- src/styles/shell.js (background)
- src/styles/theme-preview.js (background)
- src/styles/theme-preview.js
- src/styles/theme.js (background)
- src/styles/theme.js

**`--evcc-surface-chip`** — Surface Chip · default `rgba(255,255,255,0.09)` src/styles/foundation.js
- src/styles/learning.js (background)

**`--evcc-surface-input`** — Surface Input · default `rgba(255,255,255,0.06)` src/styles/foundation.js, src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/cards/profile-card.js (--surface-input)
- src/styles/external-jobs.js (background)
- src/styles/foundation.js
- src/styles/foundation.js (--evcc-bg-input)
- src/styles/foundation.js (--evcc-chip-bg)
- src/styles/maintenance.js
- src/styles/map.js (background)
- src/styles/metrics.js (background)
- src/styles/modal-host.js (--evcc-modal-surface-input)
- src/styles/modal-host.js (--evcc-modal-input-bg)
- src/styles/modal-host.js (--evcc-modal-chip-bg)
- src/styles/modal-host.js
- src/styles/modal-host.js (background)
- src/styles/order.js
- src/styles/review.js (background)
- src/styles/room-rules.js (background)
- src/styles/rooms.js
- src/styles/rooms.js (background)
- src/styles/run-profiles.js
- src/styles/run-profiles.js (background)
- src/styles/saved-zones.js
- src/styles/saved-zones.js (background)
- src/styles/setup.js (background)
- src/styles/theme-preview.js (background)
- src/styles/theme.js (background)

**`--evcc-surface-overlay`** — Surface Overlay · default `rgba(0,0,0,0.4)` src/styles/foundation.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/mobile.js (background)
- src/styles/modal-host.js (--evcc-modal-backdrop-bg)

**`--evcc-surface-panel`** — Surface Panel · default `color-mix(in srgb, var(--evcc-surface-base) 85%, white 15%)` src/styles/foundation.js, src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/base-station.js (background)
- src/styles/external-jobs.js (background)
- src/styles/foundation.js
- src/styles/foundation.js (background)
- src/styles/foundation.js (--evcc-panel-bg)
- src/styles/foundation.js (--evcc-chip-hover-bg)
- src/styles/learning.js (--evcc-learning-panel-bg)
- src/styles/maintenance.js (background)
- src/styles/map.js (background)
- src/styles/metrics.js (background)
- src/styles/mobile.js (background)
- src/styles/modal-host.js (--evcc-modal-surface-panel)
- src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-modal-chip-hover-bg)
- src/styles/order.js
- src/styles/review.js (background)
- src/styles/review.js
- src/styles/room-access.js
- src/styles/room-estimate.js
- src/styles/room-rules.js (background)
- src/styles/run-profiles.js (background)
- src/styles/saved-zones.js (background)
- src/styles/setup.js (background)
- src/styles/shell.js (background)
- src/styles/theme-preview.js (background)
- src/styles/theme-preview.js
- src/styles/theme.js (background)
- src/styles/theme.js

**`--evcc-surface-raised`** — Surface Raised · default `color-mix(in srgb, var(--evcc-surface-base) 92%, white 8%)` src/styles/foundation.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/base-station.js (background)
- src/styles/base-station.js
- src/styles/external-jobs.js (background)
- src/styles/foundation.js (background)
- src/styles/maintenance.js
- src/styles/maintenance.js (background)
- src/styles/map.js (background)
- src/styles/metrics.js (background)
- src/styles/mobile.js (background)
- src/styles/modal-host.js (--evcc-modal-surface-section)
- src/styles/review.js (background)
- src/styles/shell.js (background)
- src/styles/toast-host.js (background)

**`--evcc-surface-subtle`** — Surface Subtle · default `rgba(255,255,255,0.04)` src/styles/foundation.js
- src/cards/_shared.js
- src/cards/dashboard-card.js (background)
- src/room-card.js (--surface-subtle)
- src/styles/maintenance.js (background)
- src/styles/modal-host.js (background)
- src/styles/rooms.js (background)
- src/styles/setup.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-surface-success`** — Surface Success · default `rgba(76,175,110,0.12)` src/styles/foundation.js
- src/cards/dashboard-card.js (--status-success-bg)
- src/styles/rooms.js (background)

**`--evcc-surface-sunken`** — Surface Sunken · default `rgba(0,0,0,0.18)` src/styles/foundation.js
- src/cards/dashboard-card.js (background)
- src/styles/metrics.js (background)
- src/styles/setup.js (background)

**`--evcc-surface-warning`** — Surface Warning · default `rgba(255,180,0,0.12)` src/styles/foundation.js
- src/cards/dashboard-card.js (--status-warning-bg)
- src/styles/learning.js (background)
- src/styles/rooms.js (background)

## Borders & Shadows  ·  7 static / 7

**`--evcc-border-default`** — Border Default · default `rgba(255,255,255,0.10)` src/styles/foundation.js, src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/cards/_shared.js
- src/cards/dashboard-card.js (--border)
- src/cards/profile-card.js (--border)
- src/room-card.js (--border)
- src/styles/base-station.js
- src/styles/external-jobs.js
- src/styles/foundation.js
- src/styles/foundation.js (--evcc-chip-border)
- src/styles/job-summary.js
- src/styles/learning.js (--evcc-learning-panel-border)
- src/styles/learning.js (--evcc-learning-confidence-neutral-border)
- src/styles/learning.js
- src/styles/maintenance.js
- src/styles/map.js
- src/styles/metrics.js
- src/styles/mobile.js
- src/styles/modal-host.js (--evcc-modal-border)
- src/styles/modal-host.js (--evcc-modal-border-default)
- src/styles/modal-host.js (--evcc-modal-chip-border)
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/order.js
- src/styles/review.js
- src/styles/review.js (border-color)
- src/styles/room-access.js
- src/styles/room-rules.js (border-color)
- src/styles/room-rules.js
- src/styles/rooms.js
- src/styles/rooms.js (--evcc-estimate-default-border)
- src/styles/run-profiles.js
- src/styles/saved-zones.js
- src/styles/setup.js
- src/styles/shell.js
- src/styles/theme-preview.js
- src/styles/theme.js
- src/styles/toast-host.js

**`--evcc-border-strong`** — Border Strong · default `rgba(255,255,255,0.18)` src/styles/foundation.js, src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/base-station.js (border-color)
- src/styles/foundation.js
- src/styles/foundation.js (--evcc-chip-hover-border)
- src/styles/maintenance.js (border-color)
- src/styles/map.js (border-color)
- src/styles/metrics.js
- src/styles/modal-host.js (--evcc-modal-border-strong)
- src/styles/modal-host.js (--evcc-modal-chip-hover-border)
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/order.js
- src/styles/rooms.js (border-color)
- src/styles/theme-preview.js
- src/styles/theme.js (border-color)

**`--evcc-border-subtle`** — Border Subtle · default `rgba(255,255,255,0.06)` src/styles/foundation.js, src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/base-station.js
- src/styles/job-summary.js
- src/styles/learning.js
- src/styles/maintenance.js
- src/styles/map.js
- src/styles/metrics.js
- src/styles/mobile.js
- src/styles/mobile.js (background)
- src/styles/modal-host.js (--evcc-modal-border-subtle)
- src/styles/modal-host.js
- src/styles/review.js
- src/styles/room-estimate.js
- src/styles/room-rules.js
- src/styles/rooms.js (border-color)
- src/styles/setup.js
- src/styles/shell.js
- src/styles/theme-preview.js
- src/styles/theme.js
- src/styles/theme.js (border-color)

**`--evcc-border-success`** — Border Success · default `rgba(76,175,110,0.35)` src/styles/foundation.js
- src/styles/rooms.js (border-color)
- src/styles/rooms.js (--evcc-chip-active-bg)
- src/styles/rooms.js (--evcc-chip-active-border)

**`--evcc-border-warning`** — Border Warning · default `rgba(255,180,0,0.35)` src/styles/foundation.js
- src/styles/learning.js
- src/styles/rooms.js (border-color)
- src/styles/rooms.js (--evcc-chip-active-bg)
- src/styles/rooms.js (--evcc-chip-active-border)

**`--evcc-shadow-card`** — Shadow Card · default —
- src/styles/learning.js (--evcc-learning-panel-shadow)
- src/styles/order.js
- src/styles/rooms.js (box-shadow)
- src/styles/run-profiles.js (box-shadow)
- src/styles/saved-zones.js (box-shadow)
- src/styles/shell.js (box-shadow)
- src/styles/theme-preview.js (box-shadow)

**`--evcc-shadow-hover`** — Shadow Hover · default —
- src/styles/order.js (box-shadow)
- src/styles/order.js
- src/styles/rooms.js
- src/styles/rooms.js (box-shadow)
- src/styles/theme-preview.js (box-shadow)
- src/styles/theme-preview.js

## Chips  ·  31 static / 31

**`--evcc-chip-active-bg`** — Chip Active BG · default src/styles/rooms.js
- src/styles/foundation.js (background)

**`--evcc-chip-active-border`** — Chip Active Border · default src/styles/rooms.js
- src/styles/foundation.js (border-color)

**`--evcc-chip-active-text`** — Chip Active Text · default src/styles/rooms.js
- src/styles/foundation.js (color)

**`--evcc-chip-bg`** — Chip BG · default `var(--evcc-surface-input)` src/styles/foundation.js, src/styles/modal-host.js, src/styles/order.js, src/styles/rooms.js
- src/styles/foundation.js (background)
- src/styles/maintenance.js (background)
- src/styles/rooms.js
- src/styles/theme-preview.js

**`--evcc-chip-border`** — Chip Border · default `var(--evcc-border-default)` src/styles/foundation.js, src/styles/modal-host.js, src/styles/order.js, src/styles/rooms.js
- src/styles/foundation.js
- src/styles/maintenance.js
- src/styles/theme-preview.js

**`--evcc-chip-excluded-bg`** — Chip Excluded BG · default —
- src/styles/rooms.js (--evcc-chip-bg)
- src/styles/theme-preview.js (background)

**`--evcc-chip-excluded-border`** — Chip Excluded Border · default —
- src/styles/rooms.js (--evcc-chip-border)
- src/styles/theme-preview.js (border-color)

**`--evcc-chip-excluded-text`** — Chip Excluded Text · default —
- src/styles/rooms.js (--evcc-chip-text)
- src/styles/theme-preview.js (color)

**`--evcc-chip-font-size`** — Chip Font Size · default src/styles/modal-host.js, src/styles/order.js, src/styles/rooms.js
- src/styles/foundation.js (font-size)

**`--evcc-chip-font-weight`** — Chip Font Weight · default src/styles/modal-host.js, src/styles/order.js, src/styles/rooms.js
- src/styles/foundation.js (font-weight)

**`--evcc-chip-gap`** — Chip Gap · default —
- src/styles/foundation.js (gap)
- src/styles/order.js (gap)
- src/styles/rooms.js (gap)

**`--evcc-chip-height`** — Chip Height · default `24px` src/styles/foundation.js, src/styles/modal-host.js, src/styles/order.js, src/styles/rooms.js
- src/styles/foundation.js (min-height)
- src/styles/maintenance.js (min-height)

**`--evcc-chip-hover-bg`** — Chip Hover BG · default `var(--evcc-surface-panel)` src/styles/foundation.js, src/styles/modal-host.js
- src/styles/foundation.js (background)
- src/styles/order.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-chip-hover-border`** — Chip Hover Border · default `var(--evcc-border-strong)` src/styles/foundation.js, src/styles/modal-host.js
- src/styles/foundation.js (border-color)
- src/styles/order.js (border-color)
- src/styles/theme-preview.js (border-color)

**`--evcc-chip-hover-text`** — Chip Hover Text · default `var(--evcc-text-primary)` src/styles/foundation.js, src/styles/modal-host.js
- src/styles/foundation.js (color)
- src/styles/order.js (color)
- src/styles/theme-preview.js (color)

**`--evcc-chip-icon-height`** — Chip Icon Height · default `24px` src/styles/foundation.js, src/styles/modal-host.js
- src/styles/foundation.js (min-height)

**`--evcc-chip-icon-padding`** — Chip Icon Padding · default `4px 8px` src/styles/foundation.js, src/styles/modal-host.js
- src/styles/foundation.js (padding)

**`--evcc-chip-icon-size`** — Chip Icon Size · default `0.8rem` src/styles/foundation.js, src/styles/modal-host.js
- src/styles/foundation.js (font-size)

**`--evcc-chip-included-bg`** — Chip Included BG · default —
- src/styles/modal-host.js (background)
- src/styles/rooms.js (--evcc-chip-bg)
- src/styles/theme-preview.js (background)

**`--evcc-chip-included-border`** — Chip Included Border · default —
- src/styles/modal-host.js (border-color)
- src/styles/rooms.js (--evcc-chip-border)
- src/styles/theme-preview.js (border-color)

**`--evcc-chip-included-text`** — Chip Included Text · default —
- src/styles/modal-host.js (color)
- src/styles/rooms.js (--evcc-chip-text)
- src/styles/theme-preview.js (color)

**`--evcc-chip-neutral-bg`** — Chip Neutral BG · default —
- src/styles/order.js

**`--evcc-chip-padding`** — Chip Padding · default `5px 14px` src/styles/foundation.js, src/styles/modal-host.js, src/styles/order.js, src/styles/rooms.js
- src/styles/foundation.js (padding)
- src/styles/maintenance.js (padding)

**`--evcc-chip-radius`** — Chip Radius · default `999px` src/styles/foundation.js, src/styles/modal-host.js
- src/styles/foundation.js (border-radius)
- src/styles/maintenance.js (border-radius)
- src/styles/modal-host.js (border-radius)

**`--evcc-chip-success-bg`** — Chip Success BG · default —
- src/styles/rooms.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-chip-success-border`** — Chip Success Border · default —
- src/styles/rooms.js (border-color)
- src/styles/theme-preview.js (border-color)

**`--evcc-chip-success-text`** — Chip Success Text · default —
- src/styles/rooms.js (color)
- src/styles/theme-preview.js (color)

**`--evcc-chip-text`** — Chip Text · default `var(--evcc-text-secondary)` src/styles/foundation.js, src/styles/modal-host.js, src/styles/order.js, src/styles/rooms.js
- src/styles/foundation.js (color)
- src/styles/maintenance.js (color)
- src/styles/theme-preview.js

**`--evcc-chip-warning-bg`** — Chip Warning BG · default —
- src/styles/rooms.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-chip-warning-border`** — Chip Warning Border · default —
- src/styles/rooms.js (border-color)
- src/styles/theme-preview.js (border-color)

**`--evcc-chip-warning-text`** — Chip Warning Text · default —
- src/styles/rooms.js (color)
- src/styles/theme-preview.js (color)

## Room Cards  ·  13 static / 13

**`--evcc-profile-chip-bg`** — Profile Chip BG · default —
- src/styles/rooms.js (--evcc-chip-bg)
- src/styles/theme-preview.js (background)

**`--evcc-profile-chip-border`** — Profile Chip Border · default —
- src/styles/rooms.js (--evcc-chip-border)
- src/styles/theme-preview.js (border-color)

**`--evcc-profile-chip-custom-bg`** — Profile Chip Custom BG · default —
- src/styles/rooms.js (--evcc-chip-bg)
- src/styles/theme-preview.js (background)

**`--evcc-profile-chip-custom-border`** — Profile Chip Custom Border · default —
- src/styles/rooms.js (--evcc-chip-border)
- src/styles/theme-preview.js (border-color)

**`--evcc-profile-chip-custom-text`** — Profile Chip Custom Text · default —
- src/styles/rooms.js (--evcc-chip-text)
- src/styles/theme-preview.js (color)

**`--evcc-profile-chip-text`** — Profile Chip Text · default —
- src/styles/rooms.js (--evcc-chip-text)
- src/styles/theme-preview.js (color)

**`--evcc-room-chip-bg`** — Room Chip BG · default —
- src/styles/rooms.js (--evcc-chip-bg)
- src/styles/theme-preview.js (background)

**`--evcc-room-chip-border`** — Room Chip Border · default —
- src/styles/rooms.js (--evcc-chip-border)
- src/styles/theme-preview.js (border-color)

**`--evcc-room-chip-text`** — Room Chip Text · default —
- src/styles/rooms.js (--evcc-chip-text)
- src/styles/theme-preview.js (color)

**`--evcc-room-fill-opacity`** — Room Card Opacity · default src/styles/rooms.js
- src/styles/rooms.js (opacity)
- src/styles/theme-preview.js

**`--evcc-room-grid-columns`** — Room Grid Columns · default —
- src/styles/layout.js (grid-template-columns)

**`--evcc-room-grid-gap`** — Room Grid Gap · default `var(--evcc-grid-gap)` src/styles/layout.js
- src/styles/layout.js (gap)

**`--evcc-room-grid-min`** — Room Grid Min · default `240px` src/styles/layout.js
- src/styles/layout.js

## Map  ·  22 static + 12 dynamic / 34

**`--evcc-map-label-bg`** — Map Label Background · default src/styles/modal-host.js
- src/styles/map.js (background)

**`--evcc-map-label-text`** — Map Label Text · default src/styles/modal-host.js
- src/styles/map.js (color)

**`--evcc-map-label-text-selected`** — Map Label Text (Selected) · default src/styles/modal-host.js
- src/styles/map.js (color)

**`--evcc-map-label-order-text`** — Map Order Badge Text · default src/styles/modal-host.js
- src/styles/map.js (color)

**`--evcc-map-tooltip-bg`** — Map Tooltip Background · default src/styles/modal-host.js
- src/styles/map.js (background)

**`--evcc-map-tooltip-border`** — Map Tooltip Border · default src/styles/modal-host.js
- src/styles/map.js

**`--evcc-map-tooltip-text`** — Map Tooltip Text · default src/styles/modal-host.js
- src/styles/map.js (color)

**`--evcc-map-tooltip-hint`** — Map Tooltip Hint Text · default src/styles/modal-host.js
- src/styles/map.js (color)

**`--evcc-map-compose-selected-stroke`** — Composer Selected Outline · default src/styles/modal-host.js
- src/styles/map.js (stroke)

**`--evcc-map-compose-cut-fill`** — Composer Cutout Fill · default src/styles/modal-host.js
- src/styles/map.js (fill)

**`--evcc-map-compose-cut-selected-fill`** — Composer Cutout Fill (Selected) · default src/styles/modal-host.js
- src/styles/map.js (fill)

**`--evcc-map-vertex-selected-glow`** — Composer Selected Vertex Glow · default src/styles/modal-host.js
- src/styles/map.js

**`--evcc-map-ov-current`** — Overlay: Current Room · default src/styles/modal-host.js
- src/styles/map.js (fill)
- src/styles/map.js (stroke)

**`--evcc-map-ov-nogo`** — Overlay: No-Go Zone · default src/styles/modal-host.js
- src/styles/map.js (fill)
- src/styles/map.js (stroke)

**`--evcc-map-ov-nomop`** — Overlay: No-Mop Zone · default src/styles/modal-host.js
- src/styles/map.js (fill)
- src/styles/map.js (stroke)

**`--evcc-map-ov-wall`** — Overlay: Virtual Wall · default src/styles/modal-host.js
- src/styles/map.js (stroke)

**`--evcc-map-ov-zone`** — Overlay: Saved Zone · default src/styles/modal-host.js
- src/styles/map.js (fill)
- src/styles/map.js (stroke)

**`--evcc-map-ov-path`** — Overlay: Cleaning Path · default src/styles/modal-host.js
- src/styles/map.js (stroke)

**`--evcc-map-ov-robot`** — Overlay: Robot Marker · default src/styles/modal-host.js
- src/styles/map.js (background)
- src/styles/map.js

**`--evcc-map-ov-dock`** — Overlay: Dock Marker · default src/styles/modal-host.js
- src/styles/map.js (background)

**`--evcc-map-ov-obstacle`** — Overlay: Obstacle Marker · default src/styles/modal-host.js
- src/styles/map.js (background)
- src/styles/map.js

**`--evcc-map-ov-area-text`** — Overlay: Area Label Text · default src/styles/modal-host.js
- src/styles/map.js (color)

**`--evcc-room-fill-1`** — Map Room Color 1 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-2`** — Map Room Color 2 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-3`** — Map Room Color 3 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-4`** — Map Room Color 4 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-5`** — Map Room Color 5 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-6`** — Map Room Color 6 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-7`** — Map Room Color 7 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-8`** — Map Room Color 8 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-9`** — Map Room Color 9 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-10`** — Map Room Color 10 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-11`** — Map Room Color 11 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-12`** — Map Room Color 12 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

## Floor Textures  ·  5 static / 5

**`--evcc-floor-textures-card-enabled`** — Card Textures Enabled (0/1) · default —
- src/styles/floor-texture-styles.js

**`--evcc-floor-textures-map-enabled`** — Map Textures Enabled (0/1) · default —
- src/styles/floor-texture-styles.js

**`--evcc-floor-texture-opacity-card`** — Card Texture Opacity (all) · default —
- src/renderers/floor-texture-surface.js

**`--evcc-floor-texture-opacity-map`** — Map Texture Opacity (all) · default —
- src/styles/floor-texture-styles.js

**`--evcc-floor-texture-map-rotate`** — Map Texture Rotation (deg) · default —
- src/bindings/map.js (getPropertyValue)

## Floor Textures — Tile  ·  0 static + 7 dynamic / 7

**`--evcc-floor-tile-base`** — Tile Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-grout`** — Tile Grout Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-accent`** — Tile Grout Line Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-opacity-card`** — Tile Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-face-opacity`** — Tile Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-grout-opacity`** — Tile Grout Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-line-opacity`** — Tile Grout Line Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Wood  ·  0 static + 6 dynamic / 6

**`--evcc-floor-wood-base`** — Wood Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-accent`** — Wood Grain & Seam Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-opacity-card`** — Wood Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-depth-opacity`** — Wood Depth Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-grain-opacity`** — Wood Grain Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-seam-opacity`** — Wood Seam Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Marble  ·  10 static + 5 dynamic / 15

**`--evcc-floor-marble-base`** — Marble Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-marble-micro`** — Marble Micro Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-marble-accent`** — Marble Vein Color · default —
- src/textures/floor-texture-registry.js

**`--evcc-floor-marble-opacity-card`** — Marble Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-marble-base-opacity`** — Marble Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-marble-micro-opacity`** — Marble Micro Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-marble-vein-opacity`** — Marble Vein Opacity (master) · default —
- src/textures/floor-texture-registry.js

**`--evcc-floor-marble-vein-blur`** — Marble Vein Blur (master, px) · default —
- src/textures/floor-texture-registry.js

**`--evcc-floor-marble-vein-major-opacity`** — Marble Major Vein Opacity +/- · default —
- src/textures/floor-texture-registry.js

**`--evcc-floor-marble-vein-minor-opacity`** — Marble Minor Vein Opacity +/- · default —
- src/textures/floor-texture-registry.js

**`--evcc-floor-marble-vein-major-blur`** — Marble Major Vein Blur +/- (px) · default —
- src/textures/floor-texture-registry.js

**`--evcc-floor-marble-vein-minor-blur`** — Marble Minor Vein Blur +/- (px) · default —
- src/textures/floor-texture-registry.js

**`--evcc-floor-marble-vein-minor-light`** — Marble Minor Vein Lighten (L+) · default —
- src/textures/floor-texture-registry.js

**`--evcc-floor-marble-vein-minor-chroma`** — Marble Minor Vein Saturation (xC) · default —
- src/textures/floor-texture-registry.js

**`--evcc-floor-marble-vein-minor-hue`** — Marble Minor Vein Hue Shift (deg) · default —
- src/textures/floor-texture-registry.js

## Floor Textures — Concrete  ·  0 static + 5 dynamic / 5

**`--evcc-floor-concrete-base`** — Concrete Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-concrete-accent`** — Concrete Micro Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-concrete-opacity-card`** — Concrete Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-concrete-broad-opacity`** — Concrete Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-concrete-micro-opacity`** — Concrete Micro Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Carpet Low  ·  0 static + 5 dynamic / 5

**`--evcc-floor-carpet-low-base`** — Carpet Low Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-low-weave`** — Carpet Low Weave Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-low-opacity-card`** — Carpet Low Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-low-base-opacity`** — Carpet Low Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-low-weave-opacity`** — Carpet Low Weave Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Carpet High  ·  0 static + 5 dynamic / 5

**`--evcc-floor-carpet-high-base`** — Carpet High Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-high-weave`** — Carpet High Weave Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-high-opacity-card`** — Carpet High Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-high-base-opacity`** — Carpet High Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-high-weave-opacity`** — Carpet High Weave Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Granite  ·  0 static + 5 dynamic / 5

**`--evcc-floor-granite-light-base`** — Granite Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-granite-light-aggregate`** — Granite Aggregate Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-granite-light-opacity-card`** — Granite Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-granite-light-base-opacity`** — Granite Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-granite-light-aggregate-opacity`** — Granite Aggregate Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Queue & Ordering  ·  41 static / 41

**`--evcc-drag-opacity`** — Drag Opacity · default —
- src/styles/order.js (opacity)
- src/styles/theme-preview.js (opacity)

**`--evcc-drag-scale`** — Drag Scale · default —
- src/styles/order.js
- src/styles/theme-preview.js

**`--evcc-drag-shadow`** — Drag Shadow · default —
- src/styles/order.js (box-shadow)
- src/styles/theme-preview.js (box-shadow)

**`--evcc-order-chip-bg`** — Order Chip BG · default —
- src/styles/order.js (--evcc-chip-bg)
- src/styles/theme-preview.js (background)

**`--evcc-order-chip-border`** — Order Chip Border · default —
- src/styles/order.js (--evcc-chip-border)
- src/styles/theme-preview.js (border-color)

**`--evcc-order-chip-text`** — Order Chip Text · default —
- src/styles/order.js (--evcc-chip-text)
- src/styles/theme-preview.js (color)

**`--evcc-order-feedback-border`** — Order Feedback Border · default —
- src/styles/order.js (border-color)
- src/styles/theme-preview.js

**`--evcc-order-target-outline`** — Order Target Outline · default —
- src/styles/order.js
- src/styles/theme-preview.js

**`--evcc-progress-complete`** — Progress Complete · default —
- src/styles/rooms.js (background)

**`--evcc-progress-fill`** — Progress Fill · default —
- src/styles/rooms.js (background)

**`--evcc-queue-chip-bg`** — Queue Chip BG · default —
- src/styles/rooms.js (background)
- src/styles/rooms.js

**`--evcc-queue-chip-border`** — Queue Chip Border · default —
- src/styles/rooms.js

**`--evcc-queue-chip-gap`** — Queue Chip Gap · default —
- src/styles/rooms.js (gap)
- src/styles/theme-preview.js (gap)

**`--evcc-queue-chip-text`** — Queue Chip Text · default —
- src/styles/rooms.js (color)
- src/styles/rooms.js

**`--evcc-queue-completed-bg`** — Queue Completed BG · default —
- src/styles/rooms.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-queue-completed-border`** — Queue Completed Border · default —
- src/styles/rooms.js (border-color)
- src/styles/theme-preview.js (border-color)

**`--evcc-queue-completed-opacity`** — Queue Completed Opacity · default —
- src/styles/rooms.js (opacity)
- src/styles/theme-preview.js (opacity)

**`--evcc-queue-completed-text`** — Queue Completed Text · default —
- src/styles/rooms.js (color)
- src/styles/theme-preview.js (color)

**`--evcc-queue-current-bg`** — Queue Current BG · default —
- src/styles/rooms.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-queue-current-border`** — Queue Current Border · default —
- src/styles/rooms.js (border-color)
- src/styles/theme-preview.js (border-color)

**`--evcc-queue-current-glow`** — Queue Current Glow · default —
- src/styles/rooms.js (box-shadow)
- src/styles/theme-preview.js (box-shadow)

**`--evcc-queue-current-text`** — Queue Current Text · default —
- src/styles/rooms.js (color)
- src/styles/theme-preview.js (color)

**`--evcc-queue-hover-bg`** — Queue Hover BG · default —
- src/styles/rooms.js (background)

**`--evcc-queue-hover-border`** — Queue Hover Border · default —
- src/styles/rooms.js (border-color)

**`--evcc-queue-hover-text`** — Queue Hover Text · default —
- src/styles/rooms.js (color)

**`--evcc-queue-inferred-bg`** — Queue Inferred BG · default —
- src/styles/rooms.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-queue-inferred-border`** — Queue Inferred Border · default —
- src/styles/rooms.js (border-color)
- src/styles/theme-preview.js (border-color)

**`--evcc-queue-inferred-glow`** — Queue Inferred Glow · default —
- src/styles/rooms.js (box-shadow)
- src/styles/theme-preview.js (box-shadow)

**`--evcc-queue-inferred-text`** — Queue Inferred Text · default —
- src/styles/rooms.js (color)
- src/styles/theme-preview.js (color)

**`--evcc-queue-order-bg`** — Queue Order BG · default —
- src/styles/rooms.js (background)
- src/styles/theme-preview.js

**`--evcc-queue-order-border`** — Queue Order Border · default —
- src/styles/rooms.js
- src/styles/theme-preview.js

**`--evcc-queue-order-text`** — Queue Order Text · default —
- src/styles/rooms.js (color)
- src/styles/theme-preview.js

**`--evcc-queue-pending-bg`** — Queue Pending BG · default —
- src/styles/rooms.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-queue-pending-border`** — Queue Pending Border · default —
- src/styles/rooms.js (border-color)
- src/styles/theme-preview.js (border-color)

**`--evcc-queue-pending-opacity`** — Queue Pending Opacity · default —
- src/styles/rooms.js (opacity)
- src/styles/theme-preview.js (opacity)

**`--evcc-queue-pending-text`** — Queue Pending Text · default —
- src/styles/rooms.js (color)
- src/styles/theme-preview.js (color)

**`--evcc-queue-skipped-bg`** — Queue Skipped BG · default —
- src/styles/rooms.js (background)

**`--evcc-queue-skipped-border`** — Queue Skipped Border · default —
- src/styles/rooms.js (border-color)

**`--evcc-queue-skipped-text`** — Queue Skipped Text · default —
- src/styles/rooms.js (color)

**`--evcc-reorder-feedback-duration`** — Reorder Feedback Duration · default —
- src/styles/order.js

**`--evcc-reorder-flip-easing`** — Reorder Flip Easing · default —
- src/styles/order.js

## Status, Confidence & Alerts  ·  31 static / 31

**`--evcc-color-cleaning`** — Color Cleaning · default `var(--evcc-sem-success)` src/styles/foundation.js
- src/styles/theme-preview.js

**`--evcc-color-docked`** — Color Docked · default `var(--evcc-accent)` src/styles/foundation.js
- src/styles/theme-preview.js

**`--evcc-color-error`** — Color Error · default `var(--evcc-sem-error)` src/styles/foundation.js
- src/styles/theme-preview.js

**`--evcc-color-idle`** — Color Idle · default `var(--evcc-text-secondary)` src/styles/foundation.js
- src/styles/theme-preview.js

**`--evcc-confidence-high-bg`** — Confidence High BG · default `color-mix(in srgb, var(--evcc-sem-success) 18%, transparent)` src/styles/learning.js
- src/styles/rooms.js
- src/styles/theme-preview.js (background)

**`--evcc-confidence-high-border`** — Confidence High Border · default `color-mix(in srgb, var(--evcc-sem-success) 40%, transparent)` src/styles/learning.js
- src/styles/rooms.js
- src/styles/theme-preview.js (border-color)

**`--evcc-confidence-high-text`** — Confidence High Text · default `var(--evcc-sem-success)` src/styles/learning.js
- src/styles/theme-preview.js (color)

**`--evcc-confidence-low-bg`** — Confidence Low BG · default `color-mix(in srgb, var(--evcc-sem-error) 18%, transparent)` src/styles/learning.js
- src/styles/rooms.js
- src/styles/theme-preview.js (background)

**`--evcc-confidence-low-border`** — Confidence Low Border · default `color-mix(in srgb, var(--evcc-sem-error) 40%, transparent)` src/styles/learning.js
- src/styles/rooms.js
- src/styles/theme-preview.js (border-color)

**`--evcc-confidence-low-text`** — Confidence Low Text · default `var(--evcc-sem-error)` src/styles/learning.js
- src/styles/theme-preview.js (color)

**`--evcc-confidence-medium-bg`** — Confidence Medium BG · default `color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent)` src/styles/learning.js
- src/styles/rooms.js
- src/styles/theme-preview.js (background)

**`--evcc-confidence-medium-border`** — Confidence Medium Border · default `color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent)` src/styles/learning.js
- src/styles/rooms.js
- src/styles/theme-preview.js (border-color)

**`--evcc-confidence-medium-text`** — Confidence Medium Text · default `var(--evcc-sem-warning)` src/styles/learning.js
- src/styles/theme-preview.js (color)

**`--evcc-sem-error`** — Sem Error · default `var(--error-color, #e05252)` src/styles/foundation.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/cards/dashboard-card.js
- src/cards/dashboard-card.js (color)
- src/styles/external-jobs.js
- src/styles/external-jobs.js (color)
- src/styles/foundation.js (--evcc-color-error)
- src/styles/learning.js
- src/styles/learning.js (--evcc-learning-confidence-low-text)
- src/styles/learning.js (--evcc-confidence-low-text)
- src/styles/learning.js (color)
- src/styles/maintenance.js
- src/styles/map.js
- src/styles/map.js (color)
- src/styles/map.js (background)
- src/styles/map.js (border-color)
- src/styles/mobile.js (color)
- src/styles/modal-host.js (color)
- src/styles/review.js
- src/styles/review.js (color)
- src/styles/room-rules.js
- src/styles/room-rules.js (color)
- src/styles/room-rules.js (border-color)
- src/styles/rooms.js
- src/styles/rooms.js (color)
- src/styles/run-profiles.js (color)
- src/styles/saved-zones.js (color)
- src/styles/setup.js
- src/styles/setup.js (color)
- src/styles/setup.js (background)
- src/styles/setup.js (border-color)
- src/styles/shell.js
- src/styles/shell.js (color)
- src/styles/theme-preview.js
- src/styles/theme-preview.js (color)
- src/styles/theme.js (color)
- src/styles/toast-host.js

**`--evcc-sem-info`** — Sem Info · default `#4a9fe0` src/styles/foundation.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/external-jobs.js
- src/styles/job-summary.js
- src/styles/room-access.js
- src/styles/setup.js
- src/styles/setup.js (color)
- src/styles/theme-preview.js
- src/styles/theme-preview.js (color)

**`--evcc-sem-success`** — Sem Success · default `var(--success-color, #4caf6e)` src/styles/foundation.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/cards/dashboard-card.js (--status-success-line)
- src/styles/base-station.js
- src/styles/foundation.js (--evcc-color-cleaning)
- src/styles/learning.js
- src/styles/learning.js (--evcc-learning-confidence-high-text)
- src/styles/learning.js (--evcc-confidence-high-text)
- src/styles/learning.js (accent-color)
- src/styles/maintenance.js
- src/styles/map.js (color)
- src/styles/map.js
- src/styles/modal-host.js
- src/styles/rooms.js
- src/styles/rooms.js (--evcc-chip-active-text)
- src/styles/rooms.js (color)
- src/styles/run-profiles.js
- src/styles/setup.js (background)
- src/styles/setup.js
- src/styles/setup.js (color)
- src/styles/shell.js
- src/styles/theme.js (color)
- src/styles/theme.js
- src/styles/toast-host.js

**`--evcc-sem-warning`** — Sem Warning · default `var(--warning-color, #f5a623)` src/styles/foundation.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/cards/dashboard-card.js (--status-warning-line)
- src/styles/external-jobs.js
- src/styles/external-jobs.js (color)
- src/styles/job-summary.js (color)
- src/styles/learning.js
- src/styles/learning.js (--evcc-learning-confidence-medium-text)
- src/styles/learning.js (--evcc-confidence-medium-text)
- src/styles/learning.js (color)
- src/styles/maintenance.js
- src/styles/maintenance.js (color)
- src/styles/map.js
- src/styles/metrics.js
- src/styles/metrics.js (color)
- src/styles/mobile.js (color)
- src/styles/modal-host.js
- src/styles/modals.js (color)
- src/styles/modals.js
- src/styles/review.js (color)
- src/styles/review.js
- src/styles/room-access.js
- src/styles/room-access.js (color)
- src/styles/rooms.js
- src/styles/rooms.js (color)
- src/styles/rooms.js (--evcc-chip-active-text)
- src/styles/rooms.js (--evcc-learning-warning-text)
- src/styles/run-profiles.js
- src/styles/run-profiles.js (color)
- src/styles/setup.js
- src/styles/setup.js (color)
- src/styles/shell.js
- src/styles/shell.js (color)
- src/styles/theme-preview.js

**`--evcc-status-cleaning-bg`** — Status Cleaning BG · default —
- src/styles/rooms.js (background)

**`--evcc-status-cleaning-border`** — Status Cleaning Border · default —
- src/styles/rooms.js

**`--evcc-status-cleaning-text`** — Status Cleaning Text · default —
- src/styles/rooms.js (color)

**`--evcc-status-dot-charging`** — Status Dot Charging · default —
- src/styles/shell.js (background)

**`--evcc-status-dot-cleaning`** — Status Dot Cleaning · default —
- src/styles/rooms.js (background)
- src/styles/rooms.js
- src/styles/shell.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-status-dot-docked`** — Status Dot Docked · default —
- src/styles/shell.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-status-dot-error`** — Status Dot Error · default —
- src/styles/shell.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-status-dot-idle`** — Status Dot Idle · default —
- src/styles/shell.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-status-dot-offline`** — Status Dot Offline · default —
- src/styles/shell.js (background)

**`--evcc-status-dot-paused`** — Status Dot Paused · default —
- src/styles/shell.js (background)

**`--evcc-status-dot-returning`** — Status Dot Returning · default —
- src/styles/shell.js (background)

**`--evcc-status-dot-shadow`** — Status Dot Shadow · default —
- src/styles/shell.js (box-shadow)
- src/styles/theme-preview.js (box-shadow)

**`--evcc-status-dot-unavailable`** — Status Dot Unavailable · default —
- src/styles/shell.js (background)

**`--evcc-status-pulse-duration`** — Status Pulse Duration · default —
- src/styles/rooms.js
- src/styles/theme-preview.js

## Learning & Metrics  ·  37 static / 37

**`--evcc-estimate-default-bg`** — Estimate Default BG · default `color-mix(in srgb, var(--evcc-text-muted) 12%, transparent)` src/styles/rooms.js
- src/styles/rooms.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-estimate-default-border`** — Estimate Default Border · default `var(--evcc-border-default)` src/styles/rooms.js
- src/styles/rooms.js (border-color)
- src/styles/theme-preview.js (border-color)

**`--evcc-estimate-default-text`** — Estimate Default Text · default `var(--evcc-text-secondary)` src/styles/rooms.js
- src/styles/rooms.js (color)
- src/styles/theme-preview.js (color)

**`--evcc-estimate-learned-bg`** — Estimate Learned BG · default `color-mix(in srgb, var(--evcc-accent) 14%, transparent)` src/styles/rooms.js
- src/styles/rooms.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-estimate-learned-border`** — Estimate Learned Border · default `color-mix(in srgb, var(--evcc-accent) 30%, transparent)` src/styles/rooms.js
- src/styles/rooms.js (border-color)
- src/styles/theme-preview.js (border-color)

**`--evcc-estimate-learned-text`** — Estimate Learned Text · default `var(--evcc-text-primary)` src/styles/rooms.js
- src/styles/rooms.js (color)
- src/styles/theme-preview.js (color)

**`--evcc-learning-anim-duration-fast`** — Learning Anim Duration Fast · default `180ms` src/styles/learning.js
- src/styles/learning.js

**`--evcc-learning-anim-duration-normal`** — Learning Anim Duration Normal · default `260ms` src/styles/learning.js
- src/styles/learning.js

**`--evcc-learning-anim-duration-slow`** — Learning Anim Duration Slow · default `520ms` src/styles/learning.js
- src/styles/learning.js

**`--evcc-learning-anim-ease`** — Learning Anim Ease · default `cubic-bezier(0.22, 1, 0.36, 1)` src/styles/learning.js
- src/styles/learning.js

**`--evcc-learning-chip-font-size`** — Learning Chip Font Size · default `0.74rem` src/styles/learning.js
- src/styles/learning.js (font-size)

**`--evcc-learning-chip-font-weight`** — Learning Chip Font Weight · default `700` src/styles/learning.js
- src/styles/learning.js (font-weight)

**`--evcc-learning-chip-radius`** — Learning Chip Radius · default `var(--evcc-radius-chip, 999px)` src/styles/learning.js
- src/styles/learning.js (border-radius)

**`--evcc-learning-confidence-high-bg`** — Learning Confidence High BG · default `color-mix(in srgb, var(--evcc-sem-success) 18%, transparent)` src/styles/learning.js
- src/styles/theme-preview.js

**`--evcc-learning-confidence-high-border`** — Learning Confidence High Border · default `color-mix(in srgb, var(--evcc-sem-success) 42%, transparent)` src/styles/learning.js
- src/styles/learning.js (border-color)
- src/styles/theme-preview.js

**`--evcc-learning-confidence-high-gradient`** — Learning Confidence High Gradient · default `linear-gradient( 135deg, color-mix(in srgb, var(--evcc-sem-success) 26%, transparent), color-mix(in srgb, var(--evcc-sem-success) 10%, transparent) )` src/styles/learning.js
- src/styles/learning.js (background)

**`--evcc-learning-confidence-high-text`** — Learning Confidence High Text · default `var(--evcc-sem-success)` src/styles/learning.js
- src/styles/learning.js (color)
- src/styles/theme-preview.js

**`--evcc-learning-confidence-low-border`** — Learning Confidence Low Border · default `color-mix(in srgb, var(--evcc-sem-error) 42%, transparent)` src/styles/learning.js
- src/styles/learning.js (border-color)

**`--evcc-learning-confidence-low-gradient`** — Learning Confidence Low Gradient · default `linear-gradient( 135deg, color-mix(in srgb, var(--evcc-sem-error) 26%, transparent), color-mix(in srgb, var(--evcc-sem-error) 10%, transparent) )` src/styles/learning.js
- src/styles/learning.js (background)

**`--evcc-learning-confidence-low-text`** — Learning Confidence Low Text · default `var(--evcc-sem-error)` src/styles/learning.js
- src/styles/learning.js (color)

**`--evcc-learning-confidence-medium-bg`** — Learning Confidence Medium BG · default `color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent)` src/styles/learning.js
- src/styles/theme-preview.js

**`--evcc-learning-confidence-medium-border`** — Learning Confidence Medium Border · default `color-mix(in srgb, var(--evcc-sem-warning) 42%, transparent)` src/styles/learning.js
- src/styles/learning.js (border-color)
- src/styles/theme-preview.js

**`--evcc-learning-confidence-medium-gradient`** — Learning Confidence Medium Gradient · default `linear-gradient( 135deg, color-mix(in srgb, var(--evcc-sem-warning) 26%, transparent), color-mix(in srgb, var(--evcc-sem-warning) 10%, transparent) )` src/styles/learning.js
- src/styles/learning.js (background)

**`--evcc-learning-confidence-medium-text`** — Learning Confidence Medium Text · default `var(--evcc-sem-warning)` src/styles/learning.js
- src/styles/learning.js (color)
- src/styles/theme-preview.js

**`--evcc-learning-confidence-neutral-border`** — Learning Confidence Neutral Border · default `var(--evcc-border-default)` src/styles/learning.js
- src/styles/learning.js
- src/styles/learning.js (border-color)

**`--evcc-learning-confidence-neutral-gradient`** — Learning Confidence Neutral Gradient · default `linear-gradient( 135deg, color-mix(in srgb, var(--evcc-text-muted) 16%, transparent), color-mix(in srgb, var(--evcc-text-muted) 8%, transparent) )` src/styles/learning.js
- src/styles/learning.js (background)

**`--evcc-learning-confidence-neutral-text`** — Learning Confidence Neutral Text · default `var(--evcc-text-secondary)` src/styles/learning.js
- src/styles/learning.js (color)

**`--evcc-learning-note-text`** — Learning Note Text · default `var(--evcc-text-muted)` src/styles/rooms.js
- src/styles/rooms.js (color)
- src/styles/theme-preview.js (color)

**`--evcc-learning-panel-bg`** — Learning Panel BG · default `var(--evcc-surface-panel)` src/styles/learning.js
- src/styles/learning.js (background)
- src/styles/theme-preview.js

**`--evcc-learning-panel-border`** — Learning Panel Border · default `var(--evcc-border-default)` src/styles/learning.js
- src/styles/learning.js
- src/styles/theme-preview.js (border-color)

**`--evcc-learning-panel-shadow`** — Learning Panel Shadow · default `var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14))` src/styles/learning.js
- src/styles/learning.js
- src/styles/learning.js (box-shadow)
- src/styles/theme-preview.js (box-shadow)

**`--evcc-learning-reanchor-border`** — Learning Reanchor Border · default `color-mix(in srgb, var(--evcc-accent) 34%, transparent)` src/styles/learning.js
- src/styles/learning.js (border-color)

**`--evcc-learning-reanchor-highlight`** — Learning Reanchor Highlight · default `color-mix(in srgb, var(--evcc-accent) 16%, transparent)` src/styles/learning.js
- src/styles/theme-preview.js

**`--evcc-learning-text-muted`** — Learning Text Muted · default `var(--evcc-text-muted)` src/styles/learning.js
- src/styles/learning.js (color)

**`--evcc-learning-text-primary`** — Learning Text Primary · default `var(--evcc-text-primary)` src/styles/learning.js
- src/styles/learning.js (color)

**`--evcc-learning-text-secondary`** — Learning Text Secondary · default `var(--evcc-text-secondary)` src/styles/learning.js
- src/styles/learning.js (color)
- src/styles/theme-preview.js

**`--evcc-learning-warning-text`** — Learning Warning Text · default `var(--evcc-sem-warning)` src/styles/rooms.js
- src/styles/rooms.js (color)

## Modals & Overlays  ·  36 static / 36

**`--evcc-modal-accent`** — Modal Accent · default src/styles/modal-host.js
- src/styles/dialog.js (border-color)
- src/styles/modal-host.js (--evcc-accent)
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/theme-preview.js

**`--evcc-modal-accent-bg`** — Modal Accent BG · default src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/modal-host.js (--evcc-modal-chip-active-bg)
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/theme-preview.js (background)

**`--evcc-modal-accent-border`** — Modal Accent Border · default src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/modal-host.js (--evcc-modal-chip-active-border)
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/theme-preview.js (border-color)

**`--evcc-modal-accent-text`** — Modal Accent Text · default src/styles/modal-host.js
- custom_components/eufy_vacuum/themes/preloaded.py
- src/styles/modal-host.js (--evcc-modal-chip-active-text)
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/theme-preview.js (color)

**`--evcc-modal-backdrop-bg`** — Modal Backdrop BG · default src/styles/modal-host.js
- src/styles/modal-host.js (background)
- src/styles/modals.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-modal-backdrop-blur`** — Modal Backdrop Blur · default —
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/theme-preview.js

**`--evcc-modal-bg`** — Modal BG · default src/styles/modal-host.js
- src/styles/modal-host.js (background)
- src/styles/modals.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-modal-border`** — Modal Border · default src/styles/modal-host.js
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/theme-preview.js

**`--evcc-modal-border-default`** — Modal Border Default · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-border-default)

**`--evcc-modal-border-strong`** — Modal Border Strong · default src/styles/modal-host.js
- src/styles/dialog.js
- src/styles/modal-host.js (--evcc-border-strong)
- src/styles/modals.js

**`--evcc-modal-border-subtle`** — Modal Border Subtle · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-border-subtle)
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/room-estimate.js

**`--evcc-modal-chip-active-bg`** — Modal Chip Active BG · default src/styles/modal-host.js
- src/styles/modal-host.js (background)
- src/styles/modals.js (background)

**`--evcc-modal-chip-active-border`** — Modal Chip Active Border · default src/styles/modal-host.js
- src/styles/modal-host.js (border-color)
- src/styles/modals.js (border-color)

**`--evcc-modal-chip-active-text`** — Modal Chip Active Text · default src/styles/modal-host.js
- src/styles/modal-host.js (color)
- src/styles/modals.js (color)

**`--evcc-modal-chip-bg`** — Modal Chip BG · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-chip-bg)
- src/styles/modal-host.js (background)
- src/styles/modals.js (background)

**`--evcc-modal-chip-border`** — Modal Chip Border · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-chip-border)
- src/styles/modal-host.js
- src/styles/modal-host.js (border-color)
- src/styles/modals.js (border-color)

**`--evcc-modal-chip-hover-bg`** — Modal Chip Hover BG · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-chip-hover-bg)
- src/styles/modals.js (background)

**`--evcc-modal-chip-hover-border`** — Modal Chip Hover Border · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-chip-hover-border)
- src/styles/modals.js (border-color)

**`--evcc-modal-chip-hover-text`** — Modal Chip Hover Text · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-chip-hover-text)
- src/styles/modals.js (color)

**`--evcc-modal-chip-text`** — Modal Chip Text · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-chip-text)
- src/styles/modal-host.js (color)
- src/styles/modals.js (color)

**`--evcc-modal-footer-bg`** — Modal Footer BG · default src/styles/modal-host.js
- src/styles/modal-host.js (background)
- src/styles/modals.js (background)

**`--evcc-modal-header-bg`** — Modal Header BG · default src/styles/modal-host.js
- src/styles/modal-host.js (background)
- src/styles/modals.js (background)

**`--evcc-modal-input-bg`** — Modal Input BG · default src/styles/modal-host.js
- src/styles/dialog.js (background)
- src/styles/modal-host.js (--evcc-surface-input)

**`--evcc-modal-padding`** — Modal Padding · default —
- src/styles/modal-host.js (padding)
- src/styles/modals.js (padding)
- src/styles/theme-preview.js (padding)

**`--evcc-modal-radius`** — Modal Radius · default —
- src/styles/modal-host.js (border-radius)
- src/styles/modals.js (border-radius)
- src/styles/theme-preview.js (border-radius)

**`--evcc-modal-section-gap`** — Modal Section Gap · default —
- src/styles/modal-host.js (gap)
- src/styles/modals.js (gap)

**`--evcc-modal-shadow`** — Modal Shadow · default —
- src/styles/modal-host.js (box-shadow)
- src/styles/modals.js (box-shadow)
- src/styles/theme-preview.js (box-shadow)

**`--evcc-modal-surface-input`** — Modal Surface Input · default src/styles/modal-host.js
- src/styles/modal-host.js

**`--evcc-modal-surface-panel`** — Modal Surface Panel · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-surface-panel)
- src/styles/room-estimate.js

**`--evcc-modal-surface-section`** — Modal Surface Section · default src/styles/modal-host.js
- src/styles/modals.js (background)

**`--evcc-modal-text-muted`** — Modal Text Muted · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-text-muted)
- src/styles/modal-host.js (color)
- src/styles/modal-host.js
- src/styles/modals.js (color)
- src/styles/modals.js

**`--evcc-modal-text-primary`** — Modal Text Primary · default src/styles/modal-host.js
- src/styles/dialog.js (color)
- src/styles/modal-host.js (color)
- src/styles/modal-host.js (--evcc-text-primary)
- src/styles/modal-host.js
- src/styles/modals.js (color)
- src/styles/room-estimate.js (color)

**`--evcc-modal-text-secondary`** — Modal Text Secondary · default src/styles/modal-host.js
- src/styles/modal-host.js (--evcc-text-secondary)
- src/styles/modal-host.js (color)
- src/styles/modals.js
- src/styles/room-estimate.js (color)

**`--evcc-modal-warning-bg`** — Modal Warning BG · default src/styles/modal-host.js
- src/styles/modal-host.js (background)
- src/styles/modals.js (background)
- src/styles/theme-preview.js (background)

**`--evcc-modal-warning-border`** — Modal Warning Border · default src/styles/modal-host.js
- src/styles/modal-host.js
- src/styles/modals.js
- src/styles/theme-preview.js (border-color)

**`--evcc-modal-warning-text`** — Modal Warning Text · default src/styles/modal-host.js
- src/styles/modal-host.js
- src/styles/modal-host.js (color)
- src/styles/modals.js
- src/styles/modals.js (color)
- src/styles/theme-preview.js (color)

## Animal Companion  ·  0 static + 14 dynamic / 14

**`--evcc-animal-eye-good`** — Eye — Good (>50% battery) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye-mid`** — Eye — Mid (25–50%) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye-warn`** — Eye — Warn (15–25%) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye-low`** — Eye — Low (≤15%) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye-charging`** — Eye — Charging (pulses) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-fur`** — Fur (all animals) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-fur-shadow`** — Fur Shadow (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-fur-highlight`** — Fur Highlight (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye`** — Eye Base (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-pupil`** — Pupil (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-nose`** — Nose (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-whisker`** — Whisker (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-ear-inner`** — Ear Inner (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-white-tip`** — White Tip / Accent (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

## Animal Companion — Cat  ·  0 static + 14 dynamic / 14

*(template — Dog/Raccoon/Parrot/Snake mirror it; consumed dynamically in animal-svg/)*

**`--evcc-animal-cat-eye-good`** — Eye — Good · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye-mid`** — Eye — Mid · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye-warn`** — Eye — Warn · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye-low`** — Eye — Low · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye-charging`** — Eye — Charging · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-fur`** — Fur · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-fur-shadow`** — Fur Shadow · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-fur-highlight`** — Fur Highlight · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye`** — Eye Base · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-pupil`** — Pupil · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-nose`** — Nose · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-whisker`** — Whisker · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-ear-inner`** — Ear Inner · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-white-tip`** — White Tip / Accent · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

## Shared Foundations  ·  15 static / 15

**`--evcc-font-family`** — Font Family · default —
- src/styles/modal-host.js
- src/styles/shell.js
- src/styles/theme-preview.js
- src/styles/toast-host.js

**`--evcc-gap`** — Gap · default `var(--evcc-space-md)` src/styles/foundation.js
- src/styles/foundation.js (gap)
- src/styles/shell.js (gap)
- src/styles/theme-preview.js (gap)

**`--evcc-grid-gap`** — Grid Gap · default `12px` src/styles/layout.js
- src/styles/base-station.js (gap)
- src/styles/layout.js (--evcc-room-grid-gap)
- src/styles/layout.js
- src/styles/maintenance.js (gap)
- src/styles/metrics.js (gap)
- src/styles/review.js (gap)

**`--evcc-hover-lift`** — Hover Lift · default —
- src/styles/order.js
- src/styles/rooms.js
- src/styles/theme-preview.js

**`--evcc-pad`** — Pad · default `var(--evcc-space-lg)` src/styles/foundation.js
- src/styles/foundation.js (padding)
- src/styles/foundation.js
- src/styles/theme-preview.js (padding)

**`--evcc-press-scale`** — Press Scale · default —
- src/styles/rooms.js

**`--evcc-radius-card`** — Radius Card · default `var(--ha-card-border-radius, 12px)` src/styles/foundation.js
- src/cards/dashboard-card.js (--radius)
- src/cards/profile-card.js (--radius)
- src/room-card.js (--radius)
- src/styles/external-jobs.js (border-radius)
- src/styles/learning.js (border-radius)
- src/styles/map.js (border-radius)
- src/styles/rooms.js (border-radius)
- src/styles/shell.js (border-radius)
- src/styles/theme-preview.js (border-radius)
- src/styles/theme.js (border-radius)

**`--evcc-radius-chip`** — Radius Chip · default `999px` src/styles/foundation.js
- src/styles/external-jobs.js (border-radius)
- src/styles/foundation.js (border-radius)
- src/styles/learning.js (--evcc-learning-chip-radius)
- src/styles/order.js (border-radius)
- src/styles/rooms.js (border-radius)
- src/styles/shell.js (border-radius)
- src/styles/theme-preview.js (border-radius)

**`--evcc-radius-inner`** — Radius Inner · default `8px` src/styles/foundation.js
- src/cards/dashboard-card.js (border-radius)
- src/styles/base-station.js (border-radius)
- src/styles/external-jobs.js (border-radius)
- src/styles/job-summary.js (border-radius)
- src/styles/maintenance.js (border-radius)
- src/styles/metrics.js (border-radius)
- src/styles/modal-host.js (border-radius)
- src/styles/review.js (border-radius)
- src/styles/rooms.js (border-radius)
- src/styles/run-profiles.js (border-radius)
- src/styles/saved-zones.js (border-radius)
- src/styles/theme-preview.js (border-radius)
- src/styles/theme.js (border-radius)

**`--evcc-radius-panel`** — Radius Panel · default —
- src/styles/learning.js (border-radius)
- src/styles/room-access.js (border-radius)
- src/styles/rooms.js (border-radius)
- src/styles/run-profiles.js (border-radius)
- src/styles/saved-zones.js (border-radius)
- src/styles/theme-preview.js (border-radius)

**`--evcc-section-gap`** — Section Gap · default —
- src/styles/rooms.js (gap)
- src/styles/theme-preview.js (gap)

**`--evcc-space-lg`** — Space Lg · default `16px` src/styles/foundation.js
- src/styles/foundation.js (--evcc-pad)
- src/styles/shell.js (padding)

**`--evcc-space-md`** — Space Md · default `12px` src/styles/foundation.js
- src/styles/foundation.js (--evcc-gap)
- src/styles/rooms.js (padding-bottom)
- src/styles/rooms.js (margin-bottom)
- src/styles/rooms.js (gap)
- src/styles/theme.js (gap)

**`--evcc-space-sm`** — Space Sm · default `8px` src/styles/foundation.js
- src/styles/rooms.js (margin-top)
- src/styles/rooms.js (gap)

**`--evcc-transition-normal`** — Transition Normal · default `150ms ease` src/styles/foundation.js, src/styles/modal-host.js
- src/styles/base-station.js
- src/styles/foundation.js
- src/styles/maintenance.js
- src/styles/order.js
- src/styles/room-access.js
- src/styles/rooms.js
- src/styles/shell.js
- src/styles/theme.js (transition)

---

## Tokens with no STATIC consumer  ·  134

**134 of these are consumed DYNAMICALLY and are not dead** — this tracer is a regex scan and cannot follow a `var()` whose name is built at runtime. Only the final section is a concern.

### Consumed dynamically — animal  ·  84

`src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`. Working as intended.

`--evcc-animal-eye-good`, `--evcc-animal-eye-mid`, `--evcc-animal-eye-warn`, `--evcc-animal-eye-low`, `--evcc-animal-eye-charging`, `--evcc-animal-fur`, `--evcc-animal-fur-shadow`, `--evcc-animal-fur-highlight`, `--evcc-animal-eye`, `--evcc-animal-pupil`, `--evcc-animal-nose`, `--evcc-animal-whisker`, `--evcc-animal-ear-inner`, `--evcc-animal-white-tip`, `--evcc-animal-cat-eye-good`, `--evcc-animal-cat-eye-mid`, `--evcc-animal-cat-eye-warn`, `--evcc-animal-cat-eye-low`, `--evcc-animal-cat-eye-charging`, `--evcc-animal-cat-fur`, `--evcc-animal-cat-fur-shadow`, `--evcc-animal-cat-fur-highlight`, `--evcc-animal-cat-eye`, `--evcc-animal-cat-pupil`, `--evcc-animal-cat-nose`, `--evcc-animal-cat-whisker`, `--evcc-animal-cat-ear-inner`, `--evcc-animal-cat-white-tip`, `--evcc-animal-dog-eye-good`, `--evcc-animal-dog-eye-mid`, `--evcc-animal-dog-eye-warn`, `--evcc-animal-dog-eye-low`, `--evcc-animal-dog-eye-charging`, `--evcc-animal-dog-fur`, `--evcc-animal-dog-fur-shadow`, `--evcc-animal-dog-fur-highlight`, `--evcc-animal-dog-eye`, `--evcc-animal-dog-pupil`, `--evcc-animal-dog-nose`, `--evcc-animal-dog-whisker`, `--evcc-animal-dog-ear-inner`, `--evcc-animal-dog-white-tip`, `--evcc-animal-raccoon-eye-good`, `--evcc-animal-raccoon-eye-mid`, `--evcc-animal-raccoon-eye-warn`, `--evcc-animal-raccoon-eye-low`, `--evcc-animal-raccoon-eye-charging`, `--evcc-animal-raccoon-fur`, `--evcc-animal-raccoon-fur-shadow`, `--evcc-animal-raccoon-fur-highlight`, `--evcc-animal-raccoon-eye`, `--evcc-animal-raccoon-pupil`, `--evcc-animal-raccoon-nose`, `--evcc-animal-raccoon-whisker`, `--evcc-animal-raccoon-ear-inner`, `--evcc-animal-raccoon-white-tip`, `--evcc-animal-parrot-eye-good`, `--evcc-animal-parrot-eye-mid`, `--evcc-animal-parrot-eye-warn`, `--evcc-animal-parrot-eye-low`, `--evcc-animal-parrot-eye-charging`, `--evcc-animal-parrot-fur`, `--evcc-animal-parrot-fur-shadow`, `--evcc-animal-parrot-fur-highlight`, `--evcc-animal-parrot-eye`, `--evcc-animal-parrot-pupil`, `--evcc-animal-parrot-nose`, `--evcc-animal-parrot-whisker`, `--evcc-animal-parrot-ear-inner`, `--evcc-animal-parrot-white-tip`, `--evcc-animal-snake-eye-good`, `--evcc-animal-snake-eye-mid`, `--evcc-animal-snake-eye-warn`, `--evcc-animal-snake-eye-low`, `--evcc-animal-snake-eye-charging`, `--evcc-animal-snake-fur`, `--evcc-animal-snake-fur-shadow`, `--evcc-animal-snake-fur-highlight`, `--evcc-animal-snake-eye`, `--evcc-animal-snake-pupil`, `--evcc-animal-snake-nose`, `--evcc-animal-snake-whisker`, `--evcc-animal-snake-ear-inner`, `--evcc-animal-snake-white-tip`

### Consumed dynamically — floor-material  ·  38

`src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key. Working as intended.

`--evcc-floor-tile-base`, `--evcc-floor-tile-grout`, `--evcc-floor-tile-accent`, `--evcc-floor-tile-opacity-card`, `--evcc-floor-tile-face-opacity`, `--evcc-floor-tile-grout-opacity`, `--evcc-floor-tile-line-opacity`, `--evcc-floor-wood-base`, `--evcc-floor-wood-accent`, `--evcc-floor-wood-opacity-card`, `--evcc-floor-wood-depth-opacity`, `--evcc-floor-wood-grain-opacity`, `--evcc-floor-wood-seam-opacity`, `--evcc-floor-marble-base`, `--evcc-floor-marble-micro`, `--evcc-floor-marble-opacity-card`, `--evcc-floor-marble-base-opacity`, `--evcc-floor-marble-micro-opacity`, `--evcc-floor-concrete-base`, `--evcc-floor-concrete-accent`, `--evcc-floor-concrete-opacity-card`, `--evcc-floor-concrete-broad-opacity`, `--evcc-floor-concrete-micro-opacity`, `--evcc-floor-carpet-low-base`, `--evcc-floor-carpet-low-weave`, `--evcc-floor-carpet-low-opacity-card`, `--evcc-floor-carpet-low-base-opacity`, `--evcc-floor-carpet-low-weave-opacity`, `--evcc-floor-carpet-high-base`, `--evcc-floor-carpet-high-weave`, `--evcc-floor-carpet-high-opacity-card`, `--evcc-floor-carpet-high-base-opacity`, `--evcc-floor-carpet-high-weave-opacity`, `--evcc-floor-granite-light-base`, `--evcc-floor-granite-light-aggregate`, `--evcc-floor-granite-light-opacity-card`, `--evcc-floor-granite-light-base-opacity`, `--evcc-floor-granite-light-aggregate-opacity`

### Consumed dynamically — room-fill  ·  12

`src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7). Working as intended.

`--evcc-room-fill-1`, `--evcc-room-fill-2`, `--evcc-room-fill-3`, `--evcc-room-fill-4`, `--evcc-room-fill-5`, `--evcc-room-fill-6`, `--evcc-room-fill-7`, `--evcc-room-fill-8`, `--evcc-room-fill-9`, `--evcc-room-fill-10`, `--evcc-room-fill-11`, `--evcc-room-fill-12`

### No consumer anywhere  ·  0

Seeded + exposed in the editor but nothing reads them — no-op editor knobs (wire them up or drop them). THIS is the list a cleanup pass should act on, not the count above.

None — every catalog token is consumed, statically or dynamically.

---

## var() → non-catalog tokens  ·  12

Used in CSS but not in the editor registry (dynamic fragments or intentional internals like `--evcc-grp`).

- `--evcc-animal-X` — custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js
- `--evcc-panel-offset` — src/styles/foundation.js
- `--evcc-space-xs` — src/styles/learning.js
- `--evcc-map-rotation` — src/styles/map.js
- `--evcc-mascot-flip` — src/styles/map.js
- `--evcc-map-ov-savedzone` — src/styles/map.js
- `--evcc-map-ov-savedzone-text` — src/styles/map.js
- `--evcc-grp` — src/styles/map.js
- `--evcc-a11y-font-family` — src/styles/modal-host.js, src/styles/shell.js, src/styles/theme-preview.js, src/styles/toast-host.js
- `--evcc-surface-hover` — src/styles/rooms.js
- `--evcc-sheen-dir` — src/styles/rooms.js
- `--evcc-font-preview` — src/styles/theme.js

---

## dynamic var(--evcc-…${…}) sites  ·  3

- custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js
- src/renderers/floor-texture-surface.js

