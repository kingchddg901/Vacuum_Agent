# Clean / dirty water tank — the split, and the gap underneath it

**Status:** analysis settled 2026-09-07, **nothing applied yet.** Chris's spec, his rulings,
and the dead ends that cost a loop today. Read this before touching either component.

## There are TWO pieces of work, not one

| | families | what it is | needs |
|---|---|---|---|
| **THE SPLIT** | **99** | families that HAVE a clean-tank card, and it carries merged dirty-tank behaviour | nothing new — fix in place |
| **THE GAP** | **137** | families with a dock dirty tank and **no clean-tank card at all** | authoring from manuals |

I repeatedly conflated these. They are different jobs of different sizes.

## The numbers (280 families)

```
dirty card, NO clean card    142     ← 5 master/plumbed held out ⇒ 137 real
both                          25
clean only                    74
neither                       39
                             ───
dirty cards total  167       clean cards total  99
```

## What the merge actually is

The vendor's combined section — the X20 Max heads it **"Cleaning the Clean & Dirty Water
Tanks"** — was lifted into `clean_water_tank`. So the CLEAN card carries the COMBINED
procedure:

```
clean_water_tank, 99 blocks:  EMPTY/POUR 85%   RINSE 66%   DRY 64%   REFILL 8%
                              55 distinct shapes across 99 blocks
dirty_water_tank, 167 blocks: EMPTY 100%  RINSE 98%  TOOL-CLEAN 84%   ← already correct
```

Showing through literally: **`dirty.rinse_plain` sits inside 4 clean-tank blocks** —
`d20_pro`, `f10`, `f10_plus`, `s10`. A dirty-namespace key in a clean card.

**The dirty side needs nothing.** Its top shape is already Chris's spec: remove → pour →
rinse → clean the inner wall → refit (×46).

## Chris's spec

> Clean water: access, remove, **refill**, replace, reverse access
> Dirty water: access, remove, **empty, clean**, replace, reverse access

Plus his ruling on the clean side: *"clean if needed. its a clean water tank separate from
the dirty side by design but could collect scale or solution residue."* So the cleaning is
**gated**, not dropped and not unconditional.

Evidence the gate is right, all from our own table:

| key | users | says |
|---|---|---|
| `note.float_gentle_clean` | 14 | "don't force the float **while cleaning**" — presupposes cleaning happens |
| `note.mildew_if_left_wet` | 7 | standing water turns smelly |
| `note.no_vinegar_in_tank` | 1 | never descale it — so scale is known and NOT user-treatable |
| `note.cleaner_manual_recommended` | 2 | residue from non-approved solution |
| ~~`tank.air_hole`~~ | 42 | **REMOVED from this table — see below.** It is a vent-unblocking step, not evidence about cleaning the tank body |

### ⚠ `tank.air_hole` is NOT evidence for gating the tank clean

I originally listed it above as "the gated idiom already ships". Chris flagged it:

> "You mentioned clean air hole as an idiom that seems overly precise for needing to clean
> the tank. That is a specific mechanism."

Correct. *"If water runs out slowly or spreads unevenly, clean the air hole in the water
tank's cap"* is a **vent unblock**: specific symptom (flow is wrong), specific part (the
hole in the cap), specific cause (airlock — a blocked vent stops the tank gravity-feeding).
It says nothing about washing the tank body.

Using it as support was borrowing the *form* of a sentence as evidence for an unrelated
decision — the same error as "these keys are welded, therefore the parts are inseparable".
**Form is not evidence.**

The gate on tank cleaning stands on the rows that are actually about the tank body:
`note.float_gentle_clean` (presupposes cleaning), `note.mildew_if_left_wet`,
`note.no_vinegar_in_tank`, `note.cleaner_manual_recommended`.

**What `tank.air_hole` IS — and it is not a station part.** Measured:

```
                          users   station   robot-only
tank.air_hole              41        1          40
tank.air_hole_inlet_lid     6        0           6
```

It belongs to the **robot-mounted tank** population — the machines without a self-washing
dock. So it has no place in the station clean-tank card at all. Chris spotted this from the
wording alone: *"that reads as robot based internal tank, one of the ones without self
wash."*

It is still a real, distinct item for the families that DO have a robot tank, and arguably
an operational one, since "water runs out slowly" is noticed while mopping rather than
fired by a schedule.

⚠ I also misquoted it as "the water tank's **cap**". It says **cover**. My earlier read was
truncated mid-word and I completed it from the robot-tank picture already in my head.

## The two hardware populations are already clean in the corpus

```
tank.remove       21 users   0 station   21 robot    "Take the clean-water tank out of the ROBOT."
tank.refit        10 users   0 station   10 robot
tank.clean_out    15 users  15 station    0 robot    "…out of the BASE STATION."
tank.clean_refit  24 users  24 station    0 robot
tank.clean_fill    6 users   6 station    0 robot
```

**Zero cross-contamination.** Picking the right pair per family is mechanical — station
families take the `clean_*` keys, robot-tank families take `tank.remove` / `tank.refit`.
Do not blanket-apply either set.


## Vocabulary that already exists (no authoring needed for the split)

`tank.clean_fill` (6) · `tank.clean_fill_max` (1) · `tank.fill` (1) · `tank.clean_refit` ·
`note.no_hot_water` (7) · `tank.air_hole` (42). 17 keys name the clean-water tank; 6 carry
a fill action.

Vendor wording confirmed identical across three manuals — **l20 p8, matrix10 p7,
s10_pro_ultra p9** all say *take the clean water tank out of the base station and fill it*,
which is `tank.clean_fill` verbatim. s10_pro_ultra also carries the hot-water caution
(`note.no_hot_water`).

**Leave the 17 two-in-one blocks alone.** There the tank physically IS the dust box
(3c's parts list: 二合一水箱（水箱+尘盒）) and emptying it is correct.

## THE GAP — why 137 families have no card, and why that is not a hardware question

Chris, and it is airtight:

> "Why would you have a dirty base station tank, if you didn't have a clean one?"

A dock with a dirty-water tank washes mop pads. Washing consumes clean water. That water is
**stored or plumbed — there is no third source**, and the robot's onboard tank is what the
dock *refills*, not a supply for it.

**So a dock dirty tank IS evidence of a clean-water supply.** The 137 have the tank. The
missing card is a **lift gap**, not a fact about the machines. Do not re-open this as "do
they have one".

That also explains the shape of the 99: where a vendor wrote a combined section it got
lifted (merged, into the clean card); where the vendor split the sections, only the dirty
half was picked up and the clean half was lost entirely.

## WHY the lift missed it — and the narrow scope of that (Chris, 2026-09-07)

The refill instruction is not missing because the lift failed at reading. It is in the
manual, in a **different chapter**:

```
l20        p8  fill the clean tank    → Use / Setup chapter
           p10 clean the dirty tank   → Routine Maintenance chapter
matrix10   p7  fill the clean tank    → Use / Setup chapter
           p8  clean the dirty tank   → Routine Maintenance chapter
```

The lift harvested **Routine Maintenance**. That is why refill is 8%, and why 137 families
have no clean-tank card.

The dirty side only *looks* correct by luck: emptying is documented **inside** the cleaning
procedure, so the operational action came along free with the routine one.

### ⚠ Do NOT generalise this into a corpus-wide defect

I did, and Chris corrected it:

> "The issue is for ninety nine percent of what we do, routine is the same as use. A dirty
> filter gets cleaned because it's dirty or because the schedule says to. A brush gets
> maintained because it got jammed or because the sensor says to."

The trigger differs everywhere; the **action** almost never does. One card serves both.

**The distinction only bites where the two triggers call for DIFFERENT ACTIONS**, and that
is the water tanks and essentially only the water tanks:

| | flag trigger | schedule trigger | same action? |
|---|---|---|---|
| clean water tank | low → **fill** | → wash | **no** |
| dirty water tank | full → **empty** | → clean | no, but fused in one vendor section |
| filter, brushes, sensors, everything else | → clean it | → clean it | **yes** — one card |

### The dust bin is settled, and today's strip stands

Chris: no sensor, so there is no operational trigger to serve; its access already lives on
the filter card; on auto-empty machines it is near-never needed; and a user who fills a
dust bin knows to empty it. The 2026-09-06 removal of `bin.empty` from filter cards is
**not** reopened by any of this.

## ⛔ DEAD ENDS — walked today, do not walk again

1. **Searching `dirty_water_tank` blocks for clean-tank content.** Result: **0 of 168**,
   with the probe ablated (17 keys name the tank, 6 have fill actions, so it can bite). The
   merge is NOT in the dirty cards. It is in the clean ones.
2. **Matching the string "clean water" to find the part.** Gives **158 false positives** —
   `dirty.rinse_plain` is *"Rinse the tank with clean water"*, where clean water is the
   **medium**, not the component. Match `clean[- ]water tank` or a fill verb, never
   "clean water".
3. **Using corpus absence as evidence.** "0 master families have a clean-tank card, zero
   counterexamples" is **circular** — a family lacks a card because nobody authored one.
   That is measuring the backlog and reporting it as hardware.
4. **"Station machine ⇒ has a clean water tank" as a creation gate.** The Master line is
   plumbed and tankless — see
   [`FINDING-plumbed-variants-have-no-clean-tank.md`](FINDING-plumbed-variants-have-no-clean-tank.md).
   The screen is **negative**: look for 上下水 / water hookup / "automatically refill the
   robot's water tank", and only then exclude. `l20` carries a tank AND a hookup kit, so
   plumbing alone does not exclude.

## Held out, deliberately

The 5 master/plumbed families — `clean_master_x60_pro_steam`, `g20_master`, `master_one`,
`master_pro`, `x40_master`. Chris: *"they are possibly a variant of themselves, but we're
not looking at them right now."*

## Next action when this resumes

Build **the split** (99 blocks): refill leads, cleaning gated behind the `air_hole`-style
condition, dirty side untouched, two-in-ones untouched. Red-before / green-after audit.
**The gap (137) is a separate, larger job** and has not been scoped.
