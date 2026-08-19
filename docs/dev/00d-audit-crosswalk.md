# 00d — Audit crosswalk: finding id → the rule it produced

> **Self-contained on purpose.** The 463-finding audit corpus is git-ignored working
> data. This file is what survives it: every finding id resolves to the invariant it
> produced, so an id met in an old commit message stays meaningful after the corpus is
> gone. Snapshot of 2026-08-18; it is not generated, because its inputs are not in the
> repo.

## How to use it

You have a finding id — `A2-JOB-1`, `DQ-PAY-2` — from a commit message, a comment, or a
note. Find it below to get its anchor, then `python scripts/doc_anchor.py --show <TOKEN>`
for the rule, its declaration site and every citing site. **That replaces the stored
`file:line`, which has rotted** — every line number in the corpus now points at unrelated
code, which is why finding sites had to be resolved from titles.

## Why a family and not a finding

Findings were grouped into repair families (`RF-*`) during the 2026-07 synthesis. The
family carries the shared rule; the finding is one way it failed. So the crosswalk is
`finding → family → anchor`, and a family maps to **exactly one** invariant.

That association previously existed only in prose and in one person's head. Recovering it
cost a pass, and one pairing was wrong when derived mechanically: `RF-07` votes
`INYA5T84` from a single finding that also touched adapter config, when the family is the
phase-watchdog exclusion — [[INZKT2QF]]. Every row below was checked against the family's
own `shared_invariant` text, not derived.

## Anchored families

| family | anchor | findings |
|---|---|---|
| `RF-01` | [`IN5BRA39`](00b-invariants.md) | 5 |
| `RF-02` | [`INC63FDF`](00b-invariants.md) | 8 |
| `RF-03` | [`IN2QDNB3`](00b-invariants.md) | 10 |
| `RF-04` | [`IN4CW5Y9`](00b-invariants.md) | 10 |
| `RF-05` | [`INGZFYXX`](00b-invariants.md) | 9 |
| `RF-06` | [`IN5TNKMD`](00b-invariants.md) | 11 |
| `RF-07` | [`INZKT2QF`](00b-invariants.md) | 9 |
| `RF-08` | [`INJBNQ2Q`](00b-invariants.md) | 8 |
| `RF-10` | [`INPQ6ZE7`](00b-invariants.md) | 8 |
| `RF-11` | [`INQ619A6`](00b-invariants.md) | 16 |
| `RF-12` | [`IN6VSBJ1`](00b-invariants.md) | 6 |
| `RF-13` | [`INFJXSM4`](00b-invariants.md) | 9 |
| `RF-14` | [`INT62M7A`](00b-invariants.md) | 25 |
| `RF-15` | [`INKV8ZQD`](00b-invariants.md) | 11 |
| `RF-16` | [`INT79PB7`](00b-invariants.md) | 20 |
| `RF-17` | [`IN1FX8EH`](00b-invariants.md) | 21 |
| `RF-18` | [`IN40W49E`](00b-invariants.md) | 33 |
| `RF-19` | [`IN11T0FS`](00b-invariants.md) | 15 |
| `RF-20` | [`INJ7VXE7`](00b-invariants.md) | 8 |
| `RF-22` | [`IN5ATBW9`](00b-invariants.md) | 7 |
| `RF-23` | [`IN76GE4W`](00b-invariants.md) | 10 |
| `RF-24` | [`INCFMPP1`](00b-invariants.md) | 6 |
| `RF-25` | [`INMKEHPQ`](00b-invariants.md) | 21 |
| `RF-26` | [`INSJM6KC`](00b-invariants.md) | 8 |
| `RF-27` | [`INNPA4ZV`](00b-invariants.md) | 3 |
| `RF-28` | [`INJSETB0`](00b-invariants.md) | 16 |
| `RF-29` | [`INJW5J2A`](00b-invariants.md) | 10 |
| `RF-30` | [`IN96V4SA`](00b-invariants.md) | 7 |
| `RF-31` | [`INNJ6SGC`](00b-invariants.md) | 9 |
| `RF-32` | [`INYA5T84`](00b-invariants.md) | 11 |
| `RF-33` | [`INTCWVFM`](00b-invariants.md) | 12 |

<details><summary>Finding ids by family</summary>

**`RF-01` → `IN5BRA39`** — `A2-LIFE-1`, `A3-SNAP-3`, `A5-STR-5`, `A5-SVC-2`, `HW-FINAL-1`

**`RF-02` → `INC63FDF`** — `A2-REC-4`, `A3-CRUD-1`, `A3-ROOMS-1`, `A3-ROOMS-2`, `A4-SETUP-1`, `A5-FACADE-1`, `A5-FACADE-2`, `A5-FACADE-3`

**`RF-03` → `IN2QDNB3`** — `A1-INIT-2`, `A2-ACC-1`, `A2-CB-2`, `A3-IMAGE--2`, `A3-IMAGE--3`, `A3-IO-2`, `A3-IO-3`, `A4-SRC-2`, `A4-STATE-8`, `A5-SVC-6`

**`RF-04` → `IN4CW5Y9`** — `A2-CB-1`, `A2-CB-5`, `DR-SENS-2`, `DR-SETUP-1`, `EP-2`, `INF-5`, `SN-1`, `SN-3`, `SN-4`, `SN-7`

**`RF-05` → `INGZFYXX`** — `A2-JOB-7`, `A4-PP-RP-3`, `A4-PP-RP-7`, `A4-SETUP-5`, `A5-RUNPROF-2`, `A5-RUNPROF-3`, `A5-SVC-3`, `A6-DIAG-9`, `DQ-ACT-6`

**`RF-06` → `IN5TNKMD`** — `A1-WD-1`, `A2-CAN-1`, `A2-CAN-3`, `A2-CAN-4`, `A2-CAN-5`, `A2-CAN-6`, `A2-JOB-2`, `A4-AJ-3`, `A6-GUARD-2`, `A6-GUARD-4`, `DQ-ACT-2`

**`RF-07` → `INZKT2QF`** — `A1-WD-2`, `A1-WD-4`, `A1-WD-5`, `A2-CAN-4`, `A5-STR-1`, `A5-STR-2`, `A5-STR-3`, `A5-STR-4`, `DQ-ACT-3`

**`RF-08` → `INJBNQ2Q`** — `A4-SRC-1`, `A4-SRC-2`, `A4-SRC-3`, `A4-SRC-4`, `A4-SRC-5`, `DQ-ACT-1`, `DQ-ACT-5`, `DQ-DE-1`

**`RF-10` → `INPQ6ZE7`** — `A1-LC-2`, `A1-LC-4`, `A2-GEO-1`, `A5-POSE-1`, `A5-POSE-2`, `A5-POSE-3`, `A5-POSE-4`, `A5-POSE-5`

**`RF-11` → `INQ619A6`** — `A1-WD-3`, `A2-CAN-2`, `A3-IO-1`, `A3-REC-1`, `A3-REC-2`, `A3-REC-3`, `A3-REC-4`, `A4-AJ-2`, `A4-STATE-1`, `A4-STATE-2`, `A4-STATE-6`, `DQ-PH-1`, `DQ-PH-2`, `DQ-PH-3`, `DQ-PH-6`, `INF-8`

**`RF-12` → `IN6VSBJ1`** — `A3-COMMON-4`, `A3-COMMON-6`, `A5-METRICS-1`, `A5-STR-1`, `A6-VAC-1`, `DR-SENS-1`

**`RF-13` → `INFJXSM4`** — `A3-COMMON-1`, `A3-COMMON-3`, `A3-SNAP-1`, `A4-POSE-3`, `A6-GUARD-1`, `A6-PRE-1`, `DR-MNT-1`, `INF-4`, `SN-2`

**`RF-14` → `INT62M7A`** — `A1-CRUD-7`, `A2-JOB-1`, `A2-JOB-3`, `A2-POLYGO-2`, `A2-POLYGO-8`, `A3-IMAGE--7`, `A3-IMAGE--8`, `A3-ROOMS-10`, `A3-ROOMS-11`, `A3-ROOMS-5`, `A3-ROOMS-7`, `A4-CUSTOM-2`, `A4-SETUP-12`, `A4-SETUP-4`, `A4-SETUP-8`, `A5-RUNPROF-1`, `A5-RUNPROF-5`, `A5-RUNPROF-6`, `A5-SVC-4`, `A6-DIAG-1`, `A6-DIAG-2`, `A6-DIAG-6`, `A6-DIAG-7`, `A6-VAC-2`, `EP-1`

**`RF-15` → `INKV8ZQD`** — `A1-SERVIC-1`, `A1-SERVIC-5`, `A2-DRAFT-4`, `A2-JOB-8`, `A3-IMAGE--5`, `A4-CUSTOM-1`, `A5-FURNIS-1`, `A5-RUNPROF-8`, `A6-DIAG-5`, `A6-DIAG-6`, `A6-ZONE-C-6`

**`RF-16` → `INT79PB7`** — `A1-INIT-1`, `A1-REG-2`, `A1-REG-3`, `A1-UP-1`, `A1-UP-2`, `A1-UP-3`, `A1-WIRE-5`, `A2-DOWN-1`, `A2-DOWN-2`, `A2-DOWN-3`, `A2-LIFE-2`, `A4-RELOAD-1`, `A4-RELOAD-2`, `A4-RELOAD-3`, `A4-RELOAD-4`, `A4-SRC-5`, `A5-SVC-7`, `A6-GUARD-6`, `A6-VAC-4`, `DR-DBG-3`

**`RF-17` → `IN1FX8EH`** — `A1-CRUD-1`, `A1-CRUD-2`, `A1-CRUD-3`, `A1-CRUD-4`, `A1-CRUD-5`, `A1-CRUD-6`, `A1-CRUD-8`, `A1-INIT-3`, `A2-DRAFT-1`, `A2-DRAFT-2`, `A2-DRAFT-3`, `A2-DRAFT-6`, `A2-DRAFT-7`, `A3-PORT-1`, `A3-PORT-2`, `A3-PORT-3`, `A3-PORT-4`, `A3-PORT-5`, `A3-PORT-7`, `A3-PORT-8`, `SN-6`

**`RF-18` → `IN40W49E`** — `A1-EST-7`, `A1-EST-8`, `A1-INIT-5`, `A1-PP-RES-5`, `A1-PP-RES-6`, `A1-PP-RES-8`, `A1-PP-RES-9`, `A2-LIFE-3`, `A2-PP-CAP-1`, `A2-PP-CAP-2`, `A2-PP-CAP-3`, `A2-PP-CAP-4`, `A2-PP-CAP-6`, `A2-PP-CAP-7`, `A3-PP-CRUD-1`, `A3-PP-CRUD-4`, `A3-PP-CRUD-6`, `A3-PP-CRUD-7`, `A3-ROOMS-6`, `A3-ROOMS-9`, `A5-PP-RP-7`, `A5-PP-RP-8`, `A6-DIAG-8`, `A6-PP-EST-TD-1`, `DQ-DE-3`, `DQ-DE-4`, `DQ-PAY-1`, `DQ-PAY-5`, `DQ-PAY-6`, `DQ-Q-2`, `DQ-Q-4`, `DQ-Q-6`, `EP-8`

**`RF-19` → `IN11T0FS`** — `A1-PP-RES-2`, `A1-PP-RES-3`, `A1-PP-RES-4`, `A1-PP-RES-7`, `A2-PP-CAP-3`, `A3-PP-CRUD-2`, `A3-PP-CRUD-5`, `A3-PP-CRUD-8`, `A4-PP-RP-5`, `A5-FACADE-4`, `A5-PP-RP-2`, `A6-PP-EST-DSP-1`, `A6-PP-EST-DSP-2`, `A6-PP-EST-H2O-1`, `DQ-PAY-2`

**`RF-20` → `INJ7VXE7`** — `A3-CRUD-4`, `A3-IMAGE--6`, `A3-IO-6`, `A3-PP-CRUD-3`, `A3-ROOMS-8`, `A4-CUSTOM-5`, `A6-ZONE-C-2`, `A6-ZONE-C-5`

**`RF-22` → `IN5ATBW9`** — `A4-STATE-3`, `A4-STATE-4`, `A4-STATE-5`, `A4-STATE-9`, `A5-SVC-1`, `A5-SVC-5`, `A5-SVC-8`

**`RF-23` → `IN76GE4W`** — `A1-SERVIC-3`, `A2-JOB-4`, `A3-SNAP-4`, `A6-ZONE-C-8`, `DQ-PAY-4`, `DQ-ZONE-1`, `DQ-ZONE-2`, `DQ-ZONE-3`, `DQ-ZONE-4`, `DQ-ZONE-5`

**`RF-24` → `INCFMPP1`** — `A1-ID-1`, `A1-ID-3`, `A1-ID-5`, `A1-ID-6`, `A2-REC-2`, `A6-TRK-5`

**`RF-25` → `INMKEHPQ`** — `A1-ID-2`, `A1-ID-4`, `A2-POLYGO-5`, `A2-REC-1`, `A2-REC-3`, `A2-REC-5`, `A2-REC-6`, `A2-REC-7`, `A2-REC-8`, `A3-CRUD-2`, `A3-CRUD-3`, `A3-CRUD-5`, `A3-CRUD-6`, `A3-IMAGE--1`, `A3-IMAGE--4`, `A4-CUSTOM-6`, `A5-FURNIS-4`, `A6-GUARD-5`, `DQ-Q-5`, `DR-ONB-1`, `DR-ONB-2`

**`RF-26` → `INSJM6KC`** — `A5-AG-1`, `A5-AG-2`, `A6-AGX-1`, `A6-AGX-2`, `A6-AGX-3`, `A6-AGX-5`, `A6-AGX-6`, `A6-PP-EST-BLK-1`

**`RF-27` → `INNPA4ZV`** — `A6-AGX-4`, `EP-5`, `INF-9`

**`RF-28` → `INJSETB0`** — `A1-SERVIC-4`, `A1-SERVIC-5`, `A1-SERVIC-6`, `A1-SERVIC-7`, `A1-WIRE-3`, `A1-WIRE-4`, `A2-JOB-5`, `A2-JOB-6`, `A3-IMAGE--10`, `A3-ROOMS-3`, `A3-ROOMS-4`, `A4-CUSTOM-7`, `A4-SETUP-15`, `A5-FACADE-5`, `A5-SVC-9`, `A6-ZONE-C-7`

**`RF-29` → `INJW5J2A`** — `A1-EST-9`, `A2-DRAFT-5`, `A2-GEO-2`, `A3-IO-4`, `A3-SNAP-2`, `A4-STATE-7`, `A6-TRK-6`, `A6-TRK-7`, `A7-ROBORO-2`, `DR-ONB-5`

**`RF-30` → `IN96V4SA`** — `A1-REG-1`, `A1-REG-4`, `A2-LIFE-3`, `A6-GUARD-3`, `DR-DOCK-1`, `DR-DOCK-2`, `DR-DOCK-3`

**`RF-31` → `INNJ6SGC`** — `A4-AJ-1`, `A4-POSE-1`, `A4-POSE-2`, `A4-POSE-5`, `A6-TRK-1`, `A6-TRK-2`, `A6-TRK-3`, `A6-TRK-4`, `DQ-PH-6`

**`RF-32` → `INYA5T84`** — `A1-SERVIC-1`, `A1-WD-5`, `A3-COMMON-2`, `A4-POSE-4`, `A4-SETUP-2`, `A4-SETUP-3`, `A4-SETUP-5`, `A4-SETUP-9`, `A6-VAC-3`, `DQ-DE-3`, `DQ-DE-4`

**`RF-33` → `INTCWVFM`** — `DR-DBG-1`, `DR-DBG-2`, `DR-DBG-4`, `DR-DBG-6`, `DR-DBG-7`, `DR-DIAG-1`, `DR-DIAG-2`, `DR-DIAG-3`, `DR-DIAG-4`, `DR-DIAG-5`, `DR-LR-1`, `HW-DIAG-1`

</details>

## Resolved WITHOUT an anchor

These are answers, not gaps. A finding here is fully dispositioned.

**`RF-21`** (13 findings) — deliberately unanchored. Its own family record: 'shared_invariant: none single -- grouped for packet economy (one file, one reviewer context), NOT as a shared-repair family. Explicitly a bounded-batch, not a centralization.' Eleven independent estimator defects sharing a consumer, not a rule.

**`RF-34`** (19 findings) — deliberately unanchored. Its own family record says shared_invariant: 'none single -- platform batch grouped for packet economy'. There is no one rule to anchor; the members are unrelated platform fixes. Not a gap.

**`RF-35`** (20 findings) — deliberately unanchored. Ruled 2026-08-18. No enforcement site exists ANYWHERE in the tree, and 00b requires naming one -- 'an unregistered rule is honest; a registered rule with no consequence is not'. Its two rules are recorded under 00b's 'Not yet registered' instead. Re-open only if something starts enforcing them.

**`RF-09`** (13 findings) — rule stated, **unenforced**. Real rule, NOT enforced -- map_source.py states the absence itself: no map-geometry version stamping mechanism exists to compare against. Recorded under 00b 'Not yet registered'; mint an anchor when something enforces it. Recorded under 00b's *Not yet registered*; mint an anchor when something enforces it.

**`BATCH:*` / `DEF-*`** — packet *dispositions* (how work was batched), not repair
families. They share no invariant by construction, so anchoring them as groups would
manufacture the un-falsifiable claim this campaign spent its time removing. Members tag
individually or not at all, and *not at all* is legitimate for a one-off with no durable
rule behind it.

## Coverage

| | findings | |
|---|--:|--:|
| anchored | 348 | 72% |
| decided: no anchor | 48 | 10% |
| rule stated, unenforced | 13 | 3% |
| disposition group | 75 | 15% |
| OPEN | 0 | 0% |
| **total** | **484** | |

Every finding is dispositioned. That is what makes the corpus retirable.
