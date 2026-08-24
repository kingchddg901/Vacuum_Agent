# 39 — The Integration Entry Point

**Scope.** `__init__.py`: the four functions Home Assistant calls, the cold-start race that makes
setup run twice, and the ruling about what removing the integration does *not* delete. The store
this sets up is [32](32-the-store.md); the subsystems it constructs are
[33](33-the-orchestrator.md).

Two things here are worth reading even if you never touch this file: the invariant about depending
on another integration's entities, and the deletion ruling. Both are decisions about the product,
not about setup plumbing.

---

## 1. Four contract functions, and the work between them

Home Assistant calls `__init__.py::async_setup`, `__init__.py::async_setup_entry`,
`__init__.py::async_unload_entry` and `__init__.py::async_remove_entry`. Everything else in the
file is per-entry orchestration: constructing the manager, wiring adapter coordinators, forwarding
the six platforms in `__init__.py::PLATFORMS`, registering panels, registering four separate
service registries, and registering nine listener domains.

Listener registration is delegated rather than inlined — each domain module under `listeners/`
exposes `register` and `remove` and owns its own constants, so this file calls a pair per domain
instead of holding their internals.

---

## 2. Another integration's entities may not exist yet

This is the invariant the file exists to make into a system property:

> An operation that reads entities owned by **another** integration must not assume they exist
> during cold-start setup.

Everything an adapter derives comes from the vacuum's own integration — the attribute that decides
whether rooms are readable, and the entity registry the companion sweep searches. On a cold boot
that provider has often not finished publishing. The failure mode is not a crash:

**It reads an empty registry and a stateless vacuum, caches that answer, and never looks again —
and a restart repeats the same race rather than repairing it.**

Measured on a real install: sixty-five companion entities present, every one of the seven
maintenance sources recorded as null, and room support reported false beside a self-check that
could read five rooms. Replaying the sibling list through the resolver by hand resolved six of six.

> The matching was never wrong. The list was empty when it ran.

The remedy is to run again once Home Assistant has finished starting, and **both halves are needed
because they fix different things**: re-registering the adapter re-derives the *hints* from live
state, while refreshing capabilities re-runs the live registry sweep. The capability refresh alone
cannot fix room support, because it deliberately replays the adapter's stored hints. Writes happen
only on a real change, so a healthy install pays one detection pass and nothing else.

---

## 3. A local comment is not a system property

The most useful sentence in this file is about documentation rather than code.

The constraint in §2 was **already written down, correctly**, a few dozen lines below — in a comment
explaining why the vocabulary migration defers. That comment states that adapters are registered
from vacuum entities owned by other integrations, and that on a cold boot those often have not set
up yet.

It was true of adapter registration itself, and was never applied to it.

That is why the constraint now carries a notation anchor that any site taking the same dependency
cites, instead of living as prose next to one of its consumers. A comment explains the line it sits
on; only a named, citable invariant can be *shared* by the sites that need it.

The general lesson for anyone writing one of these documents: **when a comment states a general
truth, the fact that it is a comment is the defect.** Someone else's code needs it, and prose in
another file cannot reach them.

---

## 4. Unload undoes more than the platforms

Unloading forwards to the platforms, then — only if that succeeded — tears down everything setup
established: nine listener domains, the panels, and four service registries.

Two details are less obvious:

- **The room-source cache is invalidated.** A reloaded entry must not serve the previous life's
  cache as fresh: its freshness stamps survive the reload even though the world it described may
  not. It is the read-side analogue of the timer teardown in
  [32 §4](32-the-store.md).
- **Panels are removed through the frontend component**, because the panel helper exposes no
  unregister call of its own. The urls registered for the entry are tracked so they can be removed
  by name.

The manager's own teardown — flushing a pending write and cancelling every timer and task — is
`core/manager.py::async_shutdown`, and it is registered *before* setup is awaited so a mid-setup
failure still tears down. That ordering is what makes its never-loaded guard necessary.

---

## 5. Removing the integration clears one persistence layer of two

⚠ **This is a ruling, and the file says so.**

There are two places this integration keeps data, and removing the config entry clears exactly one:

| layer | on removal |
|---|---|
| the HA store — rooms, profiles, adapter config, the battery record | **deleted** |
| `<config>/eufy_vacuum/` — the learning tree, stall captures, the pose ring, the job archive, raw samples | **kept** |

The reasoning is that the tree is the user's own recorded history of their own home, it is the only
copy, and nothing in Home Assistant would put it back. **Removing an integration is not obviously a
request to destroy that**, so the recoverable outcome wins: a reinstall that inherits data can be
cleaned up by hand, while a purge cannot be undone.

It follows that the tree is **not managed for deletion at all** — no service, no hook, no age
policy removes it. Deleting it is a manual step, and that is the documented answer rather than a
gap waiting for a fix.

Inheritance after a reinstall is tolerable rather than merely convenient, and for a checkable
reason: learned rows are keyed by map and room slug together
([28 §1](28-learning-statistics.md)), so old data can only re-attach where **both** match a map the
vacuum later builds — and a recreated map gets a different map id in practice.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| setup runs once | it runs again after Home Assistant has started, because a cold boot reads an empty registry — §2 |
| the cold-start retry is belt-and-braces | re-registering and refreshing fix different things; neither substitutes for the other — §2 |
| the constraint was undocumented | it was documented, in a comment, beside a different consumer — §3 |
| unload only unloads platforms | it also invalidates the room-source cache, removes panels, and tears down nine listener domains and four service registries — §4 |
| removing the integration deletes its data | it clears the HA store; the on-disk tree is kept deliberately — §5 |
| the on-disk tree will be cleaned up eventually | nothing removes it; deleting it is a documented manual step — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
