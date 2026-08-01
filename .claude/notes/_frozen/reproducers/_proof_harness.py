"""Shared fixtures for the tranche-2 reproducers (RP-010..RP-041).

Tranche 1's five proofs each rebuilt their own stubs, and most of the iteration
cost was rediscovering which attributes production actually touches. Tranche 2
needs ~33, so the stubs live here once.

═══════════════════════════════════════════════════════════════════════════════
THE INERTNESS RULE — read before adding anything to this module.
═══════════════════════════════════════════════════════════════════════════════
This harness provides ONLY inert scaffolding: empty dicts, no-op callbacks,
attribute-writable namespaces, tmp-backed real stores. It MUST NOT implement,
emulate, normalize, or "helpfully" correct any production behaviour.

Every proof drives the REAL production function and asserts on what that
function does. If a proof needs production logic, it imports it.

Why this rule is load-bearing: a harness that quietly normalized a value would
make all 33 proofs pass for the wrong reason simultaneously — the tranche-1
battery lesson (`_proof_battery.py`, kept as the cautionary example) multiplied
by 33. A wrong proof is worse than no proof: it certifies a defect as repaired.

If you catch yourself writing an `if` that decides a DOMAIN question here, it
belongs in the proof, not the harness.
═══════════════════════════════════════════════════════════════════════════════

Invocation (per MATERIALIZATION-01):

    docker run --rm -v "<repo>:/workspace" -w /workspace \
      -e PYTHONPATH=/workspace eufy-vacuum-test \
      python .claude/notes/_proof_<name>.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

VAC = "vacuum.alfred"
IVY = "vacuum.ivy"
MAP = "12"

_IDLE_LOOP: "asyncio.AbstractEventLoop | None" = None


# ---------------------------------------------------------------------------
# Verdict reporting — the before/after flip contract
# ---------------------------------------------------------------------------

class Proof:
    """Accumulates per-case verdicts and renders the flip report.

    Each case declares what BEFORE looks like and what AFTER looks like. The
    script prints the packet's expected_before fragments on unrepaired source
    and the expected_after fragments once repaired — same command, output diff
    IS the closure evidence. Anything that is neither exits 1 (UNEXPECTED
    SHAPE), because a proof that silently tolerates a third state proves
    nothing.
    """

    def __init__(self, packet: str, title: str) -> None:
        self.packet = packet
        self.title = title
        self._verdicts: list[tuple[str, str]] = []
        print(f"=== {packet} — {title} ===")

    def case(
        self,
        name: str,
        *,
        before: bool,
        before_msg: str,
        after: bool,
        after_msg: str,
        detail: str = "",
    ) -> str:
        """Record one case. `before`/`after` are the two recognised shapes.

        Both true is a BUG IN THE PROOF (the shapes must be mutually exclusive)
        and is reported as UNEXPECTED rather than silently preferring one.
        """
        print(f"\n--- {name} ---")
        if detail:
            print(f"    {detail}")
        if before and after:
            verdict = "UNEXPECTED"
            print(f"    UNEXPECTED SHAPE: before and after both matched — the "
                  f"proof's two shapes are not mutually exclusive")
        elif before:
            verdict = "BEFORE"
            print(f"    {before_msg}")
        elif after:
            verdict = "AFTER"
            print(f"    {after_msg}")
        else:
            verdict = "UNEXPECTED"
            print(f"    UNEXPECTED SHAPE: matched neither the pre-repair nor "
                  f"the post-repair contract")
        self._verdicts.append((name, verdict))
        return verdict

    def finish(self) -> int:
        counts = {v: sum(1 for _, x in self._verdicts if x == v)
                  for v in ("BEFORE", "AFTER", "UNEXPECTED")}
        print(f"\n=== {self.packet}: "
              + " · ".join(f"{n} {k}" for k, n in counts.items() if n)
              + f" ({len(self._verdicts)} cases) ===")
        if counts["UNEXPECTED"]:
            for name, v in self._verdicts:
                if v == "UNEXPECTED":
                    print(f"    unexpected: {name}")
            return 1
        return 0


# ---------------------------------------------------------------------------
# Inert hass / manager scaffolding
# ---------------------------------------------------------------------------

class FakeStates:
    """Minimal HA state machine: set/get only, real values, no normalisation."""

    def __init__(self) -> None:
        self._states: dict[str, Any] = {}

    def async_set(self, entity_id: str, state: Any, attributes: dict | None = None) -> None:
        self._states[entity_id] = SimpleNamespace(
            entity_id=entity_id, state=str(state), attributes=attributes or {})

    def get(self, entity_id: str):
        return self._states.get(entity_id)

    def async_remove(self, entity_id: str) -> None:
        self._states.pop(entity_id, None)


class FakeServices:
    """Records service calls verbatim. The RECORD is the assertion surface for
    dispatch proofs — never filter or interpret calls here."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._handlers: dict[tuple[str, str], Any] = {}
        self.fail_on: set[tuple[str, str]] = set()

    def async_register(self, domain, service, handler, **kw) -> None:
        self._handlers[(domain, service)] = handler

    def has_service(self, domain, service) -> bool:
        return (domain, service) in self._handlers

    def async_remove(self, domain, service) -> None:
        self._handlers.pop((domain, service), None)

    async def async_call(self, domain, service, data=None, **kw):
        self.calls.append({"domain": domain, "service": service,
                           "data": dict(data or {})})
        if (domain, service) in self.fail_on:
            raise RuntimeError(f"{domain}.{service} failed (proof fixture)")
        handler = self._handlers.get((domain, service))
        if handler is not None:
            return await handler(SimpleNamespace(data=dict(data or {})))
        return None

    def sent(self, domain=None, service=None) -> list[dict[str, Any]]:
        return [c for c in self.calls
                if (domain is None or c["domain"] == domain)
                and (service is None or c["service"] == service)]


class FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def async_fire(self, event_type, data=None) -> None:
        self.events.append((event_type, dict(data or {})))

    def async_listen(self, event_type, listener):
        return lambda: None

    def fired(self, event_type) -> list[dict]:
        return [d for t, d in self.events if t == event_type]


def make_hass(config_dir: str | Path = "/tmp/_proof_hass") -> SimpleNamespace:
    """A hass double with the surfaces production reaches for.

    async_add_executor_job runs the function INLINE — deliberately: proofs that
    care about the loop-yield boundary (the finalize-window class) must create
    that yield explicitly, so it is visible in the proof rather than an artefact
    of the harness.
    """
    # Python 3.14 no longer auto-creates a loop for a sync caller. Sync proofs
    # legitimately build a hass without one, so fall back to a fresh loop that
    # is never run — production only reads hass.loop.time() in those paths.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        global _IDLE_LOOP
        if _IDLE_LOOP is None:
            _IDLE_LOOP = asyncio.new_event_loop()
        loop = _IDLE_LOOP

    async def _executor(func, *args):
        return func(*args)

    hass = SimpleNamespace(
        data={},
        states=FakeStates(),
        services=FakeServices(),
        bus=FakeBus(),
        loop=loop,
        config=SimpleNamespace(
            config_dir=str(config_dir),
            path=lambda *p: str(Path(config_dir).joinpath(*p)),
        ),
        async_add_executor_job=_executor,
        async_create_task=lambda coro: loop.create_task(coro),
        async_block_till_done=_block_till_done,
    )
    return hass


async def _block_till_done() -> None:
    """Let spawned tasks run to completion (two passes catches task-spawns-task)."""
    for _ in range(4):
        await asyncio.sleep(0)


class ManagerStub:
    """Manager double: `data` is REAL, everything unknown is a no-op.

    Unknown-attribute no-ops keep a pre-repair path running to completion
    instead of dying on the stub — tranche 1 lost several iterations to exactly
    that (the wipe path continued past the wipe into derived-state refresh).
    A crash would look like "the defect didn't reproduce".

    Attributes production reads as a specific TYPE are declared explicitly
    below; add here (not via __getattr__) whenever a proof hits one.
    """

    def __init__(self, hass=None, data: dict | None = None) -> None:
        self.hass = hass
        self.data: dict[str, Any] = data if data is not None else {}
        # typed attributes production manipulates directly
        self._room_history_cache_ready: set[str] = set()
        self._room_history_cache_loading: set[str] = set()
        self._room_update_callbacks: list = []
        self._run_profile_update_callbacks: list = []
        self._room_history_update_callbacks: list = []
        self._room_rule_status_update_callbacks: list = []
        self._map_state_source_cache: dict[str, dict] = {}
        self.learning_processing_enabled = True

    def __getattr__(self, name):
        # only reached for genuinely unknown attributes
        def _noop(*a, **kw):
            return None
        return _noop

    def ensure_runtime(self, *a, **kw):
        return SimpleNamespace()

    def get_active_job(self, *, vacuum_entity_id: str, map_id: str) -> dict:
        """Returns the STORED dict (not a normalized copy) — proofs that need
        the production normalizer should call the real ActiveJobTracker."""
        return (
            self.data.get("active_jobs", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )

    def stored_job(self, *, vacuum_entity_id: str = VAC, map_id: str = MAP) -> dict:
        return (
            self.data.setdefault("active_jobs", {})
            .setdefault(vacuum_entity_id, {})
            .setdefault(str(map_id), {})
        )


# ---------------------------------------------------------------------------
# Fixture builders (data shapes only — no behaviour)
# ---------------------------------------------------------------------------

def active_job(
    *,
    vacuum_entity_id: str = VAC,
    map_id: str = MAP,
    status: str = "started",
    job_id: str = "job_proof",
    queue_room_ids: list[int] | None = None,
    phases: list[dict] | None = None,
    **extra: Any,
) -> dict:
    """A minimally-populated active-job record. Extra keys pass through so a
    proof can express the exact state its packet describes."""
    job = {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "job_id": job_id,
        "status": status,
        "started_at": "2026-08-01T00:00:00Z",
        "battery_start": 90,
        "queue_room_ids": list(queue_room_ids or [1]),
        "completed_room_ids": [],
        "completed_rooms": [],
        "resolved_rooms": [{"room_id": r, "slug": f"room_{r}", "name": f"Room {r}"}
                           for r in (queue_room_ids or [1])],
        "payload": {"segments": list(queue_room_ids or [1]), "repeat": 1},
    }
    if phases is not None:
        job["phases"] = phases
        job["phase_count"] = len(phases)
        job.setdefault("current_phase_index", 0)
    job.update(extra)
    return job


def room_phase(room_ids: list[int], **extra: Any) -> dict:
    phase = {
        "phase_type": "room_group",
        "queue_room_ids": list(room_ids),
        "resolved_rooms": [{"room_id": r, "slug": f"room_{r}", "name": f"Room {r}"}
                           for r in room_ids],
        "payload": {"segments": list(room_ids), "repeat": 1},
    }
    phase.update(extra)
    return phase


def break_phase(phase_type: str = "charge_wait", **extra: Any) -> dict:
    phase = {"phase_type": phase_type, "queue_room_ids": [], "resolved_rooms": []}
    phase.update(extra)
    return phase


def managed_rooms(*room_ids: int, **per_room: Any) -> dict[str, dict]:
    return {
        str(r): {
            "room_id": r, "name": f"Room {r}", "slug": f"room_{r}",
            "enabled": True, "is_configured": True, "order": i,
            **per_room,
        }
        for i, r in enumerate(room_ids)
    }


def seed_map(manager: ManagerStub, rooms: dict, *,
             vacuum_entity_id: str = VAC, map_id: str = MAP) -> dict:
    bucket = {"map_id": str(map_id), "metadata": {}, "rooms": rooms, "summary": {}}
    manager.data.setdefault("maps", {}).setdefault(vacuum_entity_id, {})[str(map_id)] = bucket
    return bucket


def learning_store(tmp: str | Path):
    """A REAL LearningHistoryStore rooted at tmp — file behaviour is production's."""
    from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore
    return LearningHistoryStore(make_hass(tmp))


def async_noop(return_value: Any = None):
    """An awaitable no-op. Assign EXPLICITLY onto a stub for each async collaborator
    a proof needs — deliberately not auto-provided by __getattr__, so every awaited
    collaborator is visible in the proof rather than silently absorbed."""
    async def _stub(*a, **kw):
        return return_value
    return _stub


def corrupt(path: Path) -> bytes:
    """Make a JSON file unreadable while leaving its bytes recoverable."""
    healthy = path.read_bytes()
    path.write_bytes(healthy + b"\n<<TORN>>")
    return path.read_bytes()


def run(main_coro_or_fn) -> None:
    """Entry point: handles sync and async proof mains identically."""
    result = main_coro_or_fn()
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    sys.exit(result or 0)
