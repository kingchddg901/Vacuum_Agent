"""The orphaned per-map active-job sweep, and the sibling-vacuum trap it must not fall into.

WHY THIS EXISTS. The room-entity sweep in ``sensor/__init__.py`` is scoped PER
MAP: it walks the rooms of each map that exists and drops what that map no longer
wants. Nothing iterates a map that is GONE, so a deleted map's active-job sensor
stays in the registry forever, permanently ``unavailable``. The guard is complete
inside its window and structurally blind just past it.

Found 2026-08-15 with two orphans on the maintainer's box (maps ``6`` and ``99``,
of five active-job entities on one vacuum), and independently reported against the
2.1.0 beta by the #49 reporter -- "2nd is 'no longer reporting' - so not sure
where/how that's appeared".

WHY THE TESTS ARE SHAPED LIKE THIS. This sweep DELETES REGISTRY ENTRIES, and the
naive version of it has already caused real damage in this codebase: RP-009/RF-04
records a prefix scan in setup/delete that was PROVEN to registry-delete every
entity of a SIBLING vacuum whose entity_id was the scanned prefix plus a suffix --
``vacuum.alfred`` deleting map "2" swept ``vacuum.alfred_2``'s entities
(DR-SETUP-1). So the negative cases below matter more than the positive one: most
of this file is about what must SURVIVE.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.entity_helpers import (
    active_job_unique_id,
    orphaned_active_job_unique_ids,
)


def test_orphan_of_a_deleted_map_is_selected():
    """[OAJ-1] The whole point: a map that is gone leaves a removable sensor."""
    live_pairs = {("vacuum.alfred", "11"), ("vacuum.alfred", "7")}
    known = [
        active_job_unique_id(vacuum_entity_id="vacuum.alfred", map_id="11"),
        active_job_unique_id(vacuum_entity_id="vacuum.alfred", map_id="7"),
        active_job_unique_id(vacuum_entity_id="vacuum.alfred", map_id="6"),
    ]
    orphans = orphaned_active_job_unique_ids(
        known_unique_ids=known,
        managed_vacuum_ids=["vacuum.alfred"],
        live_pairs=live_pairs,
    )
    assert orphans == {"vacuum_alfred_active_job_6"}


def test_a_sibling_vacuums_entities_are_never_selected():
    """[OAJ-2] DR-SETUP-1, the exact trap: `vacuum.alfred` must not sweep `vacuum.alfred_2`.

    `vacuum.alfred`'s prefix is `vacuum_alfred_active_job_`. `vacuum.alfred_2`'s
    ids begin `vacuum_alfred_2_active_job_` -- which does NOT start with that
    prefix, and the assertion is here so a future "simplification" to a looser
    match (a prefix of `vacuum_alfred`, say) fails loudly rather than deleting a
    second vacuum's sensors.
    """
    sibling = active_job_unique_id(vacuum_entity_id="vacuum.alfred_2", map_id="3")
    orphans = orphaned_active_job_unique_ids(
        known_unique_ids=[sibling],
        managed_vacuum_ids=["vacuum.alfred"],   # the sibling is NOT managed here
        live_pairs={("vacuum.alfred", "11")},
    )
    assert orphans == set(), (
        f"selected a sibling vacuum's entity for deletion: {orphans} — this is "
        "DR-SETUP-1 recurring"
    )


def test_a_vacuum_named_active_job_does_not_swallow_its_own_ids():
    """[OAJ-3] The pathological name that defeats a bare prefix test.

    `vacuum.alfred_active_job` builds ids starting
    `vacuum_alfred_active_job_active_job_` — which DOES start with
    `vacuum.alfred`'s prefix. The remainder check is the only thing separating
    them, so it gets its own test rather than living as a comment.
    """
    weird = active_job_unique_id(
        vacuum_entity_id="vacuum.alfred_active_job", map_id="5"
    )
    assert weird.startswith("vacuum_alfred_active_job_"), (
        "premise of this test has changed — the id no longer collides, so the "
        "remainder guard may be testing nothing"
    )
    orphans = orphaned_active_job_unique_ids(
        known_unique_ids=[weird],
        managed_vacuum_ids=["vacuum.alfred"],
        live_pairs={("vacuum.alfred", "11")},
    )
    assert orphans == set()


def test_non_active_job_entities_are_never_selected():
    """[OAJ-4] Room switches, numbers and per-vacuum sensors are out of scope."""
    known = [
        "vacuum_alfred_kitchen_switch",
        "vacuum_alfred_map11_room3_order",
        "vacuum_alfred_theme_state",
        "vacuum_alfred_battery_health",
    ]
    orphans = orphaned_active_job_unique_ids(
        known_unique_ids=known,
        managed_vacuum_ids=["vacuum.alfred"],
        live_pairs={("vacuum.alfred", "11")},
    )
    assert orphans == set()


def test_map_ids_containing_spaces_survive():
    """[OAJ-5] Real map ids are not always numeric — Ivy's is `Main floor`.

    A tightening that assumed a numeric map id would delete a live sensor on the
    maintainer's own box.
    """
    live = active_job_unique_id(vacuum_entity_id="vacuum.ivy", map_id="Main floor")
    orphans = orphaned_active_job_unique_ids(
        known_unique_ids=[live],
        managed_vacuum_ids=["vacuum.ivy"],
        live_pairs={("vacuum.ivy", "Main floor")},
    )
    assert orphans == set()


def test_nothing_is_selected_when_every_map_is_live():
    """[OAJ-6] The no-op case — a healthy install loses nothing."""
    pairs = {("vacuum.alfred", "11"), ("vacuum.alfred", "7"), ("vacuum.ivy", "Main floor")}
    known = [active_job_unique_id(vacuum_entity_id=v, map_id=m) for v, m in pairs]
    orphans = orphaned_active_job_unique_ids(
        known_unique_ids=known,
        managed_vacuum_ids=["vacuum.alfred", "vacuum.ivy"],
        live_pairs=pairs,
    )
    assert orphans == set()


def test_an_unmanaged_vacuums_orphan_is_left_alone():
    """[OAJ-7] Only a MANAGED vacuum's entities are ever considered.

    A vacuum removed from management still owns its registry entries until the
    per-vacuum teardown handles them; this sweep must not do that job by accident,
    because it cannot tell "removed from management" from "temporarily absent".
    """
    other = active_job_unique_id(vacuum_entity_id="vacuum.ghost", map_id="4")
    orphans = orphaned_active_job_unique_ids(
        known_unique_ids=[other],
        managed_vacuum_ids=["vacuum.alfred"],
        live_pairs={("vacuum.alfred", "11")},
    )
    assert orphans == set()


def test_the_live_box_case_reproduces_exactly():
    """[OAJ-8] The measured real-world input, pinned.

    Five active-job entities on `vacuum.alfred` (maps 6, 11, 7, 12, 99) plus Ivy's,
    against live maps 11/7/12 and `Main floor`. Dry-run against the real registry
    on 2026-08-15 selected exactly two of 161 entities; this pins that result so a
    later change cannot quietly widen it.
    """
    live_pairs = {
        ("vacuum.alfred", "11"), ("vacuum.alfred", "7"), ("vacuum.alfred", "12"),
        ("vacuum.ivy", "Main floor"),
    }
    known = [
        "vacuum_alfred_active_job_6",
        "vacuum_alfred_active_job_11",
        "vacuum_alfred_active_job_7",
        "vacuum_alfred_active_job_12",
        "vacuum_alfred_active_job_99",
        "vacuum_ivy_active_job_Main floor",
    ]
    orphans = orphaned_active_job_unique_ids(
        known_unique_ids=known,
        managed_vacuum_ids=["vacuum.alfred", "vacuum.ivy"],
        live_pairs=live_pairs,
    )
    assert orphans == {
        "vacuum_alfred_active_job_6",
        "vacuum_alfred_active_job_99",
    }
