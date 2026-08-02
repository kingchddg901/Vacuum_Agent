"""Derive reproducer coverage from the packets + the disk. Never assert a count in prose.

MATERIALIZATION-03-HANDOFF.md used to carry a hardcoded "26 reproducers remain". It was
authored before the wave-2, M5 and M6 proof work and was never updated, so Sonnet was
reading a number that was wrong by a factor of ~2.5 and scoping the M-stages against it.
Same failure mode as the checklist's hardcoded "Hardware validation: none".

Reads:  .claude/notes/synthesis/SYNTH-*.md   (packet blocks -> named reproducer)
        .claude/notes/_proof_*.py            (what actually exists)
        .claude/notes/_landed_packets.json   (which packets shipped)
Writes: .claude/notes/REPRODUCER-STATUS.md

Run from the repo root:  python .claude/notes/_gen_repro_status.py
"""

from __future__ import annotations

import glob
import json
import pathlib
import re

NOTES = pathlib.Path(".claude/notes")
SYNTH = NOTES / "synthesis"

# A packet is a fenced yaml block carrying `packet_id:`. Its reproducer is whatever
# _proof_*.py the block names -- packets spell it `reproducer_script:` or `reproducer:`
# or mention it in prose, so match the FILENAME rather than the key.
_BLOCK = re.compile(r"```yaml\n(.*?)\n```", re.S)
_PID = re.compile(r"^packet_id:\s*(\S+)", re.M)
_PROOF = re.compile(r"_proof_[a-z0-9_]+\.py")

packets: dict[str, dict] = {}
for doc in sorted(glob.glob(str(SYNTH / "SYNTH-*.md"))):
    text = pathlib.Path(doc).read_text(encoding="utf-8", errors="replace")
    for block in _BLOCK.findall(text):
        pid = _PID.search(block)
        if not pid:
            continue
        packets[pid.group(1)] = {
            "doc": pathlib.Path(doc).name,
            "proofs": sorted(set(_PROOF.findall(block))),
        }

on_disk = {p.name for p in NOTES.glob("_proof_*.py")}
landed = {
    r["packet_id"]
    for r in json.loads((NOTES / "_landed_packets.json").read_text(encoding="utf-8"))
}

rows = []
for pid, meta in sorted(packets.items()):
    named = meta["proofs"]
    missing = [f for f in named if f not in on_disk]
    rows.append({
        "packet": pid, "doc": meta["doc"], "named": named, "missing": missing,
        "landed": pid in landed,
        # A packet with no named proof is not a gap -- some close via a gate or a
        # batch table instead. Only a NAMED-but-absent file is outstanding work.
        "state": ("none-named" if not named else "complete" if not missing else "missing"),
    })

named_files = {f for r in rows for f in r["named"]}
orphans = sorted(on_disk - named_files - {"_proof_harness.py"})
missing_rows = [r for r in rows if r["state"] == "missing"]
landed_gap = [r for r in missing_rows if r["landed"]]

A: list[str] = []
A.append("# REPRODUCER STATUS -- generated, do not hand-edit")
A.append("")
A.append("Regenerate: `python .claude/notes/_gen_repro_status.py`. Every number here is")
A.append("derived from the packet blocks and the files on disk. **Do not copy these counts")
A.append("into prose elsewhere** -- link to this file instead. The handoff doc used to")
A.append("hardcode a reproducer count and it drifted badly enough to misscope a stage.")
A.append("")
A.append("| | |")
A.append("|---|---|")
A.append(f"| Packets parsed | {len(rows)} across {len({r['doc'] for r in rows})} docs |")
A.append(f"| Distinct proofs named by packets | {len(named_files)} |")
A.append(f"| Proof files on disk | {len(on_disk)} (incl. `_proof_harness.py`, which is "
         "scaffolding, not a proof) |")
A.append(f"| Packets with every named proof present | {sum(1 for r in rows if r['state'] == 'complete')} |")
A.append(f"| Packets missing a named proof | **{len(missing_rows)}** |")
A.append(f"| Packets naming no proof at all | {sum(1 for r in rows if r['state'] == 'none-named')} |")
A.append(f"| Distinct proof files still to write | **{len({f for r in missing_rows for f in r['missing']})}** |")
A.append("")

if landed_gap:
    A.append(f"> **{len(landed_gap)} LANDED packet(s) are missing a named reproducer** -- "
             "something shipped without its evidence. Fix before anything else:")
    for r in landed_gap:
        A.append(f"> - {r['packet']} -> {', '.join(r['missing'])}")
else:
    A.append("**Every landed packet has its named reproducer present.** Nothing shipped")
    A.append("without evidence; the outstanding files all belong to unexecuted packets.")
A.append("")
A.append("---")
A.append("")
A.append("## Outstanding -- named by a packet, absent from disk")
A.append("")
if missing_rows:
    A.append("| packet | doc | missing proof | packet landed? |")
    A.append("|---|---|---|---|")
    for r in missing_rows:
        A.append(f"| {r['packet']} | {r['doc']} | `{', '.join(r['missing'])}` |"
                 f" {'**YES -- gap**' if r['landed'] else 'no'} |")
else:
    A.append("None.")
A.append("")
A.append("## Orphans -- on disk, named by no packet")
A.append("")
A.append("Not a defect. These are direct-read and ad-hoc investigations, plus NAMING DRIFT:")
A.append("a packet naming `_proof_map_identity.py` may already be served by")
A.append("`_proof_map_source_identity.py`. **Check this list before writing a missing proof**")
A.append("-- the work may exist under another name, in which case fix the packet's text.")
A.append("")
for f in orphans:
    A.append(f"- `{f}`")
A.append("")

out = NOTES / "REPRODUCER-STATUS.md"
out.write_text("\n".join(A) + "\n", encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size:,} bytes)")
print(f"packets: {len(rows)} | named proofs: {len(named_files)} | on disk: {len(on_disk)}")
print(f"missing: {len({f for r in missing_rows for f in r['missing']})} files "
      f"across {len(missing_rows)} packets · landed-with-gap: {len(landed_gap)}")
print(f"orphans: {len(orphans)}")
