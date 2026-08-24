# 44 — Onboarding and First Run

**Scope.** Getting from *installed* to *usable*: the config flow that asks for almost nothing, the
per-map onboarding state that is computed rather than stepped, and the sidebar panel registered per
vacuum. The ongoing step machine and its drift signal are [31 — The Setup Layer](31-setup-layer.md);
these own a different part of the store.

One decision runs through all three: **nothing here blocks.** Every step can be deferred, and
completeness is something the system *reports* rather than something it *enforces*.

---

## 1. The config flow accepts a blank vacuum

`config_flow.py::EufyVacuumConfigFlow` collects the vacuum entity, an optional tested-model string
and free-text notes — and **the vacuum picker is optional.** Leaving it blank still creates the
config entry; the user fills it in later through
`config_flow.py::EufyVacuumOptionsFlow`.

That matters more than it looks. The vacuum this integration manages is owned by a *different*
integration, and on a cold install that integration may not have finished setting up — the same
race [39 §2](39-the-entry-point.md) documents at the adapter layer. A required picker would mean
the install fails for a reason the user cannot act on and would not understand, at the one moment
they have the least context.

Accepting an empty entry converts a hard failure into a deferred step.

---

## 2. Onboarding state is computed, and reading it creates nothing

`onboarding/manager.py::OnboardingManager` owns the onboarding subtree and is one of the three
subsystems constructed without a manager reference ([33 §1](33-the-orchestrator.md)) — it takes the
data dict and `hass`, and nothing else.

`onboarding/manager.py::get_onboarding_state` derives completeness from **stored flags plus live
map data**, and its docstring carries the important half: *creates nothing.* A status read does not
mint the record it is reporting on.

That is the same discipline as [36 §3](36-the-service-layer.md) and
[38 §5](38-the-theme-library.md), applied one layer down. A read that creates state on the way past
makes "has this been onboarded?" unanswerable, because asking makes it true.

Two consequences of computing rather than storing completeness:

- **Only *enabled* rooms need a floor type.** Disabling a room removes it from the requirement
  without touching the onboarding record, because the requirement is derived from the live room set
  each time it is asked.
- **New rooms are detected from the vacuum's own attributes**
  (`onboarding/manager.py::check_for_new_rooms`), not from a stored expectation, so a map that
  gains a room reopens onboarding without a migration.

`onboarding/manager.py::confirm_floor_type` records a floor type as **explicitly confirmed by the
user**, which is distinct from a floor type that merely has a value. That distinction is what lets
[23 §3](23-eufy-adapter.md) treat floor type as collected for the map render and the onboarding
gate — and *not* as licence to pick a water level nobody asked for.

`onboarding/manager.py::get_rooms_onboarding_summary` aggregates across maps, and
`onboarding/manager.py::reset_onboarding` clears one map — per map, because a second floor is a
separate onboarding.

---

## 3. One panel per vacuum, with a name the user owns

`panels.py::async_register_vacuum_panel` registers one sidebar panel per managed vacuum, at a url
derived from the vacuum's object id, all pointing at the same web component.

The title is **per-vacuum and user-settable**, stored on the managed-vacuum record and defaulting to
the product name when unset. The reason is concrete: before that, two vacuums produced **two
identical sidebar entries**, and the sidebar is the one place a user cannot disambiguate by hovering
over an entity id.

A default that is right for one instance and useless for two is a common shape, and the fix is not
a cleverer default — it is making the field editable and defaulting it.

`panels.py` is also deliberately the **single source of truth** for that registration, because
three separate paths reach it: startup, adding a vacuum at runtime, and a rename. Panels registered
for an entry are tracked in a ledger so unload can remove them by name
([39 §4](39-the-entry-point.md)) — the panel helper offers no unregister call of its own, so
whatever was registered has to be remembered.

---

## 4. Common wrong assumptions

| assumption | reality |
|---|---|
| setup requires choosing a vacuum | the picker is optional and the entry is created regardless — §1 |
| onboarding is a wizard with steps | completeness is computed from live data every time it is asked — §2 |
| reading onboarding state initialises it | it explicitly creates nothing — §2 |
| every room needs a floor type | only enabled ones, and the requirement is re-derived, not stored — §2 |
| a floor type with a value is confirmed | user confirmation is a separate fact, and only it gates onboarding — §2 |
| the sidebar entry is named after the integration | the title is per-vacuum and user-settable, because two vacuums produced two identical entries — §3 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
