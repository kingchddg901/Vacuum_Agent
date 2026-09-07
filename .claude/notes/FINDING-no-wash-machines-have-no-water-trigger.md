# The no-wash machines cannot signal low water — and the split's premise does not fit them

**Status:** MEASURED 2026-09-07. **The split must be re-scoped before it is applied.**
Chris stopped this: *"we had not yet decided if the no wash vacuums got a card yet. i have 0
way to tell if they even can fire a low water alert. they are super basic systems."*

He was right on both counts, and I had closed the question early — I wrote "the 57 keep a fill
card, because nothing on those machines fills the tank for them." That answers **who fills it**,
which is not **whether it earns a card**. Those are different questions and only the first was
answered.

## 1. Can they signal low water? Overwhelmingly, no.

The question is decidable, and it does not need manual prose. A card needs a TRIGGER; a trigger
has to reach Home Assistant as an entity; Dreame entities come from MIoT properties. So it
reduces to *does this model's firmware implement the property* — which published specs answer
per model.

Upstream (`//192.168.4.104/config/custom_components/dreame_vacuum`, `dreame/types.py`) defines:

```
LOW_WATER_WARNING   siid 4, piid 41    NO_WARNING / NO_WATER_LEFT / NO_WATER_LEFT_AFTER_CLEAN
                                       / NO_WATER_FOR_CLEAN / LOW_WATER / TANK_NOT_INSTALLED
WATER_TANK          siid 4, piid 6
TANK_FILTER         siid 17            waterbox-sieve — the clean tank's own consumable counter
```

All polled (`READ_ONLY_PROPERTIES`). Against the published specs
(`https://miot-spec.org/miot-spec-v2/instances?status=all` — 143 dreame/mova/trouver vacuum
specs, the same 143 the caster-wheel ruling used), for the 22 no-wash families that have a
published spec:

| what the spec declares | families |
|---|---|
| **low-water warning** (`no-water-warn` / `nowater-tips`) | **2** — `s10`, `s10_plus` |
| tank **presence** only (`waterbox-status` No/Yes, `door-state`) | 5 |
| water **volume setting** only (`Low/Mid/High`, 低/中/高水量) — a mop-wetness OUTPUT, not a sensor | the remainder |
| **`waterbox-sieve` consumable counter** | **0 of 22** |

So on these machines there is **no level trigger and no consumable trigger** — no device-side
trigger of any kind for the clean-water tank.

### Two traps this had to clear, and a third that was real

- **Instrument blindness.** `REFERENCE-dreame-offline-harness.md` records that upstream uses
  vendor-private properties "absent from any public MIoT spec". If siid 4/41 were private, every
  absence would mean *not published*, not *cannot warn* — the same all-zero-signature trap that
  forged five wrong answers in the manual walk. **Positive control:** `dreame.vacuum.r2228z`
  publishes siid 4/piid 41 as `nowater-tips`. The instrument can see the property when it exists.
- **siid/piid are NOT stable across vendors.** On `dreame.*` siid 4 is the private
  `vacuum-extend` service; on `xiaomi.*` / `ijai.*` / `szkj.*` siid 4 is **`Alarm`**. A first pass
  counting "(4,6) present" returned 14 families — it was counting alarm properties. Judge by the
  property NAME and its VALUE-LIST, never the number.
- **`Filter` is the AIR filter.** Every model has `siid 11 Filter` (Filter Life Level / Left
  Time). The water sieve is `siid 17 waterbox-sieve`, present on the control and on none of the
  22. Checked because this exact vocabulary collision has bitten repeatedly.

### What is honestly NOT known

- **29 of the 51 no-wash families have no published spec at all.** Unknown, not negative.
- `s10` is a no-dock machine that **does** declare the low-water warning. So "basic" does not
  imply "cannot" — this is per-model, not a tier rule.
- A published spec may lag firmware.

## 2. ⛔ The bigger problem: the split's premise does not apply to these families

The split rests on: *the vendor's combined "Cleaning the Clean & Dirty Water Tanks" section was
lifted into `clean_water_tank`, so the clean card carries dirty-tank behaviour.* That can only
happen on a machine **that has a dirty tank.**

```
split scope                                              81
  manual-confirmed NO station water hardware             51   <- merge is IMPOSSIBLE here
  robot-tank but manual unreadable                        6   <- presumed same, unverified
  station-side clean tank (access.station_tank)          24   <- merge is plausible; spec fits
```

(51 + 6 + 24 = 81, and that reproduces the original 57 robot / 24 station table exactly.)

The 51 are confirmed from **their own manuals**, not from corpus absence — which matters,
because "lacks a dirty card" would be the circular reasoning Chris already caught once. Their
manuals show `clean_tank = dirty_tank = washboard = plumbed = 0`.

**Only 4 blocks corpus-wide carry a genuine `dirty.*` leak** — `d20_pro`, `f10`, `f10_plus`,
`s10`, all `dirty.rinse_plain`. Four, not eighty-one.

### What their existing cards actually contain

All 51 have a clean-water card. **51 of 51 contain pour/rinse/dry; exactly 1 contains a fill
step.** The dominant shape:

```
off_dock > remove > pour_out > tank_rinse > air_hole > air_dry_refit
```

Whatever this content is, it is **not** the merged dirty-tank procedure the split was written to
undo — there is no dirty tank on these machines to have merged from. So the split's stated
justification does not reach them, and applying it here would be replacing content on a premise
that is false for this group.

⚠ That is a statement about the SPLIT's premise, not a defence of the card. Whether the
content earns a card at all is §3 — and the answer there is probably no. Do not read this
subsection as "the cards are fine"; an earlier draft did exactly that and Chris caught it.

## 3. The card should probably NOT exist for these machines

⚠ I wrote this section twice. The first version recommended "leave the 51 as maintenance
cards — they are already right", and Chris called it: *"you are still locked on keeping that
card for the no doc vacuums."* He was right. I had gone looking for a justification to keep the
card rather than asking whether it earns one, and reached for the weakest argument available
(mildew) to do it. What follows is the honest read.

### The ruling already exists, and I failed to apply it

Chris, on the robot's used-water box: *"the robot's water tank shouldn't be in our maintenance
cards. That has slipped through for a long time."*
([`FINDING-robot-water-box-inside-dirty-tank-cards.md`](FINDING-robot-water-box-inside-dirty-tank-cards.md))

The clean-water tank on a no-dock machine is **the same class of part** — robot-side,
user-handled, no counter. I applied that ruling to the dirty side and never carried it across.

### Everything else points the same way

1. **No trigger of any kind.** No low-water property (§1), no `waterbox-sieve` counter
   (0 of 22). Nothing can fire the card, so its cadence would be a number we invented with no
   device or vendor basis.
2. **The user handles this tank more often than any cadence would fire.** On a no-dock machine
   you remove it and fill it *every time you mop*. It is not a buried HEPA filter or a sensor
   nobody sees — it is in their hands routinely. That is Chris's own operational-vs-routine
   line, and this part sits squarely on the operational side.
3. **The content is not maintenance.** Read back what the 51 cards actually contain:
   `pour_out` / `tank_empty` is **operational**; `tank.air_hole` (×37) is
   *"if water runs out slowly or spreads unevenly, clean the air hole"* — **troubleshooting
   fired by a symptom**, not a cadence task. Neither is a maintenance trigger.
4. **Drying already has a home.** `note.mildew_if_left_wet` is attached to `mop_cloth`, which has
   its own card. The mop pad is the part that actually grows mildew.
5. **The dust-box precedent fits rather than conflicts.** It was folded away for no counter plus a
   self-evident action. Here there is also no counter, and the action is not merely self-evident
   — it is something the user is *already doing by hand on every mopping run*.
6. **It is not declarable cleanly anyway.** `clean_water_tank` is undeclared in the adapter's
   component map today (its 103 blocks reach no card —
   [`PARKED-dreame-consumable-declaration.md`](PARKED-dreame-consumable-declaration.md) §5),
   and §4 records that the family gate cannot express "counter where present, guide card where
   absent" — declaring it shows an "unknown" replacement row on every model.

### ✅ RULING — no rehoming. We are not a troubleshooting guide.

Chris, 2026-09-07: *"no need we are not a trouble shooting guide."*
Refined immediately after: *"a note in a card we are keeping is ok but troubleshooting for its
own sake is different."*

I had proposed rehoming `tank.air_hole` (×41, *"If water runs out slowly or spreads unevenly,
clean the air hole in the water tank's cover"*) onto a surviving card. **Overruled.** It retires
with the cards. We do not find a new home for troubleshooting content, and we do not add cards or
sections to hold it.

⛔ **THE RULING IS ABOUT PURPOSE, NOT ABOUT CONDITIONAL WORDING.** I over-applied it within one
turn: having been told we are not a troubleshooting guide, I swept the corpus for every
symptom-fired step and was about to strip `tank.air_hole_inlet_lid` from `d20_plus / mop_cloth`
— a note riding inside a card we are KEEPING. Chris stopped that. The line is:

| | |
|---|---|
| content that exists **only** to troubleshoot, needing its own home | not ours — do not create it, do not rehome it |
| a conditional note **inside a card that exists for other reasons** | **fine, leave it alone** |

So the corpus sweep for this shape is recorded as CONTEXT, not as a worklist:

```
tank.air_hole            x41  clean_water_tank   -> dies BECAUSE ITS CARD DIES, not because
                                                    it is conditional. Nothing rehomed.
tank.air_hole_inlet_lid  x6   clean_water_tank + mop_cloth
                                                 -> 5 go with the cards; the ONE on
                                                    d20_plus/mop_cloth STAYS - a note in a
                                                    card we keep.
caster.pry_wheel_tool    x2   caster_wheel       -> STAYS. Same reason, and it is a
                                                    within-task fallback anyway.
```

**No separate cleanup task falls out of this ruling.**

### ✅ APPLIED 2026-09-07 — Chris: "i am making the call regardless now the robot tanks go"

```
51  manual-confirmed no-dock / no station water   ->  NO clean_water_tank card.
                                                       tank.air_hole retires with it, unrehomed.
 6  robot-tank, manual unreadable                 ->  same treatment once readable, or hold
24  station-side clean tank                       ->  THE SPLIT, as specified. Merge premise
                                                       holds only here.
 4  d20_pro f10 f10_plus s10 (dirty.rinse_plain)  ->  fix individually; 3 of the 4 are in the
                                                       no-dock group and are contamination
```

So the split is a **24-family** job, not 81 — and the other 57 are a *deletion* question, not
a restructuring one.

⚠ Open, and deliberately not answered here: whether "no card" is right for the **station**
machines' robot-side tanks too, and what happens to the 103 orphaned blocks. Both are Chris's.


## 4. Deletion, measured (DRY RUN 2026-09-07, nothing written)

`authoring/compose/tools/dryrun_drop_clean_tank.py`

```
families with a clean_water_tank card      99
  would be DELETED                         57
  would REMAIN                             42   <- the station-side split population

see-references broken                       0   <- no hidden coupling; checked because a
                                                   block count cannot see a `see` record
phrase keys used by the deleted blocks     41
  ORPHANED, retire cleanly                 12
  still used elsewhere, DO NOT TOUCH       29
new strings needed                          0   <- deletion never adds vocabulary
```

Nothing else falls out: `tank.air_hole_inlet_lid` on `d20_plus / mop_cloth` **stays** (§3).

Two facts from the dry run, both against the case for keeping the cards:

* **`tank.fill` is used ONCE** in the entire corpus, and is itself on the orphan list. The split
  would have propagated a near-unused step across 81 cards.
* **`note.tank_empty_promptly`** (the mildew reasoning) sits on **one** family, not corpus-wide.
  An earlier draft of this note presented it as if it justified the whole group.


## 5. The air hole is a ROBOT part, and that is the tell (Chris, 2026-09-07)

*"tank.air_hole entries in clean_water_tank that is a glitch — a robot part in the dock side."*

He is right, and it is sharper than the framing I had. `clean_water_tank` as a COMPONENT means
the dock's clean-water tank. The air hole is a feature of the **robot's** tank cover. So an
air-hole step inside `clean_water_tank` is not merely troubleshooting — it is a **robot part
filed under a dock-side component**, i.e. direct evidence the entry is misfiled.

Measured:

```
families whose clean_water_tank card carries an air-hole step   46
   in the robot-tank (no-dock) group                            46   = 100%
   in the station-tank group                                     0   = 0%
robot-tank families WITHOUT the marker                          11
```

**100% specificity.** `tank.air_hole` never once appears on a station-side card.

This matters as CORROBORATION FROM AN INDEPENDENT SIGNAL. The manual walk concluded "no station
water hardware" from vendor documents; the air-hole marker concludes "this is the robot's tank"
from the corpus's own vocabulary. The two methods share no inputs and agree exactly — the 46
are a subset of the 57, with zero outside. That is the kind of agreement the earlier corpus-only
arguments could never produce, because those were circular (a family lacks a card because nobody
authored one). This one is not.

It also reframes the deletion: the 57 are not "cards we are choosing to drop" so much as
**entries that were never the component they were filed under.**


## 6. ✅ APPLIED — what actually landed

`authoring/compose/tools/apply_robot_tanks_go.py` (APPLY=1). Backup at
`authoring/compose/_backup_robot_tanks_20260907-025617`.

```
clean_water_tank cards DELETED        58   robot-side; component removed outright
dirty_water_tank cards STRIPPED       34   robot phase only; station phase intact
phase boundaries removed              15   a dangling access.off_dock
HELD OUT                          s60_pro

audit after, all three directions
  robot-side clean cards remaining     0
  dirty.robot_box_* keys remaining     0
  dirty cards left with nothing        0

emitted module (dreame_upkeep_guides_composed.py, re-emitted)
  blocks              1880 -> 1822
  clean_water_tank     103 -> 45      exactly -58
  dirty_water_tank            168     count unchanged; contents stripped
  lint_compose                  0 findings
```

Residual mentions in the emitted module, both checked and both correct: the robot used-water
box survives only under **`s60_pro`** (held out), and the one "Fill the clean-water tank" is
**`z_series`**, a station-side card that already reads *"Access the clean-water tank in the base
station"* — the split's target shape, already right.

### ⚠ TWO BUGS THE DRY RUN CAUGHT, both silent

1. **The delete matched nothing.** `components` is a LIST of records carrying their own
   `component`, not always a dict. The first draft guarded on `isinstance(comps, dict)` and
   reported **0 of 58 deleted** while cheerfully reporting the strip had worked. A pass that
   half-applies and says so only in a count is exactly why this ran dry first.
2. **The cleanup ate a real instruction.** Removing "trailing safety./access. steps" after the
   strip deleted `safety.dock_plug_back` — *"Plug the base station back in once everything
   you washed is dry"* — the STATION procedure's closing step, on 2 cards. Now only
   `access.off_dock` is removed, and only when everything after it is a safety closer.

### ✅ s60_pro RESOLVED — it is a DEFECT, not a special case

⚠ My held-out reasoning was wrong, and Chris's memory of a platform match is what broke it:
*"i matched the S60 to the Z60 ... and the S60 roller to the mobious 60."* The recorded lineage
names a different parent, but the method was right and the cluster is real.

`STATE-dreame-manual-corpus.md` records two things I had not applied:

* **Every Dreame model ships in THREE DOCK CONFIGURATIONS** — 基础水箱版 (basic water tank),
  上下水版 (plumbed), 超薄上下水版 (ultra-thin embedded). *"The parenthesised descriptors are
  DOCK configurations, not robots."* So s60_pro's five models are ONE robot in three docks, not
  two hardware states. The onboard box is a property of the ROBOT and is on all five.
* **S60 Pro Roller is handed down from X60 Pro 滚筒版** (33000Pa vs 36000Pa). Not Z60 — and
  separately, **S60 Pro Disc = S50 Pro**, a DIFFERENT ROBOT under the same marketing name, which
  the catalog already separates as `s60_pro_disc`.

The corpus then settles it outright. Every sibling on that platform carries the SAME station card:

```
x60_pro  x60_pro_roller  s60_pro_roller  s60_premium_roller
mobius_60  v60_mobius  z60_ultra_roller_complete
      station_tank > remove > pour > rinse_plain > wall_tool_suitable > tank_refit

s60_pro    off_dock > robot_box_out > robot_box_pour > ...      <- SOLE OUTLIER
```

`s60_pro_roller` (r500b1, "S60 Pro Roller") and `s60_pro` (r500b, "S60 Pro (Roller)") are the
same machine, and the twin has the correct card. So **s60_pro's dirty card is missing its station
phase** — the same defect class as the s10 splice, with the fix sitting in its own twin.

DISPOSITION: strip the robot box like the other 34, and author the station phase from the
cluster-standard shape. Not a special case; a gap. **Still unapplied — the strip would leave it
empty until the station phase lands, so the two go together.**

### ⛔ superseded reasoning below (kept so the wrong turn is visible)

Chris: *"s60 is an exception with a special case."* Its five models are not one hardware state:

```
S60 Pro (Automatic Water Supply and Drainage)  x2   PLUMBED - no tanks at all
S60 Pro (Roller) / (Roller Drainage)           x3   roller, carries the onboard box
```

Its `dirty_water_tank` card is *entirely* robot-box, so a blanket strip would leave the roller
variants with no used-water guidance while the plumbed pair should have none at all. Needs a
per-variant decision. **Untouched by this pass.**
