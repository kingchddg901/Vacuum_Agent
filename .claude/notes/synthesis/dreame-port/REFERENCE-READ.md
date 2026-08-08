# Reference read — what Dreame should be offering, from its source

**Full-sight answer key.** Written by the coordinator with everything visible
(including `adapters/eufy/`, `adapters/roborock/` and `dispatch_engines.py`),
**before the blind builders returned**, so it can be compared against them
without hindsight. The blindness imposed on the builders is an instrument, not a
claim about how porting works — a real porter reads everything.

Source: `dreame_vacuum` v1.0.11 (Tasshack), installed on the box.

---

## 1. Dispatch — `dreame_vacuum.vacuum_clean_segment`

Target: `entity.domain: vacuum`. Fields, verbatim from `services.yaml`:

| field | required | type | bounds |
|---|---|---|---|
| `segments` | **yes** | object | list or scalar (`[3,2]` or `3`) |
| `repeats` | no | number | 1–3 |
| `suction_level` | no | number | 0–3 |
| `water_volume` | no | number | 1–3 |

Positional parallel arrays, index-aligned by room. VA's existing
`dreame_room_clean` template already emits exactly this and is verified
conformant against both the installed copy and upstream `master`.

## 2. Vocabulary — `dreame/types.py`, and this is the part a porter must NOT invent

```
DreameVacuumSuctionLevel:  QUIET=0  STANDARD=1  STRONG=2  TURBO=3   (UNKNOWN=-1)
DreameVacuumWaterVolume:            LOW=1  MEDIUM=2  HIGH=3         (UNKNOWN=-1)
```

Note the asymmetry that a careless port gets wrong: **suction is 0-based, water
is 1-based.** There is no water `0`; "no water" is not a volume, it is the mop
pad being absent (`DreameVacuumWaterTank`: NOT_INSTALLED=0 / INSTALLED=1 /
MOP_INSTALLED=10). A brand config that maps an "Off" water level to `0` emits a
payload outside the declared selector.

Four suction levels against Eufy's four (`Quiet / Standard / Boost / Max`) — a
clean 4↔4 positional mapping where two names coincide (`Quiet`, `Standard`) and
two do not (`Boost`↔`STRONG`, `Max`↔`TURBO`). **Map by POSITION and meaning, not
by word.** There is no `Turbo` in Eufy's list, so no direct collision today, but
the general hazard stands: Dreame's `TURBO` is its MAXIMUM, and any brand using
`Turbo` as a mid-tier would mis-map silently into full power.

## 3. Capabilities — real for this brand

- **mop: yes.** States `MOPPING` and `SWEEPING_AND_MOPPING`; `mop_pad_humidity`,
  `mopping_type`, `self_clean_area` selects; `CONSUMABLE_MOP_PAD`.
- **water control: yes.** `water_volume` select and a wire field.
- **per-room settings: yes, and this is the richest of the three brands.** Suction,
  water and repeats all reach the wire PER ROOM. Eufy carries per-room settings as
  rows; Roborock collapses to a batch scalar; Dreame is the only one where the
  framework's per-room run profile survives intact to the device.
- **cleaning sequence: yes** (`switch.cleaning_sequence`, `select.order`) — Dreame
  exposes per-segment ORDER as an entity, which neither shipped brand does.

## 4. Entity surface

`vacuum.<name>` plus, relevant to VA: `select.<name>_suction_level`,
`select.<name>_water_volume`, `select.<name>_cleaning_times`,
`select.<name>_mopping_type`, `select.<name>_mop_pad_humidity`,
`select.<name>_selected_map`, `select.<name>_order`, `select.<name>_name`,
`switch.<name>_cleaning_sequence`. Lifecycle states map through
`STATE_CODE_TO_STATE` onto HA's standard `cleaning / docked / idle / paused /
returning / error`.

## 5. What it should NOT declare

- **No CV segmenter.** Dreame manages segments natively —
  `vacuum_request_map`, `vacuum_rename_segment`, `vacuum_merge_segments`,
  `vacuum_split_segments`. Rooms arrive already identified. `mapping.
  segmenter_engine` resolves to the noop fallback, and a Dreame adapter needs
  `mapping.segment_primitives` **not at all**.
- **No maintenance component catalog, no water model catalog, no model catalog,
  no upkeep guides.** Content, not contract; the conformance suite `pytest.skip`s
  those shape tests when a brand declares none.

## 6. The one thing that WILL bite — and it is the known fossil

Dreame must declare its **own** `room_profiles` vocabulary. The framework's
in-code catalog is Eufy's, so a brand that omits the block inherits `Boost` and
`Max` — words Dreame's device does not use. Worse than cosmetic: a room created
from the inherited default stores `fan_speed: "Max"`, Dreame's declared options
never contain it, the card's chip rows match nothing, and
`per_room_live_settings` filters the value out so **no suction is applied at
all**. That is the Roborock incident (dev doc 21 §7) reproduced brand-for-brand.

This is the seeded finding of the adapter-boundary sweep, seen from a third
angle: import leak, behavioural fossil, and now a predicted failure for the next
brand to arrive.

## 7. Prediction against the blind builders

If the guide works, both builders should independently arrive at: the four
dispatch fields with correct bounds, a 4-level suction map to 0–3, a 3-level
water map to 1–3, mop and water capabilities true, noop segmenters, and their
own declared room-profile vocabulary. The two most likely misses are the
**water 1-based floor** (mapping an "Off"/"None" level to 0) and **omitting
`room_profiles`**, which the guide warns about in step 4 but which requires
reading that warning carefully. A CV segmenter appearing in either output is not
a miss — it is evidence of copying Eufy.
