# The 58 robot-tank families, walked. They are a COHERENT population.

**Status:** MEASURED 2026-09-07 from the families' own manuals. This **unblocks the paused
clean/dirty split** — see [`STATE-clean-dirty-water-tank-split.md`](STATE-clean-dirty-water-tank-split.md).

Chris: *"ok this sucks we need to walk thier manuals"* / *"NOT ALL 280 the 58"*.
Tool: `authoring/compose/tools/walk_manuals.py`, cache `tools/manual_signatures.json`.

⚠ These are the numbers from the **fifth** run. The first four were each wrong in a
different way — see "Five tooling faults" below, which is the more useful half of this note.

## The answer

52 of the 58 have a manual the scanner can actually read. Of those 52:

| what the manual shows | families |
|---|---|
| **no dock at all** | 36 |
| **auto-empty-only dock** — dust bag, filter, vents; no water hardware | 15 |
| **a station water tank** | **1** — `s30`, and it does not belong in the 58 |

**51 of 52 have no station-side water tank.** Their clean-water card is robot-side because
the hardware is robot-side. The 58 is not the impure set `s10` made it look like — `s10` is
odd in its **dirty** card (a splice, see
[`FINDING-s10-spliced-dirty-tank-and-tiering.md`](FINDING-s10-spliced-dirty-tank-and-tiering.md)),
and its own manual (r2382a) confirms station=0.

This is the tier Chris called before the walk: *"base no station, pro dust empty only, ultra
tanks, thin embedded plumbed."* The auto-empty band is real and it is the `_plus` / `govac`
line — `c20_plus`, `d10_plus_gen_2`, `d15_plus`, `d20_pro_plus`, `e30_pro_plus`, `f10_plus`,
`f20_plus`, `govac_200`, `govac_200_kit`, `govac_300`, `govac_300_kit`, `l10s_plus`,
`l10s_plus_se`, `l40_plus`, `s10_plus`. Every one: **clean tank 0, dirty tank 0, washboard 0,
plumbed 0**, dust bag 7–10.

### `s30` is not a member — it is THE GAP wearing a clean-card label

The real Dreame S30 (`dreame.vacuum.r2485`) is a full washing station: station 81, clean tank
10, used tank 15, washboard 10. Our composed `s30` also has `washboard`, `base_station_filter`
and a station-side `dirty_water_tank`. But its `clean_water_tank` card is the **robot's**
mopping-module tank:

```
off_dock → mop.module_release → tank.inlet_cover_off → POUR OUT
         → tank.inlet_cover_on → tank.air_dry_refit → mop.module_refit
```

So the station's own clean-water tank was never authored, and the card under that name
describes a different part. `s30` belongs in **THE GAP**, not the split — and under Chris's
ruling (*"the robot's water tank shouldn't be in our maintenance cards"*) the module-tank card
is a candidate for removal, not for conversion to a fill card.

## The vendor states our split spec verbatim

`d20_pro_plus` (r2566a), on its robot tank:

> Press the release clip to remove the water tank. Open the water inlet lid, fill the tank
> with water, and close the lid tightly.

remove → open → **FILL** → close → refit. That is the clean-water card Chris specified,
written by Dreame. It also says **lid**, not cap — independent support for the lid/cover
wording already fixed. Its dock parts list is *Ramp Extension Plate, Auto-Empty Vents, Cover,
Dust Bag Slot, Filter* — no water hardware.

## ⚠ COUNTS LOCATE, SENTENCES DECIDE — it bit 7 times

Eight families scored 1–10 `base station` hits. **Seven were the vendor using "base
station/charging dock" as a synonym for the CHARGING DOCK** — in energy-saving mode, fast
mapping, and regulatory power-consumption boilerplate. `l10s_pro_gen3` prints the equivalence
outright: `Robot Base Station/Charging Dock`. `d20`'s two hits are battery-charging specs.

```
d15=1  d20=2  f10=1  govac_200_lite=1  l10s_pro_gen3=4  l10s_pro_gen_3=4  l40=1
   -> NOT a servicing dock
d20_pro_plus=10  -> real (Ramp Extension Plate, Auto-Empty Vents, Dust Bag Slot)
```

Same failure class as the X50 Master's single "clean water tank" hit. **Never rule on a
`station` count under ~20 without reading the sentences.** A cheap discriminator that worked:
count dock-only vocabulary (`dust bag|auto-empty|ramp|install the base`) — `d20_pro_plus`
scored 20, every false positive scored 0–1.

## Five tooling faults, and why they are one fault

Chris: *"there was so many flaws with the extraction we would need to redo the full set to be
sure."* He was right, and this is the list. **Every one of them forged an all-zero
signature** — which is indistinguishable from the genuine dockless machine the walk exists to
find. The zero is the dangerous value here, so each fault manufactured the finding.

| # | fault | what it did |
|---|---|---|
| 1 | **LANGUAGE** — `SIGNALS` is English + Chinese only | a Japanese, Ukrainian or image-only manual scores 0 on every term. 5 families. Surfaced only because Chris queried the Deerma S30 by name. |
| 2 | **BIGGEST-FILE** — `pick()` took the largest matching PDF | chose a **63 MB image scan of a Deerma S30** over the real 4.1 MB `dreame.vacuum.r2485`. File size is a proxy for image count, not relevance. |
| 3 | **SUBSTRING** — `model_id in basename` | `dreame.vacuum.p2028` matched the `p2028a` file; `z10_pro` was scored on `l10_plus`'s manual. **180 id pairs corpus-wide are a prefix of another id.** |
| 4 | **RELEVANCE** — *exposed by fixing 2 and 3* | `z10_pro` and `vacuum_mop_2_lite` then resolved to **warranty cards**: readable, English, and zero on every hardware term. |
| 5 | **SUBSTRING, AGAIN — in my own fix** | I kept a `full dotted id in basename` clause for short ids. `dreame.vacuum.r2228` is a substring of the `r2228d` file, so `s10` was scored on a variant its family does not contain — and briefly read as a **water station**, contradicting the confirmed s10 finding. |

Fault 5 is the one to remember: **the repair reintroduced the defect it was repairing**, in
the branch added for a different case. It was caught only because the new result contradicted
an already-established finding. There is now a regression check that ablates it — it asserts
0 families whose selected manual does not carry the exact id it was matched by, and it prints
that the old rule scored `s10` on `r2228d`.

Current picker: rank candidates by **vendor lineage** (`dreame`/`mova`/`trouver`) then match
type, never by size; match a 4+ char id token on a **whole-token** boundary and a short one
(`ijai.vacuum.v2`) as the full id with no alphanumeric after; reject any document whose script
is not Latin/CJK, that has <500 alpha chars, or that names fewer than 2 maintenance parts.
Each record carries `readable`, `matched_by`, `script`, and what it `skipped`.

**An all-zero signature means "no dock" ONLY when the record says `readable: true`.**

## The 6 still unusable, and 5 with weak provenance

```
UNUSABLE  d9, f9                                    no manual mapped
          d9_max_gen_2_se, l20s_plus, lds_finder    only manual is Japanese / Cyrillic
          vacuum_mop_2_lite                         image-only, no extractable text
WEAK      d9_plus d9_pro e30_pro_plus f9_pro z10_pro   PDF resolved by FAMILY NAME, not a
                                                       model id - plausible, unverified
```

`e30_pro_plus` (station 52) is the only weak-provenance family carrying a conclusion; the
other four are zeros and would need verifying before being quoted as dockless.

## Three catalog defects surfaced on the way (separate work)

**1. Three model ids are not Dreame lineage.** MOVA and Trouver *are* Dreame's own sub-brands
and belong. Deerma (德尔玛) and `szkj` are different companies that got in on a SKU-string
match — Chris: *"that is a misspelling look at the name it was a bad search that found a
diffrent model and vendor"* (right about the cause, not a misspelling):

```
deerma.vacuum.a2403  "S30"    family s30    <- sat beside the real dreame.vacuum.r2485
deerma.vacuum.a2404  "X70"    family x70    <- SOLE member; whole family is foreign
szkj.vacuum.fc01eu   "S10T"   family s10t   <- SOLE member; same
```

Vendor spread of the catalog's 741 ids — dreame 587, mova 102, xiaomi 25, trouver 13,
ijai 11, deerma 2, szkj 1.

**2. Three families differ only by punctuation** — near-certain duplicates:

```
aqua10_pro_roller (r5064u)  |  aqua_10_pro_roller (r5064t)
aqua10_roller (r9533a,h,t)  |  aqua_10_roller (r501bt)
l10s_pro_gen3 (r9542b)      |  l10s_pro_gen_3 (r9542h)
```

**3. A family can span hardware states.** `s10` holds `r2228`, three `r2382*` and
`ijai.vacuum.v17`; the S10 tiering note already shows that line spanning no-station,
full-washing-station and plumbed. So a per-family signature is a **sample**, not a
description of every member — which is exactly what made fault 5 hard to see.

## What to do

- **Proceed with the split.** The clean-water card stays robot-side for these families and
  becomes a fill card. The walk asked the blocking question and answered it.
- **Pull `s30` out of the split scope** and put it in THE GAP.
- The 6 unusable need a manual in a covered language, or a hand read.
- Catalog defects 1–3 are their own change against `upkeep_catalog.py`.
