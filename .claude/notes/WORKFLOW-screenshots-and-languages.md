# Screenshots that cannot silently rot

How the committed screenshots get taken, and what stops them going stale. Three pieces:
a **pinned language wall** (shooting is free), a **freshness gate** (staleness is
detectable), and the **loop** that joins them.

---

## The failure this exists to prevent

`docs/screenshots/translations-hero-profile-card.png` rendered **"RUNS AS"**.
`run_profiles.runs_as` became **"Runs in this order"** in `ff72f49e`.

The image was committed 2026-07-09. The string changed 2026-07-12. It was correct when
taken and wrong three days later, and the README carried the outdated wording for **six
weeks** — through the v2.1.0 release, to every HACS default-store user.

Nothing in this repo could have caught it. Every gate here checks *code*, and a
screenshot is not code. It surfaced on 2026-08-25 only because a fresh capture happened
to land beside the stale one in the same README section.

**The generalisation, which is the thing worth keeping:** an image is a claim about the
product that no test reads. Any process that relies on someone *remembering* to re-shoot
will fail the same way, because the person who changes a string is never thinking about
a PNG in `docs/`.

---

## 1. The pinned language wall — makes shooting free

`http://192.168.4.104:8123/hero-shots` — three views (room card / routine card /
dashboard card), **18 cards each, one per language, positions fixed**.

Built 2026-08-25. Config is generated; the generator output lives in the session
scratchpad, and the live config is readable over the websocket API (below).

### Why pinning, and not the globe

A card resolves its language through `resolveLang(hass, config, override)`
(`src/i18n/index.js:344`), in this precedence:

| | source | scope |
|---|---|---|
| 0 | the in-card **globe** | **per-user, one shared key**, cross-device |
| 1 | `config.i18n.locale` — a **per-card pin** | that card only |
| 2 | HA's system language | — |

The old workflow used the globe: set six cards one at a time, **don't refresh**, shoot,
repeat. That works only because a card re-reads the shared key when it *re-renders* — so
card 1 keeps German while you set card 2 to Spanish, and a reload collapses every card
to whichever you picked last. It is a render-timing artifact, and it cost roughly 30
minutes per full pass in naming care, non-overlap bookkeeping and refresh avoidance.

The pin is precedence 1: per-card, refresh-proof, and it cannot collapse. `setConfig`
stores the config object verbatim with no schema stripping, and the visual editor emits
`{...this._config, …}` on every change, so a pin survives both YAML edits and someone
poking the UI editor.

### ⚠ The one thing that breaks the wall

**The globe must be on Auto.** It is precedence 0 and it outranks all 54 pins at once.
It is stored server-side per user in frontend user-data under `eufy_vacuum_card`
(`{"ui_language": "auto"}`), so it is **cross-device** — picking a language on your
phone, or on the sidebar panel, collapses the wall on the desktop.

Recovery is **one action, not 54**: open any globe, pick Auto. The same sharing that
breaks all eighteen repairs all eighteen.

**Re-pasting the dashboard YAML does NOT fix a collapse.** The pins are in the dashboard
config; the override is in user-data. They are different stores. The pins were never the
problem and will come back identical while every card still renders the overriding
language.

### ⚠ Capture tip

**Leave section titles empty.** A titled section clipped HA's "New Section" heading into
the top edge of `DashBoardCard_16-18.png`, which then had to be trimmed (2px; measured —
the text occupied rows 0–1 at brightness 543/570 against a ~45 page background, with the
card border starting at row 14). A permanent wall means that mistake would otherwise
recur on every future shoot.

---

## 2. The freshness gate — makes staleness detectable

    node scripts/check-screenshot-freshness.mjs            # the gate
    node scripts/check-screenshot-freshness.mjs --update   # AFTER re-shooting

Runs in CI via `node-tests.yml`'s `scripts/*.test.mjs` glob
(`scripts/check-screenshot-freshness.test.mjs`).

**It is not OCR.** Each family in `scripts/screenshot-i18n-manifest.json` declares which
i18n keys it renders; the manifest stores a fingerprint of those keys' **English values**;
the check fails when one moves. It cannot tell you an image is wrong — it tells you the
strings under it changed, which is the signal a human needs.

Failure output names the key, its new value, and the exact files to re-shoot.

### Key sets are derived, not hand-listed

Static `t("…")` literals are extracted from each card's own source, so a card that starts
using a new string is covered **without anyone remembering to edit the manifest** — which
matters, because "remember to update the manifest" is the same failure mode as "remember
to re-shoot".

The one thing that cannot be extracted is the dynamic `t(\`vocab.${field}.${slug}\`)` —
the chip labels (Vacuum/Mop, Quiet/Max). Those fields *are* declared literally at the
`chipRow(…, "fan_speed", …)` call sites, so the manifest names those four as prefixes
rather than sweeping all 682 `vocab.*` keys, which would flag every image whenever an
unrelated fault-vocabulary entry moved.

250 fingerprints across 4 families.

### It is proven to bite

Two tests this session passed against the very code they were written to catch, so this
was not optional:

* Reverting `run_profiles.runs_as` to `"Runs as"` — the exact key and exact string from
  the real failure — exits **1**, naming the key and all three `profile_*.png` files.
* `[BITE]` drives the checker against a throwaway manifest holding one corrupted
  fingerprint. Gutting the comparison to `const changed = []` turns that test **red**, so
  the gate cannot be disarmed while still reporting green.

### ⚠ What it deliberately does NOT cover

* **The maintenance guide prose.** The numbered care steps and notes inside
  `Filter_*.png` are model-aware content that does not live in `en.js`. Only that card's
  **chrome** is fingerprinted; a guide-content rewrite will not flag those images.
* **Layout, theme, font, or anything visual.** Only string *values*.
* **Non-English values.** The fingerprint is over English. A translation-only change
  does not flag, though in practice the packs move together.

---

## 3. The loop

1. A string changes.
2. CI fails, naming the keys and the image files.
3. Open the wall, set the globe to Auto, screenshot the affected sets.
4. `node scripts/check-screenshot-freshness.mjs --update`, commit images + manifest.

**⚠ Order is load-bearing.** `--update` re-records whatever is currently in `en.js`.
Running it *before* re-shooting silences the gate against images that are still stale —
that is how this gets disarmed, and it will look green forever afterwards.

---

## File naming and the 1–18 index

The numbering is the **globe menu order**, shared across all three card types:

     1 en    2 id    3 cs    4 de    5 es    6 fr
     7 it    8 nl    9 pl   10 pt   11 tr   12 ru
    13 he   14 ar   15 ko   16 ja   17 zh-Hans   18 zh-Hant

Room and routine cards ship six per file (`rooms_1-6`, `_7-12`, `_13-18`); the dashboard
card ships three (it carries the map). `Filter_*.png` is one per language, by code.

**Do not read this order off the source.** `listLocales()` puts `en` first and then sorts
by **endonym** via `localeCompare` — not by code, and not in the order `LOCALE_ENDONYMS`
declares. The literal lists `ja` before `ko`, but 한국어 collates ahead of 日本語, so the
menu is `ko` at 15 and `ja` at 16. To check:

    node --input-type=module -e "const m=await import('./src/i18n/index.js'); \
      m.listLocales().forEach((l,i)=>console.log(i+1, l.code, l.endonym))"

⚠ **Adding a locale renumbers every set after its endonym's sort position**, so the
filenames stop matching their contents. Re-shoot from the affected index onward.

---

## Why these are shot by hand and not by the harness

Measured 2026-08-25: the pinned render image
(`mcr.microsoft.com/playwright:v1.60.0-noble`) carries **50 fonts and zero** covering
`ja`/`zh`/`ko`/`ar`/`he`, so it renders those six as tofu. `fonts-noto-cjk` +
`fonts-noto-core` takes it to 351 with full coverage — but **only ever in a SHOOTING
container, never the gate one**, or every visual baseline moves. A real HA box already
has the fonts.

The harness *could* do the card walls: `mountCard` spreads `entry.config`, and a
config-pinned locale drives a card there (verified — the stub hass has no lang store, so
the pin wins uncontested). It is a few lines, not hours, as first estimated.

It is still not worth building. The output would be **fixture** data — "Hard Test",
"LIVINGROOM, Bryan" — against real captures showing a real house, and
`POST-2.1.0-deferred.md` #1 records the mobile shooter rendering literal `nullObject` text
and a phantom amber banner into its own frames. The map especially has no harness
equivalent.

**The cost was never the shooting.** It was naming, non-overlap, and fighting the shared
language key — all three of which the pinned wall removes. Automating the shooting would
have solved the cheap half of the problem and left staleness untouched.

---

## Reading the live dashboard config

`lovelace/config` over the websocket API — HA's own call, **not** a `.storage` edit. A
working client is in the session scratchpad (`ha_ws.py`); it authenticates with the token
at `Documents\claude use only.txt`, then:

    {"type": "lovelace/dashboards/list"}
    {"type": "lovelace/config", "url_path": "hero-shots"}

Writing is `lovelace/config/save`. Prefer pasting into the raw editor over automating it:
the raw editor is a CodeMirror and driving it with automated typing fights auto-indent
and mangles YAML.
