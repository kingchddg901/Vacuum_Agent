# PLAN — Mock Integrity (audit-1 remainder: "the MagicMock is killing us")

Status: AWAITING CHRIS'S GO. Nothing executes from this document until approved.
Grounding: docs/testing/03 + 04 read in full; every claim below re-verified against
tests/ on 2026-08-06 (post doc-truth-pass, so the docs are current).

## 1. Verified current state — this is NOT greenfield

The audit-1 lesson is already half-institutionalized. Do not nuke or rebuild what
exists:

- **`spec_manager()` exists and is correct** (`tests/_factories.py:151`):
  `create_autospec(EufyVacuumManager, instance=True)` + runtime instance attrs
  SCRAPED from `core/manager.py` (not hand-listed), + coroutine-close hygiene.
  `tests/unit/test_factories_spec_surface.py` is the guard on the guard.
- **The doctrine is documented** (docs/testing/04 §"…but use `spec_manager()`
  when the mock is handed to OUR code"): entity-driving stubs may stay partial
  (`make_manager_mock`); anything passed INTO production code must be spec'd,
  because a bare MagicMock **agrees with the caller, not the callee**.
- **The proof instrument exists**: `scripts/diff_test_equiv.py` — ORIGINAL vs
  CLONE, same test names, same pass count, identical executed-line set.
  `=> EQUIVALENT` or no cutover. This is the "don't nuke it" guarantee.
- **Adoption**: 17 test files already use `spec_manager`.

## 2. Verified remaining exposure — 86 bare `MagicMock()` in 27 files, three families

**F1 — manager stand-ins handed into production** (the family that bit 4× in
audit 1). Mostly converted; residuals found: `test_battery_sensors.py`
(4 `manager=` handoffs, no spec), `test_sensor_status.py` (9 bare, no spec),
`test_button_entity.py` / `test_listeners_active.py` (classify per-site: the
entity-driving subset is SANCTIONED and stays).

**F2 — collaborator stand-ins handed into production, no spec factory exists.**
e.g. `test_jobs_active_job.py`: 7× `fake_tracker = MagicMock()` +
`hass.data[DOMAIN]["mapping_tracker"] = MagicMock()` consumed by
`ActiveJobTracker`/jobs code. Same lie class as the manager, zero coverage by
current factories. Also ad-hoc trackers/stores in phased-job and listener tests.

**F3 — mock-hass** (the mass: e.g. 25 refs in `test_learning_estimator.py`).
Deliberately unfactored today (docs/testing/03 calls the 2-line idiom too
low-value to extract). The lie surface is real but different: `hass.states.get`
returning a MagicMock produces STATE OBJECTS that agree with the caller —
adjacent to the restart-sighting/unavailable classes audit 1 chased in
listeners.

## 3. Principles (all from the shipped docs — the plan changes call sites, not doctrine)

1. Entity-driving partial stubs are correct and stay (04-patterns).
2. A mock handed into our code is spec'd, no exceptions.
3. Every conversion is proven with `diff_test_equiv.py` — EQUIVALENT or no
   cutover. Behavior-preserving by construction, not by review.
4. Factories extract from real use, never speculatively (03-fixtures).
5. Testing docs update in the same commit as each wave (doctrine §13).

## 4. Waves

**W0 — the ratchet (stop the bleeding first).** A census test: count bare
`MagicMock()` per file against a committed shrink-only allowlist (the
KNOWN_DANGLING pattern from check-styles). New bare mocks in NEW places fail CI
immediately; the allowlist can only shrink. Cheap (one test + one JSON), lands
before any migration so the debt can't grow while it drains.

**W1 — F2 collaborator specs.** Add a generic `spec_of(cls, **attrs)` factory
(same scrape+autospec recipe as `spec_manager`, parameterized) + thin wrappers
per collaborator actually mocked (`spec_tracker`, …, extracted from real use).
Convert the F2 sites; diff_test_equiv each file; shrink the W0 allowlist.

**W2 — F1 residuals.** Per-site classification in the four named files:
handed-into-our-code → `spec_manager`; entity-driving → stays, with a one-line
comment naming it sanctioned. diff_test_equiv each.

**W3 — mock-hass (NEEDS A CHRIS DECISION — see §5).**

**W4 — the mock-failure ledger.** The audit-record wing for tests: a section in
docs/testing/05 cataloguing each known mock-caused live failure (what lied,
which family, which pin now guards it), starting with audit 1's four. Future
mock incidents append. Converts painful history into the reference that stops
its repetition.

## 5. The one open decision — W3 shape

Options for the mock-hass family, in ascending cost:

- **(a) Real `State` objects only** — replace MagicMock *states* with actual
  `homeassistant.core.State` instances (cheap, real class, no loop needed);
  keep the mock-hass shell. Kills the biggest lie (fake state attrs/values)
  for ~an afternoon of mechanical edits. RECOMMENDED as the floor.
- **(b) (a) + `spec_hass()`** — autospec the hass shell too where production
  calls hass methods; more truthful, some friction (async loop attrs, bus/
  services surfaces need stubbing per test).
- **(c) Migrate hot unit files to the real phac `hass` fixture** — maximal
  truth, measurable suite-time cost, and blurs the unit/integration boundary
  the docs deliberately keep.

Recommendation: **(a) now, (b) only for files where a hass METHOD call is what's
under test, never (c)** — the unit tier's speed is a feature.

## 6. Execution fit

Per-artifact loops with a mechanical gate → Sonnet agents, one file per task,
diff_test_equiv as the acceptance test, W0 ratchet as the backstop. Fable/Opus
only for W3 classification judgement and final verification. Waves land
independently; any pause leaves the suite strictly better than before.

## 7. Discovered during planning (Chris's question): 34 undocumented test files

"Did we document every test?" — no: 146/180 test files appear in docs/testing/;
the 34 absent are almost entirely the audit-campaign fix wave (finalize-exactly-
once, cancel chokepoints, watchdog, phased-job wiring, dispatch/zone/pose) plus
tonight's two font tests. The truth pass verified existing claims, not the
docs-vs-tree diff — the coverage-from-scopes blind spot. Fix rides W0 as a
sibling ratchet: enumerate the 34 into their subsystem pages, and add a
completeness check (update_test_docs.py or a standalone gate) that fails on any
test file absent from the docs — so this class dies with the mock class.
"How to run" is fully documented (02-running-tests) — no gap there.

## 8. Chris's actual question: do the docs SAY which tests are magic-mocked? — No.

Verified: the subsystem pages carry coverage maps (module / stmts / % / files /
layer) and behavior prose, but no per-file mock strategy — 19 incidental "mock"
mentions across 18 pages, and the unit-vs-integration Layer column does not
distinguish bare-MagicMock from spec'd from real-fixture, which is the axis that
bites. AMENDMENT to W0: the census and the documentation are ONE derivation —
extend scripts/update_test_docs.py to compute each test file's mock profile from
source (bare MagicMock count / spec_manager? / mock-hass vs real hass fixture /
factory usage) and emit it as a generated "Mocking" column in the subsystem
tables. Generated = never drifts; the same data writes the W0 shrink-only
allowlist. One instrument, two consumers: the ratchet and the reader.
