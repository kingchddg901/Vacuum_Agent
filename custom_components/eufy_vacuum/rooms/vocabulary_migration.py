"""One-shot repair of room settings written under the framework's old Eufy default.

Until 2026-08-07 ``resolve_profile_catalog`` returned Eufy's catalog when an adapter
declared none, and several room-writing paths never consulted an adapter at all. Every
room those paths touched — on ANY brand — was written with Eufy's vocabulary. Removing
the fallback stops new rooms being born that way; it cannot heal rooms already on disk,
because a stored per-room field wins over the profile it claims. This is the healing
half, and it runs once.

Two rules, both driven by what the brand DECLARES. Neither infers anything from a value's
shape, and neither has brand knowledge of its own:

**DROP** — the room carries a field that appears in NO profile the brand declares
(neither its ``builtins`` nor its ``custom_template``). The brand has no such axis, so
the stored value came from somewhere else. Roborock is the live case: it omits
``clean_intensity`` from every profile on purpose (``roborock/vocabulary.py``), yet
Roborock rooms carry it.

**RESET** — the brand declares an option list for the field and the stored value is not
in it. A retired value the brand still declares an ALIAS for keeps its meaning
(``standard`` -> ``narrow``); only a value with no alias falls back to the default. The value cannot be selected in the card and is filtered out before dispatch
(``jobs/active_job.py`` skips a ``per_room_live_settings`` entry whose value is outside
its ``options_key``), so the setting silently does nothing. It becomes the brand's
``default_profile`` value for that field — a declared, in-vocabulary answer.

RESET deliberately does NOT pick a "nearest" option. There is no ordering to be nearest
in — the option lists are declared sets, not scales — and inventing one would be the same
class of guess as the default that caused this.

What this replaces
------------------
``normalize_clean_intensity`` folded the retired Eufy values ``standard``/``normal`` to
``"Quick"`` on every read, forever, from nine call sites. It is subsumed here without a
retired-value map: ``Standard`` is absent from Eufy's declared
``clean_intensity_options``, so RESET catches it, and Eufy's declared
``clean_intensity_aliases`` (``standard`` -> ``narrow``) then supplies the answer.

NOT the identical result, and deliberately so. The old fold produced ``"Quick"``, the
FASTEST density. ``Standard`` was the MIDDLE one — the original YAML system declared
Fast / Standard / Deep with Standard as the initial value, and upstream still maps
``standard`` to ``CleanExtent.NORMAL`` (0), the middle. Folding it to Quick silently
moved every affected room to a different density. The alias is what preserves the
meaning; the default-profile fallback is only for a retired value the brand declares no
alias for. Persisting the result is what lets the read-time fold be deleted.

Safety
------
The rules only ever act on a DECLARATION being present. A brand that declares no options
for a field is not judged — Roborock withholds ``water_level_options`` on models whose mop
is not settable, and treating that absence as "no such axis" would strip ``water_level``
and ``clean_mode`` from every room on an S6. Absence of an option list means "cannot
judge", never "does not exist"; only absence from the brand's own PROFILES means that.
"""

from __future__ import annotations

import logging
from typing import Any

from ..profiles.room_profiles import VOCABULARY_FIELDS, declared_profile_fields

_LOGGER = logging.getLogger(__name__)

#: Bumping this re-runs the migration for every install. Only do that if the rules
#: themselves change in a way that must be re-applied — the flag exists so a repaired
#: room is not repaired again after the user deliberately edits it back.
MIGRATION_KEY = "room_vocabulary_v1"

#: Shared with ``ProfileManager._finalize_room_update`` — the repair and the save path
#: must agree on which axes a brand has, or the repair undoes itself one room at a time.
_VOCABULARY_FIELDS = VOCABULARY_FIELDS


def _option_values(vocabulary: dict[str, Any], field: str) -> set[str] | None:
    """Declared option values for ``field``, or None when the brand declares none.

    None means "cannot judge", and every caller must treat it that way — see the
    module docstring's safety note.
    """
    options = vocabulary.get(f"{field}_options")
    if not isinstance(options, list) or not options:
        return None
    values = {str(o.get("value")) for o in options if isinstance(o, dict) and "value" in o}
    return values or None


def _alias_target(
    vocabulary: dict[str, Any], field: str, value: Any, allowed: set[str]
) -> str | None:
    """The declared option a retired value ALIASES to, or None if it aliases to none.

    Alias tables map a lowercased display string to a canonical lowercase code
    ("standard" -> "narrow"), while the declared options carry the brand's own casing
    ("Narrow"), so the match is case-insensitive. An alias pointing at something the
    brand does not declare is ignored rather than written — that is an adapter defect,
    and honouring it would put an undeliverable value on a room.
    """
    aliases = vocabulary.get(f"{field}_aliases")
    if not isinstance(aliases, dict):
        return None
    target = aliases.get(str(value).strip().lower())
    if target is None:
        return None
    for option in allowed:
        if str(option).strip().lower() == str(target).strip().lower():
            return option
    return None


def _unadjudicated_targets(*, data: dict[str, Any], get_config) -> list[str]:
    """Vacuums that HAVE stored rooms but whose adapter presented no declaration.

    These are targets this repair is responsible for and could not evaluate — as
    distinct from targets it evaluated and found nothing to do for. The planner skips
    both (neither licenses an edit), but only the second means the work is finished.

    ⚠ AN ABSENT BLOCK DOES NOT RELIABLY MEAN "not registered YET", AND THIS DOCSTRING
    CLAIMED IT DID UNTIL 2026-08-24 (R10/C61). It credited
    ``registry._validate_room_profiles`` with REJECTING an adapter whose
    ``room_profiles`` is missing or empty. That function only RETURNS issue strings;
    ``register_adapter_config`` logs them at WARNING and **hard-raises only when
    ``config.get("source") == "config"``**. A CODE-sourced adapter is warn-only and
    registers anyway, so ``get_config`` can return a live config with no
    ``room_profiles`` — exactly the state the old text called impossible. The
    correctly-scoped wording already existed 460 lines away, at
    ``registry._warn_completion_gate_orphan``: "hard-raised for a stored config by the
    caller".

    THE ROUTE THAT ACTUALLY REACHES THIS IS A DIFFERENT ONE, and it is worth stating
    because the obvious reading sends a reader to audit the adapters, where they will
    find nothing. Both shipped adapters declare ``room_profiles`` as unconditional dict
    literals, nothing mutates it afterwards, the config path forces
    ``source="config"``, and there is no third code adapter — so the ADAPTER-DEFECT
    route is not live today. The live one is ``brands.resolve_brand`` returning
    UNSUPPORTED: it registers NOTHING while the vacuum stays managed, so
    ``get_config`` returns ``None`` forever and the vacuum is permanently pending, with
    the WARNING re-emitted on every start. No adapter defect required.

    ⚠ THE DEFERRED-LATCH DESIGN BELOW WAS WRITTEN AGAINST A COLD-BOOT RACE, WHERE
    WAITING WORKS. It has never been reconciled with the unsupported-brand arm, which
    shipped later and makes "not registered yet" permanently false rather than
    temporarily so. THIS TEXT CALLED THAT AN OPEN DESIGN QUESTION UNTIL 2026-08-24; IT
    IS RULED (C61). A target that can never be adjudicated does NOT get a terminal
    disposition — the option that gave it one wrote a persisted key under
    ``migrations``, and a stored "gave up on this vacuum" verdict outlives the reason
    for it: the brand it gave up on becomes supported in a later release and the repair
    never runs. Only the VOLUME changed. ``migrate_room_vocabulary``'s deferral line
    moved from WARNING to DEBUG, so an unadjudicatable target no longer shouts once per
    Home Assistant start for the life of the install.

    NOTHING ELSE MOVED, deliberately: this function still returns every unadjudicated
    target, the latch still refuses to record the migration as done while one exists,
    and stored rooms are judged exactly as before. The deferral is still retried on the
    next start — which is what makes the quieter level safe, and what a terminal
    disposition would have thrown away.

    On this house's boxes the site is currently inert: ``vacuum.robin`` (an unsupported
    Dreame) is in ``vacuums`` with a ``maps`` bucket holding zero rooms, so only the
    no-stored-rooms guard below keeps it out — one saved room away — and that box has
    already latched.

    Vacuums with no stored rooms are not targets — there is nothing to judge and nothing
    to come back for, and rooms created later are born under current rules.
    """
    pending: list[str] = []
    for vacuum_entity_id, maps in (data.get("maps") or {}).items():
        if not isinstance(maps, dict):
            continue
        if not any(
            isinstance(bucket, dict) and (bucket.get("rooms") or {})
            for bucket in maps.values()
        ):
            continue
        block = (get_config(vacuum_entity_id) or {}).get("room_profiles")
        if not (isinstance(block, dict) and block):
            pending.append(vacuum_entity_id)
    return pending


def plan_room_vocabulary_migration(
    *,
    data: dict[str, Any],
    get_config,
) -> list[dict[str, Any]]:
    """Return the changes the migration WOULD make. Pure: touches nothing.

    ``get_config`` is ``adapters.registry.get_adapter_config``, injected so this stays
    importable without the registry and testable without registering an adapter.
    """
    planned: list[dict[str, Any]] = []

    for vacuum_entity_id, maps in (data.get("maps") or {}).items():
        if not isinstance(maps, dict):
            continue
        config = get_config(vacuum_entity_id) or {}
        block = config.get("room_profiles")
        if not isinstance(block, dict) or not block:
            # No declaration to judge against. Skipping is the only safe act — an
            # unregistered or undeclared adapter must never license edits to stored
            # rooms.
            _LOGGER.debug(
                "vocabulary_migration: %s declares no room_profiles; skipped",
                vacuum_entity_id,
            )
            continue

        vocabulary = config.get("vocabulary") or {}
        declared = declared_profile_fields(
            {"builtins": block.get("builtins") or {}, "custom_template": block.get("custom_template")}
        )
        if not declared:
            continue
        default_profile = (block.get("builtins") or {}).get(block.get("default_profile")) or {}

        for map_id, bucket in maps.items():
            if not isinstance(bucket, dict):
                continue
            for room_id, room in (bucket.get("rooms") or {}).items():
                if not isinstance(room, dict):
                    continue
                for field in _VOCABULARY_FIELDS:
                    if field not in room:
                        continue
                    if field not in declared:
                        planned.append({
                            "vacuum_entity_id": vacuum_entity_id,
                            "map_id": str(map_id),
                            "room_id": str(room_id),
                            "field": field,
                            "action": "drop",
                            "old": room[field],
                            "new": None,
                        })
                        continue
                    allowed = _option_values(vocabulary, field)
                    if allowed is None or str(room[field]) in allowed:
                        continue

                    # A RETIRED value the brand still declares an alias for keeps its
                    # MEANING — resolve it before considering the default. Without
                    # this, Eufy's "Standard" (the original middle pass density, and
                    # the initial value of the very first setup) fell through to the
                    # default profile's "Quick", moving every affected room from the
                    # middle density to the fastest. A reduction in cleaning nobody
                    # chose, and invisible because the result was a perfectly valid
                    # value.
                    replacement = _alias_target(vocabulary, field, room[field], allowed)
                    if replacement is None:
                        replacement = default_profile.get(field)
                    if replacement is None or str(replacement) not in allowed:
                        # The brand's own default is not in its own option list. That
                        # is an adapter defect, and guessing past it would hide it.
                        _LOGGER.warning(
                            "vocabulary_migration: %s room %s has out-of-vocabulary %s=%r "
                            "but the default profile offers no valid replacement (%r); left alone",
                            vacuum_entity_id, room_id, field, room[field], replacement,
                        )
                        continue
                    planned.append({
                        "vacuum_entity_id": vacuum_entity_id,
                        "map_id": str(map_id),
                        "room_id": str(room_id),
                        "field": field,
                        "action": "reset",
                        "old": room[field],
                        "new": replacement,
                    })

    return planned


def migrate_room_vocabulary(
    *,
    data: dict[str, Any],
    get_config,
    force: bool = False,
) -> dict[str, Any]:
    """Apply the migration once, recording that it ran. Idempotent.

    Returns ``{"ran": bool, "changes": [...], "rooms_touched": int}``. The caller is
    responsible for persisting ``data``; nothing here writes to disk.
    """
    migrations = data.setdefault("migrations", {})
    if migrations.get(MIGRATION_KEY) and not force:
        return {"ran": False, "changes": [], "rooms_touched": 0}

    changes = plan_room_vocabulary_migration(data=data, get_config=get_config)

    for change in changes:
        room = (
            ((data.get("maps") or {}).get(change["vacuum_entity_id"]) or {})
            .get(change["map_id"], {})
            .get("rooms", {})
            .get(change["room_id"])
        )
        if not isinstance(room, dict):
            continue
        if change["action"] == "drop":
            room.pop(change["field"], None)
        else:
            room[change["field"]] = change["new"]

    # LATCH ONLY IF THIS RUN COULD ACTUALLY SEE SOMETHING.
    #
    # This used to be unconditional, and a run that repaired nothing still burned the
    # one shot. That is reachable on a normal cold boot: the adapters are registered
    # from the vacuum entities of OTHER integrations, and if those have not finished
    # setting up, every vacuum here is skipped for want of a declaration. The repair
    # then marked itself done having judged nothing, and the rooms it was written to
    # heal kept their bad values permanently — silently, because the skip logs at DEBUG.
    # Observed on hardware: two full restarts changed nothing, and a config-entry
    # RELOAD (by which point the vacuums existed) repaired all twenty rooms.
    #
    # The rule is EVERY target, not "any adapter answered". With two vacuums, one
    # provider being ready must not burn the opportunity for a provider that starts
    # later: a first draft latched as soon as a single declaration was found, which on
    # this very install would have repaired the Eufy and abandoned the Roborock. The
    # invariant is that a migration is complete only when every target it is responsible
    # for has reached a terminal disposition; missing runtime information is DEFERRED,
    # never SUCCESS.
    #
    # A vacuum with no stored rooms is not a target, so an install with none latches
    # vacuously rather than rescanning forever.
    _pending = _unadjudicated_targets(data=data, get_config=get_config)
    _latched = not _pending
    if _latched:
        migrations[MIGRATION_KEY] = True
    else:
        # DEBUG, NOT WARNING — downgraded 2026-08-24 by the C61 ruling.
        #
        # The failure mode this line had: a vacuum on an UNSUPPORTED brand can never be
        # adjudicated. ``brands.resolve_brand`` registers no adapter for it while the
        # vacuum stays managed, so ``get_config`` returns None forever, ``_pending``
        # never empties, and this message was re-emitted at WARNING on EVERY Home
        # Assistant start, permanently, with nothing the user could do about it.
        # (``vacuum.robin``, the unsupported Dreame on this house's boxes, is one saved
        # room away from being exactly that.) A warning that can never be acted on and
        # never stops trains people to mute the integration's log, which costs them the
        # warnings that DO mean something.
        #
        # The information is not gone, it is just not shouted: the full count and the
        # entity ids stay here for anyone debugging a repair that has not happened, and
        # every caller still gets ``latched: False`` in the return value. The latch
        # condition itself is untouched — this run still did not record itself as done
        # and still retries on the next start.
        _LOGGER.debug(
            "vocabulary_migration: %d vacuum(s) with stored rooms had no adapter "
            "declaration to judge against (%s), so their rooms could not be evaluated; "
            "NOT recording the migration as done — it will retry on the next start",
            len(_pending), ", ".join(_pending),
        )

    touched = len({(c["vacuum_entity_id"], c["map_id"], c["room_id"]) for c in changes})
    if changes:
        _LOGGER.info(
            "vocabulary_migration: repaired %d setting(s) across %d room(s) written under "
            "the framework's former Eufy default", len(changes), touched,
        )
        for c in changes:
            _LOGGER.info(
                "vocabulary_migration:   %s room %s: %s %s=%r%s",
                c["vacuum_entity_id"], c["room_id"], c["action"], c["field"], c["old"],
                f" -> {c['new']!r}" if c["action"] == "reset" else "",
            )

    return {
        "ran": True,
        "changes": changes,
        "rooms_touched": touched,
        # False means this run declined to record itself as done and will retry.
        "latched": _latched,
    }
