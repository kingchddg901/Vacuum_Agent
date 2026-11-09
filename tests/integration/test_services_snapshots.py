"""Phase 4 integration tests — snapshot service handlers.

Coverage targets
----------------
[SNP-1]  get_pause_timeout_settings returns default settings.
[SNP-2]  set_pause_timeout_settings persists and returns updated value.
[SNP-3]  get_upkeep_snapshot returns a response dict.

Note: get_dashboard_snapshot is excluded — it requires live entity state that
is not available in isolated tests. (Pre-SNAP-2 this docstring also noted it
fires hass.bus.async_fire via _maybe_roll_current_room_by_timing as a snapshot
side effect; that is no longer true — get_job_progress_snapshot is a pure
read, and only the explicit apply_job_progress_tick() call, made by
listeners/job_progress.py's ticker, fires anything.)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.eufy_vacuum.const import DOMAIN


_VAC = "vacuum.alfred"


# ---------------------------------------------------------------------------
# [SNP-1] get_pause_timeout_settings
# ---------------------------------------------------------------------------

async def test_get_pause_timeout_settings_service_returns_default(hass, manager_with_services):
    """[SNP-1] Returns vacuum_entity_id and a default timeout value."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_pause_timeout_settings",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert "pause_timeout_minutes_default" in result


async def test_get_pause_timeout_settings_service_creates_vacuum_record(hass, manager_with_services):
    """[SNP-1] Calling for an unseen vacuum does not raise."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_pause_timeout_settings",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# [SNP-2] set_pause_timeout_settings
# ---------------------------------------------------------------------------

async def test_set_pause_timeout_settings_service_persists_value(hass, manager_with_services):
    """[SNP-2] Saved timeout is reflected in data after set service call."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    await hass.services.async_call(
        DOMAIN,
        "set_pause_timeout_settings",
        {"vacuum_entity_id": _VAC, "pause_timeout_minutes_default": 30},
        blocking=True,
        return_response=True,
    )
    stored = manager_with_services.data["vacuums"][_VAC]["pause_timeout_minutes_default"]
    assert stored == 30


async def test_set_pause_timeout_settings_service_returns_updated(hass, manager_with_services):
    """[SNP-2] Service returns updated=True with the persisted value."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_pause_timeout_settings",
        {"vacuum_entity_id": _VAC, "pause_timeout_minutes_default": 15},
        blocking=True,
        return_response=True,
    )
    assert result["updated"] is True
    assert result["pause_timeout_minutes_default"] == 15
    assert result["vacuum_entity_id"] == _VAC


async def test_set_pause_timeout_settings_service_zero_allowed(hass, manager_with_services):
    """[SNP-2] Zero is a valid pause_timeout_minutes_default (disables timeout)."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_pause_timeout_settings",
        {"vacuum_entity_id": _VAC, "pause_timeout_minutes_default": 0},
        blocking=True,
        return_response=True,
    )
    assert result["updated"] is True
    assert result["pause_timeout_minutes_default"] == 0


# ---------------------------------------------------------------------------
# [SNP-3] get_upkeep_snapshot
# ---------------------------------------------------------------------------

async def test_get_upkeep_snapshot_service_returns_dict(hass, manager_with_services):
    """[SNP-3] get_upkeep_snapshot returns a response dict."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_upkeep_snapshot",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum_entity_id" in result


# ---------------------------------------------------------------------------
# [SNP-5] get_maintenance_source_candidates
# ---------------------------------------------------------------------------

async def test_get_maintenance_source_candidates_service_is_reachable(
    hass, manager_with_services
):
    """[SNP-5] THE POINT OF THIS TEST IS THE CALL SITE, not the payload.

    `get_maintenance_source_candidates` existed on the manager for a day with ZERO callers — no
    service, not on a snapshot, nothing. It was written as "the picker's read half" and the
    picker could not have read it. That is `f/audit_callsite_reachability` exactly: a correct
    function with no call site passes every audit, and the suite was green the whole time.

    So this asserts the SERVICE answers, which is the half that was missing. The response is
    wrapped in a dict because a HA service response must be a mapping, and `candidates` is a
    list even when empty — the card distinguishes "fetch has not landed" (null) from "nothing to
    offer" ([]), and returning the wrong one shows an empty-state to someone still loading.

    THE INPUT THAT MAKES THIS RED: drop the `hass.services.async_register` call, or the
    `services.yaml` entry, or rename the constant on one side only.
    """
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)

    assert hass.services.has_service(DOMAIN, "get_maintenance_source_candidates"), (
        "the service is not registered — the manager method is unreachable again"
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_maintenance_source_candidates",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert isinstance(result.get("candidates"), list), (
        f"candidates must be a list even when empty, got {result.get('candidates')!r}"
    )


async def test_get_maintenance_source_candidates_refuses_an_unmanaged_vacuum(
    hass, manager_with_services
):
    """[SNP-5b] INKV8ZQD — a read answers empty-with-a-reason rather than inventing a record.

    Every other read service in this module carries the same guard; without it, asking about a
    vacuum this install does not have would reach the manager and could MINT a record for it
    (the shape that bit `get_pause_timeout_settings` in August).
    """
    result = await hass.services.async_call(
        DOMAIN,
        "get_maintenance_source_candidates",
        {"vacuum_entity_id": "vacuum.not_ours"},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum.not_ours" not in (manager_with_services.data.get("vacuums") or {}), (
        "a read must not create the vacuum record it was asked about"
    )


# ---------------------------------------------------------------------------
# [SNP-4], [SNP-6] - [SNP-8]  the unmanaged-vacuum split, and this file's one WRITE.
#
# `services/snapshots.py` was at 84.81% and its twelve uncovered units were two whole
# behaviours, not a scattered tail:
#
#   * both READ handlers' unmanaged arms (`INKV8ZQD: a read answers
#     empty-with-a-reason`) -- never driven, so nothing asserted that a card asking
#     about a vacuum we do not manage gets a payload rather than an error.
#   * `_handle_set_vacuum_capability` in its entirety, including its registered
#     delegator. The MANAGER method behind it is well covered by
#     test_user_capability.py; the SERVICE that reaches it had no test at all -- the
#     same forgotten-sibling shape this campaign keeps finding.
#
# THE SPLIT IS A RULING, not a style choice (2026-08-18, `INT62M7A`): a WRITE refuses
# with `ServiceValidationError` so HA shows a toast rather than a traceback, and a
# READ returns its empty shape carrying `reason` -- "because a read is how a card
# discovers state and turning discovery into an error trades a blank panel for a red
# toast". [SNP-6] is deliberately next to [SNP-4] so the asymmetry is visible in one
# place; a test of either half alone cannot show that the split exists.
#
# ⚠ SNP-5 IS ALREADY TAKEN (the maintenance-source reachability test above), which is
# why [SNP-4] carries both reads as parametrize rows rather than claiming a second id.
# Two overlapping SNP- ranges in one file would be the `MIG-` collision again.
#
# ⚠ AND [SNP-5b] IS THE THIRD READ'S EQUIVALENT, with two things worth knowing. Its
# NAME says `refuses_an_unmanaged_vacuum` while its body asserts the service ANSWERS
# -- the docstring is right and the name is not. And it asserts only
# `isinstance(result, dict)`, so a handler returning a bare `{}` would satisfy it;
# [SNP-4] asserts the `reason` field, which is the half that distinguishes "not ours"
# from "empty". Noted rather than renamed in passing.
#
# ⚠ THE MODULE DOCSTRING ABOVE EXCLUDES get_dashboard_snapshot "because it requires
# live entity state". That is true of its MANAGED path and not of this one: the
# unmanaged arm returns before `async_refresh_map_state_source` is reached, so it
# needs no live state at all. The exclusion was never about this branch.
# ---------------------------------------------------------------------------

_GHOST = "vacuum.not_ours"

#: DERIVED from the manager's own allowlist, never retyped. `set_vacuum_capability`
#: refuses anything outside `USER_ANSWERABLE_CAPABILITIES` with a ValueError, and a
#: hardcoded name would silently stop testing the write path the day that tuple
#: changes -- the first draft used an invented "mop" and got exactly that refusal.
def _answerable_capability(manager):
    allowed = manager.USER_ANSWERABLE_CAPABILITIES
    assert allowed, "no capability is user-answerable, so these tests prove nothing"
    return allowed[0]



@pytest.mark.parametrize("service", [
    pytest.param("get_dashboard_snapshot", id="dashboard"),
    pytest.param("get_upkeep_snapshot", id="upkeep"),
])
async def test_snp4_a_read_about_an_unmanaged_vacuum_answers_empty_with_a_reason(
    hass, manager_with_services, service
):
    """[SNP-4] Both reads return the honest empty payload, not an error.

    `reason` is the whole point of the shape: it lets a consumer tell "nothing here"
    from "not ours". Minting a phantom bucket for an unchecked id made those two
    byte-identical forever after, which is the failure the gate was added for.

    THE REASON IS ASSERTED, not just the absence of a raise. A handler that returned
    `{}` or `{"vacuum_entity_id": ...}` would satisfy "did not raise" while destroying
    exactly the distinction this exists to preserve.

    AND NO RECORD MAY BE MINTED. The gate's own docstring notes it only became usable
    as an authority once `get_pause_timeout_settings` stopped `setdefault`-ing into
    `data["vacuums"]` -- "a gate cannot be built on a dict its own read path writes
    to". So the assertion that the bucket is still absent afterwards is the one that
    keeps this honest.

    RED: drop the `is_managed_vacuum` guard and the dashboard read raises on an
    unmanaged id while the upkeep read mints a record.
    """
    assert _GHOST not in manager_with_services.data.get("vacuums", {}), (
        "precondition: the vacuum must be unmanaged"
    )

    result = await hass.services.async_call(
        DOMAIN, service, {"vacuum_entity_id": _GHOST},
        blocking=True, return_response=True,
    )

    assert result["vacuum_entity_id"] == _GHOST
    assert result["reason"] == "unmanaged_vacuum", (
        f"a read lost the reason that distinguishes 'not ours' from 'empty': {result}"
    )
    assert _GHOST not in manager_with_services.data.get("vacuums", {}), (
        "the read minted a record for a vacuum we do not manage -- which is what "
        "made 'nothing here' and 'not ours' indistinguishable in the first place"
    )


async def test_snp6_a_write_about_an_unmanaged_vacuum_refuses(hass, manager_with_services):
    _CAP = _answerable_capability(manager_with_services)
    """[SNP-6] The other half of the ruling: a WRITE refuses rather than answering.

    `require_managed_vacuum` raises `ServiceValidationError` -- a CALLER error, so HA
    surfaces a toast rather than a traceback. Per `INT62M7A`, "a mutation either
    refuses with a reason or succeeds carrying what it applied. Silently minting a
    bucket and reporting success is the third thing, and it is the bug."

    This sits beside [SNP-4] on purpose. Either test alone looks like an arbitrary
    choice of error shape; together they show the split is deliberate and which side
    each handler is on.

    RED: swap `require_managed_vacuum` for `is_managed_vacuum` + an empty-read return
    and this stops raising -- while [SNP-4] keeps passing, which is exactly why both
    are needed.
    """
    from homeassistant.exceptions import ServiceValidationError

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_vacuum_capability",
            {"vacuum_entity_id": _GHOST, "capability": _CAP, "supported": True},
            blocking=True, return_response=True,
        )

    assert _GHOST not in manager_with_services.data.get("vacuums", {}), (
        "the refused write still minted a bucket"
    )


@pytest.mark.parametrize("supported", [
    pytest.param(True, id="true"),
    pytest.param(False, id="false"),
])
async def test_snp7_the_capability_service_records_the_users_answer(
    hass, manager_with_services, supported
):
    """[SNP-7] The write path end to end, through the registered service.

    The manager method is covered by `test_user_capability.py`; what had no test was
    the SERVICE -- its schema, its managed-vacuum gate, its `resolved_call_data`
    pass, and the `await manager.async_save()` that makes the answer survive a
    restart. A user settling a capability by hand and losing it on the next boot is
    the failure that matters here, and only the service carries that save.

    BOTH VALUES ARE DRIVEN because they are not symmetric in meaning: the whole point
    of the feature is that a model-family GUESS reading as False "denies a feature to
    hardware that has it", so an explicit False has to be storable and distinguishable
    from the guess.

    ⚠ THE SAVE IS PINNED SEPARATELY, and it has to be. Asserting on `manager.data`
    cannot see the save at all -- the handler mutates the dict and then persists it,
    so the read-back passes either way. Measured: dropping
    `await manager.async_save()` reddened NOTHING until the spy below was added, and
    an earlier draft of this docstring claimed otherwise. The spy WRAPS the real
    method rather than replacing it, so the save still happens and the behaviour
    under test is unchanged.

    RED: drop `await manager.async_save()` and the spy records no call; drop the
    handler body and the read-back fails.
    """
    _CAP = _answerable_capability(manager_with_services)
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)

    with patch.object(
        manager_with_services, "async_save",
        wraps=manager_with_services.async_save,
    ) as saved:
        result = await hass.services.async_call(
            DOMAIN, "set_vacuum_capability",
            {"vacuum_entity_id": _VAC, "capability": _CAP, "supported": supported},
            blocking=True, return_response=True,
        )

    assert isinstance(result, dict) and result, "the service returned no payload"
    assert saved.await_count == 1, (
        f"the handler did not persist the answer ({saved.await_count} saves), so it "
        f"would be lost on the next restart"
    )
    overrides = manager_with_services.data["vacuums"][_VAC].get(
        "user_capabilities", {}
    )
    assert overrides.get(_CAP) is supported, (
        f"the user's answer was not recorded as {supported!r}: {overrides}"
    )


async def test_snp8_an_absent_supported_clears_rather_than_storing_false(
    hass, manager_with_services
):
    """[SNP-8] ABSENT means CLEAR -- hand the question back to detection.

    The schema says so in as many words: "Optional, and absent means CLEAR -- hand the
    question back to detection. A user who answers wrongly must not be stuck with it."
    The handler passes `data.get("supported")`, so absent arrives as None, and None
    must not be stored as False -- that would pin the wrong answer permanently, which
    is the exact failure the feature exists to undo.

    SET FIRST, THEN CLEAR, because "no override present" is also what a service that
    never stored anything produces. The first call is the precondition that makes the
    second one mean something.

    RED: default the handler to `data.get("supported", False)` and the clear stores
    False instead of removing the override.
    """
    _CAP = _answerable_capability(manager_with_services)
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)

    await hass.services.async_call(
        DOMAIN, "set_vacuum_capability",
        {"vacuum_entity_id": _VAC, "capability": _CAP, "supported": False},
        blocking=True, return_response=True,
    )
    overrides = manager_with_services.data["vacuums"][_VAC].get("user_capabilities", {})
    assert overrides.get(_CAP) is False, (
        f"precondition: the override must be stored before clearing it: {overrides}"
    )

    # ...and now the same call with `supported` OMITTED entirely.
    await hass.services.async_call(
        DOMAIN, "set_vacuum_capability",
        {"vacuum_entity_id": _VAC, "capability": _CAP},
        blocking=True, return_response=True,
    )

    overrides = manager_with_services.data["vacuums"][_VAC].get("user_capabilities", {})
    assert _CAP not in overrides, (
        f"an omitted `supported` was stored rather than clearing the override, so the "
        f"user is stuck with their answer: {overrides}"
    )
