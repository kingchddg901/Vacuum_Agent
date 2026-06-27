# 33 — i18n system

Home Assistant localizes an integration's config flow and entity names, but it
gives a custom Lovelace card **nothing** for its own markup — every literal in
the card's renderers is English regardless of the user's HA language. This
subsystem is the seam that closes that gap: ~1,900 UI strings, plural-correct in
any language, switchable per-user, with community translations loadable at
runtime behind a security gate.

Source lives at
[`src/i18n/`](https://github.com/kingchddg901/Vacuum_Agent/tree/master/src/i18n/)
(the card is a build artifact — edit `src/`, run `npm run build:deploy`; never
hand-edit the bundle).

Two audiences:

- **Card developers** adding or touching UI strings — read [Authoring strings](#authoring-strings).
- **Translators / contributors** adding a language — start with the how-to,
  [Contributing a translation](../contributing/translating.md); this page is the
  mechanism underneath it.

## Files

```
src/i18n/
├── en.js                 English base — the source of truth + the key manifest
├── index.js              translate() / resolveLang() / registerLocale / loadLocale
├── flatten.js            nested authoring JSON → flat catalog (+ commons/plurals)
├── sanitize-locale.js    the intake GATE (sanitize-or-quarantine untrusted drop-ins)
├── lang-store.js         per-user language choice, persisted via HA frontend user-data
└── guide-translations.js generated upkeep-guide content (see "Guide on the card")
```

The non-English locales are **not** bundled — they ship as nested JSON served
assets (`custom_components/eufy_vacuum/frontend/locales/<code>.json`) and load +
flatten at runtime. English (`en.js`) is the only bundled catalog: it is both the
universal fallback and the complete key manifest everything else is validated
against.

## translate() and resolution

A renderer calls `this.t("rooms.empty")` (defined in `renderers/shared.js`); it
resolves the user's language and delegates to `translate(lang, key, vars,
options)` in `index.js`.

Resolution order, most-explicit first (`resolveLang`):

0. **`override`** — the in-card language control's per-user choice ([the globe](#the-language-control)).
1. **`config.i18n.locale`** — a per-dashboard author pin.
2. **`hass.locale.language` / `hass.language`** — the HA system language.
3. **`"en"`**.

A missing key renders **the key itself** (`rooms.empty`), never a blank — a
visible miss in dev.

### Review status and auto-activation

Separate from the [intake-gate outcomes](#the-intake-gate) (which judge a *file's
safety*, not its review state), every locale carries a **review status**
(`LOCALE_STATUS` in `index.js`) that controls whether it may auto-activate from the
HA system language:

| status | meaning | auto-activates at step 2? |
|---|---|---|
| `stable` | native-reviewed (English is always `stable`) | **yes** |
| `draft` | AI-generated, not yet native-reviewed | no |
| `custom` | a runtime drop-in (`config/eufy_vacuum/locales/`) | no |
| `unknown` | no status on record | no |

**The rule the gate enforces** (`isDraftLocale` in `resolveLang`): step 2 (the HA
system language) activates a locale **only if its status is `stable`**. A `draft`
or `custom` locale falls through to English at step 2 and is reachable only by a
deliberate choice — the globe override or the dashboard pin (steps 0–1), which
bypass the gate. Promotion `draft → stable` after native review is a one-line
`LOCALE_STATUS` change, and it is the single switch that lets a language follow the
system language.

Consequence today: **all shipped non-English locales are `draft`**, so **`Auto`
(follow-the-system-language) resolves to English for everyone** until a locale is
promoted — by design (an unreviewed translation never activates silently), but the
[user-facing language page](../user-guide/19-language.md) makes that visible to the
user rather than leaving `Auto` looking broken.

## Trust Model B

Locales may be community-contributed, so `translate()` **HTML-escapes the catalog
string by default** — a contributed value carrying `<script>` can never reach an
`innerHTML` sink raw. The short, audited set of first-party strings that carry
*authored* markup (`<strong>`, `<code>`, …) opt out via `options.raw` (exposed as
`this.tRaw`). Interpolated `{name}` **values** are inserted raw — the caller
escapes user data at the sink, exactly as the original literal did.

This escape is one of **two independent layers**. The other is the
[intake gate](#the-intake-gate), which scrubs a contributed locale *before* it is
registered. Two layers is the correct posture for an untrusted path: even if the
gate is bypassed, the per-render escape still neutralizes a plain string — and the
gate exists because `tRaw` values are emitted raw, where the escape does not run.

## Authoring strings

- **Plain text:** add the key to `en.js`, call `this.t("ns.key")`.
- **Interpolation:** `this.t("rooms.n_selected", { count: n })` against
  `"{count} selected"`. Escape user data in the var: `{ name: this.escapeHtml(x) }`.
- **Plurals:** the value is an **object** of CLDR forms (`{ one, other }`; English
  ships those two). `translate()` reads `vars.count` and selects the form via the
  language's native `Intl.PluralRules` — no per-language logic in the card; a
  locale supplies whatever its language needs (Russian `one/few/many/other`, …).
- **Authored markup:** key the *text run*, keep the markup in the template where
  you can; only reach for `this.tRaw` for the audited markup allowlist.

### tVocab — backend vocabulary values

The integration hands the card stable **vocabulary** values (a fan-speed `"max"`,
a clean-mode `"vacuum_mop"`, a run `"status"`, a theme token key, a maintenance
component) as English labels. `this.tVocab(field, value, fallback)` localizes them:

- Keys on `vocab.<field>.<slug>` where the slug is `value` lowercased with
  non-alphanumerics collapsed to `_`.
- **Falls back to the backend label** for any value not keyed — so a new brand /
  model / value renders its English label unchanged (never a raw key).
- Returns an HTML-escaped string. **`this.tVocabRaw`** is the raw twin, for the
  few sinks that escape downstream (e.g. a value dropped into a data object the
  renderer `escapeHtml`s later — using `tVocab` there would double-escape).

The template literal **must be inline in the `t()` call**
(`this.t(\`vocab.${field}.${slug}\`)`) so the [reachability check](#checki18n)
sees every `vocab.*` key — a `this.t(varKey)` would read as a dead key. Standalone
components that don't use the renderers prototype (the room-card classes) carry
their own `tVocab` method using the same pattern.

## The language control

The header **globe** lets a user pick a language for *their* view, independent of
the HA system language and of other users. The choice is persisted with HA's
**frontend user-data** API (`frontend/get_user_data` / `set_user_data`,
`lang-store.js`) — per-user, cross-device, server-stored. It is the most explicit
source in `resolveLang` and bypasses the draft-gate (a deliberate opt-in).

Because this lives in *frontend* user-data, the **backend cannot read it** — a
constraint that drives the [guide-on-card](#guide-on-the-card) design.

## Locales: bundled, shipped, and drop-in

`loadDroppedLocales(baseUrl)` discovers `<code>.json` files from a served
`index.json` and loads each via `loadLocale` (fetch → `flattenLocale` →
`validateLocale` → `registerLocale`). It runs twice (`ensureLocalesLoaded`):

1. The **shipped** non-English locales (first-party, from the served frontend
   dir) — no status, keep their bundled review status (e.g. `draft`).
2. The user **drop-ins** (`config/eufy_vacuum/locales/`, tagged `status:"custom"`)
   — gated as untrusted (below) and draft-gated like any unreviewed locale.

`en.json` is refused (the base is not overridable). `validateLocale` drops bad
shapes / unsafe keys (`__proto__`) / placeholder-parity violations, so the English
fallback is always intact. **`flattenLocale`** lets locales be *authored* nested
(commons + scoped sections) and flattens them against the English manifest into
the flat `key → string | plural-object` catalog `translate()` expects.

## Guide on the card

Maintenance **guide content** (cleaning steps, notes, frequencies) used to follow
`hass.config.language` — the HA *instance* language — because it is built in a
shared backend snapshot with no per-user context. That diverged from the ~95% of
the card driven by the per-user globe (a confusing "two switches"). Since the
per-user language is frontend-only the backend can't reach it, so the guide moved
**onto the card**: `guide-translations.js` (generated by
`scripts/sync-guide-translations.py` from the same Python source of truth) carries
the English base + the official-manual translations, and
`maintenance.js _localizedGuide()` overlays steps/notes/frequency by the resolved
per-user language (per-field → English → the backend value). One switch.

## The intake gate

> Security boundary. A user-dropped `custom` locale is **untrusted** and its
> values feed ~13 `tRaw` `innerHTML` sinks. The gate scrubs or rejects each file
> **before** `registerLocale`, so by translate-time provenance no longer matters.

`sanitizeOrQuarantineLocale(catalog)` in `sanitize-locale.js` returns one of three
bright-line outcomes:

| outcome | trigger | action |
|---|---|---|
| `REJECT_MALFORMED` | not a plain object of string / plural-of-string values | soft skip, **not** hash-locked (retried next reload) |
| `QUARANTINE_HOSTILE` | any value carries **active content** | reject the **whole file** (a tamper signature taints the shared-source siblings); hash-locked |
| `LOAD` | clean, or only inert-disallowed markup that was scrubbed | register the cleaned catalog |

It walks **every** value, including each plural-object form, and:

- **Detects by PARSING**, not regex — a real-browser `<template>` walk, the same
  parser the `innerHTML` sink uses. That is what defeats encoded/padded evasion
  (`java&#9;script:` collapses to its scheme via `new URL()`; `on\nerror` resolves
  to its true attribute name in the DOM). Active content = a dangerous tag
  (`script`/`iframe`/`object`/`embed`/`link`/`meta`/`base`/`form`), an `on*`
  handler, or a non-`http(s)` URL scheme (including scheme-relative `//host`).
- **Scrubs inert junk** to **escaped-visible** text — a disallowed `<span>` renders
  as literal `&lt;span&gt;` so a translator *sees* their mistake (silent stripping
  hides it). The allowlist `strong`/`em`/`code`/`a` survives; an `<a href>` off the
  host allowlist (`github.com` / `kingchddg901.github.io`) keeps its text, drops
  the href.
- **Hardens** the scrubbed output through **DOMPurify** as a final, independent
  pass — the string that ultimately reaches the sink is one DOMPurify certifies.

The gate runs **only on `status:"custom"` drop-ins** (shipped locales are vetted
at build time) **and only in a browser** (`typeof document` — the sink only exists
there; Node/SSR has nothing to defend). It fails **closed** (a throw → no
register). `loadLocale` hashes the raw bytes (`FNV-1a` — a dedup key, not a crypto
primitive): a hostile file is hash-locked and skipped *silently* on re-load, while
a fixed file gets a new hash and is re-evaluated fresh — no rebuild, no manual
step. `getLocaleQuarantineReport()` exposes the record for diagnostics.

> Why DOMPurify is the *final* pass, not the detection engine: `DOMPurify.removed`
> logs the `BODY` wrapper (not the forbidden tag) when the whole value is stripped,
> so it's unreliable for detection. The `<template>` walk + escape-visible scrub
> are self-sufficient and adversarially tested; DOMPurify is kept as
> defense-in-depth over them.

## check:i18n

`npm run check:i18n` (`scripts/check-i18n.mjs`, framework-free Node) is the
contract gate, run after every wave:

- **Contract** — exercises `translate()`: the fallback chain, interpolation,
  plural selection, and Trust-Model-B *adversarially* (a `<script>` catalog value
  must come back escaped) — the real security assertion the visual harness can't
  make.
- **Keys** — every literal `t("…")`/`tRaw("…")` in `src/` must exist in `en.js`
  (an orphan renders a raw key — FATAL); every defined key must be **reachable**
  from source (a literal call, a quoted key-as-data-value, or a `t(\`…${…}…\`)`
  template — this is why `tVocab` inlines its template). Source-derived, no
  allowlist.
- **Locale validation** — each shipped locale validated against the manifest
  (placeholder parity, plural forms, no unsafe keys), reporting its `→ en`
  fallback count.

The **intake gate** has its own real-Chromium adversarial suite
(`scripts/sanitize-locale.test.mjs`) — jsdom would test a *different* parser than
the runtime sink, exactly where mutation-XSS hides, so it bundles the real
`index.js` and runs `loadLocale` end-to-end in the browser. See
[Testing](../testing/01-overview.md).
