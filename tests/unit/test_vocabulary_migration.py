"""The one-shot repair of rooms written under the framework's former Eufy default.

This rewrites SETTINGS ON A USER'S REAL ROOMS at startup, so the bar is higher than
"the happy path works". What matters as much as the rooms it repairs is the rooms it
declines to touch: a migration that over-reaches silently changes how somebody's vacuum
cleans, and there is no error to notice.

The dangerous rule is DROP. An early draft keyed it on "the brand declares no options
for this field", which reads correct and would have stripped ``clean_mode`` and
``water_level`` from every room on a Roborock S6 — that model declares no options for
them because its mop is not settable, not because the axis does not exist. MIG-5 pins
the distinction that averted it: absence of an OPTION LIST means "cannot judge"; only
absence from the brand's own PROFILES means "no such axis".

Coverage targets
----------------
[MIG-1] DROP: a field no declared profile carries is removed.
[MIG-2] RESET: an out-of-vocabulary value becomes the brand's default_profile value.
[MIG-3] in-vocabulary values are left exactly alone.
[MIG-4] a vacuum whose adapter declares nothing is SKIPPED, never guessed at.
[MIG-5] no option list declared → the field is not judged (the S6 safety case).
[MIG-6] the brand's own default being out-of-vocabulary is reported, not worked around.
[MIG-7] idempotent: the second run is a no-op, and an edited-back room stays edited.
[MIG-8] planning is pure — planning alone mutates nothing.
[MIG-9] the retired-value fold is subsumed without any retired-value map.
[MIG-11] a run that saw NO adapter does not latch the one shot; an install with no
         stored rooms does (nothing to come back for).
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.rooms.vocabulary_migration import (
    MIGRATION_KEY,
    migrate_room_vocabulary,
    plan_room_vocabulary_migration,
)

from tests.brand_catalogs import EUFY_BLOCK, SYNTHETIC_BLOCK, SYNTHETIC_VOCABULARY

_VAC = "vacuum.probe"


def _config(**overrides):
    cfg = {
        "adapter_id": "synthetic",
        "room_profiles": SYNTHETIC_BLOCK,
        "vocabulary": SYNTHETIC_VOCABULARY,
    }
    cfg.update(overrides)
    return cfg


def _data(rooms: dict, vacuum: str = _VAC) -> dict:
    return {"maps": {vacuum: {"map1": {"rooms": rooms}}}}


def _getter(config):
    return lambda vacuum_entity_id: config


def _room(**fields):
    base = {"room_id": 1, "name": "Kitchen"}
    base.update(fields)
    return base


# ---------------------------------------------------------------------------
# DROP
# ---------------------------------------------------------------------------

def test_drops_a_field_the_brand_declares_no_axis_for():
    """[MIG-1] Roborock's live case: rooms carrying ``clean_intensity``, which it omits
    from every profile on purpose, written there by core's Eufy-shaped default."""
    no_intensity = {
        **SYNTHETIC_BLOCK,
        "builtins": {
            name: {k: v for k, v in profile.items() if k != "clean_intensity"}
            for name, profile in SYNTHETIC_BLOCK["builtins"].items()
        },
        "custom_template": {
            k: v for k, v in SYNTHETIC_BLOCK["custom_template"].items()
            if k != "clean_intensity"
        },
    }
    data = _data({"1": _room(clean_intensity="Standard", fan_speed="SynthMid")})

    result = migrate_room_vocabulary(
        data=data, get_config=_getter(_config(room_profiles=no_intensity)),
    )

    room = data["maps"][_VAC]["map1"]["rooms"]["1"]
    assert "clean_intensity" not in room
    assert room["fan_speed"] == "SynthMid", "an unrelated field was touched"
    assert [c["action"] for c in result["changes"]] == ["drop"]


# ---------------------------------------------------------------------------
# RESET
# ---------------------------------------------------------------------------

def test_resets_an_out_of_vocabulary_value_to_the_brands_default():
    """[MIG-2] The live Ivy case: a room storing a fan speed absent from its brand's
    declared options, which dispatch skips entirely — the setting silently does nothing."""
    data = _data({"1": _room(fan_speed="Max")})   # Eufy's word, on a synthetic brand

    result = migrate_room_vocabulary(data=data, get_config=_getter(_config()))

    expected = SYNTHETIC_BLOCK["builtins"]["vacuum_quick"]["fan_speed"]
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["fan_speed"] == expected
    assert result["changes"][0]["action"] == "reset"
    assert result["changes"][0]["old"] == "Max"


def test_reset_does_not_pick_a_nearest_option():
    """[MIG-2b] The replacement is the DECLARED default, not the closest-looking value.

    "Nearest rung" would be a guess dressed as a fix, and the option lists are declared
    sets with no ordering to be nearest in. ``SynthMax`` is lexically closest to the
    stored ``Max``; the correct answer is the default profile's ``SynthMid``.
    """
    data = _data({"1": _room(fan_speed="Max")})
    migrate_room_vocabulary(data=data, get_config=_getter(_config()))
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["fan_speed"] == "SynthMid"


def test_leaves_in_vocabulary_values_completely_alone():
    """[MIG-3] The adversarial half: a correct room must come through byte-identical."""
    good = _room(
        fan_speed="SynthMax", water_level="SynthWet", clean_intensity="SynthDeep",
        clean_mode="vacuum_mop", path_type="narrow", clean_passes=2, edge_mopping=True,
    )
    data = _data({"1": dict(good)})

    result = migrate_room_vocabulary(data=data, get_config=_getter(_config()))

    assert result["changes"] == []
    assert data["maps"][_VAC]["map1"]["rooms"]["1"] == good


# ---------------------------------------------------------------------------
# Refusals — what it must NOT do
# ---------------------------------------------------------------------------

def test_skips_a_vacuum_whose_adapter_declares_nothing():
    """[MIG-4] No declaration is no licence. An unregistered or undeclared adapter must
    never authorise edits to stored rooms — there is nothing to judge them against."""
    data = _data({"1": _room(fan_speed="Max", clean_intensity="Standard")})

    result = migrate_room_vocabulary(data=data, get_config=lambda _v: None)

    assert result["changes"] == []
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["fan_speed"] == "Max"


def test_a_run_that_saw_no_adapter_does_not_burn_the_one_shot():
    """[MIG-11] The skip in MIG-4 must not also count as the repair having happened.

    Adapters are registered from the vacuum entities of OTHER integrations. On a cold
    boot those may not have set up yet, so every vacuum is skipped for want of a
    declaration — the same branch MIG-4 exercises. Latching there marked the repair done
    having judged nothing, and the rooms kept their bad values forever, silently.

    Observed on hardware before this guard: two full restarts repaired nothing, and a
    config-entry reload (by which point the vacuums existed) repaired all twenty rooms.
    """
    data = _data({"1": _room(fan_speed="Max", clean_intensity="Standard")})

    blind = migrate_room_vocabulary(data=data, get_config=lambda _v: None)

    assert blind["changes"] == []
    assert blind["latched"] is False
    assert MIGRATION_KEY not in data.get("migrations", {})

    # The next start, with adapters up, still gets its one shot.
    ready = migrate_room_vocabulary(data=data, get_config=_getter(_config()))

    assert ready["changes"], "the retry must actually repair"
    assert ready["latched"] is True
    assert data["migrations"][MIGRATION_KEY] is True


def test_one_ready_adapter_does_not_burn_the_shot_for_a_slower_one():
    """[MIG-11] The dangerous case is PARTIAL readiness, not total.

    Two vacuums, two providers, independent setup order. A first draft of this guard
    latched as soon as ANY declaration was found — which on a real two-vacuum install
    repairs the ready one and abandons the other permanently. Repairing what it can is
    correct; calling itself finished is not.
    """
    data = {
        "maps": {
            "vacuum.ready": {"map1": {"rooms": {"1": _room(fan_speed="Max")}}},
            "vacuum.slow": {"map1": {"rooms": {"2": _room(fan_speed="Max")}}},
        }
    }
    only_ready = lambda v: _config() if v == "vacuum.ready" else None  # noqa: E731

    partial = migrate_room_vocabulary(data=data, get_config=only_ready)

    # It repairs what it legitimately can...
    assert any(c["vacuum_entity_id"] == "vacuum.ready" for c in partial["changes"])
    assert not any(c["vacuum_entity_id"] == "vacuum.slow" for c in partial["changes"])
    # ...but must NOT declare itself done while a target is unevaluated.
    assert partial["latched"] is False
    assert MIGRATION_KEY not in data.get("migrations", {})

    # Next start, both up: the slow one still gets its repair, and NOW it latches.
    both = migrate_room_vocabulary(data=data, get_config=_getter(_config()))

    assert any(c["vacuum_entity_id"] == "vacuum.slow" for c in both["changes"])
    assert both["latched"] is True
    assert data["migrations"][MIGRATION_KEY] is True


def test_an_install_with_no_stored_rooms_still_latches():
    """[MIG-11] "Nothing to judge against" and "nothing to repair" are different.

    Without this half, a user with no rooms yet would re-run the scan on every single
    start forever, since no adapter is ever consulted for a store with no maps. There is
    nothing to come back for — rooms created later are born under current rules.
    """
    data: dict = {"maps": {}}

    result = migrate_room_vocabulary(data=data, get_config=lambda _v: None)

    assert result["changes"] == []
    assert result["latched"] is True
    assert data["migrations"][MIGRATION_KEY] is True


def test_does_not_judge_a_field_with_no_declared_option_list():
    """[MIG-5] The check that averted a destructive migration.

    A Roborock S6 declares no ``water_level_options`` because its mop is not settable —
    a capability statement, not a vocabulary one. Treating that absence as "no such
    axis" would have stripped water_level from every room on that model. Absence of an
    option list means CANNOT JUDGE; only absence from the brand's own profiles means
    the axis does not exist, and water_level IS in its profiles.
    """
    vocab = {k: v for k, v in SYNTHETIC_VOCABULARY.items() if k != "water_level_options"}
    data = _data({"1": _room(water_level="TotallyBogus")})

    result = migrate_room_vocabulary(
        data=data, get_config=_getter(_config(vocabulary=vocab)),
    )

    assert result["changes"] == []
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["water_level"] == "TotallyBogus"


def test_a_brand_whose_own_default_is_invalid_is_reported_not_worked_around(caplog):
    """[MIG-6] The brand's default_profile value is not in the brand's own options.

    That is an adapter defect. Substituting something plausible would hide it, so the
    room is left as-is and the mismatch is logged — a wrong setting the user can see
    beats a silently invented one they cannot.
    """
    broken = {
        **SYNTHETIC_BLOCK,
        "builtins": {
            **SYNTHETIC_BLOCK["builtins"],
            "vacuum_quick": {
                **SYNTHETIC_BLOCK["builtins"]["vacuum_quick"], "fan_speed": "NotDeclared",
            },
        },
    }
    data = _data({"1": _room(fan_speed="Max")})

    result = migrate_room_vocabulary(
        data=data, get_config=_getter(_config(room_profiles=broken)),
    )

    assert result["changes"] == []
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["fan_speed"] == "Max"
    assert "no valid replacement" in caplog.text


# ---------------------------------------------------------------------------
# Once, and only once
# ---------------------------------------------------------------------------

def test_runs_once_and_a_repaired_room_stays_repaired_after_a_user_edit():
    """[MIG-7] Idempotence is not a nicety here.

    Without the flag, a user who deliberately sets a room back to an unusual value would
    have it "repaired" again on every restart — the migration would become a permanent
    policy rather than a one-time fix.
    """
    data = _data({"1": _room(fan_speed="Max")})

    first = migrate_room_vocabulary(data=data, get_config=_getter(_config()))
    assert first["ran"] is True and first["changes"]
    assert data["migrations"][MIGRATION_KEY] is True

    # The user deliberately sets something the brand does not declare.
    data["maps"][_VAC]["map1"]["rooms"]["1"]["fan_speed"] = "Max"
    second = migrate_room_vocabulary(data=data, get_config=_getter(_config()))

    assert second["ran"] is False
    assert second["changes"] == []
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["fan_speed"] == "Max"


def test_planning_mutates_nothing():
    """[MIG-8] The dry run must be genuinely pure — it is how the change is reviewed
    before it is allowed to touch a real store."""
    data = _data({"1": _room(fan_speed="Max", clean_intensity="Standard")})
    before = {k: dict(v) for k, v in data["maps"][_VAC]["map1"]["rooms"].items()}

    planned = plan_room_vocabulary_migration(data=data, get_config=_getter(_config()))

    assert planned, "nothing planned — this test would pass vacuously"
    assert data["maps"][_VAC]["map1"]["rooms"] == before
    assert "migrations" not in data


# ---------------------------------------------------------------------------
# What it replaced
# ---------------------------------------------------------------------------

def test_the_retired_eufy_intensity_fold_is_subsumed_with_no_retired_value_map():
    """[MIG-9] ``normalize_clean_intensity`` folded "Standard"/"Normal" → "Quick" on
    every read, from nine call sites, forever.

    It needs no replacement rule. ``Standard`` is simply absent from Eufy's declared
    ``clean_intensity_options``, so the generic RESET catches it, and Eufy's own
    ``default_profile`` declares ``"Quick"`` — the identical result, reached from a
    declaration rather than a constant, computed once instead of on every read.
    """
    eufy_config = {
        "adapter_id": "eufy",
        "room_profiles": EUFY_BLOCK,
        "vocabulary": {
            "clean_intensity_options": [
                {"value": "Quick", "label": "Quick"},
                {"value": "Narrow", "label": "Narrow"},
                {"value": "Deep", "label": "Deep"},
            ],
        },
    }
    data = _data({"1": _room(clean_intensity="Standard")})

    migrate_room_vocabulary(data=data, get_config=_getter(eufy_config))

    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["clean_intensity"] == "Quick"


@pytest.mark.parametrize("retired", ["Standard", "Normal"])
def test_both_retired_intensity_values_are_repaired(retired):
    """[MIG-9b] Both values the old fold knew about, reached without naming either."""
    eufy_config = {
        "adapter_id": "eufy",
        "room_profiles": EUFY_BLOCK,
        "vocabulary": {"clean_intensity_options": [
            {"value": v, "label": v} for v in ("Quick", "Narrow", "Deep")
        ]},
    }
    data = _data({"1": _room(clean_intensity=retired)})
    migrate_room_vocabulary(data=data, get_config=_getter(eufy_config))
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["clean_intensity"] == "Quick"


def test_mig_10_a_retired_value_keeps_its_meaning_via_a_declared_alias():
    """[MIG-10] A RETIRED value the brand aliases keeps its MEANING, not the default.

    The case that shipped wrong. Eufy's "Standard" was not a phantom: the original
    YAML system declared Fast / Standard / Deep with Standard as the INITIAL value —
    the middle pass density — and robovac_mqtt still maps "standard" to
    CleanExtent.NORMAL (0), the middle. A 2026-07-26 commit folded it to "quick" on
    the premise that it "was never a real Eufy value", and this migration inherited
    that by falling through to the default profile.

    The result was valid-looking and wrong: every affected room moved from the middle
    density to the FASTEST one. Less cleaning, chosen by nobody, and undetectable
    afterwards because the stored value was a perfectly legal option.
    """
    eufy_config = {
        "adapter_id": "eufy",
        "room_profiles": EUFY_BLOCK,
        "vocabulary": {
            "clean_intensity_options": [
                {"value": v, "label": v} for v in ("Quick", "Narrow", "Deep")
            ],
            "clean_intensity_aliases": {"fast": "quick", "standard": "narrow",
                                        "normal": "narrow"},
        },
    }
    data = _data({"1": _room(clean_intensity="Standard")})
    migrate_room_vocabulary(data=data, get_config=_getter(eufy_config))
    # The MIDDLE option, not the default profile's Quick.
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["clean_intensity"] == "Narrow"


def test_mig_10b_without_the_alias_it_still_falls_back_to_the_default():
    """[MIG-10b] The control. Only an ALIASED value keeps its meaning; a value the
    brand says nothing about still resolves to the declared default, because there is
    nothing to preserve."""
    eufy_config = {
        "adapter_id": "eufy",
        "room_profiles": EUFY_BLOCK,
        "vocabulary": {
            "clean_intensity_options": [
                {"value": v, "label": v} for v in ("Quick", "Narrow", "Deep")
            ],
            "clean_intensity_aliases": {"standard": "narrow"},
        },
    }
    data = _data({"1": _room(clean_intensity="Bogus")})
    migrate_room_vocabulary(data=data, get_config=_getter(eufy_config))
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["clean_intensity"] == "Quick"


def test_mig_10c_an_alias_pointing_at_an_undeclared_option_is_ignored():
    """[MIG-10c] An alias whose target the brand does not declare is an adapter defect.
    Honouring it would write an undeliverable value onto a room, so the default wins."""
    eufy_config = {
        "adapter_id": "eufy",
        "room_profiles": EUFY_BLOCK,
        "vocabulary": {
            "clean_intensity_options": [
                {"value": v, "label": v} for v in ("Quick", "Narrow", "Deep")
            ],
            "clean_intensity_aliases": {"standard": "does_not_exist"},
        },
    }
    data = _data({"1": _room(clean_intensity="Standard")})
    migrate_room_vocabulary(data=data, get_config=_getter(eufy_config))
    assert data["maps"][_VAC]["map1"]["rooms"]["1"]["clean_intensity"] == "Quick"
