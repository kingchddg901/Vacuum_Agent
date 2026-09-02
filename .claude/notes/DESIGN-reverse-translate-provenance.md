# DESIGN — reverse-translation, corpus TM, and per-family language provenance

Settled with Chris 2026-09-01, while the EN-direct step-1 batches ran. **Not built.** Governs the
reverse-translate pass (the ~97 families with no English manual) and how language status is shown.

## The problem Chris named
> "It is going to be odd to need to mark English as stable once we review the translations."

English is the library's base language, so it is implicitly authoritative. But for families whose
manual is **not** English, our English is itself a **derived artifact** (machine-translated) sitting
at the ROOT of the dependency tree — so proofing it after the fact would invalidate everything
generated from it. English stops being definitionally stable; it becomes *a language with provenance*.

## Ruling 1 — NEVER pivot. Translate DIRECT from the source language.
CN → EN → DE is two hops of drift. CN → DE is one. **And direct costs the SAME**: either way you
produce 18 language outputs, so it is 18 translator agents either way — the only difference is which
source text each reads. No efficiency argument for the pivot; it is strictly worse. So:
- English becomes **just one of the 18 outputs** (the one Chris can proof), not the pivot.
- Correcting English therefore does NOT invalidate the other 17 — they were never derived from it.
  **That dissolves the "odd to mark English stable" problem.**

## Ruling 2 — LIFT before translating; when translating, source from the CLOSEST family; cross-check the corpus
Chris: *"if we have to translate we do it from the closest family we can use as its source and cross
check for phrases that are already in the corpus as sanity check."*

**Precedence ladder, per (family, language, component):**
1. **`lift`** — the family's OWN manual carries that language → the vendor's exact words. Zero loss,
   and the terminology matches what is printed in the user's own manual/app.
2. **`tm`** — the closest platform sibling (reg-code / base-name resolution, same machinery that maps
   models→manuals) published that component in that language → reuse the vendor's phrasing.
3. **`translated`** — direct from the nearest sibling's source language (CN→X, NO pivot), then
   **cross-checked against the TM**: a translation that disagrees with existing vendor wording for
   the same component is a FLAG, never a silent overwrite.
4. **`novel`** — no corpus support at all → explicitly marked unverified.

**Why the TM works here (measured 2026-09-01):**
- **698 (family,language) pairs are liftable** straight from the EN-direct families' own manuals;
  85 of those families carry ≥4 languages.
- Liftable non-English volume: `es=115 fr=114 it=80 de=80 pl=75 nl=68 ru=62 pt=58 zh=32 ko=12 ja=2`.
- The corpus is highly repetitive — the earlier consistency audit measured **73% of authored
  step-slots are byte-identical reuse** across families. So a TM built from those 698 pairs should
  cover most of what the CN-only families need: "translation" collapses mostly into MATCHING wording
  Dreame already published, not generating new prose.
- A TM concept already exists in the pipeline — `scripts/build_guides.py` docstring: *"TM stays
  immutable evidence; the structure keys by component + carries `src` pointers back to it."*

**Verification asymmetry this fixes:** a LIFTED string is provable (the provenance verifier scores it
against its source manual). A TRANSLATED string cannot be scored that way, and Chris can proof
English but not German. The ladder pushes as much content as possible into the provable tiers and
leaves the unverifiable remainder *visibly flagged* rather than blended in.

## Ruling 3 — the draft marker is CARD-WIDE and CONSERVATIVE (Chris; corrects an earlier per-family idea)
> Chris: *"this is the card wide setting. if any string it can show is not natively reviewed the
> whole language gets marked draft."*

The globe picker is a **card-wide display-language** setting, so the marker must describe the WHOLE
language pack, not the family in view. **If ANY string the card can show in that language is not
natively authored or reviewed, the entire language is marked draft.**
⚠ An earlier draft of this note proposed resolving the marker PER-FAMILY (no mark when the viewed
family's English is a native lift). **That was wrong and is retracted** — it is incoherent for a
card-wide setting: a user would pick Deutsch while viewing a native-German family, see no mark, then
switch vacuums and get unreviewed machine German with no warning. Card-wide setting ⇒ card-wide claim.

Marker = a single AND across the language (per-string provenance is still tracked, to COMPUTE this
and to drive the proof workflow):

| every string in the language is… | picker shows |
|---|---|
| `lift` / `tm` (vendor's own words) or `translated`+reviewed | **stable** (no mark) |
| anything else — one unreviewed `translated` or `novel` string is enough | **(draft)** in-language |

**English** therefore gains the draft mark the moment ANY reverse-translated English string ships —
even though it is native for 164 families — and loses it when the proof pass covers the remainder.
It is simply **first to graduate**, because it is the only language with a reviewer.

### Two consequences that change priorities
1. **Lifting is what CLEARS the marker, not just a quality nicety.** A natively-lifted string is
   vendor-authored, so it needs no review. The review surface == the non-lifted remainder.
   Maximising lift/TM directly shrinks what stands between a language and "stable".
2. **For the 16 non-English languages, lift/TM is the ONLY realistic path to stable — there is no
   reviewer.** Chris can proof English; nobody here can proof Korean or Polish. So Deutsch can only
   lose its `(Entwurf)` if essentially every German string is a native lift or a TM match from
   Dreame's own German manuals. This reframes the **698 liftable pairs** from "better fidelity" to
   "the sole mechanism that can ever clear the draft marker for most of the picker".

## Ruling 4 — SOURCE HIERARCHY, and "cadence-only" components (settled 2026-09-01)
Chris asked to expand the search beyond the manuals for parts that manuals never document
(scale inhibitor, retractable/clearance legs, water refilling inlet, dirt funnel barrier,
side brush extension, MopExtend). Three levels were checked and AGREE:
1. **1,042 corpus manuals** (whitespace-normalised, `fan filter` as a positive control):
   **no procedure** for any of them — only parts-diagram labels + interval-table cadence rows.
2. **Dreame's official forum** (thread 481): the scale inhibitor is **service-centre only** — not
   even sold in Europe; you send the machine in. That is WHY no procedure exists.
3. **Dreame's official care blog**: covers only the standard parts (bin, brushes, sensors, filters,
   mop pads, dock) — the same ones the manuals already document.
⇒ **Dreame has never published a procedure for those parts.** Verified, not assumed.

**RULING — cadence-only components are legitimate; invented steps are not.**
Ship the part with the vendor's OWN stated frequency and NO steps:
`Retractable legs — clean as needed` · `Water refilling inlet — once every month` ·
`Scale inhibitor — replace every 18–36 months (service centre)`.
Fully sourced (it is literally their table), passes the provenance verifier, tells the user the part
needs attention. ⇒ **EMIT CHANGE: keep step-less components when they carry a cadence** (only drop
components with no steps AND no notes AND no cadence).

**SOURCE HIERARCHY (do not re-litigate):**
| source | use |
|---|---|
| the model's own manual | AUTHORITATIVE — author from this |
| corpus TM (sibling manuals) | authoritative vendor wording |
| the **Dreame app** | vendor-authored: consumable descriptions + **usage-hour cadences** ("replace the side brush every 200 hours") + LIVE remaining-life telemetry |
| official care pages | usable if they document a procedure the manual lacks (they mostly don't) |
| **forum** | RESEARCH ONLY — never guide content. Support there suggested **cola/lemon juice** for descaling, contradicting Dreame's own docs. |
| AI / blogs / YouTube syntheses | **NEVER.** Fails the provenance verifier (scores 0) and carries real liability ("use compressed air", "mild disinfectant", "unscrew the module"). |
⚠ The tell, from a live example: an AI answer's maintenance steps for these parts *sounded* right.
Everything in it that was TRUE was true because it is in the manual — and **56 packets had already
captured it** ("Unscrew the side brush with a screwdriver…"). Everything it added beyond the manual
was precisely the unverifiable part. Plausibility is not provenance.

### DECLINED — `silver_ion_sterilizer` (Chris, 2026-09-01). Do not re-propose.
The Dreame app shows an "Accessory Usage → Silver Ion Sterilizer" page (100% / 365 days, with a
Reset button), and the L10s Ultra / S10 manual (`r2228d`, Robin's own platform) DOES carry
"Silver Ion Sterilizer and Filter kit — 12 months" in its interval table — matching the app's 365
days. It looked like a textbook cadence-only component. **Chris declined it:**
- the app's **reset is a no-op**;
- the counter reads **100% on a used machine** — it never decrements, so "365 days remaining" is a
  printed default, NOT a measurement. The cadence has no real backing.
- 2 families out of 159 — a one-off fluff component.
⚠ **GENERALISABLE CHECK:** a consumable counter pinned at exactly 100% on a used machine is NOT
tracking. The four real ones decrement and show varied values (96/95/97/77%). **Verify a counter
actually moves before trusting it as live data.**

## OPPORTUNITY — live consumable telemetry (verified on Robin 2026-09-01)
The Dreame app's consumable page (96% / 193 hours for the side brush) is **already flowing through
the integration**, matching the app EXACTLY: `side_brush_left`=96 / `side_brush_time_left`=193,
`main_brush_left`=97/293, `filter_left`=95/143, `sensor_dirty_left`=77/23.
So **4 of the 24 component keys have live per-device remaining-life**, in the app's usage-hours basis.
A guide could show "96% remaining, 193 hours" instead of only the manual's calendar "every 3–6 months".
⚠ Note `COMPONENT_FREQUENCIES` currently models CALENDAR intervals only — usage-hours is a second
basis. NOT BUILT; recorded as a design opportunity.

## Sequencing
1. Author each family from its manual, **per language**, lifting natively wherever available.
2. For CN-only families: translate **direct** from Chinese to each target, TM-cross-checked.
3. English for those families is `translated` → **Chris's proof pass** → `reviewed`/stable. It is
   simply FIRST to graduate (it is the language he can proof), which then makes
   "Auto (follow Home Assistant)" safe for English; the other 16 graduate as they are verified.
4. ⚠ Do NOT generate 17 packs off unreviewed machine-English and then correct the root — that is the
   rework trap this whole design exists to avoid.

## Scope reality (measured)
- Reverse-translate set: **97 families / 190 models**, of which **88 are CHINESE-ONLY** (single `zh`
  slice) — lifting cannot help there, translation is genuinely required. Only 3 are multi-language.
  Languages present across that set: `zh=90 ko=3 ja=2 ru=2 nl=2 de=2`.
- EN-direct set: **164 families**, language counts per family ranging 1→11
  (`{1:19, 2:24, 3:36, 4:5, 5:5, 6:1, 7:10, 8:30, 9:21, 10:6, 11:7}`).

## Ruling 5 — ANCHOR the translation, don't just check it afterwards (Chris, 2026-09-01)
> Chris: *"the same idea can be used to anchor the translations in the first place."*

The corpus TM is a GENERATION-TIME CONSTRAINT, not only a validation pass. When translating a
CN-only family's component, first resolve the nearest **vendor-authored English** for that same
component (sibling family via reg-code / base-name), and hand it to the translator as an anchor:
*"this is how Dreame words this component in English — translate the Chinese faithfully, matching
their terminology and phrasing conventions."*
- Consistency happens BY CONSTRUCTION rather than by correction.
- Review becomes CONFIRMATION, not repair.
- Divergences become MEANINGFUL: without an anchor half of what a reviewer flags is synonym drift
  ("universal wheel" vs "omnidirectional wheel"). With one, a divergence means a real hardware
  difference on that model, or a genuine translation problem — both worth a human's time.

⚠ **RISK — anchor contamination.** Given a reference, a model will sometimes COPY THE ANCHOR
instead of translating the source, producing output that looks perfect and is silently wrong: it
describes the SIBLING's procedure, not this model's. Same failure shape as a probe that lies toward
its expected finding. Two cheap guards:
1. **Flag output byte-identical to its anchor** when the Chinese source materially diverges
   (different step count / very different length). Identical output from different sources is the
   signature.
2. **Keep the SOURCE visible in the review artifact.** Even untranslated, structure is
   language-agnostic: "the Chinese has 5 numbered steps, this English has 3" is readable without
   knowing a word of Chinese (the same trick the shape-sectioner used).

⇒ Provenance gains a distinction worth carrying: `translated (anchored, matches TM)` is a
higher-confidence tier than `translated (free)` — the anchored ones can be SKIMMED, the free ones
must be READ.

## REVIEW ARTIFACT (design agreed 2026-09-01; BUILD AFTER the CN step-1 pass)
Chris: *"blocks of modals for components, a tabbable artifact, maybe 2 set per page."* Purpose: let
Chris proof the CN→EN output. ⚠ He does NOT read Chinese, so "is this translation correct?" is not
answerable by eye — the artifact must supply a REFERENCE to compare against.
- **Tabs = component** (`main_brush`, `filter`, …) — review one component type across many models;
  repetition is what makes an anomaly pop.
- **Each block = one family's component modal**, styled like the card's real modal, so he reviews
  what the user will actually see.
- **Two-up per row: translated (CN→EN) | nearest vendor-authored English reference**, differing
  spans highlighted. Families with NO reference are flagged *unreferenced* — those need a real read.
- **Persist a per-string verdict (approve / flag / edit).** Not decoration: it is what feeds the
  `reviewed` tier, which is what lets English graduate from `(draft)` to stable in the globe picker.
- OPEN QUESTION for Chris: two panes = *translated vs reference* (better for catching bad
  translations) OR *two families side-by-side* with the reference inline (better for spotting
  inconsistency between sibling models)?

## ⚠ FINDING (2026-09-02, non-English batch 1) — A MODEL CANNOT BE TRUSTED TO REFUSE GARBAGE INPUT
Three CN slices contained BYTE-IDENTICAL glyph-index noise (a broken ToUnicode CMap on a subsetted
font: CJK-SHAPED codepoints forming no words, ~32% in CJK Unified, ~6% PUA, stray Armenian). Given
that same undecodable text:
- `W20 Pro`'s agent correctly returned **0 components**;
- `免洗10`'s agent returned **10 components of plausible, detailed English maintenance steps** — all
  FABRICATED, since nothing readable was there. Quarantined.

**Two lessons, both load-bearing:**
1. **GATE THE INPUT DETERMINISTICALLY, UPSTREAM.** Agent behaviour on undecodable input is
   INCONSISTENT — identical bytes, opposite outcomes. Never rely on the prompt ("if unreadable, omit")
   to hold. `authoring/scrambled_nonen.json` + the detector in the slice builder now gate it.
2. **A BYTE-IDENTITY CONTAMINATION CHECK IS NOT ENOUGH.** The anchor check found 0/384 components
   byte-identical to the anchor and was CLEAN — yet this fabrication sailed through, because it was
   plausible PARAPHRASE from domain knowledge, not copying. Identity catches copying; it does not
   catch invention. The real guard is the input gate plus the structural check (`source_steps` vs
   emitted steps).

**Scramble detector (what the slice builder now runs):** for a declared script, the fraction of
non-space/non-digit chars actually IN that script's Unicode ranges; scrambled text scores ~32% for
`zh` where clean Chinese scores far higher, and carries ~5-6% PUA. ⚠ Distinguish from a LANGUAGE
MISLABEL: `X10+` scored latin=2% and looked scrambled, but is perfectly readable **Bulgarian** —
wrong label, good text. Mislabels are fixed by relabelling; scrambles need re-OCR.
⚠ ROOT CAUSE OF THE REGRESSION: my slice builder read the PDF text layer DIRECTLY, bypassing
`pre_process.window`'s existing PUA/unclassifiable detection and outcome-driven OCR fallback. The
machinery existed; the new path skipped it.

**Language self-report earned its place:** asking each agent for `source_lang_confirmed` caught
`X10+` nl→**bg**, `X10` ru→**bg**, `D9 Max` ru→**uk**, and both scrambles — none of which the
windower's own labelling knew about.

## 📌 THE NATIVE SOURCE TEXT IS SAVED — LIFT IT, DO NOT TRANSLATE IT (Chris, 2026-09-02)
> Chris: *"as long as we remember, we have the language and don't try to translate it."*

**WHERE IT IS** (durable, outside the repo):
- `durable/dreame-port-fixture/authoring/slices_nonen/` — **104 files, 2.1 MB**, the NATIVE-language
  maintenance sections: `zh=87, ru=3, ko=3, ja=2, de=2, nl=1, fr=1, it=1`.
- `durable/dreame-port-fixture/authoring/slices/` — **161 files, 3.3 MB**, the English-manual set
  (many of those manuals are multi-language, so de/fr/es/it are liftable from them too — the 698
  (family,language) pairs measured earlier).

**WHAT THE PACKETS DO AND DO NOT CONTAIN:** `packets_nonen/*.json` carry ENGLISH components only
(`provenance:"translated"`, `source_lang:"zh"`). The native text is NOT in the packet — it lives in
the slice file. So the native-language pack is a PASS NOT YET RUN, not something already captured.

⚠ **THE TRAP TO AVOID WHEN THE LANGUAGE PACKS ARE BUILT:** for the 87 Chinese families, generating
`zh` from our English would be **CN → machine-EN → back-translated CN**, throwing away Dreame's OWN
Chinese wording that is sitting in the slice. Same for ru/ko/ja/de/nl/fr/it on their families.
⇒ **Run a NATIVE extraction over the SAME slices** (same 25 keys, same structure, steps verbatim in
the source language) and LIFT that as the language pack. English stays the translated artifact.

**WHY IT ALSO DECIDES THE DRAFT MARKER:** a lifted `zh` pack is vendor-authored, so it needs no
reviewer and can be STABLE. A back-translated `zh` pack is unreviewable (nobody here proofs Chinese)
and would therefore be PERMANENTLY `(draft)` under the card-wide rule. Lifting is the only mechanism
that can ever clear the marker for the non-English languages.
