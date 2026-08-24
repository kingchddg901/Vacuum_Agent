# 40 — Diagnostics and Evidence

**Scope.** Four mechanisms for answering *what did it actually do*: the support dump, the silent
log ring, the decision record that makes invisible branches visible, and the semantic receipt
protocol. They are layered rather than alternative, and §5 gives the one rule that separates them.

Everything here is about the gap between what a system does and what it can later be asked about.
Three of the four exist because a specific question could not be answered after the fact.

---

## 1. The support dump must not change what it reports

`diagnostics.py::async_get_config_entry_diagnostics` powers the Download Diagnostics button.
The dump is support-oriented and brand-agnostic, and its most valuable section is
**entity resolution** — for every role the adapter declares, the entity it resolved to, whether
that entity exists, and its current state.

That section is first for a measured reason: the most common *"I can't configure my rooms"* report
is a missing or blank active-map sensor, and it shows up here at a glance.

⚠ **The dashboard snapshot is deliberately excluded**, and the reason is the important part:
computing it can advance room timing and fire room-transition events during a live clean. A
diagnostics download has to stay **read-only**, because a support tool that perturbs the run it is
reporting on produces evidence about itself.

That constraint is easy to lose. The snapshot is the single richest object in the system and the
obvious thing to include; what makes it wrong is not its size but its side effects.

---

## 2. The flight recorder captures one integration without flooding the log

Turning on debug logging for an integration floods the *shared* Home Assistant log — noisy, and
sometimes enormous. `debug_capture.py::DebugCapture` captures one integration's debug output into
a **bounded in-memory ring** instead, and dumps it on demand.

Two properties are worth noting:

- **It is deliberately drop-in and integration-agnostic.** The module carries its own licence
  header and setup instructions, and nothing in it names this integration. It is written to be
  copied into somebody else's component with one setting changed.
- **Redaction is configurable at the boundary** rather than at each call site, so what must never
  reach a shared dump is filtered in one place.

---

## 3. A branch that returns silently cannot be captured

`decision_log.py::emit` writes one machine-readable record per decision point, and it exists
because the flight recorder alone was not enough.

The case that produced it: a room-timing fallback fired through **one of four silent `return None`
paths**, and after the fact there was no way to tell which. The line that states the principle is
the one to carry:

> The flight recorder can only capture what the code emits; a branch that returns silently is
> invisible to it no matter how the capture is configured.

So the two are not redundant and neither replaces the other. **Capture is a buffer; the decision
log is an emission discipline.** Turning the capture up cannot compensate for code that says
nothing.

The module also refuses a tempting name. It is not called `trace_*`, because that prefix already
belongs to the pose-path capture modules, and filing an unrelated thing under an established prefix
is how two subsystems become one in a reader's head.

---

## 4. Receipts: an edge asserted by both ends

`receipts/` is a pilot of a stricter idea — **radio discipline**. A receipt is shaped like a
transmission, addressee first:

```
TO | this is | FROM | outcome | facts... | [provenance]
```

Addressee first for two reasons given in place: every station decides on the first token whether to
keep listening, and putting it first states the **obligation** before the content.

Three design rules make it more than a log format:

**The reply names the caller back.** An edge in the call graph is therefore asserted by *two*
parties. A pass-through that claims it called something is contradicted by that something naming
whoever really called it — so the graph is checked against itself rather than against somebody's
reading of the code.

**Messages do not nest.** No receipt carries its ancestry; each names only its immediate
neighbours, and the chain is reconstructed at replay time by joining on correlation and the
to/from pair. That is what keeps a receipt **constant-size at any depth** — if messages nested,
the deepest paths would cost the most, which is backwards.

**Provenance marks the injection point and is never inherited forward**, for the same reason:
inheriting a marker *is* ancestry in the message. A reader learns that a chain began synthetically
by joining at replay, like anything else structural.

Cost is treated as a design constraint rather than an afterthought:
`receipts/__init__.py::emit` checks the log level **before** it touches anything else, and facts
are passed as positional values that are already locals at the call site — never a dict
comprehension built to be discarded.

### One catalog, two renders

`receipts/catalog.py` holds meaning, fields and prose for every entry, and both the raw wire view
and the human prose view are **projections of it**. Nothing is maintained twice, because *two
documents drift and the drift is one-way and silent.* The card's own translation source is treated
the same way, with a check that fails fatally on a key used but not defined.

What the catalog deliberately does **not** carry is the contract — what a station is *supposed* to
do. That lives in the design docs, and the catalog holds a pointer rather than a copy:

> the design doc says how the system is supposed to work; the recorder says what this execution
> actually did

Copying the contract into the catalog would create exactly the second document that drifts.

---

## 5. Which one to reach for

| question | mechanism |
|---|---|
| what does this install look like right now | the support dump — §1 |
| what did this integration log during that run | the flight recorder — §2 |
| which branch was taken at a decision with no output | the decision log — §3 |
| who called whom, and did both ends agree | receipts — §4 |

The ordering is by **what has to exist beforehand**. The dump needs nothing. The recorder needs
logging to have happened. The decision log needs the code to have been instrumented at the branch.
Receipts need both ends instrumented and a catalog entry.

Reaching for a heavier mechanism than the question requires is wasted work; reaching for a lighter
one produces a confident answer to a question it cannot actually see — which is how four silent
return paths looked like one.

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
