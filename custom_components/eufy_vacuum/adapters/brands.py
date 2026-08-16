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

1. **platform** — the vacuum's ENTITY-registry ``platform`` appears in a registrar's
   declared ``platforms``. The adapter states its own identity in its ``const.py``;
   core only compares.
2. **unsupported** — nothing claimed it. No adapter is registered and we SAY SO.

NO PER-USER BRAND OVERRIDE — a decision, not a gap. What is supported is a specific
UPSTREAM INTEGRATION that has been tested, not a brand in the abstract: "Vacuum Agent
supports ``robovac_mqtt``" is the precise, testable claim. So:

- if a supported integration is renamed, WE change the declared platform and ship it —
  a maintenance commitment, not something pushed onto users;
- if someone wants an unsupported system driven, the answer is an ADAPTER, not a switch
  pointing an existing brand's vocabulary at hardware it was never written for. Anyone
  determined enough can rename the providing integration themselves, and is well past
  needing a supported affordance for it.

An earlier design had ``data["brand_overrides"]`` as a read path awaiting a UI. Removed:
nothing would ever write it, and a read path with no writer is a declaration defended by
a comment rather than by a reader.

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

⚠ This guard activates over EXISTING installs, and the only recovery is ours to ship.
The refusal therefore has to be a DIAGNOSIS: it names the providing integration, because
that string is exactly what we need in an issue to decide whether to add it.
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
# Support is now a POSITIVE, DECLARED statement: if no adapter claims a platform, we say
# so instead of guessing. There is no user-facing escape hatch by design — a rename is
# ours to follow, and an unsupported system wants an adapter, not an override.


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

    ``source`` is ``"platform"`` or ``"unsupported"`` — TWO values, matching the two
    arms in the module docstring. It said ``"override"`` as well until 2026-08-16, long
    after the override arm was deliberately removed; a documented return value the
    function cannot produce is worse than an undocumented one, because a caller can
    branch on it and the branch is simply dead.

    Never raises on an unreadable entity registry: brand resolution runs during setup
    for every managed vacuum, and one bad read must not take the integration down — it
    degrades to ``unsupported`` with a log line.

    FLAGGED, not fixed: ``data`` is no longer read. It carried the removed
    ``brand_overrides`` lookup, and callers still pass it. Dropping it is a signature
    change with call sites, so it is recorded here rather than done in passing.
    """
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
    ``unsupported`` arm rather than being treated as "no brand" — the two are the same
    outcome today, but only because ``unsupported`` is currently the only arm left.
    """
    try:
        entry = er.async_get(hass).async_get(vacuum_entity_id)
    except Exception:  # pragma: no cover - defensive
        _LOGGER.debug(
            "brands: entity-registry read failed for %s", vacuum_entity_id, exc_info=True
        )
        return None
    return getattr(entry, "platform", None) if entry is not None else None



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
    able to return None). What changes is that we now SAY it, naming the providing
    integration — instead of silently driving an unknown device as a Eufy.

    The message is a DIAGNOSIS, not an apology: that platform string is exactly what an
    issue needs for us to decide whether to support it, and it is the only recovery
    route there is.
    """
    registrar, source = resolve_brand(hass, vacuum_entity_id, data=data)

    if registrar is None:
        _LOGGER.warning(
            "eufy_vacuum: %s is not supported — its entities come from the %r "
            "integration, and Vacuum Agent supports %s. It will be left unconfigured "
            "rather than driven with another brand's settings. If you believe this "
            "integration should be supported, please open an issue and include the "
            "integration name above.",
            vacuum_entity_id,
            _vacuum_platform(hass, vacuum_entity_id) or "unknown",
            # set() first: two brands may legitimately declare the same providing
            # integration, and listing it twice in a user-facing message reads as a bug.
            ", ".join(sorted({
                p for r in BRAND_REGISTRARS for p in r.platforms
            })) or "no integrations",
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
