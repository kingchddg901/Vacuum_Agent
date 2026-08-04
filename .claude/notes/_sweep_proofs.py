"""Run every reproducer and classify it — hunting for STALE proofs.

Chris, 2026-08-03: "check for proof changes."

WHY. _proof_inflight_askers.py reported UNEXPECTED SHAPE on a CORRECT fix. It
stubbed `get_job_progress_snapshot`, which was the listener's call when it was
written; RP-037 b/3 (7b53ed4, SNAP-2) made that a pure read and moved the ticker
onto `apply_job_progress_tick`. The proof kept watching the old name.

That is the campaign's rule — "run the reproducer, not just pytest" — failing
from the other side: it assumes the reproducer still measures production. A
refactor can silently retarget one, the full suite stays green, and nobody finds
out until somebody happens to work that packet. Four packets landed today from a
concurrent session (RP-035/036/037/039), touching core/manager.py,
jobs/active_job.py, jobs/job_monitor.py, learning/*, listeners/*, panels.py,
debug_capture.py and diagnostics.py. Any proof watching a symbol they moved is
now suspect.

CLASSIFICATION — the distinction that matters:
  AFTER       the fix landed and still holds. Good.
  BEFORE      the packet has not landed. EXPECTED, not a problem — RP-017/023/041
              are open by design.
  UNEXPECTED  the proof matched neither contract. THIS is the stale signal.
  ERROR       crashed — import moved, signature changed, fixture gone. Also stale.

So a green sweep is "no UNEXPECTED and no ERROR", NOT "everything AFTER".

Run: python .claude/notes/_sweep_proofs.py
     (needs docker — proofs import the integration; see scripts/test.bat)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROOFS = sorted(p for p in (ROOT / ".claude" / "notes").glob("_proof_*.py"))

DOCKER = [
    "docker", "run", "--rm",
    "-v", f"{ROOT}:/workspace", "-w", "/workspace",
    "-e", "PYTHONPATH=/workspace", "eufy-vacuum-test",
]

# Proofs print a tally like "=== RP-014: 2 BEFORE · 1 AFTER (3 cases) ==="
TALLY = re.compile(r"===\s*([\w\-/]+):\s*(.+?)\s*\((\d+) cases?\)\s*===")


def classify(out: str, code: int) -> tuple[str, str]:
    # Harness v2 renders compromised files as "QUARANTINED — 0 of N admissible"
    # (uninvoked stub / contract recusal / unexpected shape). More specific than
    # the bare UNEXPECTED check, so it goes first.
    if "QUARANTINED" in out:
        reason = next((l.strip() for l in out.splitlines()
                       if any(k in l for k in ("UNINVOKED STUB", "RECUSED", "unexpected:"))),
                      "quarantined")
        return "QUARANTINED", reason[:110]
    if "UNEXPECTED" in out:
        m = TALLY.search(out)
        return "UNEXPECTED", (m.group(2) if m else "unexpected shape")
    if code != 0:
        last = [l for l in out.strip().splitlines() if l.strip()]
        # a non-zero exit with a clean tally is just "still BEFORE", not a crash
        if last and TALLY.search(out):
            m = TALLY.search(out)
            return "BEFORE", m.group(2)
        return "ERROR", (last[-1][:110] if last else f"exit {code}, no output")
    m = TALLY.search(out)
    if m:
        summary = m.group(2)
        return ("AFTER" if "BEFORE" not in summary else "BEFORE"), summary
    return "NO_TALLY", "ran clean but printed no verdict line"


def main() -> int:
    buckets: dict[str, list[tuple[str, str]]] = {}
    print(f"running {len(PROOFS)} proofs...\n")
    for p in PROOFS:
        rel = f".claude/notes/{p.name}"
        r = subprocess.run(DOCKER + ["python", rel], capture_output=True)
        out = (r.stdout + r.stderr).decode("utf-8", "replace")
        kind, detail = classify(out, r.returncode)
        buckets.setdefault(kind, []).append((p.name, detail))
        print(f"  {kind:11} {p.name}")

    print("\n" + "=" * 78)
    for kind in ("QUARANTINED", "UNEXPECTED", "ERROR", "NO_TALLY", "BEFORE", "AFTER"):
        rows = buckets.get(kind, [])
        if not rows:
            continue
        print(f"\n{kind}  ({len(rows)})")
        for name, detail in rows:
            print(f"   {name:44} {detail[:60]}")

    suspect = len(buckets.get("QUARANTINED", [])) + len(buckets.get("UNEXPECTED", [])) \
        + len(buckets.get("ERROR", [])) + len(buckets.get("NO_TALLY", []))
    print("\n" + "=" * 78)
    if suspect:
        print(f"SUSPECT: {suspect} proof(s) neither BEFORE nor AFTER — read each.")
        print("A proof that matches neither contract is measuring something that moved.")
        return 1
    print("All proofs report a clean BEFORE or AFTER — none has been retargeted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
