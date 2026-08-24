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

#: Write outcomes. THREE, not two, and the third is the point: a write we could not
#: CONFIRM is not a write we know failed. The device may well have taken it. Reporting
#: `unconfirmed` keeps "checked and wrong" apart from "could not check" -- the same
#: three-state distinction the UI design calls for (amber / green / grey), and the
#: reason an infrastructure failure never has to read as a device refusal.
WRITE_OK = "ok"
WRITE_UNCONFIRMED = "unconfirmed"
WRITE_UNSUPPORTED = "unsupported"
WRITE_REFUSED = "refused"

#: The marker an adapter puts where the ordered ids belong. Replaced WHOLESALE, never
#: string-interpolated -- a template that stringifies its substitution is how a list
#: becomes "[27, 25]" on the wire (Chris, 2026-08-20).
ORDER_SENTINEL = "$order"


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
    """Collects decoded results matching a PREDICATE. Best effort.

    A logging handler that raises would surface as a logging error on an unrelated
    library's emit path, so every failure is swallowed.

    The predicate is a parameter rather than the hardcoded clean-order shape because
    the WRITE path captures a reply off the same line with a different shape: the read
    matches a flat list of known room ids, the write matches the literal ack
    ``['ok']`` — which ``is_clean_order`` correctly REFUSES (it is a ``list[str]``).
    One capture window, two questions.

    ⚠ THE READ'S PREDICATE STAYS MEMBERSHIP-BASED AND THAT IS LOAD-BEARING. The module
    docstring records the ablation: drop the known-room-id membership check and the
    ``[0]`` emitted every poll tick is accepted as a clean order. Parameterising the
    question must not become an invitation to weaken it to a type check.
    """

    def __init__(self, *, decoded_prefix: str, predicate) -> None:
        super().__init__(level=logging.DEBUG)
        self._prefix = decoded_prefix
        self._predicate = predicate
        self.matches: list[Any] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            result = parse_decoded_result(record.getMessage(), self._prefix)
            if result is not None and self._predicate(result):
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
        #: vacuum_entity_id -> the order WE last wrote. Provenance for Clear; see
        #: last_written. In-memory like the cache: after a restart we no longer claim
        #: authorship, which fails toward asking rather than toward wiping.
        self._written: dict[str, list[int]] = {}
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
        handler = _MatchHandler(
            decoded_prefix=decoded_prefix,
            predicate=lambda result: is_clean_order(result, known),
        )
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

    # ------------------------------------------------------------------ write

    def can_write(self, vacuum_entity_id: str) -> bool:
        """Whether this vacuum's adapter declares a clean-order WRITE.

        Separate from ``is_supported`` (which gates the read and the sensor) because
        the two are genuinely independent: every declaring brand can be READ, and only
        a brand whose write mechanism has been established declares the write half.

        ⚠ THE ROBOROCK DECLARATION IS MODEL-GATED, NOT BRAND-GATED. ``set_clean_sequence``
        is the V1 device protocol; newer Qrevo/B01 models answer a DIFFERENT transport
        (``service.set_room_order`` on ``RoborockB01Q7Methods``). Declaring the write
        for every Roborock would ship a control that silently does nothing on those —
        the exact declaration-with-no-wire shape this codebase keeps finding. The
        adapter includes the block only for families where the V1 namespace applies,
        and an unknown model gets nothing.
        """
        cfg = self._config(vacuum_entity_id)
        return bool(isinstance(cfg, dict) and isinstance(cfg.get("write"), dict))

    def last_written(self, vacuum_entity_id: str) -> list[int] | None:
        """The order WE last wrote, or None.

        PROVENANCE, and it is what makes Clear honest. If the device order matches this,
        we put it there and clearing it destroys nothing of the user's. If it differs,
        they changed it in their own app since — say so before wiping it. Without this
        the two cases are indistinguishable and Clear becomes a coin flip on someone
        else's data.
        """
        return self._written.get(vacuum_entity_id)

    async def async_write(
        self, vacuum_entity_id: str, order: list[int]
    ) -> dict[str, Any]:
        """Write an explicit clean order to the device. Returns {"status", "order"}.

        ⚠ THIS EDITS A PERSISTENT, MAP-LEVEL USER SETTING IN THE VENDOR APP. It is not
        scoped to one run: a saved sequence orders EVERY start, including ones the user
        begins from the Roborock app, and it renders in their app's own Sequence screen
        as numbered badges. Anything user-facing that triggers this must say so —
        "this changes the saved sequence in your Roborock app", never "for this run".

        SET IS A FULL REPLACE (proven live 2026-08-19): one write of [27, 25, 23, 22]
        overwrote [24, 22, 25] outright. There is no merge, no incremental op and so no
        partial state to recover from, which is why a failed verify can simply re-fire.
        """
        cfg = self._config(vacuum_entity_id)
        write_cfg = (cfg or {}).get("write")
        if not isinstance(write_cfg, dict):
            return {"status": WRITE_UNSUPPORTED, "order": None}

        # Refuse an order we cannot vouch for. Every id must be a managed room on the
        # active map: writing an id the user does not manage puts a room into their
        # saved sequence that our UI will never show them.
        known = self.known_room_ids(vacuum_entity_id)
        clean: list[int] = []
        for raw in order or []:
            try:
                rid = int(raw)
            except (TypeError, ValueError):
                return {"status": WRITE_REFUSED, "order": None}
            if isinstance(raw, bool) or rid not in known:
                return {"status": WRITE_REFUSED, "order": None}
            if rid in clean:
                return {"status": WRITE_REFUSED, "order": None}  # a duplicate is not an order
            clean.append(rid)

        return await self._write_payload(vacuum_entity_id, write_cfg, "payload", clean)

    async def async_clear(self, vacuum_entity_id: str) -> dict[str, Any]:
        """Clear the device's saved order so it path-optimises again.

        ``clear`` is declared by the adapter rather than derived from an empty
        ``payload``, because "the empty case" is a BRAND FACT: an empty list clears
        Roborock, but another brand might need an explicit null, a sentinel, or a
        different command entirely. Deriving it would be core inventing a brand's word.
        """
        cfg = self._config(vacuum_entity_id)
        write_cfg = (cfg or {}).get("write")
        if not isinstance(write_cfg, dict) or not isinstance(write_cfg.get("clear"), dict):
            return {"status": WRITE_UNSUPPORTED, "order": None}
        return await self._write_payload(vacuum_entity_id, write_cfg, "clear", [])

    async def _write_payload(
        self,
        vacuum_entity_id: str,
        write_cfg: dict[str, Any],
        key: str,
        order: list[int],
    ) -> dict[str, Any]:
        """Substitute, fire, and try to confirm. Never raises."""
        via = str(write_cfg.get("via") or "")
        if via != "v1_send_command":
            _LOGGER.debug(
                "eufy_vacuum: clean-order write strategy %r not implemented for %s",
                via, vacuum_entity_id,
            )
            return {"status": WRITE_UNSUPPORTED, "order": None}

        template = write_cfg.get(key)
        service = write_cfg.get("service") or {}
        domain, name = service.get("domain"), service.get("service")
        if not (isinstance(template, dict) and domain and name):
            return {"status": WRITE_UNSUPPORTED, "order": None}

        # WHOLESALE substitution: the sentinel is replaced by the LIST, not rendered
        # into a string. Only an exact-match value is a hole -- a sentinel embedded in
        # a longer string is left alone rather than half-substituted, because a partial
        # match here would put a mangled payload on the wire.
        payload = {
            k: (list(order) if v == ORDER_SENTINEL else v)
            for k, v in template.items()
        }

        ack_cfg = write_cfg.get("ack") if isinstance(write_cfg.get("ack"), dict) else {}
        expected = ack_cfg.get("equals")
        source_logger = str(ack_cfg.get("source_logger") or "")
        decoded_prefix = str(ack_cfg.get("decoded_prefix") or "")

        # No ack declared, or no capture machinery for it: fire and report UNCONFIRMED.
        # Never OK -- an unverified write must not present as a verified one.
        if not (expected is not None and source_logger and decoded_prefix):
            await self._fire(domain, name, vacuum_entity_id, payload=payload)
            self._written[vacuum_entity_id] = list(order)
            return {"status": WRITE_UNCONFIRMED, "order": list(order)}

        logger = logging.getLogger(source_logger)
        handler = _MatchHandler(
            decoded_prefix=decoded_prefix,
            predicate=lambda result: result == expected,
        )
        prior_level = logger.level
        prior_propagate = logger.propagate
        confirmed = False
        try:
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
            logger.addHandler(handler)

            await self._fire(domain, name, vacuum_entity_id, payload=payload)

            waited = 0.0
            while waited < _READ_TIMEOUT_S and not handler.matches:
                await asyncio.sleep(_POLL_S)
                waited += _POLL_S
            confirmed = bool(handler.matches)
        except Exception:  # pragma: no cover - defensive
            _LOGGER.debug(
                "eufy_vacuum: clean-order write failed for %s", vacuum_entity_id,
                exc_info=True,
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(prior_level)
            logger.propagate = prior_propagate

        # Record provenance on EITHER outcome. An unconfirmed write may well have
        # landed -- the ack is how we learn, not whether it happened -- so forgetting it
        # would make a Clear we DID cause look like the user's own sequence.
        self._written[vacuum_entity_id] = list(order)
        # The cache now describes a device we just changed; the old read is stale.
        self._store(vacuum_entity_id, list(order) if confirmed else None,
                    STATUS_OK if confirmed else STATUS_UNAVAILABLE)
        return {
            "status": WRITE_OK if confirmed else WRITE_UNCONFIRMED,
            "order": list(order),
        }

    async def _fire(
        self,
        domain: str,
        name: str,
        vacuum_entity_id: str,
        command: Any = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Send a command. Swallows a missing/unsupported service — the caller
        then simply finds no match and reports unavailable/unconfirmed.

        Takes either a bare ``command`` (the read) or a whole adapter-declared
        ``payload`` (the write). One firing point rather than two, so the
        service-unavailable degradation is written once.
        """
        from homeassistant.exceptions import HomeAssistantError

        data = {"entity_id": vacuum_entity_id}
        data.update(payload if payload is not None else {"command": command})
        try:
            await self.hass.services.async_call(
                domain,
                name,
                data,
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.debug(
                "eufy_vacuum: clean-order service %s.%s unavailable for %s (%s)",
                domain, name, vacuum_entity_id, err,
            )
