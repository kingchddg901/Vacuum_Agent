"""Proof RP-034 (RF-17; Q7) — core-theme deletion does not survive, and imports are unvetted.

RP-034's reproducer_script names three recipes. The first ("overwrite with empty draft
-> target wiped to {}") is already driven verbatim by `_proof_theme_overwrite_source.py`;
this drives the other two. Together the pair covers the script. The rest of the 21
finding_ids (notify parity, draft lifecycle, PORT-2/5/7, CRUD-6/8) live in other
functions with their own mechanisms and are not driven here.

  1. A DELETED CORE THEME COMES BACK. delete_theme removes the entry outright and
     writes no record that the removal was intentional. ThemeManager.__init__ runs
     ensure_preloaded_theme_library, which re-adds every PRELOADED_THEME_SPECS id not
     currently in the library. So the delete survives exactly until the next restart.
     Constructing a second ThemeManager over the same data dict IS that restart — no
     mocking, the real seeder.

     The user's read of this is worse than a no-op: the theme disappears, they move on,
     and it silently returns days later. Packet clause (2): the delete must write a
     deleted_core_ids tombstone that the seeder consults.

  2. AN IMPORTED THEME CAN CARRY ANY KEY IT LIKES. import_theme checks that `tokens` IS
     a dict and never looks at what is IN it. Keys outside the --evcc-* namespace are
     stored verbatim, and the response reports no rejects, so nothing downstream or
     on-screen distinguishes a valid token from junk. Packet clause (5): keys are
     validated against the known-token allowlist and rejects are listed in the response
     -- "one bad file can no longer blank the card".

     The proof asserts BOTH halves of the after-state: the bad key is absent AND the
     response names it. Silently dropping it would leave the user with a theme that
     imported "successfully" and does not look right.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_theme_semantics.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.themes.manager import ThemeManager   # noqa: E402


def _core_theme_id(tm: ThemeManager) -> str:
    """The first library entry the seeder stamped source=='core'."""
    for tid, entry in tm._get_theme_data()["library"].items():
        if isinstance(entry, dict) and entry.get("source") == "core":
            return tid
    raise AssertionError("no core theme in the seeded library — harness assumption broke")


def case_deleted_core_theme_resurrects(proof: H.Proof) -> None:
    data: dict = {}
    tm = ThemeManager(data)
    core_id = _core_theme_id(tm)

    deleted = tm.delete_theme(theme_id=core_id)
    gone_immediately = core_id not in tm._get_theme_data()["library"]

    # RESTART: a second manager over the same stored dict re-runs the real seeder.
    tm_after_restart = ThemeManager(data)
    library = tm_after_restart._get_theme_data()["library"]
    resurrected = core_id in library
    tombstones = data["theme"].get("deleted_core_ids")

    proof.case(
        f"delete core theme {core_id!r}, then restart",
        before=deleted.get("ok") and gone_immediately and resurrected and not tombstones,
        before_msg="core theme resurrected — the delete took effect, nothing recorded "
                   "that it was intentional, and the seeder put it straight back on the "
                   "next construction; the user sees it vanish and silently return",
        after=deleted.get("ok") and gone_immediately and not resurrected
        and bool(tombstones) and core_id in tombstones,
        after_msg="the delete writes a deleted_core_ids tombstone the seeder consults, "
                  "so it stays deleted across restarts",
        detail=f"deleted ok={deleted.get('ok')} · gone before restart={gone_immediately} "
               f"· present after restart={resurrected} · tombstones={tombstones!r}",
    )


def case_import_stores_unvetted_keys(proof: H.Proof) -> None:
    tm = ThemeManager({})
    BAD = "--totally-not-a-real-token"
    GOOD = "--evcc-card-background"

    result = tm.import_theme(payload={
        "name": "imported by proof",
        "tokens": {GOOD: "#101014", BAD: "url(javascript:0)"},
    })

    entry = None
    for candidate in tm._get_theme_data()["library"].values():
        if isinstance(candidate, dict) and candidate.get("name") == "imported by proof":
            entry = candidate
            break
    stored_tokens = (entry or {}).get("tokens") or {}
    rejects = result.get("rejected") or result.get("rejected_keys") or []

    proof.case(
        "import a theme carrying one valid token and one key outside the --evcc-* namespace",
        before=result.get("ok") and BAD in stored_tokens and not rejects,
        before_msg="stored — import validates that `tokens` is a dict and never looks "
                   "at what is in it, so an arbitrary key lands in the library and the "
                   "response reports nothing wrong",
        # both halves: dropped AND reported. A silent drop leaves the user with a theme
        # that imported "successfully" and does not look right.
        after=result.get("ok") is not None and BAD not in stored_tokens
        and BAD in rejects and GOOD in stored_tokens,
        after_msg="the unknown key is rejected and NAMED in the response, while the "
                  "valid --evcc-* token is kept",
        detail=f"stored keys={sorted(stored_tokens)} · rejects reported={rejects!r} "
               f"· result keys={sorted(result)}",
    )


def main() -> None:
    proof = H.Proof("RP-034", "core deletes do not survive restart; imports are unvetted")
    case_deleted_core_theme_resurrects(proof)
    case_import_stores_unvetted_keys(proof)
    proof.finish()


H.run(main)
