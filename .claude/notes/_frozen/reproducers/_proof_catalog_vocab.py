"""Proof RP-025 (RF-18) — clauses (i) and (ii): Eufy literals leak past the catalog.

Two cases, out of 31 finding_ids across 5 required_behavior groups and 11
files -- the two cheapest, most self-contained mechanisms (both pure
functions in profiles/room_profiles.py, no manager/harness wiring needed).
The other three groups (iii: catalog threading through ProfileManager's
entry points; iv: capability-gated clean_intensity + protected-name catalog
union; v: display sets/backfill/estimator/lifecycle/dock-vocab/room-field
validation across 8 other files) are NOT driven here -- each is its own
independent mechanism, left for follow-up.

Clause (i) -- normalize_room_profile's third-arm literals (line 207-209:
fan_speed default "Max", water_level default "Off", clean_intensity default
"Quick" via normalize_clean_intensity's own arg) fire whenever BOTH the
profile being normalized AND the catalog's normalize_defaults omit a field
-- which is exactly the "brand declares nothing" case, i.e. a non-Eufy
adapter or no catalog at all. required_behavior: these three DISPLAY-AXIS
fields should become "" ("nobody said") there, matching the architectural
rule resolve_room_profile_for_room already follows for the same reason (its
own docstring at line 411-414: "Last-resort fallbacks are '' ... NOT Eufy
display literals ... this module quietly becoming a fourth source of Eufy
vocabulary"). normalize_room_profile is a SIBLING function serving the same
principle and currently violates it.

Clause (ii) -- resolve_profile_catalog (line 156-173) builds every catalog
key with `block.get(key) or <eufy_default>`. `or` treats any FALSY declared
value -- including a brand's deliberate `{}` ("this brand has no built-in
profiles") -- identically to the key being absent, silently injecting
Eufy's BUILT_IN_ROOM_PROFILES in its place. required_behavior: `key in
block` (presence, not truthiness) so a declared-empty block is honored.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_catalog_vocab.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.profiles.room_profiles import (   # noqa: E402
    normalize_room_profile,
    resolve_profile_catalog,
    BUILT_IN_ROOM_PROFILES,
)


def main() -> int:
    proof = H.Proof("RP-025", "clauses (i)+(ii): Eufy literals leak past a brand's own catalog")

    # -------------------------------------------------------------------
    # Case 1 (i): a brand-new custom profile with no catalog at all.
    # -------------------------------------------------------------------
    normalized = normalize_room_profile(None, catalog=None)

    proof.case(
        "normalize_room_profile called for a brand-new profile with no catalog "
        "(the 'brand declares nothing' case)",
        before=(
            normalized.get("fan_speed") == "Max"
            and normalized.get("water_level") == "Off"
            and normalized.get("clean_intensity") == "Quick"
        ),
        before_msg="the display-axis fields (fan/water/intensity) fall back "
                   "to hardcoded Eufy display literals -- a non-Eufy brand's "
                   "custom profile silently acquires Eufy's own vocabulary "
                   "with no brand ever having said so",
        after=(
            normalized.get("fan_speed") == ""
            and normalized.get("water_level") == ""
            and normalized.get("clean_intensity") == ""
        ),
        after_msg="display-axis fields fall back to '' ('nobody said'), "
                  "matching the same rule resolve_room_profile_for_room "
                  "already follows -- framework canonicals (path_type, "
                  "clean_passes, edge_mopping, mop_required, clean_mode) "
                  "are unaffected",
        detail=f"normalize_room_profile(None, catalog=None)={normalized}",
    )

    # -------------------------------------------------------------------
    # Case 2 (ii): a brand deliberately declares NO built-in profiles.
    # -------------------------------------------------------------------
    catalog = resolve_profile_catalog({"builtins": {}})

    proof.case(
        "an adapter's room_profiles block explicitly declares builtins={} "
        "(this brand ships no framework built-in profiles)",
        before=(catalog.get("builtins") == BUILT_IN_ROOM_PROFILES),
        before_msg="the `or` fallback treats the declared-empty dict as "
                   "'absent' identically to no block at all, silently "
                   "injecting Eufy's own BUILT_IN_ROOM_PROFILES -- the "
                   "brand's explicit 'we have none' is unrepresentable",
        after=(catalog.get("builtins") == {}),
        after_msg="`key in block` distinguishes declared-empty from absent "
                  "-- a brand can genuinely ship zero built-in profiles and "
                  "have that respected",
        detail=f"resolve_profile_catalog({{'builtins': {{}}}})['builtins']={catalog.get('builtins')}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
