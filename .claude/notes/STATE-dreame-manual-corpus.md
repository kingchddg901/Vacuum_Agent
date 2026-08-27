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

## ⚠ THE DEVICE LIST RENAMES THINGS. THREE TRANSLATION LAYERS, ALL MEASURED

A name that returns nothing is often the vendor's name for a real product, rewritten.

**1. SUFFIX LETTERS EXPANDED TO WORDS.** `GoVac 100 Lite` and `GoVac 200 lite` are
declared names; retail sells **`GoVac 100L`** and **`GoVac 200L`**. Searching "Lite"
returns nothing because nobody writes it. Try the letter form before concluding absence.

**2. CHINESE VARIANT NAMES TRANSLATED TO ENGLISH.** The parenthetical descriptors are
literal renderings of the Chinese retail line, confirmed against Chinese reviews:

    X50 Pro 增强版      -> X50 Pro (Enhanced Edition)
    X50 Pro 履带版      -> X50 Pro (Tracked Version)
    X50 Pro 超薄上下水   -> X50 Pro (Ultra-Thin embedded) + water supply
    X50 Pro 滚筒版      -> the Roller variants

  So these are REAL products with REAL manuals, unfindable in English and findable in
  Chinese. My earlier "internal SKU labels, unhuntable" was half right and half wrong.

**3. PRO IS THE CHINA NAME FOR THE GLOBAL ULTRA (current generation).** `X50 Pro` is
`r2489`; `X50 Ultra` is `r2489a/b/c`. Same platform, and `R2489A-X50_Series` is the manual
for both. Bare `Pro` was a real retail name in the PREVIOUS generation (D9 Pro, L10 Pro,
W10 Pro, X20 Pro — all held) and stopped being one after it. Dreame publishes
`x50-pro-ultra-user-manual` pages and NO bare-Pro page.

⚠ **REBRANDS CLOSE MODELS THAT HUNTING NEVER WILL.** `GoVac 100L` = `D9 Max Gen 2`,
proven by the regulatory code `RLD34GA` printed on a Walmart spec sheet and on nine
manuals we already hold. No document had to be found. **A retailer spec sheet carries the
regulatory code, and the regulatory code is the join.**

---

## ⚠ CORRECTION: "GOVAC IS FULLY CLOSED" WAS WRONG

Ten GoVac models were enumerated from the help-centre haul and every one resolved to a
Western sibling. That was true. The device list declares **FIFTEEN** GoVac names, and the
enumeration was never checked against the declaration — a set was closed and reported as
the set. Second time in this campaign. **Coverage from scopes, never from findings.**

Honest state: 9 held and named · `GoVac 205 Plus` (+case twin) held but vector-outline so
no text join can read it · `GoVac 400 Complete` inherits GoVac 400 by the Complete rule ·
`GoVac 505` held but not a declared model · `GoVac 100L` = D9 Max Gen 2 ·
**`GoVac 200L` (`RL12SA`) is the one real gap** · `GoVac 510 Complete` returns zero hits
in English AND Chinese, has no base model and no help-centre article — likely not a product.

---

## ⚠ THE R-STEM IS A BATCH, NOT A PRODUCT — REJECTED BY ITS OWN CONTROL

A sweep rescuing every missing name whose r-stem is shared with a held name returned 53
names / 79 keys and would have lifted coverage to 52%. **It failed its positive control:
among held pairs where BOTH manuals can be read, a shared stem predicts a shared
regulatory code only 45% of the time.** `Aqua 10 Roller` shares stem `r501` with
`L10s Ultra Gen 3`, `L40 Ultra Gen 2` and `L50 Ultra CE` — four different certified
machines. All 53 withdrawn.

⚠ The registry ablation could not fire at all — zero overlap between the rescued names and
the DoC index. **A guard that cannot go red proves nothing**, so the control had to be run
where ground truth existed instead.

---

## CHINESE DOMESTIC CHANNEL — MAPPED, MOSTLY GATED

| source | state |
|---|---|
| `dreame.tech/upload/down/` | **dead** — real once, now swallowed by a Nuxt SPA catch-all |
| `doc.quark.cn` | JS shell -> page images via wenku, no file |
| `pan.quark.cn` | listing API is PUBLIC, download is gated |
| `shuomingshu.net` | works; **5 robot manuals in 90 pages**, proxies to Quark |

Retrieval is a browser job, not a script job. Three domestic manuals obtained this way:

    R2548   S50 Ultra (Ultra-Thin embedded)   RLS45CE / RLS46CE / RLS55CE
    R2580   X50 Pro (Tracked Version)         RLZ61CE
    R2580X  tracked + plumbed                 RLZ61CE  (same certified machine)

All three from 追觅贸易（天津）有限公司 — first-party, not rebadges. They carry the first
corpus evidence for **履带 tracked mop**, **升降 lifting LiDAR** and **机械足 mechanical
feet**. ⚠ pypdf reads ~11 of 44 pages on these: identity and codes are solid, the
maintenance steps are NOT readable without rendering.

⚠ **GoVac HAS NO CHINESE PRESENCE.** Chinese-language hits are 北美/加拿大省钱快报 —
diaspora deal sites quoting USD. JD, Suning and Zhihu show only the domestic line.

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

---

## THE SWARM (2026-08-26)

207 names were still open after every channel-walk this campaign could think of.
Chris authorised a fan-out: **21 agents, 10 names each, dig everywhere, surface links
they cannot follow.** The brief is in the workflow script and carries this campaign's
whole failure list as instructions — search the marketing name never the model key;
try the letter-suffix retail form (`100L` not `100 Lite`); parenthesised descriptors
are translated Chinese retail names, so search the Chinese; check warehouse clubs;
brand-verify from inside the PDF; a filename is a claim, not evidence; and report a
blocked link as a **hit**, never as a negative.

**Why the structural bottleneck matters more than the count:** only 6 of the 207 open
names carry a known regulatory code. 201 have none. Without a code we cannot tell how
many distinct *machines* those 207 names represent — the answer could be 40 or 200,
and every plan built on the name count is built on sand. So the swarm was told to
record a reg code wherever it appears — retailer titles, box photos, spec tabs,
certification filings — and that a spec page carrying a code with no manual attached
is a **good** result. The codes are worth more than the manuals; they are what
collapses the list.

### Two rules the swarm exists to test
* *Absence of a search hit is not absence of a product.* This campaign wrote off
  `GoVac 510 Complete` as probably-not-real. Chris found it on Costco Canada, item
  1733460. The blind spot was **retail channel**, not search quality — warehouse clubs
  and channel-exclusive SKUs are close to invisible to normal search, and that is the
  entire point of a channel-exclusive rename.
* *A found set is not the set.* "GoVac is fully closed" was reported off a haul of 10
  when 15 are declared. Second time this campaign an enumeration was mistaken for a
  census. The swarm's own output is subject to the same rule: **an agent that returns
  nothing leaves its 10 names UNSEARCHED, not clean** — the script logs dead agents
  separately for exactly this reason, and those names must not be scored as negatives.

## RECURRING DEFECT — cp1252 ON WRITE

`open(path, "w")` on this box defaults to cp1252 and dies on the first CJK character
or `⚠`. It has now killed the *output* of four completed jobs — the work succeeded and
the write threw. **Always `pathlib.Path.write_text(..., encoding="utf-8")`, and
`PYTHONIOENCODING=utf-8` for anything that prints.** The failure mode is the expensive
one: full cost paid, nothing kept.

---

## THE RESYNC: NAME <-> CODE <-> MACHINE (2026-08-26)

The objective moved. Manuals stopped being the goal; the goal became collapsing 339
marketing names onto the far smaller set of machines behind them. Chris's argument was
from plausibility - **339 names is too large a line for anyone to actually maintain, so
most of it has to be rebadging** - and the evidence now supports it.

### The artefact that solves the resync
`https://global.dreametech.com/pages/declaration-of-conformity` publishes 299
certification PDFs whose FILENAMES carry all three identifiers at once:

    DoC_English-R9527-RLF41GD_F20_Plus_<uuid>.pdf
                 ^stem  ^code   ^marketing name

That is the join the campaign had been missing. 171 filings parse; 54 target names gain
a regulatory code from it alone.

### Confirmed: the parenthesised descriptors collapse
These are the highest-value rows, because descriptor variants are most of the open list:

    RLP23SE   P50 (Auto Water Supply and Drainage) | P50 (Selected Auto...) | P50 (Selected Edition)
    RLZ11HE   P70 (Clean World Edition) | P70 Pro | P70 Pro (Auto Water Supply and Drainage)
    RLR81CE   Aqua10 Ultra Track | ...Complete | ...S
    RLL42SDA  L10s Pro Gen 2 | L10s Pro Gen 3        <- a generation that is one filing
    RLL53SE   L10s Ultra Gen 3 | L50 Ultra CE        <- across product LINES
    RLF41GD   D20 Air Plus | F20 Plus                <- content-verified in both PDFs

`Complete` = packaging is now confirmed on five more base codes (RLX41CE, RLX63CE,
RLX85CE, RLR81CE, RLH71DE). `Heat` = firmware confirmed on RLL82CE.

### The code is on manuals we ALREADY HOLD
94 held manuals print a regulatory code and no recognised name - non-English editions,
print files named by stem. Under a name join they are invisible: **we own the document
and cannot tell what it is for.** Joining through the code resolved 88 of 94 and closed
five open names (L30s Ultra, L40 Plus, X50s Pro Ultra, X60 Master, X60 Pro Ultra
Complete). Only 4 codes on held manuals map to no known name: RLE22GD, RLE22GA,
RLE23SD, RLR61CE. Those four are the genuine unknowns.

## PROXIMITY IS NOT ASSERTION - three instances in one night

Every wrong number tonight had the same shape: a join that treated *appearing near* as
*being about*.

1. **Rebadge count 67 -> 15.** Credited every code MENTIONED in a record to that
   record's name. Put `F10 Plus` under RLF41GD when its own manual says RLF11SE.
2. **Cartesian code<->name pairing.** A document with 6 codes and 3 names does not
   assert 18 pairings. Across the corpus that manufactured up to **171 false edges**.
   Fixed by using only 1xN or Nx1 documents; 32 ambiguous documents excluded.
3. **Name co-listing.** A name in a manual is not proof the manual COVERS it -
   compatibility lists name models too. Guarded by excluding high-count outliers.

The tell in all three: the number went UP when the rule got looser. A join that finds
more when you relax it is measuring the rule, not the world.

## CONFIDENT ZEROS - the regex family

Four separate zero-results tonight were the pattern, not the corpus:
* `RL[A-Z]{2}` demanded two letters after RL. Real codes have ONE (`RLX85CE` = RL-X-85-CE).
  Found zero codes in a file containing six.
* Trailing letters are 1 to 4 (`RLS3D`, `RLS6LADC`), not a fixed 2.
* Matched against the URL-ENCODED filename.
* **`\b` between `RLS3D` and `_D10_Plus` never fires - underscore is a word character.**
  Dropped 155 of 175 filings. This campaign had already been bitten by this once.

Rule earned: on this data, anchor with `(?<![A-Za-z0-9])` / `(?![A-Za-z0-9])`, never `\b`.

## INSTRUMENT NOTES
* **pypdfium2 is 21x faster than pypdf** for text extraction on this corpus (0.35s vs
  7.47s per file). A 4-hour job becomes 12 minutes.
* **The undirected sweep beat the directed one.** Asking "what is X equivalent to"
  primes for name-matches and discards everything else; asking "what is X in China / in
  Japan / anywhere" returned ~200 code strings against the directed sweep's 38, plus
  1,674 raw co-occurrence observations. Chris's method, and it won on the metric that
  mattered. Record co-occurrence WITHOUT letting the agent judge relevance - the
  interpreting happens over the whole pile, not at any one page.
* **AliExpress answers scripted searches on regulatory codes AND internal stems**
  (`R2489A` returns results) - sellers index on factory numbers, and a spare-part
  compatibility list is a maintenance-equivalence graph. But it throttles fast: the same
  query returned 636 KB then 2.4 KB a minute later, and a stub reads exactly like "no
  results". **Alibaba is a hard block** - identical 89,630-byte page for every query.
  Both are better done in a human browser than in a script.

---

## THE S-SERIES RULE: ONE ROBOT, THREE DOCKS (2026-08-26)

A 7-agent Chinese-language sweep of the 69 open S-series names (812k tokens, a fifth of
the earlier English swarms) returned the structural answer the whole campaign needed.
Chinese lineup guides state it outright:

    追觅每款机型都有三种配置：基础水箱版、上下水版和超薄上下水版
    Every Dreame model ships in three configurations: basic water-tank, plumbed
    (auto water supply and drainage), and ultra-thin plumbed (cabinet-embedded).

**The parenthesised descriptors are DOCK configurations, not robots.** One robot times
three docks equals three catalogue names. Dreame also built the 超薄嵌入式 line by taking
robots from *different* series and pairing them with the plumbing module - which is why
the ultra-thin names cut across series so confusingly.

Confirmed by CCC certificate, same certificate on both members of each pair:

    2024010708696171   S50 Pro          = S50 Pro (Ultra-Thin embedded)
    2024010708672454   S50 Ultra        = S50 Ultra (Ultra-Thin embedded)
    2024010708672871   S40 (Enhanced)   = S40 (Enhanced Ultra-Thin embedded)
    2024180708051259   S30 Pro Ultra (Enhanced) = ...(Enhanced Ultra-Thin embedded)
    2024180708051259   all three S60 Premium Roller trims

### Cross-name collapses - the ones nobody would guess
* **S60 Disk = S50 Pro.** The S60 Pro 圆盘版 carries CCC `2024010708696171`, byte-for-byte
  the S50 Pro's certificate. It is the S50 Pro platform sold under the S60 name.
* **S40 Pro = S40 (Enhanced).** Same CCC `2024010708672871`.
* **S10 Pro Plus 机械臂版 = S10 Pro Ultra 机械臂版.** One regulatory code `RLS62CE`, and a
  single retail listing names BOTH: 「追觅 S10Pro Ultra/Plus机械臂版 扫地机器人 RLS62CE」.
* **S10 Pro (Hot Water) = S10 Pro.** Chinese retail files both under 型号 "S10 Pro" - the
  两 names on our list are one SKU.
* **S60 Pro Roller is handed down from X60 Pro 滚筒版** (下放), 33000Pa vs 36000Pa.

### The counter-example that matters most
**S60 Pro Disc is NOT a mop-swap of S60 Pro Roller - it is a DIFFERENT ROBOT under the
same marketing name.** Disc sits on the S50 Pro platform; Roller sits on the X60 Pro
platform. Same two words in the name, two unrelated machines. Any rule that collapses on
name similarity gets this backwards.

### CCC certificates are FAMILY-level - coarser than an RL code
`2023010708528676` covers nine names including S10 Pro, and was separately attributed to
X40 Pro Ultra. A CCC certificate covers a manufacturer + product family, not one model.
**A shared CCC alone is NOT proof of one machine.** It becomes strong only when the spec
tab agrees too - identical 净重 / 额定功率 / 产品尺寸. The agents spotted this themselves
and flagged it; it is the domestic analogue of the base-code-vs-exact-code distinction.

### Maintenance-relevant deltas (the reason we asked for differences, not equivalences)
* The S10 热水版 **removed** the camera and the auto cleaning-solution dosing versus the
  old S10 - so there is no cleaning-solution cartridge to service. A procedure written
  from the older manual would describe a part the machine does not have.
* S10 Pro Plus 机械臂版 differs from S10 Pro Ultra 机械臂版 **only** by omitting the
  割毛滚刷 (active hair-cutting roller, ~300元, separately purchasable). Every procedure
  transfers except the roller one.
* S40 Pro vs S40 增强版: navigation hardware differs (LDS vs LDS+structured light).

### Parts as identity
* `RAW0` - 自动上下水模块, fits S10 and S10 Plus.
* `B101CN` - brush/mop/filter kit sold as fitting **S10, X10, L10s Ultra, L10s Pro** -
  independent corroboration that the domestic S10 and the global L10s Ultra are one
  maintenance group.
* `RLS6LADC` is the platform code for the **global L10s Ultra**, and Chinese sources
  describe it as "also known as the S10 series". Variants seen: `-2` (China domestic),
  `-6-EU/AU`. **That is the S<->L bridge, at platform level.** We hold L10s Ultra manuals.

---

## CCC IS A GROUPING, NOT AN IDENTITY - and the registry is captcha-gated

Two certificate detail pages, read from the official CNCA registry (Chris solved the
captchas; the pages are not machine-reachable), settled a question that had been carrying
most of the S-series collapse.

### CCC certificate 2024010708696171
    产品类别    0708：真空吸尘器
    规格型号    RLX93CE、RLX94CE、RLX75CE、RLX75CE-1、RLX93CE-1、RLX96CE、RLX97CE
    基站        RCXE0106、RCXE0107、RCXE0101、RCXE0102、RCSE0105、RCXE0106-1、RCXE0203
    委托人/生产者 追觅贸易（天津）有限公司

**ONE certificate carries SEVEN distinct regulatory codes.** Therefore two marketing names
sharing a CCC number are NOT thereby one machine - they may be two different codes inside
the same family. A CCC is a certification FAMILY, one level coarser than the RL code, in
exactly the way a base code (RLX85CE) is coarser than an exact code (RLX85CE-4).

**This invalidated 7 of the 12 "defensible" S-series merges**, all of which were built on
shared-CCC. What survives is only:
  * S10 Pro Plus 机械臂版 = S10 Pro Ultra 机械臂版  (shared exact code RLS62CE, and one
    retail listing names both)
  * S10 Pro (Hot Water) = S10 Pro                   (same 型号 in CN retail)
  * S60 Pro Disc x3                                  (same 型号 S60Pro圆盘版)
Honest S-series collapse: **69 open names -> about 65**, not the 57 previously reported.

### The seven codes are NOT in our data at all
RLX93CE / RLX94CE / RLX75CE / RLX75CE-1 / RLX93CE-1 / RLX96CE / RLX97CE appear in no
manual, no DoC filing, and no swarm result. (We hold RLX96DE and RLX97DE - a D suffix,
not C.) Seven certified robots we had no record of. **Evidence that the catalogue may be
LARGER than 339 names implies, not smaller** - a point against the strong rebadging
hypothesis, from the most authoritative source available.

### Why this cannot be harvested
The detail URL carries `captcha_output`, `pass_token` and `gen_time` - one captcha solve
per certificate. Reusing a solved token against other certNumbers would be circumventing
the control, so it is not an option. 198 household certificates for 追觅贸易（天津）,
165 of them dated 2025-2026. Not harvestable by either of us at that rate.
Worse, `规格型号` is sometimes just `见附页` (see attachment) - certificate 2024010708672871
defers its model list to a downloadable attachment, so a solved captcha does not even
guarantee data.

### Incidental
Both sampled robot certificates are 暂停 (suspended) with the identical window
2026-08-24 to 2026-11-23. A simultaneous suspension across multiple Dreame vacuum
certificates - noted, unexplained, and not something this project needs to resolve.

## THE RECURRING ROOT CAUSE, STATED ONCE

Every wrong number this campaign produced came from letting a GROUPING identifier stand
in for an IDENTITY identifier:
    filename shares a stem            -> assumed same product
    record mentions a code            -> assumed the name carries that code
    document contains code and name   -> assumed they pair (cartesian)
    two names share a CCC certificate -> assumed same machine
Each time the count went UP when the rule got looser, and each time that was the tell.
**A join that finds more when you relax it is measuring the rule, not the world.**
Rank of evidence, strongest first, for anything built on this corpus:
    1. a code and a name printed in the same document, read from the document
    2. a vendor certification FILENAME carrying both
    3. an exact regulatory code shared between two names
    4. a shared 型号 in retail
    5. a shared BASE code            <- family, not identity
    6. a shared CCC certificate      <- family, not identity
    7. a code mentioned in prose near a name  <- not evidence

---

## THE CENSUS: 107 ROBOT-VACUUM CERTIFICATES, ONE ENTITY, CHINA ONLY

Filtering the CNCA registry by 获证组织名称 = 追觅贸易(天津) AND 产品名称及单元（主）=
智能吸尘器 yields the robot-only subset. Counted, not estimated:

    107 certificates      58 有效 (valid) · 23 暂停 (suspended) · 26 注销 (cancelled)
    by year   2020:4  2021:6  2022:5  2023:15  2024:23  2025:31  2026:23

That is **one entity, one country, robot vacuums only**. Our entire target catalogue is
339 marketing names spanning Dreame + Mova + Trouver + Xiaomi across every market. And the
single certificate we opened carried SEVEN distinct regulatory codes, so 107 is a floor on
the number of certified domestic platforms, not a ceiling.

### VERDICT ON THE REBADGING HYPOTHESIS
Chris's argument was: 339 names is too large a line for anyone to maintain, therefore most
of it must be rebadging. **The registry says otherwise.** Dreame certifies robot vacuums
at a rate of ~25-30 new certificates a year and has done since 2023. They really do build
and certify this many distinct machines.

The collapse we did find is REAL but LOCAL:
  * dock variants within one family (水箱版 / 上下水版 / 超薄上下水版) - one robot, three names
  * trim within one family where a certificate or 型号 is shared
  * "Complete" packaging variants - confirmed on five base codes
It is NOT a catalogue-wide veneer over a handful of machines. The honest S-series number
is 69 open names -> about 65 on sound evidence.

### THE 有效 FILTER HID HALF THE DATA
The first 198-row household pull was filtered to 有效, which silently dropped all 23
suspended and all 26 cancelled robot certificates - 49 of 107, 46%. Three CCC numbers were
briefly written off as "not present" purely because of that filter. **A status filter is a
sampling decision, and a default one is still a decision.** Seven of the nine
agent-sourced CCC numbers are confirmed robot certificates of this entity once the filter
is off.

### INCIDENTAL, UNEXPLAINED
23 certificates share the identical suspension window 2026-08-24 to 2026-11-23. A mass
simultaneous suspension across Dreame's vacuum line. Recorded because it is the kind of
fact that explains a future surprise; not something this project needs to resolve.

## COVERAGE AGAINST THE SUPPORTED SURFACE (2026-08-26)

Chris's scope ruling: "we will support in general what they have listed."
The list is Tasshack's `docs/supported_devices.md`, held locally at
`durable/dreame-port-fixture/catalogue/supported_devices.md` — **741 models,
386 distinct names**. (An earlier WebFetch of the same page returned 344 models
and asserted a total of 511. Both wrong. The local copy is authoritative.)

Measured against those 741:

| | models | of 741 |
|---|---|---|
| guide authored (the 7 families) | 202 | 27% |
| manual held in corpus | 383 | 51% |
| **held but NOT authored** | **261** | **35%** |
| no manual, no guide | 278 | 38% |

Three findings.

**The 261 is the cheapest work left.** 98 names have manuals on disk and no
guide written — no sourcing, no scraping, no new jobs. Not fringe hardware:
matrix10ultra (13 models), p70proultra (8), s70ultraroller (7), s70roller (7),
s10 (6), z60ultrarollercomplete (6), aqua10ultrarollercomplete (6).

**Every authored guide is `dreame.*`.** All 154 non-Dreame IDs (mova 102,
xiaomi 25, trouver 13, ijai 11, deerma 2, szkj 1) have zero coverage. 85 of
them are in the authorable pile (mova 67, trouver 10, xiaomi 7, ijai 1), so
the ruling is mostly reachable from disk.

**Nothing in the corpus was wasted.** Zero of 123 corpus names fall outside
their list.

### Caveat: the 51% may be circular

Zero corpus names outside the catalogue is a suspicious result. Most likely
`manual_names.json` was named *from* `supported_devices.md`, which would make
the corpus→list join self-confirming — blind to any name the catalogue does
not declare. **Do not spend the 51% figure without breaking this.** Re-run the
join off manual *text* (`derived/attested.json`, `derived/manual_text_cache.json`,
94 MB) rather than assigned filenames. The 27% authored figure does not depend
on this join and stands.

### Scope verdict

The census method was right; the population was too big. 671 keys / 339 names
was aimed past a 741-model / 386-name surface. The release gate is unchanged
and unmet: **no `BRAND_REGISTRARS` row exists, and no model→family mapping
exists at all** — so even the 202 covered models resolve to nothing at runtime.

Method: series-token join (`x50 x60 l20 x40 l50 l10s`) against normalised
(alnum-lowercase) names. Prefix-matching the raw family keys undercounts —
`l10s_gen2` scores 0 because the catalogue writes "L10s Pro Gen 2"
(`l10sprogen2`), which never starts with `l10sgen2`.

## THE DOCUMENT IS THE UNIT (2026-08-26)

Two manuals arrived from Chris's hunt. Together they settle how the remaining
202-name hunt should be run.

    R9528A   "Dreame Aqua10 Ultra Track Series"    RLR81CE / RLR81CE-1   station RCZE0308
    R9535    "Dreame Aqua10 Ultra Roller Series"   RLH71DE / RLH71DE-1   station RCHE0401

Each document is scoped to a SERIES and declares exactly two codes, a base and
a `-1`. The series name is on the cover page - first-party, not a filename
claim. **One document retires ~2 hunting-list rows.** 202 names is therefore
~100 documents, not 202.

### `-1` is a SKU variant, not a machine variant

On the Track side the spec table gives ONE value column for both codes
(charging 4.5 h, 14.4 V, 75 W, 2400-2483.5 MHz), ONE base station, ONE battery
pair, and the EU DoC names them as a single radio equipment type
"RLR81CE/RLR81CE-1". The English text never hedges by model - no "depending on
model", no "selected models"; the single "depends" is about usage frequency.

This refines THE S-SERIES RULE recorded above. Here it is not one robot three
docks - it is **one robot, one dock, two SKUs**.

### Track vs Roller costs exactly one part

Maintenance tables diffed part-for-part (EN, R9528A p7 vs R9535 p13). 27 parts
shared with identical names AND identical intervals. The complete delta:

    TRACK only    Washboard filter            (once every 1-2 months)
                  Washboard heating module    -- same component as below,
    ROLLER only   Heating module              -- relabelled
                  Fluffing roller             <- the only genuinely new part

So a Track manual is ~96% of the upkeep content for the whole Aqua10 family.
The library's existing split of `washboard` vs `washboard_filter` across
families turns out to BE this Track/Roller distinction - the taxonomy already
anticipated it.

### Chris's ruling: plumbing is an accessory, not a variant

Chris: "master we found is the plumbed in version. really no extra maintence
that i can tell some setup though." The documents confirm it and go further -
BOTH stations carry the same callout:

    "Reserved Slot for Connecting the Water Hookup Kit for Auto Refilling and
     Draining. Note: the kit needs to be purchased separately. (Only available
     in specific regions)"

Every unit ships plumbing-capable; the kit is bought separately. It adds ZERO
rows to either maintenance table. **Aqua10 Ultra Roller Master (RLH91DE) joins
the Roller group.**

Generalised: **configuration variants do not fork a maintenance guide.**
Plumbed vs tank-fed, bundle contents, `-1` suffix, dock hardware - none moved a
maintenance line. Only the floor-contact mechanism did. Parts-groups are driven
by MECHANISM, not SKU, which is why 202 names collapse toward the artifact's
own count of 23 parts groups.

### Consequence: stop hunting Aqua manuals

Both Aqua10 mechanisms are now in hand, so the Aqua parts universe is complete.
The remaining Aqua rows (Aqua10 Roller RLH31CE, Aqua10s Roller AE RLH21SE,
Aqua20 Roller FE, Aqua10 Pro Roller) need a code->group ASSIGNMENT, not a
manual. That is a lookup line, not a hunt.

### Unresolved - do not write this down as fact

Chris's find maps RLH71DE -> "Aqua 10 Pro Roller", but R9535's cover calls its
series "Aqua10 Ultra Roller", and "Aqua10 Ultra Roller Master" carries a
different code (RLH91DE) on the hunting list. So RLH71DE / RLH71DE-1 are two
Ultra Roller SKUs whose marketing names are NOT pinned by the document.
Proximity is not assertion - needs a second source.

Also: "Aqua 10 Pro Roller" and "Aqua10 Pro Roller" are near-certainly one
machine occupying two hunting rows. A spacing-variant dedup sweep across all
202 is probably worth one script.

### Hardware difference with no upkeep cost

Track station RCZE0308 has a UV lamp ("Solid Blue: UV light is working");
Roller station RCHE0401 documents only white and orange. Power differs too
(20 V 2 A / 89 W vs 20 V 3 A / 112 W). Generates no maintenance task, but
matters for station-level content.

### Cost to author the Aqua10 families

~15 components, of which FOUR are new to DREAME_UPKEEP_GUIDE_LIBRARY:
`fluffing_roller` (Roller only), `omnidirectional_wheel`, `retractable_legs`,
`clean_water_tank`. Everything else already exists in the taxonomy.

## THE 51% CAVEAT WAS POINTED THE WRONG WAY (2026-08-26, same day)

Recorded above: "Flagged the 51% as possibly circular ... Do not spend the 51%
figure without breaking this." That warning was wrong in DIRECTION. Resolved by
reading `scripts/dreame_corpus_name.py` instead of inferring from the data.

The circularity is REAL: `--devices` is a required argument and the matcher is
`build_matcher(target_names)` built from `supported_devices.md`. The namer
cannot emit a name the catalogue does not declare.

But that makes "0 of 127 corpus names outside their list" a TAUTOLOGY, not
evidence of an inflated number. It was guaranteed by construction, so it is
not a finding and should never have been reported as suspicious.

The 51% itself is a FLOOR:
  - it counts only COVERED (a manual's TEXT names the model), which is the
    script's own strict state;
  - ATTESTED (filename-only claims) is deliberately excluded from it;
  - it can only MISS names the catalogue does not declare - the script's own
    example is `X60 Ultra Complete`, a real retail name the integration never
    declares.

So the number is conservative and can be spent. True coverage is somewhat
higher than 51%, not lower.

Also corrected: matrix10ultra was reported here as the biggest name in the
HELD-BUT-NOT-AUTHORED bucket, which was right. It was NOT "uncovered" - a
later restatement in conversation said so and that was a slip. The RLX95CE
finding (Matrix10 Ultra = X50 Ultra MatriX) does not move the coverage number;
what it buys is that one guide serves both names.

### The code merge cannot expand coverage - structural, not a bug

Tested: merge every supported name that shares a regulatory code with a name
the corpus already holds. Result +0 models, +0 names. Codes are observable ONLY
through manuals already held, and those manuals' names are already counted. No
corpus-internal join can grow the number.

Consequence: the captcha-gated registry walk is the ONLY lever that can expand
coverage beyond the corpus. Worth weighing that against simply authoring the
261 held-but-unauthored models, which needs no new sourcing at all.
