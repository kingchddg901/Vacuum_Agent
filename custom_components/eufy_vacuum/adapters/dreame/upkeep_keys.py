# -*- coding: utf-8 -*-
"""REGIME -> i18n KEYS. The whole Dreame guide, derived, not authored per family.

    DREAME_UPKEEP_KEY_GUIDES[regime_id][component] = {"steps": [key, …], "notes": [key, …]}

The values are **i18n keys, not text**. The card resolves them through its own per-user language
pack (`src/i18n/guide-keys.js` + the served `guides/keys/<lang>.json`), because the card is the
only layer that knows which language the person reading it chose — the backend sees the HA
instance language and nothing else.

WHY THIS REPLACED 255 AUTHORED FAMILIES

Every family carried its own transcribed prose, so 700 models needed hundreds of hand-authored
guides and every one of them needed translating into 18 languages. The card content actually
depends on THREE measured fields (`upkeep_regimes.py`), and all 700 models collapse to SEVEN
distinct cards. So the whole catalogue is 51 keys. Adding a model is one row in the regime table
and renders a card that already exists, already translated.

THREE RULES FROM THE DESIGN, ALL VISIBLE AS CODE BELOW

  1. THE CARD CANNOT SUBSTITUTE. Every key is a complete sentence in the viewer's language. There
     is no {component} interpolation, so a SHARED key can never name its object — and that only
     works because the card prints the component name as the panel heading.
  2. A SHARED KEY CARRIES NO PRONOUN AND NO NOUN. "Rinse it" needs gender agreement in ten of the
     eighteen languages; "Rinse with clean water only" does not. Breaking this turns a 51-key set
     into 18 x 6 authored strings.
  3. THE GATE IS ORDERED. `dry.fully_before_refit` always precedes the closer, because the closer
     is what absorbs the refit.

NEVER STATE ACCESS TYPE. Screw or clip, one brush or two, arrows printed on the part — the user is
holding it and can see. NO REASSEMBLY STEPS except where a part can go back wrong AND NOT TELL
YOU; exactly one qualifies in the whole catalogue, the Matrix10 mop pad holders returning to their
slots.

DO NOT NARRATE WHAT THE OBJECT SUPPLIES. Opening a lid to empty a container, lifting a cover to
reach inside — the part states those. This rule removed three clauses that had been carried in
from vendor manuals, which write full procedures because their reader may never have seen the
machine. Ours is holding it.
"""

from __future__ import annotations

from .upkeep_regimes import DREAME_MODEL_REGIMES

# ── THE SHARED TAIL ──────────────────────────────────────────────────────────────────────────
# Six keys doing most of the work. Measured over the whole corpus: "clean water only" appears
# 671 times in 671 documents — one line per manual, every manual.
RINSE = "rinse.clean_water_only"
DRY = "dry.fully_before_refit"
WIPE = "wipe.soft_dry_cloth"
# An object-free shared key inherits the PANEL HEADING as its implied object. That is right for
# Sensors and WRONG for the brush bay, where "wipe clean" read as "wipe the brush". So the cavity
# gets its own key.
CAVITY = "wipe.compartment_soft_dry_cloth"
HAIR = "tool.remove_tangled_hair"
NO_DET = "note.no_detergent"

# ── THE UNIVERSAL NOTE — on every card, added by Chris 2026-09-12 ────────────────────────────
# It is the ONE note that does not name a consequence, which is the bar the other four meet
# (torn filter mesh, bent bristles, fogged sensor windows, detergent). It earns its place
# differently: IT BOUNDS WHAT THE CARD CLAIMS TO BE. These panels are seven jobs distilled from
# vendor procedures — deliberately not the manual — and saying so is honest rather than
# decorative.
#
# ⭐ THE NOUN IS THE VENDOR'S, NOT A TRANSLATION. It sends the reader to go and FIND a document,
# so calling it something the cover does not say would send them looking for the wrong thing.
# The 18 strings take their term from the multi-language X50 manual's Contents page — one vendor
# naming the document in 40 languages in a single table. SEVEN of my drafted terms were
# defensible translations and wrong against the artefact (de Bedienungsanleitung ->
# Benutzerhandbuch, ru Руководство пользователя -> Инструкция по эксплуатации, tr Kullanım ->
# Kullanıcı Kılavuzu, ar دليل المستخدم -> دليل الاستخدام, id, zh-Hans, zh-Hant).
#
# NOT A SHARED-KEY VIOLATION: rule 2 bans naming the CARD'S OBJECT, so one key can serve every
# panel. "User Manual" is the same noun everywhere and is never the thing being serviced.
MANUAL = "note.see_user_manual"

# ── THE TWO CLOSERS ──────────────────────────────────────────────────────────────────────────
# Not a step like the others. Every other line acts on a part; this one tells the reader the task
# is CLOSED and nothing is left dangling — "I'm done, I didn't leave it turned off". It is on
# every card by design, which is not the same thing as being overloaded.
#
# It is two keys because what CLOSURE REQUIRES differs. If the user picked the robot up, closure
# is the robot back on its dock — where it charges, where the map origin is, and what the firmware
# treats as its last known position. If they never touched it, closure is just running again.
# One key could not say both, which is why Japanese could not render the old single key: 戻す
# demands a destination, and the English had papered the distinction over.
DOCK_IT = "service.return_to_dock"        # robot-side: the robot was in your hands
BACK_IN = "service.return_to_service"     # dock-side: the robot never moved

# ── THE FIVE ROBOT TASKS — every model gets all five ─────────────────────────────────────────
ROBOT = [
    # Dust bin and filter are ONE task: the filter body is attached to the bin, on the suction
    # path, so it cannot vary with mop type. This is the ONLY panel that acts on two objects, so
    # its steps carry nouns and it takes a task-specific rinse instead of the shared one — the
    # heading names only the filter, so nothing else would say "bin". ORDER: the filter comes OUT
    # before the bin is emptied — tipping the contents past a filter still sitting in it coats the
    # thing you are about to clean.
    # COMPONENT KEY IS `filter`, NOT `dust_bin_and_filter`. The component key is the CORE's
    # identity for the card — it carries the countdown sensor and the reset button
    # (maintenance_components.py) and it is what the card's 18 translated headings are keyed on.
    # Inventing a new key here would have produced TWO cards for one object: a `filter` card with
    # the countdown and no steps, and a `dust_bin_and_filter` card with the steps and an English
    # heading. So the panel speaks the core's vocabulary and the extra object stays named IN THE
    # STEPS, which this panel's steps already do.
    # (the filter panel is built by `_filter()` below — it is the ONE panel that varies, because
    # the 2-in-1 bin carries the water tank with it. Everything else here is the same on all 700.)
    # NO DRY GATE. Hair removal is dry and the compartment wipe is explicitly a DRY cloth, so
    # nothing here ever gets wet. The gate survives only on parts that are RINSED.
    ("main_brush",
     ["access.brush_guard", HAIR, CAVITY, DOCK_IT], []),
    # The rinse is CONDITIONAL and the condition lives IN THE SENTENCE — the card cannot branch.
    ("side_brush",
     ["side.remove", HAIR, "side.rinse_if_soiled", DOCK_IT],
     ["note.side_brush_do_not_yank"]),
    # Charging contacts folded in here: the action is identical to the sensors, and both are
    # "wipe a dry cloth over something electrical".
    # Same reason as `filter` above: the key is `sensor`, the core's, so this lands on the card
    # that already owns the sensor countdown and already has 18 translated headings. The contacts
    # are named in their own step.
    ("sensor",
     [WIPE, "contacts.dock_side_too", DOCK_IT], ["note.wet_cloth_damages_sensors"]),
    # NAMED FOR WHAT THE STEPS DESCRIBE. Dreame's procedure heading is "Omnidirectional Wheel"
    # and every noun in the procedure is that wheel — verified in the RUSSIAN edition, where case
    # and number are explicit and `Ролик` (the caster) NEVER appears. We used to call this
    # `caster_wheel`, which described the wrong part.
    #
    # The second wheel is NOT derivable from the regime — it appears across every mop type — so
    # instead of a fourth field the wipe step is worded to be TRUE ON EVERY MACHINE. When a fact
    # is not derivable, word the step so being wrong costs nothing.
    ("omnidirectional_wheel",
     # ORDER: everything done AT THE ROBOT first, then everything AT THE SINK. Putting the wipe
     # after the dry gate split the at-the-robot work across a wait.
     ["wheel.omnidirectional_remove", HAIR, "wheel.wipe_other_wheels", RINSE, DRY, DOCK_IT], []),
]

# ── THE DUST BIN AND FILTER — the one panel that varies ──────────────────────────────────────
# THE 2-IN-1 CLAUSE, ruled 2026-09-10 and landed 2026-09-12: "the Dust Bin and Filter task is ONE
# key set for all 700 models, with a single conditional line hanging off `tanks`. No 2-in-1
# branch, no extra column, no extra bucket."
#
# WHY `tanks == "no"` IS THE RIGHT HINGE — Chris's rule, measured over all 713 rows with zero
# violations: a machine that MOPS and has NO STATION TANKS must carry its water on board. On
# these models that water rides in the DUST BIN UNIT, and 149 of them were being handed a bin
# card that never mentioned the tank they were lifting out with it.
#
# IT REPLACES A CARD RATHER THAN ADDING ONE. `robot_water_tank` was its own panel on 20 models;
# clean tap water poured down a sink does not earn a trip of its own.
#
# ⛔ IT IS AN ACTION, NOT AN EXPLANATION. My first draft told the reader the water tank comes out
# together with the bin. Chris: **"they can see the water tank."** That is DO NOT NARRATE WHAT THE
# OBJECT SUPPLIES — the person is holding the unit with the water in it; describing the assembly
# back to them is the vendor-manual voice this design exists to avoid. The clause earns its place
# only by adding the ACT: empty the water while you are here, so it is not left standing.
#
# NO PRONOUN. "Empty it as well" needs gender agreement in ten of the eighteen languages.
BIN_IS_2IN1 = "bin.empty_water_too"

FILTER_STEPS = ["access.dust_bin", "filter.remove_and_tap", "bin.empty",
                "rinse.bin_and_filter_clean_water", DRY, DOCK_IT]
FILTER_NOTES = ["note.filter_no_brush_finger_sharp", NO_DET]


def _filter(mop: str, tanks: str):
    """The dust-bin-and-filter panel; gains one clause on a 2-in-1 bin.

    ⛔ BOTH HALVES OF THE RULE. Chris stated it as "if not auto wash BUT MOP YES it has a tank of
    some kind onboard" — a machine that does not mop has no water ANYWHERE, so `tanks == "no"`
    alone is not the condition. I dropped the mop half here while writing it correctly into
    DUK-6, and Dreame cannot expose the mistake: all 700 of its models mop, so no regime
    exercises the branch. PORTING EUFY FOUND IT — its X8, L60 and L60 SES are vacuum-only, and
    they were being told to empty water out of a dust bin that has never held any.
    """
    steps = list(FILTER_STEPS)
    if tanks == "no" and mop in MOP:
        # ORDER: straight after the dust is out, while the unit is still over the bin and before
        # the rinse — pouring water through a compartment you have not emptied makes slurry.
        steps.insert(steps.index("bin.empty") + 1, BIN_IS_2IN1)
    return ("filter", steps, list(FILTER_NOTES))


# ── THE MOP — one branch fires. Each earns its place by carrying an INVISIBLE job. ───────────
# SimuMop folds into cloth: same pad, same holder, same wash, same dry. Its difference is HOW IT
# MOPS (powered oscillation vs passive drag) = cleaning performance, not maintenance.
MOP = {
    # The assembly comes apart at TWO joints and there are FOUR objects. Neither is guessable.
    "pad": ["mop.pad_carriages_off", "mop.pad_off_carriage", "mop.pad_clean_all_four",
            DRY, DOCK_IT],
    # THE MODULE HOLDS WATER. Pull it off over a carpet and you find out the hard way.
    "cloth": ["mop.cloth_module_off", "mop.cloth_pour_out_water", "mop.cloth_pad_off_module",
              RINSE, DRY, DOCK_IT],
    # There is a FILTER in the mop compartment. You would never know it was there.
    "roller": ["mop.roller_release_and_lift", "mop.compartment_and_filter", RINSE, DRY, DOCK_IT],
    # The hair tangles in the BRACKET, not the mop — clean the mop, refit it, and the tangle is
    # still there. The track manual carries the SAME compartment-and-filter entry as the roller,
    # so it shares that key rather than going without the step.
    "track": ["mop.track_release_assembly", "mop.track_detach_from_bracket",
              "mop.track_hair_in_bracket", "mop.compartment_and_filter", RINSE, DRY, DOCK_IT],
}
# ⛔ THE MOP CARRIES NO NOTES. It held two and Chris dropped both 2026-09-12:
#   note.cloth_air_hole_if_slow_flow  "…clean the small air hole in the tank cover"  — a
#       DIAGNOSTIC, not a consequence. It sends the reader to a cause; it does not name damage
#       they cannot undo.
#   note.track_slot_rotates_normally  "The slot turns by itself… That is normal, not a fault."
#       — REASSURANCE about a non-event.
# The four surviving notes all name a consequence the user cannot see coming and cannot reverse
# (torn filter mesh, bent side-brush bristles, fogged sensor windows, detergent). That is the bar.
MOP_NOTE: dict[str, list[str]] = {}
MOP_ALIAS = {"SimuMop": "cloth"}

# ── THE DOCK — self-wash is the only gate left. ──────────────────────────────────────────────
# The dust bag was ruled out entirely: install-and-forget, no procedure, and a vendor cadence that
# swings tenfold. So a five-value dock field is ONE BIT here.
#
# ⛔ THE STATION WATER TANKS HAD A PANEL AND NO LONGER DO (479 models). Chris: **"water_tanks card
# only is there if a sensor supports"**, then, on Dreame's tank enums: **"the status on dreame is
# just installed or low / not worth a card."** `adapter.py` already recorded the hardware half —
# Dreame publishes NO numeric water percent, every water sensor is an ENUM
# (not_available/not_installed/low_water/installed) — so nothing can back the countdown a card
# is built around. It also collided with the older ruling that dock tank STEPS GO: 6 of the 9
# tank keys were pure narration ("Take out the dirty water tank and pour it out"), which is DO
# NOT NARRATE WHAT THE OBJECT SUPPLIES.
#
# THE PLUMBED GATE THAT LANDED EARLIER THE SAME DAY IS NOW MOOT AND THAT IS FINE — it was correct,
# it shipped, and the panel it protected then went away entirely. The reasoning survives in the
# DUK-6 assertion and in the handoff; the 70-model defect it fixed was real either way.

# STEP 1 IS A PRECONDITION, NOT A WARNING. Dreame carries TWO heat cautions — one on the routine
# removal, one on the occasional descale — and we had only the second, so the lift that every
# maintenance pass performs was unwarned. Cooling is the precondition for both, so one leading
# step retires both. It hedges the hardware because heating-module presence is not derivable from
# the regime, and conditions instead on the LAST WASH CYCLE, which the user can always evaluate.
#
# NO DRY GATE: the wash tray is a wet service item living in a station that fills with water. The
# gate is for parts that must be DRY BEFORE THEY WORK AGAIN.
#
# DESCALING IS OUT OF SCOPE. It was never ruled in — it arrived because the vendor attaches the
# burn caution TO the descale step, so fetching the warning meant arriving holding the procedure.
# It was also the only step that had the user apply a SUBSTANCE they must go and obtain, on a
# part a minority of these stations have.
# THE COMPONENT ID IS `cleaning_tray`, THE STEP KEYS STAY `washboard.*`. Chris 2026-09-12:
# "washboard = cleaning tray" and "cleaning tray is pretty dang generic". `washboard` is the
# metaphor Dreame's manuals reach for; the generic word is the better CANONICAL id, and Eufy
# already ships `cleaning_tray` translated in all 17 packs, so every brand reads its own
# language with no label_key and no new string.
#
# The step keys do NOT follow, and that is not an oversight: prefixes here are by ACTION or
# OBJECT and have never matched panel ids -- `side_brush` renders `side.*`, `sensor` renders
# `wipe.*` + `contacts.*`, `main_brush` renders `access.*`. Renaming four already-translated
# keys to chase a panel name would cost 4 x 18 strings and buy nothing.
CLEANING_TRAY = ("cleaning_tray",
                 ["washboard.allow_cooling_before_service", "washboard.remove", RINSE,
                  "washboard.wipe_base", "washboard.filter_if_fitted", BACK_IN], [])

# ⛔ `robot_water_tank` WAS A PANEL ON 20 MODELS AND IS NOW ONE CLAUSE ON THE FILTER CARD.
# Settled 2026-09-10, landed 2026-09-12: clean tap water poured down a sink does not earn a trip
# of its own. See BIN_IS_2IN1 / `_filter()` above.

# The Matrix10 dock parks three mop assemblies in slots and swaps them by room type. This panel is
# ADDITIONAL to the robot's own mop panel, not a replacement: the holders MOUNT TO THE ROBOT (its
# parts list carries "Mop Pad Holder Mounting Holes") and the dock only STORES them, so a set is
# on the robot at any moment and replacing the branch left those pads with no panel at all.
MOP_SWAP = ("mop_pad_holders",
            ["access.station_door", "mop.holders_remove", "mop.pads_off_holders_and_clean",
             DRY,
             # THE ONLY REASSEMBLY STEP IN THE DESIGN. It earns its place because it fails
             # SILENTLY: put the scrubbing pair in the sponge slot and the dock deploys the wrong
             # pad for the floor. It runs fine and cleans wrong.
             "mop.holders_to_corresponding_slots",
             BACK_IN],
            [])

# ⛔ `robot_used_water_box` WAS A PANEL ON 111 MODELS (roller + track) AND IS GONE.
# An EARLIER ruling kept it — dirty water, sits between washes, grows residue — and I flagged the
# reversal rather than overwrite it. Chris resolved the actual distinction: **"the act is rare per
# machine for the dirty water tank."** Rare PER MACHINE, not rare by model count (111 is 16% of
# the catalogue). A card is a job someone does; a job almost nobody performs is not one.

SELF_WASH = ("wash+empty", "wash+empty+swap", "wash_only")


def emit(mop_type: str, dock_tier: str, tanks: str):
    """The three measured fields -> [(component, [step keys], [note keys])], in service order.

    EIGHT COMPONENTS, NOT FOURTEEN. "JOBS, NOT PARTS": a card is one trip and one set of hands,
    and a job touches several parts. A vendor's parts table enumerates OBJECTS because that is
    how spares are sold and wear is tracked — reading it as a card list is what took this
    adapter from 4 components to 14, the same drift roborock made independently six weeks
    earlier. The seven jobs plus the Matrix10 swap are the whole surface.
    """
    mop = MOP_ALIAS.get(mop_type, mop_type)
    out = [_filter(mop, tanks)] + list(ROBOT)
    if mop in MOP:
        # ONE `mop` COMPONENT, NOT FOUR. The branches are step-sets, not cards: exactly one fires
        # per model and they are never co-present, so `mop_pad`/`mop_cloth`/`mop_roller`/
        # `mop_track` were four names for one job. The panel heading is the job; the steps say
        # which assembly. (Dreame's own procedures call roller and track alike "the mop
        # assembly".)
        out.append(("mop", MOP[mop], MOP_NOTE.get(mop, [])))
    if dock_tier == "wash+empty+swap":
        out.append(MOP_SWAP)            # ADDITIONAL to the robot's own pads, not a replacement
    if dock_tier in SELF_WASH:
        out.append(CLEANING_TRAY)
    # THE UNIVERSAL NOTE GOES LAST ON EVERY PANEL. Appended here rather than written into each
    # component so it cannot drift: a new component gets it automatically, and DUK-6c proves
    # every emitted panel carries it.
    return [(c, s, list(n) + [MANUAL]) for c, s, n in out]


def regime_id(mop_type: str, dock_tier: str, tanks: str) -> str:
    """Stable, self-describing id. Readable back to the three fields that produced it, so a
    payload carrying `mop_pad|wash+empty|yes` can be traced to the table without a lookup."""
    return "%s|%s|%s" % (mop_type, dock_tier, tanks)


# regime_id -> component -> {"steps": [key], "notes": [key]}. Built once at import from the
# regimes actually present; nothing is stored that could drift from `emit`.
DREAME_UPKEEP_KEY_GUIDES: dict[str, dict[str, dict]] = {}
for _regime in sorted(set(DREAME_MODEL_REGIMES.values())):
    DREAME_UPKEEP_KEY_GUIDES[regime_id(*_regime)] = {
        _comp: {"steps": list(_steps), "notes": list(_notes)}
        for _comp, _steps, _notes in emit(*_regime)
    }

# model id -> regime id. Replaces DREAME_MODEL_GUIDE_FAMILIES.
DREAME_MODEL_KEY_REGIMES: dict[str, str] = {
    _m: regime_id(*_r) for _m, _r in DREAME_MODEL_REGIMES.items()
}

# Every key any model can emit. The card's pack must cover this set exactly — a key emitted and
# not authored renders as its own name, which is the fallback and cannot be silent.
DREAME_UPKEEP_KEYS: frozenset[str] = frozenset(
    k
    for _guide in DREAME_UPKEEP_KEY_GUIDES.values()
    for _comp in _guide.values()
    for k in (_comp["steps"] + _comp["notes"])
)
