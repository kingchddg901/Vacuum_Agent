"""Device clean ORDER — read the order the vacuum will clean its rooms in.

WHAT THIS IS
------------
Some brands hold a device-side cleaning ORDER that overrides their own path
optimisation. Roborock calls it a "Sequence" and exposes it in their app; the device
answers ``get_clean_sequence`` with a flat list of segment ids, in the SAME id space as
our ``room_id``. Empty list means no order is set and the robot optimises the path
itself.

Core stays brand-free: everything device-specific is adapter-declared under
``device_clean_order`` and this module evaluates it generically. A brand that omits the
block is disabled = a no-op, and no sensor is created.

WHY THE READ IS AWKWARD (the whole reason this module exists)
-------------------------------------------------------------
``vacuum.send_command`` is **SupportsResponse.NONE** — asking for ``return_response``
is an HTTP 400. The command fires, the device answers, and HA drops the answer on the
floor. The reply surfaces in exactly one place, a DEBUG line in python-roborock::

    roborock/protocols/v1_protocol.py
    _LOGGER.debug("Decoded V1 message result: %s", result)

So a readback means attaching a logging handler to that logger for a short window.
**This modifies nothing in roborock or python-roborock and needs nothing installed by a
user** — ``logging.getLogger(name)`` returns a process-global singleton, so we attach to
the object they already log to. Same mechanism ``debug_capture.py`` uses: save level +
propagate, attach, restore in a ``finally``.

THE DECODED LINE DOES NOT SAY WHICH COMMAND IT ANSWERS.
Disambiguation is by SHAPE: a clean order is a flat list whose members are ALL known
room ids. Validated against 53 real decoded results (2026-08-19): 4 matches, all 4 from
a command we fired, zero unprompted. The shapes it must reject::

    [{'msg_ver': 2, 'state': 8, ...}]        status
    [{'main_brush_work_time': ...}]          consumables
    [{'start_hour': 22, ...}]                do-not-disturb
    [734826, 11824807500, 336, [...]]        clean summary
    [0]                                      <- THE TRAP, emitted every poll tick
    [[1787200920, 1787201244, ...]]          clean record
    ['ok']                                   a write ack

``[0]`` is why membership in the known-room-id set is load-bearing and must never be
weakened to a type check: ablated, the sensor reports ``[0]`` as an order every ~15 s.

REPOINTING
----------
``read.via`` selects the acquisition strategy, so swapping to a proper response is a
DECLARATION change, not a code change. When upstream registers ``get_clean_sequence``
with ``SupportsResponse.ONLY`` (as ``get_vacuum_current_position`` already is in that
same integration), add a ``service_response`` strategy here and flip ``via``. The cache,
the sensor and every consumer stay untouched.

READ IS NEVER PASSIVE. We only accept a match inside the window after firing our own
command. Do not turn this into a background listener — the ``[]`` shape is only
unambiguous because nothing else in the poll cycle returns an empty list, and that is an
observation about today's poll set, not a guarantee.
"""

from __future__ import annotations

import ast
import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any

from ..adapters.registry import get_adapter_config as _get_adapter_config
from ..timestamp_utils import utc_now_iso

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

#: How long to wait for the device's reply after firing the read, in seconds. The
#: observed round trip is well under a second; this is slack, not a target.
_READ_TIMEOUT_S = 3.0

#: Poll granularity while waiting. The handler runs on whichever thread logging emits
#: from, so we poll a list rather than await an Event across a thread boundary.
_POLL_S = 0.1

#: Cache status values. ``unavailable`` and an EMPTY ORDER are different facts and must
#: never collapse into one field — an empty order means the device path-optimises, an
#: unavailable read means we know nothing at all.
STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"
STATUS_NEVER_READ = "never_read"


def parse_decoded_result(line: str, decoded_prefix: str) -> Any | None:
    """The decoded python literal from one log line, or None if it isn't one.

    Never raises: an unparseable payload must degrade to "no reading", not to an
    exception on a path a live run can touch.
    """
    plain = re.sub(r"\x1b\[[0-9;]*m", "", line)
    idx = plain.find(decoded_prefix)
    if idx < 0:
        return None
    try:
        return ast.literal_eval(plain[idx + len(decoded_prefix):].strip())
    except (ValueError, SyntaxError):
        return None


def is_clean_order(result: Any, known_room_ids: set[int]) -> bool:
    """Is this decoded result a clean-order reply?

    A flat list whose members are ALL known room ids; empty means cleared.

    ``known_room_ids`` membership is the load-bearing condition — see the module
    docstring's ``[0]`` note. ``bool`` is excluded explicitly because
    ``isinstance(True, int)`` is True in Python.
    """
    if not isinstance(result, list):
        return False
    if not result:
        return True
    return all(
        isinstance(x, int) and not isinstance(x, bool) and x in known_room_ids
        for x in result
    )


class _MatchHandler(logging.Handler):
    """Collects decoded results matching the clean-order shape. Best effort.

    A logging handler that raises would surface as a logging error on an unrelated
    library's emit path, so every failure is swallowed.
    """

    def __init__(self, *, decoded_prefix: str, known_room_ids: set[int]) -> None:
        super().__init__(level=logging.DEBUG)
        self._prefix = decoded_prefix
        self._known = known_room_ids
        self.matches: list[Any] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            result = parse_decoded_result(record.getMessage(), self._prefix)
            if result is not None and is_clean_order(result, self._known):
                self.matches.append(result)
        except Exception:  # pragma: no cover - defensive, must never break logging
            pass


class CleanOrderManager:
    """Owns the device clean-order cache and the read that fills it.

    Constructed with the core manager (the bundled-subsystem pattern), same as
    ``LiveRoomRefreshManager``. Reads adapter config; owns no persistence — the cache is
    in-memory and a restart simply re-reads.
    """

    def __init__(self, *, manager: "EufyVacuumManager") -> None:
        self._manager = manager
        #: vacuum_entity_id -> {"order": list[int]|None, "read_at": iso, "status": str}
        self._cache: dict[str, dict[str, Any]] = {}
        #: Serialises reads. The logger's level is PROCESS-GLOBAL state, so two
        #: concurrent reads would fight: the first to finish restores the level and
        #: truncates the other's capture. Reads are rare; serialising is cheaper than
        #: refcounting and cannot get the bookkeeping wrong.
        self._read_lock = asyncio.Lock()

    @property
    def hass(self):  # noqa: D401 - thin accessor onto the core manager's hass
        return self._manager.hass

    # ------------------------------------------------------------------ config

    def _config(self, vacuum_entity_id: str) -> dict[str, Any]:
        """The adapter's ``device_clean_order`` block, or {} when not declared."""
        cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("device_clean_order")
        return cfg if isinstance(cfg, dict) and cfg.get("enabled") else {}

    def is_supported(self, vacuum_entity_id: str) -> bool:
        """Does this vacuum's adapter declare a device-side clean order at all?

        The sensor is created only where this is True, so a brand that omits the block
        gains no entity rather than an entity that is permanently unknown.
        """
        return bool(self._config(vacuum_entity_id))

    # ------------------------------------------------------------------ cache

    def cached(self, vacuum_entity_id: str) -> dict[str, Any]:
        """The last read for this vacuum. Never None — an unread vacuum reports
        ``never_read`` rather than an empty order, because those are different facts."""
        return self._cache.get(vacuum_entity_id) or {
            "order": None,
            "read_at": None,
            "status": STATUS_NEVER_READ,
        }

    def _store(self, vacuum_entity_id: str, order: list[int] | None, status: str) -> None:
        self._cache[vacuum_entity_id] = {
            "order": order,
            "read_at": utc_now_iso(),
            "status": status,
        }

    # ------------------------------------------------------------------ rooms

    def known_room_ids(self, vacuum_entity_id: str) -> set[int]:
        """Managed room ids on the vacuum's active map — the shape filter's vocabulary.

        Empty when the map isn't ready, which makes a read fail closed: with no known
        ids, only ``[]`` could match, so we decline to read at all rather than accept a
        list we cannot validate.
        """
        map_id = self._manager.resolve_active_map_id(vacuum_entity_id)
        if not map_id:
            return set()
        rooms = (
            self._manager.get_managed_rooms(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id
            )
            or {}
        ).get("rooms", {}) or {}
        out: set[int] = set()
        for key in rooms:
            try:
                out.add(int(key))
            except (TypeError, ValueError):
                continue
        return out

    # ------------------------------------------------------------------ read

    async def async_read(self, vacuum_entity_id: str) -> dict[str, Any]:
        """Read the device's clean order and cache it. Returns the cache entry.

        Best effort: every failure path caches ``unavailable`` and returns, because a
        diagnostic read must never raise into a caller that might be mid-dispatch.
        """
        cfg = self._config(vacuum_entity_id)
        read_cfg = cfg.get("read") if cfg else None
        if not isinstance(read_cfg, dict):
            return self.cached(vacuum_entity_id)

        via = str(read_cfg.get("via") or "")
        if via != "v1_debug_log":
            # An unknown strategy is a declaration we do not implement yet — the
            # repoint seam. Fail as unavailable, never guess.
            _LOGGER.debug(
                "eufy_vacuum: clean-order read strategy %r not implemented for %s",
                via, vacuum_entity_id,
            )
            self._store(vacuum_entity_id, None, STATUS_UNAVAILABLE)
            return self.cached(vacuum_entity_id)

        known = self.known_room_ids(vacuum_entity_id)
        if not known:
            # No vocabulary to validate against — see known_room_ids.
            self._store(vacuum_entity_id, None, STATUS_UNAVAILABLE)
            return self.cached(vacuum_entity_id)

        async with self._read_lock:
            order = await self._read_via_v1_debug_log(vacuum_entity_id, read_cfg, known)

        if order is None:
            self._store(vacuum_entity_id, None, STATUS_UNAVAILABLE)
        else:
            self._store(vacuum_entity_id, list(order), STATUS_OK)
        return self.cached(vacuum_entity_id)

    async def _read_via_v1_debug_log(
        self, vacuum_entity_id: str, read_cfg: dict[str, Any], known: set[int]
    ) -> list[int] | None:
        """Fire the read command and capture the reply off the source logger.

        Returns the order (possibly empty), or None when nothing matched.
        """
        source_logger = str(read_cfg.get("source_logger") or "")
        decoded_prefix = str(read_cfg.get("decoded_prefix") or "")
        service = read_cfg.get("service") or {}
        command = read_cfg.get("command")
        domain, name = service.get("domain"), service.get("service")
        if not (source_logger and decoded_prefix and domain and name and command):
            return None

        logger = logging.getLogger(source_logger)
        handler = _MatchHandler(decoded_prefix=decoded_prefix, known_room_ids=known)
        prior_level = logger.level
        prior_propagate = logger.propagate
        try:
            # DEBUG only for this window, and propagate off so the diverted DEBUG
            # firehose never reaches the user's main log. Their INFO+ is unaffected:
            # we restore both in the finally, and we add a handler rather than
            # replacing theirs.
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
            logger.addHandler(handler)

            await self._fire(domain, name, vacuum_entity_id, command)

            waited = 0.0
            while waited < _READ_TIMEOUT_S and not handler.matches:
                await asyncio.sleep(_POLL_S)
                waited += _POLL_S
            # Last match wins: the poll batch can interleave, and our reply is the
            # most recent thing to arrive after our own command.
            return handler.matches[-1] if handler.matches else None
        except Exception:  # pragma: no cover - defensive
            _LOGGER.debug(
                "eufy_vacuum: clean-order read failed for %s", vacuum_entity_id,
                exc_info=True,
            )
            return None
        finally:
            logger.removeHandler(handler)
            logger.setLevel(prior_level)
            logger.propagate = prior_propagate

    async def _fire(
        self, domain: str, name: str, vacuum_entity_id: str, command: Any
    ) -> None:
        """Send the read command. Swallows a missing/unsupported service — the caller
        then simply finds no match and caches ``unavailable``."""
        from homeassistant.exceptions import HomeAssistantError

        try:
            await self.hass.services.async_call(
                domain,
                name,
                {"entity_id": vacuum_entity_id, "command": command},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.debug(
                "eufy_vacuum: clean-order read service %s.%s unavailable for %s (%s)",
                domain, name, vacuum_entity_id, err,
            )
