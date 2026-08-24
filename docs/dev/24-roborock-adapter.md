# 24 — The Roborock Adapter

**Scope.** How the second brand answers [the contract](22-adapter-contract.md), and what it cost to
be second. Read [23 — The Eufy Adapter](23-eufy-adapter.md) first — this brand paid the
bill for the residual default described there.

Roborock had to say out loud everything Eufy gets for free by having been first. Three of its six
data modules exist only because a framework answer was Eufy's answer, and two more exist because of
the shape of the upstream HA `roborock` integration rather than the device. That is the useful lens
for the whole package — most of what looks like verbosity is a name Eufy already occupied.

---

## 1. What the adapter computes

`adapters/roborock/adapter.py::register_roborock_adapter_for_vacuum` computes six things at
runtime — the model profile, mop settability, dock capabilities, detected capabilities, resolved
entity ids, and the mop pre-call list — and otherwise emits a roughly 600-line literal dict into
`adapters/registry.py::register_adapter_config`. Nothing in the file executes during a clean; the
framework reads the dict.

Its only upward coupling is one row in `adapters/brands.py::BRAND_REGISTRARS`. Everything else is
downward, into its own package and four core helpers.

---

## 2. Identity is data, not a callable

The package declares `adapters/roborock/const.py::UPSTREAM_PLATFORMS` and core compares it against
the entity registry's `platform`. What it replaced was a per-brand detector — a function core
called in table order, which read the device registry's manufacturer and a model prefix — and the
deleted function is kept in place as a commented block so the next porter does not reinvent it.

The replacement is better evidence, not just a cleaner shape. `platform` is set by HA from the
providing integration's domain and is never blank; manufacturer and model are free text and are
routinely empty on real installs, which is why Eufy never had a detector at all.

**What it fixed is the more important half.** A function-pointer table lets a brand express
"probably me", and it had a default arm. Removing that arm is what let a Dreame stop being silently
registered as a Eufy.

---

## 3. The dock is resolved live, and three cheaper probes were measured wrong

`adapters/roborock/dock.py::dock_profile` reads the **second** device in the Roborock config entry —
the dock — takes its `model_id` integer, and runs it through python-roborock's own capability
table. This is the strongest work in the package, and its value is mostly in what it refuses.

Three cheaper probes were each tried against real hardware and each measured wrong:

| probe | why it fails |
|---|---|
| "a dock device exists" | satisfied on a charger-only S6 by a single drying binary sensor, admitted because the product schema declares the DPS |
| `model_id != o0_dock` | a dockless unit reports the string `"Unknown"`, not `"0"` |
| "probe for dock entities" | HA publishes a cleaning-brush countdown on any washable dock, even where the vendor's own support flag is false |

They over-report in **both** directions, so neither a presence test nor an absence test is safe.
Vendoring the library's no-dock set was also rejected: a copied vendor set goes stale silently,
which is the exact failure this module exists to prevent.

Two design properties follow:

- **The return is tri-state.** `None` means *undetermined*, never *no dock*, and falls back to the
  catalog's conservative default. A missing library, or a dock newer than the installed one, would
  otherwise decide a capability by accident.
- **Three flags are asked separately** — washable, dryable, collectable — rather than riding one
  blanket `has_dock`. An auto-empty dock collects but cannot wash; another washes but cannot
  collect. A blanket flag is not a simplification, it is a wrong answer on two dock types, and the
  wrong answer offers a mop wash on a dock with no water in it.

Every model profile in `adapters/roborock/model_catalog.py::MODEL_PROFILES` declares `has_dock`
False **on purpose**, as the undetermined-fallback only. The same robot model ships with several
station tiers, so a per-model dock column cannot answer the question and would diverge silently the
first time a model shipped with a different station.

---

## 4. Where the reverse port sent the bill

Five places where being second cost a declaration, a new name, or a change to core.

### The canonical name for water was already taken

Roborock's mop-intensity select is **not** mapped into the framework's existing `water_level`
entity role — the slot a porter would reach for. `core/capabilities.py::detect_capabilities`
derives station-water support from that slot's presence, so filling it with a robot-side mop select
reports station water on a dockless unit. The select is bound to a new role instead, and mop
support is asserted through a capability hint.

This is the clearest vocabulary collision the reverse port produced: `water_level` is *Eufy's
station-water sensor*, so the second brand's water control cannot use the canonical word for water.

### Completion could not use the framework's secondary signal

The framework's default secondary check is the cleaning target reaching a sentinel, which is what
Eufy declares. Roborock's current-room sensor reverts to the **dock room's name** at the end, never
a sentinel, so that check can never pass and a run would never finalize. Roborock keys on the
job-active binary clearing instead — it stays on through a mid-job recharge dock and clears only at
the true finish.

### An omitted engine declaration does not mean inert

`job_segmenter` and `mapping.segmenter_engine` are declared **explicitly** as no-ops rather than
omitted, because the framework's fallback for an absent job segmenter is Eufy's counter-plateau
detector. Omitting the block runs Eufy's algorithm over Roborock's counters and fabricates phantom
room boundaries — in the observed run trace, the only area plateaus were obstacle stalls.

This is the sharpest form of the failure mode: **an omitted declaration does not fail, it silently
runs the other brand's algorithm.**

### The room-profile catalog had to be declared in full

Omitting it — which this adapter originally did, on the documented reasoning that framework
defaults suffice — handed every Roborock room Eufy's display vocabulary. That shipped: a new room's
suction value was not in this brand's option list, so dispatch's option filter dropped it and an
unedited Roborock room applied **no suction at all**, while the card's strict equality chip row
rendered nothing selected.

The keys are deliberately kept identical to Eufy's; only the values differ. That is what lets a
stored room and the profile picker survive a brand switch. And empty is not absent:
`adapters/registry.py::register_adapter_config` fails an absent block as "not written yet", while a
per-key empty dict is a brand stating it has none.

### String error codes forced a change in core

Roborock declares error codes as lowercase enum strings. Core's three classification entry points
each opened by coercing the code to an exact integer and bailing on `None` — Eufy surfaces numbers,
so nobody noticed — which meant **all five Roborock tables were unreachable at runtime** and the
shipped fault labels never resolved, regardless of what the adapter declared.
`core/error_tracker.py::_code_key` now normalizes, keeping the float and bool guards while
resolving numeric strings. The brand additionally declares that the message carries the code,
because for Roborock the code lives in the entity state rather than a numeric attribute.

---

## 5. Declarations that look redundant and are not

**`PATH_TYPE_OPTIONS` is declared unconditionally**, though no catalogued model exposes path
control. Capability gating decides whether an axis is *offered*; the option list decides whether a
stored value is *valid*, and those are different questions. While no list existed, a fossil string
written by an old core backfill was both un-droppable (the field is declared by the profiles) and
un-resettable (`rooms/vocabulary_migration.py` can only reset a value it can check against a list),
so it sat on every room. This is also why tidying "callerless option lists" in this file is
dangerous — `adapters/roborock/vocabulary.py::PATH_TYPE_OPTIONS` looks exactly like
`adapters/roborock/vocabulary.py::MOP_MODE_OPTIONS`, and only one of them is dead.

**Two lifetime entity suffixes are declared that bind to no role**, purely to arm a collision
guard. Suffix matching is `endswith`, so a lifetime counter's suffix matches a per-run metric's;
until both halves were declared, the guard was unarmed and replaying its own predicate against this
adapter's map returned the lifetime counter where the same predicate on Eufy returned the right
answer. Both halves of a collision must be declared.

**One role carries a declared upstream translation key.** Roborock publishes a binary sensor whose
translation key is one word off from its suffix, and on a localized install the entity id is in the
user's language, which no suffix rescue can reach. Without the escape hatch the only signal that
arms completion never resolves, the run never observes an active lifecycle, and the stranded-run
reaper marks the job interrupted about fifteen minutes after dispatch — possibly mid-clean, with
nothing reaching learning.

**The mop pre-call targets its entity by role, not by id.** Pre-call blocks are built *before* the
entity rescue runs, so a baked-in id is the pre-rescue guess. On a localized install the real select
has a translated object id, so every water push named an entity that does not exist — and because
HA logs a missing service target at warning rather than raising, the push silently did nothing.

---

## 6. Nine declarations are byte-identical to core's default

Worth stating plainly, because the natural way to measure the seam's necessity is to count what the
second brand had to declare — and that count is nine too high.

The low-battery threshold, the error-code attribute name list, the unknown-error message, the
task-status error value, three dispatch field names, the discovery room-id key, and two setup-drift
values all equal what core would have used anyway. Five of the six phase-timing keys equal core's
constants; only the confirmation window differs, and that is the one the block's own comment argues
for.

None of these is wrong. But in three cases the core default is **Roborock's** word rather than
Eufy's, which is worth knowing before treating every core default as residue.

---

## 7. The model tables disagree with each other

The package carries two model tables keyed by the same vendor strings, with nothing comparing them,
and both reach the user.

`adapters/roborock/model_catalog.py::MODEL_PROFILES` supplies the display name that becomes the
registered config's, while `adapters/roborock/upkeep_catalog.py::ROBOROCK_MODEL_NAMES` feeds the
maintenance card. They disagree on at least one code: one names it the base model, the other names
it the Pro Ultra and tiers it as a wash station. The model catalog's own hedge — "if a code is
wrong the profile simply never matches" — does not cover this, because the code is real and **does**
match; it just names a different device. So one owner sees two different model names in one UI,
while the model that name belongs to has no capability profile at all.

A second code is described in the model catalog as charge-only with no station to model, and tiered
in the upkeep catalog as having a dust-collection dock. Most likely the code covers both a docked
and a dockless variant and each file assumed one. It stopped being cosmetic when the guide tiers
went live: the family gate now renders a dock-dust-bag guide on the charge-only unit.

**The consumable count is stated three times and is wrong in all three.** It says twelve; there are
fourteen. It has drifted twice before, and the correction note itself is now stale — the commit
that added the last two components updated none of the prose copies. The pinning test enumerates
all fourteen, so the count is right only where a machine checks it and wrong everywhere a reader
looks.

---

## 8. Surfaces that do not do what they say

> ✅ **CORRECTED 2026-08-23.** All nine are annotated at their sites; the section is kept as the record of what was
> found. Two corrections worth carrying here because the numbers changed:
>
> - **The unbacked count was two numbers, not one.** Re-measured by AST: the sets below that
>   comment hold 86 entries / 49 distinct, and 31 distinct codes are classified. Neither "60
>   declared" nor "44 of the 53 classified" reproduces under any rule, so both were removed
>   rather than replaced — a count that licenses trusting a whole table is worse wrong than
>   absent. The "53 enum states" figure is a live-instance reading and is left as recorded.
> - **The zone-clean seam is now CLOSED**, not just documented (D18): the adapter passes the
>   hint from the model profile, so a catalog entry declaring `False` reaches the dispatch
>   refusal. It defaults `True`, so no catalogued model changes.
>
> The dock-capability contradiction keeps its behavioural remainder — the three literals are
> annotated with both fix shapes but left in place, because changing them is a capability
> surface decision rather than a comment edit.

**The dock investment cannot reach the UI.** `adapters/roborock/dock.py::dock_profile` resolves the
vendor's answers, passes them to `core/capabilities.py::detect_capabilities` as hints — and the same
config's `capabilities` block then hardcodes wash, dry and empty to False about five hundred lines
later, at brand level, from one model's behaviour. The two dictionaries agree only when no dock is
found. Worse, the hints cannot survive a refresh: this brand persists neither its capability hints
nor its model family, so a capability refresh re-derives from that hardcoded block, and dock support
is a hint OR a wash-entity presence with no wash entity among the declared candidates. The card
hides the Base Station tab on those same literals, so the whole truth table cannot turn that tab on.

**A safety reassurance is inverted for the one entry it is about.** A comment states that a rejected
select is caught, logged, and never aborts the run. The water pre-call declares the safest
mixed-mode policy, and that path fires whenever the batch contains any non-mop room — including the
plainest case, an all-vacuum batch. On that path both a missing target entity and any exception from
the select raise and **abort the dispatch**. Since an uncatalogued model defaults to mop-settable,
this is reachable on any Roborock not in the catalog whose mop set is actually rejected.

**One capability seam is open at the core end and unconnected at the brand end.** A comment explains
that zone-clean support is read from capabilities so a model catalog entry can declare it False and
be believed. No model profile carries that key and the hints dict never forwards one, so a catalog
entry declaring False is silently ignored — the exact failure the core mechanism's own docstring
says it exists to prevent.

**The package README describes a dead mechanism under its live name.** The module docstring sends
readers there first. It states that the brand is auto-detected by manufacturer and model prefix —
the detector §2 documents as removed, and which the package's own `__init__.py` says is gone on
purpose — along with a consumable count, three blocks listed as deferred that are all now declared,
and a pruned key listed as pending.

**The localization note is flatly inverted.** A declaration-site comment says the guide translations
are empty today so guides render in English. The directory holds seventeen language modules
transcribed from the vendor's own manuals. A reader deciding whether localization work is
outstanding is told it is, at the site that would tell them otherwise.

**A verification number that licenses trusting the whole fault table is unbacked.** The comment
claims sixty declared strings; the four sets declare fifty, forty-four of them distinct. The number
matches nothing under any counting rule and was already wrong in the commit that wrote it. The two
other figures in the same sentence are both exactly right, which is what makes the third read as
measured.

**A fossil corroborates a decision that did not need it.** The fan-speed option list is documented
as ordered to match a dispatch global pre-call rank. There is no fan-speed pre-call — there was one,
and it was replaced by per-room live settings. The ascending order still has a real justification;
the fossil clause adds a false second reason. Core carries the same fossil in a docstring that still
uses a fan-speed rank as its worked example.

**`path_type` is attributed to the wrong owner.** A comment calls it Roborock's name for pass
density, each brand declaring the axis under its own name. It is neither brand's word: it was
invented in this project's initial release, three weeks before adapters or a second brand existed,
as a duplicate of an axis already carried. Roborock later adopted the field that was already
canonical, which is why it now reads as Roborock's — and the giveaway is that one value appears in
*both* brands' option lists for the axis.

**A correct exclusion is defended by a mechanically wrong reason.** A sentinel is excluded on the
grounds that a Roborock error code could legitimately *contain* the word. The test is exact set
membership after strip and lowercase, not containment, so only a state exactly equal to it was ever
at risk, and none of the upstream enum states is. The exclusion is right as hygiene; a porter
copying the reasoning to a third brand would over-narrow their sentinel set on a false premise.

**Cross-reference line numbers in this package are not maintained.** Three in-file pointers to a
single declaration are stale by ninety to two hundred and thirty lines. On its own that is minor,
but it is the same drift signature as the consumable count and the guide-tier note: follow names in
this package, never line numbers.

> One comment in this package was checked *because* it is the most assertive one in it — the
> callerless-by-design block over the mop-mode option list — and every checkable clause holds. Its
> only drift is that an unscoped repository search now returns a second hit, a notes file quoting
> the symbol. Recorded here so a later reader does not discover that and discard the whole block.

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
