"""Generate .claude/notes/synthesis/packet-closure-map.json.

Extracts, from every packet's YAML block in the SYNTH-*-packets-*.md synthesis
docs, the ONE piece each packet already declares that says what it closes:

  - wave 0/1 packets (SYNTH-03/04): `repair_family: RF-NN` -- a single family.
    What it closes = every closure-matrix.json row whose `owner` is that family
    (owner is the matrix's pinned single closure-owning family per finding --
    see REVIEW-01-reconciliation.md).
  - wave 2+ packets (SYNTH-06..12): `finding_ids: [...]` -- a literal list of
    closure-matrix canonical_ids. Used directly, in preference to `family_id`
    (also present on these waves) -- finding_ids is the more precise, packet-
    authored set; family_id is informational.

This does NOT run a general YAML parser over the whole block -- these blocks
mix real YAML with free prose (parentheticals, arrows, unquoted commentary)
that breaks a generic loader. It targets exactly the three well-formed fields
above with field-scoped regexes and leaves everything else alone.

A handful of packets (RP-040's four-batch prose closure; CARD-1..9, which
reference carried-forward items and prose rather than a clean id list) don't
match either shape. They are recorded with both fields null rather than
guessed at -- the consuming generators must treat that as "not yet
automatically resolvable" and warn loudly if such a packet is ever landed,
not silently resolve it to an empty closed set.

    python .claude/notes/_gen_packet_closure.py

Re-run whenever a SYNTH-*-packets-*.md file is added or a packet's closure
fields change.
"""
import glob
import json
import pathlib
import re

FILES = sorted(glob.glob(".claude/notes/synthesis/SYNTH-*-packets-*.md"))

packets = []
for fp in FILES:
    text = pathlib.Path(fp).read_text(encoding="utf-8")
    for block in re.findall(r"```yaml\n(.*?)\n```", text, re.DOTALL):
        m = re.search(r"^packet_id:\s*(\S+)\s*$", block, re.MULTILINE)
        if not m:
            continue  # a non-packet yaml fence, if one ever appears
        packet_id = m.group(1)

        family = None
        fm = re.search(r"^repair_family:\s*(\S+)\s*$", block, re.MULTILINE)
        if not fm:
            fm = re.search(r"^family_id:\s*(\S+)\s*$", block, re.MULTILINE)
        if fm:
            family = fm.group(1)

        finding_ids = None
        im = re.search(r"^finding_ids:\s*\[(.*?)\]", block, re.MULTILINE | re.DOTALL)
        if im:
            ids = re.findall(r'"([^"]+)"', im.group(1))
            if ids:  # a prose "[...]" with no quoted strings is not a real list
                finding_ids = ids

        packets.append({
            "packet_id": packet_id,
            "repair_family": family,
            "finding_ids": finding_ids,
            "source_doc": fp.replace("\\", "/"),
        })

ids_seen = [p["packet_id"] for p in packets]
assert len(ids_seen) == len(set(ids_seen)), f"duplicate packet_id across docs: {ids_seen}"

unresolvable = [p["packet_id"] for p in packets if not p["repair_family"] and not p["finding_ids"]]

out = pathlib.Path(".claude/notes/synthesis/packet-closure-map.json")
out.write_text(json.dumps(packets, indent=1), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size:,} bytes)")
print(f"packets: {len(packets)} across {len(FILES)} docs")
if unresolvable:
    print(f"unresolvable (neither repair_family nor finding_ids -- prose closure, "
          f"needs hand curation before landing): {', '.join(unresolvable)}")
