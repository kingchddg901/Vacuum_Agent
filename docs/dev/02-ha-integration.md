# 02 — The Home Assistant Surface

**Scope.** Everything this integration exposes to Home Assistant and everything it takes from it:
the four contract functions, the six entity platforms, the eighty services, and the **eleven
events** — which are the one part of that surface with no other owning document.

The rest of this page is a chooser. Each surface has its own document; what belongs here is how
they relate and when to reach for which.

---

## 1. Four ways in, one way out

| surface | what it is for | doc |
|---|---|---|
| **config entry** | install, reload, unload, delete | [39](39-the-entry-point.md) · [44](44-onboarding-and-first-run.md) |
| **services** | do something, or ask something — eighty of them | [36](36-the-service-layer.md) |
| **entities** | continuous state, across six platforms | [37](37-the-entity-surface.md) |
| **panels** | one sidebar entry per vacuum | [44 §3](44-onboarding-and-first-run.md) |
| **events** | *this happened* — eleven, fire-and-forget | §2 below |

Services and entities are the two a person touches. **Events are the one surface that is purely
outbound**: nothing in this integration listens to its own events, and nothing waits on one.

---

## 2. The event surface

Eleven distinct events, fired from **26 sites** across the tree:

| event | fired | meaning |
|---|---|---|
| `eufy_vacuum_job_finished` | 6× | a run reached a terminal state |
| `eufy_vacuum_run_incomplete` | 5× | it ended without covering the queue |
| `eufy_vacuum_stall_detected` | 3× | the robot appears stuck |
| `eufy_vacuum_room_started` | 3× | a room began |
| `eufy_vacuum_room_finished` | 2× | a room ended |
| `eufy_vacuum_path_blocked` | 2× | a route the run needed is closed |
| `eufy_vacuum_room_skipped` | 1× | a queued room was passed over |
| `eufy_vacuum_room_completed` | 1× | (see §3) |
| `eufy_vacuum_external_run_pending` | 1× | an app-started run is waiting for review — [30](30-external-runs.md) |
| `eufy_vacuum_job_progress_tick` | 1× | a lightweight polling signal |
| `eufy_vacuum_stall_captured` | 1× | a stall capture was written — [15](15-stall-capture-image.md) |

**The card subscribes to five of the eleven** — job finished, run incomplete, room started, room
finished, room completed. The other six exist for automations and for diagnosis, which is the
point: the event surface is wider than the card's needs *on purpose*, because an automation is a
first-class consumer and not an afterthought.

Two payload builders are shared rather than per-site —
`services/_common.py::job_finished_event_payload` and
`services/_common.py::run_incomplete_event_payload` — because the same event fires from several
places and a per-site payload would drift into several shapes under one name.

**A run's most important events fire more than once from different code paths.** Job-finished has
six fire sites because a run can end six ways ([06](06-run-end.md)); the shared builder is what
keeps those six agreeing on what a finished job looks like.

---

## 3. Ten event names derive from the domain and one does not

Ten of the eleven are built as `f"{DOMAIN}_…"` in `const.py`.
`EVENT_ROOM_COMPLETED` is a **hardcoded string literal**, and it lives in `mapping/tracker.py`
rather than with the others.

> ✅ **CORRECTED 2026-08-23.** `EVENT_ROOM_COMPLETED` and its neighbour `EVENT_BOUNDARY_SAVED` now live in
> `const.py`, derived from `DOMAIN` like their nine siblings. The derived strings are
> byte-identical to the literals they replace, so nothing changed on the wire and the card's
> subscription is unaffected — verified by asserting the resolved values. `mapping/tracker.py`
> re-exports both, so existing importers keep working. All eleven outbound events now derive
> from one place.

Nothing is broken today — the literal matches what the pattern would produce. But it is the one
event name that would not follow if the domain changed, and it is the one that is not visible when
reading the event block in `const.py`. Being defined away from its siblings is *why* it drifted from
their shape.

⚠ There is a second-order point worth stating, because it is easy to miss: the domain those ten
derive from is itself **re-exported from the brand package** ([45 §1](45-the-shared-layer.md)). So
ten public event names, subscribed to by automations in users' homes, are ultimately derived from a
constant filed under one brand's folder.

---

## 4. Which surface answers which question

| you want to | use | not |
|---|---|---|
| know a value continuously | an **entity** | polling a service |
| know the moment something happens | an **event** | watching an entity for a transition |
| change something | a **service** | writing to the store |
| ask something complex | a **service with a response** — 77 of 80 return one ([36 §4](36-the-service-layer.md)) | reading `.storage` |
| see everything at once | the **diagnostics download** ([40 §1](40-diagnostics-and-evidence.md)) | the dashboard snapshot, which has side effects |

The last row is the one that catches people. The richest object in the system is the dashboard
snapshot, and computing it can advance room timing and fire room-transition events during a live
run — so it is deliberately excluded from diagnostics, and reaching for it as a debugging shortcut
perturbs the thing being debugged.

---

## 5. What Home Assistant owns, and what that costs

Three things this integration depends on and does not control:

- **The state machine.** Every fact about the vacuum arrives as an entity state published by
  another integration. That integration may not have finished starting when setup runs, which is
  why setup runs a second time ([39 §2](39-the-entry-point.md)).
- **The entity registry.** Entity ids are a naming convention, not a contract — users rename them
  and integrations change them — which is why roles are resolved and rescued rather than assumed
  ([34](34-capability-detection.md)).
- **The store helper.** It is the only supported path to disk; Home Assistant rewrites `.storage`
  from its own memory on shutdown, so a hand-edit is overwritten rather than merged
  ([32 §1](32-the-store.md)).

One thing worth knowing about HA's own behaviour, because a guard depended on the opposite: **a
service call naming an entity that does not exist does not raise.** It logs a warning. A safety
abort wrapped in `except Exception` around such a call is inert
([42 §4](42-the-send-side.md)).

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| the events are the card's API | the card subscribes to five of eleven; the rest are for automations — §2 |
| an event fires from one place | job-finished fires from six, which is why the payload builder is shared — §2 |
| the event names are all built the same way | ten derive from the domain; one is a hardcoded literal in another file — §3 |
| the domain is the framework's | it is re-exported from the brand package, and ten public event names derive from it — §3 |
| the dashboard snapshot is a good debugging read | computing it has side effects during a live run — §4 |
| a missing service target raises | HA logs a warning, and a guard relying on the exception never fires — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
