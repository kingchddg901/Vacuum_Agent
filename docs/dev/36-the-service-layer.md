# 36 — The Service Layer

**Scope.** The integration's public API: how sixteen domain modules register eighty services, the
two shared behaviours every handler inherits, and where the line between a service's name and its
prose is drawn. The card's own three-layer parameter path is
[frontend/backend-contract-and-data-shapes](frontend/backend-contract-and-data-shapes.md).

This is the surface an automation, a script and the card all share. Everything below exists because
those three callers have different tolerances for being told *no*.

---

## 1. Sixteen domains, two names each

Every domain module exposes exactly two things: a `register(hass)` function and a `SERVICES` tuple
of the names it registered. `services/__init__.py::async_register_services` calls the first on
every module; `services/__init__.py::async_unregister_services` walks the second and removes each
name.

Teardown is therefore **derived from the same declaration that set registration up**, rather than
maintained as a second list. A service added to a module and forgotten in its tuple would leak past
an unload — which is the failure a hand-maintained teardown list invites and this shape cannot have,
provided the tuple is the thing `register` iterates.

Registration order carries exactly one meaning: Developer Tools lists services in the order they
were registered, so the domains users invoke directly are registered first and the panel, setup and
adapter services last. Nothing else depends on it.

---

## 2. `map_id` is optional everywhere, and resolved from the adapter

Every service that takes a map accepts the field as optional.
`services/_common.py::resolved_call_data` fills it in when the caller omits it or passes a blank,
by reading the vacuum's current active map through the adapter's declared active-map entity —
`rooms/room_discovery.py::get_active_map_id`.

The framework stays adapter-agnostic here: **a brand that declares an active-map entity gets the
auto-resolve for free, and one that does not requires callers to pass the map explicitly.** There
is no brand check anywhere in the path.

Three pass-through cases are enumerated in place, and the third is the interesting one:

| case | behaviour |
|---|---|
| map already supplied | returned unchanged |
| no vacuum id | returned unchanged — the schema will reject the call anyway |
| the active-map entity is missing or sentinel-valued | **returned unchanged**, so the manager raises its own clear error about the missing argument |

That last row is the decision. Substituting a plausible-looking map when the real one cannot be
read would turn "I don't know which map" into a confident operation against the wrong one, and a
wrong map is the difference between cleaning the kitchen and cleaning a room upstairs.

---

## 3. A write refuses; a read answers honestly

Both halves address the same input — a service call naming a vacuum this integration does not
manage — and they answer differently on purpose.

**Writes refuse.** `services/_common.py::require_managed_vacuum` raises a validation error, which
Home Assistant surfaces as a toast rather than a traceback, because it is a caller mistake and not
an internal failure. The rule it enforces is stated as a three-way choice where the third option is
the bug:

> a mutation either refuses with a reason or succeeds carrying what it applied. Silently minting a
> bucket and reporting success is the third thing, and it is the bug.

**Reads answer.** `services/_common.py::unmanaged_vacuum_read_result` returns the handler's normal
empty shape with a `reason` attached. The justification is about who calls a read: *a read is how a
card discovers state, and turning discovery into an error trades a blank panel for a red toast.*

The `reason` field is what makes the empty answer honest — it lets a consumer distinguish **nothing
here** from **not ours**, a distinction that the old phantom-bucket behaviour destroyed permanently,
because minting a bucket made the two byte-identical from then on.

**The split is inspectable rather than judged.** Whether a handler mutates is a property of the
handler, so which of the two rules applies is decidable by reading it — not a per-service opinion
that drifts.

⚠ Note how this guard was turned on. It newly rejects input that previously succeeded, so before
activating it the existing per-vacuum stores on the reference install were enumerated and confirmed
to key only on managed vacuums — there was no pre-existing phantom for it to start refusing. A
guard that activates over existing data has to be checked against that data first, not only against
its own tests.

---

## 4. Almost everything returns a response — and the three that do not

Of eighty registrations, **seventy-seven declare `supports_response`**. A caller gets back what
happened rather than having to re-read state to find out.

Three do not: discovering rooms, saving managed rooms, and clearing the active job. Two of those
three **mutate**, and the invariant block in the rooms module names the sharper half of the problem
— within that area, saving managed rooms is simultaneously the most destructive service and the
only mutation that returns nothing.

That matters because §3's contract only half applies without a response. A write can refuse loudly,
but "succeeds carrying what it applied" needs a channel to carry it in. A destructive service that
returns nothing leaves a caller unable to distinguish *applied to twelve rooms* from *applied to
zero* without going back to the store to look.

> This is also the one place the original design still shows. The first integration returned nothing
> from any service and wrote every result into storage for the card to read back. The service layer
> has since inverted that almost completely — these three are what is left of it.

---

## 5. Names are not translated; failures are

`services.yaml` is 3,809 lines, almost exactly the size of the Python package it describes, and
**none of it is localized.** The translation files carry blocks for config, options, entities, the
title and exceptions — and no services block at all.

The reasoning is that a service name is an **identifier**. It is what an automation writes, what a
script calls, and what a user pastes into an issue; translating it would make the same action carry
different names on different installs and break every shared automation across a language change.

Failures are the opposite case. `services/_common.py::require_managed_vacuum` raises with a
translation key and placeholders rather than an English string, because an error message is prose a
person reads, not an identifier anything calls.

So the line runs between the two halves of the same service: **its name is machine vocabulary and
stays fixed; its error text is human prose and is translated.** That is the same
whose-word-is-this test applied in [35 §5](35-the-fault-tracker.md) and
[33 §4](33-the-orchestrator.md), on a different axis.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| `map_id` is required | it is optional everywhere and auto-resolved from the adapter's active-map entity — §2 |
| an unreadable active map falls back to a default | it is left absent so the manager raises; a substituted map is a confident wrong operation — §2 |
| an unmanaged vacuum always errors | writes refuse, reads return an empty shape with a reason — §3 |
| an empty read result means no data | it may mean not-ours; the `reason` field is the difference — §3 |
| every service returns a response | three do not, and two of those mutate — §4 |
| `services.yaml` should be localized | service names are identifiers; only the exception text is translated — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
