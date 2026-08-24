# 22 — The Adapter Contract

**Scope.** What a brand must declare to be driven by this integration, what happens on each
omission, and — the part that surprises people — **which of those rules actually run for you.**

The two shipped brands implement this contract, and each has its own document: [23 — The Eufy
Adapter](23-eufy-adapter.md) and [24 — The Roborock Adapter](24-roborock-adapter.md).

**The per-field schema is generated, not written.** Every block, every key, its type, whether it is
required and what an omission degrades to — that table is produced from
`adapters/config_schema.py` itself and lives at
`.claude/generated-docs/adapter-config/ADAPTER-CONFIG.generated.md` in the repo. It is the successor
to the hand-written config reference, and it cannot go stale against the schema because it is
derived from it. This document covers what the schema cannot say: which rules actually run, what an
omission means in practice, and where a declaration has no reader.

---

## 1. Two validators, and they do not run on the same paths

There is no single gate. There are two, written in different styles, enforcing different things.

| | `config_schema.py::validate_adapter_config` | `registry.py::_validate_adapter` |
|---|---|---|
| what it is | a recursive walk of a 33-block data literal | a hand-written rule list |
| checks | required keys, container type, enum membership, nested fields, **unknown-key rejection** | engine names resolve, tuning validators pass, `capability_hints` membership, `dispatch.template` registered, `setup.steps` ids |
| **runs on** | **the config-save service only** | **both paths** |

`validate_adapter_config` has exactly one caller: `services/adapter_config.py`. Nothing else in
the tree invokes it.

### The asymmetry a porter has to know

**A code adapter never gets the schema walk at all.** `adapters/eufy/adapter.py` calls
`register_adapter_config` directly at startup with `"source": "code"`, and
`registry.py::AdapterCoordinator.register_adapter_config` raises only when
`config["source"] == "config"`. So for a code-declared brand:

- no required-key check
- no type check
- no enum check
- **no unknown-key rejection** — a typo'd block is simply absent
- everything the registry does find is a log line

The rationale is real: a code-adapter regression would otherwise take every install's startup
down, and a warning degrades where a raise would brick. The cost is that **the two shipped brands
are held to this contract by `tests/adapters/test_adapter_contract.py` and by nothing else at
runtime.**

> ⚠ If you are writing a brand package, the schema is documentation, not enforcement. Run the
> contract test.

---

## 2. What is actually required

Five top-level keys: `adapter_id`, `source`, `entities`, `dispatch`, `room_profiles`.

**Only `dispatch` has teeth below the block level** — `template`, `service_domain` and
`service_name` are required subkeys. Everything else is required as a *block*:

- `entities` is required, but all 26 of its role keys are optional. `entities: {}` validates clean.
- `room_profiles` is a bare `dict` with no declared fields, so `room_profiles: {}` also passes the
  schema — and is then refused at registration by `_validate_room_profiles`.

The other 28 blocks are optional. A five-key config carrying two empty dicts returns no schema
issues at all.

**Ten top-level blocks are declared as bare `dict` and are never recursed into** —
`settings_selects`, `mapping`, `map_state_source`, `map_render`, `device_clean_order`,
`job_segmenter`, `room_attribution`, `room_profiles`, `anomaly`, `capability_hints`. Inside them
there is no unknown-key check and no interior typing. The registry hand-enforces a few interior
rules; the rest is unguarded.

**The schema is a floor, not the contract**, and the file says so itself.

---

## 3. What an omission resolves to

Almost every permissive default resolves to a concrete **Eufy** answer rather than to a refusal.
That is the single largest brand-neutrality liability in the tree, and it is partly instrumented:
`registry.py::_EUFY_FALLBACK_BLOCKS` makes three of them audible at registration — `mapping` →
`eufy_cv_v1`, `job_segmenter` → `eufy_counter_v1`, `room_attribution` → `eufy_anchor_winding_v1`.
Those warnings are silent today because both shipped brands declare all three.

Not instrumented: an absent or unknown `dispatch.template` resolves to `_FALLBACK_TEMPLATE =
"eufy_room_clean"`, and the wire field names fall back to Eufy strings (`map_id`, `rooms`, `id`,
`clean_times`).

**Those are not defaults anyone selected.** This integration is a port of a working Eufy system —
the brand abstraction was built around code that already ran — and `map_id` / `rooms` / `id` /
`clean_times` are the original payload's own keys, unchanged since before an adapter layer
existed. An adapter that declares nothing does not get a neutral answer; it gets the
pre-abstraction one. That is worth knowing when judging how much of the seam is finished: the
remaining Eufy-isms are concentrated wherever no second brand has yet forced the question.

### Nothing and empty are different, in three places

| declaration | means | and if you conflate them |
|---|---|---|
| `room_profiles` absent or `{}` | not written yet — **refused** | a partial block is fine; declaring *some* keys means you engaged with the contract |
| an error code in neither `evidence_safe_` nor `evidence_invalidating_` list | visibly unclassified | a vendor's new code silently changes the arithmetic |
| a `*_options` vocabulary absent | **cannot judge** — never "the axis does not exist" | strips `water_level` and `clean_mode` from every room on an S6 |

Only absence from the brand's own **profiles** means an axis is gone — see
[20 — Room Profiles](20-room-profiles.md).

---

## 4. Where core still knows a brand's words

Structurally the boundary holds. Core reads role **keys** (`entities.active_cleaning_target`),
passes i18n keys rather than learning error codes, and entity rescue walks whatever roles the
adapter declared rather than a hardcoded list.

Three leaks:

**`dispatch.template` is a closed enum, and three of its four values are brand names.** A fourth
brand cannot declare a new dispatch template through the config path at all — it has to ship code
that registers an engine.

**Every absent-default is Eufy's answer**, per §3.

**`discovery.implicit_map_id` defaults to `"main"`.**

✅ **CORRECTED 2026-08-23.** `const.py` and `adapters/eufy/vocabulary.py` both stated that a brand declaring
`active_vacuum_states` "would be REJECTED at validation". True on the config path; silently
ACCEPTED on the code path, per §1 — and both shipped brands are code-declared, so the
guarantee never applied to either of them. Both comments now name the path the rejection
holds on, and name `tests/adapters/test_adapter_contract.py` as what actually binds a code
adapter.

---

## 5. Declarations nothing reads

The schema is a porter-facing surface, and three of its entries promise behaviour that does not
exist.

`vocabulary.blocked_work_mode_states` and `vocabulary.blocked_task_status_states` have **no
readers anywhere.** Their only occurrences outside the schema are in the Eufy adapter, declaring
real values for them. `entities.work_mode` **is** read, but not for what the schema says — it goes
to `core/capabilities.py` for capability detection, and no start-blocker consults it.

A porter who declares all three gets nothing, and has no way to discover that from the schema.

> ⚠ **These are not aspirational declarations. The check was live, was orphaned, and was then
> correctly garbage-collected — in that order.** It has four datable stages:
>
> 1. **The generator.** `generate_vacuum_system_full_power_mode_inline_lock_v3_corrected.yaml:1295`
>    emitted an eight-arm Jinja ladder whose arm 4 was
>    `{% elif work_mode in ['Smart Follow', 'Auto', 'Room'] %} blocked_work_mode`, with the message
>    `Vacuum is still in an active work mode.` at :1325. Arm 5 was the task-status equivalent.
> 2. **The first integration (2026-04-02).** The ladder was ported to Python verbatim as
>    a `build_start_block_reason` function in that snapshot's `queue/queue_engine.py`, keeping all
>    three strings and the message text unchanged, and its `get_start_status` called it. The gate
>    was enforced. Neither symbol survives in the tree today, so neither is cited as live.
> 3. **Orphaned before the repo existed.** By the initial commit `eae291fa` the function is still
>    present and still correct, but `core/manager.py` no longer calls it, and no commit ever
>    removed that call — the caller was dropped inside the pre-git window, so git cannot see it
>    happen. This is why the check reads as though it was never wired.
> 4. **Removed.** `2bfda655` deleted it, describing it in its own commit body as
>    `build_start_block_reason() dead orphan removed`. By then that was accurate.
>
> The three strings then reappeared as `blocked_work_mode_states` in the Eufy adapter — the same
> values, now as vocabulary with no consumer. The data outlived the gate twice over.
>
> It also changes what to distrust. Nothing here is visible from git alone: at every commit that
> exists, the function is either dead or gone. Only the pre-git snapshot shows it running.

### What the remedy turned out to be, which is not what the history suggested

The archaeology above says *a gate this product used to have*, and the obvious conclusion is to
restore it. Measured against the code, that conclusion is right for one key and wrong for the other,
and the wrong half is the one that looks most restorable.

**`blocked_task_status_states` is SUPERSEDED, not lost.** The gate it named still runs — it is
spelled with different vocabulary. `jobs/job_monitor.py::evaluate_job_lifecycle` refuses a start on
`active_run_task_states` and on `hard_service_states`, and those two already cover **every** value
the Eufy adapter declares here:

| declared `blocked_task_status_state` | already refused by |
|---|---|
| `Cleaning` | `active_run_task_states` |
| `Returning` | `active_run_task_states` |
| `Washing Mop` | `hard_service_states` |

So restoring a reader would add a **second, shorter copy of a live rule**, with its own message and
its own drift risk — the failure mode this codebase already names as how the shorter copy becomes
the bug. The right move is the opposite of restoring: say plainly that the key is dead and point a
porter at the two sets that are live.

**`blocked_work_mode_states` has no equivalent, and no ground to stand on either.** No start-blocker
consults `work_mode` at all. On the reference install the sensor reads `unknown` — and
`job_monitor.py::_norm` maps `unknown` to the empty string, so even a restored gate could not match
one of these values on the hardware that declares them. Building a refusal on that signal would need
the signal to work first; that is a separate piece of work, not a port completion.

The schema and the adapter now both state that these keys are not consumed, and why. A porter who
declares them still gets nothing, but can now discover that from the surface they are reading —
which was the actual harm.

---

## 6. Entity rescue lives here and does not belong here

`adapters/entity_resolve.py` rescues declared entity ids whose naming pattern does not match
reality — a translation-key lookup, a suffix sweep, a sibling walk.

**It is a cross-cutting service filed under `adapters/`,** and the evidence is structural rather
than aesthetic: it imports nothing from its own package, contains no brand vocabulary in
executable code, and four of its six consumers are outside `adapters/`. `core/capabilities.py`
alone imports six of its symbols and rebuilds the loop around them; `dock/` and `maintenance/`
take `resolve_action_entity`. Only `resolve_declared_entities` is genuinely adapter-facing — it is
the one function that takes brand vocabulary.

> ⚠ **The misplacement has already been paid for.** `core/manager.py` reaches the same function by
> two routes in one file: the public `from ..adapters.entity_resolve import sweep_siblings`, and a
> private `from .capabilities import _sweep_siblings` — which is a two-line wrapper that calls the
> public one. `core/capabilities.py` carries a comment beginning *"ONE COPY — …This was the
> third"*, recording that copies of this logic have been collapsed before.

---

## 7. Common wrong assumptions

| assumption | actually |
|---|---|
| declaring a config wrong fails loudly | only for a user-saved config; a code adapter warns and registers |
| the schema validates every adapter | it runs on one code path, from the config-save service |
| `entities` being required means some entity is required | the block is required; all 26 roles are optional and `{}` passes |
| an unknown key in `mapping` or `capability_hints` is caught | those blocks are bare `dict` and are never recursed into |
| an undeclared block is a refusal | it is usually a fallback, and the fallback is usually Eufy's answer |
| a missing `*_options` list means the brand has no such axis | it means the framework cannot judge; axis existence comes from the profiles |
| declaring `blocked_work_mode_states` blocks a start | nothing reads it |
| `entity_resolve` is adapter code | one of its seven exported symbols is adapter-facing |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
