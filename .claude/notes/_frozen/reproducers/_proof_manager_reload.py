"""Proof (RP-003 / #14:A1-INIT-1): a reloaded entry's PREVIOUS manager can still run
and write. Nothing cancels manager-referencing callbacks on unload, and async_save has
no closed-guard — so a timer armed by manager A fires after B has taken over and
clobbers the shared store with A's stale data.

Structure: manager A armed with a debounced-save callback (as async_call_later /
listeners do), unload simulated (today: nothing to call — the class exposes no
shutdown seam), manager B constructed over the same store and saves, then A's
captured callback fires.

Run: docker eufy-vacuum-test -> python .claude/notes/_proof_manager_reload.py
"""
import asyncio
import sys
from types import SimpleNamespace

from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

SHUTDOWN_NAMES = ("async_shutdown", "shutdown", "async_close", "async_unload")


def make_hass():
    return SimpleNamespace(
        config=SimpleNamespace(config_dir="/tmp/_proof_hass",
                               path=lambda *p: "/tmp/_proof_hass/" + "/".join(p)),
        data={},
    )


class FakeDisk:
    """Stands in for the ONE shared .storage file both managers write."""
    def __init__(self):
        self.content = None
        self.writes = []

    def bind(self, label):
        disk = self

        class _Storage:
            async def async_save(self, data):
                disk.content = dict(data)
                disk.writes.append(label)
        return _Storage()


async def main() -> int:
    disk = FakeDisk()

    # --- entry setup #1 -------------------------------------------------------
    a = EufyVacuumManager(make_hass())
    a.storage = disk.bind("A")
    a.data = {"owner": "A", "vacuums": {"vacuum.alfred": {"stale": True}}}

    # a listener/timer armed during A's life captures A (exactly what
    # async_call_later callbacks in this integration hold):
    async def armed_callback():
        await a.async_save()

    # --- unload ---------------------------------------------------------------
    present = [n for n in SHUTDOWN_NAMES if callable(getattr(a, n, None))]
    if present:
        result = await getattr(a, present[0])()
        cancelled = (result or {}).get("timers_cancelled",
                                       getattr(a, "_cancelled_count", ""))
        print(f"shutdown seam found: {present[0]}")
        print(f"timers cancelled: {cancelled}")
    else:
        print("no shutdown seam on EufyVacuumManager "
              f"(checked {', '.join(SHUTDOWN_NAMES)}) — unload cannot reach A")

    # --- entry setup #2 -------------------------------------------------------
    b = EufyVacuumManager(make_hass())
    b.storage = disk.bind("B")
    b.data = {"owner": "B", "vacuums": {"vacuum.alfred": {"stale": False}}}
    await b.async_save()
    assert disk.content["owner"] == "B"

    # --- A's captured callback fires (timer expiry post-unload) ---------------
    await armed_callback()

    owner = (disk.content or {}).get("owner")
    print(f"store owner after A's late callback: {owner!r}  (write order: {disk.writes})")
    if owner == "A":
        print("stale manager saved after unload")
        print("B's data was replaced by the unloaded manager's copy")
    elif owner == "B":
        print("stale save suppressed")
    else:
        print(f"UNEXPECTED SHAPE: owner={owner!r}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
