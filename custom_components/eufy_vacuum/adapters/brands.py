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
2. **detected** — the first registrar whose ``detect`` returns True, in table order.
3. **default** — the terminal registrar (``is_default=True``, exactly one).

The default arm is DECLARED, not structural, and ``resolve_brand`` reports which of the
three routes was taken so the caller can log it. That distinction is the point: "this is
a Eufy" and "we could not tell, so we assumed Eufy" are different facts, and until now
they produced identical, silent behaviour.

Eufy carries no ``detect`` at all — deliberately. The Eufy adapter never reads the device
registry for manufacturer/model, so there is no honest positive test to write, and
inventing one would dress an assumption up as an identification. A Eufy install resolves
via ``default``, which is the truth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.core import HomeAssistant

from .eufy.adapter import register_eufy_adapter_for_vacuum
from .roborock.adapter import (
    is_roborock_vacuum,
    register_roborock_adapter_for_vacuum,
)

_LOGGER = logging.getLogger(__name__)

#: Storage key holding explicit per-vacuum brand choices
#: (``{vacuum_entity_id: brand_id}``). Distinct from ``data["adapters"]``, which holds a
#: whole stored adapter CONFIG — this is only the choice of which registrar to run.
BRAND_OVERRIDES_KEY = "brand_overrides"


@dataclass(frozen=True)
class BrandRegistrar:
    """One brand's detection + registration pair.

    ``detect`` is positive identification only — it must never return True on a
    "probably" — and may be None for a brand that has no honest test (see the module
    docstring). ``register`` assembles and registers that brand's adapter config for one
    vacuum and is idempotent.
    """

    brand_id: str
    register: Callable[[HomeAssistant, str], None]
    detect: Callable[[HomeAssistant, str], bool] | None = None
    is_default: bool = False


#: Ordered; the first positive ``detect`` wins. Exactly one entry is ``is_default``.
#:
#: Eufy is last AND the default, which preserves the previous ``else``-arm behaviour
#: byte-for-byte: a vacuum that is not identifiably a Roborock is registered as a Eufy.
#: That is deliberate rather than aspirational — ``is_roborock_vacuum`` reads the device
#: registry, which is sparse or absent on real installs, and a Eufy with a blank
#: manufacturer has always landed here and worked. Making no-match a refusal would break
#: those users to fix a purity problem; revisit once the UI selector exists to recover.
BRAND_REGISTRARS: tuple[BrandRegistrar, ...] = (
    BrandRegistrar(
        brand_id="roborock",
        register=register_roborock_adapter_for_vacuum,
        detect=is_roborock_vacuum,
    ),
    BrandRegistrar(
        brand_id="eufy",
        register=register_eufy_adapter_for_vacuum,
        detect=None,
        is_default=True,
    ),
)


def get_default_registrar() -> BrandRegistrar:
    """The terminal arm. Raises if the table declares none — a wiring error, not runtime."""
    for registrar in BRAND_REGISTRARS:
        if registrar.is_default:
            return registrar
    raise RuntimeError(
        "BRAND_REGISTRARS declares no default arm; exactly one entry must set is_default"
    )


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
) -> tuple[BrandRegistrar, str]:
    """Return ``(registrar, source)`` for one vacuum.

    ``source`` is ``"override"`` / ``"detected"`` / ``"default"`` — see the module
    docstring. Never raises for a bad override or a detector that throws: brand
    resolution runs during setup for every managed vacuum, and one malformed stored value
    or one unhappy device-registry read must not take the integration down. Both
    degrade to the next step with a log line.
    """
    override = _read_override(data, vacuum_entity_id)
    if override is not None:
        registrar = get_registrar(override)
        if registrar is not None:
            return registrar, "override"
        # An unknown id is a stale or hand-edited value. Fall through to detection
        # rather than failing — but say so, because the user's stated intent is being
        # ignored and that should never be silent.
        _LOGGER.warning(
            "brands: ignoring unknown brand override %r for %s; falling back to detection",
            override,
            vacuum_entity_id,
        )

    for registrar in BRAND_REGISTRARS:
        if registrar.detect is None:
            continue
        try:
            if registrar.detect(hass, vacuum_entity_id):
                return registrar, "detected"
        except Exception:  # pragma: no cover - defensive
            _LOGGER.debug(
                "brands: %s detection failed for %s",
                registrar.brand_id,
                vacuum_entity_id,
                exc_info=True,
            )

    return get_default_registrar(), "default"


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
) -> tuple[str, str]:
    """Resolve the brand and run its registrar. Returns ``(brand_id, source)``.

    The single call site in ``async_setup_entry``. Logs at DEBUG for a positively
    identified or explicitly chosen brand, and at INFO when the default arm was reached
    by no-match — that line is the one that used to not exist, and it is what tells a
    user with an unrecognised vacuum why it is being driven as a Eufy.
    """
    registrar, source = resolve_brand(hass, vacuum_entity_id, data=data)
    registrar.register(hass, vacuum_entity_id)
    if source == "default":
        _LOGGER.info(
            "eufy_vacuum: %s was not identified as any supported brand; "
            "registering the default (%s) adapter",
            vacuum_entity_id,
            registrar.brand_id,
        )
    else:
        _LOGGER.debug(
            "eufy_vacuum: registered %s adapter for %s (%s)",
            registrar.brand_id,
            vacuum_entity_id,
            source,
        )
    return registrar.brand_id, source
