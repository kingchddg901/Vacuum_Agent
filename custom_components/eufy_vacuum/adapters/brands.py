"""Brand selection — which adapter registrar runs for a given vacuum.

THE single place that answers "what brand is this vacuum?". Before this module the
answer was a two-arm ``if/else`` in ``__init__.py`` with Eufy as the unconditional
``else``, which had four costs:

- Eufy was a *structural* default, not a declared one. Anything not positively
  identified as Roborock silently became a Eufy, with no log line to say so.
- Adding a third brand meant editing integration core rather than adding a package.
- The unsupported case could not be tested, because it did not exist as a code path.
  Several future-brand findings were unreachable for exactly that reason.
- The promised per-vacuum UI brand selector had nowhere to plug in.

Adding a brand is now: write the package, add one ``BrandRegistrar`` row below. Core
is untouched. See doc 21 §7.

Resolution order, first win takes it:

1. **override** — an explicit per-vacuum choice in ``data["brand_overrides"]``. A user
   saying "this is a Roborock" outranks auto-detection, which is the whole point of
   having a selector. Nothing writes this key yet; the read path exists so the UI has
   somewhere to land.
2. **platform** — the vacuum's ENTITY-registry ``platform`` appears in a registrar's
   declared ``platforms``. The adapter states its own identity in its ``const.py``;
   core only compares.
3. **unsupported** — nothing claimed it. No adapter is registered and we SAY SO.

IDENTITY IS DATA. There is no ``detect`` callable and no ``is_X_brand`` function in this
table, deliberately. An earlier version had one per brand and core called each in turn —
which is ``if brand:`` wearing a function pointer, and putting brand knowledge back into
core's control flow is precisely what the adapter seam exists to remove. A brand now
declares WHICH INTEGRATION PROVIDES IT and core does nothing but compare strings; the
brand cannot express "probably me", because that question is no longer asked.

``resolve_brand`` reports which route was taken so the caller can log it. "This is a
Eufy", "the user told us it is a Eufy", and "nothing claims this at all" are three
different facts, and all three used to produce the same silent outcome: a Eufy adapter.

EUFY NOW HAS AN HONEST POSITIVE TEST, AND THIS IS THE NOTE THAT SAID IT COULDN'T.
The previous text here read: *Eufy carries no ``detect`` at all — deliberately. The Eufy
adapter never reads the device registry for manufacturer/model, so there is no honest
positive test to write, and inventing one would dress an assumption up as an
identification.* That reasoning was sound about the DEVICE registry, where manufacturer
and model are free text and routinely blank. It does not apply to the ENTITY registry:
``platform`` is set by HA from the providing integration's domain, is never blank, and
is not a guess about the hardware — it is a fact about who created the entity. Alfred
reports ``robovac_mqtt``; so do all 65 of ptruman's entities in issue #49.

SUPPORT IS A POSITIVE STATEMENT. There is no default arm. A vacuum no adapter claims is
UNSUPPORTED: it stays managed, gets no adapter config, and the log says which platform we
did not recognise. Previously it was silently registered as a Eufy — which is how
``vacuum.robin`` (a Dreame) ran on Eufy's vocabulary and bound 2 of ~10 roles by
coincidence of naming, looking configured rather than wrong.

⚠ This is a guard that activates over EXISTING installs. A Eufy served by a
differently-named fork of ``robovac_mqtt`` would go from working to unsupported, so the
refusal must always name ``brand_overrides`` as the way back. Nothing writes that key
yet — the UI selector is the missing half of this change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..const import ENTITY_OVERRIDES_KEY
from .eufy.adapter import register_eufy_adapter_for_vacuum
from .eufy.const import UPSTREAM_PLATFORMS as EUFY_PLATFORMS
from .roborock.adapter import register_roborock_adapter_for_vacuum
from .roborock.const import UPSTREAM_PLATFORMS as ROBOROCK_PLATFORMS

_LOGGER = logging.getLogger(__name__)

#: Storage key holding explicit per-vacuum brand choices
#: (``{vacuum_entity_id: brand_id}``). Distinct from ``data["adapters"]``, which holds a
#: whole stored adapter CONFIG — this is only the choice of which registrar to run.
BRAND_OVERRIDES_KEY = "brand_overrides"


@dataclass(frozen=True)
class BrandRegistrar:
    """One brand's identity claim + registration entry point.

    Identity is DATA, not a callable. ``register`` assembles and registers that brand's
    adapter config for one vacuum and is idempotent.
    """

    brand_id: str
    #: ``(hass, vacuum_entity_id, *, entity_overrides=None) -> None``.
    #: ``entity_overrides`` is the user's resolved ``{role: entity_id}`` map for
    #: THIS vacuum, already extracted by the tier above — a brand is handed the
    #: meaning, never the storage key (ISO-1).
    register: Callable[..., None]
    #: HA integration domain(s) providing this brand's vacuum entity, declared BY THE
    #: ADAPTER in its own ``const.py``. Matched against the entity registry's
    #: ``platform``. This is the adapter's identity claim about itself; core never
    #: sniffs strings on a brand's behalf.
    platforms: tuple[str, ...] = ()


#: Ordered; the first registrar claiming the vacuum's platform wins.
#:
#: ADDING A BRAND IS DATA, NOT CODE. A brand declares the integration domain(s) that
#: provide its vacuum entity in its own ``const.py``; this table carries that tuple and
#: core compares. There is deliberately NO per-brand ``is_X_brand`` callable — core
#: asking each brand "is this yours?" puts brand knowledge back in core's control flow,
#: which is the arrangement the adapter seam exists to remove.
#:
#: THERE IS NO DEFAULT ARM. A vacuum whose platform matches nothing is UNSUPPORTED and
#: gets no adapter — see ``resolve_brand``. Support is a positive, declared statement.
BRAND_REGISTRARS: tuple[BrandRegistrar, ...] = (
    BrandRegistrar(
        brand_id="roborock",
        register=register_roborock_adapter_for_vacuum,
        platforms=ROBOROCK_PLATFORMS,
    ),
    BrandRegistrar(
        brand_id="eufy",
        register=register_eufy_adapter_for_vacuum,
        platforms=EUFY_PLATFORMS,
    ),
)


#: The ``source`` returned when no registrar claims a vacuum. It is a real answer, not
#: an error: the vacuum stays MANAGED (it is already in ``get_known_vacuum_ids``) and
#: simply has no adapter config, which every consumer of ``get_adapter_config`` already
#: tolerates — the registry has always been able to return None.
UNSUPPORTED = "unsupported"


# REMOVED — ``get_default_registrar`` and the ``is_default`` flag.
#
# The terminal arm registered Eufy for anything unidentified, which meant a Dreame, a
# Xiaomi, or a template vacuum silently ran on Eufy's entity naming, vocabulary and
# maintenance components. `vacuum.robin` (a Dreame) was the live proof: it bound 2 of
# ~10 roles by coincidence of naming and looked configured rather than wrong.
#
# Support is now a POSITIVE, DECLARED statement. If no adapter claims a platform, we say
# so instead of guessing, and `brand_overrides` remains the escape hatch for anyone we
# refuse wrongly (a Eufy on a differently-named fork, say).


def get_registrar(brand_id: str) -> BrandRegistrar | None:
    """Look a registrar up by brand_id. None when the id is unknown."""
    wanted = str(brand_id or "").strip().lower()
    for registrar in BRAND_REGISTRARS:
        if registrar.brand_id == wanted:
            return registrar
    return None


def resolve_brand(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    *,
    data: dict[str, Any] | None = None,
) -> tuple[BrandRegistrar | None, str]:
    """Return ``(registrar, source)`` for one vacuum; registrar is None if unsupported.

    ``source`` is ``"override"`` / ``"platform"`` / ``"unsupported"`` — see the module
    docstring. Never raises for a bad override or an unreadable registry: brand
    resolution runs during setup for every managed vacuum, and one malformed stored
    value must not take the integration down. Each step degrades to the next with a
    log line.
    """
    override = _read_override(data, vacuum_entity_id)
    if override is not None:
        registrar = get_registrar(override)
        if registrar is not None:
            return registrar, "override"
        # An unknown id is a stale or hand-edited value. Fall through rather than
        # failing — but say so, because the user's stated intent is being ignored and
        # that should never be silent.
        _LOGGER.warning(
            "brands: ignoring unknown brand override %r for %s; falling back to the "
            "platform match",
            override,
            vacuum_entity_id,
        )

    platform = _vacuum_platform(hass, vacuum_entity_id)
    if platform is not None:
        for registrar in BRAND_REGISTRARS:
            if platform in registrar.platforms:
                return registrar, "platform"

    return None, UNSUPPORTED


def _vacuum_platform(hass: HomeAssistant, vacuum_entity_id: str) -> str | None:
    """Return the providing integration's domain for a vacuum entity, or None.

    Reads the ENTITY registry, not the device registry. HA sets ``platform`` from the
    integration that created the entity and it is never blank — which is exactly what
    the device registry's manufacturer/model are not, and why this module previously
    held that Eufy had no honest positive test to write.

    None means the vacuum is not in the entity registry at all (a YAML/template vacuum,
    or a lookup during teardown). That is a real answer and must fall through to the
    remaining arms rather than being treated as "no brand".
    """
    try:
        entry = er.async_get(hass).async_get(vacuum_entity_id)
    except Exception:  # pragma: no cover - defensive, mirrors the detect arm
        _LOGGER.debug(
            "brands: entity-registry read failed for %s", vacuum_entity_id, exc_info=True
        )
        return None
    return getattr(entry, "platform", None) if entry is not None else None


def _read_override(data: dict[str, Any] | None, vacuum_entity_id: str) -> str | None:
    """Pull an explicit brand choice out of storage. None when absent or unusable."""
    if not isinstance(data, dict):
        return None
    overrides = data.get(BRAND_OVERRIDES_KEY)
    if not isinstance(overrides, dict):
        return None
    value = overrides.get(vacuum_entity_id)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().lower()


def register_brand_adapter(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    *,
    data: dict[str, Any] | None = None,
) -> tuple[str | None, str]:
    """Resolve the brand and run its registrar. Returns ``(brand_id, source)``.

    ``brand_id`` is None when no adapter claims the vacuum. That is not an error and
    must not raise: the vacuum stays managed with no adapter config, which every
    consumer of ``get_adapter_config`` already handles (the registry has always been
    able to return None). What changes is that we now SAY it, naming the platform we did
    not recognise and the override that overrules us — instead of silently driving an
    unknown device as a Eufy.
    """
    registrar, source = resolve_brand(hass, vacuum_entity_id, data=data)

    if registrar is None:
        _LOGGER.warning(
            "eufy_vacuum: %s is not a supported vacuum — its entities are provided by "
            "the %r integration, which no installed adapter claims. It will be left "
            "unconfigured rather than driven with another brand's settings. If this is "
            "wrong, set a brand override for it in %r.",
            vacuum_entity_id,
            _vacuum_platform(hass, vacuum_entity_id) or "unknown",
            BRAND_OVERRIDES_KEY,
        )
        return None, source

    # Resolve the user's per-vacuum entity overrides HERE and hand the registrar
    # the finished dict. A brand must never learn the storage key: ISO-1 confines
    # brand packages to the adapter SDK, and "core owns the KEYS, never a brand's
    # words" is the same rule stated from the other side. The brand receives
    # meaning ({role: entity_id}), not our schema.
    _overrides = ((data or {}).get(ENTITY_OVERRIDES_KEY) or {}).get(vacuum_entity_id) or {}
    registrar.register(hass, vacuum_entity_id, entity_overrides=_overrides)
    _LOGGER.debug(
        "eufy_vacuum: registered %s adapter for %s (%s)",
        registrar.brand_id,
        vacuum_entity_id,
        source,
    )
    return registrar.brand_id, source
