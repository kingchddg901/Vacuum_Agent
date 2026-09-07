# Never detect the language. Keep every locale a live candidate.

**Status:** RULE + a working derivation, 2026-09-07. Chris's, after watching four separate
language failures in one session.

> **"unknown-language document → all supported locales remain live candidates until the document
> itself narrows them."**

## The four failures this replaces

Every one came from DETECTING a language first and then choosing patterns for it:

1. `walk_manuals` admitted **Latin + CJK only**. A Japanese, Ukrainian or image-only manual
   scored zero on every hardware term — indistinguishable from a genuinely dockless machine,
   which is the exact finding the walk existed to make. 5 families wrong.
2. **Hangul was added only after Chris supplied two Korean manuals** by hand. The corpus had 45
   Hangul documents the whole time.
3. `s70_pro_roller`'s SKU-scale manual was rejected outright as **Cyrillic-script**, so the family
   was reported as "only junk/line manuals" when a perfectly good 45-page manual was sitting there.
4. When I did write patterns, I **guessed**. Russian ones, for a document that is **Ukrainian**
   (`резервуар для використаної води`, `кришку`, `пилу`) — so `dirty_tank` scored 0 on a manual
   that plainly documents one.

Corpus scripts: Latin 2236, CJK 262, Cyrillic 146, Kana 95, Hangul 45, Arabic 41, Hebrew 37.
Everything outside the two I had patterns for was being called unreadable.

## The rule

**Score against every locale at once. Whichever terms hit tell you what the document is.** A
multilingual EU manual hits many locales, which is correct rather than confusing. There is no
detection step to get wrong, and no script gate to forget to widen.

## Where the words come from — our own packs, not a guess

`upkeep_guides_i18n/` ships every guide step in **17 languages** beside English, aligned
positionally per family+component. So each locale's term is DERIVED:
`tools/derive_signals_from_i18n.py`.

```
dirty_tank  17 locales   汚水タンク · 오수 탱크 · réservoir d'eau sale · tangki air kotor
                         Kirli su tankını · nádržku na použito · מיכל המים המש · مستعمل
station     15           ベースステーション · 베이스 스테이션 · Basisstation · المحطة الأساسية
mop_pad     17    dust_bag 16    dust_box 13
```

### ⚠ It must be DISCRIMINATIVE, not longest-common-substring

LCS across the positive steps returns whatever grammar they share. For Japanese `base station`
it produced **「ます。」** — a sentence ending. A real term appears in steps that MENTION the part
and **not** in steps that do not, so every candidate is scored against a NEGATIVE control set and
anything common to both is rejected. Same ablation discipline as everything else here: **a signal
that fires on the control is not a signal.**

## Two honest limits

**Ukrainian is not among the 18.** Tested on the s70_pro_roller manual, the union scores
`station=67` (narrowing it to the English/Indonesian term, so the document carries English too)
and `dirty_tank=0` — correct, because we have no Ukrainian vocabulary. The method reports the gap
rather than hiding it as "no dirty tank".

**Derived terms can be over-specific.** The Korean control scores `station=0`: the derived term is
`베이스 스테이션` while the manual writes `스테이션` alone. A full phrase where the document uses
the head noun. Worth adding a head-noun variant, weighed against the false positives a shorter
alternative admits.

**`clean_tank` derives in 0 locales** — the packs translate the WIRED library, where
`clean_water_tank` appears in exactly 1 family, below the support floor. It needs a different
source, not a different method.

## The general form

This is the language case of a wider rule that cost five separate measurements today:

> Do not narrow the candidate set on a property you inferred. Let the artefact narrow it.

Same shape as the share-resolution failures (`keys_of()[0]` reads a share-shaped record as empty)
and the fitness rules (a 10-page index read, a 782-page line manual, a warranty card). In every
case a shallow inference about the input silently shrank the population being measured.
