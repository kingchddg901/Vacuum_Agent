# Per-language card captures

Real Home Assistant captures backing the language section of the top-level README:
the **room card** and a **saved routine card**, across all eighteen shipped languages.

## What is here

Each file is a grid of consecutive languages in **globe-menu order**, which is a
single 1-18 index shared by all three card types.

    rooms_1-6.png     profile_1-6.png       1-6    en · id · cs · de · es · fr
    rooms_7-12.png    profile_7-12.png      7-12   it · nl · pl · pt · tr · ru
    rooms_13-18.png   profile_13-18.png     13-18  he · ar · ko · ja · zh-Hans · zh-Hant

    DashBoardCard_1-3.png     1-3    en · id · cs
    DashBoardCard_4-6.png     4-6    de · es · fr
    DashBoardCard_7-9.png     7-9    it · nl · pl
    DashBoardCard_10-12.png   10-12  pt · tr · ru
    DashBoardCard_13-15.png   13-15  he · ar · ko
    DashBoardCard_16-18.png   16-18  ja · zh-Hans · zh-Hant

The dashboard card runs three per file rather than six because it carries the map.

`rooms_1-6` and `profile_1-6` are the README's visible pair; everything else sits
inside the `<details>` block so the page does not open as a wall of screenshots.

## Do not read the order off the source

`listLocales()` (`src/i18n/index.js`) puts **en first, then sorts by ENDONYM** with
`localeCompare` — not by code, and not in the order `LOCALE_ENDONYMS` declares. The
literal lists `ja` before `ko`, but 한국어 collates ahead of 日本語, so the menu is
`ko` at 15 and `ja` at 16. **Simplified Chinese (`zh-Hans`) is 17 and Traditional
(`zh-Hant`) is 18.**

To check rather than assume:

    node --input-type=module -e "const m=await import('./src/i18n/index.js');       m.listLocales().forEach((l,i)=>console.log(i+1, l.code, l.endonym))"

A new locale changes every index after its endonym's sort position, so adding one
renames the sets rather than appending to them.

## Why the 13-18 pair is the important one

It is the only evidence for the boldest claim in that section. The prose promises
"including right-to-left Arabic & Hebrew" and lists Japanese, Korean and Chinese —
and every shot that preceded these was Latin or Cyrillic, so a reader asking whether
RTL actually mirrors got no answer from the images that existed to answer it. These
show it: in Hebrew and Arabic the controls are right-aligned, the step numbers move
to the right, and Start/Run moves to the left.

## Why these are shot by hand and not by the harness

Measured 2026-08-25: the pinned render image
(`mcr.microsoft.com/playwright:v1.60.0-noble`) carries 50 fonts and **zero** covering
`ja`/`zh`/`ko`/`ar`/`he`, so the harness renders those six as tofu boxes. Adding
`fonts-noto-cjk` + `fonts-noto-core` fixes it (351 fonts, full coverage) — but that
must only ever be done to a SHOOTING container, never the gate one, or every visual
baseline moves. A real HA box already has the fonts, which is what makes these cheap
by hand and expensive to automate.

## Re-shooting

These are real captures, so they carry real UI text and can go stale. That is not
hypothetical: the pair they replaced was committed 2026-07-09 showing **"RUNS AS"**,
`run_profiles.runs_as` became **"Runs in this order"** on 2026-07-12, and the README
carried the outdated wording for six weeks — through the v2.1.0 release. If a visible
string in either card changes, re-shoot the affected set.

Nothing gates this. There is no check that these images match the shipped strings.
