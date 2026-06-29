# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow semantic-ish versioning.

Releases before 0.9.10 are recorded as
[GitHub tags/releases](https://github.com/kingchddg901/Vacuum_Agent/releases)
only.

## [Unreleased]

## [1.5.0] - 2026-06-28

**Drive your vacuum from your own dashboard.** Beyond the sidebar panel, the
integration now ships **two drop-in Lovelace cards** you add to your normal
dashboards straight from the card picker — no resources to register. The **Vacuum
Agent — Dashboard Mode** card is a compact multi-room control surface (pick rooms +
their settings, run a saved profile or an Eufy app scene, see the map, Start / Dock);
the **Eufy Room Card** is one card per room. Both carry the per-user language globe,
and the embedded map is the full map from the panel. Thanks to
[@Pistakkio](https://github.com/Pistakkio) for the request
([#34](https://github.com/kingchddg901/Vacuum_Agent/issues/34)).

### Added
- **Dashboard Mode card** (`vacuum-agent-dashboard`) — a compact, embeddable
  multi-room control card: a status header, a collapsible map, a collapsing per-room
  accordion (toggle a room, expand it to set that room's own mode / suction / water /
  path / passes), a run-launcher for your saved profiles and (Eufy) app scenes, and
  Start / Dock. **Arm-then-Start:** choosing rooms, a profile, or a scene is inert —
  nothing runs until you press Start. Hide any section from the visual editor.
- **Embedded map in the cards.** The full map — the VA-rendered room-blob backdrop,
  rotate, pan/zoom, overlay layers, the map companion, and "draw a box" zone clean —
  now runs inside the dashboard card too, not just the panel (lazily loaded so the
  card stays light until the map is shown).
- **Pin your map view.** The map remembers your pan and zoom between reloads (per
  device); the fit button resets it.
- **Move room names.** Drag a room's name label anywhere on the map (handy when a name
  sits over a doorway); drag it back to the room's centre to restore automatic
  placement.
- **Language globe in both cards.** The same per-user language picker the panel has —
  your choice follows you across devices.
- **Strict cleaning order (Roborock).** When a vacuum cleans rooms in a fixed order
  rather than path-optimising, the card offers a "use strict order" toggle.

### Fixed
- **Translations render correctly.** Fixed a double-escaping bug where a translated
  string containing an apostrophe (e.g. French *"Niveau d'aspiration"*) showed the raw
  `&#39;` entity, and a stale-cache bug where a freshly translated locale could load an
  old copy (newly added keys falling back to English). Translated the new card strings
  into all seven shipped languages.
- **Map view stays put.** The pinned pan/zoom is no longer wiped on first load, and a
  window/container resize can no longer scroll the map off-screen.
- **Eufy scene picker.** The Eufy app-scene dropdown no longer lists the placeholder
  "None" option, and hides entirely when there's nothing to pick.
- **Room card vacuum swap.** Changing the vacuum in a Room card's editor now correctly
  refreshes its room list.

### Changed
- The map and the Rooms list in the dashboard card are **collapsible**, to keep the
  card compact.

### Documentation
- New **[Dashboard & Room cards](docs/user-guide/20-dashboard-and-room-cards.md)** user
  guide; the developer **card-architecture** reference gained a section on the
  standalone cards, the three-bundle build, and the `<eufy-vacuum-map>` host.

## [1.4.1] - 2026-06-28

### Fixed
- **Removing the original (config-flow) vacuum no longer brings it back.**
  Deleting the vacuum the integration was first set up with now also clears it
  from the config entry, so it doesn't reappear on the next reload/restart.
  (1.4.0 dropped the vacuum's data but left it in `CONF_VACUUM_ENTITY_ID`, which
  setup re-created on load — thanks to Pistakkio for catching it.)

## [1.4.0] - 2026-06-28

**Remove one vacuum, not the whole integration.** You can now delete a single
managed vacuum from its device page — its panel, entities, and data are removed
while your other vacuums keep running. Plus documentation refreshes.

### Added
- **Remove a single vacuum.** Deleting a managed vacuum's device in
  **Settings → Devices & Services → Vacuum Agent** now removes just that vacuum
  (its sidebar panel, entities, trackers, and stored data) instead of only
  offering "Disable." The other managed vacuums are left untouched, and its
  learning history and saved map images are retained on disk so re-adding the
  same vacuum restores them. (Implements Home Assistant's
  `async_remove_config_entry_device` hook.)

### Documentation
- README refreshed: a **Contributors** section (thanks @Nebr88 for the Roborock
  duration / live-room fixes), the language packs surfaced, the live-map
  prerequisite corrected to **eufy-clean v1.11.1+** (now in jeppesens mainline —
  no fork), and the battery / map-tools wording tightened.
- Developer docs: corrected the Eufy live-map sourcing throughout (jeppesens
  mainline, not a community fork).

## [1.3.0] - 2026-06-27

**The card speaks your language.** The whole card UI is now localizable — every
tab, the adapter vocabulary, relative timestamps, toasts, and the maintenance
guides all read from a translation catalog instead of hardcoded English. This
release ships **seven languages** (German, French, Spanish, Dutch, Italian,
Portuguese, Russian), a per-user language picker in the card header, a per-user
localized upkeep guide, and a security gate that lets you safely drop in your own
translations. Plus: Eufy scalar/Tuya device support, and Roborock duration /
live-room fixes from an external contributor.

### Added
- **Pick your card language.** A language globe in the card header lets each user
  switch the card's display language on the fly. The choice is saved per-user on
  the server (Home Assistant frontend user-data), so it follows you across every
  device and browser; **Auto** defers to your Home Assistant language. A
  per-dashboard **Display language** override is also available in YAML
  (`config.i18n.locale`) and as a dropdown in the visual config editor, so one
  dashboard can force a specific language (or English) regardless of the system
  language.
- **Seven languages, full parity.** German (de), French (fr), Spanish (es), Dutch
  (nl), Italian (it), Portuguese (pt), and Russian (ru) — each a complete
  translation with **English filling in automatically** for anything a locale
  leaves untranslated. Essentially the entire card is covered: Setup and Rooms
  onboarding, the shell/header, the live Map and mapping-review, Upkeep/Maintenance
  and Base Station, the Room rule editor, Metrics, Learning Review/History,
  External Jobs, the Theme editor and preview, and the standalone room card.
- **Localized adapter vocabulary.** Clean mode, fan speed, water level, clean
  intensity, run status, sort/filter chips, confidence/trust tiers, maintenance
  labels, and theme-editor token/group/facet/tag names now render in the card
  language rather than the backend's English (any unkeyed value safely falls back
  to its English label). Relative timestamps ("just now", "yesterday", "5m ago")
  and the fresh-install "setup needed" placeholder are localized too, and
  event-driven toasts, confirmations, and inline errors now appear in your
  language.
- **Localized maintenance guides, following the card language.** The cleaning
  steps, notes, and recommended frequencies for the filter, rolling brush, side
  brush, sensors, and dust collector now appear in your language — sourced verbatim
  from Eufy's official X10 Pro Omni (T2351) manuals for de/es/fr/nl/it/pt, with
  Russian translated and cross-checked against those official versions (Eufy
  publishes no Russian manual). The guide now follows the **per-user** language
  globe, fixing a reported split where ~95% of the card followed the user's
  language but the guide stayed on the Home Assistant instance language; 286
  missing frequency phrases were back-filled across all model families.
- **Per-language plurals.** Count-driven strings now use each language's own
  grammar via `Intl.PluralRules`, so a translation supplies as many plural forms
  as its language needs (Russian's one/few/many/other, Arabic's six) and the right
  form is chosen by count automatically.
- **Bring your own language.** Drop a JSON locale into
  `config/eufy_vacuum/locales/` and the integration auto-discovers and serves it;
  the card lists it in the language globe under its native name. A locale can also
  be pointed at by URL from the dashboard config (single `url` or a per-language
  `url_map`), fetched and validated at runtime (same-origin only). A generated
  translator reference (`en.reference.jsonc`) ships alongside the locales with the
  full key structure, the English value, and an inline context note per string
  (1,373 keys, 533 with notes) as a copy-from template that is never itself loaded.
  Translators author in a readable nested structure with shared `commons`; the card
  flattens it at load time, so the organization costs nothing at render.
- **Documentation.** A user guide for choosing a language, and a contributor
  translating guide covering the authoring format, plural rules, dropping in your
  own locale, the draft-to-stable review path, and exactly what the intake gate
  allows, scrubs, and quarantines.
- **The learning data reads your language too.** The Learning Review job cards —
  the auto-exclude suggestion badges and the per-run "this run …" explanation — the
  composed room-profile labels in the Metrics and Learning Review filters, chips,
  and cards, and the fallback label for an unnamed map all localize now. Each is
  keyed on a stable backend code with the English text as a per-value fallback, so
  a code we haven't translated still reads in English rather than a raw key.

### Changed
- **Drafts don't activate automatically.** The seven new languages ship as
  AI-assisted drafts pending native-speaker review, and are draft-gated: a draft
  language reached via your Home Assistant system language quietly falls back to
  English until it is native-reviewed. You can still explicitly opt into any
  language (or force English) from the globe or the dashboard config, which
  bypasses the gate. Russian is the live pilot under native review.
- **Pickers always read in their own script.** The language menu and draft tags
  render in each language's own name and script (for example "Deutsch (Entwurf)",
  "Русский (черновик)"), so the menu stays readable even from inside an unfamiliar
  translation.
- **Untrusted translations are hardened on two independent layers.** Every catalog
  string is HTML-escaped by default at the rendering sink, so a translation value
  can never inject markup; custom drop-in locales additionally pass through a
  sanitize-or-quarantine intake gate (below) before being registered. The first-
  party locales shipped with the card are vetted at build time and are unaffected.
- **Drop-in locales get three clear outcomes.** A dropped-in locale loads as-is if
  clean, loads with disallowed formatting scrubbed (a friendly allowlist keeps
  `<strong>`, `<em>`, `<code>`, and `<a>` links to github.com /
  kingchddg901.github.io, showing other tags as visible literal text so a
  translator sees the mistake), or is rejected wholesale if it contains active
  content (`script`/`iframe`, `on*` handlers, or `javascript:`/`data:`/protocol-
  relative URLs). The gate parses strings through the same browser HTML parser the
  display code uses, so encoded evasion like `java&#9;script:` is caught for what it
  really is. Rejected files are remembered by content hash and skipped silently on
  reload; fixing the file clears it, and a diagnostics report shows what was
  quarantined and why.
- **Translations are layout-gated in CI.** Every shipped locale is rendered under
  deliberately lengthened text (desktop and mobile) and the build fails if any
  translated string breaks the layout, so a card in your language stays usable and
  free of unwanted horizontal scrolling.
- **Maintenance values prefer structured backend fields.** Percent remaining,
  hours, and used-since-reset are now read as structured fields (instead of echoing
  a pre-built English summary), so numbers and units format correctly in each
  language; trust-reason and dock action-gate messages are keyed on stable reason
  codes so they localize cleanly. Animal/companion names and the "Rainbow Bridge"
  idiom translate via established renderings, while protected proper names (e.g. the
  "Rainbow Bridge — Mittens" memorial) stay untranslated.
- **Deleting an unnamed map is now a one-click confirm.** The backend no longer
  synthesizes an English "Map 6" name for an unnamed map — which leaked English in
  every language and forced you to type an English token to delete it. Unnamed maps
  render the localized "Map {id}" label and drop their high-protection delete from
  "type the exact name" to a single explicit confirm; named maps still require
  typing their (locale-invariant) stored name.

### Fixed
- **The renderer now actually switches language.** A renderer-layer bug read the
  wrong Home Assistant handle and always fell through to English, silently making
  roughly 1,350 translated keys inert for language switching; the entire tab UI had
  been rendering in English regardless of your chosen language. A standalone
  room-card placed without a main card had the same problem (the runtime locale
  load was only wired into the main card). Both are fixed.
- **German "fan speed."** Corrected "Lüftergeschwindigkeit" (fan-blade RPM) to
  "Saugkraft" (suction) in four places to match vacuum terminology.
- **German/Dutch furnished-map labels.** An uploaded graphic was labelled
  "Kunst"/"kunst" (artwork) across nine strings; changed to "Grafik" (de) and
  "Afbeelding" (nl) to fit an uploaded floor-plan image.
- **Spanish/Portuguese accents.** Theme-editor labels were missing their diacritics
  after a first pass dropped them; re-translated with proper native spelling
  (Spanish restored across 95 labels, Portuguese across 212). Portuguese
  relative-time "mes" corrected to "mês".
- **Setup headings and floor-type chips.** Wizard step headings and floor-type
  chips (Hardwood, Tile, Carpet, …) were baked-in English data values that fell
  back to English even when a translation was active; they now translate in all
  seven languages (e.g. German Setup headings now render in German).
- **English-leaking maintenance sections.** Filled four guide sections that
  rendered in English inside otherwise-localized cards (mopping cloth, swivel wheel,
  rolling-brush guard note, dust-collector tank note) across all seven languages,
  and cleaned up Italian/Portuguese/Dutch notes that had leaked manual-section
  references.
- **Latent encoding/empty-value bugs.** Fixed double-encoding that would have shown
  literal HTML entities (e.g. a French "l'eau", a group name like "Status,
  Confidence & Alerts") in room-estimate rows, the mapping-review outlier badge, and
  theme group-filter chips; a Metrics cell that rendered blank because an empty
  translation was mistaken for "no value"; and a status slug so the backend's
  British "cancelled" is recognized and translated rather than leaking raw.
- **Restored the card shell styling.** A stray backtick in a stylesheet comment
  truncated the bundled CSS, leaving the header unstyled and tab scrolling broken
  with no error. The styling is back, and a build guard now fails loudly on this
  class of breakage rather than shipping it silently.
- **Smaller card download.** Non-English locales no longer ship inside the card
  bundle — they are served as JSON and loaded at runtime, shrinking the card from
  ~1.93 MB to ~1.15 MB (about 40% / 772 KB smaller).
- **No stray English on the profile cards.** The "save candidate" badge and a few
  setting values ("Vacuum and mop", "Standard", "Turbo") rendered English on the
  Metrics → Profiles cards and filters because the stored values were un-normalized
  display strings; they now localize.
- **The room editor only offers settings your robot has.** Each picker (suction /
  mode / water / intensity) listed values aggregated from *every* saved profile, so
  a value from one brand's template (e.g. a Eufy "Standard" suction) appeared as a
  selectable option on another robot — including a Roborock, whose suction set is
  only gentle/quiet/balanced/turbo/max. Pickers now show the adapter's declared
  options plus the room's own current value, nothing else.

### Eufy scalar/Tuya devices
- **Support for reduced-transport ("scalar/Tuya") Eufy robots.** Vacuum Agent now
  drives Eufy robots on eufy-clean's legacy path, where the robot exposes its room
  list as a vacuum attribute but never creates an active-map sensor. These devices
  can now import rooms and run per-room cleans — anchoring to a single implicit map
  when there is no active-map sensor but the room list is populated, instead of
  failing with a red "No active map detected" warning. The X10 Pro Omni is verified;
  the other mapper families (X / S / L / LR / Omni) are expected to work and are
  test-and-report. Live map still needs the smcneece eufy-clean fork.
- **Model detected from the device registry.** A scalar-provisioned X10 (model
  T2351) now detects as the "x10" family instead of falling back to "generic",
  restoring its mop, mop-wash/dry, dust-empty, and path-control capability hints.
  Existing installs self-heal on the next restart, and a capability refresh no
  longer reverts a correctly detected model back to "generic" (which had silently
  disabled rooms on scalar devices).
- **Diagnostics now open with a plain-English `self_check`.** The diagnostics
  download leads with a summary answering "why can't I import my rooms?" — the
  transport mode (full MQTT vs. reduced scalar/Tuya), whether room control/import
  are available, whether the map picture can render, and the detected model — without
  reading the raw internals.
- **Docs: which Eufy models Vacuum Agent can drive.** The README "Tested hardware"
  section and the user-guide overview gained a "Will my Eufy vacuum work?" guide:
  per-room cleaning, the live map, room rollover, and learning/ETA all require an
  Eufy that builds a room map with per-room segments. The basic-navigation RoboVac
  C-series and G-series build no room map and are documented as unsupported (owners
  are pointed to eufy-clean directly).

### Roborock (external contribution by [@Nebr88](https://github.com/Nebr88), [#19](https://github.com/kingchddg901/Vacuum_Agent/pull/19))
- **Cleaning durations are recorded correctly.** Roborock reports cleaning time as a
  duration sensor (minutes, sometimes hours or milliseconds) rather than raw
  seconds; Vacuum Agent now converts using the sensor's unit before storing, so runs
  and the learning/ETA system are no longer off by a factor of 60 (a 6.15-minute
  clean records as 369 s, not 6).
- **Live room tracking no longer completes rooms prematurely.** Roborock's
  current-room signal is a live pointer that can revisit rooms while it optimizes its
  route; pointer changes are now treated as position updates only, deferring room
  completion to the final job snapshot. Per-room fan speed is still pushed live as
  the robot moves through its optimized order.
- **No spurious anomaly warnings on optimized routes.** Stall, running-long, and
  skipped-room checks assumed queue-order cleaning; for path-optimizing devices that
  legitimately jump ahead, those checks are now suppressed so a normal optimized
  route is not misreported as a problem.

### Internal
- **i18n contract + reachability gates.** A framework-free `npm run check:i18n`
  suite (grew from 11 to 26 assertions) asserts the fallback chain, interpolation,
  plural selection, escape-by-default, the draft-gate, locale validation, and
  prototype-pollution defenses, plus an orphan/dead-key check (orphan = fatal) that
  proves key reachability from source rather than a hand-maintained allowlist. A
  central `validateLocale()` drops bad entries while keeping the rest, blocks
  `__proto__`/`constructor`/`prototype` keys, enforces placeholder parity, and keeps
  the clean catalog a strict subset so English fallback is never removable.
- **Locale-intake sanitiser.** `src/i18n/sanitize-locale.js` parses via a real
  `<template>` walk (matching the actual sink) with an escape-visible scrub, a tag/
  link-host allowlist, URL-parser-based scheme checks, FNV-1a content-hash
  quarantine, and DOMPurify as a final hardening pass; covered by a real-Chromium
  adversarial suite (mutation-XSS, namespace payloads, host-confusion) and vetted by
  three blind security reviewers.
- **Harness hardening.** Added a pseudo-long/Cyrillic locale generator, a property-
  based layout-overflow gate at desktop @500px and mobile @390px, a real-locale
  `shoot-locales` render path (7 languages × 10 tabs, zero real overflow), and an
  `i18n-locale` spec that proves the UI actually switches language — the regression
  the English-only harness had missed. A build-time `check-styles.mjs` guard
  verifies brace balance to prevent silent CSS truncation. English output stayed
  byte-identical across every migration wave.
- **Misc.** De-bundled locale loading shares one catalog load with no double-fetch;
  context-free primitives (Save/Edit/On/Off/…) hoisted to `common.*`; removed the
  dead `_slugify_profile_name` slugifier; `deploy-live.ps1` gained an optional
  `-LiveRoot` to target a clone instance. Roborock tests realigned to live-pointer
  behavior; lifecycle/dock-drift test flakes stabilized (2,771 passed, 1 skipped).
  Developer reference (`docs/dev/33-i18n-system.md`) added; `mkdocs --strict` clean.
- **Settings normalized to canonical codes.** Observed clean-mode / clean-intensity
  / fan-speed / water-level values are normalized through adapter-owned alias maps
  (mirroring the existing water-level aliases) before they reach the card, so it
  always receives a code its vocabulary is keyed on — no future un-keyed display
  string can leak from that path. Each brand declares its own maps in its adapter.
  Backed by a code-first reason-code path: the learning manager emits stable codes
  (status, sanity flags, learning blockers, exclude/cancel reasons) and the card
  localizes them, keeping the English text only as the fallback.

## [1.2.5] - 2026-06-23

### Fixed
- **Empty-rooms hint points to the right place.** When a managed vacuum has no
  rooms yet, its empty-state hint now directs you to **Setup → Import Active
  Map** (the path that actually populates rooms) instead of a stale instruction.

## [1.2.4] - 2026-06-23

### Fixed
- **Stable room identity for non-Latin names.** Room slugs are now NFC-normalized
  before becoming identifiers, so Cyrillic/accented room names that differ only by
  Unicode composition resolve to one stable identity across reconciliation.
- **Unnamed Roborock map imports.** A Roborock map with no name no longer fails to
  import (external contribution by [@Nebr88](https://github.com/Nebr88),
  [#18](https://github.com/kingchddg901/Vacuum_Agent/pull/18)).
- **DOM-XSS hardening.** Map-tooltip room labels are HTML-escaped before they reach
  the DOM, so a crafted room name can't inject markup into the map overlay.

### Changed
- **Live-map / zone messaging retargeted to the jeppesens fork.** The Eufy
  live-map and zone-clean docs now point at the maintained `jeppesens` eufy-clean
  fork (v1.11.1+) instead of the older smcneece fork.

### Internal
- Closed `map_source_coordinator` + `_common` coverage gaps and reconciled the
  testing docs; refreshed the README Screenshots + Documentation sections for the
  GitHub Pages hub.

## [1.2.3] - 2026-06-22

### Added
- **Download Diagnostics.** The integration now answers Home Assistant's
  *Download diagnostics* button (Settings → Devices & Services → Vacuum Agent →
  ⋮). Per managed vacuum it reports how each adapter role resolves to a real
  entity — the fastest way to spot a missing/blank `active_map` sensor, the most
  common onboarding snag — plus the active map, every stored map and its per-room
  config, capabilities, the raw provider vacuum state, and the maintenance
  snapshot. Read-only, brand-agnostic (Eufy + Roborock), with credentials and the
  free-text notes field redacted.
- **Issue templates.** A bug-report form that asks for a diagnostics download up
  front (so reports arrive with the data needed to triage them), plus a
  feature-request form.

## [1.2.2] - 2026-06-22

### Added
- **Lifetime device stats on the Maintenance tab.** Total cleaned area (m²), total
  cleaning time, and lifetime clean count — plus the **dock firmware version** — now
  surface in the Maintenance overview, sourced from the robovac_mqtt v1.11.0+ Eufy
  sensors. Each value is shown only on devices that report it (hidden otherwise), so
  brands/models without these sensors are unaffected.

### Fixed
- Battery health (`_battery_health` sensor) is now capped at **100%** — a battery is
  never "healthier than new". A raw reading above 100 (the cell charging faster than
  its install baseline, common while the baseline is young) looked odd; the uncapped
  value stays on the `_cv_charge_speed` diagnostic sensor and the health sensor's
  `uncapped_pct` attribute.

## [1.2.1] - 2026-06-22

### Fixed
- `services.yaml`: the furnished-render services (`set_furnished_art_placement`,
  `set_room_viewport`) declared a number-selector `step` of `0.0001`, below Home
  Assistant's `1e-3` floor, which failed `hassfest` validation. Switched those
  resolution-independent pct-float fields to `step: any`. No behavior change — these
  services are driven by the card, not entered by hand.
- CI: refreshed the map-configuration visual-regression baseline (the tab grew when
  the furnished-render + align panels landed in v1.2.0).

## [1.2.0] - 2026-06-22

**The map comes alive.** The Map view goes from a static backdrop to a live, interactive
surface: the robot is tracked across it in real time, you can lay a render of your actual
furnished home over the live map (the robot and overlays ride on top), draw a box to
zone-clean, and more. The biggest map release since the integration began.

### Added
- **Mittens joins the map.** A new **Rainbow Bridge** animal group — companions for
  remembered pets — debuts with **Mittens**. Unlike the themeable animals, she's painted
  true to life: her real markings stay fixed whatever theme you run, and only her eyes
  shift with battery state. *In loving memory.*
- **Live robot tracking & map overlays.** A new VA-owned read of the device's own map
  (`map_state_source`) puts the live robot position, heading, dock, current room, cleaning
  path, and hazards (no-go / no-mop / walls) on the map in real time — plus native
  current-room rollover and a faster live room/fan refresh on Roborock. A **Mascot follows
  robot** toggle lets your companion ride the robot's live position.
- **Furnished render.** Lay a to-scale render of your real home over the live map so the
  robot drives across your actual furniture. **Save map image** to trace over, upload your
  art, pick a view mode (Live / Blend / Art), and align by eye — drag, scale, rotate
  (coarse ±90°, fine ±1°/±0.1°, ±15° trim slider). No calibration step — aligning by eye
  once is all it needs, so the live overlays ride on top for free. Brand-agnostic
  (Eufy fork + Roborock).
- **Zone cleaning (draw a box).** Zone-clean an area you draw on the live map, at any map
  rotation, with suction/mop settings — on **Eufy** (via the fork) **and Roborock** (stock
  integration, no fork/PR). Per-clean caps: Eufy up to 10 zones; Roborock up to 5, each
  1–32.8 ft² (enforced in the card + at dispatch).
- **More map interactions.** Tap rooms on the map to build a clean selection (unpicked
  rooms dim), **Hide area** to mask map noise, and draggable room-area (m²) labels. On a
  **bare Roborock live map** (no drawn rooms), the room names, the mascot, and tap-to-select
  now work from the device's own rooms (selected rooms light up).
- **Smarter external-run learning.** App-started runs now use the robot's recorded path to
  work out which rooms were actually cleaned, feeding the external-run review wizard.

### Changed
- New user guides for furnished render, zone cleaning, hide-area, and the live map, plus
  reconciled services/data-model references and consistent "NN — Title" nav titles across
  the docs site.
- Eufy-measured planning defaults moved into the Eufy adapter (cleaner brand boundary).
- Internal: the core manager was re-bundled into focused subsystems — `PhaseRunner`
  (strict-order phases), `ActiveJobTracker` run-anomaly detection, a `live_refresh`
  subsystem (Roborock live room/fan), and `MapSourceCoordinator` (the `map_state_source`
  backend). No behavior change.

### Fixed
- Strict-order finalization records every phase's timing, not just the last.
- Learning guards: recharge-drain bias, attribution-confidence marker, and rescuing the
  first cleaned room when `cleaning_area` is stale.
- Roborock live-room refresh targets `roborock.*` (not `vacuum.*`) and sticky-disables on a
  missing service.
- CI flakes: serialized the dock-drift append + isolated its test; closed re-run
  config-dir/executor leaks.

## [1.1.1] - 2026-06-16

**Optional CV stack, handled cleanly.** The CV libraries (numpy, Pillow, scipy) that
power Auto (CV) map segmentation are optional — the integration loads and works fully
without them. This release makes that explicit instead of a silent dead-end.

### Changed
- **Auto (CV) is gated on runtime library availability.** The dashboard snapshot now
  surfaces `cv_available` / `cv_missing`; when numpy/Pillow/scipy are absent (e.g. on HA
  Container/Core), the card hides the "Auto (CV)" chip and shows a note pointing to Live
  map / custom layouts / manual bounds, rather than a silent "No segments analysed".
- **README install matrix.** Required = Home Assistant + one supported provider vacuum
  entity; optional = a provider map/camera entity, the CV science stack, and brand
  companion entities. Manual map setup is the source of truth and is never required to
  install or load — Vacuum Agent is a supervisory layer over whatever the provider exposes.

### Fixed
- Corrected a stale code comment pointing at a non-existent `mapping/image_segments.py`
  (the CV pipeline lives in `adapters/eufy/segmentor.py`).

## [1.1.0] - 2026-06-16

**Eufy live maps (via the eufy-clean fork).** Eufy vacuums can now use a live map as
the Map-view backdrop and compose tap-selectable rooms over it — the same flow the
Roborock S6 has — for installs running the community
[eufy-clean fork by smcneece](https://github.com/smcneece/eufy-clean) that renders the
robot's map and exposes it as a `camera.<device>_map` entity. Plain (non-fork) Eufy
installs are unaffected.

### Added
- **Eufy live-map backdrop + selectable "Live map" source.** A Setup-tab "Live map
  camera" picker points the Map view at a live `camera.`/`image.` entity
  (override-first over an auto-resolved `camera.{object_id}_map` pattern, existence-
  gated). A "Live map" segmentation source lets you draw and link tap-selectable rooms
  straight over the live map, reusing the custom-layout composer — richer than the
  Roborock integration, which draws no polygons. A per-vacuum room-label toggle hides
  the card's own labels so they don't stack on a map that already carries them, and a
  `camera.` backdrop refreshes at frame cadence via a cache-bust on its stable token.

### Changed
- Acknowledged Home Assistant's built-in Roborock integration and its maintainers in
  the README.
- Doc reconciliation for the live-map feature (user guide, services reference, dev
  references).

## [1.0.0] - 2026-06-16

**Second brand: Roborock.** Vacuum Agent began as an Eufy integration; 1.0 makes
it a *multi-brand* one. Everything brand-specific now lives in a declarative
adapter, and the **Roborock S6** ships as the second supported brand — per-room
cleaning, native live room tracking, live maps, and strict ordering, all
Eufy-safe (the Eufy path is byte-identical where it should be). 1.0 marks the
architecture settling: the adapter seam, the dispatch-engine job model, and the
live-map pipeline are now the stable foundation other brands plug into. The
**Eufy X10 Pro Omni** and the **Roborock S6** are each brand's tested reference
model.

### Added
- **Roborock adapter (Roborock S6).** A capability-detecting adapter brings a
  second brand online with no core forks: room discovery from the `roborock.get_maps`
  service response (with name-slug identity reconciliation), live name→segment-id
  resolution at dispatch, completion keyed on the cleaning binary, per-room **live**
  fan speed, and native `current_room` live room rollover. The S6's real
  constraints are modeled honestly — mop/water is observe-only, passes are global,
  and room profiles are dropped — rather than faked.
- **Live maps in the card.** On live-map brands the Map view uses the vacuum's
  **live map image** as the backdrop (no screenshot upload): draw and save room
  segments straight over it, rotate it in 90° steps (stored server-side, so it
  follows you across devices) with the whole layer — image, polygons, labels,
  mascot — turning together, and watch a dwell-debounced mascot follow the robot's
  current room (draggable even when rotated).
- **Strict cleaning order.** A per-run opt-in for path-optimizing brands (e.g. the
  S6, which treats queue order as advisory): the integration sequences the run one
  room at a time in your exact order, with a per-phase watchdog that settles,
  dispatches, verifies the device actually started the room, and retries — fixing
  the "second room never fired" failure where a robot ignores a clean sent the
  instant it docks.
- **Per-vacuum panel rename.** Each vacuum's sidebar entry can be renamed live from
  the Setup tab (default "Vacuum Agent") — useful once you run more than one.
- **Room-identity reconciliation.** When a re-segment renumbers rooms, an
  apply/dismiss review carries each room's durable settings, access-graph grants,
  and floor-type confirmations onto the new IDs by name.
- **Add-another-vacuum** control in the Setup tab, and capability-gated navigation
  (Base Station and Map Bounds tabs appear only on models that have them).

### Changed
- **Adapter discipline.** Brand specifics are declarative config, not core code:
  the dispatch payload **shape** and **job model**, the live-map image entity-id
  pattern, and the strict-order phase-timing all moved out of core into the adapter.
- **Docs reconciled to multi-brand.** The README and the entire `docs/` tree
  (62 audited doc↔code findings across 32 files) now cover Eufy and Roborock with
  brand-aware inline callouts; a new Roborock adapter developer reference was added.

### Fixed
- Recharge-resume finalize guard (a mid-job dock-to-recharge no longer ends the job).
- Honor an explicit `supports_water_control` capability hint (S6 water is unsettable).
- Reconciliation no longer leaks stale rule-status onto a re-used room ID.
- Live-backed custom segments rendered off-screen; mascot drag drifted on a rotated map.
- Learning snapshot reads moved off the hot path.

## [0.11.0] - 2026-06-14

**Theme System 2.0.** Themes were already fully customizable; this release makes
them *discoverable, shareable, and per-device*. A tag system runs across the card
and the public gallery, a submission bot turns a pasted export into a reviewed
pull request, colorblind-safety is now verified rather than claimed, and each
browser can pin its own theme.

### Added
- **Theme tags + search, in the card and the gallery.** Every theme is auto-tagged
  from its palette — mode (dark/light), accent, temperature, surface, contrast,
  accessibility, and source — with free-text "vibe" tags on top. Filter and search
  the gallery *and* the card's own theme picker with the same vocabulary (OR within
  a facet, AND across facets), and edit a theme's vibe tags inline in the picker.
- **Theme submission pipeline.** Submit a theme to the gallery from a GitHub issue
  form: a bot validates the export, auto-tags it, verifies colorblind-safety,
  renders a real-card preview, and opens a pull request for a maintainer. Nothing
  publishes automatically. See
  [Sharing themes](https://kingchddg901.github.io/Vacuum_Agent/docs/user-guide/15-sharing-themes/).
- **Verified colorblind-safe badge + "Best for" filter.** colorblind-safe is now a
  badge *any* theme can earn — verified by simulating the three dichromacy types,
  not eyeballed — and a **Best for** filter surfaces themes tuned for red-green or
  blue-yellow vision.
- **Per-device theme selection.** Pin a theme to just this browser or kiosk
  ("This device only"), or follow the shared active theme. Your library and edits
  stay shared across devices; only the *selection* is local.
- **Theme picking on mobile.** The Theme tab is now reachable on phones for
  browsing, switching, importing, and exporting whole themes (the Palette and
  Token editors stay desktop-only).
- **One-click gallery download** and **theme source provenance** (core / community
  / generated / manual), shown as a filter facet.
- **New documentation.** A
  [Theme system](https://kingchddg901.github.io/Vacuum_Agent/docs/user-guide/17-theme-system/)
  user guide and an
  [Authoring a theme](https://kingchddg901.github.io/Vacuum_Agent/docs/contributing/theme-authoring/)
  contributing guide, plus full docs for the tag system, submission flow,
  per-device themes, and colorblind buckets.

### Changed
- **Theme Export/Import is now a modal.** Export opens a window showing the JSON
  with a **Copy** button (and a **Send to HA** option that posts it to a persistent
  notification); Import is a paste box — replacing the old console dump and browser
  prompt. Copy works on plain-HTTP LANs via a fallback.
- **Theme picker layout.** A collapsible filter band and a scrollable grid keep a
  large library usable.

### Security
- **Pre-release hardening (adversarial review).** Closed a stored-XSS through a
  submitted author URL, restricted author-URL credits to direct http(s) links (no
  shorteners or dangerous schemes), fixed a per-device pin that could wipe itself
  on load, and stopped theme metadata (tags/author) being dropped when a theme is
  overwritten.

## [0.10.3] - 2026-06-13

Map-editor visibility fixes (custom-layout composer + CV vertex editing).

### Fixed
- **The composer's selection outline stays visible on light / photo map backdrops.**
  A selected shape's bright outline could wash out over a light custom-photo backdrop;
  it now carries a thin black halo on each side, so it reads on any backdrop.
- **Map-editor lines and vertex handles no longer balloon when you zoom in.** The
  CV-segment polygon stroke and the vertex grab dots were sized in map units, so they
  grew as you zoomed to align a room and hid the floor plan underneath. They are now a
  fixed thin size at any zoom level.

## [0.10.2] - 2026-06-13

Light-theme readability fixes — the card now renders light themes cleanly,
surfaced by adding the gallery's first light theme.

### Fixed
- **Room order numbers (#1–#5) are readable on light themes.** The room-card order
  label inherited a fixed near-white colour and disappeared on light surfaces; it
  now tracks the theme's secondary text colour (unchanged on dark themes).
- **The room-rules "Disabled" tag keeps its pill on light themes.** Its background
  and border were hard-coded white; they now use the surface/border tokens.

## [0.10.1] - 2026-06-13

A small theming fix.

### Fixed
- **Modals now follow the active theme.** A custom theme that set only the core
  colors — surfaces, text, and accent, as hand- and AI-authored themes typically
  do — left every modal (the room editor, the app-started-run review wizard, and
  the rest) on the default dark palette, because the modal/overlay token family
  didn't derive from those core colors. Modals now derive their surfaces, text,
  and accent from the active theme, so any theme themes its modals too. A
  light-mode default is preserved, and the built-in themes are unchanged.

## [0.10.0] - 2026-06-12

A UI-heavy release: hand-drawn custom map layouts, a real documentation site, and
a reworked profile filter — plus a batch of fixes.

### Added
- **Named custom map layouts.** Keep several hand-drawn layouts per vacuum
  alongside Auto/CV detection. Each layout can have its own backdrop, rooms, room
  links, and mascot dock spot. Build rooms from primitive shapes — rectangles and
  circles — then move, scale, resize, rotate, merge, or subtract cutouts. Link
  each custom room to a real vacuum room, then save and re-edit later. See
  [Making your own maps](https://kingchddg901.github.io/Vacuum_Agent/docs/user-guide/16-making-your-own-maps/).
- **Documentation site.** The docs now render as a searchable
  [MkDocs site on GitHub Pages](https://kingchddg901.github.io/Vacuum_Agent/docs/),
  cross-linked with the theme gallery.
- **Profile filters reworked.** The Metrics and Learning Review profile filters
  now have a search box, a height-capped scroll area, and settings-disambiguated
  chips. Duplicate-named profiles, such as several "Kitchen Vacuum Quick"
  variants, show their settings so you can tell them apart on both the chips and
  the result cards.
- **Independent floor-texture toggles.** Map polygons and room cards can now
  control floor textures separately.
- **Custom-map polish.** Added mascot dock spots and composer shape rotation.

### Fixed
- Large map backdrops no longer exceed Home Assistant's 4 MiB websocket limit and
  drop the connection. Uploads are resized/recompressed client-side while
  preserving transparency.
- Non-first custom layouts now render their room-control map correctly.
- Dashboard snapshots no longer block the event loop on a `room_stats` read.

### Internal
- Large test-coverage and documentation-reconciliation pass.

## [0.9.17] - 2026-06-08

> The external-run capture + review capability in this release was driven entirely by
> [@chubban-lgtm](https://github.com/chubban-lgtm)'s question in
> [#4](https://github.com/kingchddg901/Vacuum_Agent/issues/4) — *"does it not use the
> runs from the eufy app for learning review?"* I didn't think it was possible at first;
> a little digging proved otherwise. Thank you.

### Added
- **External-run review wizard: server-side re-segmentation.** The "review an
  external (app-driven) run" flow no longer only lets you merge rooms client-side
  — it now re-segments on the backend from the raw counter trace. Step 1 is a
  **room-count stepper** plus a per-boundary **Split here** / **Merge up** control
  (action-first labels — the button says what it *does*); step 2 is a **per-room
  settings editor** for `fan_speed` / `clean_intensity` / `water_level` drawn from
  the adapter vocabulary (it mirrors the live room editor). The card calls the new
  `eufy_vacuum.resegment_external_run` service (`src/actions/external-jobs.js`),
  which takes either an `expected_rooms` count *or* an explicit `active_boundaries`
  list (mutually exclusive) and returns the re-segmented record.
- **Pending external-run schema v2.** Finalizing an external run now persists the
  raw `counter_samples` + `settings_samples` and the full candidate-boundary pool
  alongside the segments (`learning/external_ingest.py`,
  `PENDING_SCHEMA_VERSION = 2`), so a run can be re-segmented after the fact
  without re-driving the robot. Records are flagged `resegmentable` when samples
  are present; v1 records (no samples) gracefully degrade to the legacy
  merge-only view. Samples are stripped from every served/returned record
  (`strip_samples`) so the API stays light.
- **Transit-aware boundary detection.** `counter_segmentation.py` is decomposed
  into `find_candidates` → `select_active` → `build_segments`. `find_candidates`
  now surfaces a **`transit`** boundary kind (a 60–90 s flat-area inter-room move)
  in addition to `wash_plateau` / `area_jump` — the real-transit case the old
  single-pass filter silently dropped. The legacy `segment_counters()` is kept as
  a **byte-identical back-compat wrapper** (transit disabled), so the
  finalize/history path is unchanged.
- **Live queue: running-long & skipped indicators.** `get_job_progress_snapshot`
  now reports a soft **`running_long`** anomaly (the current room is past
  `running_long_ratio` × its estimate but below the existing 2× stall) and a
  conservative **`skipped`** signal (a queued room strictly before the current one
  that never completed). The queue chips render these as a warning ring
  (running-long) and a dashed, struck-through chip (skipped); a new
  `eufy_vacuum_room_skipped` event (`EVENT_ROOM_SKIPPED`) fires once per skipped
  room.
- **Brand-agnostic JOB-segmenter engine seam.** The counter/run segmenter — the
  per-room boundary detector that reads the `cleaning_time` / `cleaning_area`
  counters — is now pluggable, mirroring the dispatch-engine pattern
  (`learning/job_segmenter_engines.py`, modelled on `queue/dispatch_engines.py`).
  An adapter selects an engine via a new `job_segmenter.engine` config key; the
  framework resolves it from `_JOB_SEGMENTER_ENGINES`. This is the COUNTER
  segmenter — distinct from the MAP segmenter (`mapping/segmenter_engines.py`,
  `eufy_cv_v1`), which is unchanged. The engine owns the brand-specific stages
  (`find_candidates`, `build_segments`) and the legacy one-shot composition
  (`segment_legacy`); `select_active` stays a brand-agnostic *framework* function
  (`counter_segmentation.select_active`) so the external-review wizard's
  count/toggle logic is uniform across brands. Canonical cross-engine
  `JobBoundaryCandidate` / `JobSegment` TypedDicts document the contract.
  `EufyCounterSegmenter` (`eufy_counter_v1`) delegates verbatim to the
  `counter_segmentation` primitives and defines its `DEFAULT_TUNING` *by
  reference* to that module's constants, so the Eufy path is byte-for-byte
  identical by construction. Unlike the map seam, an absent/unknown engine falls
  back to the **Eufy** engine (not a noop), so live rollover, external-run ingest,
  and learned history keep working with no adapter registered. All three counter
  consumers now route through the engine — learned history
  (`learning/history_store.py`), external-run ingest
  (`learning/external_ingest.py`), and live rollover (`jobs/active_job.py`).

### Changed
- **Live current-room tracking is now transit-aware.** The 5 s job-progress tick
  (`jobs/active_job.py`) advances the current room on a real 60–90 s inter-room
  transit, not only on a wash/area-jump boundary, via a new transit-aware
  boundary count — fixing rooms that the live queue under-counted mid-run. The
  finalize/history segmentation is untouched.
- **Brand-agnostic adapter hooks (Eufy is the default, byte-identical).** The
  Eufy adapter config gains a `live_transition` block (boundary gaps, cadence,
  `rollover_kinds`, `native_transition_source`) and an `anomaly` block
  (`running_long_ratio` 1.5, `stall_ratio` 2.0). The previously-hardcoded
  constants in `planning/run_plan.py` (per-level water rate, wash-interval bounds,
  low-water margin) are now read as *adapter-overridable hooks* —
  `_water_rate_ml_per_minute` takes a `rate_override` from
  `water_model_configs[model]["water_rates"]`, and the wash-interval bounds /
  low-water margin read `wash_frequency_bounds` (top-level adapter config) and
  `water_model_configs[model]["low_clean_water_margin_ml"]` respectively — each
  falling back to the prior Eufy value when the key is absent. (The Eufy adapter
  does not yet declare those override keys, so Eufy keeps the built-in defaults and
  behavior is unchanged; the seam is in place for a second brand.) The room-profile
  capability gate (`profiles/room_profiles.py`) now *derives* the mop→vacuum
  downgrade target from the vacuum-only built-in profile (`get_room_profile`)
  instead of hardcoding it.
- **Boundary thresholds de-duplicated to a single source.** The five gap/area/
  cadence thresholds (`gap_delayed_s`, `gap_transit_s`, `gap_plateau_s`,
  `area_jump_m2`, `cadence_s`) now live **only** in the adapter's
  `job_segmenter.tuning` block — live rollover, external-run ingest, *and* learned
  history all read them from the resolved engine tuning. The `live_transition`
  block was trimmed to just its orchestration knobs (`enabled`, `rollover_kinds`,
  `native_transition_source`); the five threshold keys were removed from it (and
  from `_LIVE_TRANSITION_DEFAULTS` in `jobs/active_job.py`). The persisted
  external-run record field `gap_transit_s` (60.0) is unchanged — only its
  provenance moved (module constant → resolved engine tuning). Values and behavior
  are unchanged for Eufy. *(This supersedes the 0.9.16-era note that
  `live_transition` carried the boundary gaps and cadence.)*
- **Adapter-sourced room-profile vocabulary.** Room profiles are now resolved from
  the adapter rather than read straight off the in-code constants. A new adapter
  `room_profiles` block + `resolve_profile_catalog()` (`profiles/room_profiles.py`)
  merges the block over the in-code defaults **per key** (`builtins`,
  `custom_template`, `legacy_aliases`, `default_profile`, the floor-type fan/water
  defaults, `normalize_defaults`); a None/empty block returns the in-code defaults
  verbatim. Every resolver gained an optional `catalog` param. The in-code
  `BUILT_IN_ROOM_PROFILES` stays the framework default and the
  `_PROTECTED_ROOM_PROFILE_NAMES` source (that module-load binding is untouched);
  the Eufy adapter declares the block *by reference* to those constants, so Eufy is
  byte-identical. Wired into the **dispatch** path (`queue/queue_engine.py`
  `build_room_clean_payload`), which resolves the catalog from the adapter and
  threads it into per-room resolution and the capability gate. The global/singleton
  profile editor and the pure room-builder defaults still use the framework default
  catalog (no per-vacuum context); a second brand's editor UI would show framework
  defaults until threaded — a documented follow-up.

### Fixed
- **Graduated external runs no longer falsely flagged "failed sanity checks."**
  The jobs index stored `sanity_passed` as `None`, so the history snapshot's
  `not item.get('sanity_passed', True)` test never hit its default and tagged
  *every* graduated external run as failing the backend sanity checks. The checks
  now use `item.get('sanity_passed') is False` (`learning/manager.py`), and
  graduation sets `sanity_passed=True` / `sanity_flags=[]` explicitly (external
  runs only graduate after passing the tier-1 identity gate, so they're sane by
  construction).
- **External-run room dropdown readability.** The "assign to room" `<select>`
  options now pin a dark background / light text, fixing washed-out unreadable
  options in Windows Chrome.

## [0.9.16] - 2026-06-06

### Fixed
- **Run Profiles panel no longer overlaps the room cards.** On narrow card
  widths the panel positioned itself with a viewport media query that ignored
  the card living in a container narrower than the window, so it overlapped the
  rooms. It now wraps below them via container-relative flex — the two never
  collide at any width.

### Added
- **Theme gallery + submission system.** A public
  [theme gallery](https://kingchddg901.github.io/Vacuum_Agent/) where you can
  browse community themes (each previewed as the real card), download one to load
  via **Upload**, and **submit your own** with a "+ Submit a theme" button. A
  submission flows through an issue form, a bot that validates the export and
  renders an inline preview, and a pull request a maintainer reviews and merges —
  nothing auto-publishes, and the validator reuses the card's own import safety.
  The gallery and bot are repo-hosted, so this doesn't change what HACS installs.

### Docs
- **Theme-sharing documentation pass.** New end-user guide
  (`user-guide/15-sharing-themes`), the full gallery + submission architecture in
  `dev/27-render-harness`, and cross-links from the theme-system, README, and
  testing docs.

## [0.9.15] - 2026-06-06

### Added
- **Colorblind Safe theme.** A new built-in theme with a CVD-validated palette —
  every status-color pair stays distinguishable under protanopia, deuteranopia,
  and tritanopia (CIEDE2000 ΔE ≥ 15). See the new Accessibility guide.
- **Always-on status shape marks.** Mapping-review badges now carry a distinct
  non-color shape per state in addition to color, so status is never conveyed by
  color alone — this applies to *every* theme, not just the colorblind one.

### Fixed
- **Mapping-review badges are now themeable.** They were colored by undefined CSS
  variables, so the hardcoded fallback always won and no theme could recolor
  them. Migrated to the registry `--evcc-sem-*` tokens (with a new
  `--evcc-sem-info`), so themes — including the colorblind palette — now drive the
  badge colors.

## [0.9.14] - 2026-06-05

### Added
- **Two-tier marble veins.** Marble now renders separate **major** and **minor**
  vein layers. A master opacity/blur rides both tiers at once; per-tier offsets
  nudge each tier while preserving the gap between them. The minor tier *recedes*
  — its color is a clamped lighten / desaturate / hue offset from the master
  (OKLCH relative color), so it reads as atmospheric depth rather than a flat
  second color. Per-tier blur is opt-in.
- **Per-floor-type theme export/import.** Move a single floor type's look in
  isolation: **Download Floor** exports just that type's tokens
  (`evcc-floor-{type}-…json`), and uploading a floor-scoped file **replaces only
  that floor's namespace** on your active theme (clear-then-apply, values
  clamped, unknown namespaces skipped) instead of swapping the whole theme.
- **Marble presets.** Carrara, Portoro, and Calacatta starter bundles for the
  two-tier vein system. They apply as a scoped replace on the marble namespace —
  they tune marble in place, they are not separate themes to switch to.

### Changed
- **Single-source token ranges.** Editor sliders and the import clamp now share
  one min/max/step definition per token, so a slider can never show a value its
  own importer would reject.
- **Floor masks regenerated at 2048×2048** (were 512) to match the tiling/shift
  the renderer uses — sharper textures without visible seams.

### Fixed
- **Floor-texture legibility.** Status chips, room controls, and the active-clean
  progress fill stay readable over a filled floor texture across a wide range of
  theme colors (opaque chip backing, halo text-shadow, and explicit z-layer
  pinning so the texture can no longer occlude the progress fill).

### Docs
- **Full documentation accuracy pass** across the developer and advanced guides:
  corrected the adapter-config schema (17 top-level keys; `mapping` is validated
  but is not a schema field), the config-flow and storage shapes, and the
  events/services references — removed three never-implemented "runtime
  management" services and corrected `map_id` to optional (auto-resolves to the
  active map). Testing-doc counts and coverage tables regenerated.

## [0.9.13] - 2026-06-03

### Fixed
- **Integration brand logo.** `logo.png` / `logo@2x.png` were ~2× over Home
  Assistant's brand-image size limit (1024×256 / 2048×512), so the new HA brands
  proxy (which serves the integration's local `brand/` folder by domain) rejected
  them and the logo failed to load. Downscaled to spec (512×128 / 1024×256); the
  icon was already correct.

## [0.9.12] - 2026-06-03

### Fixed
- **Completed the "Vacuum Agent" rename.** The sidebar **panel title** and the
  card's panel text still read "Eufy Vacuum" — a separate string from the product
  name renamed in 0.9.11 (`sidebar_title`, not "Eufy Vacuum Manager"). Both now
  read "Vacuum Agent".

## [0.9.11] - 2026-06-03

### Changed
- **Renamed the product display name to "Vacuum Agent"** (was "Eufy Vacuum
  Manager"); the GitHub repo moved to `Vacuum_Agent`. The Home Assistant
  **domain stays `eufy_vacuum`** — all `eufy_vacuum.*` services, `eufy_vacuum_*`
  events, and `/eufy_vacuum/` paths are unchanged, so existing installs and
  automations keep working. Eufy remains the only supported brand.

## [0.9.10] - 2026-06-03

Mostly a bug-fix release, with significant under-the-hood groundwork for
multi-brand support.

### Fixed
- **Learning stats no longer corrupt on disk.** Learning JSON is written
  atomically (temp file + atomic replace), and a malformed file (e.g. a
  half-written `accuracy_stats.json`) is tolerated and self-heals instead of
  erroring on every startup.
- **No more event-loop stalls.** Synchronous file I/O during setup, dashboard
  refresh, and the job-start snapshot now runs in the executor — resolves the
  "Detected blocking call … inside the event loop" warnings.
- **Mid-job restart recovery fixed.** A crash in the periodic trace-sample flush
  meant a job spanning a Home Assistant restart silently lost its trace (no
  boundary learning); the flush now works.
- **No spurious maintenance warnings at startup.** Maintenance sensors no longer
  log "source entity unavailable" during the normal cross-integration load race;
  they start unavailable and only warn on a genuine availability drop.
- **Dock/maintenance reset buttons resolve correctly** when firmware entity names
  drift (the token-fallback resolution path was unreachable and always returned
  nothing).

### Added
- **Pluggable dispatch engine** with payload shapes for Eufy, Roborock/Ecovacs
  (flat id-list), and Dreame (parallel-array), plus a sequenced job-model
  mechanism wired into start/finalize — groundwork for second-brand adapters.
- **Brand-agnostic adapter conformance test harness.**
- **Developer docs:** Eufy adapter worked-example + CV-segmentor references, and
  a rewritten porting guide for the adapter architecture.
- **`scripts/update_test_docs.py`** — regenerates the testing-doc counts and
  per-module/coverage tables so they don't drift.

### Changed
- **Brand-agnostic core:** charging reads and the last residual Eufy assumptions
  moved out of core into adapter config; duplicate button data de-duplicated.
- **Test coverage to 94.1%** statement (CV segmentor 22% → 70%); CI gate aligned
  with the local behavior gate; checkout@v5 + setup-python@v6.

### Removed
- Dead code: defunct map entry-gating ("System-A"), the vestigial
  `boundary_pixel` field, and an unreachable current-room induction branch in the
  job-progress snapshot.

[0.9.13]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.12...v0.9.13
[0.9.12]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.11...v0.9.12
[0.9.11]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.10...v0.9.11
[0.9.10]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.9.1...v0.9.10
