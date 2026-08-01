"""Generate the canonical findings corpus — Gate 1 steps 2-4.

    python .claude/notes/_gen_corpus.py

Reads the FROZEN sources only, never the live ones, so the corpus is reproducible from the
committed snapshot. Emits one normalized record per line.

Honesty rules (plan §8): never invent a field that was not recorded. Absent verifier metadata is
`UNKNOWN_NOT_PERSISTED` with a reason, not a fabricated boolean.
"""
import json
import pathlib
import re
import collections

F = pathlib.Path(".claude/notes/_frozen")
OUT = pathlib.Path(".claude/notes/corpus")
OUT.mkdir(parents=True, exist_ok=True)

SEVR = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
NOT_PERSISTED = {"value": "unknown", "reason": "not_persisted_by_historical_audit_schema"}


def subsystem_of(path: str) -> str:
    """First package component under the integration root, else the module name."""
    p = (path or "").replace("\\", "/")
    m = re.search(r"custom_components/eufy_vacuum/(.+)$", p)
    rest = m.group(1) if m else p
    parts = [x for x in rest.split("/") if x]
    if not parts:
        return "unknown"
    return parts[0] if len(parts) > 1 else parts[0].replace(".py", "")


def effective_severity(declared, corrections):
    corr = [c for c in (corrections or []) if c and c != "unchanged"]
    if not corr:
        return declared
    return sorted(corr, key=lambda s: SEVR.get(s, 9))[-1]


def severity_conflict(corrections, verdict_count=2):
    """The meta-verifier's assertion #1.

    Audits #7-#17 FILTER "unchanged" out of the array (verified: the literal appears only in
    #18). So for those, a 1-element array means one lens corrected and the other did not —
    a genuine disagreement. #18 and Stage B store both values verbatim.
    """
    c = corrections or []
    if len(c) == 1 and verdict_count >= 2:
        return True
    return len(set(c)) > 1 if len(c) >= 2 else False


records = []


# ---------------------------------------------------------------- audits (#7-#18)
man = json.loads((F / "_audit_runs.json").read_text(encoding="utf-8"))
for label, fp in man.items():
    art = pathlib.Path(fp)
    res = json.loads(art.read_text(encoding="utf-8", errors="replace"))["result"]

    def base(f, status, corpus):
        corrections = f.get("severity_corrections") or []
        verdicts = f.get("verdicts")            # #18 + Stage-B shape: labelled, with evidence
        confirmations = f.get("confirmations")  # #7-#17 shape: prose, one per lens, unlabelled
        # execution participation was never a recorded field on any historical audit
        exec_status = dict(NOT_PERSISTED)
        if verdicts and any("executed_a_check" in v for v in verdicts):
            exec_status = {"value": "recorded",
                           "executed_by": [v["lens"] for v in verdicts if v.get("executed_a_check")]}
        return {
            "canonical_id": f"{label.split()[0]}:{f['id']}",
            "finding_id": f["id"],
            "corpus": corpus,
            "status": status,
            "origin_audit": label,
            "origin_artifact": str(art).replace("\\", "/"),
            "review_mode": "audit_two_lens",
            "title": f.get("title"),
            "severity_declared": f.get("severity"),
            "severity_effective": f.get("effective_severity") or effective_severity(f.get("severity"), corrections),
            "severity_corrections": corrections,
            "severity_conflict": severity_conflict(corrections, f.get("verdict_count", 2)),
            "subsystem": subsystem_of(f.get("file", "")),
            "area": f.get("area"),
            "files": [f.get("file")] if f.get("file") else [],
            "line": f.get("line"),
            "brands": f.get("brands_affected"),
            "observed_behavior": f.get("mechanism") or f.get("what_code_does") or "not_recorded",
            "reproduction": f.get("reproduction", "not_recorded"),
            "user_impact": f.get("user_impact"),
            "guards_checked": f.get("guards_checked", "not_recorded"),
            "doc_checked": f.get("doc_checked", "not_recorded"),
            "confidence": f.get("confidence", "not_recorded"),
            "verification": {
                "verdict_count": f.get("verdict_count", len(verdicts or confirmations or [])),
                "confirmations": confirmations or "not_recorded",
                "killed_by": f.get("killed_by", []),
                "verdicts": verdicts or "not_recorded",
                "lens_labelled": bool(verdicts),
                "execution_status": exec_status,
            },
            "evidence_class": "UNKNOWN_NOT_PERSISTED",   # backfilled in step 6
            "needs_runtime_check": (f.get("confidence") == "needs-runtime-check"),
        }

    for f in res.get("survived") or []:
        records.append(base(f, "open_verified", "A"))
    for f in res.get("killed") or []:
        r = base(f, "killed", "C")
        r["kill_reason"] = f.get("killed_by") or [v.get("reason") for v in (f.get("verdicts") or [])]
        r["anti_unification_value"] = "killed_lookalike"
        records.append(r)


# ---------------------------------------------------------------- direct reads + targeted agents
# "hardware baseline" is the STRONGEST evidence class in the corpus: the defect was observed
# on a real device in a committed flight-recorder capture AND traced to source. It must not
# fall through to targeted_agent_unverified, which would tell Fable the opposite.
MODE = {"direct read": "orchestrator_direct_read",
        "hardware baseline": "hardware_observed_and_source_traced"}
for r in json.loads((F / "_direct_reads.json").read_text(encoding="utf-8")):
    run = r["run"]
    mode = MODE.get(run, "targeted_agent_two_lens" if "2-lens" in run else "targeted_agent_unverified")
    killed = bool(r.get("wontfix")) and r["id"].endswith("a")   # SN-10a is a true kill
    wontfix = bool(r.get("wontfix")) and not killed
    rec = {
        "canonical_id": f"{run}:{r['id']}",
        "finding_id": r["id"],
        "corpus": "C" if killed else "A",
        "status": "killed" if killed else ("wontfix_acknowledged" if wontfix else "open_verified"),
        "origin_audit": run,
        "origin_artifact": ".claude/notes/_frozen/_direct_reads.json",
        "review_mode": mode,
        "title": r.get("title"),
        "severity_declared": r.get("orig"),
        "severity_effective": r.get("sev"),
        "severity_corrections": [],
        "severity_conflict": False,
        "subsystem": subsystem_of(r.get("file", "")),
        "area": None,
        "files": [r.get("file")] if r.get("file") else [],
        "line": r.get("line"),
        "brands": r.get("brands"),
        "observed_behavior": r.get("impact"),
        "reproduction": "not_recorded",
        "user_impact": r.get("impact"),
        "guards_checked": "not_recorded",
        "doc_checked": "not_recorded",
        "confidence": "not_recorded",
        "verification": {
            "verdict_count": 2 if "2-lens" in run else 0,
            "confirmations": "not_recorded",
            "killed_by": [],
            "verdicts": ".claude/notes/_frozen/_stageB_result.json" if "2-lens" in run else "not_recorded",
            "lens_labelled": "2-lens" in run,
            "execution_status": ({"value": "recorded", "source": "stage_b"} if "2-lens" in run
                                 else {"value": "orchestrator_verified_at_source",
                                       "adversarially_verified": False}),
        },
        "evidence_class": ("CONFIRMED_EXECUTED"
                           if mode in ("orchestrator_direct_read",
                                       "hardware_observed_and_source_traced")
                           else "UNKNOWN_NOT_PERSISTED"),
        "needs_runtime_check": False,
    }
    if r.get("wontfix"):
        rec["disposition_note"] = r["wontfix"]
    records.append(rec)


# ---------------------------------------------------------------- carried-forward obligations
carried_path = pathlib.Path(".claude/notes/_carried.json")
if carried_path.exists():
    for i, c in enumerate(json.loads(carried_path.read_text(encoding="utf-8")), 1):
        records.append({
            "canonical_id": f"carried:CF-{i}",
            "finding_id": f"CF-{i}",
            "corpus": "A",
            "status": "carried_forward_obligation",
            "origin_audit": "pre-campaign / carried",
            "origin_artifact": ".claude/notes/_carried.json",
            "review_mode": "carried_obligation",
            "title": c["title"],
            "severity_declared": None, "severity_effective": None,
            "severity_corrections": [], "severity_conflict": False,
            "subsystem": c.get("subsystem", "unknown"), "area": None,
            "files": [], "line": None, "brands": "both",
            "observed_behavior": c["note"], "reproduction": "not_recorded",
            "user_impact": c["note"], "guards_checked": "not_recorded",
            "doc_checked": "not_recorded", "confidence": "not_recorded",
            "verification": {"verdict_count": 0, "confirmations": "not_recorded",
                             "killed_by": [], "verdicts": "not_recorded",
                             "lens_labelled": False,
                             "execution_status": {"value": "not_applicable",
                                                  "reason": "obligation, not an audit finding"}},
            "evidence_class": "not_applicable",
            "needs_runtime_check": False,
            "blocked_by": c.get("blocked_by"),
        })


# ---------------------------------------------------------------- validate (plan §13) + emit
errors = []
seen = collections.Counter(r["canonical_id"] for r in records)
for cid, n in seen.items():
    if n > 1:
        errors.append(f"duplicate canonical_id: {cid} x{n}")
VALID = {"open_verified", "open_source_only", "open_hardware_confirmed", "pending_stage_a",
         "pending_verification", "deferred_empirical", "partially_fixed", "wontfix_acknowledged",
         "carried_forward_obligation", "fixed_historical", "killed", "rejected"}
for r in records:
    if r["status"] not in VALID:
        errors.append(f"{r['canonical_id']}: unknown status {r['status']}")
    if not r.get("origin_artifact"):
        errors.append(f"{r['canonical_id']}: missing provenance")
    if r["status"] == "killed" and not (r.get("kill_reason") or r.get("disposition_note")):
        errors.append(f"{r['canonical_id']}: killed without a kill reason")

path = OUT / "audit-findings-canonical.jsonl"
with path.open("w", encoding="utf-8", newline="\n") as fh:
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

by_corpus = collections.Counter(r["corpus"] for r in records)
by_status = collections.Counter(r["status"] for r in records)
by_mode = collections.Counter(r["review_mode"] for r in records)
conflicts = [r["canonical_id"] for r in records if r["severity_conflict"]]

print(f"wrote {path} — {len(records)} records, {path.stat().st_size/1024:.0f} KB")
print(f"  corpus: {dict(by_corpus)}")
print(f"  status: {dict(by_status)}")
print(f"  review_mode: {dict(by_mode)}")
print(f"  severity conflicts (assertion #1): {len(conflicts)}")
print(f"  VALIDATION: {'PASS' if not errors else str(len(errors)) + ' ERRORS'}")
for e in errors[:10]:
    print("   !", e)
