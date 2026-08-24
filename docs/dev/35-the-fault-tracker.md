# 35 — The Fault Tracker

**Scope.** How upstream faults are latched, survive a restart, and reach the job record: the three
buffers and why they have different lifetimes, the two-phase handoff to finalization, and where the
line between Home Assistant's words and a brand's words is drawn. What is *deducted* from a run's
cleaning time is [06 §6](06-run-end.md); the per-brand code tables are
[23 §5](23-eufy-adapter.md) and [24 §4](24-roborock-adapter.md).

`core/error_tracker.py::ErrorTracker` reads the vacuum entity and its error-message sensor through
Home Assistant's state engine and **never imports upstream coordinator or parser code.** Everything
it knows about a fault arrives as a state value, which is what makes it survive an upstream refactor
that would otherwise be a breaking change.

---

## 1. Three buffers, three lifetimes

All three live under one per-vacuum record in the store.

| buffer | lifetime | cleared by |
|---|---|---|
| `active_run_error` | sticky for the duration of a job | `core/error_tracker.py::commit_active_run`, and only after the durable record is written |
| `last_device_error` | persists until a human acknowledges it | the acknowledge service |
| `recent_errors` | a ring of the last fifty rising edges | nothing — it rolls |

They are not three views of one thing. `last_device_error` is overwritten on **every** rising edge
regardless of whether a job is running, because "what went wrong most recently on this machine" is a
question that does not care about run context. `active_run_error` only accumulates while a job is
active, because it is evidence *about that run*.

---

## 2. The handoff to finalization is two-phase, deliberately

The finalizer reads the active-run latch through
`core/error_tracker.py::peek_active_run` — a **non-destructive** read — and the latch is cleared
separately by `core/error_tracker.py::commit_active_run`, **only after the durable job record has
been written.**

The failure this defends against is specific: a read-and-clear would destroy the run's error history
at the moment it was consumed, so a save that then failed would leave the run recorded with no
faults and no way to recover them. Splitting the read from the clear makes the latch a resource the
finalizer *borrows* until the write succeeds.

The same reasoning governs acknowledgement. Acknowledging a fault **while a job is in flight marks
the latch rather than deleting it** — the user has seen it, but the run has not yet been written, so
the evidence has to stay until it lands.

---

## 3. A rising edge is an observation, not a transition

**Any** observation whose value is an error fires a rising edge. It is not gated on a change, so
re-reporting the same fault appends another entry and increments the count. One observation, one
entry.

The accepted cost is stated in place: an HA restart while an error is live records that error a
second time. That is the correct trade for this buffer — under-counting a fault that is genuinely
still happening is worse than a duplicate entry, and the duplicate is visible for what it is.

A **falling edge** is a real transition, back to a not-error value, and it stamps a recovery time on
the newest un-stamped entry. So the two edges are asymmetric on purpose: the rising one counts
observations, the falling one closes intervals.

---

## 4. The late-arrival grace window

When the vacuum entity goes to `error` but the message sensor is still empty, there is nothing yet
to latch. Rather than record a fault with no content or drop it, a one-shot timer is scheduled:

- the message arrives inside the window → the placeholder latch is **upgraded** with the real
  message and code
- the window elapses → the latch is finalized with the brand's unknown-error message and a null
  code

Both shipped brands declare a five-second window. The alternative — latch immediately on whatever is
there — produces a permanent "unknown error" for a fault whose description was a moment late, which
is exactly the case a user cannot act on.

---

## 5. Which strings are the brand's, and which are not

The not-error set is **brand vocabulary**, read from the adapter, and the two shipped brands
genuinely disagree: one declares a sentinel the other deliberately excludes, because on that brand
the word could legitimately appear inside a real error state. The framework's own
`core/error_tracker.py::_NOT_ERROR` is a last-resort fallback for when no adapter is registered, not
the default answer.

The grace window, the error-code attribute names, the unknown-error message and the task-status
error value are all adapter knobs too.

⚠ **The vacuum entity's `error` state is deliberately not among them.** That string is Home
Assistant's own activity value, not a brand's word, so making it configurable would invite a brand
to redefine a platform constant. The test being applied is *whose vocabulary is this* — and it is
the same test that keeps profile axes out of the core migration loop in
[33 §4](33-the-orchestrator.md).

---

## 6. One coercion guard is short

Three classification entry points — `core/error_tracker.py::classify_error_code`,
`core/error_tracker.py::error_source_for_code` and `core/error_tracker.py::error_label_key` —
normalise a code through `core/error_tracker.py::_code_key`, which carries two guards documented in
the Eufy adapter: never a bare integer conversion, because truncating a float lands on a real
neighbouring code, and never accept a boolean, because `bool` is an `int` subclass and `True` would
resolve to code 1.

`core/error_tracker.py::_safe_int`, which reads the code from the entity attribute **before** either
of those sees it, has neither guard.

Both coerced values land on codes that are robot-sourced and not evidence-safe, so their seconds are
deducted from cleaning time — the arithmetic the whole fault table exists to protect. No
non-integer has been observed arriving there, so this is a guard asymmetry with a named input rather
than a confirmed field failure. It is the shorter of two copies of one predicate, which is the
shape worth checking for elsewhere.

---

## 7. Common wrong assumptions

| assumption | reality |
|---|---|
| the three buffers are views of one fault | they have different lifetimes and different clearing rules — §1 |
| the finalizer consumes the latch | it peeks; the clear happens only after the durable write — §2 |
| an acknowledged fault is gone | mid-job it is marked, not deleted — §2 |
| a rising edge means the fault is new | it means the fault was observed; a restart re-records a live one — §3 |
| `error` on the vacuum entity is brand vocabulary | it is Home Assistant's activity value and is deliberately not configurable — §5 |
| the code is normalised once | it is coerced on the way in by a shorter predicate than the one that classifies it — §6 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
