# PM-3 — The Instrument Shop

**Postmortem doc 3 of 4** (see `synthesis/DESIGN-postmortem-compiler.md` §7 for the set).
Every tool the audit campaign built, written as an operator's manual for the next audit.
INTERNAL document. Written 2026-08-04 from the tools' own docstrings and design docs, not
from recollection.

**Format per instrument — four fields, deliberately:**
- **Answers** — the question it exists to settle.
- **Born from** — the failure that forced it. (This is the field that rots first in
  memory and matters most later: a tool whose origin is forgotten gets "simplified"
  back into the failure it prevented.)
- **Invocation** — exact, runnable.
- **Trust boundary** — what its output must NEVER be taken to prove. Every instrument
  here has one; an instrument without a stated limit is how false confidence
  re-enters the system.

Standard build/test gates (docker suite, `test:units`, i18n ratchet, mkdocs, visual
baselines) are NOT duplicated here — they predate the campaign and live in
SESSION_HANDOFF §3. This catalog is what the campaign *added*.

---

## A. The proof system — "is this defect really fixed?"

### A1. `_proof_harness.py` — the shared reproducer harness (v2)

- **Answers:** gives every reproducer inert scaffolding (stubs, tmp-backed real stores,
  attribute-writable namespaces) so a proof drives the REAL production function.
- **Born from:** tranche-1 proofs each rebuilt their own stubs, and `_proof_battery.py`
  demonstrated the fatal version of the shortcut — a harness that "helpfully" normalizes
  a value makes every proof pass for the wrong reason simultaneously. Hence the
  **INERTNESS RULE** at the top of the module: the harness must never implement,
  emulate, or correct any production behaviour; if it contains an `if` deciding a
  domain question, it is a bug in the harness.
- **v2 additions (2026-08-04, `208a884`), each answering a measured staleness class:**
  - `Proof.patch()` — the only sanctioned stub path; a registered stub that is never
    invoked FAILS the proof (catches the moved-call-site class with zero declarations).
  - quarantine rendering — a file with any `UNEXPECTED`/`ERROR` case renders
    `QUARANTINED — 0 of N admissible`; no case in a compromised file counts as
    evidence. Never fires on `BEFORE` (healthy partially-landed packets legitimately
    report mixed `BEFORE · AFTER`).
  - `require_contract()` — mechanism-sensitive proofs declare the contract version they
    were written against, checked against production's `contract_versions.py`
    (seeded: `completed_room_evidence` v2). The only handle on the retired-mechanism
    class, kept deliberately narrow.
  - `proof.case()` exposes only `before=`/`after=` — no third "correct either way" arm
    can be written.
- **Invocation:** imported by `_proof_*.py`; each proof runs standalone:
  `python .claude/notes/_proof_<name>.py` (inside the test image for backend proofs).
- **Trust boundary:** an AFTER verdict proves the *proof's* claim holds — it does not
  prove the packet's whole clause list landed (that is the x-of-y ledger's job), and a
  proof inherits its packet's authority: written from a wrong packet it certifies the
  wrong packet.

### A2. The `_proof_*.py` corpus — 61 reproducers

- **Answers:** per-packet executable evidence: the defect existed (BEFORE on frozen
  source) and the repair holds (AFTER on current source).
- **Born from:** "run the reproducer, not just pytest" — the suite can stay green while
  the specific defect behaviour survives.
- **Rule with teeth:** a proof must be observed to FAIL on frozen source *for the
  intended reason* before its packet is worked (Pass-6 rule 7). An adversarial pass
  over nine proofs found defects in four, one structurally unable to flip (RP-016
  case 3 hand-simulated the mutation without calling production).
- **Trust boundary:** proofs go stale silently when *other* fixes land — that is A3's
  entire reason to exist. Never bank a proof verdict older than the last relevant
  landing.

### A3. `_sweep_proofs.py` — the staleness sweep

- **Answers:** is every reproducer still measuring production?
- **Born from:** `_proof_inflight_askers.py` reported UNEXPECTED on a CORRECT fix —
  RP-037 moved the ticker onto `apply_job_progress_tick` and the proof kept watching
  the old symbol. Three of the four observed staleness classes happen *because
  something else was fixed correctly*; batch-landing makes this routine, not rare.
- **Invocation:** `python .claude/notes/_sweep_proofs.py` (run at every pinned SHA;
  AUDIT-2 gate 13). Buckets: `AFTER` (good) · `BEFORE` (packet open — expected, not a
  problem) · `UNEXPECTED`/`ERROR` (adjudicate NOW) · `NO_TALLY` (pre-harness proofs
  that print no verdict line — means "no verdict", NOT "broken"; v2 makes the class
  unrepeatable for new proofs).
- **Trust boundary:** the sweep classifies; it does not diagnose. Which staleness class
  hit, and whether the underlying repair still holds, is adjudication work.

### A4. The `_probe_*.py` pattern — executable probes during discovery

- **Answers:** does the suspected behaviour actually occur, before anyone writes a
  finding or a fix?
- **Born from:** design review of Phased Jobs found 8 defects; executable probes then
  found 6 MORE in 8 tries — before wiring, while a fix was free. (Examples:
  `_probe_issue48_edge_mopping.py`, `_probe_completion_without_binary.py`,
  `_probe_replay_segmenter.py`.)
- **Rules:** probes live in notes/scratch, never modify repo files, run against a
  read-only checkout in the test image; transcripts are evidence.
- **Trust boundary:** a probe proves reachability of a behaviour under its fixture —
  severity still needs the user-guide check (charter delta 9), and a probe fixture can
  itself fabricate an impossible state (that is a named causal edge in PM-1's graph).

## B. Route & replay evidence — "did the intended mechanism run?"

### B1. `tools/trace_route.py` — route capture, fallback census, route diff

- **Answers:** a green outcome proves success; only the executed ROUTE proves the
  success used the intended mechanism.
- **Born from:** the campaign's recurring enemy — false agreement about which code
  actually ran (charter delta 7; three-agent design convergence in
  `DESIGN-trace-route-tool.md`). First census run on the green replay test immediately
  found 4 live rescue paths, two previously unnamed.
- **Invocation:**
  - `python tools/trace_route.py run -o route.json -- python -m pytest tests/replay --no-cov`
  - `python tools/trace_route.py census route.json` — every EXCEPT handler that
    executed under a green run (the mechanical form of "silent degradation that
    conceals failures").
  - `python tools/trace_route.py diff before.json after.json` — routes at two SHAs,
    each captured in its own pinned worktree (the three-path fix review: catches
    "output appears fixed, named defect not proven fixed" — the A3-REC-3 class).
- **Trust boundary (printed in its own docstring — repeat it wherever output is used):**
  proves what EXECUTED, never what SHOULD execute; a vanished mechanism still needs
  architectural history to judge; deterministic tracing is NEVER race evidence.

### B2. `tests/replay/` — the recorder-replay run harness

- **Answers:** drive the REAL listeners with REAL recorded device streams — a fixture
  recorded from the device cannot encode intended-instead-of-actual behaviour (the
  cure for the mock-failure classes, not just their ledger).
- **Born from:** charter delta 12; Chris feeds labeled HA-recorder exports of actual
  Alfred/Ivy runs. Proof-of-life: the real pj_2026-08-02T23-04-45 window replays into a
  noticed → buffered → grace-finalized external capture with the full suite green.
- **Mechanics:** `bundle.py` (extractor) + `harness.py` (frozen-time driver through the
  public state-change seam; stimulus-only — the integration's own entities are
  excluded from the stimulus; settle phase for scheduled tail work). Corpus lives in
  `_frozen/replays/` (57 Alfred + 11 Ivy episodes, inventoried and cross-matched).
- **Open remainder:** `blocked → design: [dispatched-oracle mode]` — start the job from
  the archived record's own queue/payload and assert the finalized record against the
  archive.
- **Trust boundary:** replay is deterministic — it reproduces sequences and gaps,
  NEVER await-interleavings; race findings stay with the uninstrumented race
  methodology. And the corpus over-represents short kitchen-first test runs — fine for
  lifecycle/finalize concordance, NOT a representative workload for estimator or
  coverage claims.

### B3. `_crossmatch_replays.py` — the concordance gate

- **Answers:** do the device's account (frozen recorder episodes) and the system's
  account (learning archive) still agree about the same 68 runs?
- **Born from:** outcome tests can stay green while finalization drifts; concordance
  against the device's own record cannot (route-evidence thinking applied at system
  level). Baseline 2026-08-04: 57/57 + 11/11 matched, zero orphans either direction,
  boundary deltas Ivy ≤1s / Alfred ≤138s (first-room transit).
- **Invocation:** `python .claude/notes/_crossmatch_replays.py --check` (exit 1 on
  regression; thresholds = baseline + headroom: zero unmatched, zero orphans, Ivy ≤5s /
  Alfred ≤180s). **Run after ANY change to job lifecycle, record schema, or the
  finalizer.** In AUDIT-2 gate 8's green-at-the-pin list and S1's probe kit.
- **Trust boundary:** the frozen window never changes — so it detects *destabilization
  relative to that window*, not correctness of new behaviour the window never
  exercised. A green check on a new feature proves nothing about the feature.

## C. Ledger machinery — "never assert a count in prose"

The campaign's bookkeeping failed in both directions (phantom-open AND false-closed),
and each generator exists because a specific hand-maintained number was caught lying.

### C1. `_gen_audit_doc.py`
Generates `docs/dev/maintenance/highly-aggressive-audit.md` — COMPLETED from `git log`
over the campaign window (first fix `31da1fe`), OPEN from `_audit_runs.json`. **Never
hand-edit the generated doc.** Trust boundary: subject-line parsing — a `RP-XXX:`
subject can be authoring, not landing (the RP-047 trap); `git show --stat` is the
landing test.

### C2. `_gen_checklist.py` → `OPEN-FIX-CHECKLIST.md` (+ `_open_findings.json`)
The open-fix ledger from audit JSON + the landed-packet manifest. Born from: hardcoded
standing tables drifting ~2.5× in both directions. Trust boundary: only as good as its
manifest (see C3) and the packet-closure map (see C5's uncertainty band).

### C3. `_sync_landed_packets.py`
Reconciles `_landed_packets.json` against git. Born from: the manifest recorded 20
packets while 58 had landed, so every regeneration silently reverted 38 packets'
`[x] applied` marks — and someone was hand-patching a *generated* file to compensate
("165 findings applied / 319 open" while the truth was 455/29 — doc-vs-code drift
sitting inside the campaign's own bookkeeping). Existing entries are NEVER overwritten;
`hardware:` blocks (the only record a packet met a real vacuum) are preserved verbatim.
Invocation: `python .claude/notes/_sync_landed_packets.py [--write]`.

### C4. `_gen_repro_status.py` → `REPRODUCER-STATUS.md`
Reproducer coverage derived from packets + disk. Born from: a handoff doc carrying
"26 reproducers remain" that was wrong by ~2.5× and was actively mis-scoping work.
This is the trustworthy packet tracker across ALL synthesis docs (the checklist's
"landed" list tracks only the original campaign).

### C5. `_gen_packet_closure.py` → `packet-closure-map.json`
Per-packet declared closures (wave-0/1 by `repair_family`, wave-2+ by `finding_ids`),
extracted with field-scoped regexes because the packet YAML blocks mix prose. **Known
measured uncertainty band:** family-credit under-credits explicitly-named findings and
over-credits partial families; BOTH naive repairs were tried and are provably wrong in
opposite directions (9 findings falsely reopen / 17 falsely close). Per-finding
adjudication is AUDIT-2 gate-9 work — do not "fix" the generator.

### C6. `_check_advanced_doc_drift.py`
Mechanical doc-vs-code diff of the CONTRACT surface (`docs/advanced/` — service
parameter tables, event names, 700+ lines of copy-paste automation YAML). Four checks
in ~1s; exit 1 on a BREAK. Born from: this is the one doc tree where drift doesn't
confuse a reader — it silently breaks their automations; and it is structurally
diffable, so agent reading time is waste. Trust boundary: the exempt list (flight
recorder + queue-break surface while Phased Jobs is rebuilt) lives in the script and
must be revisited if either decision changes; GAPS (real-but-undocumented) are a doc
task, BREAKS are a lie in print.

## D. Evidence stores — the append-only memory

- **`_frozen/`** — the digest-verified evidence vault (`.gitattributes -text` so SHA-256
  digests survive a fresh clone): `corpus/` (canonical findings), `journals/` (raw agent
  returns, upstream of post-processing — recovered audit #18's verdicts when
  post-processing dropped them), `audits/` (early-era prose), `baseline/` (hardware
  before/after captures), `replays/` (the recorder corpus), `reproducers/`.
- **`_premises.json`** — the premise ledger: shared empirical claims with
  status/evidence/retired_by. Born from: ~1.4M tokens spent by four verification groups
  re-deriving a premise disproved on-device the day before. A retirement auto-flags
  every dependent finding *carrying the retiring evidence with the flag*. Hard rule:
  every verification agent reads `_adjudicated_findings.json` unconditionally.
- **`_adjudicated_findings.json` / `_reopened_findings.json`** — rulings and reopens,
  append-only. The reopen record is what makes "closure is binary; findings are not"
  enforceable.
- **`corpus/audit-findings-canonical.jsonl` + `closure-matrix.json`** — the 516-record
  normalized corpus and the findings→families matrix (machine-checked, 0 unassigned).
- **Trust boundary for ALL stores:** append, never rewrite. A hand edit to a generated
  or frozen artifact survives until the next regeneration and then vanishes — or
  worse, doesn't, and becomes unattributable fact.

## E. One-off instruments worth keeping

- **`_score_job_active_rules.py`** — scored candidate "job-active" predicates against
  real recorded history instead of arguing about them (#46). The pattern generalizes:
  when a predicate is disputed, score all candidates against the archive.
- **Flight recorder as audit instrument** — product feature, but every hardware
  checkpoint captures with Everything (unfiltered) via
  `eufy_vacuum.debug_capture_start` (the switch cannot set target/ring). The capture
  IS the evidence format for `hardware:` blocks.
- **The pinned-worktree discipline** — not a script, but the instrument that keeps two
  concurrent sessions from contaminating evidence: audits run against
  `git worktree add` at a pinned SHA, never the shared tree (AUDIT-2 gate 10).

---

## The meta-pattern, for whoever builds the next instrument

Every tool above follows the same shape, and the next one should too:

1. It exists because a specific measured failure occurred (named in its docstring).
2. It DERIVES its answer from primary sources (git, disk, coverage, the archive) —
   never from a number a human remembered to update.
3. It states its own trust boundary, and the boundary is repeated wherever its output
   is consumed.
4. Its output is either regenerated at read time or frozen with a digest — nothing in
   between.

The campaign's one-line version: **check the code, not the count — and make the check
cheap enough that nobody is tempted to trust the count.**
