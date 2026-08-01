# REVIEW-01 — Mechanical reconciliation (Pass 1)

Method: deterministic script (`pass1_recon.py`) over `closure-matrix.json` +
SYNTH-01a/b + SYNTH-02. Matrix now carries a pinned single **owner** per record.

## Results

| Check | Result |
|---|---|
| Records | 484 open; 0 omitted; 0 double-counted (Σ owner tallies = 484) |
| Cross-listed records | 35 — ALL resolved to a single closure owner (pinned in matrix, was previously deferred to packet time — **review forced this now**) |
| Member IDs resolve | 484/484 (validated at synthesis; re-run clean) |
| Families in implementation sequence | all 33 accepted + 3 batches present in SYNTH-02 |
| Packets resolve to family/batch | 40/40 |
| Deferred items have reopen conditions | **DEFECT D7:** DEF-2 owned 4 records (A7-ROBORO-1/5/6/7) while its own text says they are NOT deferred (source-decidable, batched into RP-030). **Corrected: owners reassigned to RP-030's mapping small batch.** DEF-1/3/4/5 have concrete reopen conditions ✔ |
| Hardware-gated items at checkpoints | all tier-2 families map to HC-0..HC-5; expensive outlier (mid-job recharge) explicitly Chris-gated ✔ |
| Frontend obligations | 8 rows in SYNTH-02's consumer table; all scheduled or explicitly open ✔ |
| Closure totals vs corpus | catalogue `estimated_closure_count` values are FAMILY-view counts and disagree with single-owner tallies for 9 families (e.g. RF-24: est 6 vs owner-count 4 because ID-5/ID-6 close in DEAD-CODE/DOC-ONLY). **Ruling: the matrix owner tally is authoritative; catalogue counts are planning prose.** No corpus rewrite performed. |

Script artifact (cosmetic): the addendum batch label `SMALL-CORRECTNESS-2` truncates
to `SMALL-CORRECTNESS-` in the tally regex; the 11 records are correctly owned.

## Owner tallies (authoritative closure counts)

RF-01:5 · RF-02:8 · RF-03:10 · RF-04:8 · RF-05:8 · RF-06:10 · RF-07:8 · RF-08:7 ·
RF-09:13 · RF-10:8 · RF-11:15 · RF-12:5 · RF-13:9 · RF-14:25 · RF-15:10 · RF-16:19 ·
RF-17:20 · RF-18:29 · RF-19:14 · RF-20:8 · RF-21:13 · RF-22:7 · RF-23:10 · RF-24:4 ·
RF-25:21 · RF-26:8 · RF-27:3 · RF-28:15 · RF-29:8 · RF-30:7 · RF-31:9 · RF-32:10 ·
RF-33:11 · RF-34:18 · RF-35:19 · SMALL:59 · DEAD:8 · DOC:8 · DEF-1:1 · DEF-3:2
(after D7 correction; DEF-2 dissolved into RP-030/RF-09 ownership)

**Pass 1 verdict: implementation-ready after the D7 correction (applied to the matrix).**
