# DESIGN — trace_route: the execution-route instrument ("courthouse security footage")

**Status: DESIGN BANKED 2026-08-03, no code. Converged across a three-agent review loop
(Chris ↔ GPT ↔ Claude, two rounds). Build on Chris's go; small tool, not a subsystem.**

## Identity — what this is

A standalone, on-demand instrument that answers: **"did the code do this the WAY we believe
it did?"** A green outcome proves success; only the route proves the success used the
intended mechanism. It is NOT a proof-admissibility gate (that job goes to declared
warrants + coverage contexts in the proof harness — separate, tiny, already mounted on
harness v2 / `_sweep_proofs.py`), NOT the deferred Semantic Trace system (no persistence,
no schema, no runtime residency), NOT the Flight Recorder (no log capture), and NOT
admissible evidence for race proofs (observation alters scheduling; races stay
uninstrumented — await-interleaving stress + invariant checks).

The recurring enemy it targets, named across both reviews: **false agreement about which
code actually ran** — stub agreed with the caller not the callee; permissive fake accepted
an omitted argument; finalizer "tested" but never invoked; fixture returned through an
earlier guard; sibling consumer bypassed the shared helper; branch structurally present but
operationally unreachable; exception swallowed and replaced by a plausible fallback; test
asserted the final shape without proving which mechanism produced it.

## Shape

`tools/trace_route.py` — wraps any pytest invocation or scenario script; scopes to
`custom_components/eufy_vacuum` by module prefix; emits a compact agent-readable stream
(function enter/exit, branch outcomes, exception edges; monotonic sequence). Mechanism:
`coverage.py` dynamic contexts or `sys.settrace` — whichever proves less async-hostile in
the pytest-homeassistant event-loop env (coverage.py preferred: async line attribution is
already solved there; settrace fights coverage/debuggers and blurs coroutine hops). Zero
source modification — no instrumented worktrees. Attach, run, read, discard.

## Three modes (the whole v1 surface)

1. **Route read** — run one scenario, agent reads the route, reports how the outcome was
   reached. The discovery mode: catches surprises nobody declared.
2. **Fallback census** — run the suite (or one scenario) green, then report every executed
   degraded branch: each swallowed exception, fired fallback, rescue path that carried a
   passing test to its assertion. Mechanizes the audit prompt's "silent degradation paths
   that conceal failures." Prime probe stage for audit-2 S1–S3 at the pinned SHA.
3. **Three-path fix review** — for a landing packet: trace the scenario at the BEFORE SHA
   and the AFTER SHA (two pinned worktrees, diff on demand — NO stored baselines), compare
   against the expected repaired route. Catches partial closure mechanically: "intended
   branch no longer reached; earlier fallback now returns the expected value; output
   appears fixed, named defect not proven fixed." This is the A3-REC-3 / RP-013c
   half-closure class, which cost the campaign its most expensive reopens.

Test-archaeology (refactor breaks a test → diff old/new routes → "the test patches a method
that stopped participating; fix the test, not production") is mode 3 with a different
question — comes free, needs no extra machinery.

## Limits (agreed by all three reviewers — state them wherever output is shown)

- Proves what EXECUTED, never what SHOULD execute. A vanished mechanism still needs
  architectural history to decide whether its removal was authorized.
- Route-reached is necessary, not sufficient: a proof can walk every expected line and
  assert a retired contract. Judgment against the current spec stays verifier-tier work.
- Race behavior: out of scope, permanently.

## Non-goals that keep it from becoming Semantic Trace

No persisted traces, no baseline store (A/B = two worktrees, diffed live), no value
capture in v1 (control flow only; the stub-consumption case needs just a spy bool + a
coverage bool), no schema versioning, no live-HA runtime attachment.
