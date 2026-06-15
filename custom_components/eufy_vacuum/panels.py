"""Sidebar panel registration helpers.

One sidebar panel is registered per managed vacuum (url ``eufy-vacuum-<object_id>``,
web component ``eufy-vacuum-command-center``). The sidebar TITLE is per-vacuum and
user-settable: it's stored on the managed-vacuum record (``panel_title``) and
defaults to ``"Vacuum Agent"`` when unset, so two vacuums no longer show two
identical sidebar entries once renamed.

This module is the single source of truth for that registration so the three call
sites — startup (``__init__.async_setup_entry``), add-a-vacuum
(``setup/workflow.add_vacuum``), and the live rename service
(``services/setup.setup_set_panel_title``) — all compute the title and register
the panel identically. ``panel_custom.async_register_panel`` raises ``ValueError``
on a duplicate url, so a live rename removes the existing panel first
(``replace=True``).
"""

from __future__ import annotations

import logging

from homeassistant.components import frontend, panel_custom
from homeassistant.core import HomeAssistant

from ._frontend_url import panel_js_url

_LOGGER = logging.getLogger(__name__)

DEFAULT_PANEL_TITLE = "Vacuum Agent"
PANEL_ICON = "mdi:robot-vacuum"
WEBCOMPONENT_NAME = "eufy-vacuum-command-center"


def panel_url_for(vacuum_entity_id: str) -> str:
    """The frontend url path for a vacuum's panel (``eufy-vacuum-<object_id>``)."""
    object_id = vacuum_entity_id.split(".", 1)[-1]
    return f"eufy-vacuum-{object_id}"


def effective_panel_title(record: dict | None) -> str:
    """The sidebar title for a managed-vacuum record.

    Returns the user-set ``panel_title`` when present and non-blank, else the
    default ``"Vacuum Agent"`` (so unset/older records are unchanged).
    """
    title = str((record or {}).get("panel_title") or "").strip()
    return title or DEFAULT_PANEL_TITLE


async def async_register_vacuum_panel(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    *,
    title: str,
    replace: bool = False,
) -> str | None:
    """Register (or live re-register) one vacuum's sidebar panel.

    With ``replace=True`` an existing panel at the same url is removed first so the
    ``sidebar_title`` can change without a restart (``async_register_panel`` raises
    ``ValueError`` on a duplicate url). Returns the registered url path, or ``None``
    when it was already registered (``replace=False`` + duplicate).
    """
    panel_url = panel_url_for(vacuum_entity_id)
    if replace:
        try:
            frontend.async_remove_panel(hass, panel_url)
        except Exception:  # pragma: no cover - defensive (panel may not exist)
            _LOGGER.debug(
                "eufy_vacuum: no existing panel /%s to replace", panel_url, exc_info=True
            )
    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=panel_url,
            webcomponent_name=WEBCOMPONENT_NAME,
            js_url=panel_js_url(),
            sidebar_title=title,
            sidebar_icon=PANEL_ICON,
            config={"vacuum_entity_id": vacuum_entity_id},
            require_admin=False,
            embed_iframe=False,
        )
        _LOGGER.debug(
            "eufy_vacuum: registered panel /%s for %s (title=%r)",
            panel_url, vacuum_entity_id, title,
        )
        return panel_url
    except ValueError:
        _LOGGER.debug("eufy_vacuum: panel /%s already registered", panel_url)
        return None
