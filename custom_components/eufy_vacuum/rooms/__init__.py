"""Room discovery and managed room configuration for the Eufy Vacuum integration.

Exposes:
- AccessGraphManager — room access graph validation and automation rule evaluation.
  Constructed inside EufyVacuumManager after storage is loaded.
- RoomMapManager — discover, save, read, remove, and rebuild room/map CRUD.
  Constructed inside EufyVacuumManager after storage is loaded.

The package holds NINE modules, all importable directly: access_graph.py,
reconciliation.py, room_crud.py, room_defaults.py, room_discovery.py,
room_manager.py, source_refresh.py, utils.py and vocabulary_migration.py.
Only AccessGraphManager and RoomMapManager are re-exported here; everything
else is reached by its own module path.

⚠ was: "The existing room_discovery.py, room_manager.py, and utils.py modules
are unchanged and continue to be importable directly." This is the package
docstring — the first thing a reader opens to learn what ``rooms/`` holds — and
it named three of the nine while asserting those three were unchanged, which
reads as "nothing here has moved since the split". Only the importable clause
survived. room_discovery.py in particular has been substantially rewritten
since: the source/shape branch split (``room_list_shape``, 2026-08-07), the
``_single_cached_map_id`` fallback (ISSUE #46), the
``_implicit_attribute_map_id`` path, and the INCFMPP1 slug-disambiguation pass
are all later additions. The old sentence also gave no pointer at all to
room_defaults.py, reconciliation.py, source_refresh.py or
vocabulary_migration.py.
"""

from __future__ import annotations

from .access_graph import AccessGraphManager
from .room_crud import RoomMapManager

__all__ = ["AccessGraphManager", "RoomMapManager"]
