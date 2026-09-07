# Not every station machine has a clean water tank — the Master line is plumbed

**Status:** established 2026-09-06. Chris: *"ah master variant is plumbed."*
**Read this before creating a `clean_water_tank` block for any family that lacks one.**

## The fact

A base station does **not** imply a user-filled clean water tank. The **Master** variants
are plumbed: mains water feeds the station through a hookup kit, and the station refills
the robot's onboard tank automatically. There is nothing for the user to fill.

Evidence, three independent manuals:

| model | 清水箱 / "clean water tank" | plumbing |
|---|---|---|
| r2310b/d/e/f/g — Master Pro, Master One, X40 Pro, X30 Pro | **0** in all five | 上下水模块 present; "the robot's tank is auto-refilled through the base station" |
| X40 Master (RLX73CE) | **0** | water hookup ×4, auto refill ×2, drain ×18 |
| X50 Master (R9434H, R9434J) | 1 — a **boilerplate caution** about what may be added, not a procedure | water hookup ×4, auto refill ×3; "close the main water valve… install the water hookup accessories for auto refilling and draining" |

The X50 Master case is the one to be careful with: the phrase "clean water tank" *appears*,
so a text search finds it. Reading it shows a safety caution, not a part with a refill
step. **Presence of the phrase is not presence of the part.**

## ⚠ What is NOT evidence — Chris caught this

> "dirty only is because we have not split yet[,] cyclical reasoning"

Correct. I originally supported this finding with a corpus count — *"5 master-named
families have a dirty tank and no clean tank, and 0 master-named families have a
clean-tank card, zero counterexamples."* **That argument is circular and is withdrawn.**

A family is "dirty-only" because **nobody has authored a clean-tank card yet**, not
because the machine lacks the tank. The whole clean/dirty split is the work that has not
been done. Counting its absence and calling the count evidence is measuring the backlog
and reporting it as hardware.

The same applies to the 142. That number describes our authoring state. It says nothing
about which of those machines have a clean water tank.

**Only the manual evidence above supports this finding**, and it stands on its own: five
r2310 documents with 清水箱 = 0 while carrying 上下水模块, plus X40 Master and X50 Master.
That is the source speaking about hardware, independent of anything we have or have not
written.

The five master-named families currently lacking a clean-tank card are
`clean_master_x60_pro_steam`, `g20_master`, `master_one`, `master_pro`, `x40_master` —
listed as *where to look*, not as evidence.

## Why it matters — the near-miss

The clean/dirty water-tank split was about to use this gate:

> a family with a dirty-water card and a base station also has a clean water tank, so give
> it a clean-water card built from `tank.clean_fill` + `tank.clean_refit`

That would have shipped a **refill procedure for a tank that does not exist** across the
whole Master line. It surfaced only because Chris asked to see the two ambiguous families
and then asked about their **siblings** — `master_pro` is `dreame.vacuum.r2310`, and
r2310e / r2310f (X40 Pro / X30 Pro) are the same base model with suffix variants, already
on disk from an earlier question.

## The gate that is actually safe

"Station machine" is **not** sufficient. Require evidence that the family HAS the tank:

- its manual's **parts list** names a clean water tank, **or**
- its manual has a *procedure* — "take the clean water tank out of the base station and
  fill it" (l20 p8, matrix10 p7, s10_pro_ultra p9 all say exactly this), **or**
- it already has a `clean_water_tank` block — the 74, proven by construction

Disqualifiers: a water hookup / 上下水 module, "automatically refill the robot's water
tank", or a clean-tank mention that is only a caution.

⚠ `l20` is what stops this becoming "plumbed ⇒ no tank": its parts list carries a Clean
Water Tank **and** a "Water Hookup Kit for Auto Refilling and Draining". Plumbing can be an
*option alongside* the tank, not only a replacement for it.

## Consequence for the clean/dirty water-tank split

- **The 74 families that already have a clean-tank card** — safe to restructure (refill
  leads, cleaning gated). They demonstrably have the tank.
- **Every family without a clean-tank card** — NOT safe to fill blind, and note that this
  set is defined by our backlog, not by the hardware. Confirmed plumbed families must never
  get one. The rest need per-family evidence by the gate above, which means reading their
  parts list — the corpus cannot answer it, because the corpus is what is unfinished.
