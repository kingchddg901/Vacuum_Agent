/**
 * ============================================================
 * THEME TOKENS: DASHBOARD CARDS
 * ============================================================
 *
 * PURPOSE
 * -------
 * The frame of the three cards a user adds to their own dashboard:
 * eufy-room-card, vacuum-agent-dashboard and vacuum-agent-profile-card.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * NOT the same surface as "Cards & Surfaces" or "Room Cards", both of
 * which style the PANEL. "Room Cards" controls `.evcc-room-card`, the
 * room TILE inside the panel's Rooms view (src/styles/rooms.js:381),
 * and `--evcc-card-padding` / `--evcc-card-gap` / `--evcc-card-min-height`
 * control that same tile. Those labels read as though they govern the
 * standalone cards and they never have. This group is the one that does.
 *
 * WHY ONLY TWO TOKENS
 * -------------------
 * Three of the five frame properties are ALREADY controllable and have
 * been all along -- background, border-radius and border-colour resolve
 * through --evcc-surface-card, --evcc-radius-card and
 * --evcc-border-default on all three cards. Only border-width and
 * box-shadow were hardcoded, which is why issue #83's reporter could
 * move some of the frame and not the rest, with nothing to distinguish
 * the two cases. These are the missing two, and nothing else.
 *
 * The frame does not need a padding token: only profile-card pads the
 * frame itself (the other two pad per section, because they have a
 * bordered footer that must meet a rounded corner), so one control
 * would move one card of three. That is a deliberate divergence, not a
 * replica -- see docs/dev/00c-replicas.md.
 *
 * RANGE IS DECLARED, NOT INHERITED
 * --------------------------------
 * --evcc-card-frame-border-width carries an EXPLICIT range. A `size`
 * token with no range falls back to the per-group SLIDER_CONFIG in
 * src/renderers/theme.js, or to {min:0,max:64,step:1} when the group is
 * absent from that table -- a 0-64px slider for a 1px border, where
 * every usable value sits in the first 3% of travel. 40 of the 77
 * scalar tokens currently inherit a bound that way.
 *
 * ============================================================
 */

import { makeTypedGroupToken } from "./helpers.js";

// anchor: RNA0TM68  the card FRAME -- the replica set.
// One rule ("how the outer edge of a user-added card is drawn") written out in three
// places, because each card frames itself differently and that divergence is real:
//   src/room-card.js            -- as --ha-card-* custom properties, because this card
//                                  frames with Home Assistant's <ha-card> element
//   src/cards/dashboard-card.js -- .card, a plain div
//   src/cards/profile-card.js   -- .evcc-pcard, a plain div
// The three cannot be unified without making two of them render an ha-card they do not
// want, so this is coordination, not extraction. Every token added here lands three
// times; a green suite cannot see a missing copy, which is the whole reason this
// register exists. Listed in docs/dev/00c-replicas.md.
export const DASHBOARD_CARD_GROUP = "Dashboard Cards";

const cardToken = makeTypedGroupToken(DASHBOARD_CARD_GROUP, "size");

export const DASHBOARD_CARD_TOKENS = [
  // A frame border is 0-8px in practice; 0 is a legitimate value and the
  // single most-requested one (#83). Half-pixel steps because HA themes in
  // the wild do use them.
  cardToken(
    "--evcc-card-frame-border-width",
    "Frame Border Width",
    "size",
    { min: 0, max: 8, step: 0.5 },
  ),

  // type "shadow" renders as a free-text input: there is no composite
  // shadow editor anywhere in the registry. Honest, and it accepts the
  // full CSS value including a comma-separated stack.
  cardToken.shadow(
    "--evcc-card-frame-shadow",
    "Frame Shadow",
  ),
];
