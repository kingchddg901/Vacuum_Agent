"""Reconcile `_landed_packets.json` with what git says actually landed.

WHY THIS EXISTS. OPEN-FIX-CHECKLIST.md is generated from this manifest — its
header even says "Generated from the audit JSON, not from recollection". But the
manifest recorded 20 packets while 58 had landed, so every regeneration reverted
38 packets' `[x] applied` marks to `[ ]`, and someone had been hand-patching the
`[x]` back INTO the generated file. A hand edit to a generated doc survives until
the next `python _gen_checklist.py` and then vanishes silently.

Consequence while it was wrong: the ledger claimed "165 findings applied via 20
packets" and "319 open" — so anyone scoping remaining work from it would re-do
finished packets, or believe several times more work was outstanding than really
was. That is the doc-vs-code drift this whole campaign exists to catch, sitting
in the campaign's own bookkeeping.

WHAT IT DOES. Scans git for `RP-xxx` / `CARD-x` mentions in commit subjects,
takes the earliest commit per packet as its landing, and merges into the existing
manifest. EXISTING ENTRIES ARE NEVER OVERWRITTEN — notes and, critically, the
`hardware` blocks (which carry evidence file paths and are the only record that a
packet met a real vacuum) are preserved verbatim.

Run:  python .claude/notes/_sync_landed_packets.py [--write]
Then: python .claude/notes/_gen_checklist.py
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / ".claude" / "notes" / "_landed_packets.json"
CLOSURE_MAP = ROOT / ".claude" / "notes" / "synthesis" / "packet-closure-map.json"

PACKET = re.compile(r"\b(RP-\d+[a-f]?|CARD-\d+)\b")

#: PARTIALLY landed packets — code exists for SOME of their findings, not all.
#: Held out of the manifest entirely, because a packet_id in _landed_packets.json
#: closes every finding_id in its closure-map entry, WHOLE. There is no partial
#: state, so recording one of these would mark unwritten fixes as applied — the
#: exact fabricated closure this script exists to prevent, just from the other
#: direction (the manifest being too GENEROUS rather than too stale).
#:
#: Remove the entry once the packet is complete and the next sync picks it up.
_PARTIAL: dict[str, str] = {
    "RP-021b": (
        "3 of 5 findings landed (f208788 A4-PP-RP-2 CRITICAL, 4c93fb5 A4-PP-RP-6, "
        "0fa6cd9 A4-PP-RP-1). STILL OPEN: #8:A4-PP-RP-4 (applied-profile stamp + "
        "third step source in _build_effective_start_plan — deliberately parked, "
        "it changes step-source precedence and wants a hardware baseline first) "
        "and #13:A5-RUNPROF-4 (per-step service schema + structured refusal). "
        "_proof_profile_roundtrip.py correctly still reports 1 BEFORE."
    ),
}

#: Packets whose CODE landed under a commit subject that never named them, so no
#: amount of git-subject scanning can find them. Curated by hand, each with the
#: source evidence that it really is implemented — because the whole point of this
#: script is to stop the ledger asserting things it cannot show.
#:
#: All three rode in on 40cbaac, a phased-jobs commit that swept in a concurrent
#: session's files (battery/manager.py +310 lines among them). Verified present in
#: current source, not inferred from the commit: battery/manager.py carries the
#: RP-043/RP-044 precedence inversion in compute_time_to_target_pct's docstring and
#: the session_open_without_own_sample branch, and RP-045's
#: health_qualifying_sessions retention plus _session_cc_qualifies /
#: _session_cv_qualifies. Contract tests landed separately as 075e6cf (BM-26..28).
_LANDED_OFF_SUBJECT = {
    "RP-043": ("40cbaac", "2026-08-03",
               "Code landed inside 40cbaac (a phased-jobs commit that swept in a "
               "concurrent session's battery/manager.py). Verified in source: the "
               "zone-rate-over-baseline precedence in compute_time_to_target_pct."),
    "RP-044": ("40cbaac", "2026-08-03",
               "Code landed inside 40cbaac. Verified in source: the "
               "session_open_without_own_sample branch that skips a previous "
               "charge's carried-over stats. Tests 075e6cf."),
    "RP-045": ("40cbaac", "2026-08-03",
               "Code landed inside 40cbaac. Verified in source: "
               "health_qualifying_sessions plus decoupled _session_cc_qualifies / "
               "_session_cv_qualifies in battery/manager.py."),
}


#: A packet LANDS when code changes. Commits under these roots are the campaign's
#: own paperwork — packet docs, proofs, ledgers, freeze manifests.
_CODE_ROOTS = ("custom_components/", "src/", "tests/", "scripts/", "harness/")


def _touches_code(sha: str) -> bool:
    files = subprocess.run(
        ["git", "-C", str(ROOT), "show", "--stat=200", "--format=", "--name-only", sha],
        capture_output=True, check=True,
    ).stdout.decode("utf-8", "replace").split()
    return any(f.startswith(_CODE_ROOTS) for f in files)


def git_landings() -> dict[str, dict]:
    """packet_id -> {commits (oldest first), landed_at, doc_only_commits}.

    MENTION IS NOT LANDING. The obvious heuristic — earliest commit whose subject
    names the packet — is WRONG here, and dangerously so: this campaign commits
    `materialize RP-043 + RP-044` (writes the packet doc and its proof) and
    `audit: RP-042 corrected` (edits the spec) long before, or entirely without,
    the fix. All three touch only `.claude/notes/`. Recording those as landings
    would stamp a landed_at on packets whose code never shipped and mark their
    findings applied — inventing closure, which is worse than the staleness this
    script exists to repair.

    So a landing requires a commit that changed production or test code. Doc-only
    mentions are counted separately and reported, never used.
    """
    out = subprocess.run(
        ["git", "-C", str(ROOT), "log", "--reverse",
         "--format=%h\x1f%ad\x1f%s", "--date=short"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8", "replace")

    found: dict[str, dict] = {}
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        sha, date, subject = parts
        # Only the SUBJECT — a body may merely discuss another packet.
        for pid in dict.fromkeys(PACKET.findall(subject)):
            entry = found.setdefault(
                pid, {"commits": [], "landed_at": None, "doc_only": []})
            if _touches_code(sha):
                entry["commits"].append(sha)
                if entry["landed_at"] is None:
                    entry["landed_at"] = date
            else:
                entry["doc_only"].append(sha)
    return found


def main() -> int:
    write = "--write" in sys.argv
    existing = {p["packet_id"]: p for p in json.loads(
        MANIFEST.read_text(encoding="utf-8"))}
    known = {p["packet_id"] for p in json.loads(
        CLOSURE_MAP.read_text(encoding="utf-8"))}
    landings = git_landings()

    added, unknown, already, doc_only, partial = [], [], [], [], []
    for pid, info in sorted(landings.items()):
        if pid in existing:
            already.append(pid)
            continue
        if pid in _PARTIAL:
            partial.append(pid)
            continue
        if not info["commits"]:
            curated = _LANDED_OFF_SUBJECT.get(pid)
            if curated:
                sha, date, note = curated
                added.append({"packet_id": pid, "commits": [sha],
                              "landed_at": date, "note": note})
                continue
            # Mentioned in git, but every mention was paperwork. NOT landed.
            doc_only.append((pid, len(info["doc_only"])))
            continue
        if pid not in known:
            # A packet git mentions but the closure map has never heard of closes
            # nothing and must not be invented into the ledger.
            unknown.append(pid)
            continue
        added.append({
            "packet_id": pid,
            "commits": info["commits"],
            "landed_at": info["landed_at"],
            "note": "Landed per git (first commit touching code); back-filled by "
                    "_sync_landed_packets.py.",
        })

    print(f"already recorded : {len(already)}")
    print(f"to back-fill     : {len(added)}")
    if partial:
        print(f"PARTIAL — held out so unwritten fixes are not marked applied: {len(partial)}")
        for pid in partial:
            print(f"  ~ {pid}: {_PARTIAL[pid]}")
    print(f"MENTIONED but DOC-ONLY — not landed, correctly skipped: {len(doc_only)}"
          + (f" -> {[p for p, _ in doc_only]}" if doc_only else ""))
    print(f"git-only, not in closure map (SKIPPED): {len(unknown)}"
          + (f" -> {unknown}" if unknown else ""))
    for entry in added:
        print(f"  + {entry['packet_id']:9} {entry['commits'][0]}  {entry['landed_at']}"
              f"  ({len(entry['commits'])} code commit(s))")

    if not write:
        print("\nDRY RUN — re-run with --write to apply.")
        return 0

    merged = list(existing.values()) + added
    merged.sort(key=lambda p: (p["packet_id"].split("-")[0], p["packet_id"]))
    MANIFEST.write_text(
        json.dumps(merged, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    hw = sum(1 for p in merged if p.get("hardware"))
    print(f"\nwrote {len(merged)} packets ({hw} carrying a hardware block — preserved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
