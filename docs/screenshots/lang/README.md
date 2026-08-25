# Per-language card captures

Real Home Assistant captures backing the language section of the top-level README:
the **room card** and a **saved routine card**, across all eighteen shipped languages.

## What is here

Six files, in `docs/screenshots/`, each a six-language grid:

    rooms_1-6.png     profile_1-6.png     en · id · cs · de · es · fr
    rooms_7-12.png    profile_7-12.png    it · nl · pl · pt · tr · ru
    rooms_13-18.png   profile_13-18.png   he · ar · ko · ja · zh-Hans · zh-Hant

`*_1-6` are the README's visible pair; the other four sit inside the `<details>`
block so the page does not open as a wall of screenshots.

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
