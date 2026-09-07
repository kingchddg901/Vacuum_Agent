# `s10` has a dirty-water card for hardware it does not have — and the S10 tiering

**Status:** CONFIRMED 2026-09-07 from manuals Chris supplied. **Not fixed.**

## The defect

`s10`'s `dirty_water_tank` card describes taking a **used-water tank out of the base
station**. The S10 has no base station.

Its own manual (`s10_R2382K`) — counted across the whole document:

```
base station   0        used water tank  0
washboard      0        clean water tank 0
```

What it actually documents: open the **robot's** cover, press the clip, take the water tank
out, fill it, put it back. A robot-mounted tank on a machine with a charging dock only.

So the dirty card is a **splice** — content from a sibling model, which is precisely the
failure `DESIGN-composed-guide-architecture` exists to prevent. The 2026-09-07
station-access pass then compounded it by prefixing "Access the used-water tank in the base
station".

`s10`'s **clean**-water card is correct as robot-side. Only the dirty card is wrong.

## Where the splice came from — the S10 tiering is real

Chris: *"the tiering if the s10 is real and annoying."* Counted across five manuals:

| family (model) | product | base station | used tank | washboard | clean tank |
|---|---|---|---|---|---|
| `s10` (r2382k) | S10 | **0** | **0** | **0** | **0** |
| `s10_pro` (r2421) | S10 Pro Hot Water | 75 | 14 | 7 | 6 |
| `s10_pro_max` (r2360w) | S10 Pro Max Hot Water | 75 | 14 | 7 | 6 |
| `s10_pro_ultra` (r9312) | S10 Pro Ultra 2-roller | 83 | 15 | 10 | 7 |
| `s10_pro_ultra` (r2310b) | S10 Pro Ultra Ultra-Thin | 117 | 7 | 13 | **0** |

**One product name, three hardware configurations:**

1. **no station at all** — the base S10 alone
2. **station with clean + dirty tanks** — S10 Pro, Pro Max, Pro Ultra (r9312)
3. **station, PLUMBED, no clean tank** — S10 Pro Ultra Ultra-Thin (r2310b), consistent with
   [`FINDING-plumbed-variants-have-no-clean-tank.md`](FINDING-plumbed-variants-have-no-clean-tank.md);
   r2310b is in the same r2310 series as the Master line

The tier boundary is exactly between **"S10"** and **"S10 Pro"**, and every Pro variant has
the station tank the S10's card wrongly describes.

Also: r2421 and r2360w have **identical** counts, so S10 Pro and S10 Pro Max ship the same
manual content under different SKUs.

## ⛔ The heuristic that found this DOES NOT WORK — do not reuse it

I looked for "families with a dirty-water card but no station components in our corpus" and
got **15**. That list is unusable. Tested against manuals immediately:

```
s10          station=0     ← real
l10s_ultra   station=70, used tank=14, washboard=6   ← plainly a station machine
```

`l10s_ultra` was a false positive: it is a station machine whose washboard card we simply
have not composed. The heuristic measures **our backlog**, not the hardware — the same
circular reasoning Chris caught in the plumbed-variant note. Of the 15, only `s10` is
confirmed; the other 14 are unknown and each needs its own manual.

The reliable test is per-manual: count `base station` / `used water tank` / `washboard`
in the family's own document.

## Consequence for the paused clean/dirty split

`s10` sits inside the **58 robot-tank families** whose fate is the open question in
[`STATE-clean-dirty-water-tank-split.md`](STATE-clean-dirty-water-tank-split.md). It turns
out to be a station-less machine carrying a fabricated station card — so the 58 is **not a
clean population**, and members may be misclassified in either direction. The question
"should robot tanks have maintenance cards" cannot be answered from that set as it stands
without checking manuals.

## When it is fixed

- `s10/dirty_water_tank` should not exist. Confirm no other S10-tier content leaked in.
- `s10/clean_water_tank` stays, robot-side, and is a fill card under the split spec.
- Check the other 14 from the discarded list one manual at a time; do not bulk-act on it.
