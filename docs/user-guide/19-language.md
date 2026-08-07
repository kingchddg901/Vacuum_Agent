# 19 — Language

The card can speak your language. It ships in **18 languages**: English plus
Arabic, Chinese (Simplified and Traditional), Czech, Dutch, French, German,
Hebrew, Indonesian, Italian, Japanese, Korean, Polish, Portuguese, Russian,
Spanish, and Turkish — and you can switch any time. Right-to-left languages
(Arabic, Hebrew) flip the whole card's layout to match.

## Pick your language

Click the **globe** in the card header and choose a language. The change is
instant.

Your choice is **yours** — it applies only to your view, not to other people who
use the same dashboard, and it follows you across your devices (it's saved to
your Home Assistant account, not the browser).

Pick **Auto** to follow your Home Assistant language automatically — but note that
**Auto only switches to languages that have been native-reviewed.** Every language
other than English is currently a *draft* (see below), so **Auto shows English for
now**. To use your language today, pick it directly from the globe. (In the
sidebar panel's menu, when Auto is being gated this way the **Auto** row says
so and points you at your language's row below; the compact globe on the
dashboard cards doesn't show this note.)

!!! info "Drafts"
    Languages other than English are currently AI-assisted and marked as a draft
    in that language's own word — "Deutsch (Entwurf)", "Русский (черновик)" —
    until a native speaker has reviewed them. A draft never switches on by itself —
    so **Auto stays on English** and you choose the language manually from the
    globe. Once a language is reviewed and promoted, **Auto** will follow your Home
    Assistant language to it automatically. The wording will keep improving.

## The typeface lives here too

The sidebar panel's globe menu carries a **Typeface** section when a
dyslexia-friendly font is available for your language — see
[Accessibility](14-accessibility.md#dyslexia-friendly-typeface). It's in this
menu rather than its own because it's the same kind of setting: a per-user
display preference that follows your login. (The compact globe on the
dashboard cards doesn't include this section.)

If you don't see it, the font hasn't been verified for your language yet.

## Don't see your language?

Anyone can add one — a translation is just a JSON file, no coding and no rebuild.
Drop a `<code>.json` file into `config/eufy_vacuum/locales/` on your Home
Assistant instance, restart, then hard-refresh the dashboard (Ctrl+Shift+R) and
pick it from the globe. A drop-in shows as *(custom)* in the menu and — like a
draft — never switches on by itself; you choose it explicitly. **A brand-new
language code added this way applies for that browser session only** — it
isn't saved to your account, so it's back to your previous language after a
reload. (A drop-in that reuses one of the card's existing bundled codes, e.g.
your own `de.json`, persists normally like any other pick.) For how to make
one (and how to contribute it back), see
[Translating the card](../contributing/translating.md).
