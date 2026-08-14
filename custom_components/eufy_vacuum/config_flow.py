"""Config flow for Vacuum Agent.

Collects the user's vacuum entity (so the integration knows which device
to manage) plus an optional tested-model string and free-text notes.
The vacuum picker is OPTIONAL during initial setup — leaving it blank
still creates the config entry; the user can fill it in later via
Configure → Options.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_NOTES,
    CONF_TESTED_MODEL,
    CONF_VACUUM_ENTITY_ID,
    DATA_RUNTIME,
    DEFAULT_TITLE,
    DOMAIN,
    ENTITY_OVERRIDES_KEY,
    SUPPORTED_TESTED_MODEL,
)
from .core.capabilities import REASON_RESOLVED

_LOGGER = logging.getLogger(__name__)

#: Prefix for the per-role override fields on the options form. Namespaced so a
#: role can never collide with CONF_NOTES / CONF_VACUUM_ENTITY_ID, and so the
#: submit handler can recognise them without knowing the role vocabulary.
_OVERRIDE_FIELD_PREFIX = "entity_override__"

#: Unfiltered on purpose — see _options_schema.
_ANY_ENTITY_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig())

_VACUUM_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="vacuum"),
)


class EufyVacuumConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup flow — collects vacuum entity, model identifier, and notes."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single step: collect vacuum entity + model + optional notes, then finish."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            # reload_on_update=False: the entry-update reload is handled by the
            # add_update_listener in __init__ (options changes need it). HA 2026.6
            # deprecates having BOTH a reloading config-flow method and an update
            # listener (double-reload/race) — error from 2026.12 — so this flow
            # must NOT also reload. Single-instance anyway, so this just aborts.
            self._abort_if_unique_id_configured(reload_on_update=False)
            # Drop the vacuum field from data if blank — keeps the config-entry
            # data clean and the integration's setup_entry can detect "no
            # vacuum chosen yet" by checking for key absence.
            if not user_input.get(CONF_VACUUM_ENTITY_ID):
                user_input.pop(CONF_VACUUM_ENTITY_ID, None)
            return self.async_create_entry(title=DEFAULT_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional(CONF_VACUUM_ENTITY_ID): _VACUUM_SELECTOR,
                vol.Required(CONF_TESTED_MODEL, default=SUPPORTED_TESTED_MODEL): str,
                vol.Optional(CONF_NOTES, default=(
                    "Open the Vacuum Agent panel in the sidebar to add your vacuum "
                    "and import its current map."
                )): str,
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        # HA >= 2024.12: do NOT pass config_entry to the OptionsFlow constructor.
        # The framework auto-attaches it as a read-only property; assigning it
        # in __init__ raises AttributeError on the property setter.
        return EufyVacuumOptionsFlow()


class EufyVacuumOptionsFlow(OptionsFlow):
    """Options flow for editing the vacuum entity and notes after initial setup.

    The vacuum entity field here is the recovery path for users who installed
    before the field existed in the config flow (or skipped it during initial
    setup). Saving a new value reloads the config entry, which in turn
    registers the panel for the chosen vacuum.

    No __init__: ``self.config_entry`` is set automatically by HA on the
    OptionsFlow base class as of 2024.12. Defining our own __init__ that
    assigns ``self.config_entry`` raises ``AttributeError: property
    'config_entry' of 'EufyVacuumOptionsFlow' object has no setter``.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options edit form and persist changes on submit."""
        previous_vacuum = self.config_entry.options.get(
            CONF_VACUUM_ENTITY_ID,
            self.config_entry.data.get(CONF_VACUUM_ENTITY_ID, ""),
        )

        if user_input is not None:
            notes = user_input.get(CONF_NOTES, "")
            vacuum_entity_id = user_input.get(CONF_VACUUM_ENTITY_ID)
            if vacuum_entity_id:
                # FLOW-3: the form's default was baked in at RENDER time
                # (below) from self.config_entry as it stood THEN. If the
                # device behind that default was deleted while this dialog
                # sat open (__init__._teardown_vacuum /
                # _schedule_clear_configured_vacuum already stripped it from
                # entry.data/options), submitting the untouched default would
                # resurrect it. Re-validate against HA's live state now,
                # rather than trusting what the stale form remembers.
                if self.hass.states.get(vacuum_entity_id) is None:
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._options_schema(
                            current_vacuum=previous_vacuum,
                            current_notes=notes,
                            unresolved_roles=self._resolution_gaps(previous_vacuum),
                            current_overrides=self._current_overrides(previous_vacuum),
                        ),
                        errors={CONF_VACUUM_ENTITY_ID: "vacuum_not_found"},
                    )
                # FLOW-2: switching to a different vacuum here does NOT
                # reconcile the vacuum being replaced -- remove_vacuum_record
                # is never called from this flow (its one caller is the
                # device-delete path). Decision (pre-resolved, not
                # relitigated here): KEEP the old vacuum's stored data by
                # default; just make the change visible in the log so the
                # operator knows which vacuum_entity_id is now orphaned from
                # this entry.
                if previous_vacuum and previous_vacuum != vacuum_entity_id:
                    _LOGGER.warning(
                        "eufy_vacuum: options flow switched the configured "
                        "vacuum from %s to %s — %s's stored data (rooms, "
                        "maps, history, etc.) is KEPT, not removed; delete "
                        "its device from the device page if you want it "
                        "cleared",
                        previous_vacuum, vacuum_entity_id, previous_vacuum,
                    )
                data = {CONF_NOTES: notes, CONF_VACUUM_ENTITY_ID: vacuum_entity_id}
            else:
                data = {CONF_NOTES: notes}

            # live:ENT-7 — persist any entity overrides the user picked.
            #
            # MERGE, NEVER REPLACE, and that is not a style preference. These
            # fields are rendered only for roles that FAILED to resolve, so a
            # role fixed by an override stops being unresolved and its field
            # disappears from the next render. Rebuilding the map from the form
            # alone would then drop that override, the role would break again,
            # the field would come back — an install oscillating between fixed
            # and broken on every visit to this screen.
            #
            # The cost of merging is that this screen cannot CLEAR an override;
            # removal belongs to the panel's Setup tab, which renders the ones
            # already set and can offer an explicit remove.
            target_vacuum = vacuum_entity_id or previous_vacuum
            picked = {
                key[len(_OVERRIDE_FIELD_PREFIX):]: str(value).strip()
                for key, value in user_input.items()
                if key.startswith(_OVERRIDE_FIELD_PREFIX) and str(value or "").strip()
            }
            all_overrides = {
                vac: dict(roles)
                for vac, roles in (
                    self.config_entry.options.get(ENTITY_OVERRIDES_KEY) or {}
                ).items()
                if isinstance(roles, dict)
            }
            if target_vacuum and picked:
                merged = dict(all_overrides.get(target_vacuum) or {})
                merged.update(picked)
                all_overrides[target_vacuum] = merged
                _LOGGER.info(
                    "eufy_vacuum: entity overrides set for %s: %s",
                    target_vacuum, picked,
                )
            if all_overrides:
                data[ENTITY_OVERRIDES_KEY] = all_overrides
            return self.async_create_entry(title="", data=data)

        current_notes = self.config_entry.options.get(
            CONF_NOTES, self.config_entry.data.get(CONF_NOTES, ""),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self._options_schema(
                current_vacuum=previous_vacuum,
                current_notes=current_notes,
                unresolved_roles=self._resolution_gaps(previous_vacuum),
                current_overrides=self._current_overrides(previous_vacuum),
            ),
        )

    @staticmethod
    def _options_schema(
        *,
        current_vacuum: str,
        current_notes: str,
        unresolved_roles: tuple[str, ...] = (),
        current_overrides: dict[str, str] | None = None,
    ) -> vol.Schema:
        """Build the options form schema for a given current vacuum/notes pair.

        live:ENT-7. When roles failed to resolve, one entity picker per role is
        appended. Deliberately NOT a separate menu step: five existing tests
        assert this flow shows a single ``init`` form, and a menu would change
        the shape of an already-working screen to no user benefit.

        When everything resolved, ``unresolved_roles`` is empty and this schema
        is byte-identical to the one that shipped before — a healthy install
        never sees a field it does not need.
        """
        schema: dict[Any, Any] = {}
        if current_vacuum:
            schema[vol.Optional(CONF_VACUUM_ENTITY_ID, default=current_vacuum)] = (
                _VACUUM_SELECTOR
            )
        else:
            schema[vol.Optional(CONF_VACUUM_ENTITY_ID)] = _VACUUM_SELECTOR
        schema[vol.Optional(CONF_NOTES, default=current_notes)] = str

        overrides = current_overrides or {}
        for role in unresolved_roles:
            key = f"{_OVERRIDE_FIELD_PREFIX}{role}"
            existing = overrides.get(role)
            # Unfiltered entity selector on purpose. The whole reason this field
            # exists is that our own naming assumptions missed — including the
            # case of a companion on a DIFFERENT device, which no filter derived
            # from those assumptions would ever offer.
            if existing:
                schema[vol.Optional(key, default=existing)] = _ANY_ENTITY_SELECTOR
            else:
                schema[vol.Optional(key)] = _ANY_ENTITY_SELECTOR
        return vol.Schema(schema)

    def _current_overrides(self, vacuum_entity_id: str) -> dict[str, str]:
        """Overrides already stored for one vacuum, so fields render pre-filled."""
        if not vacuum_entity_id:
            return {}
        stored = self.config_entry.options.get(ENTITY_OVERRIDES_KEY) or {}
        roles = stored.get(vacuum_entity_id) if isinstance(stored, dict) else None
        return dict(roles) if isinstance(roles, dict) else {}

    def _resolution_gaps(self, vacuum_entity_id: str) -> tuple[str, ...]:
        """Roles that did not resolve, or that had competing candidates.

        Best-effort by construction: this screen's PRIMARY job is editing the
        vacuum and notes, and it must still open when the runtime is missing or
        capability detection is unhappy — which is exactly when a user comes
        looking for it.
        """
        if not vacuum_entity_id:
            return ()
        try:
            manager = self.hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
            if manager is None:
                return ()
            caps = manager.get_vacuum_capabilities_snapshot(
                vacuum_entity_id=vacuum_entity_id
            )
            if not isinstance(caps, dict):
                return ()
            reasons = caps.get("entity_resolution_reasons") or {}
            augmentation = caps.get("entity_augmentation") or {}
            ambiguous = augmentation.get("ambiguous") or {}
            gaps = {
                role
                for role, reason in reasons.items()
                if reason != REASON_RESOLVED
            }
            gaps.update(ambiguous)
            return tuple(sorted(gaps))
        except Exception:  # pragma: no cover - defensive; never block the form
            _LOGGER.debug(
                "eufy_vacuum: could not read resolution gaps for %s",
                vacuum_entity_id,
                exc_info=True,
            )
            return ()
