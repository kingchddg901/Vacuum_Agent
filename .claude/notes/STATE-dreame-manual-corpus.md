# Dreame manual corpus + channel map — 2026-08-26

**Written for compression.** The session that produced this ran long; this is the durable
part. Numbers here are measured, not estimated, and the ones I got wrong are recorded as
wrong because the corrections are the useful bit.

---

## THE DENOMINATOR — get this right or every percentage lies

| | |
|---|---|
| model keys the integration declares | **741** |
| SUPPORTED TARGET (robot + map + rooms) | **666** |
| authored upkeep guides | 75 keys (**11.3%**) |
| manuals on disk | **229 files, 2.8 GB** |
| target keys a manual covers | **31 (4.7%) to 186 (27.9%)** — a RANGE, see below |

⚠ **THREE DENOMINATOR ERRORS, ALL IN MY FAVOUR, ALL CAUGHT LATE:**

1. I parsed only `dreame.vacuum.*` = 587. The integration ALSO declares `mova` (102),
   `xiaomi` (25), `trouver` (13), `ijai` (11), `deerma` (2), `szkj` (1). **741 total, all
   suffixes distinct, zero overlap between prefixes** — they are additional devices, not
   rebadges. Every figure was 21% too generous.
2. I then read `DEVICE_INFO` `field[0]` as a product class and EXCLUDED 118 real robot
   vacuums. **It is the BRAND** — dreame 0, xiaomi 1, mova 2, trouver 3, exactly 1:1 with
   the prefix. Mova's 102 keys carry segment capabilities on 99. The tell was that the
   excluded set equalled a category I already had: *a filter whose output equals an
   existing category is not filtering, it is renaming.*

3. **THE 42.8% COVERAGE FIGURE WAS NEVER REAL.** It was a NAME count divided by a KEY
   denominator — 285 names over 666 keys — two different units. The instrument itself
   was honest; it prints `manuals in hand cover N target names`. I transcribed "names"
   as "keys". Re-run today it says **87 names**, not 285. Nothing in the output looked
   wrong, because a plausible number in the wrong unit reads exactly like a measurement.

`scripts/dreame_target_models.py` now does this correctly. Re-run it rather than quoting
numbers from memory.

---

## ⚠ COVERAGE CANNOT BE COMPUTED FROM FILENAMES — THE JOIN IS UNSOUND

Dreame names its own manual PDFs by r-code (`R2562A-L40_s_Ultra_CE`, `R2551H_L40s_Ultra`),
so matching manuals to model keys on that code looks obviously right. It is not.

**The two namespaces only half-overlap.** Of the 63 distinct codes on 228 manuals,
**31 are exactly a model key and 32 are not.** The misses are edition letters with no
counterpart in the key list — `R2363K` and `R2363L` are manuals for a stem whose only
keys are `r2363`, `r2363a`, `r2363n`. So:

* **exact-code join UNDER-credits** — it throws away half the manuals: **31 keys, 4.7%**
* **stem join OVER-credits** — one manual is credited to every sibling under the stem:
  **186 keys, 27.9%**

And the stem is genuinely ambiguous: **77 r-stems carry more than one marketing name,
covering 324 keys — 43.7% of the catalogue.** `r9524` alone is *three different
machines*: `r9524b` GoVac 200, `r9524c/k` D15 Plus, `r9524a/h/j/m` F10 Plus. Crediting
the GoVac 200 manual to that stem silently covers six keys it says nothing about.

The old matcher did BOTH wrong things at once — `R(\d{3,4})` truncates 5-digit codes
(`R50573` → `r5057`, a stem belonging to something else) and drops the letter entirely.

**The only sound join is the manual's own applicability statement** — the marketing names
it prints, or the regulatory model codes on its Specifications page (`RLX85CE`, `RLD35GD`).
Both require reading the PDF. `scripts/.../reg_codes.py` extracts exactly those, and is
the instrument that collapses this range to a number. **Until it lands, quote the range.**

⚠ I nearly reported "the namespaces are completely disjoint, 0 of 63" — that was my own
bug, comparing `2562a` against `r2562a` after stripping the prefix on one side only.
Same shape as the six probes below: a transform applied to one side of a comparison.

---

## ⚠ "NO RASTERISER IN THIS ENVIRONMENT" IS NO LONGER TRUE — I INSTALLED ONE

Stated as a hard constraint in this note and in `pdf_layout_dump.py`, and it shaped real
decisions: the layout-dump workaround exists *because* of it, and image-only manuals were
written off as unreadable. It was true. It was also fixable in one command.

    python -m pip install pypdfium2      # self-contained wheel, wraps Chrome's PDF engine

    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    doc[i].render(scale=2.0).to_pil().save(png)     # 144 dpi, then just READ the png

**60 of 631 cached manuals (9.5%) carry no usable text layer.** They are overwhelmingly
NON-ROBOT products — electric toothbrushes, hair dryers, air purifiers, `Shine 10`,
`Turbo`, `Aero C`. The robot cases are `GoVac 205 Plus` and Xiaomi `M40`.

⚠ **THESE ARE NOT SCANS.** Text is converted to VECTOR OUTLINES — crisp at any zoom, but
there is no text layer AND no embedded image, so `pypdf`'s `page.images` returns nothing
either. Both obvious instruments report "empty" for a page that is perfectly legible.
Rendering is the only thing that works, and it works completely.

⚠ **CHECK THE TOOL, NOT ITS NAME.** `shutil.which("convert")` returns
`C:\WINDOWS\system32\convert.EXE` — the Windows *filesystem* converter, nothing to do
with ImageMagick. A name-only probe would have reported a rasteriser that was not there.

The lesson is not about PDFs. **A capability recorded as absent stays absent only until
someone re-checks it**, and this one had been load-bearing for weeks of workarounds.

---

## THE NAMING CONVENTION, DECODED — so nobody reads 2,000 manuals again

A regulatory code is ONE CERTIFIED MACHINE. So if two names share a code, the word that
differs between them changed nothing physical. Measured across the corpus:

| word | same code | different code | means |
|---|---|---|---|
| **Complete** | **5** | **0** | **packaging only — same robot, bigger box** |
| Heat | 1 | 0 | firmware feature, no re-certification |
| Pro | 1 | 8 | real hardware tier |
| Ultra | 1 | 3 | real hardware tier |
| Plus | 0 | 3 | real hardware |
| Master | 0 | 1 | real — plumbed to mains water |
| AE / CE | 0 | 8 | regional certification |

`X60 Max Ultra Complete` therefore decodes as: the Max Ultra machine, in the Complete
accessory bundle. Two superlatives are load-bearing, one is the box.

**USE IT:** every `… Complete` name inherits its base family's guide. No separate
authoring, no separate hunt. Same for `… Heat`.

⚠ Sample sizes are small (5 pairs for Complete, 8 for Pro) and cover only names where we
hold a manual printing a code. Indicative, not proven — but consistent with the Master
finding, which was measured independently at 67% shared manual text.

⚠ **MASTER IS SEPARATELY CERTIFIED AND STILL SHARES MAINTENANCE.** Mains water plus mains
power is a different safety case, so it needs its own approval — while the brushes and
filters stay identical. That makes the map ASYMMETRIC: *same code ⇒ same machine* is
strong; *different code ⇒ different maintenance* is weak. Merge on a shared code freely;
never SPLIT a guide family on a differing one without checking the parts table.

---

## ⚠ NAMES ARE BOOBY-TRAPPED — 25% OF THEM

Of 389 declared names: **181** are a prefix of another name, **153** are a substring of
another, 91 carry a parenthetical descriptor, 77 r-stems hold more than one product, 18
names appear under more than one vendor prefix, 3 differ only by case. **96 names (25%)
are ambiguous by at least one of these.** `S30 Pro` is a prefix of NINE others.

Plus cross-industry collisions that aren't even in that count: `E20` is Dreame AND eufy.
`M30` is Xiaomi AND a Tuya white-label. `D102CN` is Xiaomi AND a Korean call bell from
2012. `D20` is a robot AND a hair dryer. `S50` is a robot AND an air fryer. `H40` is a
robot AND a humidifier.

**ONLY LONGEST-MATCH-WINS SURVIVES THIS.** Four matchers were written before that landed:
bare substring (`e10` inside `shin-e10`), single-token equality (broke `GoVac 205 Plus`),
contiguous token run (`E30 Pro` inside `e30-pro-PLUS`), and a throwaway verifier that
reproduced the prefix bug an hour after it was fixed elsewhere. The correct rule was
already sitting in the text join the whole time.

⚠ **DESCRIPTOR NAMES ARE NOT RETAIL NAMES.** `X60 Pro Disc`, `X60 Pro Roller`,
`X50 (Tracked Version)` are internal SKU labels for the mop mechanism — **zero of them
appear anywhere in 1,999 manuals across 20 vendor stores.** They are unhuntable, not
unfound. Where a descriptor IS retail — `Aqua10 Roller`, `Z60 Ultra Roller`, `S70 Roller`
— the family has covered examples. Key the rule on that evidence, never on the word.

---

## ⚠ THE UNIT IS THE MODEL NAME, NOT THE MODEL KEY

Chris's correction, 2026-08-26, and it dissolves the join problem above rather than
solving it. **Cover every NAME and the keys come with it.**

* 339 target names carry 666 target keys — a name is worth 2.0 keys on average.
* **94 of those names have keys under MORE THAN ONE r-code.** `X50 Ultra` spans four
  (`r2489`, `r24896`, `r24898`, `r9538`); `Matrix10 Ultra` spans five. **No code-based
  join can ever collect these** — which is exactly why key-space matching kept producing
  a RANGE instead of a number.
* A name is also the unit of WORK: one manual page, one guide family. Keys are the reach
  it buys. The guide library already knew this — `A FAMILY IS A MANUAL PAGE`.

The name join replaces the filename join: extract the model names a manual PRINTS, then
expand each name to all its keys. Cached text lives in `manual_text_cache.json`, names
per manual in `manual_names.json`, both rebuildable with `manual_name_index.py`.

**Three states, not two.** A name is COVERED only when a manual's TEXT names it.
A name whose only evidence is a FILENAME is ATTESTED — kept off the hunting list but not
counted as covered, because a filename is the same class of claim that made a eufy manual
look like a Dreame E20. 19 names sat in that state; `verify_attested.py` adjudicates them.

⚠ **Don't prioritise the hunt and don't skip apparent variants.** One manual often names
several models — `R2416A-X40_Ultra` names *X40 Ultra* AND *X40 Ultra Complete*, different
r-codes entirely. Dedupe on arrival (SHA + printed names), never by guessing up front.

---

## GOVAC — CLOSED 2026-08-26, every model by vendor document

The `support.dreametech.com` walk (2,133 articles → 1,156 attachments → **171 PDFs**)
carried all ten GoVac manuals. Corpus went 229 → **385 files**; 156 new, 15 byte-identical
dupes caught on arrival, 0 failures.

| GoVac | reg-code | Western equivalent |
|---|---|---|
| 200 / 200 Kit | `RLF12SE` | none — own manual |
| 205 Plus | — | own manual, no text layer — **readable by rendering** |
| 300 / 300 Kit | `RLD35GD` | **D20 Plus** |
| 400 | `RLD52SE` | **L40 Ultra CE** |
| 500 | `RLL77SE` | **L40 Ultra AE** |
| 505 | `RLL51SE` | **L50 Ultra AE** |
| 508 | `RLX63CE` | **X40 Ultra** |
| 600 | `RLL94CE` | **L50 Ultra** |
| 800 | `RLX85CE` | **X50 Ultra** |

**GoVac 800 = X50 Ultra is the one that pays** — the `x50` guide family is already
authored (41 keys), so it inherits a finished guide with no new work.

⚠ **THE ONE PREDICTION THAT WAS TESTED, AND HELD.** Before the GoVac manuals existed on
disk, 400/500/508 were inferred from two independent local lines: the reg-code sitting on
exactly one Western manual, and the key structure (`r25799` = `r2579`+digit = L40 Ultra
AE; `r24162` = `r2416`+digit = X40 Ultra). Ablated first — stem-minus-a-digit resolves for
only **11% of 300 random keys**, so the rule is not vacuous. All five later matched the
vendor documents exactly. Worth remembering as the shape of a claim that CAN be checked:
two lines from different data, plus an ablation showing the instrument can say no.

---

## CHANNEL MAP — what actually yields manuals

| channel | yield | notes |
|---|---|---|
| `global.dreametech.com` index | **118 PDFs → 228 keys** | 234 slugs scraped; server-rendered |
| `support.dreametech.com` help centre | **walk IN PROGRESS** | **2,133 articles** |
| `dreametech.zendesk.com` help centre | 62 PDFs → +57 keys | **only 784 articles — a DIFFERENT, smaller instance** |
| Mova (`us`/`www`/`de`/`fr`/`it`.mova.tech) | **45 PDFs** | 259 distinct files; de/fr/it ≈ 80 each |
| Retailer CDNs (Home Depot etc.) | works | archives DISCONTINUED models |
| Upstream GitHub issues | 54 platforms, 24 on our missing list | **identity, not manuals** |
| manualslib | 1 of 245 | `robots.txt` disallows `/download/` — do not script it |
| `www.dreametech.com` (US) | untested | **JS SPA**, 3.1 MB with zero links in HTML |

⚠ **TWO HELP CENTRES EXIST.** `dreametech.zendesk.com` (784 articles) 404s on articles
that `support.dreametech.com` (2,133) serves. I walked the small one and reported its
result as the channel's yield.

---

## THE LESSON THIS SESSION ACTUALLY TAUGHT

**Seven broken probes, one pattern: a transform applied to ONE SIDE of a comparison,
or a narrowing decision made BEFORE seeing the evidence.**

1. `--biggest-only` ranked PDFs by languages in the FILENAME → downloaded the Estonian and
   Khmer editions of four models and reported "0 failed".
2. Attachment regex required `.pdf` → Zendesk uses `article_attachments/{id}`, no
   extension. Zero across 140 sections.
3. Article bodies come back EMPTY from the list endpoint; attachments are a separate
   resource (`/articles/{id}/attachments.json`).
4. PDF regex required `https?://` → Shopify serves protocol-relative `//`. This produced a
   **confident false negative for ALL of Mova**, which I then "confirmed" three ways —
   index, 12 slug guesses, six product pages — every one using the same broken pattern.
   *Three confirmations of one bug read exactly like evidence.*
5. Walked the wrong help-centre HOST, then misdiagnosed it as my own section filter.
6. Worst: a JS-filter check returned `0` vs `0` and printed **"raw HTML covers the
   catalogue"** — `0 <= 0 * 0.25` is `True`. It had been rate-limited (HTTP 429) and the
   silent `except: continue` turned "the server refused me" into "nothing is there".

**A search engine has no priors about corpus shape. I have nothing but priors, and mine
were wrong every time.** That is the real reason to farm retrieval out to
Gemini/ChatGPT — not breadth, but that they do not need to guess the shape first.

⚠ **NEVER RENDER A VERDICT ON AN EMPTY SAMPLE.** Guard every summary with "did I measure
anything at all?" — this is written into three scripts and I still shipped one without it.

---

## GOVAC — 12 unresolved r-codes, current disposition

Verified against vendor documents, not assertions:

* `r25642` **GoVac 300 Kit — CLOSED.** Its manual prints regulatory model **`RLD35GD`**,
  *identical to GoVac 300's*. Same hardware, different box. Inherits GoVac 300 → D20 Plus.
* `r9524` / `r95249` GoVac 200 — manual in hand (`RLF12SE`).
* `r5314` GoVac 300 → D20 Plus — Dreame's own maintenance kit names both.
* `r95279` / `r63015` **GoVac 205 Plus — manual IN HAND but IMAGE-ONLY.** 26 pages,
  12.6 MB, entire text layer is six characters (`US-A00`). **SOLVED 2026-08-25** — see
  below; it renders and reads cleanly now.
* `r5021`, `r25799`, `r24162`, `r95385` — ChatGPT supplied regulatory codes
  (`RLD52SE`, `RLL77SE`, `RLX63CE-1`); **verification against held manuals was RUNNING
  when this was written** (`scripts/.../reg_codes.py`). Not yet confirmed.

⚠ **A RETAILER LISTING IS NOT A MANIFEST.** A Home Depot PDF listed as "Dreame Robot
Vacuum 3-in-1 E20" is a **eufy** manual — 23 eufy mentions, zero Dreame,
`support@eufy.com`. Both brands sell an "E20". Quarantined as
`MISFILED-eufy-E20-not-dreame.pdf`. **Brand-verify every retailer PDF from its CONTENTS.**

---

## S-SERIES → WESTERN L/X — Chris was right, my instrument was blind

r-code identity found only 2 of 17 S40 keys mapping to L40/L40s — but **both landed on
L40/L40s and nothing else**. Then the calibration: **93 names appear under more than one
r-code (same product by construction), and capability-profile matching detects that
relationship only 28% of the time.** So `UNVERIFIABLE` means *cannot tell*, never *false*,
and my "only 25% supported" was a floor I nearly reported as a verdict.

---

## SCRIPTS BUILT (all committed, `19eb3333` and earlier)

* `dreame_manual_pipeline.py` — index / links / fetch / locate
* `dreame_i18n_segment.py` — language-block segmentation, `--verify-only` refuses
  anything it cannot cleanly split. **37 of 44 manuals passed at last full run.**
* `dreame_target_models.py` — the four-bucket classifier and the honest denominator
* `verify_rebadge_claims.py` — adjudicates external claims; exits 1 on conflict
* `pdf_layout_dump.py` — visual reading order. ⚠ **SUPERSEDED.** It reconstructs reading
  order from text matrices *because* there was no rasteriser. There is one now; prefer
  rendering the page.
* `verify_dreame_guide_provenance.py` — 264 strings scored, 0 defects

## HAND-OFF PACKAGE

`durable/dreame-port-fixture/handoff/` — 8 batches + `govac.md`, retrieval-only briefs
carrying the "filename is not a manifest" and "retailer listing is not a manifest" rules.
**They are now over-scoped** — regenerate against current coverage before sending.

## IMMEDIATE NEXT STEPS

1. Read the two background jobs: reg-code verification, and the
   `support.dreametech.com` walk (2,133 articles — expected to be the biggest haul yet).
2. Re-run coverage; re-generate the hand-off batches against what is actually left.
3. **Transcription backlog is between ~0 and ~111 keys**, not the "153+" this note
   previously claimed — that figure came out of the broken filename join. At the stem
   ceiling 186 target keys have a manual and 75 have a guide; at the exact join far
   fewer. The reg-code output is what turns this into a real work queue.
4. **Regenerate the hand-off briefs' RETURN shape.** The tables already list every
   marketing name under a stem, so the ambiguity is disclosed going out — but the
   example JSON keys the reply on `r_code`, which throws that disambiguation away on
   the way back. A manual for `r500` is useless unless the reply says WHICH of its
   eight names it covers. Make `models_named_on_that_page` the join key and demote
   `r_code` to a bucket label.
