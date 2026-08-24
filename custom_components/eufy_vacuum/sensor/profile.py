"""Available cleaning profiles sensor.

Reports how many cleaning profiles are available for a vacuum, given
its detected capabilities, and exposes profile metadata as attributes.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from ..entity_helpers import build_vacuum_device_info
from ..profiles.room_profiles import get_available_profiles, resolve_profile_catalog


class EufyVacuumProfileSensor(SensorEntity):
    """Sensor reporting the count and details of available cleaning profiles for a vacuum."""

    _attr_has_entity_name = True
    _attr_translation_key = "available_profiles"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        *,
        manager,
        vacuum_entity_id: str,
        capabilities: dict[str, Any],
    ) -> None:
        """Initialize sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._capabilities = capabilities

        self._attr_unique_id = f"{vacuum_entity_id}_available_profiles"
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)

    @property
    def native_value(self) -> str:
        """Return the number of available profiles as a string."""
        profiles = self._get_profiles()
        return str(len(profiles))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return profile names, labels, and capability flags."""
        profiles = self._get_profiles()

        return {
            "profile_count": len(profiles),
            "profiles": profiles,
            "profile_labels": {
                key: value.get("label", key)
                for key, value in profiles.items()
            },
            "supports_mop_features": self._capabilities.get("supports_mop_features", False),
            "supports_water_control": self._capabilities.get("supports_water_control", False),
            # Was an unconditional True. Published alongside an empty `profiles` dict
            # that is the "confident and empty" shape: it tells a reader the absence
            # was EXPLAINED — a capability removed them — so nobody looks further. For
            # 17 days that is exactly what it did, while the real cause was a missing
            # catalog and no capability was involved at all.
            #
            # Scoped to "was there anything here to filter", which is the narrowest
            # true statement. It does NOT claim something was actually removed — a
            # fully-capable vacuum filters nothing and still reports True, which is the
            # flag's original meaning (this list is capability-scoped) and is left
            # alone deliberately.
            "capability_filtered": bool(self._catalog().get("builtins")),
        }

    def _get_profiles(self) -> dict[str, Any]:
        """Return profiles filtered by this vacuum's capabilities.

        ⚠ THE ``catalog=`` ARGUMENT IS LOAD-BEARING AND WAS MISSING FROM 2026-08-07
        TO 2026-08-24. ``ad8c074c`` ("core owns the key space, not a brand's words")
        removed the in-code framework catalog — correctly; core must not own a brand's
        vocabulary — and every other caller was updated to resolve the adapter's
        catalog instead. This one was not: it is the only caller of
        ``get_available_profiles`` in the integration, and ``sensor/profile.py`` was
        not among the files that commit touched.

        Without it, ``get_default_room_profiles(catalog=None)`` yields ``{}``, the
        merge yields only stored profiles, and the built-in whitelist then filters
        those out too — so the sensor published ``profiles: {}`` and
        ``profile_count: 0`` on EVERY vacuum, while still asserting
        ``capability_filtered: True``. Measured on three live vacuums 2026-08-24
        before the fix: alfred/ivy/robin all read ``'0'``.

        WHAT THAT COST IS NOT THE NUMBER. The card's Review tab reads this attribute
        (``src/state/review.js::reviewProfileMatcherCatalog``) and takes each entry's
        ``definition`` from it. With the dict empty, the profile matcher could not
        match anything and rendered "no matches" unconditionally — a live-looking
        control that could never produce a result. It failed as an empty RESULT rather
        than as an error, which is why it went unreported for 17 days.

        ⚠ THE SUITE STAYED GREEN THROUGHOUT, and the reason is worth keeping: `[SE-5]`
        asserted ``"profiles" in attrs`` and ``isinstance(attrs["profiles"], dict)``,
        and its sibling asserted ``int(value) >= 0``. An empty dict and a zero satisfy
        all three. Tests that cannot distinguish "populated" from "empty" are why a
        whole-integration regression survived a green suite; `[SE-13]` now names the
        input that goes red.
        """
        stored_profiles = self._manager.data.get("profiles", {}).get("room_profiles", {})

        return get_available_profiles(
            capabilities=self._capabilities,
            stored_profiles=stored_profiles,
            catalog=self._catalog(),
        )

    def _catalog(self) -> dict[str, Any]:
        """Resolve this vacuum's declared profile catalog.

        ⚠ ``resolve_profile_catalog(None)`` DOES NOT RETURN AN EMPTY DICT — it returns
        a fully SHAPED one whose sections are all empty, so ``bool(catalog)`` is True
        even when the adapter declared nothing. Anything asking "did we actually get a
        catalog" must test a section (``builtins``), never the catalog itself. Checked
        by execution, 2026-08-24, because the truthy-looking empty shape is exactly the
        kind of thing that makes a guard read as working.
        """
        # Deferred import, mirroring every other get_adapter_config call site
        # (queue_engine.py, profiles/manager.py) - keeps the registry out of this
        # module's import cycle.
        from ..adapters.registry import get_adapter_config

        return resolve_profile_catalog(
            (get_adapter_config(self._vacuum_entity_id) or {}).get("room_profiles")
        )
