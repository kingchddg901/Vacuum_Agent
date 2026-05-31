# Subsystem Test Maps

Per-subsystem "what's tested and how" docs. Each maps a subsystem's source
modules to their test files, lists the behaviors under test, explains the setup
patterns specific to that subsystem, and records the deliberate gaps.

| Subsystem | Test map | Status |
|-----------|----------|--------|
| Learning | [learning](learning.md) | Complete — **the template** |
| Mapping | [mapping](mapping.md) | Pure pipeline + helpers covered; orchestrators deferred |
| Jobs | [jobs](jobs.md) | Start-gate + pure tracker helpers covered |
| Battery | [battery](battery.md) | Wear/health math + sensors covered; HA wiring deferred |
| Dock | [dock](dock.md) | Action gating + dispatch + event recording covered |
| Rooms | _todo_ | partial suite exists (`test_room_manager`, `test_rooms_utils`, `test_services_rooms`) |
| Themes | _todo_ | `test_themes_*` |
| Setup | _todo_ | `test_setup_*` |
| Profiles | _todo_ | `test_profiles_room_profiles`, `test_services_*_profiles` |

## Writing a new test map

Copy [learning.md](learning.md) and keep its five sections:

1. **Coverage map** — table of source module → stmts → cov% → test file → layer.
2. **What's tested** — per module, the behaviors (reference target-ID ranges).
3. **How it's tested** — the setup patterns this subsystem uses (which fixtures,
   `tmp_path` vs integration `hass`, seeding helpers).
4. **Known gaps** — what's deliberately untested and why.
5. **Extending** — where new tests for this subsystem should go.

Measure coverage by running **all** of the subsystem's test files together (see
[../02-running-tests.md](../02-running-tests.md#per-file-vs-combined-coverage)),
and link the matching `docs/dev/` architecture file at the top.
