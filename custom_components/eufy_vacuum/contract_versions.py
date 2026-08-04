"""Mechanism-contract versions for mechanism-sensitive reproducers.

The retired-mechanism staleness class (audit-2 charter §4 delta 6): a design can
change without its output STRUCTURE changing — the accumulated completed-rooms
field became a derived index and both yield a set of room ids — so nothing
textual fails and a proof written against the old mechanism keeps passing while
certifying the wrong thing.

This registry is production's half of the fix. A proof that asserts a MECHANISM
(not an outcome) declares the version it was written against via
``Proof.require_contract(name, version)``; bumping the constant here when the
mechanism is deliberately replaced makes every stale proof recuse itself loudly
instead of banking a verdict.

Narrow BY DESIGN — this is the one place a declared premise earns its cost.
Outcome-asserting proofs must not appear here; add an entry only when a repair
deliberately replaces HOW something is computed while preserving WHAT it yields.
Bump the version in the SAME commit as the mechanism change.
"""

from __future__ import annotations

CONTRACT_VERSIONS: dict[str, int] = {
    # Completed-room evidence: v2 = derived index over phase/room timings.
    # v1 (accumulated completed_room_ids field) retired 2026-08-03 — the change
    # that produced _proof_completed_evidence.py's silent staleness.
    "completed_room_evidence": 2,
}
