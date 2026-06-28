# Card translations

These JSON files are the card's UI translations — **data, not code**. Each
`<code>.json` (e.g. `fr.json`, `pt-BR.json`) maps translation keys to strings;
anything a locale leaves out falls back to English, so a partial translation is
perfectly valid.

## Want to add or fix a language?

Start from **[`en.reference.jsonc`](en.reference.jsonc)** in this folder — the
generated English reference with the full key list and a context note on every
ambiguous string. Translate the values, save as `<code>.json`, and drop it into
`config/eufy_vacuum/locales/` on your Home Assistant instance (no rebuild —
restart, then pick it from the header **globe**).

📖 Full guide: **[Translating the card](https://kingchddg901.github.io/Vacuum_Agent/docs/contributing/translating/)**.

> `en.reference.jsonc` is generated (`npm run build:locale-reference`) as a
> copy-from template only — it is **never loaded** at runtime, so editing it does
> nothing; translate a `<code>.json` instead.
