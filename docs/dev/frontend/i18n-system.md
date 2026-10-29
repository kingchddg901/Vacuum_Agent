# i18n system

Home Assistant localizes an integration's config flow and entity names, but it
gives a custom Lovelace card **nothing** for its own markup — every literal in
the card's renderers is English regardless of the user's HA language. This
subsystem is the seam that closes that gap: ~2,500 UI strings, plural-correct in
any language, switchable per-user, with community translations loadable at
runtime behind a security gate.

Source lives at
[`src/i18n/`](https://github.com/kingchddg901/Vacuum_Agent/tree/master/src/i18n/)
(the card is a build artifact — edit `src/`, run `npm run build:deploy`; never
hand-edit the bundle).

Two audiences:

- **Card developers** adding or touching UI strings — read [Authoring strings](#authoring-strings).
- **Translators / contributors** adding a language — start with the how-to,
  [Contributing a translation](../../contributing/translating.md); this page is the
  mechanism underneath it.

## Files

```
src/i18n/
├── en.js                 English base — the source of truth + the key manifest
├── index.js              translate() / resolveLang() / registerLocale / loadLocale
├── flatten.js            nested authoring JSON → flat catalog (+ commons/plurals)
├── sanitize-locale.js    the intake GATE (sanitize-or-quarantine untrusted drop-ins)
├── lang-store.js         per-user language choice, persisted via HA frontend user-data
├── font-store.js         per-user typeface choice (`ui_font`), same user-data object
└── guide-keys.js          generated upkeep-guide KEY pack (see "Guide on the card")
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
[user-facing language page](../../user-guide/19-language.md) makes that visible to the
user rather than leaving `Auto` looking broken.

## Trust Model B

Locales may be community-contributed, so `translate()` **HTML-escapes the catalog
string by default** — a contributed value carrying `<script>` can never reach an
`innerHTML` sink raw. The short, audited set of first-party strings that carry
*authored* markup (`<strong>`, `<code>`, …) opt out via `options.raw` (exposed as
`this.tRaw`). Interpolated `{name}` **values** are inserted raw — the caller
escapes user data at the sink, exactly as the original literal did. In an **RTL**
locale each substituted run is additionally wrapped in Unicode bidi isolates
(FSI `U+2068` … PDI `U+2069`) so an embedded LTR token — a number, `%`, `m²`, an
`entity_id`, a duration like "14 min" — keeps its own direction; LTR locales are
left byte-identical. Invisible controls are used rather than a literal `<bdi>`
tag because `.t()` output also lands in plain-text sinks — the `textContent`
writes in `bindings/theme.js` / `bindings/map.js`, and the ~200 HTML **attribute**
values (`title=` / `aria-label=` / `placeholder=`) — where a tag would render as
visible text rather than as markup.

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

> ⚠ **Pick the twin by the SINK, and the mistake is invisible until a translator
> types an apostrophe.** `_renderBaseStationStat` escapes what it is handed, so the
> Base Station stat rows must use `tVocabRaw`; the escaping twin there yields
> `&amp;` / `&#39;` on screen. That stayed harmless for as long as it did only
> because of a property of the *data*, not of the code — measured 2026-10-27: zero
> of the 18 `vocab.device_status.*` catalogues contain `& < > " '`, while 144
> `vocab.*` values across 92 keys elsewhere do. So the bug is latent per-field and
> goes live the day a locale renders that field with a possessive or a contraction.
> Check the sink, not the current catalogue.

A **continuous** axis's band labels are vocabulary values too, and they come as *words*
rather than codes: Dreame declares `water_level_range.labels` = "Slightly Dry" / "Moist"
/ "Wet" for its 1..32 wetness slider, whose slugs land on
`vocab.water_level.{slightly_dry,moist,wet}` — the same three keys its coarse select
needs, so one family serves both. Localize at the point where the three labels are read
(`sliderRow` in `cards/_shared.js`, `_renderWetnessSlider` in `renderers/room-editor.js`),
not at the rendered word: the slider's live word is copied from `data-word-low/mid/high`
on every input event, so a fix at the render alone reads correctly until the first drag.

Three fields on the Base Station "Station Status" panel show how narrowly this is
scoped: `device_status` (the dock's own sensor), `lifecycle_state` (the start-readiness
verdict from `jobs/job_monitor.py`, six values, replica set `RN1SW6P4`) and `status`
(**this integration's** active-job slot, `jobs/active_job.py`). Three adjacent rows,
three different producers — which is why a pass that fixed the first left the other two
English. `get_dock_action_status` carries `active_job_status` and never `task_status`, so
the "Task" row is our job's state, not the robot's device string.

For room-**setting** values (`clean_mode` / `clean_intensity` / `fan_speed` /
`water_level`) the slug-derives-the-key contract only lands if the value the card
receives is already the canonical code. Stored settings are un-normalized display
strings ("Vacuum and mop", "Standard", "BoostIQ"), whose slug (`vacuum_and_mop` /
`standard` / `boostiq`) would miss the canonical key (`vacuum_mop` / `boost`) and
silently fall back to English. So the **backend normalizes** them first: each
brand's adapter declares display→canonical alias maps
(`adapter_config.vocabulary.{clean_mode,clean_intensity,fan_speed,water_level}_aliases`),
and `learning/manager.py::_normalize_profile_setting` canonicalizes every observed
room-profile setting before emitting — so on that surface the card gets a code its
vocab is keyed on. **Two mechanisms hold this property, not one:** the normalizer
covers the Learning Review's observed settings, while the surfaces that render a
room's *stored* value untouched (the rooms-view per-room chips, the standalone room
card, the external-run summary) are covered by **display-slug alias keys** — every
locale ships `vocab.clean_mode.vacuum_and_mop` alongside `vocab.clean_mode.vacuum_mop`,
so the label the card actually stored localizes rather than falling back to English.
Add a display spelling to an adapter's alias map and you must add the matching alias
key, or that surface silently reverts to English for every language.

That sentence was unenforced until 2.5.3, and nine spellings had no key — which is why
sinks that *do* call `tVocab` still rendered English for them: a correct call against a
missing key falls back, silently, to the backend's word. **`[AVK-1]`**
(`tests/unit/test_i18n_alias_vocab_keys.py`) is the gate now; it slugs every statically
declared alias and fails on any with no `vocab.<field>.<slug>` key. Writing it settled two
things:

- **An alias keeps its OWN word, not the canonical key's.** `clean_intensity.standard`
  canonicalizes to `narrow`, and showing a Eufy owner "Narrow" where their app says
  "Standard" would put core's internal key in front of the brand's word. `clean_mode` is
  the single exception (`[AVK-3]`), because all three brands name that axis with one
  phrase, so its aliases are spellings of one word rather than competing app terms.
- **Roborock's aliases are exempt because they are built at runtime.**
  `build_positional_aliases` derives them from the device's live option list, so the
  spellings are not knowable ahead of time. They ride `tVocab`'s documented fallback to
  the adapter's label, and localizing them belongs to the per-install vocabulary question,
  not to this contract. `[AVK-4]` anchors that exemption to the builder, so it dies with
  the code rather than outliving it.

(Reason-code
surfaces follow the same contract: the Learning Review
badges + per-job notes `tVocabRaw` the stable backend code — `vocab.reason_code.*`,
`vocab.exclude_suggested_reason.*` — with the English text as the per-code fallback.)

The template literal **must be inline in the `t()` call**
(`this.t(\`vocab.${field}.${slug}\`)`) so the [reachability check](#checki18n)
sees every `vocab.*` key — a `this.t(varKey)` would read as a dead key. Standalone
components that don't use the renderers prototype (the room-card classes) carry
their own `tVocab` method using the same pattern.

> ⚠ **And the call must be DOTTED.** The scanner's pattern is `/\.t(?:Raw)?\(`…`/` — it
> needs `.t(` or `.tRaw(`, so a bare `t(\`…\`)` on an injected translator parameter is
> invisible to it however correct the template is. That rules out the obvious shape for a
> pure helper outside the renderer prototype: take a translator, build the key, call it.
> A first cut of `floorTypeDisplayName` did exactly that, and all seven floor keys
> immediately reported dead. **The fix is to route through `tVocab` rather than to widen
> the scanner** — `tVocab` already carries a dotted inline template, so a helper that takes
> a `tVocabFn` and calls `tVocabFn(field, value, fallback)` inherits its reachability. It is
> also why both frontend-registry helpers (`animalDisplayName`, `floorTypeDisplayName`) take
> a vocab twin rather than a plain `t`.

### Two frontend REGISTRIES are vocabulary too

`vocab.animal.*` and `vocab.floor_type.*` are the exceptions to "the integration hands the
card vocabulary values": the animal companions and the floor textures are declared in the
card's own code and served assets, so no backend `*_label` was ever involved and the
surfaces simply printed the registry id. Two things about them are worth stating:

- **A proper noun gets no key.** `mittens` is a memorial pet — the 🌈 Rainbow Bridge group
  exists to treat her as a name — so she is deliberately absent from `vocab.animal.*` and
  resolves through the registry's own label in every language. Same exemption
  `font.opendyslexic` holds. `[ANM-1]` asserts she is the ONLY unkeyed entry, so a species
  added without a key is caught rather than inheriting the exemption.
- **The fallback makes a completeness gate necessary.** Both helpers prettify an unkeyed id
  rather than failing, which means a registry entry with no key renders a plausible English
  word and reads exactly like a finished one. `[FTL-1]` and `[ANM-1]` are what tell
  "English by design" from "nobody added the key".

`vocab.floor_type.*` replaced `theme_preview.floor.*` in 2.5.3. The old group was named for
its first consumer while the theme editor's own floor select needed the same seven words,
and its one irregular key (`.granite` serving the `granite_light` texture, annotated as
such) is the drift a consumer-named group collects — the single entry a derived key cannot
carry (`f/token_names_consumer_neutral`).

### faultLabel — brand fault codes

Hardware faults follow the same backend-hands-a-key contract, with their own
seam. The backend never sends fault *text*: the adapter maps a vendor's numeric
code to an i18n **key** (`adapters/eufy/vocabulary.py` `EUFY_ERROR_LABEL_KEYS`,
Roborock likewise), and the card resolves it at render time via
`this.faultLabel(key, code)` (`src/state/faults.js`, mixed onto the state by
`applyFaultState`):

- Keys on **`fault.<brand>.<slug>`** — the English base carries the per-brand
  tables (`en.js`, the `fault.eufy.*` / `fault.roborock.*` blocks), so locales
  translate fault labels like any other key. 237 keys total (189 Eufy + 48
  Roborock).
- The resolution is one inline template — `this.t(\`fault.${brand}.${slug}\`)`
  (`faults.js::faultLabel`) — which is what proves all 237 `fault.*` keys reachable to
  [check:i18n](#checki18n) instead of reporting them dead; that single-template
  property is a stated design reason for the seam existing at all.
- **Fallback is the raw code, deliberately.** A key with no entry (a brand that
  declares nothing, or a code the vendor shipped after the table was written)
  falls to `faults.unknown_code` ("Error 6013" — honest and searchable), or
  `faults.unknown` when there is no code either. A translator echoing the key
  back (`label === key`) is treated as no-entry, so a dotted key is never
  printed at the user.
- The Job Summary modal's fault list (`renderers/job-summary.js`
  `_renderJobSummaryFaults`) calls `faultLabel` directly per fault, alongside
  `source`/`recovered` fields the label alone doesn't carry. A sibling helper,
  `faultRows(errors)` (`state/faults.js:56`, alongside `faultLabel` itself —
  not in the renderer), maps a run's captured error list to a
  reduced `{index, code, capturedAt, label}` shape — but it has no production
  caller today; only `faultLabel` is wired into a renderer.

## The language control

The header **globe** lets a user pick a language for *their* view, independent of
the HA system language and of other users. The choice is persisted with HA's
**frontend user-data** API (`frontend/get_user_data` / `set_user_data`,
`lang-store.js`) — per-user, cross-device, server-stored. It is the most explicit
source in `resolveLang` and bypasses the draft-gate (a deliberate opt-in).

Because this lives in *frontend* user-data, the **backend cannot read it** — a
constraint that drives the [guide-on-card](#guide-on-the-card) design.

The same `eufy_vacuum_card` user-data object also carries the per-user
**typeface** choice (`ui_font`, `font-store.js`) — both writers read-then-merge
the stored object rather than clobber it, so the two preferences coexist. The
typeface chain itself is [styles-system §4](styles-system.md); the font
*offering* is language-gated (`fontSupportsLang`, `font-store.js`) — a font is
offered for a locale only after its glyph coverage has been verified against
that locale's shipped catalogue, not assumed from "looks Latin" — a cmap
inspection of the shipped OpenDyslexic-Regular/Bold found 1586 codepoints
including Latin Extended and Cyrillic, which is why `cs`/`pl`/`tr`/`ru` are in
the verified set; Hebrew and CJK are genuinely absent from the cmap and Arabic
additionally needs shaping. It ships one entry — `opendyslexic`,
verified for 12 of the 18 shipped locales (`cs`, `de`, `en`, `es`, `fr`, `id`,
`it`, `nl`, `pl`, `pt`, `ru`, `tr`).

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
**onto the card**: `guide-keys.js` (generated by `scripts/sync-dreame-guide-keys.py` from the
authoring fixture) carries the 42 English guide sentences; the other 17 languages are served as
`frontend/guides/keys/<lang>.json`.

⚠ THE PER-FAMILY PROSE CHANNEL IS GONE (2026-09-12). `guide-translations.js` and its 17 served
`frontend/guides/<lang>.json` packs held ~2.4 MB of vendor guide text keyed by device FAMILY.
All three adapters ship i18n KEYS now, so the last producer was deleted with the Roborock port
and nothing could fill the catalogs. The card's family-routing branch went with them.
the English base + the official-manual translations, and
`maintenance.js _localizedGuide()` overlays steps/notes/frequency by the resolved
per-user language (per-field → English → the backend value). One switch.

## The intake gate

> Security boundary. A user-dropped `custom` locale is **untrusted** and its
> values feed ~60 `tRaw` `innerHTML` sinks. The gate scrubs or rejects each file
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
contract gate, run after every wave. Four sections:

- **A. `translate()` contract** — exercises `translate()`: the fallback chain,
  interpolation, plural selection, `resolveLang`, `validateLocale`,
  `loadLocale`/`loadDroppedLocales`, and Trust-Model-B *adversarially* (a
  `<script>` catalog value must come back escaped) — the real security
  assertion the visual harness can't make.
- **B. Key cross-check** — every literal `t("…")`/`tRaw("…")` in `src/` must
  exist in `en.js` (an orphan renders a raw key — FATAL); every defined key
  must be **reachable** from source, one of three provable forms: (1) a
  literal `t("…")`/`tRaw("…")` call, (2) the full key appearing as a quoted
  string anywhere in `src/` (a data value handed to `t()` through a variable),
  or (3) a `t(\`…${…}…\`)` **template**, each `${…}` segment matched
  generically — this is why `tVocab` and `faultLabel` inline their templates.
  Source-derived, no allowlist; a template whose leading literal segment has
  no `.` is rejected, so a pathologically dynamic `${a}.${b}` can never
  silently exempt the whole catalog. A key defined but never reachable is
  reported as a dead key (warning, not a failure).
- **C. Shipped locale validation** — each served locale JSON is flattened
  against the English manifest and validated (placeholder parity, plural
  forms, no unsafe keys), reporting its `→ en` fallback count. A broken
  committed translation fails the build, not the user's render.
- **D. English-identical ratchet** — a locale value byte-identical to its
  English value is either legitimately universal (cognate, unit, symbol,
  product term) or untranslated leakage, and telling them apart needs a human
  exactly once. `scripts/i18n-accepted-english.json` is the reviewed snapshot
  (`accepted`: key → locale list or `"*"`; `pending`: provisionally tolerated
  but listed so entries can't rot invisibly — `accepted` holds **221 keys / 1005
  (key, locale) pairs** at 2.5.3, `pending` 2: `vocab.obstacle_type.cable`
  (`es`) and `vocab.obstacle_type.pedestal` (`es`, `pt`). ⚠ The file's own `_meta`
  asserts "pending is now empty" under a dated 2026-08-04 note, which was true that day
  and has been wrong since 2026-08-06; a 2026-10-28 note further down now says so, but the
  rule stands — read the `pending` object, never the prose beside it). Only
  **NEW** English-identical values not in the snapshot are flagged; comparison is
  language-blind by design (no dictionaries; plural objects compared by
  key-sorted serialization). **Don't re-derive the counts — the section prints its
  own**: one line giving the identical total and its accepted / pending / new split,
  from the same loop that does the flagging.

> **What the ratchet cannot judge, and the cheap rule that covers part of it.** Section
> D asks whether a value is English-identical, never whether being English is *right* —
> that call was made once, by hand, and then it is a snapshot. So an acceptance granted
> in error is invisible to it forever, and a *replica* of that acceptance inherits the
> error (`vocab.dreame.fan_speed.turbo` was added as a faithful copy of
> `vocab.fan_speed.max`'s ruling, and copied its one wrong locale with it).
>
> One asymmetry is mechanically checkable: a **non-Latin-script** locale (`ar`, `he`,
> `ja`, `ko`, `ru`, `zh-Hans`, `zh-Hant`) whose value still carries a Latin *word*, with
> placeholders and units stripped. Run over the whole catalogue 2026-10-27 it returned 15
> candidates — 7 real leaks, 7 `font.opendyslexic` (a typeface name, correct by design),
> and `ja` `common.ok` (standard in Japanese UIs; `ru` transliterated to `ОК`). The
> `ja` hit was decisive because *every* sibling in its field was Japanese and all six
> other non-Latin locales had translated that same key.
>
> **Its detection floor:** of the 1005 accepted pairs, **890 are in Latin-script locales**
> and the rule is blind to every one of them — a cognate and an untranslated word are
> byte-identical to it. It also says nothing at all about a value that is wrong but not
> English. It covers the remaining 115.
>
> ⚠ **One new entry deliberately breaks the Latin-script-only invariant** the paragraph
> above leaves behind: `vocab.fan_speed.boost_iq` / `.boostiq` are accepted for `"*"`,
> because their value is the product name **BoostIQ**, which Eufy's app shows
> untranslated in every language. Same exemption `font.opendyslexic` holds — it is a
> name, not a word. The rule will flag them on every future run; that is the cost of the
> rule being mechanical, and the reason the `_meta` note says so explicitly.
>
> The pairs reconcile exactly, which is the check that the snapshot has not rotted — and
> the section now **prints that reconciliation itself** rather than leaving it to hand
> arithmetic, which got it wrong twice (a string-only probe skipped the plural-object keys
> and invented three phantom "stale acceptances"; the snapshot's own pair count was then
> read as the identical count). At 2.5.3 the line reads **1008 pairs = 1005 accepted + 3
> pending + 0 new**, and 1005 is also the whole snapshot — every accepted pair is still
> English-identical, so there is nothing stale in it at all.
>
> ⚠ These four figures were last correct at the FIRST commit of the 2.5.3 census and were
> wrong by the time it was tagged — caught by the release audit, in the same paragraph that
> says hand arithmetic got it wrong twice. Re-derive them from the file and the gate's own
> printed line whenever this section is touched; do not carry them forward by hand.

- **E. Script sanity** — two shapes of *wrong* that need no dictionary, so unlike
  section D they are **failures in both modes**: neither is ever an editorial
  choice. (1) a CJK character in a non-CJK pack, (2) a high-frequency English
  function word inside a translated sentence, and (3) a value that is entirely
  Latin script in a non-Latin pack. Markup, its attribute values and `{placeholders}`
  are stripped first, and a pair section D has already accepted is skipped — one
  adjudication file, read by two sections.

> **Why section E exists, and what it cannot see.** Both of its first two cases were made
> for real while landing the 2.5.3 census, by assembling a sentence from two drafts and
> then *re-reading* it: a Czech string ending in the English "again", and a CJK word
> (`配置`) inside a Spanish one. Re-reading 374 strings found neither; four lines of scan
> found both. It also reaches a case **section D structurally cannot** — `zh-Hant`
> `theme.tab_tokens` was "Token" against an English "Tokens", so it was Latin-script but not
> English-*identical*, and the ratchet never looked at it. Section E is what surfaced it,
> and it was then ruled a defect rather than a loanword: that pack now reads 令牌.
>
> Three of its checks needed narrowing before they were usable, each found by running it
> rather than by thinking about it: the fullwidth-forms block (`U+FF00–FFEF`) is **out** of
> the CJK range, because `＋` and `－` are deliberate wide glyphs on the map's resize
> buttons; markup must be stripped, because `map.seg_cv_unavailable` carries a docs URL
> containing *making-your-own-maps* and every one of the 17 correctly-translated packs
> reported an English "your"; and the word test matches **whole tokens**, because
> `/[a-z]{3,}/` found "and" inside the Turkish *olağandışı*.
>
> **Its floor:** it says nothing about a plausible-but-wrong word in a Latin-script pack,
> which is exactly section D's blind spot too. Between them the two sections cover script
> mixing and byte-identity; neither covers meaning.
>
> Its residue over all 49,699 shipped values is **one** — `external_jobs.empty_app_branded`
> in `zh-Hant`, where "App" is ordinary written Chinese in Taiwan — recorded in
> `latin_in_non_latin`, a separate object from `accepted` because it is not
> English-identical and filing it there would assert something untrue. It was two until
> `theme.tab_tokens` was settled on 2026-10-28.

**`--strict-coverage`** is release-gate mode: NEW English-identical values and
any untranslated key become **failures** instead of a printed list (the
"@100%" claim is an enforced invariant at release time). A plain `check:i18n`
run stays permissive — an en-first mid-wave tree is a legitimate state. Sections A, B
and E fail in both modes.

## Classify a localization gap by what is BESIDE it, not by what it prints

The single most expensive mistake in the 2.5.3 census was a triage one. Fifty-five sinks
were bucketed by the **symptom** — "this prints a backend English sentence" — which
produced a bucket of eight labelled *needs backend reason-codes, the separate larger job*.
Measured against the producers, seven of the eight were card-side and three needed **no new
key at all**:

| what it printed | what was actually beside it |
|---|---|
| the Base Station's attention summary | `attention_count`, and the Upkeep tab already composing the same two keys from it |
| an upkeep row's remaining/usage detail | `_maintenancePrimaryValue` / `_maintenanceSecondaryValue`, twenty lines away in the same file |
| the learning panel's water warning | `water_warning_reason`, already used one line up to pick the notice's colour |
| the rule editor's save refusal | `result.reason`, in hand and ranked **third**, below two English strings |
| the setup wizard's step heading | the step `id`, with a resolver already trying `setup.step_<id>` |

So the question that sorts a sink is never "where does this English come from?" — it is
**"what else is in this payload, and does the card already know how to say it?"** A sink
whose code, helper or key is already present is the same one-line precedence fix as the
rest of the census; only a sink with genuinely nothing beside it is backend work. In this
census exactly one qualified: a thrown service exception in `renderers/setup.js`, which has
no code because the throw site is HA's, and inventing one means wrapping every service
call. That one is **documented as not localizable** rather than left looking missed:

> **The one string in the Setup view that stays English on purpose.**
> `renderers/setup.js`'s transient `error` line renders `String(error)` raw, and that is
> correct. It is not a backend `ActionResult` with a `reason` beside it — it is whatever the
> HA service call *threw*, so there is no code to key on and no closed set to enumerate.
> The card's own refusal strings on that surface already route through `setup.failed_*`
> keys; this line is the residue, and it is a diagnostic rather than UI copy. Giving it a
> code would mean wrapping every service call in a translating shim, trading a localized
> sentence for a less accurate one. If it ever needs to read in another language, the fix
> belongs at the throw site.

The **intake gate** has its own real-Chromium adversarial suite
(`scripts/sanitize-locale.test.mjs`) — jsdom would test a *different* parser than
the runtime sink, exactly where mutation-XSS hides, so it bundles the real
`index.js` and runs `loadLocale` end-to-end in the browser. See
[Testing](../../testing/01-overview.md).
