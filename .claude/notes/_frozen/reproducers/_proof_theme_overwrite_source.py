"""Proof RP-034 (RF-17; Q7) — overwrite_theme's resolution source is wrong.

Two cases, out of 21 finding_ids across CRUD/DRAFT/PORT groups -- both trace
to the SAME four-line root cause in overwrite_theme (themes/manager.py:
298-308), matching the packet's own reproducer_script recipe verbatim
("overwrite with empty draft (before: target wiped to {}; after: refused)").
The other named example (core delete -> restart-sim tombstone) and every
CRUD/PORT/DRAFT/notify-parity finding are NOT driven here -- left for a
follow-up pass; provenance/tombstone/import-allowlist logic lives in
different functions with their own mechanisms, not this one.

overwrite_theme reads:
    vac = self._get_vacuum_theme(vacuum_entity_id)
    active_id = str(vac.get("active_theme_id") or "").strip()
    active_entry = library.get(active_id) if active_id else None
    resolved = self._resolved_theme_payload(active_entry=active_entry, draft=...)
    existing = library[theme_id]                    # <- the actual TARGET, unused as a base
    entry = {..., "tokens": dict(resolved.get("tokens", {})), ...}
    theme["library"][theme_id] = entry               # <- persisted verbatim, replacing "existing"

_resolved_theme_payload's base is `active_entry` (line 195: `_normalize_theme_entry
(active_entry)`) -- the CURRENTLY ACTIVE theme -- never `existing` (the target
library entry actually being overwritten). Q7 requires the opposite: "resolved
= target's own palette + draft applied over it ... NEVER the active theme as
source." Two independently observable consequences of this ONE wrong variable:
  (a) an empty/no-op draft with no active theme resolves to an entirely empty
      base -- the target is silently wiped to {} rather than refused.
  (b) a non-empty draft, with an ACTIVE theme that differs from the target,
      resolves against the ACTIVE theme's tokens -- the target's own
      untouched-by-the-draft values are replaced by the active theme's
      (including keys the target never had at all), not preserved.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_theme_overwrite_source.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.themes.manager import ThemeManager   # noqa: E402

VAC = H.VAC


def main() -> int:
    proof = H.Proof("RP-034", "Q7: overwrite_theme resolves against the ACTIVE theme, not the target")

    # -------------------------------------------------------------------
    # Case 1: empty draft, no active theme -> target silently wiped to {}.
    # -------------------------------------------------------------------
    data1: dict = {}
    tm1 = ThemeManager(data1)
    tm1._get_theme_data()["library"]["target-theme"] = {
        "id": "target-theme", "name": "Sunset",
        "tokens": {"--evcc-bg": "#111111", "--evcc-fg": "#eeeeee"},
        "colors": {"--evcc-accent": "#ff8800"}, "alpha": {},
    }
    vac1 = tm1._get_vacuum_theme(VAC)
    vac1["active_theme_id"] = None
    vac1["working_draft"] = {"tokens": {}, "colors": {}, "alpha": {}}

    result1 = tm1.overwrite_theme(vacuum_entity_id=VAC, theme_id="target-theme")
    target_after1 = tm1._get_theme_data()["library"]["target-theme"]

    proof.case(
        "overwrite_theme called with an empty working draft and no active theme set",
        before=(result1.get("ok") is True and target_after1.get("tokens") == {}),
        before_msg="ok:True is returned but the target's real content "
                   "(2 tokens + 1 color) is gone, replaced with an entirely "
                   "empty palette -- a silent, unrequested wipe reported as success",
        after=(result1.get("ok") is False),
        after_msg="an empty/unresolvable draft refuses ({success:false, "
                  "reason:...}) instead of silently overwriting the target "
                  "with nothing",
        detail=f"result={result1} · target tokens after={target_after1.get('tokens')}",
    )

    # -------------------------------------------------------------------
    # Case 2: non-empty draft, ACTIVE theme differs from target -> target's
    # own untouched values are replaced by the ACTIVE theme's, not preserved.
    # -------------------------------------------------------------------
    data2: dict = {}
    tm2 = ThemeManager(data2)
    lib2 = tm2._get_theme_data()["library"]
    lib2["target-theme"] = {
        "id": "target-theme", "name": "Forest",
        "tokens": {"--evcc-bg": "#111111", "--evcc-fg": "#eeeeee"},
        "colors": {}, "alpha": {},
    }
    lib2["other-active-theme"] = {
        "id": "other-active-theme", "name": "Ocean",
        "tokens": {"--evcc-bg": "#000000", "--evcc-fg": "#ffffff", "--evcc-warn": "#ff0000"},
        "colors": {}, "alpha": {},
    }
    vac2 = tm2._get_vacuum_theme(VAC)
    vac2["active_theme_id"] = "other-active-theme"
    # The draft only touches --evcc-fg -- --evcc-bg is meant to survive UNTOUCHED.
    vac2["working_draft"] = {"tokens": {"--evcc-fg": "#dddddd"}, "colors": {}, "alpha": {}}

    result2 = tm2.overwrite_theme(vacuum_entity_id=VAC, theme_id="target-theme")
    target_after2 = tm2._get_theme_data()["library"]["target-theme"]
    tokens_after2 = target_after2.get("tokens", {})

    proof.case(
        "the draft edits ONE token; the ACTIVE theme (a DIFFERENT theme than the target) "
        "has its own distinct values for the target's untouched token, plus a token the "
        "target never had at all",
        before=(
            tokens_after2.get("--evcc-bg") == "#000000"  # leaked from the ACTIVE theme
            and "--evcc-warn" in tokens_after2            # leaked, target never had this key
        ),
        before_msg="the target's own --evcc-bg (#111111) is silently replaced "
                   "by the ACTIVE theme's (#000000), and --evcc-warn (a key "
                   "the target never declared) leaks in from the active "
                   "theme -- resolution used the wrong theme as its base",
        after=(
            tokens_after2.get("--evcc-bg") == "#111111"   # the target's own, preserved
            and "--evcc-warn" not in tokens_after2         # never leaked in
            and tokens_after2.get("--evcc-fg") == "#dddddd"  # the actual draft edit still lands
        ),
        after_msg="resolution bases on the TARGET's own existing entry, with "
                  "only the draft's actual edits overlaid -- untouched target "
                  "values survive, nothing leaks in from whatever happens to "
                  "be active",
        detail=f"result={result2} · target tokens after={tokens_after2}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
