# 13 — Onboarding — Subsystem Test Map

The onboarding subsystem tracks per-map setup completeness: whether rooms have
been discovered and whether every enabled room has a confirmed floor type. It
feeds the start-status `onboarding_required` gate and the onboarding sensor.
Covered by **11 tests in 1 file** (plus the onboarding sensor in
[18 — platforms](18-platforms.md)).

Source: `custom_components/eufy_vacuum/onboarding/`
Architecture reference: [44 — Onboarding and First Run](../../dev/44-onboarding-and-first-run.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `manager.py` | 100 | 97% | `test_onboarding_manager.py` | integration | **bare x1** |

---

## What's tested

- **State computation** — `get_onboarding_state`: `rooms_discovered`,
  `floor_types_complete`, the `enabled_rooms_needing_floor_type` list, and the
  overall status (`complete` / `floor_type_needed` / `rooms_needed`).
- **Mutations** — `mark_rooms_discovered`, `confirm_floor_type`, `reset_onboarding`.
- **Floor-type re-key after re-segment** (`remap_confirmed_floor_types`, OB-6) —
  carries existing floor-type confirmations onto re-segmented room ids via the
  old→new `id_remap` (and drops the old keys) so a renumbered-but-already-confirmed
  room isn't re-prompted after a reconcile migrate, which would otherwise re-block
  cleaning with `onboarding_required`. No-op when `id_remap` is empty.
- **New-room check** — `check_for_new_rooms` against the adapter-declared room-list
  attribute, per declared SHAPE. Two defects were closed here on 2026-11-08 and
  neither was visible to line coverage:

| id | what it holds |
|---|---|
| `OB-7` | **no brand word stands in for an undeclared attribute** — the read was `or "segments"`, which is Eufy's attribute name in a brand-agnostic method |
| `OB-8` | a `per_map_mapping` brand is no longer answered **False forever** — and the count that answers is the requested map's, not the whole mapping's |
| `OB-9` | DR-ONB-2's refusal does not apply when the source **is** map-keyed |
| `OB-10` | ...but it still fires on the flat branch — `OB-9`'s control |

  **`OB-7`: the fallback was invisible, not merely untested.** `attribute =
  discovery.get("room_list_attribute") or "segments"` reports as COVERED whenever the
  line executes, and the right-hand operand of an `or` is not a branch coverage
  tracks — so with any test declaring the attribute, the fallback never ran and
  nothing said so. The schema documents no default for this key, nothing live
  documented one, and `rooms/room_discovery.py` refuses without it. Unlike
  `room_list_entity`, no sentinel could stand in: nothing can name a device's
  attribute for its adapter. `OB-7`'s state deliberately carries a `segments`
  attribute with enough rooms to answer `True`, which is what makes it able to fail —
  asserting `False` against a state with no `segments` would pass either way.

  **`OB-8` is the larger one.** The method read the attribute as a flat list
  unconditionally. Dreame declares `per_map_mapping` with a `rooms` attribute holding
  `{map_name: [rooms]}`, so `isinstance(segments, list)` failed on a dict that was
  never the wrong shape and every call returned `False` — not a wrong answer about new
  rooms, a permanent "no" for an entire brand. Selection now goes through
  `select_segments_for_map`, the same rule `room_discovery.py` uses for this shape, so
  the two cannot drift.

  **`OB-9`/`OB-10` are one claim in two halves.** DR-ONB-2 refuses when the requested
  map is not the active one, because "the live source cannot be map-scoped". That is
  true of a flat list and false of a map-keyed attribute, so the refusal is now scoped
  to the flat branch. Ablation separates *scoped* from *deleted*: applying the refusal
  on the per-map branch reddens `OB-9` alone; dropping it from the flat branch reddens
  `OB-3b` and `OB-10`.

  Five ablations, five at the predicted verdict. The fifth is declared **SUBSUMED**:
  swapping `select_segments_for_map` for a bare `raw.get(str(map_id))` reddens nothing,
  because the two agree on every input these tests drive — so the RP-019/ID-2 row in
  `OB-8` checks the *shared* rule's guard, not a divergence this method could introduce
  on its own.

> **Gotcha:** `save_managed_rooms` auto-confirms floor types. To exercise the
> incomplete-onboarding path you must clear
> `data["onboarding"][vac][map]["floor_types_confirmed"]` after seeding — see
> the core start-status gate test.

---

## How it's tested

`OnboardingManager(data, hass)` over a plain `data: dict = {}` with a local
`MagicMock` `hass` fixture, with rooms seeded via a local `_seed_rooms(data,
rooms)` helper that writes `data["maps"][vac][map]["rooms"]` directly. (The
shared `manager`/`setup_map` harness exists and is used by other integration
tests, but not this one.)

---

## Known gaps

`manager.py` measures **96.90%** (2 statements, 2 branch arms uncovered of 100
statements / 32 arms), re-measured 2026-11-08.

> ⚠ This section said "98% … one uncovered line … `check_for_new_rooms`, line 288"
> and called that line "defensive-by-design, intentionally uncovered". Every part of
> that had rotted: the percentage, the line number, the count, and the
> characterisation. The non-list guard it named is now the FLAT branch's guard, and
> the shape it was defending against — a `per_map_mapping` dict — was never malformed
> at all; treating it as malformed is what returned `False` forever for Dreame
> (`OB-8`). A guard described as defensive is the one nobody re-examines, which is
> how that survived.

**`check_for_new_rooms` has NO production callers**, and that is the honest frame for
what is left here. It is not in `services.yaml`; the only reference is an uncalled,
`pragma`-annotated delegator on `core/manager.py`. It was fixed rather than deleted
because the mechanism is real and the method is public surface an external
pyscript/AppDaemon caller could hold — but `room_count_at_last_check`, the stored side
of its comparison, is read here and nowhere else, so it is write-only in practice
(audit flag CS-2, alongside CS-1's dead `*_notified` fields). Deleting the method
would strand that key and remove public surface, so whether it goes is **Chris's
call**, not a cleanup; `docs/audit-1-closeout.md` already names the delete option.
