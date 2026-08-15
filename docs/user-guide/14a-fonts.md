# 14a — Fonts

The card can be read in a different typeface, and the reason it can is
accessibility: **OpenDyslexic** ships with it, ready to switch on. OpenDyslexic
weights the bottom of every letter so characters are harder to flip or confuse —
if letters swap places on you, or you've been told to try a dyslexia-friendly
font, this is the one setting worth trying. There is nothing to download and
nothing to buy.

You can also drop in any other typeface you have the right to use, without
waiting for a release — see [Add your own typeface](#add-your-own-typeface).

## Turn it on

1. Open the **globe** in the card header — the same menu you pick a language in.
2. Find the **Typeface** section, below the list of languages.
3. Click **OpenDyslexic**.

The card changes immediately. Every option is drawn *in the typeface it offers*,
so you can see what you're choosing before you choose it, and the menu
deliberately stays open — one more click puts it back if it isn't for you.

**Default** is the card's starting state: use whatever your theme and Home
Assistant use.

!!! note "Your choice, on every device"
    The typeface is saved to your Home Assistant account rather than to the
    browser, so it follows your login to every device you open the card on. It
    changes nothing for anyone else using the same dashboard.

The **Typeface** section lives in the full card's globe menu — the one in the
sidebar panel. The compact globe on the dashboard and room cards is
language-only (see [Language](19-language.md)).

## Which languages OpenDyslexic is offered in

Twelve, at the moment: **English**, Czech, Dutch, French, German, Indonesian,
Italian, Polish, Portuguese, Russian, Spanish, and Turkish.

A typeface is offered for a language only once the font file has been checked to
contain every letter that language's screens actually use — the check reads the
font file itself, so a font can't simply claim coverage it doesn't have.
OpenDyslexic carries no Hebrew, Arabic, Chinese, Japanese or Korean letters, so
it isn't offered there: half a screen in the typeface and half in something else
is worse to read than not switching at all.

If the **Typeface** section isn't in your globe menu, nothing has been verified
for the language you're currently viewing in. Switching the card's language, or
adding a font that covers your language, brings the section back.

!!! note "Letters the font doesn't carry"
    The check covers the card's own wording. Your own words can contain letters
    the typeface doesn't have — a room you named in Cyrillic, for example — and
    those fall back to your usual font rather than rendering as empty boxes.
    That's deliberate.

OpenDyslexic is included in regular and bold. The card sets no italic body text,
so no italic file is shipped.

## Add your own typeface

Any typeface you have the right to use can be added by dropping files into your
Home Assistant configuration. No update, no rebuild, and it survives HACS
updates, because it lives in your config folder rather than inside the
integration.

### 1. Make a folder for the font

One folder per font, inside `config/eufy_vacuum/fonts/` — that folder is created
for you the first time the integration starts. Each font folder holds a
`font.json` describing the typeface, the font's `.woff2` files, and its licence:

```
config/eufy_vacuum/fonts/
    atkinson/
        font.json
        AtkinsonHyperlegible-Regular.woff2
        AtkinsonHyperlegible-Bold.woff2
        OFL.txt
```

### 2. Write font.json

```json
{
  "id": "atkinson",
  "family": "Atkinson Hyperlegible",
  "faces": [
    { "file": "AtkinsonHyperlegible-Regular.woff2", "weight": 400 },
    { "file": "AtkinsonHyperlegible-Bold.woff2", "weight": 700 }
  ]
}
```

| Field | Required | What it is |
|---|---|---|
| `id` | yes | A short name for this font, unique among your fonts. Lowercase letters, digits, hyphens and underscores, up to 32 characters, starting with a letter or digit. `opendyslexic` is taken. |
| `family` | yes | The font's real family name, as the font file declares it. Up to 64 characters; no quotes, backslashes, braces or semicolons. |
| `label` | no | The name shown in the menus. Defaults to `family`. Typeface names are shown as-is in every language, never translated. |
| `faces` | yes | Up to four `.woff2` files and the weight each one is. A weight that isn't a whole number between 100 and 900 is read as 400. |
| `fallback` | no | Up to four families to fall back to for letters this font doesn't carry. The list always ends in a generic family — `sans-serif` is added if you don't supply one. |

!!! note "You don't declare which languages it supports"
    There is deliberately no languages field. Home Assistant opens the files you
    listed, reads the letters actually in them, and offers the font only for
    languages it can cover completely — so the answer comes from the font rather
    than from a claim about it. Two consequences worth knowing: **every** file
    you list has to carry a letter for it to count (a bold file missing an
    accented character narrows the whole font), and Arabic additionally needs
    the font's letter-joining table, so a font with the letters but no joining
    isn't offered for it. Only letters and digits are counted — punctuation,
    arrows and symbols always fall back and are never held against a font.

### 3. Restart and refresh

Restart Home Assistant, then refresh the dashboard. The font library is built
while Home Assistant starts, so a **restart is required** — reloading the
integration isn't enough.

The new typeface then appears in the globe menu's **Typeface** section (for the
languages it covers) and as a chip on the Theme tab's **Font Family** token.

### Rules and limits

- **`.woff2` files only.** Other font formats aren't read.
- The folder name may be up to 64 letters, digits, hyphens or underscores.
  Symbolic links are ignored — put the real files in the folder.
- Up to four files per font; the card loads up to 32 fonts.
- If two folders use the same `id`, the first one alphabetically wins and the
  other is skipped.
- Keep the font's licence file in its folder, and check that the licence permits
  you to use it this way.

### When something's wrong

| If | Then |
|---|---|
| the folder has no `font.json` | the folder is ignored |
| `font.json` can't be read, or a required field is missing or invalid | the font is skipped, and the log names the folder |
| a file listed in `faces` isn't there | the whole font is skipped, and the log names the missing file |
| a `.woff2` file is damaged and can't be read | the font is listed but offered for no language |
| the font-reading libraries aren't available | the same — listed, offered for no language, and the log says why |

Home Assistant's log (**Settings → System → Logs**) names the folder and the
reason in each case. Nothing here can break the card: a bad drop-in is skipped,
and the built-in typeface, your themes and your current choice are untouched.

## Fonts and themes

Two controls set the card's font, and they don't fight:

- **Typeface**, in the globe menu, is *yours* — your account, your devices.
- **Font Family**, in the **Theme** tab under **Tokens → Shared Foundations**,
  belongs to the theme, so it's shared with everyone viewing this vacuum's card.

The Font Family token offers one-click chips — **System UI**, **Home
Assistant**, **Georgia**, **Consolas**, **OpenDyslexic**, and every typeface
you've dropped in — above a free-text box for anything else. Each chip is drawn
in the font it sets. The Palette and Tokens editors work at every width, a
phone included; see [Theme system](17-theme-system.md).

When you've picked a **Typeface**, it wins over the theme's **Font Family** for
you: an accessibility choice outranks a decorative one, and someone else's theme
can't take your typeface away. Set the Typeface back to **Default** and the
theme's font takes over again.

One asymmetry to expect: a font you drop in appears as a **Font Family** chip
whether or not it passed the language check, but the **Typeface** menu only
offers it once it has.

## Removing a font

Delete its folder from `config/eufy_vacuum/fonts/` and restart Home Assistant.
If it was the typeface you had selected, the card falls back to **Default** on
its own.
