"""Tests for the EufyVacuumConfigFlow setup flow and EufyVacuumOptionsFlow.

Coverage targets
----------------
Setup flow:
  [CF-1]  Showing the form returns the user step.
  [CF-2]  Valid input with all fields → entry created, vacuum_entity_id in data.
  [CF-3]  Valid input with vacuum field left blank → entry created,
          vacuum_entity_id absent from data.
  [CF-4]  Duplicate setup is refused at flow START (manifest single_config_entry),
          before any form is rendered.
  [CF-5]  The flow's own unique_id guard still refuses a duplicate on the paths
          the manifest gate does not cover.

Options flow:
  [OF-1]  Opening options shows the form pre-populated from existing data.
  [OF-2]  Submitting new vacuum_entity_id → stored in options.
  [OF-3]  Clearing vacuum_entity_id (empty string) → key absent from options.
  [OF-4]  Opening options when vacuum was set via initial data (not options).
  [OF-5]  FLOW-3: submitting a vacuum_entity_id that no longer exists in HA's
          state machine (e.g. a stale form outliving a device delete) is
          refused with a form + vacuum_not_found error, not written to options.
  [OF-6]  FLOW-2: switching to a different (existing) vacuum logs a warning
          naming the old vacuum_entity_id, and does not touch its stored data.
  [OF-7]  The DEFERRED INSTALL through this screen: a blank-vacuum entry gets a
          picker with NO default, and a notes-only submit saves no vacuum key.
  [OF-8]  live:ENT-7: a role whose reason is not `resolved`, and a role recorded
          as CONTESTED under `entity_augmentation["ambiguous"]`, each get an
          override picker — and a RESOLVED role does not.
  [OF-9]  A stored override comes back as that picker's default.
  [OF-10] Saving one override MERGES with another role's stored override rather
          than replacing the vacuum's whole role map.
  [OF-11] A blank or padded override is refused by the entity selector, before
          `async_step_init` is entered at all.
  [OF-12] A missing runtime still opens the form, and does so WITHOUT taking the
          exception path.
  [OF-13] The positive control for [OF-12]: a runtime that cannot answer DOES log
          the record, so [OF-12]'s absence assertion is not an empty-set pass.

Every one of [OF-7]..[OF-13] has a named production edit that reddens it and
nothing else; the nine of them were run as ablations, each reddening exactly one
test. Two of those edits are worth knowing about because they look harmless:
`merged = {}` (a replace) and `_ANY_ENTITY_SELECTOR = str`.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eufy_vacuum import config_flow as config_flow_module
from custom_components.eufy_vacuum.const import (
    CONF_NOTES,
    CONF_TESTED_MODEL,
    CONF_VACUUM_ENTITY_ID,
    DATA_RUNTIME,
    DOMAIN,
    ENTITY_OVERRIDES_KEY,
)
from custom_components.eufy_vacuum.core.capabilities import (
    REASON_ABSENT,
    REASON_OVERRIDE_UNRESOLVED,
    REASON_RESOLVED,
)
from custom_components.eufy_vacuum.adapters.eufy.const import SUPPORTED_TESTED_MODEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _start_flow(hass: HomeAssistant):
    """Initialise a fresh setup flow and return the first result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    return result


# ---------------------------------------------------------------------------
# Setup flow — [CF-1] through [CF-4]
# ---------------------------------------------------------------------------

async def test_setup_flow_shows_form(hass: HomeAssistant):
    """[CF-1] Initiating the flow without data shows the user step form."""
    result = await _start_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result.get("errors")  # None or {} both acceptable


async def test_setup_flow_creates_entry_with_vacuum(hass: HomeAssistant):
    """[CF-2] Submitting all fields creates an entry with vacuum_entity_id in data."""
    await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        (await _start_flow(hass))["flow_id"],
        user_input={
            CONF_VACUUM_ENTITY_ID: "vacuum.alfred",
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "My robot",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vacuum Agent"
    data = result["data"]
    assert data[CONF_VACUUM_ENTITY_ID] == "vacuum.alfred"
    assert data[CONF_TESTED_MODEL] == SUPPORTED_TESTED_MODEL
    assert data[CONF_NOTES] == "My robot"


async def test_setup_flow_creates_entry_without_vacuum(hass: HomeAssistant):
    """[CF-3] Leaving vacuum blank creates an entry; vacuum_entity_id absent from data."""
    # Omit CONF_VACUUM_ENTITY_ID entirely — the field is Optional in the schema.
    # Passing "" would fail EntitySelector validation before our stripping logic runs.
    result = await hass.config_entries.flow.async_configure(
        (await _start_flow(hass))["flow_id"],
        user_input={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert CONF_VACUUM_ENTITY_ID not in result["data"]


async def test_setup_flow_aborts_before_showing_the_form(hass: HomeAssistant):
    """[CF-4] C43: a second setup attempt is refused at async_init, not after the form.

    The refusal itself was never in doubt — async_step_user has always called
    _abort_if_unique_id_configured. But that guard lives INSIDE the submit branch,
    so it can only fire once the user has picked a vacuum, typed a model and
    submitted: the whole form filled in for a flow that was doomed before it
    opened. manifest.json declaring ``single_config_entry`` is what moves the
    refusal to flow start (HA aborts in ConfigEntriesFlowManager.async_init with
    ``single_instance_allowed``).

    Asserting FlowResultType.ABORT alone would pass for either mechanism — the
    step_id assertion is the one that bites, because without the manifest key
    this call returns the ``user`` FORM.
    """
    # First install, through the real flow.
    result = await hass.config_entries.flow.async_configure(
        (await _start_flow(hass))["flow_id"],
        user_input={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Second attempt: merely STARTING the flow must already be the end of it.
    result2 = await _start_flow(hass)
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "single_instance_allowed"
    assert result2.get("step_id") is None  # no form was ever rendered
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_setup_flow_unique_id_guard_still_refuses_duplicate(hass: HomeAssistant):
    """[CF-5] The in-flow unique_id guard survives as defence in depth.

    The manifest gate covers the ordinary user path only. It does not run for
    SOURCE_IGNORE/reauth/reconfigure, and it cannot see an entry that appears
    while a flow is already open — the case reproduced here: the flow is started
    while nothing is configured, the entry arrives (added directly, not via a
    flow, so HA does not cancel flows in progress), and only then is the form
    submitted. Ablated (guard removed on the grounds that the manifest now
    covers it) this goes red while CF-4 stays green — the flow runs to
    completion and is refused later, by HA's finish-flow gate, as the generic
    ``single_instance_allowed`` instead of this integration's own
    ``already_configured``. No duplicate entry either way; what the guard buys
    is the specific reason and the refusal happening in our step.
    """
    flow = await _start_flow(hass)
    assert flow["type"] == FlowResultType.FORM  # nothing configured yet

    MockConfigEntry(domain=DOMAIN, data={CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL},
                    unique_id=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "",
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Options flow — [OF-1] through [OF-4]
# ---------------------------------------------------------------------------

async def test_options_flow_shows_prepopulated_form(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-1] Opening options shows form pre-populated from the existing entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert CONF_VACUUM_ENTITY_ID in schema_keys
    assert CONF_NOTES in schema_keys


async def test_options_flow_updates_vacuum_entity(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-2] Submitting a new vacuum_entity_id stores it in options."""
    mock_config_entry.add_to_hass(hass)
    # FLOW-3: submit now re-validates the vacuum against HA's live state.
    hass.states.async_set("vacuum.new_robot", "docked")

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init["flow_id"],
        user_input={
            CONF_VACUUM_ENTITY_ID: "vacuum.new_robot",
            CONF_NOTES: "Updated",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VACUUM_ENTITY_ID] == "vacuum.new_robot"
    assert result["data"][CONF_NOTES] == "Updated"


async def test_options_flow_vacuum_default_preserved(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-3] Once a vacuum_entity_id is set, omitting the field keeps it.

    The options form uses `vol.Optional(key, default=current_vacuum)` when a
    vacuum is already configured, so voluptuous fills the default back in when
    the field is absent from user_input.  This is intentional — the options
    flow has no "clear" affordance for a vacuum that is already set.
    """
    mock_config_entry.add_to_hass(hass)
    # FLOW-3: the schema default ("vacuum.alfred") is what actually gets
    # submitted (voluptuous fills it in before async_step_init runs), so it
    # must exist in HA's state for the re-validation to accept it.
    hass.states.async_set("vacuum.alfred", "docked")

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init["flow_id"],
        user_input={
            CONF_NOTES: "no vacuum key submitted",
            # CONF_VACUUM_ENTITY_ID intentionally omitted
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Default kicks in — original vacuum entity is preserved, not cleared.
    assert result["data"][CONF_VACUUM_ENTITY_ID] == "vacuum.alfred"


async def test_options_flow_refuses_deleted_vacuum(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-5] FLOW-3: submitting a vacuum_entity_id that no longer exists in
    HA's state machine (e.g. a stale dialog outliving a device delete) is
    refused with a form + vacuum_not_found error, not written to options."""
    mock_config_entry.add_to_hass(hass)
    # Deliberately NOT registering vacuum.gone in hass.states.

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init["flow_id"],
        user_input={
            CONF_VACUUM_ENTITY_ID: "vacuum.gone",
            CONF_NOTES: "should not save",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {CONF_VACUUM_ENTITY_ID: "vacuum_not_found"}
    # The entry itself was never updated.
    assert mock_config_entry.options.get(CONF_VACUUM_ENTITY_ID) is None


async def test_options_flow_switch_logs_warning_for_old_vacuum(
    hass: HomeAssistant, mock_config_entry, caplog
):
    """[OF-6] FLOW-2: switching to a different (existing) vacuum logs a
    warning naming the OLD vacuum_entity_id — its stored data is deliberately
    KEPT, not auto-removed, since this flow never calls remove_vacuum_record."""
    mock_config_entry.add_to_hass(hass)
    hass.states.async_set("vacuum.alfred", "docked")
    hass.states.async_set("vacuum.new_robot", "docked")

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with caplog.at_level("WARNING"):
        result = await hass.config_entries.options.async_configure(
            init["flow_id"],
            user_input={
                CONF_VACUUM_ENTITY_ID: "vacuum.new_robot",
                CONF_NOTES: "switched",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VACUUM_ENTITY_ID] == "vacuum.new_robot"
    assert any(
        "vacuum.alfred" in rec.message and "vacuum.new_robot" in rec.message
        for rec in caplog.records
    )


async def test_options_flow_no_warning_when_vacuum_unchanged(
    hass: HomeAssistant, mock_config_entry, caplog
):
    """[OF-6] Control: resubmitting the SAME vacuum_entity_id does not log the
    switch warning — it only fires on an actual change."""
    mock_config_entry.add_to_hass(hass)
    hass.states.async_set("vacuum.alfred", "docked")

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with caplog.at_level("WARNING"):
        result = await hass.config_entries.options.async_configure(
            init["flow_id"],
            user_input={
                CONF_VACUUM_ENTITY_ID: "vacuum.alfred",
                CONF_NOTES: "unchanged",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert not any("stored data" in rec.message for rec in caplog.records)


async def test_options_flow_reads_vacuum_from_data(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-4] vacuum_entity_id set in initial data (not options) appears in the form."""
    # mock_config_entry has vacuum_entity_id in .data, not .options
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    # The form schema should include a default for CONF_VACUUM_ENTITY_ID
    # drawn from config_entry.data — verified by inspecting schema defaults.
    defaults = {
        str(k): k.default() if callable(k.default) else None
        for k in result["data_schema"].schema
        if hasattr(k, "default")
    }
    assert defaults.get(CONF_VACUUM_ENTITY_ID) == "vacuum.alfred"


# ---------------------------------------------------------------------------
# Options flow — [OF-7] through [OF-12]
#
# THE DEFERRED INSTALL AND THE ENTITY-OVERRIDE PICKERS, neither of which had any
# test. `mock_entry_no_vacuum` already existed in tests/conftest.py and was used
# only by test_init_setup.py, so the options flow -- which docs/dev/44 § 1 names as
# the RECOVERY PATH for exactly that install -- was never opened on one.
#
# A note on what is asserted. `vol.Optional(key)` with no default and
# `vol.Optional(key, default=None)` both read as `None` through the
# `k.default() if callable(...)` idiom used above, so these tests compare against
# `vol.UNDEFINED` itself. The weaker form would pass if a default were introduced,
# which is the one change it exists to catch.
# ---------------------------------------------------------------------------

def _schema_markers(result) -> dict[str, Any]:
    """{field name: the voluptuous Marker}, so a default can be told from none."""
    return {str(k): k for k in result["data_schema"].schema}


def _override_field(role: str) -> str:
    """The options form's field name for one role's entity override.

    Derived from the shipped prefix rather than hand-written: a test that spells
    `entity_override__x` itself keeps passing when the prefix moves, and the field
    it then asserts on is one the form no longer renders.
    """
    return f"{config_flow_module._OVERRIDE_FIELD_PREFIX}{role}"


def _seed_capabilities(manager, vacuum_entity_id: str, snapshot: dict[str, Any]) -> None:
    """Store a capabilities snapshot the way detection would have left it.

    NO MOCK OF THE PRODUCER. `EufyVacuumManager.get_vacuum_capabilities_snapshot`
    is documented as reading `self.data["capabilities"]` as-is and never running
    detection, so seeding the store exercises the real accessor rather than a fake
    that agrees with my reading of it. The vocabulary below is the real one:
    `entity_resolution_reasons` and `entity_augmentation` are built in
    `core/capabilities.py` (the dict returned alongside anchor `CNAYBZY3`), the
    reason words come from its `REASON_*` constants, and `ambiguous` is a
    `{role: [competing entity ids]}` dict set only when non-empty.
    """
    manager.data.setdefault("capabilities", {})[vacuum_entity_id] = snapshot


@pytest.mark.covers("custom_components/eufy_vacuum/config_flow.py::EufyVacuumOptionsFlow._options_schema")
@pytest.mark.covers("custom_components/eufy_vacuum/config_flow.py::EufyVacuumOptionsFlow._current_overrides")
async def test_of7_deferred_install_can_save_notes_without_choosing_a_vacuum(
    hass: HomeAssistant, mock_entry_no_vacuum
):
    """[OF-7] The install that skipped the vacuum picker, through the options form.

    `docs/dev/44-onboarding-and-first-run.md` § 1 states the whole point of
    accepting a blank vacuum: it "converts a hard failure into a deferred step",
    and this flow is where the step is deferred TO. That path had no test, and two
    arms of the code exist only for it -- the schema arm that registers the vacuum
    field with NO default, and the submit arm that builds `data` with no vacuum key.

    THE TWO ASSERTIONS ARE ONE CLAIM. On a configured entry the field carries
    `default=current_vacuum`, so voluptuous fills the default back in whenever the
    field is omitted -- that is [OF-3]'s subject, and it is why the no-vacuum submit
    arm is unreachable on a configured entry. Give the blank entry a default too and
    the submit would carry a vacuum id the user never chose, so the schema check and
    the saved-data check are the same guarantee read at both ends. Measured: a
    `default=""` there does not merely add a key, it makes the screen UNSUBMITTABLE
    -- voluptuous applies the default and then runs the validator, which refuses
    `""` as an entity id, so the recovery form raises for exactly the user it exists
    for.

    LIMIT, STATED BECAUSE IT WAS MEASURED. This pins the arm against ADDING the
    vacuum key, not against over-copying: rewrite it as `data = dict(user_input)`
    and all of these tests still pass. That substitution is behaviourally
    indistinguishable on every reachable input rather than merely unnoticed --
    voluptuous rejects extra keys, and a blank-vacuum entry renders no override
    fields (`_resolution_gaps` returns `()` on a falsy vacuum), so `user_input` on
    this path can only ever be `{CONF_NOTES: ...}`. Worth knowing before someone
    "simplifies" the arm on a path where that stops being true.
    """
    mock_entry_no_vacuum.add_to_hass(hass)

    init = await hass.config_entries.options.async_init(mock_entry_no_vacuum.entry_id)
    assert init["type"] == FlowResultType.FORM
    markers = _schema_markers(init)
    assert CONF_VACUUM_ENTITY_ID in markers, (
        "the picker must still be offered -- it is the recovery affordance"
    )
    assert markers[CONF_VACUUM_ENTITY_ID].default is vol.UNDEFINED, (
        "a blank entry must get NO default, or voluptuous submits a vacuum the "
        "user never picked"
    )

    result = await hass.config_entries.options.async_configure(
        init["flow_id"], user_input={CONF_NOTES: "still deciding"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_NOTES: "still deciding"}
    assert CONF_VACUUM_ENTITY_ID not in result["data"]


@pytest.mark.covers("custom_components/eufy_vacuum/config_flow.py::EufyVacuumOptionsFlow._options_schema")
async def test_of8_only_unresolved_and_ambiguous_roles_get_an_override_picker(
    hass: HomeAssistant, mock_config_entry, manager
):
    """[OF-8] live:ENT-7 — which roles the form offers to fix, and which it does not.

    THE CONTROL IS THE POINT. A gap computation that returned every role it saw
    would pass any test that merely counts pickers, so this seeds one role that
    RESOLVED cleanly and asserts it gets no field. Without that row the test would
    hold just as well if `_resolution_gaps` ignored the reason entirely.

    Both sources of a gap are seeded, because they arrive by different routes and
    `core/capabilities.py` says so at the site carrying anchor `CNAYBZY3`: a role
    whose reason is not `resolved`, and a role recorded in
    `entity_augmentation["ambiguous"]` because companions CONTESTED it and the
    resolver declined to guess. `gaps.update(ambiguous)` reads a dict's keys, so an
    ambiguous role contributes its name and not its candidate list.
    """
    mock_config_entry.add_to_hass(hass)
    _seed_capabilities(manager, "vacuum.alfred", {
        "entity_resolution_reasons": {
            "task_status": REASON_RESOLVED,
            "water_level": REASON_ABSENT,
        },
        "entity_augmentation": {
            "ambiguous": {
                "cleaning_area": [
                    "sensor.alfred_area_a", "sensor.alfred_area_b",
                ],
            },
        },
    })

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert init["type"] == FlowResultType.FORM
    markers = _schema_markers(init)
    assert _override_field("water_level") in markers, "an absent role must be fixable"
    assert _override_field("cleaning_area") in markers, (
        "a CONTESTED role must be fixable -- declining to guess is the reason the "
        "picker exists"
    )
    assert _override_field("task_status") not in markers, (
        "a resolved role must NOT be offered a picker; this is the row that makes "
        "the other two mean something"
    )
    # The ambiguous role's candidates are not themselves roles.
    assert _override_field("sensor.alfred_area_a") not in markers


@pytest.mark.covers("custom_components/eufy_vacuum/config_flow.py::EufyVacuumOptionsFlow._options_schema")
@pytest.mark.covers("custom_components/eufy_vacuum/config_flow.py::EufyVacuumOptionsFlow._current_overrides")
async def test_of9_a_stored_override_prefills_its_picker(
    hass: HomeAssistant, mock_config_entry, manager
):
    """[OF-9] The `if existing:` arm — a previous choice comes back as the default.

    Without it the user re-picks from scratch every time the screen opens, and
    because the field is rendered only while the role is still unresolved, that is
    exactly when they are most likely to be mid-diagnosis. Asserted against
    `vol.UNDEFINED` rather than "is not None", since the no-default arm yields a
    marker whose default is that sentinel.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            ENTITY_OVERRIDES_KEY: {
                "vacuum.alfred": {"water_level": "number.alfred_water"},
            },
        },
    )
    _seed_capabilities(manager, "vacuum.alfred", {
        "entity_resolution_reasons": {"water_level": REASON_OVERRIDE_UNRESOLVED},
    })

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    markers = _schema_markers(init)
    field = _override_field("water_level")
    assert field in markers
    default = markers[field].default
    assert default is not vol.UNDEFINED, "a stored override must come back pre-filled"
    assert default() == "number.alfred_water"


async def test_of10_submitting_one_override_keeps_another_roles_stored_override(
    hass: HomeAssistant, mock_config_entry, manager
):
    """[OF-10] MERGE, NEVER REPLACE — and only a pre-seeded store can tell them apart.

    The shipped comment describes the failure a replace would cause, and it is not
    cosmetic: these fields are rendered ONLY for roles that failed to resolve, so a
    role fixed by an override stops being unresolved and its field disappears from
    the next render. Rebuild the map from the form alone and that override is
    dropped, the role breaks again, the field returns -- an install oscillating
    between fixed and broken on every visit.

    A test that submits one override into an EMPTY store cannot see any of that: a
    replace and a merge produce the identical result. So `dock_status` is stored
    first and deliberately left OUT of both the gap set and the submitted form, the
    way a role already fixed by an override behaves. If the merge became a replace,
    `dock_status` vanishes from the saved options and this goes red.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            ENTITY_OVERRIDES_KEY: {
                "vacuum.alfred": {"dock_status": "binary_sensor.alfred_docked"},
            },
        },
    )
    # Only water_level is unresolved now -- dock_status was fixed by the override
    # above, so the form does not render a field for it.
    _seed_capabilities(manager, "vacuum.alfred", {
        "entity_resolution_reasons": {"water_level": REASON_ABSENT},
    })
    hass.states.async_set("vacuum.alfred", "docked")

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert _override_field("dock_status") not in _schema_markers(init), (
        "precondition: the already-fixed role must be absent from the form, which "
        "is what makes a replace lose it"
    )

    result = await hass.config_entries.options.async_configure(
        init["flow_id"],
        user_input={
            CONF_VACUUM_ENTITY_ID: "vacuum.alfred",
            CONF_NOTES: "fixed water level",
            _override_field("water_level"): "number.alfred_water",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    saved = result["data"][ENTITY_OVERRIDES_KEY]["vacuum.alfred"]
    assert saved == {
        "dock_status": "binary_sensor.alfred_docked",
        "water_level": "number.alfred_water",
    }


@pytest.mark.parametrize("blank", ["   ", "", "  number.alfred_water  "])
async def test_of11_a_blank_override_is_refused_by_the_form_itself(
    hass: HomeAssistant, mock_config_entry, manager, blank
):
    """[OF-11] A blank or padded override never reaches the handler at all.

    An override is tried FIRST when a role resolves, so storing `""` would make a
    role that merely had no user choice start reporting `override_unresolved`
    instead of `absent` -- a different diagnosis on the one screen built to be
    trusted. What stops it is not the submit handler but the ENTITY SELECTOR: it
    runs `cv.entity_id_or_uuid`, so HA refuses the whole submission before
    `async_step_init` is entered.

    ⚠ I WROTE THIS TEST THE OTHER WAY FIRST AND IT COULD NOT PASS, which is how the
    finding below turned up. The handler filters picks on
    `str(value or "").strip()`, and I took that to mean a blank arrives and is
    dropped. It cannot arrive. Measured against the real selector, it accepts a
    clean entity id or an omitted field and rejects every one of: whitespace, `""`,
    `None`, a PADDED id, and a domain-less name. So both halves of that filter are
    inert through this form -- the blank test can never be true, and `.strip()` has
    nothing to strip because a padded id is refused upstream. That is the same
    inert-branch shape, for the same reason, that ledger D25 records against
    `EufyVacuumConfigFlow.async_step_user` one layer up in this very file; the
    classification is now recorded at the site.

    So the assertion is the guarantee that actually holds, and it bites: replace
    `_ANY_ENTITY_SELECTOR` with a plain `str` and every row here stops raising and
    returns CREATE_ENTRY instead. The padded row is in because it is the only one
    that would otherwise look like a job for `.strip()`.
    """
    mock_config_entry.add_to_hass(hass)
    _seed_capabilities(manager, "vacuum.alfred", {
        "entity_resolution_reasons": {"water_level": REASON_ABSENT},
    })
    hass.states.async_set("vacuum.alfred", "docked")

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            init["flow_id"],
            user_input={
                CONF_VACUUM_ENTITY_ID: "vacuum.alfred",
                CONF_NOTES: "nothing picked",
                _override_field("water_level"): blank,
            },
        )

    # NO "and nothing was written" ROW HERE, deliberately. The obvious one --
    # `assert ENTITY_OVERRIDES_KEY not in mock_config_entry.options` -- was in this
    # test and is removed: `mock_config_entry` ships `options={}` and nothing here
    # writes to it, so the assertion is already true before the flow starts and
    # stays true whatever the submit does. Delete the `pytest.raises` block above
    # and it would STILL pass. A stronger version is not available either: the raise
    # means `async_step_init` never runs, so "the store is untouched" is guaranteed
    # by the raise rather than asserted alongside it. Its red set is EMPTY, so it is
    # a preference, not a claim -- and a tautology is the one thing this file cannot
    # afford to carry, given what it is for. [OF-10] is where a real
    # nothing-was-clobbered assertion lives, because there the store is pre-seeded
    # with a role the submit does not carry.


async def test_of12_a_missing_runtime_is_expected_not_an_error(
    hass: HomeAssistant, mock_config_entry, caplog
):
    """[OF-12] The form opens before the runtime exists, WITHOUT taking the except.

    `_resolution_gaps` documents this as best-effort because the screen's primary
    job is editing the vacuum and notes, and it "must still open when the runtime is
    missing" -- which is precisely when a user comes looking for it.

    ⚠ THE OBVIOUS ASSERTION HERE CANNOT BITE, so it is not the assertion. Delete the
    `manager is None` guard and the form still opens with no pickers: the attribute
    access on `None` raises, the broad `except` catches it, and the function returns
    `()` either way. That is the subsumed-guard shape that has already cost this repo
    a worthless test. What the guard actually changes is WHICH PATH is taken, so the
    discriminator is the debug record the except arm logs -- absent when a missing
    runtime is handled as the expected state, present the moment it is handled as a
    failure. Ablating the guard turns this red on that line alone.
    """
    mock_config_entry.add_to_hass(hass)
    assert hass.data.get(DOMAIN, {}).get(DATA_RUNTIME) is None, (
        "precondition: no runtime manager registered"
    )

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.eufy_vacuum.config_flow"
    ):
        init = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

    assert init["type"] == FlowResultType.FORM
    markers = _schema_markers(init)
    assert CONF_VACUUM_ENTITY_ID in markers and CONF_NOTES in markers
    assert not [k for k in markers if k.startswith(
        config_flow_module._OVERRIDE_FIELD_PREFIX
    )], "no runtime means no gap information, so no pickers"
    assert not [
        rec for rec in caplog.records if "could not read resolution gaps" in rec.message
    ], (
        "a missing runtime is an expected state, not an exception to swallow -- see "
        "the docstring above for why this is the assertion that can fail"
    )


async def test_of13_a_runtime_that_cannot_answer_does_log_and_still_opens(
    hass: HomeAssistant, mock_config_entry, caplog
):
    """[OF-13] The positive control for [OF-12], and it is not optional.

    [OF-12]'s whole claim rests on asserting the ABSENCE of a debug record, and an
    absence assertion proves nothing until something proves the record is VISIBLE to
    caplog in the first place. Get the logger name wrong, lose propagation, or have
    the level not applied, and [OF-12] passes vacuously -- it would pass with the
    guard it exists to pin deleted. This repo has already shipped that mistake in
    another form: a CI check that matched nothing counted zero failures of zero runs
    and reported green while two of five jobs were red. A pass over an empty set is
    indistinguishable from a real pass.

    So this is the same screen with a runtime that is PRESENT but cannot answer --
    which is what the broad `except` in `_resolution_gaps` is actually for, and what
    deleting [OF-12]'s guard turns a missing runtime into. Two facts at once: the
    record is real and reachable (so [OF-12]'s absence check is load-bearing), and
    the form still opens either way (so the best-effort promise in the docstring
    holds on the exception path too, not just the guarded one).
    """
    mock_config_entry.add_to_hass(hass)
    # Not None, so the guard does not fire -- and with no snapshot method, so the
    # attribute access raises and the except arm runs.
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = object()

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.eufy_vacuum.config_flow"
    ):
        init = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

    assert init["type"] == FlowResultType.FORM, "the form must open anyway"
    markers = _schema_markers(init)
    assert CONF_VACUUM_ENTITY_ID in markers and CONF_NOTES in markers
    assert not [k for k in markers if k.startswith(
        config_flow_module._OVERRIDE_FIELD_PREFIX
    )]
    assert [
        rec for rec in caplog.records if "could not read resolution gaps" in rec.message
    ], (
        "the record must be VISIBLE here, or [OF-12]'s absence assertion is an "
        "empty-set pass that would survive deleting the guard it pins"
    )
