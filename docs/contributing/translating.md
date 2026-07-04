# Translating the card

So you want the card to speak another language — to keep for yourself, or to
contribute back. A translation is **data, not code**: a JSON file of
`key → string`. You can drop one in, restart, and pick it from the header globe —
no rebuild. This page is about making one *good*; the machinery underneath is in
the [i18n system reference](../dev/33-i18n-system.md).

## Where strings come from

English (`src/i18n/en.js`) is the source of truth and the complete key list —
~2,090 keys. A locale is a **subset**: anything you leave out (or get wrong)
falls back to English, so a partial translation is perfectly valid and ships
fine. Start from the generated English reference — it carries a context comment
on every ambiguous key, so you can translate without reading the source:

**→ [Open `en.reference.jsonc`](https://github.com/kingchddg901/Vacuum_Agent/blob/master/custom_components/eufy_vacuum/frontend/locales/en.reference.jsonc)** — click **Raw** (or **⋯ → Download**) to grab it, translate the values, and save as `<code>.json`.

(Repo path: `custom_components/eufy_vacuum/frontend/locales/en.reference.jsonc`. The
shipped locales — [`de`](https://github.com/kingchddg901/Vacuum_Agent/blob/master/custom_components/eufy_vacuum/frontend/locales/de.json) / `fr` / `es` / `nl` / `it` / `pt` / `ru.json` in that same folder — are good models for structure.)

## Authoring format

Files are **authored nested** — grouped by section, with a `commons` block for
words shared across sections — and flattened against the English manifest at load
time. A flat `{ "rooms.empty": "…" }` file is the degenerate case and also works.

```jsonc
{
  "commons": { "save": "Speichern", "cancel": "Abbrechen" },
  "rooms": {
    "empty": "Keine Räume",
    "n_selected": { "one": "{count} ausgewählt", "other": "{count} ausgewählt" }
  }
}
```

- **Keep `{placeholders}` exactly** — same braces, same name. A dropped `{count}`
  is rejected for that key (it would render wrong); an extra one is a harmless
  warning.
- **Plurals are objects** of your language's CLDR cardinal categories — exactly
  what `Intl.PluralRules('<your-code>')` produces (Russian needs
  `one/few/many/other`; most languages `one/other`). Every form keeps the
  placeholders.
- **Don't translate** product names ("Home Assistant"), memorial pet names
  (Mittens / your own pets — proper names), or the model-family codes. Generic
  animal-companion names (Cat/Dog/…) and the "Rainbow Bridge" idiom *do* translate
  to their established renderings.

## Dropping one in

1. Put `<code>.json` (e.g. `de.json`, `pt-BR.json` — the filename stem is the
   locale code) in `config/eufy_vacuum/locales/` on your HA instance.
2. Restart Home Assistant (the integration regenerates the served index at
   startup), then hard-refresh the dashboard (Ctrl+Shift+R).
3. Pick it from the header **globe**. A drop-in is treated as *custom* and is
   reachable only by that explicit choice (it never auto-activates from the system
   language until it's native-reviewed).

## What the intake gate allows

A dropped locale is **untrusted** — some of its values are rendered as markup — so
it passes through a [sanitize-or-quarantine gate](../dev/33-i18n-system.md#the-intake-gate)
before it loads. Knowing the rules keeps your file from being rejected:

- **Allowed markup:** `<strong>`, `<em>`, `<code>`, and `<a href="…">` pointing at
  `github.com` or `kingchddg901.github.io`. That covers every place the card
  renders authored markup.
- **Inert junk is scrubbed, not fatal.** A `<span>`, a `<div>`, an off-site link —
  the file still loads, but those render as *visible literal text* (e.g. you'll
  see `<span>` in the UI). That's your cue to fix it; it isn't a security problem.
- **Active content quarantines the whole file.** A `<script>`/`<iframe>`, an
  `onclick=`/`onerror=`, a `javascript:` link — any of these is treated as
  tampering and the **entire file is rejected** (the other ~1,900 keys share its
  source, so none are trusted). Translations never need any of this.

If a file is quarantined it's remembered by its content hash and skipped silently
until you change it — fix the offending value, restart, and it re-evaluates fresh.

## Getting it reviewed / contributed

A new AI-assisted or unreviewed translation ships as a **draft** — usable by
explicit pick, but it won't auto-activate. Once a native speaker has reviewed it,
promote it to `stable` (a one-line `LOCALE_STATUS` change) so it can follow the HA
system language automatically. `draft` and `stable` are the two review states a
shipped locale moves between; the
[review-status taxonomy](../dev/33-i18n-system.md#review-status-and-auto-activation)
defines exactly what each status controls (and how it differs from the intake
gate's safety outcomes).

The per-language **[native-review worklist](translation-review.md)** lists the
specific judgment-calls flagged for each shipped locale
(`de`/`fr`/`es`/`nl`/`it`/`pt`/`ru`) — a native speaker's to-do list. Confirm or
correct an item there or in the
[translate discussion](https://github.com/kingchddg901/Vacuum_Agent/discussions/25).

To contribute a language upstream, open a PR adding `<code>.json` to the served
locales folder and its status to the locale tables in `src/i18n/index.js`. The
[i18n reference](../dev/33-i18n-system.md) covers the manifest, plural mechanism,
and the `check:i18n` gate your file is validated against.
