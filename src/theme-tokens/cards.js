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
  // The frame's own background and border colour. They are NOT the same question as
  // Surface Card / Border Default, which paint the card's INSIDE as well -- these two
  // move the frame alone, which is why a dashboard card's select and its room rows
  // deliberately keep reading --surface / --border.
  // An HA theme reaches these through --evcc-surface-card / --evcc-border-default
  // instead (foundation.js, anchor RNT9NEY2); nothing here names an --ha-card-* rung,
  // because a rung here would let an HA theme beat a VA one.
  cardToken.color("--evcc-card-frame-background", "Frame Background"),
  cardToken.color("--evcc-card-frame-border-color", "Frame Border Colour"),

  // A frame border is 0-8px in practice; 0 is a legitimate value and the
  // single most-requested one (#83). Half-pixel steps because HA themes in
  // the wild do use them.
  cardToken(
    "--evcc-card-frame-border-width",
    "Frame Border Width",
    "size",
    { min: 0, max: 8, step: 0.5 },
  ),

  // type "shadow" renders the PER-LAYER editor (_renderThemeShadowTokenRow) whenever
  // parseShadow can take the value apart -- X, Y, Blur, Spread, a colour and Inset per
  // layer, with add, remove and reorder. It falls back to the free-text box for a value
  // the fields cannot round-trip, such as a var() pointing at another token or a calc()
  // in one of the lengths, and leaves that text exactly as written.
  // (This comment said no composite editor existed anywhere in the registry. That was
  // true when the token was added and stopped being true later in the SAME release.)
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

/* =========================================================
   PER-CARD OVERRIDES -- one more rung on the same chain
   =========================================================
   HIS CALL 2026-11-16, and the reason matters more than the feature: "yaml is
   fine for some but most of the reason i made the theme editor is to not need
   it for most people". A seam that only YAML can reach would have been half the
   job again -- so these are real registry tokens with real controls, not just a
   var() a theme author could discover.

   THE CHAIN GAINS ONE RUNG, and that is the whole mechanism:

       var(--evcc-card-<id>-<thing>,      <- this card only
           var(--evcc-card-<thing>,       <- all three cards
               var(<panel token | --ha-card-*>,
                   <literal>)))

   So: nothing set anywhere paints as it always did; the shared token moves all
   three cards together; a per-card token moves exactly one. Each rung is
   strictly more specific than the one it falls through to.

   DERIVED FROM THE SHARED EIGHT, NOT RESTATED. Every per-card token copies its
   sibling's label, type and range by spreading the already-built token object,
   so a range retuned above cannot drift from its per-card twin -- which is the
   defect a parallel table of {label, type, min, max, step} would invite, and
   this group already carries two deliberately-explicit ranges that would be
   exactly the thing to get wrong twice.

   EACH CARD DECLARES ONLY WHAT IT READS, measured per token across the three
   card files rather than assumed: the frame and text controls reach all three,
   header padding and the field gap exist on the room and Dashboard Mode cards,
   and row/section padding exist only on Dashboard Mode -- it is the only card
   with room rows and sections. A control for a thing a card does not have would
   be a slider that moves nothing, which is worse than its absence.
   ========================================================= */

/** The id each card is known by in the fixtures and the density specs. */
const CARD_IDS = Object.freeze(["room", "dashboard", "profile"]);

const SHARED_BY_THING = new Map(
  DASHBOARD_CARD_TOKENS.map((t) => [t.key.replace("--evcc-card-", ""), t]),
);

/** Which of the ten each card actually reads. Measured, not assumed.
 *  All three read frame-background and frame-border-color: every card draws a frame,
 *  the room card through ha-card and the other two through a plain div. */
const READS = Object.freeze({
  room: ["frame-background", "frame-border-color", "frame-border-width", "frame-shadow",
         "action-glow", "font-scale", "header-padding", "field-gap"],
  dashboard: ["frame-background", "frame-border-color", "frame-border-width", "frame-shadow",
              "action-glow", "font-scale", "header-padding", "field-gap",
              "row-padding", "section-padding"],
  profile: ["frame-background", "frame-border-color", "frame-border-width", "frame-shadow",
            "action-glow", "font-scale"],
});

/** Editor subgroup per card. Deliberately NOT the card-picker name: that one
 *  reads "Eufy Room Card", and a brand word has no business naming a core
 *  group whose siblings have to speak for every adapter. */
export const PER_CARD_GROUP = Object.freeze({
  room: `${DASHBOARD_CARD_GROUP} — Room`,
  dashboard: `${DASHBOARD_CARD_GROUP} — Dashboard Mode`,
  profile: `${DASHBOARD_CARD_GROUP} — Profile`,
});

/* EVERY PER-CARD KEY, SPELLED OUT, and it has to be.
   scripts/check-styles.mjs builds its "tokens a theme may supply" inventory by
   TEXT-SCANNING this directory for --evcc-* literals; it does not import the
   registry. Keys built at runtime as `--evcc-card-${id}-${thing}` are therefore
   invisible to it, and every var() site reads as a dangling reference -- measured
   when this landed, the build failed with exactly one error per site (51 at the time). Spelling the
   keys out is the fix, not relaxing the gate: it also makes them greppable,
   which is how anyone actually finds a token.
   The SHAPE is still derived from the shared sibling below, so a retuned range
   cannot drift. [PCT-1] pins this list against what READS implies, so the two
   halves cannot disagree. */
export const PER_CARD_KEYS = Object.freeze([
  "--evcc-card-room-frame-background",
  "--evcc-card-room-frame-border-color",
  "--evcc-card-room-frame-border-width",
  "--evcc-card-room-frame-shadow",
  "--evcc-card-room-action-glow",
  "--evcc-card-room-font-scale",
  "--evcc-card-room-header-padding",
  "--evcc-card-room-field-gap",

  "--evcc-card-dashboard-frame-background",
  "--evcc-card-dashboard-frame-border-color",
  "--evcc-card-dashboard-frame-border-width",
  "--evcc-card-dashboard-frame-shadow",
  "--evcc-card-dashboard-action-glow",
  "--evcc-card-dashboard-font-scale",
  "--evcc-card-dashboard-header-padding",
  "--evcc-card-dashboard-field-gap",
  "--evcc-card-dashboard-row-padding",
  "--evcc-card-dashboard-section-padding",

  "--evcc-card-profile-frame-background",
  "--evcc-card-profile-frame-border-color",
  "--evcc-card-profile-frame-border-width",
  "--evcc-card-profile-frame-shadow",
  "--evcc-card-profile-action-glow",
  "--evcc-card-profile-font-scale",
]);

/** Split a per-card key back into its card id and its shared sibling's suffix. */
function splitPerCardKey(key) {
  for (const id of CARD_IDS) {
    const prefix = `--evcc-card-${id}-`;
    if (key.startsWith(prefix)) return { id, thing: key.slice(prefix.length) };
  }
  throw new Error(`PER_CARD_KEYS: "${key}" names no known card id`);
}

export const PER_CARD_TOKENS = PER_CARD_KEYS.map((key) => {
  const { id, thing } = splitPerCardKey(key);
  const base = SHARED_BY_THING.get(thing);
  if (!base) {
    // Fails at IMPORT rather than shipping a token whose shape came from nowhere --
    // a typo would otherwise mint a control with no range and a blank label.
    throw new Error(`PER_CARD_KEYS: "${key}" has no shared token "${thing}"`);
  }
  if (!READS[id].includes(thing)) {
    // A control for a thing this card does not read is a slider that moves nothing.
    throw new Error(`PER_CARD_KEYS: ${id} does not read "${thing}"`);
  }
  return Object.freeze({ ...base, key, group: PER_CARD_GROUP[id] });
});
