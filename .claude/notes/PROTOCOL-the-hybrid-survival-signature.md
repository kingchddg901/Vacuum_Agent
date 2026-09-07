# Hybrid survival: a dual-labelled thing escapes every single-axis sweep

**Status:** PATTERN + a working detector, 2026-09-07. Cost three sweeps before it was named.

Chris, after the 2-in-1 water card survived two deletions:

> we already dropped dust box but the water tank saved it, then the "special case" saved it
> when we dropped the water tank

and, from his thread with GPT, the compressed form:

> I'm not X, I'm Y. — Fine, survive the X sweep.
> I'm not Y, I'm XY. — Fine, survive the Y sweep.
> Then the ontology catches up: X is gone. Y is gone. XY exists only because it was dodging
> both classifications.

## The case that produced it

The Dreame 2-in-1 is ONE physical part on the robot holding both a water tank and a dust box.

```
dust box retired (folded into filter)   -> survived: "I'm a water tank"
robot water tanks deleted               -> survived: "I'm a 2-in-1 special case"
```

That second exclusion was real — it was written for the SPLIT, where emptying IS correct when
the tank is the bin — and it was carried into a DELETION pass without re-reading what it was
for. An exclusion outlives the reason it was written.

## ⚠ The half the taxonomy framing does NOT catch

The cure as stated is: stop asking *"which bucket is this in?"* and ask *"does this still
represent a concept we intend to ship?"* That is right, and it would not have been enough here.

Four families (`e12` `e20` `e20_plus` `f20`) held `clean_water_tank` as
`shares_with: "dustbin"` — **no steps of their own**. `famload.keys_of()` returns an empty step
list for a share-shaped record, and every target test written that day was `keys_of(...)[0]`. So
those four were invisible to three passes at once. **100 records corpus-wide are share-shaped.**

> Asking the right question of an enumeration that cannot see the object still returns the wrong
> answer.

So the signature has two halves, and the second is mechanical:

1. **Sweep by CONCEPT, not by label.**
2. **Prove the enumerator can see every record shape** before trusting a sweep's scope. Ablate
   it: feed it one record of each shape and check the count.

Same class as [[feedback_partial_guard_blind_spot]] — a guard that exists reads as complete.

## The detector

An **in-scope component whose content is borrowed from an out-of-scope donor**. That is a retired
concept kept alive by a label that survived. Run over `scope.json` + the share graph:

```
filter              <- dustbin            81   DELIBERATE - the documented dust-box fold
mop_compartment     <- mop_pad_holder      1   FALSE POSITIVE - see the discrimination below
base_station_filter <- dust_bag            1   ⛔ REAL
```

### The discrimination it needs: is the borrowed content ACCESS or the TASK?

* `s70_roller / mop_compartment` borrows 6 roller-removal steps from `mop_pad_holder`, but the
  TASK is `mop.compartment_wipe` — the roller work is just how you REACH the compartment on a
  roller machine. Structurally the same as the normal `assembly_out > compartment_wipe >
  assembly_click_in`. **Borrowed access is fine.**
* `x40_pro / base_station_filter` ships `tank_cover_off > out_discard > station_dust_wipe >
  new_in_cover_close` — **3 of 4 steps are dust-bag REPLACEMENT**, a different task from wiping a
  filter. The other 25 `base_station_filter` cards are a single step, `station_dust_wipe`.
  **A borrowed task is the hybrid.**

And the tell that makes it matter: `dust_bag` has real steps in 10 families and is OUT of scope,
so none of them emit. **`x40_pro` is the only place dust-bag replacement reaches a shipped card.**

## When to run it

After ANY component retirement, fold, or scope change — that is exactly when a hybrid is created,
and it will not show up as a failure anywhere. Nothing goes red; the obsolete concept simply keeps
shipping under a name that is still allowed.

## Open

`x40_pro / base_station_filter` is unfixed — Chris's call, since the remedy is either trimming it
to `station_dust_wipe` like the other 25, or deciding dust-bag replacement is worth scoping in on
its own merits. `govac_300` also carries a pre-existing `filter -> dustbin -> filter` cycle; it
resolves and `dustbin` does not emit, so it is inert.


## Corollary: REACHABILITY IS NOT SCOPE MEMBERSHIP

Chris: *"the out of scope keys go away they are causing issues but we cant break the output
doing this."*

They cause issues because they are the hiding places — `dust_bag`'s own keys are why `x40_pro`
shipped bag replacement under a filter label, and 44 of the 171 one-use keys sat in components
that can never emit: bespoke vocabulary carrying no coverage.

**But an out-of-scope component can still reach output.** `filter <- dustbin` is the documented
dust-box fold and covers 81 families, so dustbin's keys emit. The naive test —
*is this component in `scope.json`'s keep list?* — said **108 keys removable**. Share-resolved it
is **103**, and the difference is five dustbin keys that in-scope filter cards borrow. Deleting
them would have broken 81 real cards.

```
A key is removable only if EVERY component referencing it is, in its own family,
neither in scope NOR lent to an in-scope component.
```

Removed: 103 reachable only through a dead component, plus 76 defined and referenced nowhere at
all. **Phrase table 612 -> 433 keys, 298 records stripped.**

### The gate that made it safe

The claim being made is *"these keys cannot reach a card."* So the test is not a review, it is a
hash:

```
emitted library BEFORE  2278229eaecfff0a
emitted library AFTER   2278229eaecfff0a      BYTE-IDENTICAL
```

If one byte had differed, the premise was false by definition and the script says so rather than
reporting success. `git status` on the emitted library shows no diff at all — the cleanup is
invisible downstream, which is exactly what "unreachable" has to mean.

**Generalise it:** any cleanup justified by "this is dead" should be gated on the output being
byte-identical, not on the reviewer agreeing it looks dead.

### Tally: the share shape broke five measurements in one session

1. the robot-tank deletion — missed 4 share-shaped 2-in-1 cards
2. the 2-in-1 deletion — same 4, again
3. the gap fill — same 4, again (harmless: it did not overwrite them)
4. `clean vs dirty` counts — reported `omni_m30s` as clean-without-dirty; its dirty card *shares
   from* clean, so `keys_of()[0]` read it as absent
5. this pass — the naive split would have deleted five live dustbin keys

Every one came from `famload.keys_of(...)[0]`, which returns an EMPTY step list for a
share-shaped record. 100 records corpus-wide are share-shaped. **Any corpus question — a sweep, a
count, a reachability test — must resolve shares first, or it is answering about a different
corpus than the one that ships.**
