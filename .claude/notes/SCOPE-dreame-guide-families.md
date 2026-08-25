# Dreame guide families — the scope, and why it is r-codes and not names

**Decision (Chris, 2026-08-25): the target is Dreame's CURRENT-ISH lineup**, i.e. what
their own comparison page still lists — `dreametech.com/pages/robot-vacuum-and-mop-comparison`.
Not the 587 models the integration declares, and not the 228 historical platforms.

**26 platforms. 4 already have manuals. 22 to go.**

---

## The rule — corrected 2026-08-25, second version

> **A guide family is a MANUAL PAGE. Its scope is every `dreame.vacuum.*` key whose
> marketing name appears on that page.**

Not the r-code, and not the marketing name. Both were tried and both are wrong:

* **r-code is too NARROW.** `X40 Ultra Complete` is `r2449`, not `r2416` — yet Dreame
  ships **one manual for X40 Ultra and X40 Ultra Complete together**. Keying on the
  manual's own r-code would leave `r2449` unguided while the manual plainly covers it.
  Same shape on X50: one page for Ultra + Ultra Complete, six platforms between them.
* **marketing name is too BROAD.** "X50" is 23 distinct names across ~20 codes.

**The manual page is the only boundary Dreame actually draws**, and it draws it by
printing one maintenance section for a set of models. That is vendor assertion, not our
inference — the strongest evidence available short of hardware.

⚠ **This supersedes the first version of this rule, which said "a family is an r-code
platform".** That was measured but under-scoped: it produced 7% coverage and would have
orphaned `r2449`, `r5020`, `r9515` and the four X50 Ultra Complete codes, all of which
sit on manual pages we already hold.

### Coverage under the corrected rule

| family | page covers | keys | platforms |
|---|---|---|---|
| `x50` | X50 Ultra + X50 Ultra Complete | **41** | r2489, r2532, r2538, r5048, r9446, r9538 |
| `l20` | L20 Ultra + L20 Ultra Complete | 15 | r2253, r2338, r2394 |
| `x40` | X40 Ultra + X40 Ultra Complete | 9 | r2416, r2449 |
| `x60` | X60 Ultra + X60 Pro Ultra Complete | 5 | r5089, r6001, r9515 |
| `l10s_gen2` | L10s Ultra Gen 2 | 3 | r2469, r5020 |
| `l50` | L50 Ultra | 2 | r9493 |

**75 of 587 models — 13%** from six manual pages. Earlier readings were 7% (r-code
only) and 26% (name only); both were artefacts of the wrong key.

`x50` is over half of that reach and its manual carries 17 of the project's 18
languages. If exactly one more family is authored, it is that one.

Routing keys on the **full model string** via a generated name→family table, built from
`supported_devices.md` so it tracks upstream rather than being hand-typed.

---

## Why names and codes cannot be the key (the underlying measurement)

Marketing names and r-codes are many-to-many **in both directions**, measured against
`Tasshack/dreame-vacuum` `docs/supported_devices.md`:

```
"X50 Ultra"            26 keys ->  r2489 AND r9538      one name, two platforms
"X50 Ultra Complete"   15 keys ->  r2532, r2538, r5048, r9446
r2518                          ->  "X50 Pro Ultra", "X50 Ultra (Enhanced Edition)",
                                   "X50s Pro Ultra"     one platform, three names
```

"X50" alone is **23 distinct names across ~20 r-codes**. So a name identifies neither
the hardware nor a manual, and mapping guides by name would hand one platform's
instructions to another's hardware — the defect already committed once in
`a2efcf46` and fixed in `d45e2ec4`.

**The manuals do not resolve it either.** "X50 Series" and "X60 Series" name only
themselves: no applicability statement, no model list, checked on pp. 1-6 of each. The
X40 manual is the exception and names its two variants in the filename.

⚠ **`r501` is a live collision inside the current lineup.** `L60 Pro Ultra` and
`L40 Ultra Gen 2` are both `r501`, as are `L10s Ultra Gen 3` and `X60 Master`. So the
three-digit codes need their suffix to be a key at all — `r501bt` is Aqua 10 Roller,
`r501h` is something else. Keys are `r` + **3 or 4** digits + a **variable-length**
suffix; a `r\d{4}` regex silently drops ~9% of Dreame robots.

---

## The 26 current-ish platforms

| model | platforms | manual |
|---|---|---|
| X60 Max Ultra Complete | *(not in the upstream list at all)* | |
| X60 Ultra | `r5089`, `r9515` | **r5089 ✓** |
| Matrix10 Ultra | `r2513`, `r502`, `r5062` | |
| Aqua10 Ultra Roller | `r9535` | |
| Aqua10 Roller | `r9533` | |
| X50 Ultra | `r2489`, `r9538` | **r2489 ✓** |
| L60 Pro Ultra | `r501` | |
| L60 Ultra | `r5090`, `r6015` | |
| L60 Ultra PE | `r5039` | |
| L60 Ultra FE | *(not in the upstream list)* | |
| L50 Ultra | `r9493` | **✓** |
| L40s Ultra | `r2551` | |
| L40s Ultra AE | `r2579`, `r500` | |
| L40s Ultra CE | `r2562`, `r5021` | |
| L40 Ultra Gen 2 | `r501` | |
| L10s Ultra Gen 2 | `r2469`, `r5020` | **r2469 ✓** |
| D30 Ultra | `r5057` | |
| D20 Pro Plus | `r2566`, `r9537` | |
| D20 Plus | `r2564`, `r5314` | |

**Most current models are TWO platforms** — X60 Ultra is `r5089`+`r9515`, X50 Ultra is
`r2489`+`r9538`, L10s Ultra Gen 2 is `r2469`+`r5020`.

⚠ An earlier version of this note called those "half-covered". **That was wrong**, and
it was the r-code rule causing it: both codes of each pair sit on the SAME manual page,
so one family legitimately covers both. Robin's guides do apply to an `r5020` L10s
Ultra Gen 2, because Dreame prints one maintenance section for the model name they
share. Two platforms is not two hardware sets.

⚠ **`X60 Max Ultra Complete` — the current flagship — is not in the upstream device
list.** It cannot be driven at all by the installed build, let alone guided.

---

## What authoring one family costs

1. **Automate the finding.** `Routine Maintenance` locates the care section reliably:
   `l20` pp20-26 · `x40` 19-26 · `l10s_gen2` 18-25 · `x50` 22-30 · `l50` 23-30.
2. **Read the pages.** Do NOT script the extraction — PDF text order does not follow
   the visual columns, and a collapsed extract of the Gen 2 "Main Brush" block arrives
   with used-water-tank sentences inside it. That produced a false "the dust bag
   differs" finding that reading corrected.
3. **Author the family whole**, from that platform's own manual.

**Never factor a shared base out of two families because their component names match.**
Measured between `x60` and `l10s_gen2`: of the **11 component keys in common, exactly
ONE (`caster_wheel`) has identical steps**. Ten differ — six of them while having the
same step COUNT, so nothing shape-based catches it. The differences are hardware: Gen 2
opens a robot cover the X60 has not got, its side brush pulls where the X60's unscrews,
its contacts and vents are two sections where the X60 has one.

Manual pages needed: ~13 for the 22 platforms, since siblings share a page
(`L40s Ultra`/`AE`/`CE`, `D20 Plus`/`Pro Plus`, the Aqua10 pair).

---

## Coverage is measured against the LINEUP, not against downloads

The check that produced this file: after two families were written, coverage against
the full model list came out **26% by name and 7% by r-code**. The GAP was the finding
— two keys disagreeing by a factor of four proved neither resolved what a family
covers, which is what sent us to the manual page as the boundary. Under the corrected
rule it is **13%, 75 of 587**.

Re-run it whenever a family lands. "We wrote two families" is not a coverage statement.

## Status

Authored: `x60` (from R6001), `l10s_gen2` (from R2469X). Both in
`custom_components/eufy_vacuum/adapters/dreame/dreame_upkeep_guides.py`.

⚠ There is still **no `BRAND_REGISTRARS` row**, and adding one is the release. The
adapter is gated on a released upstream build carrying Tasshack #1707.
