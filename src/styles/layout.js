/**
 * ============================================================
 * STYLES: LAYOUT
 * ============================================================
 *
 * PURPOSE
 * -------
 * Shared layout primitives that can be reused across multiple
 * tabs/views, not just Rooms.
 *
 * This file owns:
 * - theme-aware content grids
 * - shared responsive layout helpers
 *
 *
 * WHAT THIS FILE SHOULD NOT CONTAIN
 * ----------------------------------
 * - room card styling
 * - modal styling
 * - shell/header/nav styling
 * - chip styling
 *
 *
 * THEME VARIABLES
 * ---------------
 * --evcc-grid-gap
 *   Shared default gap for feature grids.
 *
 * --evcc-room-grid-gap
 *   Room-grid-specific gap override.
 *
 * --evcc-room-grid-min
 *   Minimum room card width used by the auto-fit fallback.
 *
 * --evcc-room-grid-columns
 *   Explicit room grid template. When set, this overrides the
 *   auto-fit fallback completely.
 *
 *
 * GRID BEHAVIOR
 * -------------
 * The room grid uses this priority order:
 *
 * 1. Explicit theme-controlled columns:
 *      --evcc-room-grid-columns
 *
 * 2. Fallback responsive auto-fit:
 *      repeat(auto-fit, minmax(--evcc-room-grid-min, 1fr))
 *
 * This makes fixed 2/3/4 column layouts possible while still
 * keeping a responsive default when no theme override is set.
 *
 * ============================================================
 */

export const layoutStyles = `

  /* =========================================================
     SHARED GRID TOKENS
     ========================================================= */

  :host {
    --evcc-grid-gap:      12px;
    --evcc-room-grid-gap: var(--evcc-grid-gap);
    --evcc-room-grid-min: 240px;
  }

  /* =========================================================
     ROOM GRID
     =========================================================
     Reusable theme-aware grid primitive for the Rooms view.
     Future tabs can follow this same pattern with their own
     --evcc-<feature>-grid-* variables.
     ========================================================= */

  .evcc-room-grid {
    display: grid;
    gap: var(--evcc-room-grid-gap, var(--evcc-grid-gap, 12px));
    grid-template-columns: var(
      --evcc-room-grid-columns,
      repeat(auto-fit, minmax(var(--evcc-room-grid-min, 240px), 1fr))
    );
  }

  /* =========================================================
     RESPONSIVE SAFETY
     =========================================================
     On smaller screens, force a single column so cards never
     get too compressed even if a theme sets fixed columns.
     ========================================================= */

  @media (max-width: 720px) {
    .evcc-room-grid {
      grid-template-columns: 1fr;
    }
  }
`;