

# ---------------------------------------------------------------------------
# [ER-COLLIDE] live:ENT-4 — the second copy of the exclusivity guard
# ---------------------------------------------------------------------------

async def test_a_lifetime_total_is_never_rescued_into_a_per_run_role(hass):
    """[ER-COLLIDE] Found LIVE on the maintainer's own install.

    `_cleaning_area` also matches `..._total_cleaning_area`, and both roles are
    declared in the same `entities` map. The ambiguity check cannot catch it:
    that check excludes the declared id from its own candidate list, so exactly
    ONE sibling matches and one match looks decisive.

    Real damage, not theoretical — `cleaning_area` was bound to a sensor reading
    17,975 ft² while the true per-run sensor read 0.0, feeding a lifetime counter
    into the learning store, counter segmentation and battery metrics.

    The guard existed in augment_candidates_from_device and not here. A fix
    applied to one copy of a predicate and not its twin.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.entity_resolve import (
        resolve_declared_entities,
    )

    entry = MockConfigEntry(domain="robovac_mqtt", entry_id="ercollide")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    device_id = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("robovac_mqtt", "ercollide")},
    ).id
    registry.async_get_or_create(
        "vacuum", "robovac_mqtt", "uid_vac",
        suggested_object_id="alfred", device_id=device_id, config_entry=entry,
    )
    # Only the AREA-PREFIXED lifetime total exists; the per-run sensor has no
    # state yet, which is the startup window this rescue runs in.
    registry.async_get_or_create(
        "sensor", "robovac_mqtt", "uid_total",
        suggested_object_id="dining_room_alfred_total_cleaning_area",
        device_id=device_id, config_entry=entry,
    )

    entities = {
        "cleaning_area": "sensor.alfred_cleaning_area",
        "total_cleaning_area": "sensor.alfred_total_cleaning_area",
    }
    resolved, report = resolve_declared_entities(hass, "vacuum.alfred", dict(entities))

    assert resolved["cleaning_area"] == "sensor.alfred_cleaning_area", (
        "the per-run role was rescued to the LIFETIME TOTAL — a ~4000x wrong "
        "number fed into learning, segmentation and battery metrics, silently"
    )
    assert "cleaning_area" not in report
    assert resolved["total_cleaning_area"] == (
        "sensor.dining_room_alfred_total_cleaning_area"
    ), "the total's OWN role must still be rescued; this guard must not over-reach"
