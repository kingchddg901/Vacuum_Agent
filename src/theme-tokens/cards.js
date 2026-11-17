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

  /* =========================================================
     DENSITY -- keyed by the card, inheriting from the panel
     =========================================================
     HIS RULING 2026-11-16: "key by the card it works on with inheritance
     setting from the panel". Each of these is read as a TWO-STEP chain:

         var(--evcc-card-<thing>, var(--evcc-<panel equivalent>, <literal>))

     so a card value wins; absent one the panel's own token carries down; and
     absent both, today's shipped pixel paints. That makes every one of them
     zero-delta at the default, because BOTH halves of the chain are undeclared
     -- the panel's density tokens have never been declared either, they are
     read as `var(--evcc-card-padding, 12px)` at styles/rooms.js:389.

     WHY NOT JUST REUSE THE PANEL'S TOKENS. Because they are not the same
     surface: --evcc-card-padding drives `.evcc-room-card`, the room TILE inside
     the panel's Rooms view, and one slider cannot mean both without moving two
     unrelated things at once. Reusing them is the mislabelling this group was
     created to end (see the header note). Inheriting from them is the opposite:
     it gives a user who themes the panel a card that follows, for free, and one
     who wants the card different a place to say so.

     TYPES. The three paddings are compound values (two and three parts), which
     cannot be a slider -- src/renderers/theme.js renders only single scalars as
     one -- so they are `lengths`: still a text box, but one that states it wants
     CSS lengths and coerces a bare number to px. They shipped as the generic
     `text`, whose box said only the word "Default", which is what issue #83 asked
     about. Field gap is a single length and gets a real
     slider with an explicit range, because this group's SLIDER_CONFIG net is
     {0,8,0.5} and a 6px gap sits inside it. */

  // room-card `.header` is `14px 16px 12px`; dashboard-card's is `14px 16px 10px`.
  // The 2px disagreement is real and unexplained; each site keeps its own literal
  // as the final fallback, so setting this token is what makes them agree.
  cardToken.lengths(
    "--evcc-card-header-padding",
    "Header Padding",
  ),

  // The room row's head. The one knob a user with a long room list asks for.
  cardToken.lengths(
    "--evcc-card-row-padding",
    "Row Padding",
  ),

  // The dashboard card's section inset -- its only breathing-room control.
  // NOT the frame padding: that was declined deliberately, because only the
  // profile card pads its frame, so one token would move one card of three.
  cardToken.lengths(
    "--evcc-card-section-padding",
    "Section Padding",
  ),

  // Label-to-control gap. 6px has no member on the 4/8/12/16 spacing scale, so
  // snapping it to --evcc-space-sm would be +2px in both cards.
  cardToken(
    "--evcc-card-field-gap",
    "Field Gap",
    "size",
    { min: 0, max: 16, step: 0.5 },
  ),

  // The accent halo on the profile card's Run button. No existing token fits:
  // --evcc-shadow-card and --evcc-shadow-hover are elevation and hover, and both
  // already carry depth-shadow literals everywhere they are read. Deliberately
  // NOT chained to one of them -- a resting accent halo is a different thing, so
  // this is the one density token with no panel parent to inherit from.
  cardToken.shadow(
    "--evcc-card-action-glow",
    "Action Glow",
  ),

  /* =========================================================
     TYPE SIZE -- one multiplier, not nineteen tokens
     =========================================================
     HIS RULING 2026-11-16: "i like the font sizes that are there but users may
     not ... per item sizes seems excessive but a font scale to hold the diff
     between them may work well."

     So this is a MULTIPLIER, and every font-size in the three cards is written
     as `calc(<its own literal> * var(--evcc-card-font-scale, 1))`. Multiplying
     is what "hold the diff between them" means arithmetically: the RATIO between
     any two sizes is untouched at every setting, so the type relationships he
     likes survive being scaled, and nothing about the design has to be
     re-decided to make the text bigger.

     WHY NOT A SET OF STEPS. The cards carry 19 distinct sizes over 51
     declarations. A token per size is 19 tokens and 342 translated strings, and
     it hands the user a way to flatten the hierarchy by accident -- set two
     steps equal and a label stops reading as a label. A token per STEP (a 4-step
     scale) is fewer, but it forces 51 declarations onto 4 values, which is a
     visible retype of the cards he just said he likes. The multiplier is the
     only shape that is free at the default.

     DEFAULT 1 IS EXACTLY TODAY. calc(0.80rem * 1) is 0.80rem, so every existing
     install is byte-identical -- verified against the committed card renders.

     RANGE IS DECLARED. Without it this inherits the group's SLIDER_CONFIG of
     {0, 8, 0.5}, which on a multiplier means a slider whose first notch doubles
     the text and whose last makes it eight times life size. 0.5-2.0 in 0.05
     steps is the usable band; 0 would make the text vanish, and the clamp is
     what stops that being one drag away. */
  cardToken(
    "--evcc-card-font-scale",
    "Font Scale",
    "number",
    { min: 0.5, max: 2, step: 0.05 },
  ),
];
