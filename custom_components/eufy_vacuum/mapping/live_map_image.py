"""Brand-declared fallbacks for finding a vacuum's live map image entity.

``core/manager.py::_resolve_live_map_image_entity`` finds the live-map backdrop from
the adapter's ``mapping.live_map_image_entity_pattern`` (``{object_id}`` +
``{map_slug}``). That only works when the provider names the entity after the map.
An adapter can also declare ``mapping.live_map_image_entity_resolver``: the name of
one of the resolvers below, tried when the pattern (and the device-sibling search)
found nothing. Core looks the name up here and never learns what the brand is.

``roborock_map_flag`` — HA core's Roborock integration names each map's ``image``
entity from the map's name AT THE TIME the entity is created, or ``Map <flag>``
when the map has no name yet. Name a map in the Roborock app afterwards and the
entity keeps its old id (``image.<vac>_map_1``) until the integration reloads,
while the selected-map select already reports the new name — so the pattern
derives ``image.<vac>_<new_name>``, which does not exist, and the live map and the
map-overlays sensor go dark. What does not change is the map FLAG: each Roborock
image entity carries ``map_flag``, and the Roborock home trait it reads from maps
each flag to the map's CURRENT name. Matching on that finds the right image no
matter what its entity id says.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


def _image_entity_object(hass: HomeAssistant, entity_id: str) -> Any:
    """The live ``ImageEntity`` object behind ``entity_id``, or None."""
    component = hass.data.get("image")
    get_entity = getattr(component, "get_entity", None)
    if not callable(get_entity):
        return None
    try:
        return get_entity(entity_id)
    except Exception:  # noqa: BLE001 - never break resolution
        return None


def _roborock_map_infos(entity: Any) -> dict | None:
    """The ``{flag: MapInfo}`` dict a Roborock image entity reads its map from."""
    home = getattr(entity, "_home_trait", None)
    if home is None:
        coordinator = getattr(entity, "coordinator", None)
        home = getattr(getattr(coordinator, "properties_api", None), "home", None)
    infos = getattr(home, "home_map_info", None)
    return infos if isinstance(infos, dict) else None


def roborock_map_flag_image(
    hass: HomeAssistant, vacuum_entity_id: str, map_id: str
) -> str | None:
    """The Roborock ``image`` entity whose map is currently named ``map_id``.

    Searches the ``image`` entities on the vacuum's own device. Returns None when
    the device, the entity objects or the map list cannot be read, or when no image
    belongs to a map of that name — the caller then has no live map, as before.
    """
    if not map_id:
        return None
    wanted = str(map_id).strip().casefold()
    ent_reg = er.async_get(hass)
    vac_entry = ent_reg.async_get(vacuum_entity_id)
    if vac_entry is None or vac_entry.device_id is None:
        return None
    for entry in er.async_entries_for_device(ent_reg, vac_entry.device_id):
        if entry.domain != "image" or hass.states.get(entry.entity_id) is None:
            continue
        entity = _image_entity_object(hass, entry.entity_id)
        flag = getattr(entity, "map_flag", None)
        if flag is None:
            continue
        info = (_roborock_map_infos(entity) or {}).get(flag)
        name = getattr(info, "name", None)
        if isinstance(name, str) and name.strip().casefold() == wanted:
            return entry.entity_id
    return None


#: Resolver name (as an adapter declares it) -> resolver.
LIVE_MAP_IMAGE_RESOLVERS: dict[str, Callable[[HomeAssistant, str, str], str | None]] = {
    "roborock_map_flag": roborock_map_flag_image,
}


def resolve_declared_live_map_image(
    hass: HomeAssistant, name: Any, vacuum_entity_id: str, map_id: Any
) -> str | None:
    """Run the resolver an adapter declared by ``name``. None if unknown or failing."""
    resolver = LIVE_MAP_IMAGE_RESOLVERS.get(name) if isinstance(name, str) else None
    if resolver is None or map_id is None:
        return None
    try:
        return resolver(hass, vacuum_entity_id, str(map_id))
    except Exception:  # noqa: BLE001 - a resolver must never break the snapshot
        _LOGGER.debug(
            "live map image resolver %s failed for %s", name, vacuum_entity_id,
            exc_info=True,
        )
        return None
