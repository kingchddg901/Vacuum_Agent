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


def panel_js_url() -> str:
    """Return the panel JS URL with a mtime-based cache-busting query string."""
    try:
        mtime = int(os.path.getmtime(_BUNDLE_PATH))
    except OSError:
        mtime = 0
    return f"{_BASE_URL}?v={mtime}"
