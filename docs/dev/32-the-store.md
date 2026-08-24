# 32 — The Store

**Scope.** The single persistent document everything in this integration writes to: how it reaches
disk, the two write paths and when each is correct, what its schema actually is as opposed to what
it declares, and the two guards that stop a reload destroying it. Initialisation, migrations and
the callback system are [33 — The Orchestrator](33-the-orchestrator.md). The learning subsystem
keeps its own separate file store — [26](26-learning-record-store.md).

There is **one** store, it is written **whole** every time, and every subsystem shares it. Most of
what follows is a consequence of those three facts.

---

## 1. One supported way to disk

`core/storage.py::EufyVacuumStorage` wraps Home Assistant's own `Store` helper, and the comment on
that line states the rule plainly: this is the only supported way our data reaches disk.

Home Assistant rewrites `.storage` from its own memory on shutdown, so a hand-edit to the file is
not merged — it is **overwritten**, and a file it cannot reconcile becomes a `.corrupt` backup. The
consequence stated in place is the useful one:

> If a value can only be changed by editing that file, the missing thing is a service, not a
> licence to edit it.

The store key is imported from the brand package rather than derived, and that is deliberate: the
key is **persisted**, so it cannot be recomputed without orphaning every existing install's data.
It is one of only three core-into-adapter imports in the tree — see
[23 §2](23-eufy-adapter.md).

---

## 2. Two write paths, and the delayed one is a callback

`core/manager.py::async_save` writes immediately. `core/manager.py::async_save_delayed` schedules a
coalesced write about two seconds later through HA's own delayed-save mechanism.

The delayed path exists for high-frequency, low-stakes updates — the motivating case is a theme
draft slider being dragged, which used to trigger **one full-integration-data disk write per
edit**. The trade is stated rather than assumed: losing the last couple of seconds of in-flight
edits to a crash is acceptable; a write per frame is not.

⚠ **The delayed path takes a callback, not data.** The function it is given is invoked at *write*
time, not at call time, so it must keep returning the live dict — a bound method or a closure over
the current data, never a snapshot captured when the call was made. A snapshot here would persist
whatever the store looked like two seconds ago and silently discard everything written since.

**Choosing between them is a per-caller judgement, and it is not always made.** The battery
subsystem writes a full store per sample and never uses the coalescing path —
[16 §](16-battery-record.md) records that as a defect of that subsystem, not of this one. The
mechanism is here; using it is opt-in.

---

## 3. The declared schema is a minority of the real one

`core/storage.py::async_load` returns eight top-level keys for a fresh install: vacuums, maps,
theme, analytics, maintenance, dock events, onboarding, and the error tracker.

At runtime **at least twelve more** appear, created lazily by whichever subsystem needs them first
— active jobs, capabilities, discovery, queue, payloads, battery, room history, room-rule status,
setup progress, pending run steps and the learning-pending pair among them. None of them is named
in the loader.

The practical effect is that **reading `async_load` tells you what a fresh install looks like, not
what the store contains.** Four of the declared keys are never created by the lazy path at all,
and most of the lazy keys are never declared, so neither list is the schema. The schema is the
union, and it is written down nowhere.

One key gets a defensive backfill on load rather than lazy creation — the error tracker section,
added for installs that predate it, set only if missing. That is the pattern the other twelve do
not follow.

---

## 4. Two guards against a reload eating the store

Both live on the teardown path, and both defend against the same class of event: a manager that is
no longer the live one still holding a reference to `self.data`.

### The stale-manager guard

Both write paths refuse once the manager is closed, and log rather than fail quietly. The reasoning
is that an unloaded manager must not clobber a store that a newer manager — from a reload — already
owns. It is belt-and-braces, and the cost of being wrong in the other direction is total.

`core/manager.py::async_shutdown` flushes any pending delayed write **directly through the storage
layer** rather than through the manager's own save, precisely because the manager's save is gated
on that flag. Without the bypass, closing would drop a debounce window that was about to land.
HA's own final-write listener does not cover this: it guards a full Home Assistant shutdown, not an
integration unload or reload.

### The never-loaded guard, and why it is `_loaded`

This is the sharper one. The integration registers its teardown callback **before** awaiting
initialisation — deliberately, so that a failure partway through setup still tears down cleanly.

That ordering means the teardown can run against a manager whose `async_load` never completed, with
`self.data` still the empty dict seeded in the constructor. An unguarded flush at that moment
writes `{}` over the user's entire store: every managed room, every map, every learned profile and
every theme. Silent, total, and triggered by an unrelated setup failure.

The flush is therefore gated on an explicit **loaded** flag, and the two cheaper guards are
rejected in place with reasons:

| candidate guard | why it fails |
|---|---|
| `data` is truthy | a genuinely empty store on a fresh install is a legitimate thing to flush |
| `hasattr` | no guard at all — the attribute always exists, it is seeded in the constructor |

The general shape is worth carrying: when a teardown is registered before the thing it tears down
exists, every teardown step needs a predicate for "did this ever start", and *emptiness is not that
predicate.*

---

## 5. Common wrong assumptions

| assumption | reality |
|---|---|
| the store's schema is in `async_load` | that is a fresh install; at least twelve more keys appear lazily — §3 |
| writes are partial | every write serialises the whole document — §2 |
| the delayed save takes the data to write | it takes a callback invoked at write time; a snapshot silently discards later writes — §2 |
| saves coalesce by default | coalescing is opt-in per caller and most callers do not — §2 |
| HA's final-write listener covers a reload | it covers a full HA shutdown only — §4 |
| an empty `data` means nothing was loaded | a fresh install is legitimately empty; the flag is the only reliable signal — §4 |
| `.storage` can be hand-edited | HA rewrites it from memory and an unreconcilable file becomes `.corrupt` — §1 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
