# Development deltas — the current epoch's diff against the DR baseline

Per [00a — Documentation Epoch and Reconciliation Model](../00a-documentation-epoch-lifecycle.md):
the numbered docs in `docs/dev/` are the **Disaster-Recovery baseline** — the reconciled,
present-tense rebuild truth as of the last epoch close. Files in THIS directory are the
current epoch's **deltas** against that baseline.

Reading rule: read the relevant DR section first, then the matching delta here. A delta
overrides the baseline only where it explicitly says it differs. **No delta file for a
subsystem means the DR baseline is authoritative, full stop.**

Deltas may be painfully honest — hypotheses, competing interpretations, unadjudicated
evidence, known gaps. Their job is to preserve active engineering reasoning accurately
enough for the next epoch-closing audit to adjudicate it.

---

## Epoch ledger

| epoch | closed | closing operation |
|---|---|---|
| **Epoch 1** | **2026-08-06** | The hostile-audit campaign (464 findings / 67 packets, cleared) + the DR reconciliation pass that established this baseline. Provenance: the audit record (`.claude/notes/synthesis/`, closure ledgers, the postmortem corpus). |
| Epoch 2 | open | Accumulating. First known delta candidates: the Phased Jobs rebuild; `live:FONT-1`'s unresolved remainder. |
