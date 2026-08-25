# Per-language card captures

Real HA captures, one **room card** and one **profile card** per shipped language,
for the collapsed language wall in the top-level README.

Naming — exact, lowercase, the locale code as it appears in
`custom_components/eufy_vacuum/frontend/locales/`:

    room-<code>.png
    profile-<code>.png

e.g. `room-ar.png`, `profile-zh-Hant.png`. English is `en`.

## The eighteen

en · ar · cs · de · es · fr · he · id · it · ja · ko · nl · pl · pt · ru · tr · zh-Hans · zh-Hant

## Shoot these FIRST if the batch gets interrupted

    ar  he  ja  ko  zh-Hans  zh-Hant

Not arbitrary. Two reasons:

1. **They are the only ones carrying claims the README currently cannot evidence.**
   The text promises "including right-to-left Arabic & Hebrew" and lists Japanese,
   Korean and Chinese — and every existing hero shot is Latin or Cyrillic. A reader
   asking "does RTL actually mirror?" gets no answer from the images that exist to
   answer it.
2. **The harness cannot produce them.** Measured 2026-08-25: the pinned render image
   (`mcr.microsoft.com/playwright:v1.60.0-noble`) has 50 fonts and **zero** covering
   ja/zh/ko/ar/he, so those six render as tofu boxes. Installing `fonts-noto-cjk` +
   `fonts-noto-core` fixes it (351 fonts, full coverage) — but that must never be
   done to the GATE container, only to a shooting one, or every visual baseline moves.
   A real HA box has system fonts already, which is why these are cheap for a human
   and expensive for the harness.

The remaining eight (en/de/es/fr/it/nl/pt/ru) already appear in the two hero grids,
so they are the ones to shoot last.
