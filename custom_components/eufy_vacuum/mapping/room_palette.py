"""Room-fill colour cascade — the BACKEND half of the card's ``map-room-color.js``.

WHY THIS EXISTS, AND WHY IT IS A COPY. The card resolves a room's fill through one
cascade, defined once in ``src/cards/map-room-color.js``::

    per-room override (room.color)  ->  theme token --evcc-room-fill-<N>  ->  default palette

That module exists BECAUSE the SVG fill path and the raster fill path were two
byte-identical hardcoded copies that had to be unified. This module is a third copy, in a
second language, and that is only acceptable because it is GATED: ``tests/unit/
test_room_palette_parity.py`` reads the JavaScript and fails the build when the two
palettes diverge. An ungated copy would drift, and the symptom would be a notification
image that quietly stops matching the map on screen — with nothing reporting it.

Do not "improve" the colours here. If the palette should change, change
``ROOM_FILL_PALETTE`` in the JS and let the gate tell you to update this one.

WHAT DIFFERS FROM THE JS, AND WHY. Only the theme layer. The card reads the resolved
custom property off a mounted node (``getComputedStyle``) because a canvas cannot take CSS
variables. There is no CSSOM here, so :func:`room_fill_rgb` takes the stored theme
``tokens`` mapping instead — the same values, one layer earlier. Everything else ports
line for line.

Pure: no Home Assistant imports, no I/O. Import it from a renderer or a test freely.
"""

from __future__ import annotations

import re
from typing import Any

#: The canonical default room-fill palette (12 colours). MUST equal ROOM_FILL_PALETTE in
#: src/cards/map-room-color.js — the parity test is what makes that true.
ROOM_FILL_PALETTE: tuple[str, ...] = (
    "#00e5ff", "#ff6b35", "#a3e635", "#e879f9",
    "#fbbf24", "#a78bfa", "#fb7185", "#34d399",
    "#60a5fa", "#f472b6", "#4ade80", "#f97316",
)

ROOM_FILL_N = len(ROOM_FILL_PALETTE)

#: Returned by :func:`hex_to_rgb` for anything unparseable — matching the JS, which paints
#: grey rather than raising when a theme token holds a non-hex value.
_GREY: tuple[int, int, int] = (128, 128, 128)

_HEX6 = re.compile(r"^#[0-9a-f]{6}$")
_HEX3 = re.compile(r"^#[0-9a-f]{3}$")


def slot(idx: Any) -> int:
    """Wrap any (possibly negative / fractional) index into a 0..N-1 palette slot."""
    try:
        i = int(float(idx))
    except (TypeError, ValueError):
        i = 0
    return ((i % ROOM_FILL_N) + ROOM_FILL_N) % ROOM_FILL_N


def room_fill_token_name(idx: Any) -> str:
    """The 1-based theme-token name for palette slot ``idx`` (0-based, wraps)."""
    return f"--evcc-room-fill-{slot(idx) + 1}"


def room_fill_default(idx: Any) -> str:
    """The default hex for palette slot ``idx`` (0-based, wraps)."""
    return ROOM_FILL_PALETTE[slot(idx)]


def normalize_hex(value: Any) -> str | None:
    """Canonical ``#rrggbb`` (lowercased), or None for anything that is not a valid hex.

    None means "no override", so the caller falls through to the theme/default layer. This
    is the single gate for the per-room layer — a cleared, empty or garbage value must
    reach the next layer rather than painting something.
    """
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    if not s:
        return None
    if not s.startswith("#"):
        s = f"#{s}"
    if _HEX6.match(s):
        return s
    if _HEX3.match(s):
        return f"#{s[1]}{s[1]}{s[2]}{s[2]}{s[3]}{s[3]}"
    return None


def hex_to_rgb(value: Any) -> tuple[int, int, int]:
    """Parse ``#rgb`` / ``#rrggbb`` to ``(r, g, b)``; grey for anything else.

    Grey rather than an exception is deliberate and matches the JS: a theme token may hold
    a value this cannot parse (a CSS function, a named colour), and a map that renders in
    grey is recoverable where a raised exception on a job-lifecycle path is not.
    """
    h = str("" if value is None else value).replace("#", "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{6}", h):
        n = int(h, 16)
        return ((n >> 16) & 255, (n >> 8) & 255, n & 255)
    if re.fullmatch(r"[0-9a-fA-F]{3}", h):
        n = int("".join(c * 2 for c in h), 16)
        return ((n >> 16) & 255, (n >> 8) & 255, n & 255)
    return _GREY


def room_fill_rgb(idx: Any, tokens: dict[str, Any] | None = None) -> tuple[int, int, int]:
    """RGB for palette slot ``idx``, honouring a theme token when one is set.

    ``tokens`` is the stored theme's token mapping (the backend's stand-in for the card's
    ``getComputedStyle`` read). Absent or unset token → the default palette, so a themeless
    install renders exactly the default colours.

    Resolve ONCE per render and index the result per pixel — never call this per pixel.
    """
    hex_value = room_fill_default(idx)
    if isinstance(tokens, dict):
        token = tokens.get(room_fill_token_name(idx))
        if isinstance(token, str) and token.strip():
            hex_value = token.strip()
    return hex_to_rgb(hex_value)


def room_override_rgb(value: Any) -> tuple[int, int, int] | None:
    """RGB for a per-room override, or None when it is not a valid hex.

    None, NOT grey — the caller must fall through to the palette rather than painting a
    fallback colour over a room whose override was simply cleared.
    """
    hex_value = normalize_hex(value)
    return None if hex_value is None else hex_to_rgb(hex_value)


def resolve_room_rgb(
    *,
    idx: Any,
    override: Any = None,
    tokens: dict[str, Any] | None = None,
) -> tuple[int, int, int]:
    """The full cascade in one call: override → theme token → default palette.

    The card applies these three layers in two different places (inline SVG fill, and the
    raster's per-rid map). Backend callers have only the raster case, so the whole cascade
    collapses to this.
    """
    return room_override_rgb(override) or room_fill_rgb(idx, tokens)
