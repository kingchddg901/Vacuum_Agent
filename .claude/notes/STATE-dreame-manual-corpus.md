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
| manuals in hand covering target keys | ~285+ (**42.8%** at last count) |
| manuals on disk | **229 files, 2.8 GB** |

⚠ **TWO DENOMINATOR ERRORS, BOTH IN MY FAVOUR, BOTH CAUGHT LATE:**

1. I parsed only `dreame.vacuum.*` = 587. The integration ALSO declares `mova` (102),
   `xiaomi` (25), `trouver` (13), `ijai` (11), `deerma` (2), `szkj` (1). **741 total, all
   suffixes distinct, zero overlap between prefixes** — they are additional devices, not
   rebadges. Every figure was 21% too generous.
2. I then read `DEVICE_INFO` `field[0]` as a product class and EXCLUDED 118 real robot
   vacuums. **It is the BRAND** — dreame 0, xiaomi 1, mova 2, trouver 3, exactly 1:1 with
   the prefix. Mova's 102 keys carry segment capabilities on 99. The tell was that the
   excluded set equalled a category I already had: *a filter whose output equals an
   existing category is not filtering, it is renaming.*

`scripts/dreame_target_models.py` now does this correctly. Re-run it rather than quoting
numbers from memory.

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

**Six broken probes, one pattern: a narrowing decision made BEFORE seeing the evidence.**

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
  12.6 MB, entire text layer is six characters (`US-A00`). No OCR and no rasteriser in
  this environment, so `pdf_layout_dump` and the i18n segmenter are blind to it.
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
* `pdf_layout_dump.py` — visual reading order (no rasteriser exists here)
* `verify_dreame_guide_provenance.py` — 264 strings scored, 0 defects

## HAND-OFF PACKAGE

`durable/dreame-port-fixture/handoff/` — 8 batches + `govac.md`, retrieval-only briefs
carrying the "filename is not a manifest" and "retailer listing is not a manifest" rules.
**They are now over-scoped** — regenerate against current coverage before sending.

## IMMEDIATE NEXT STEPS

1. Read the two background jobs: reg-code verification, and the
   `support.dreametech.com` walk (2,133 articles — expected to be the biggest haul yet).
2. Re-run coverage; re-generate the hand-off batches against what is actually left.
3. **153+ keys have a manual on disk and no guide written.** That is transcription, not
   hunting, and it is now the larger half of the remaining work.
