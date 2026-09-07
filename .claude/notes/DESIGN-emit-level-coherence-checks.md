# Emit-level coherence checks — per step in a block, not per key globally

**Status:** designed, not built. Chris's framing, 2026-09-06.
**Depends on:** step-key provenance in the debug artifact (built 2026-09-06, see below).

## The level

Checks run **at emit, over the steps of one block**. Not over the phrase table, and not
over key pairs across the corpus.

```
removed  → must be refitted later in THIS block
opened   → must be closed later in THIS block
wetted   → must be dried before it is refitted in THIS block
acted on → must come after its own removal in THIS block
unplugged → must be plugged back in later in THIS block
```

Every rule is block-local. None needs to know whether key A outranks key B anywhere else.

## Why not a global canonical order

The obvious idea — the card renders a list in order, so predetermine that order — was
measured and **does not work**. On the emitted artifact:

```
distinct co-occurring key pairs        3,280
  always the same relative order       3,204   97.7%
  appear both ways                        76    2.3%
ordering instances                    45,467
  following the dominant direction    45,258   99.54%

CYCLES in the dominant relation:          20
```

97.7% pairwise consistency looks like a canonical order is almost there. It is not:
**20 cycles** mean no total order can exist, e.g.

```
tank_refit → off_dock → tank_rinse → outside_wipe_dry → tank_refit
rinse_only → tip_out → filter_tap → rinse_only
```

The cycles are not corpus incoherence. They are keys playing **different roles in
different blocks**. `access.off_dock` is the clearest case: it is not a fixed-rank step,
it is a **phase boundary**. In a single-phase block it is step 1; in
`x50_ultra/dirty_water_tank` it is step 6, because steps 1-5 service the *station's*
used-water tank and steps 6-10 service the *robot's* used-water box. Both are correct.

I initially read those six blocks as defective (`rinse_plain` before `off_dock`, 6 vs 6,
"off_dock should be absolute"). **That was wrong** — they are two-phase procedures. The
error is instructive: a global per-key rule cannot express "phase boundary", so it
reports legitimate structure as conflict.

## Track record — this is why the level matters

| check | level | outcome |
|---|---|---|
| caster coherence (dry-without-wet, wet-without-removal) | block-local | RED 8 → GREEN 0, no false positives |
| blocks-the-user audit | block-local | RED 9 → GREEN 0 |
| invented phase taxonomy | global | called a normal vendor order an inversion **95 times** |
| paired-action linter (regex over 592 phrases) | global | 1401 → 1050 → 968 findings vs a review that found 68; abandoned |

Both global attempts failed the same way: they needed a corpus-wide notion of "correct
position", and no such thing exists.

## Division of labour that has actually been working

- **The corpus proposes.** "217 of 224 blocks put the close immediately before the
  refit" is how `bin.cover_close` was placed across 66 blocks. Pairwise dominance is a
  *rule generator*.
- **A human ratifies.** The proposed rule is shown with its support before it is applied.
- **The block-local check enforces**, and must be able to go RED on current data before
  it is trusted. A fix whose check cannot fail first has not been shown to do anything.

The 97.7% figure earns its keep at step 1 and nowhere else. Do not turn it into a gate.

## What it plugs into

`compose()` returns `step_keys` / `note_keys`, paired with each sentence in the same
comprehension that renders it. `emit_composed.py` forks on `EMIT_MODE`:

```
release (default) → dreame_upkeep_guides_composed.py         1.53 MB, ships
debug             → dreame_upkeep_guides_composed_debug.py   2.24 MB, gitignored
```

The debug artifact carries `step_keys`, `note_keys` and `shares_with`, positionally
aligned (verified: 1,880 blocks, 0 mismatches). So the checker runs against **what
ships**, not against the fixture — which matters, because the artifact was found to be
**stale** by 228 blocks on 2026-09-06 and nothing warned about it.

## The lint reached 0 findings on 2026-09-06 — what it took

`TIER OVERREACH` sat at 23 for a long time and every one of them was the same false
positive. The mechanism scan read whole sentences, so `access.turn_over`'s reason clause
— "so that you do not scratch its top **cover**" — read as a claim that the robot has a
removable cover. One phrase, 6 archetypes x 4 components, 23 findings of noise that would
have hidden a real one.

Fixed at the class, not the symptom: the scan now runs over `claim_of(text)`, which drops
reason clauses (`so that`, `to avoid`, `to prevent`, `otherwise`, `because`) and keeps the
asserting clause. **Deliberately not an allowlist entry** for `access.turn_over` — an
allowlist with no floor is an off switch.

Ablated before trusting it:

```
"Press the brush guard clips inwards and lift the guard off."   -> guard, clips, guard
"Open the dust box cover."                                      -> cover
"Unscrew the end caps so that the brush comes free."            -> Unscrew, end caps
```

The third is the one that matters: the claim still fires while its reason is ignored. It
strips reasons, not claims.

⚠ **A heredoc corrupted the fix on the first two attempts.** `` written inside a
`python - <<'PYEOF'` block became a literal **backspace byte (0x08)** in the regex, so
`REASON` searched for a control character and silently never matched — the lint kept
reporting 23 and looked unchanged. `cat -A` is what exposed it. Every other file written
that way the same day was scanned for control bytes and is clean, but prefer the Write
tool for anything containing regex escapes.

## Where the emitter actually lives (fixed 2026-09-06)

`emit_composed.py` and `famload.py` existed **only in a session scratchpad** while being,
respectively, the emitter for the 1.6 MB shipped artifact and the only safe reader for the
three record shapes. The fixture had `emit.py` and `emit_nonen.py` but neither of these.
Scratchpads are session-scoped, so the toolchain for the shipped guide library was one
cleanup away from gone while a full day of content was being fed through it.

Both now live in `dreame-port-fixture/authoring/compose/` alongside `compose.py` and
`lint_compose.py`, together with `gutter.py`. **Verified, not assumed:** re-emitting from
the durable copy reproduces the committed artifact byte-for-byte.

Run it from there, not from a scratchpad.

## Cadence: no per-family override — RULED, do not re-propose

E5's own maintenance table says `Filter = Weekly`; the `CADENCE` map in `emit_composed.py`
is per-component and global and says "Every 2 weeks or as needed". Chris, 2026-09-06:
*"the or as needed covers it and its a niggle for a lot of work."* The trailing condition
is what absorbs a family that documents a tighter interval. The ruling is also written
into the map itself, where someone would go to change it.

## What this does NOT replace

**The canary.** Provenance is self-reported by the composer. If the share chain resolves
to the wrong `src`, provenance reports that source's keys faithfully and looks perfectly
consistent while being wrong — and that failure has happened here (see `_own`'s
docstring: 196 blocks declared a share, 191 held `see`, so `shares_with` never fired).
`fill()` guards the slot seam by raising; **nothing but a cycle check guards the share
seam.** That seam is the canary's job, and the canary is an input-substitution test,
which is independent of the composer in a way provenance cannot be.

## The remedy step: re-read the source page, word-level, column-aware

When a rule fires, the next question is always "is the source wrong, or did we mangle
it?" There is now a cheap answer, and it is **not OCR**.

**Exposure is near-total; realised damage is tiny.**

```
1,033 source pages sampled across 6 manuals
  926 two-column                                   (90%)
  924 where naive extraction order != column order (89%)

detectable damage in the COMPOSED output              6 blocks of 1,880 (0.3%)
```

Those two numbers are not in conflict. 89% is **exposure** — pages whose extraction
order cannot be trusted. 0.3% is **realised damage** — because on many pages the naive
order lands correctly anyway, and where it did not, whoever authored the guide was
reading prose and often reconstructed the sequence by hand.

**What the scrambling looks like.** X20 Max p14 (`xiaomi.vacuum.d109gl`, PDF p15) is the
worked example: "Cleaning the Dust Compartment and Filter" starts bottom-left and
finishes top-right. Naive `get_text()` emits all six headings first, then the bodies in
a different order, so the filter section arrives as **step 2, step 3, … then step 1**,
separated by three other sections. Our `x20_max/filter` block had `clip_open_out` before
`release_button_out` — exactly what you build if step 1's clauses land last.

**What works, in order of preference:**

| approach | verdict |
|---|---|
| `get_text()` | scrambles multi-column pages |
| `get_text(sort=True)` | **worse** — sorts by y across the whole page, interleaving columns line by line |
| block geometry, column-then-y | close, but **3 of 18 blocks on that page straddle the midline** — the PDF's own segmentation merges columns |
| word geometry split at the **midline** | **fails on this corpus** — see the correction below |
| **word geometry split at detected GUTTERS** | **works.** Generic N-column; reproduces the e30_aqua misfile mechanically |
| render + OCR | unnecessary here, and lossy. Only for pages with no text layer — measured destroying every procedure line on the 96 dpi raster edition |

### CORRECTION 2026-09-06 — "two-column" is wrong for this corpus

The midline assumption above was inherited from the X20 Max, and it is **not
general**. Dreame ships landscape spreads: the E30 Aqua page carrying the
un-merged main-brush steps is **1191 × 397 with FIVE columns**, gutters at
x≈290 / 580 / 870. A midline split lands *inside* a column, so the detector
reported that page as single-column and the whole sweep came back clean.

The calibration case is the guard. **Run any column detector against E30 Aqua
p20 (page index 12 of `trouver.vacuum.r2461r__c4d67be8.pdf`) first** — it must
report multi-column AND naive ≠ column order, because that page's damage is
already confirmed. A sweep whose known-true case comes back clean is measuring
nothing; this one did, twice, before the detector was fixed.

Working detector: occupancy-histogram the word x-extents in ~2pt bins, take
maximal empty runs wider than ~1.2% of page width and not touching the text
bounds as gutters, split columns at gutter midpoints, sort each column by
(y, x), concatenate left to right. Implementation: `scratchpad/gutter.py`.

### EXPOSURE IS NOT DAMAGE — the heading-shift test

A page whose reading order is untrustworthy is exposure. Damage happens only
when the wrong order changes **which section heading precedes the sentence**,
because that heading is what the lift files it by. E30 Aqua p20:

```
naive : [Side Brush and Mop Pad Holder] … 2. Lift the brushes from both the left and right sides …
column: [Routine Maintenance]           … 2. Lift the brushes from both the left and right sides …
```

Scoped sweep 2026-09-06, 17 structurally-flagged families:

```
checkable (packet + PDF present)                    10
raw heading-shift candidates                        51
  after dropping page-title-level headings           7
  CONFIRMED new misfiles                             0   (all 7 already filed correctly)
NOT CHECKED (no packet, or no PDF matched)           7   — unknown, NOT clean
```

### ⚠ CORRECTION — "naive != column order" is a BASE RATE, not a finding

This note previously reported "9 of 9 families have a disagreeing page — exposure is
total" as if it measured something. **It does not.** Ablated against the known-good
control on 2026-09-06:

```
E30 Aqua (the calibration manual)   42 of 42 multi-column pages disagree   = 100%
```

Any header, footer, page number or figure caption reorders under column sorting, so
whole-page string equality is always false on a multi-column page. The metric cannot
separate a damaged page from a healthy one and must never be quoted as exposure.

**The heading-shift test is the only one that ever discriminated** — 51 raw candidates
to 7 after dropping page-title-level headings to 0 confirmed. Use that, and report the
denominator (pages the probe actually reached) alongside it.

### What the rare-namespace detector actually finds: SHARED ACCESS, not merges

All 7 unreachable families were worked on 2026-09-06 once Chris supplied manuals. The
detector flags a component whose steps borrow a key from a different physical part. In
**5 of 6 readable cases the reason was that the vendor reaches one part THROUGH the
other**, and the borrowed key is the access step:

| family | flagged | verdict | vendor's own words |
|---|---|---|---|
| `l20` | `side_brush` ← `mop.*` | legit | section headed "Side Brush & Mop Pad Holder" |
| `matrix10` | `dock_contacts` ← `vent.*` | legit | "Auto-Empty Vents, Charging Contacts and Signaling Area" |
| `3c` | `clean_water_tank` ← `bin.*` | legit | the part IS 二合一水箱（水箱+尘盒） — tank *and* dust box, one moulding |
| `x50_master` | `detergent_inlet` ← `bag.*` | legit | "Remove the dust tank cover and pull out the auto-detergent compartment" |
| `x40_pro` | `base_station_filter` ← `bag.*` | legit — the station-filter wipe IS **step 3 of 更换尘袋, the dust-bag replacement**: open the station door, discard the bag, wipe the dust-collection filter, fit a new bag, close the door |
| `x30_pro` | `side_brush` ← `mop.*` | **NOT a finding — see the retraction below.** It HAS a mop holder (拖布盘 x2); its manual just documents no cleaning procedure for it. |
| `vacuum_mop_pro` | — | unreachable, zero text layer on all 20 pages |

**So read a namespace borrow as an access path first and a merge second.** It is the same
fact as `dustbin` folding into `filter`: you cannot service the filter without holding the
dust box, you cannot reach the detergent compartment without lifting the dust tank cover.
Namespace reasoning cannot see a shared access path, so it reports one as a defect.

### Three kinds of claim, and which ones need a human

The anti-splice control — don't author beyond the source, don't connect things that are
not connected, don't keep searching for a justification — **is correct and stays as it
is.** Chris, 2026-09-06:

> "this is not a failing[,] is a proper control that fails in this case. dont search
> forever[,] dont connect unrelated things[,] 99% good but in this case it bites[,] not
> something to overwrite. its why i am still in the loop"

So this section is **not** a licence to author more freely. It is a map of where the
control's known narrow failure sits, so the escalation is aimed rather than constant.

| the claim | inferable without a source? | why |
|---|---|---|
| **WHAT to do** — clean the part that gets dirty | usually **yes** | follows from what the part *is* and what it touches |
| **HOW to do it** — wash / vacuum / tap / keep dry | **no** | material and design fact, invisible from outside |
| **WHAT the part is, how it comes apart** | **no** | mechanism. This is what the anti-splice rule exists for |

Worked against the day's ground truth, all of it supplied by Chris:

- *caster axle separates from the wheel* — row 3. I concluded press-fit from a labels-only
  diagram; 11 of 11 sources say it separates.
- *E30 Aqua has TWO main brushes* — row 3. No amount of reading our corpus produces that.
- *e5's HEPA must stay dry; its foam should be vacuumed, not washed* — row 2. I had
  proposed a single filter with a tapping step. Both halves wrong, and the failure mode is
  a user destroying a filter.
- *"remove the mop plate, clean it, refit it"* — row 1. The holder is in permanent contact
  with a wet pad holding dirty water; it gets dirty because of what it is. **No manual
  needed, and precedent from sibling families is not the reason it is sound.**

Every intervention that changed an outcome today was row 2 or row 3. None was row 1,
because row 1 does not need one.

**The defects the composed architecture was built to stop are MECHANISM splices** — steps
asserting end caps, clips or hatches a given model may not have. A generic "clean the
thing that gets dirty" borrows no mechanism and was never the hazard. Suppressing row 1
is the control being slightly too broad, which is the right direction for it to err.

### ⚠ RETRACTION — `x30_pro` was NOT a finding

Reported above as the one real defect of the seven. It was not, and Chris's two questions
are what broke it:

> "does the x30 pro even have a mop holder. the fact the steps are paired means nothing
> to doing them alone"

**The reasoning error.** I treated a manual's section grouping as evidence about hardware.
It is a layout choice. That 主刷和边刷 puts the main and side brush under one heading says
nothing about whether either can be done alone, and nothing about what else the machine
has.

**The factual error, which is worse.** The line I reasoned from — 取下拖布盘并清理，清理完后
装回主机, "remove the mop plate, clean it, refit it" — is on **x40_pro's** page 22, not
x30_pro's. Two Chinese manuals read in one session and a sentence carried across. Always
re-read the page in the document you are about to make a claim about.

**What is actually true.** x30_pro HAS a mop holder — 拖布盘 x2, in the box and on the
parts diagram. Its manual documents no cleaning procedure for it: every mention is the
parts list, the diagram, "take the mop off the plate to replace it" (that is the mop, not
the holder), and a troubleshooting step. Same shape as e5's filter — the part is real, the
vendor is silent.

So `mop.holder_off_clean` on `x30_pro/side_brush` describes a part the machine has, with
a generic and safe action that four sibling families document verbatim. **Kept.** All
seven families are now explained; the detector produced zero real defects, which is a
result about the corpus, not a failure of the detector.

### "Dust compartment" names TWO different parts — Chris, 2026-09-06

> "dust compartment sounds like where the dust bag goes — we have encountered this
> semantic issue before"

Correct, and it is already recorded once, in `scope.json`'s m30_pro reversal: the manuals
name **尘盒** (the dust box, on the ROBOT) and **集尘仓** (the bin the dust BAG sits in, in
the STATION) as different parts. English collapses both onto "dust box / dust tank / dust
compartment / dust bin".

**This corrects the vocabulary-churn figure measured earlier the same day.** That table
reported "dust box: 4 distinct terms, Dreame alone uses all 4" as intra-vendor
inconsistency. It is not purely that — some of those four name a *different part*. Churn
and ambiguity were counted together, so the churn number overstates.

Our own table is nearly clean on this, measured:

```
phrases using a dust-container word
  name the BASE STATION explicitly    9 keys   unambiguous (all bag.*, station filter.*)
  name the ROBOT explicitly          10 keys   unambiguous (all bin.*, access.*)
  name neither                       55 keys   bin. 30, filter. 15, note. 9, bag. 1
```

54 of the 55 unqualified keys are robot-side and sit on robot cards, so the card
disambiguates. **The single exposure is `bag.fit_close_permissive`** — "Fit a new dust bag
into the dust compartment. Close the dust compartment." — a STATION part named with an
unqualified robot-sounding word. Used by `wash_station/dust_bag` only, and `dust_bag` is
out of scope on the fault surface, so it does not ship. It is a landmine for the day
`dust_bag` returns: qualify it then.

### ⚠ ABLATE THE PROBE TERM BEFORE REPORTING AN ABSENCE

Three separate false "clean" results on 2026-09-06, all the same cause — probing with
**our** vocabulary instead of the document's:

1. searching vendor PDFs for the phrase table's normalised English — 14 of 16 families
   reached zero pages, reported as zero problems;
2. searching a Hebrew manual with English part names;
3. searching `x30_pro` for 拖布支架 when that manual only ever says 拖布组件 — `拖布支架`
   occurs **zero** times, so "the two parts never co-occur" was a non-look. Re-probed with
   the right term, the real finding appeared.

The fix is mechanical and cheap: **assert the probe term occurs in the document at all
before concluding it found nothing.** Report the denominator — pages the probe reached —
next to every result.

### Manuals are DUAL-PAGE SPREADS

Chris, 2026-09-06. A "page" in these PDFs is frequently **two logical pages side by
side**, page number centred at the bottom — which is why the E30 Aqua page carrying the
un-merged main-brush steps is 1191x397 with FIVE columns. It is two pages of 2-3 columns
each.

Consequence for any reading-order work: the centre break is a **page boundary, not a
gutter**. Content does not flow across it, and a section on the left page is not
continued by the first column of the right page. The gutter detector currently treats
both alike, which happens to give the right order (left page, then right page) but would
mis-join two sections that meet at the boundary.

So e30_aqua remains the only confirmed case beyond the documented six, and the
0.3% realised-damage figure survives a targeted attempt to beat it.

### Aiming the sweep: rare (component, namespace) pairs

Content-blind and cheap — no PDF needed. Flag a component whose keys borrow a
namespace belonging to a different physical part. It fires on the known case
(`mop.*` inside `side_brush`, 5 families of 1,692 placements = 0.30%). Most rare
pairs are just naming, not merges (`fluffing_roller` keys live in `mop.`,
`charging_contacts` legitimately uses `sensor.wipe`), so the output is a
candidate list for reading, never a fix list.

### Why probing with our own wording does not work

The first run searched each PDF for the phrase table's **normalised** sentence
and reached zero pages in 14 of 16 families — then reported that as zero
problems. Vendor vocabulary churn is the cause and it is worse *within* a vendor
than between vendors:

| part | distinct terms | worst single vendor |
|---|---|---|
| mop holder | 7 | Dreame alone uses 5 — mop assembly · mop pad holder · mop pad holders · mopping assembly · mopping module |
| dust box | 4 | Dreame alone uses all 4 — dust bin · dust box · dust compartment · dust tank |
| caster | 3 | Dreame alone uses all 3 — omnidirectional · universal · caster wheel |
| dirty tank | 3 | Dreame alone uses all 3 — used water tank · used water box · dirty water tank |

Probe with the **packet's** lifted sentences (the vendor's own English), never
with the phrase table's.

**Detection is content-blind**, which is what breaks the chicken-and-egg. You do not need
to know a block is wrong; you need to know its page is two-column, and that is pure
geometry. Extract twice — naive and column-aware — and compare. Disagreement flags the
page before anyone reads a word of it.

**Do not bulk re-extract.** At 0.3% realised damage it is not worth it, and three things
that *looked* like interleave damage were legitimate two-part procedures
(`omni_m30s/main_brush`, `x20_max/main_brush`, `x50_ultra/dirty_water_tank`). This is a
per-block remedy invoked when a rule fires, not a migration.

## Known inputs for the first build

- 40 live findings from review #2 cluster into: missing REFIT (9), missing CLOSE (4),
  missing REMOVAL (3), missing DRY gate (2), missing PLUG-BACK (1). Those five classes
  are precisely the rules above, so the checker should reproduce them.
- Guard against the recurring **record-shape trap**: compute the audit from
  `famload.keys_of` (handles bare list / `{"see"}` / `{"phrase_keys"}`), never from a
  bespoke walk. A fixer that walked only dicts reported "150 of 153" and exited zero.
