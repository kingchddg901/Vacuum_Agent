# 33 — The Orchestrator

**Scope.** What `core/manager.py` does that is not storage: the ordered construction of fifteen
subsystems, the schema migrations that run on every load, what a restart loses and how each loss is
repaired, and the six notification channels. Persistence and the store's schema are
[32 — The Store](32-the-store.md).

The manager is a **facade over subsystems**, not a monolith — but it is a facade twelve of those
subsystems hold a reference back to. That asymmetry is the most useful measurement in this
document, and §1 gives it plainly.

---

## 1. Fifteen subsystems, and three of them do not need the manager

`core/manager.py::async_initialize` constructs the subsystem managers in sequence. Twelve receive
the manager itself. Three receive only what they actually use:

| construction | subsystems |
|---|---|
| `data` only | themes |
| `data` + `hass` | onboarding, access graph |
| the whole manager | the other twelve — maintenance, dock, profiles, active job, phase runner, run plan, room map, live refresh, clean order, map source, dispatch, external run |

**A subsystem that takes the whole manager can reach anything, so nothing constrains what it
reaches.** The three narrow ones are the only subsystems whose dependency surface is stated in
their signature, and — not coincidentally — the themes manager is also the only one that owns its
own notification list rather than borrowing the manager's (§5).

That is the extractability test in one table: narrow construction and self-owned state travel
together, and the twelve wide ones would each need their dependency on `manager` resolved before
they could move.

---

## 2. The construction order is load-bearing

Three orderings are stated in place as requirements rather than accidents:

- **Themes after the store loads**, because it seeds and owns the theme sub-tree.
- **Phase runner after the active-job tracker**, because its watchdog reads it.
- **Phase re-arming last**, after every subsystem exists — see §3.

Everything else is imported lazily inside the method rather than at module scope. That keeps the
import graph shallow at load time, and it is why a subsystem's import cycle shows up as a runtime
failure during setup rather than as a failed module import.

---

## 3. A restart loses in-memory state, and the repair has two shapes

Persisted state survives a reload; the tasks and timers driving it do not. The load path reconciles
that, and the interesting part is that **the same stale flag needs opposite treatment depending on
what was driving it.**

A persisted strict-order dispatch guard is **released** on load. There is no live watchdog after a
reload, so leaving the guard set would suppress the completion gate *forever* — the run would never
finish. Clearing it lets a room-group run advance through the normal completion path.

A charge-wait or wait phase is **re-armed** instead, at the very end of initialisation. Its only
driver is an in-memory poller the restart also lost, so clearing the guard alone would wedge it in
`started` with nothing to advance it. Re-arming re-spawns the poller *and* re-asserts the guard,
which is why it has to happen after the phase runner exists.

The distinction is worth stating generally: **clearing a stale flag is correct only when something
else will drive the state forward.** When the flag was the only evidence that a driver existed,
clearing it strands the work instead of freeing it.

The same pass drops a deprecated storage block outright — the icon-selects state, left behind when
that platform was removed, which only bloats the file on existing installs.

---

## 4. The migration loop owns metadata, never vocabulary

Every load walks stored rooms and backfills fields added since they were written, using
`setdefault` so a room that already has the key is untouched.

⚠ **This loop consults no adapter, and that is exactly why it must not touch brand vocabulary.**
From the initial release until it was removed, the loop headed its list with a `path_type` default.
That is a per-brand *profile axis*, and stamping it here set it on **every room of every brand**,
including brands whose adapter never declared the axis. The value it stamped stringifies downstream
to the literal `"None"` — which is why that fossil turned up on units with no dispatch path for the
field at all, and why it was simultaneously undroppable and unresettable until an option list
existed to judge it against ([24 §5](24-roborock-adapter.md)).

The line the loop must not cross again is stated in place: profile axes arrive through the declared
catalog and are stripped by `core/manager.py::_finalize_room_update` when undeclared. What is safe
to default here is **framework-owned room metadata** — keys the framework defines for every brand —
and nothing else.

This is the clearest instance in core of the residual-default problem from
[23 §2](23-eufy-adapter.md): a loop with no adapter in scope cannot know whose word it is writing,
so it must only write words that belong to no brand.

---

## 5. Six notification channels, one of them delegated

The manager holds subscriber lists for room updates, run-profile updates, room-history updates,
room-rule-status updates, and new managed vacuums. Registration is idempotent in both directions —
registering twice adds one entry, unregistering something absent is a no-op — so a platform that
re-registers on reload cannot accumulate duplicates.

Theme callbacks are the exception: `core/manager.py::register_theme_update_callback` **delegates**
to the themes manager, which keeps its own list. Five channels live here and one lives in the
subsystem that owns its data, which is the §1 asymmetry showing up again.

---

## 6. Notification is copy-then-isolate

Every notifier does the same two things, and both are defences rather than style:

- **It iterates a copy of the list.** A subscriber that unregisters itself while being notified —
  an entity being removed, most obviously — would otherwise mutate the list under the loop.
- **It wraps each callback in its own try/except and logs the traceback.** One subscriber raising
  cannot stop the others from being told.

Without the second, a single misbehaving entity platform silently stops every other consumer
receiving updates, and the symptom is a stale card rather than an error anyone would connect to the
cause. The failure is logged with the vacuum and map that triggered it, so the broken subscriber is
nameable from the log rather than by elimination.

---

## 7. Common wrong assumptions

| assumption | reality |
|---|---|
| the manager is a monolith | it is a facade over fifteen subsystems — but twelve hold a reference back to it — §1 |
| subsystem construction order is incidental | three orderings are stated requirements, and re-arming must run last — §2 |
| a stale flag should always be cleared on load | only when something else will drive the state; otherwise it strands the work — §3 |
| the room backfill loop is a safe place to add a default | only for framework-owned metadata; a brand axis there produced a fossil on every room of every brand — §4 |
| all update callbacks live on the manager | theme callbacks are delegated to the subsystem that owns the data — §5 |
| a failing callback breaks the notification | each is isolated and logged; the rest still fire — §6 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
