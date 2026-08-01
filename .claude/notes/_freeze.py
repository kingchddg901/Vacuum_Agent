"""Re-runnable freeze of the audit evidence corpus.

Copies every source the ledger is generated from into `_frozen/`, rewrites the manifest to
point at the frozen copies so the snapshot is SELF-CONTAINED, and records a SHA-256 digest
per artifact plus a count reconciliation.

    python .claude/notes/_freeze.py

Re-run whenever a source artifact changes. The snapshot is committed (force-added past
.gitignore) because the ledger is generated and its evidence would otherwise exist on one
machine only. `.gitattributes` marks `_frozen/**` as `-text` so digests survive a clone.
"""
import datetime
import hashlib
import json
import pathlib
import shutil
import subprocess

N = pathlib.Path(".claude/notes")
F = N / "_frozen"
LEDGER = pathlib.Path("docs/dev/maintenance/highly-aggressive-audit.md")
CURATED = ("_direct_reads.json", "_clusters.json", "_order.json", "_calibration.json",
           "_stageB_result.json", "_mapping_result.json", "_carried.json")


def digest(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:16]


def safe(label):
    for a, b in (("#", ""), (" ", "-"), ("(", ""), (")", ""), ("/", "-")):
        label = label.replace(a, b)
    return label


def main():
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    for sub in ("audits", "reproducers", "journals"):
        (F / sub).mkdir(parents=True, exist_ok=True)

    digests, total = {}, 0

    # 1. audit artifacts, with the manifest rewritten to the frozen copies
    man = json.loads((N / "_audit_runs.json").read_text(encoding="utf-8"))
    frozen_man = {}
    for label, src in man.items():
        dst = F / "audits" / f"{safe(label)}.json"
        shutil.copy2(src, dst)
        rel = str(dst).replace("\\", "/")
        frozen_man[label] = rel
        digests[rel] = digest(dst)
        total += dst.stat().st_size
    (F / "_audit_runs.json").write_text(json.dumps(frozen_man, indent=1), encoding="utf-8")

    # 2. curated sources
    for name in CURATED:
        src = N / name
        if src.exists():
            shutil.copy2(src, F / name)
            digests[f".claude/notes/_frozen/{name}"] = digest(F / name)
            total += (F / name).stat().st_size

    # 3. reproducers and workflow journals (raw agent returns = deepest provenance)
    for p in sorted(N.glob("_proof_*.py")) + sorted(N.glob("_stageA_repro.py")):
        shutil.copy2(p, F / "reproducers" / p.name)
        total += p.stat().st_size
    for p in sorted((F / "journals").glob("*.jsonl")):
        digests[str(p).replace("\\", "/")] = digest(p)
        total += p.stat().st_size

    # 3b. the canonical corpus — the artifact Fable actually consumes
    corpus = pathlib.Path(".claude/notes/corpus/audit-findings-canonical.jsonl")
    if corpus.exists():
        (F / "corpus").mkdir(exist_ok=True)
        shutil.copy2(corpus, F / "corpus" / corpus.name)
        digests[f".claude/notes/_frozen/corpus/{corpus.name}"] = digest(corpus)
        total += corpus.stat().st_size

    # 3c. hardware baseline — already lives under _frozen/, so nothing to copy, but it MUST be
    # digested: it is the only evidence here that cannot be regenerated from source. A silent
    # edit to a flight-recorder dump would otherwise pass unnoticed.
    baseline = F / "baseline"
    if baseline.is_dir():
        for p in sorted(baseline.rglob("*")):
            if p.is_file():
                rel = str(p).replace("\\", "/")
                digests[rel] = digest(p)
                total += p.stat().st_size

    # 4. the generated ledger as this snapshot's reference output
    shutil.copy2(LEDGER, F / LEDGER.name)
    digests[f".claude/notes/_frozen/{LEDGER.name}"] = digest(LEDGER)
    total += LEDGER.stat().st_size

    # 5. reconcile from the FROZEN copies, never the live ones
    surv = killed = clean = with_verdicts = 0
    for label, fp in frozen_man.items():
        res = json.loads(pathlib.Path(fp).read_text(encoding="utf-8", errors="replace"))["result"]
        s = res.get("survived") or []
        surv += len(s)
        with_verdicts += sum(1 for x in s if x.get("verdicts") or x.get("confirmations"))
        killed += len(res.get("killed") or [])
        clean += len(res.get("clean_areas") or [])
    dr = json.loads((F / "_direct_reads.json").read_text(encoding="utf-8"))
    dr_open = [r for r in dr if not r.get("wontfix")]

    counts = {"audits": len(frozen_man), "audit_survivors": surv,
              "survivors_carrying_verdict_evidence": with_verdicts,
              "non_audit_records": len(dr), "non_audit_open": len(dr_open),
              "open_total": surv + len(dr_open), "killed_records": killed,
              "clean_areas": clean}
    (F / "FREEZE.json").write_text(json.dumps(
        {"frozen_at_sha": sha,
         "frozen_at": datetime.datetime.now().isoformat(timespec="seconds"),
         "counts": counts, "digests": digests}, indent=1), encoding="utf-8")

    print(f"frozen at {sha[:12]} | {total / 1024 / 1024:.2f} MB | {len(digests)} digested artifacts")
    for k, v in counts.items():
        print(f"  {k:<38} {v}")
    return counts


if __name__ == "__main__":
    main()
