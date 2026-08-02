// CARD-6 clause 2 (Q12): whether the dashboard card's zone-repeat control
// (the 1x/2x chips) should render. Pure + DOM-free so it unit-tests with
// `node --test`, same reasoning as dashboard-dispatch.js and zone-geometry.js —
// dashboard-card.js extends HTMLElement and isn't importable under plain
// `node --test`, so the DECISION lives here and the component just calls it.
//
// Capability-DECLARED only, no brand-name checks (Q12's explicit wording).
// `supports_zone_repeat` does not exist in the dashboard snapshot yet — the
// backend capability this gates on lands with RP-021a/RP-022 (this packet's
// own blockers), which have not landed as of this fix. Until then this is
// unconditionally false for every brand, which is not a bug: Q12 decided
// "unsupported and UNSURFACED until verified", and an undeclared capability
// is exactly the unverified case. The seam is ready — once the backend adds
// the key, this starts returning true for brands that declare it, with no
// further frontend change needed.

/**
 * @param {object|null|undefined} snapshot - get_dashboard_snapshot payload.
 * @returns {boolean}
 */
export function canZoneRepeat(snapshot) {
  return snapshot?.supports_zone_repeat === true;
}
