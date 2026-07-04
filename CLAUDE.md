# eufy-vacuum-manager — working rules

## ⛔ SCAN THE DOCS BEFORE SCOPING (hard gate — do this FIRST)

Before scoping any change **or** investigating how a subsystem works, read the relevant
doc under `docs/dev/` first. Start at **`docs/dev/README.md`** (index of ~42 dev docs); if
unsure which file, run `grep -ril "<term>" docs/` before opening code.

The render pipeline, map-data shapes, id mappings, adapter contracts, storage model, and
card architecture are **all documented**. Reuse the doc and frame new work as a *delta* —
do **not** re-derive internals from code when a doc already answers it, and don't raise a
"feasibility" concern before confirming no doc resolves it.

Recognize the pattern — misses this has already cost:

- The VA-render payload ships **`room_names` = `{rid: name}`** (the raster-rid → room bridge).
  Documented in `docs/dev/map-state-source.md`; re-derived from code instead → a wrong turn.
- The room editor is a **body-level modal** bound in `bindModalHostEvents` (not the shadow
  root). Documented in `docs/dev/19-card-architecture.md`; re-derived → a wrong turn.
- A sub-agent's *assumption* about internals (e.g. "raster rid == room.id") is not a doc.
  Prefer the doc; verify agent claims against it or against real device data.

## Build / deploy / test (don't guess these)

- **Frontend:** edit `src/`, then `npm run build:deploy`. Never hand-edit `frontend/*.js`
  (build artifacts). Gates: `npm run check:i18n`, `npm run check:styles`. JS unit tests:
  `node --test src/**/*.test.mjs`.
- **Deploy to live HA:** `scripts/deploy-live.ps1 -SkipBuild` (Z:\ = prod). A **frontend**
  change needs only a hard-refresh; a **backend** (Python) change needs a full HA restart.
- **HA Python tests (Docker only):**
  `docker run --rm -v "<repo>:/workspace" -w /workspace eufy-vacuum-test python -m pytest tests/ -q --no-header --no-cov -p no:cacheprovider`
- Every user-facing string routes through i18n at creation (`src/i18n/en.js` + `check:i18n`).
