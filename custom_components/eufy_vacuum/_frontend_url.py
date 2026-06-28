"""Helpers for the panel JS URL with cache busting.

The HA frontend service worker caches static panel assets aggressively. To
avoid having to bump a hard-coded ``?v=N`` query string on every bundle deploy
we fingerprint the bundle's mtime and append it to the URL.

Re-registering the panel (HA restart or config entry reload) is still required
for browsers to pick up the new URL — but that already happens whenever a
Python change is in the same deploy, and is faster than the manual bump.
"""

from __future__ import annotations

import os

_BUNDLE_PATH = os.path.join(
    os.path.dirname(__file__), "frontend", "eufy-vacuum-command-center.js"
)
_BASE_URL = "/eufy_vacuum/frontend/eufy-vacuum-command-center.js"

_CARDS_BUNDLE_PATH = os.path.join(
    os.path.dirname(__file__), "frontend", "eufy-vacuum-cards.js"
)
_CARDS_BASE_URL = "/eufy_vacuum/frontend/eufy-vacuum-cards.js"


def panel_js_url() -> str:
    """Return the panel JS URL with a mtime-based cache-busting query string."""
    try:
        mtime = int(os.path.getmtime(_BUNDLE_PATH))
    except OSError:
        mtime = 0
    return f"{_BASE_URL}?v={mtime}"


def cards_module_url() -> str | None:
    """Return the global cards-bundle module URL (mtime cache-busted), or None.

    The standalone cards (room-card + dashboard card) ship in this panel-free
    bundle, registered as a GLOBAL frontend module so they're defined on every
    page — including a cold dashboard that never opens the sidebar panel. Returns
    None when the bundle isn't present (an older/partial deploy) so the caller can
    skip registration rather than advertise a URL that 404s on every page.
    """
    try:
        mtime = int(os.path.getmtime(_CARDS_BUNDLE_PATH))
    except OSError:
        return None
    return f"{_CARDS_BASE_URL}?v={mtime}"
