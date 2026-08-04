import json, pathlib, collections

import re
SEVR = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
manifest = json.loads(pathlib.Path(".claude/notes/_audit_runs.json").read_text(encoding="utf-8"))
rows = []
for _label, _fp in manifest.items():
    _r = json.loads(pathlib.Path(_fp).read_text(encoding="utf-8", errors="replace"))["result"]
    for _f in _r["survived"]:
        _c = [s for s in (_f.get("severity_corrections") or []) if s != "unchanged"]
        _e = sorted(_c, key=lambda s: SEVR.get(s, 9))[-1] if _c else _f["severity"]
        _p = _f["file"].replace("\\", "/")
        _m = re.search(r"custom_components/eufy_vacuum/(.+)$", _p)
        rows.append({"run": _label, "id": _f["id"], "sev": _e, "orig": _f["severity"],
                     "file": _m.group(1) if _m else _p, "line": _f["line"],
                     "title": _f["title"], "brands": _f["brands_affected"],
                     "impact": _f["user_impact"]})
pathlib.Path(".claude/notes/_open_findings.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
RUN_LABELS = list(manifest)

_dr = pathlib.Path(".claude/notes/_direct_reads.json")
if _dr.exists():
    rows.extend(json.loads(_dr.read_text(encoding="utf-8")))

# ADJUDICATED findings — an overlay, not an edit to the audit JSON. The audits are
# frozen evidence; a verdict about a finding is a LATER judgement and belongs
# beside it, not inside it. `wontfix` already existed but only for _direct_reads
# rows, which are hand-maintained; an AUDIT finding had no way to be adjudicated
# at all, so anything judged overstated just sat open and got re-litigated.
# Same shape and lifecycle as _reopened_findings.json: hand-written, applied here,
# and LOUD when it goes stale.
_ADJ = pathlib.Path(".claude/notes/_adjudicated_findings.json")
if _ADJ.exists():
    _by_cid = {}
    for _r in rows:
        _run = _r["run"]
        _prefix = _run.split()[0] if _run.startswith("#") else _run
        _by_cid.setdefault(f"{_prefix}:{_r['id']}", _r)
    for _a in json.loads(_ADJ.read_text(encoding="utf-8")):
        _row = _by_cid.get(_a["finding_id"])
        if _row is None:
            print(f"WARNING: adjudicated finding {_a['finding_id']!r} not found among open "
                  f"findings -- already closed by a packet, or a stale entry in "
                  f"_adjudicated_findings.json")
            continue
        _note = f"{_a['verdict'].upper()} ({_a['adjudicated_at']}) -- {_a['reason']}"
        # Two verdict shapes, because "this is not a defect" and "this is a real
        # defect ranked wrong" are different judgements and only one of them
        # removes work from the board. A severity correction keeps the finding
        # OPEN and re-ranks it; collapsing both into wontfix would quietly retire
        # findings that still need fixing, which is the over-close failure this
        # campaign guards against.
        if _a.get("severity"):
            _row["sev"] = _a["severity"].upper()
            _row["adjudication"] = _note
        else:
            _row["wontfix"] = _note

# Deliberately-not-fixing entries are tracked, but they are NOT open findings and must
# not reappear in the fix list — an unmarked wontfix just gets re-litigated.
WONTFIX = [r for r in rows if r.get("wontfix")]
rows = [r for r in rows if not r.get("wontfix")]


# Applied state, derived from landed packets (.claude/notes/_landed_packets.json) via
# the packet-closure map (.claude/notes/synthesis/packet-closure-map.json, generated
# by _gen_packet_closure.py) and the closure matrix (.claude/notes/synthesis/
# closure-matrix.json). Shaped the same way as WONTFIX above: an applied finding is
# NOT open, but it is rendered DISTINCTLY (checked box + commit sha), never silently
# dropped — a disappeared finding is indistinguishable from one never found.
# `rows` filtering (mirrors WONTFIX) removes applied findings from the singles/
# severity counts; clusters are rendered from _clusters.json directly, bypassing
# `rows` entirely, so each cluster's own "Closes:" line is annotated per-id instead.
def _canonical_id(r):
    run = r["run"]
    prefix = run.split()[0] if run.startswith("#") else run
    return f"{prefix}:{r['id']}"


_landed = json.loads(pathlib.Path(".claude/notes/_landed_packets.json").read_text(encoding="utf-8"))

# Hardware validation is DERIVED from _landed_packets.json's optional `hardware` block, never
# asserted in prose here. The standing line used to be the hardcoded string "none -- nothing
# from this campaign has run on a real vacuum"; it kept reprinting `none` after the first runs
# landed, which is precisely the doc-vs-code drift this campaign exists to catch. A packet earns
# its row by carrying evidence file paths, so the claim cannot outrun the artifacts.
_HW = {p["packet_id"]: p["hardware"] for p in _landed if p.get("hardware")}
if not _HW:
    _hw_standing = "**none** -- nothing from this campaign has run on a real vacuum"
    _hw_gate_line = ("**Before any of it ships: a hardware run.** Nothing from this campaign "
                     "has met a vacuum.")
else:
    _hw_brands = sorted({b for h in _HW.values() for b in h.get("brands", [])})
    _hw_standing = (f"**{len(_HW)} packets** validated on hardware "
                    f"({', '.join(sorted(_HW))}) across {len(_hw_brands)} brand(s): "
                    f"{'; '.join(_hw_brands)}. Evidence in `_frozen/baseline/`")
    _hw_gate_line = (f"**Hardware gate: {len(_HW)} of {len(_landed)} landed packets validated "
                     f"on a real vacuum** ({', '.join(sorted(_HW))}). The remaining "
                     f"{len(_landed) - len(_HW)} are green in CI only -- treat an unvalidated "
                     f"packet as unshipped.")
_pclosure = {p["packet_id"]: p for p in json.loads(
    pathlib.Path(".claude/notes/synthesis/packet-closure-map.json").read_text(encoding="utf-8"))}
_cmatrix = json.loads(
    pathlib.Path(".claude/notes/synthesis/closure-matrix.json").read_text(encoding="utf-8"))
_owner_of = {r["canonical_id"]: r["owner"] for r in _cmatrix}

APPLIED = {}  # canonical_id -> landed packet dict
for _pk in _landed:
    _spec = _pclosure.get(_pk["packet_id"])
    if _spec is None:
        print(f"WARNING: landed packet {_pk['packet_id']!r} not found in "
              f"packet-closure-map.json -- re-run _gen_packet_closure.py?")
        continue
    if _spec["finding_ids"]:
        _cids = set(_spec["finding_ids"])
    elif _spec["repair_family"]:
        _cids = {c for c, o in _owner_of.items() if o == _spec["repair_family"]}
    else:
        print(f"WARNING: landed packet {_pk['packet_id']!r} has neither finding_ids "
              f"nor repair_family in packet-closure-map.json -- closes NOTHING; needs "
              f"hand curation before it can be marked applied (see _gen_packet_closure.py)")
        _cids = set()
    for _cid in _cids:
        APPLIED.setdefault(_cid, _pk)

# REOPENED: a landed packet's finding_ids close findings WHOLE, but a finding can have
# more than one half. RP-013c declared #9:A3-REC-3 and closed its finalization half; the
# live-progress half was untouched, and the ledger claimed a fix Chris then disproved on
# hardware in a single run. Closure is binary, findings are not -- so reopened entries are
# subtracted here and reported LOUDLY below. Silently moving one back to open would repeat
# the original error in the other direction.
_REOPENED = json.loads(
    pathlib.Path(".claude/notes/_reopened_findings.json").read_text(encoding="utf-8")
) if pathlib.Path(".claude/notes/_reopened_findings.json").exists() else []
for _r in _REOPENED:
    _was = APPLIED.pop(_r["finding_id"], None)
    if _was is None:
        print(f"WARNING: reopened finding {_r['finding_id']!r} was not marked applied -- "
              f"stale entry in _reopened_findings.json, or the packet that credited it "
              f"was never landed")

# bare-id lookup for cluster annotation (_clusters.json ids are bare, e.g. "DQ-DE-1")
APPLIED_BARE = {_cid.rsplit(":", 1)[-1]: _pk for _cid, _pk in APPLIED.items()}

APPLIED_ROWS = [r for r in rows if _canonical_id(r) in APPLIED]
rows = [r for r in rows if _canonical_id(r) not in APPLIED]
_reopened_ids = {_r["finding_id"] for _r in _REOPENED}
rows += [r for r in APPLIED_ROWS if _canonical_id(r) in _reopened_ids]
APPLIED_ROWS = [r for r in APPLIED_ROWS if _canonical_id(r) not in _reopened_ids]

CLUSTERS = json.loads(pathlib.Path(".claude/notes/_clusters.json").read_text(encoding="utf-8"))

clustered = {i for c in CLUSTERS.values() for i in c["ids"]}
_fully_closed_clusters = [k for k, cl in CLUSTERS.items()
                           if cl["ids"] and all(i in APPLIED_BARE for i in cl["ids"])]


def base_id(i):
    return i.split("-", 1)[1] if len(i) > 1 and i[0] == "A" and i[1].isdigit() else i


singles = [r for r in rows if r["id"] not in clustered and base_id(r["id"]) not in clustered]

L = []
A = L.append
A("# OPEN FIX CHECKLIST -- hostile audit campaign")
A("")
A("Durable ledger of every finding NOT yet applied. Generated from the audit JSON, not from")
A("recollection. **This file lives in git-ignored `.claude/notes/` -- it does not survive a")
A("machine loss.** Copy it somewhere backed up if that matters to you.")
A("")
A("## Standing")
A("")
A("| | |")
A("|---|---|")
A("| Fixes SHIPPED | audits #1-#6 + the adapter remainder, all deployed |")
A(f"| Fixes APPLIED (landed packets) | **{len(APPLIED_ROWS)}** findings via "
  f"{len(_landed)} packets ({', '.join(p['packet_id'] for p in _landed)}) |")
A(f"| Audits covered here | {', '.join(RUN_LABELS)} |")
c = collections.Counter(r["sev"] for r in rows)
A(f"| Open findings | **{len(rows)}** -- {len(CLUSTERS) - len(_fully_closed_clusters)} open "
  f"clusters ({len(_fully_closed_clusters)} fully applied) + {len(singles)} singles |")
A(f"| By severity | CRITICAL {c['CRITICAL']} / HIGH {c['HIGH']} / MEDIUM {c['MEDIUM']} / LOW {c['LOW']} |")
A(f"| Hardware validation | {_hw_standing} |")
A("")
if _REOPENED:
    A("")
    A(f"> ### {len(_REOPENED)} REOPENED finding(s) — a landed packet was credited with a fix that")
    A("> does not hold. Closure is binary; findings are not.")
    for _r in _REOPENED:
        A(">")
        A(f"> **{_r['finding_id']}** — credited to {_r['credited_to']}, reopened {_r['reopened_at']}")
        A(f"> - **Evidence:** {_r['evidence']}")
        A(f"> - **Why:** {_r['why']}")
        if _r.get("not_fixable_by"):
            A(f"> - **NOT fixable by:** {_r['not_fixable_by']}")
    A("")

A("`verified` = I personally opened the file and confirmed the mechanism at source. Everything")
A("else was reported by a finder and confirmed by both adversarial verifiers, but not")
A("independently re-checked by me.")
A("")
A("**Re-verify before scoping.** Audit #4 taught this the expensive way: RC-3 and RC-7 were both")
A("substantially stale by the time they were worked, because fixes had landed in between. An")
A("audit is a snapshot, not a ledger.")
A("")
A("---")
A("")
A("## TIER 1 -- clusters. Several findings, ONE fix each. Do these first.")
A("")
for k, cl in CLUSTERS.items():
    v = "**[VERIFIED AT SOURCE]**" if cl.get("verified") else "*(not independently verified)*"
    _closed_here = [i for i in cl["ids"] if i in APPLIED_BARE]
    _tag = f" — **{len(_closed_here)}/{len(cl['ids'])} applied**" if _closed_here else ""
    A(f"### {k}. {cl['name']} {v}{_tag}")
    A("")
    A(f"- **Seam:** `{cl['seam']}`")
    _id_bits = [f"~~{i}~~ ✅ {APPLIED_BARE[i]['packet_id']} (`{APPLIED_BARE[i]['commits'][0]}`)"
                if i in APPLIED_BARE else i for i in cl["ids"]]
    A(f"- **Closes:** {', '.join(_id_bits)}")
    A(f"- **What breaks:** {cl['note']}")
    A(f"- **Fix:** {cl['fix']}")
    _box = "[x]" if k in _fully_closed_clusters else "[ ]"
    # hardware-checked ticks only when the cluster is FULLY closed and every packet that closed
    # it carries a hardware block. A partially-applied cluster never ticks, even if the packets
    # that did land were validated -- the untouched findings are the unvalidated part.
    _cl_packets = {APPLIED_BARE[i]["packet_id"] for i in cl["ids"] if i in APPLIED_BARE}
    _hw_box = "[x]" if (k in _fully_closed_clusters and _cl_packets
                        and _cl_packets <= set(_HW)) else "[ ]"
    A(f"- {_box} applied  [ ] tested  {_hw_box} hardware-checked")
    A("")
A("---")
A("")
A("## TIER 2 -- singles, by corrected severity")
A("")
for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
    grp = [r for r in singles if r["sev"] == s]
    if not grp:
        continue
    A(f"### {s} ({len(grp)})")
    A("")
    for r in sorted(grp, key=lambda x: (x["file"], x["line"])):
        was = "" if r["sev"] == r["orig"] else f" _(finder said {r['orig']})_"
        A(f"- [ ] **{r['id']}** `{r['file']}:{r['line']}` [{r['brands']}]{was}  ")
        A(f"  {r['title']}  ")
        A(f"  -> {r['impact'][:220].strip()}")
        # An adjudicated finding keeps its ORIGINAL title and impact -- the audit
        # text is evidence and is never rewritten -- so without this line the
        # entry still asserts the harm that was disproved, with nothing to say so.
        # Same failure as the WONTFIX list being collected and never rendered.
        if r.get("adjudication"):
            A(f"  -> **ADJUDICATED:** {r['adjudication']}")
    A("")
A("---")
A("")
if APPLIED_ROWS:
    A(f"## APPLIED -- {len(APPLIED_ROWS)} findings closed by a landed packet")
    A("")
    A("Not open work. Kept here (rather than removed) so the audit trail stays intact --")
    A("a disappeared finding is indistinguishable from one never found.")
    A("`.claude/notes/_landed_packets.json` is the source of truth for what has landed; see")
    A("`_gen_packet_closure.py` for how a packet resolves to the finding ids below.")
    A("")
    for r in sorted(APPLIED_ROWS, key=lambda x: (APPLIED[_canonical_id(x)]["packet_id"], x["file"])):
        pk = APPLIED[_canonical_id(r)]
        shas = ", ".join(f"`{c}`" for c in pk["commits"])
        A(f"- [x] **{r['id']}** `{r['file']}:{r['line']}` [{r['brands']}] "
          f"-- **{pk['packet_id']}** ({shas}, {pk['landed_at']})  ")
        A(f"  {r['title']}")
    A("")
    A("---")
    A("")
A("## TIER 3 -- carried over from before audit #7, never closed")
A("")
CARRIED = [(c["title"], c["note"]) for c in json.loads(
    pathlib.Path(".claude/notes/_carried.json").read_text(encoding="utf-8"))]
for t, d in CARRIED:
    A(f"- [ ] **{t}** -- {d}")
A("")
A("---")
A("")
A("## Suggested order for a cheap execution window")
A("")
A("Ordered by (verified) x (blast radius) x (cost), not by severity label.")
A("")
A("1. **C5** -- 2 lines, verified, closes a gap I introduced. Cheapest real win.")
A("2. **C7** -- verified CRITICAL. Slug uniqueness at discovery: wrong physical room AND silent")
A("   destruction of the second room's stored settings. Fix the docstring's false claim too.")
A("3. **C1** -- verified CRITICAL seam. The other wrong-physical-room path.")
A("4. **C10** -- small, and the third route to the same wrong-room outcome (a failed refresh is")
A("   indistinguishable from a successful one, so stale ids reach the wire).")
A("5. **C9** -- destructive writes. An empty selection wiping a map's rooms is one bad call away.")
A("6. **C3** -- try/finally so one transient failure stops bricking every future run.")
A("7. **C8** -- decide reconciliation's trigger. The machinery is built and nothing calls it.")
A("   This is the ROOT of C1/C7 rather than another instance of them.")
A("8. **C2** -- cancel correctness. Needs care around the await boundaries.")
A("9. **C6** -- user-visible on every mop room, but changes resolution precedence. Test hard.")
A("10. **C4** -- per-phase attribution. Touches the shape of learning data.")
A("11. Tier 2 HIGHs, then MEDIUMs. LOWs only when the file is already open for another reason.")
A("")
A(_hw_gate_line)
A("")
A("## Campaign cost, for calibration")
A("")
A("| Audit | Tokens | Wall |")
A("|---|---|---|")
A("| #7 dispatch+queue | 1.58M | 23 min |")
A("| #8 profiles+planning | 1.95M (incl. a re-verify my own harness bug forced) | 40 min |")
A("| #9 jobs | 1.50M | 23 min |")
A("| #10 rooms | 1.07M | 21 min |")
A("")
A("Cost tracks the 8-agent shape far more than subsystem size -- #10 covered 2,531 LOC for 1.07M")
A("while #7 covered 1,515 LOC for 1.58M. Scope future audits by agent count, not by LOC.")
A("")
# ADJUDICATED / WONTFIX. This list was COLLECTED and never RENDERED -- a dead
# variable since it was introduced, so the two direct-read entries had been
# silently absent from the output the whole time. That is precisely the failure
# this file guards against everywhere else: a finding that disappears is
# indistinguishable from one that was never found, and an unrendered wontfix gets
# re-litigated by the next audit exactly like an unmarked one.
A("## ADJUDICATED -- judged not-a-fix, with reasoning. NOT open, NOT forgotten.")
A("")
A("A finding here was examined and deliberately not fixed. The reasoning is kept in")
A("full so audit #2 can overturn it on evidence rather than rediscover it from")
A("scratch. Audit findings are adjudicated in `.claude/notes/_adjudicated_findings.json`")
A("(an overlay -- the audit JSON itself is frozen evidence and is never edited);")
A("direct-read rows carry `wontfix` inline.")
A("")
if not WONTFIX:
    A("_None._")
    A("")
for _w in sorted(WONTFIX, key=lambda r: (r["run"], r["id"])):
    A(f"- **{_w['id']}** ({_w['run']}) `{_w.get('file', '?')}"
      f"{':' + str(_w['line']) if _w.get('line') else ''}`  ")
    A(f"  {_w.get('title', '')}  ")
    A(f"  -> {_w['wontfix']}")
    A("")

A("## Regenerating this file")
A("")
A("    python .claude/notes/_gen_checklist.py")
A("")
A("Reads `.claude/notes/_audit_runs.json` (label -> workflow output path). To add an audit,")
A("append one line to that manifest and re-run. Clusters are hand-curated in the generator --")
A("a new audit's findings arrive as Tier 2 singles until they are clustered by hand.")
A("")

out = pathlib.Path(".claude/notes/OPEN-FIX-CHECKLIST.md")
out.write_text("\n".join(L), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size:,} bytes)")
print(f"applied: {len(APPLIED_ROWS)} findings via {len(_landed)} packets")
print(f"clusters: {len(CLUSTERS)} covering {len(clustered)} ids "
      f"({len(_fully_closed_clusters)} fully applied)")
print(f"singles: {len(singles)}   carried: {len(CARRIED)}")
