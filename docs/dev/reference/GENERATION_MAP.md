<!-- GENERATED FILE — DO NOT EDIT BY HAND. Regenerate: python scripts/gen_generation_map.py -->

# Generation map

One authoritative graph of every checked-in **generated** artifact: who owns it,
what it is generated **from**, what **regenerates** it, and what changes
**downstream** when its source does. Rendered from the `GENERATORS` registry in
`scripts/check_generated_docs.py`; that
gate's UNGATED scan fails CI if any banner-bearing tracked file is missing here, so
this map is complete by construction. **Do not hand-edit** — edit the registry.

- **gated** — CI runs the generator and fails if the tree is stale (inputs are in-tree).
- **map-only** — inputs live outside the tree (e.g. `durable/` fixtures) or it is run
  by hand, so CI does not staleness-check it; it is still owned and mapped.

## The graph

| output(s) | gate | generated&nbsp;by | edit instead (sources) | downstream |
|---|---|---|---|---|
| `docs/dev/reference/ADAPTER-CONFIG.generated.md`, `docs/dev/reference/CAPABILITY-FLAGS.generated.md` | gated | `adapter-config` (python scripts/gen_adapter_config_docs.py) | `custom_components/eufy_vacuum/adapters/config_schema.py` · `custom_components/eufy_vacuum/adapters/registry.py` · `custom_components/eufy_vacuum/core/capabilities.py` · `custom_components/eufy_vacuum/adapters/eufy/adapter.py` · `custom_components/eufy_vacuum/adapters/roborock/adapter.py` · `custom_components/eufy_vacuum/adapters/dreame/adapter.py` | — |
| `custom_components/eufy_vacuum/frontend/animal-svg/animals/*.js` (6) | map-only | `animal-modules` (node scripts/build-animal.mjs <descriptor.json> --first-party) | `custom_components/eufy_vacuum/frontend/animal-svg/src/` | — |
| `src/i18n/guide-keys.js` | map-only | `dreame-guide-keys` (python scripts/sync-dreame-guide-keys.py) | `durable/dreame-port-fixture/resources/key-authoring/` _(external)_ | — |
| `docs/dev/reference/EVENTS.md` | gated | `events` (python scripts/gen_event_docs.py) | `custom_components/eufy_vacuum/` | — |
| `docs/dev/reference/GENERATION_MAP.md` | gated | `generation-map` (python scripts/gen_generation_map.py) | `scripts/check_generated_docs.py` | — |
| `custom_components/eufy_vacuum/frontend/locales/en.reference.jsonc` | map-only | `locale-reference` (npm run build:locale-reference) | `src/i18n/en.js` | — |
| `docs/testing/subsystems/*.md` (19) | gated · region | `mock-column` (python scripts/mock_docs.py) | `tests/` | — |
| `docs/dev/reference/THEME_TOKEN_MAP.md`, `docs/dev/reference/THEME_TOKEN_USAGE.md` | gated | `theme-tokens` (node scripts/gen-theme-token-docs.mjs) | `src/theme-tokens/` · `src/styles/` | — |

## Reverse index — “I need to change …”

- **`custom_components/eufy_vacuum/`** → regenerates `docs/dev/reference/EVENTS.md` · run `python scripts/gen_event_docs.py`
- **`custom_components/eufy_vacuum/adapters/config_schema.py`** → regenerates `docs/dev/reference/ADAPTER-CONFIG.generated.md`, `docs/dev/reference/CAPABILITY-FLAGS.generated.md` · run `python scripts/gen_adapter_config_docs.py`
- **`custom_components/eufy_vacuum/adapters/dreame/adapter.py`** → regenerates `docs/dev/reference/ADAPTER-CONFIG.generated.md`, `docs/dev/reference/CAPABILITY-FLAGS.generated.md` · run `python scripts/gen_adapter_config_docs.py`
- **`custom_components/eufy_vacuum/adapters/eufy/adapter.py`** → regenerates `docs/dev/reference/ADAPTER-CONFIG.generated.md`, `docs/dev/reference/CAPABILITY-FLAGS.generated.md` · run `python scripts/gen_adapter_config_docs.py`
- **`custom_components/eufy_vacuum/adapters/registry.py`** → regenerates `docs/dev/reference/ADAPTER-CONFIG.generated.md`, `docs/dev/reference/CAPABILITY-FLAGS.generated.md` · run `python scripts/gen_adapter_config_docs.py`
- **`custom_components/eufy_vacuum/adapters/roborock/adapter.py`** → regenerates `docs/dev/reference/ADAPTER-CONFIG.generated.md`, `docs/dev/reference/CAPABILITY-FLAGS.generated.md` · run `python scripts/gen_adapter_config_docs.py`
- **`custom_components/eufy_vacuum/core/capabilities.py`** → regenerates `docs/dev/reference/ADAPTER-CONFIG.generated.md`, `docs/dev/reference/CAPABILITY-FLAGS.generated.md` · run `python scripts/gen_adapter_config_docs.py`
- **`custom_components/eufy_vacuum/frontend/animal-svg/src/`** → regenerates `custom_components/eufy_vacuum/frontend/animal-svg/animals/*.js` (6) · run `node scripts/build-animal.mjs <descriptor.json> --first-party`
- **`durable/dreame-port-fixture/resources/key-authoring/`** _(external, provenance only)_ → regenerates `src/i18n/guide-keys.js` · run `python scripts/sync-dreame-guide-keys.py`
- **`scripts/check_generated_docs.py`** → regenerates `docs/dev/reference/GENERATION_MAP.md` · run `python scripts/gen_generation_map.py`
- **`src/i18n/en.js`** → regenerates `custom_components/eufy_vacuum/frontend/locales/en.reference.jsonc` · run `npm run build:locale-reference`
- **`src/styles/`** → regenerates `docs/dev/reference/THEME_TOKEN_MAP.md`, `docs/dev/reference/THEME_TOKEN_USAGE.md` · run `node scripts/gen-theme-token-docs.mjs`
- **`src/theme-tokens/`** → regenerates `docs/dev/reference/THEME_TOKEN_MAP.md`, `docs/dev/reference/THEME_TOKEN_USAGE.md` · run `node scripts/gen-theme-token-docs.mjs`
- **`tests/`** → regenerates `docs/testing/subsystems/*.md` (19) · run `python scripts/mock_docs.py`

## Per generator — edit here, never there

### `adapter-config`
_the adapter config contract, witnessed by all three shipped adapters_
- **EDIT HERE:** `custom_components/eufy_vacuum/adapters/config_schema.py`, `custom_components/eufy_vacuum/adapters/registry.py`, `custom_components/eufy_vacuum/core/capabilities.py`, `custom_components/eufy_vacuum/adapters/eufy/adapter.py`, `custom_components/eufy_vacuum/adapters/roborock/adapter.py`, `custom_components/eufy_vacuum/adapters/dreame/adapter.py`
- **DO NOT EDIT:** `docs/dev/reference/ADAPTER-CONFIG.generated.md`, `docs/dev/reference/CAPABILITY-FLAGS.generated.md`
- **REGEN:** `python scripts/gen_adapter_config_docs.py`

### `animal-modules`  ·  map-only
_per-animal codegen from a sanitised descriptor; own gate is check-animal-pr_
- **EDIT HERE:** `custom_components/eufy_vacuum/frontend/animal-svg/src/`
- **DO NOT EDIT:** `custom_components/eufy_vacuum/frontend/animal-svg/animals/*.js` (6)
- **REGEN:** `node scripts/build-animal.mjs <descriptor.json> --first-party`

### `dreame-guide-keys`  ·  map-only
_the 18 Dreame key packs -> bundled EN + served per-lang key JSON_
- **EDIT HERE:** `durable/dreame-port-fixture/resources/key-authoring/` (external)
- **DO NOT EDIT:** `src/i18n/guide-keys.js`
- **REGEN:** `python scripts/sync-dreame-guide-keys.py`

### `events`
_every hass.bus.async_fire call site_
- **EDIT HERE:** `custom_components/eufy_vacuum/`
- **DO NOT EDIT:** `docs/dev/reference/EVENTS.md`
- **REGEN:** `python scripts/gen_event_docs.py`

### `generation-map`
_this registry, rendered as the who-generates-what navigation graph_
- **EDIT HERE:** `scripts/check_generated_docs.py`
- **DO NOT EDIT:** `docs/dev/reference/GENERATION_MAP.md`
- **REGEN:** `python scripts/gen_generation_map.py`

### `locale-reference`  ·  map-only
_translator reference: full nested key structure + context comments of en.js_
- **EDIT HERE:** `src/i18n/en.js`
- **DO NOT EDIT:** `custom_components/eufy_vacuum/frontend/locales/en.reference.jsonc`
- **REGEN:** `npm run build:locale-reference`

### `mock-column`
_the generated Mocking column, from the mock census_
- **EDIT HERE:** `tests/`
- **DO NOT EDIT:** `docs/testing/subsystems/*.md` (19)
- **REGEN:** `python scripts/mock_docs.py`

### `theme-tokens`
_theme editor registry + card CSS_
- **EDIT HERE:** `src/theme-tokens/`, `src/styles/`
- **DO NOT EDIT:** `docs/dev/reference/THEME_TOKEN_MAP.md`, `docs/dev/reference/THEME_TOKEN_USAGE.md`
- **REGEN:** `node scripts/gen-theme-token-docs.mjs`
