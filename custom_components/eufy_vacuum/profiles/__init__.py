"""Profiles subsystem for the Eufy Vacuum integration.

Exposes:
- ProfileManager — owns room-profile and run-profile CRUD.
  Constructed inside EufyVacuumManager after storage is loaded.

room_profiles.py holds the KEY SPACE, the normalize helpers and the resolve
logic, and is importable directly via ``profiles.room_profiles``. It holds NO
built-in presets: its own banner reads "There is NO framework default catalog
and no fallback", and ``get_default_room_profiles`` returns
``deepcopy(cat.get("builtins") or {})`` under the docstring "There are no
in-code built-ins to fall back to". The presets are a BRAND's words and moved
to ``adapters/eufy/room_profiles.py`` on 2026-08-07 — that file says so in its
own opening line.

⚠ was: "The existing room_profiles.py module (built-in presets, normalize
helpers, resolve logic) is unchanged and continues to be importable directly."
Only the last clause survived. This is the package's front door, so a reader
looking for the built-in profile catalog was sent to room_profiles.py and found
none — and "unchanged" positively discouraged checking whether the module still
works the way the paragraph described, which is the whole point of the
core-owns-keys-not-words split.
"""

from __future__ import annotations

from .manager import ProfileManager

__all__ = ["ProfileManager"]
