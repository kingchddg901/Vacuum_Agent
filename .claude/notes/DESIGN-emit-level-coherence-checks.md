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
  of those, with >=1 page where naive != column      9   (9 of 9 — exposure is total)
raw heading-shift candidates                        51
  after dropping page-title-level headings           7
  CONFIRMED new misfiles                             0   (all 7 already filed correctly)
NOT CHECKED (no packet, or no PDF matched)           7   — unknown, NOT clean
```

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
