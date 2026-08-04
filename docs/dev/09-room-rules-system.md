# 09 — Room Rules System

Room rules let you automate what happens to each room at job start. A rule watches a Home Assistant entity and, when its condition is true, either blocks the room entirely (a **Blocker**) or overrides its cleaning settings (a **Modifier**).

Source files:
- Rule operators and operand normalisation: `custom_components/eufy_vacuum/rooms/access_graph.py` (`AccessGraphManager`)
- Effective start plan / preflight: `custom_components/eufy_vacuum/planning/run_plan.py` (`RunPlanManager`)
- Mid-job path-block re-evaluation: `custom_components/eufy_vacuum/planning/run_plan.py`
- Frontend state: `src/state/room-rules.js`
- Frontend renderer: `src/renderers/room-rules.js`
- Frontend bindings: `src/bindings/room-rules.js`

---

## 1. Rule types

### Blocker

A Blocker removes the room from the cleaning queue for the current job when its condition is true.

- **Can**: exclude the room from the payload entirely.
- **Cannot**: change any cleaning settings.
- **Effect shape** (wire payload): `{ "action": "exclude", "reason": "<optional human label>" }`. After backend normalization the stored blocker effect always carries an empty `changes: {}` — i.e. `{action: "exclude", reason, changes: {}}`.

A Blocker can cause cascade blocks. If Room B requires Room A (Room A `grants_access_to` B), and Room A is blocked, Room B also becomes inaccessible and is excluded — even if Room B has no blocker rule of its own.

### Modifier

A Modifier overrides one or more of the room's cleaning settings for the current job when its condition is true. The room is still cleaned; only its settings change.

- **Can**: override `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, `edge_mopping`.
- **Cannot**: exclude the room from the queue.
- **Effect shape**: `{ "action": "mutate", "reason": "<optional>", "changes": { "fan_speed": "Quiet" } }`

Multiple modifier rules can match simultaneously. Changes from all matching modifiers are merged using last-write-wins per field (explained in section 5).

---

## 2. Condition system — all operators

Each rule has a single `entity_id`, one `operator`, and (for most operators) one `value`. The backend evaluates `_room_rule_matches(rule)` against live HA state.

### Operand normalisation

Before any comparison the state value is run through `_normalize_rule_operand`:

1. If the input is already a Python `bool`, return it unchanged.
2. If it is `int` or `float`, return `float(value)`.
3. Otherwise stringify it, strip whitespace, lowercase it.
   - `"true"` or `"on"` → `True`
   - `"false"` or `"off"` → `False`
   - If the result parses as a float, return that float.
   - Otherwise return the lowercase string.

The same normalisation is applied to both the entity state value and the rule's `value` operand before equality or membership tests.

### Operator reference

#### `is_on`
Returns `True` when `str(state_value).strip().lower() == "on"`.
No `value` operand needed. Only valid for boolean-category entities.

#### `is_off`
Returns `True` when `str(state_value).strip().lower() == "off"`.
No `value` operand needed.

#### `exists`
Returns `True` when the entity exists in HA (i.e. `hass.states.get(entity_id) is not None`).
No `value` operand. Evaluated before the state is read.

#### `missing`
Returns `True` when the entity does not exist in HA.
No `value` operand. Evaluated before the state is read.

If the entity is missing and the operator is anything other than `exists` or `missing`, the rule returns `False` without further evaluation.

#### `equals`
```python
normalized_state == _normalize_rule_operand(target_value)
```
Both sides are normalised. Works for strings, numbers, and booleans. A state of `"25.0"` matches a `value` of `25` because both normalise to `25.0`.

#### `not_equals`
```python
normalized_state != _normalize_rule_operand(target_value)
```
Logical inverse of `equals`.

#### `gt`, `gte`, `lt`, `lte`
Numeric comparisons. The backend attempts:
```python
state_number = float(state_value)
target_number = float(target_value)
```
If either conversion raises `TypeError` or `ValueError`, the rule returns `False`. No normalisation is applied — raw string `state_value` is passed directly to `float()`.

| Operator | Comparison |
|---|---|
| `gt` | `state_number > target_number` |
| `gte` | `state_number >= target_number` |
| `lt` | `state_number < target_number` |
| `lte` | `state_number <= target_number` |

#### `in`
```python
options = target_value if isinstance(target_value, list) else [target_value]
normalized_options = {_normalize_rule_operand(option) for option in options}
return normalized_state in normalized_options
```
`target_value` can be a JSON array or a single value. Each option is normalised before building the set. Matching is therefore case-insensitive and type-coercing (same rules as `equals`).

#### `not_in`
Logical inverse of `in`. Returns `True` when the normalised state is **not** in the normalised options set.

### Edge cases

- **Missing entity, non-existence operator**: returns `False`.
- **Non-numeric state with `gt`/`gte`/`lt`/`lte`**: returns `False`.
- **Unknown operator string**: falls through all branches and returns `False`.
- **`value` is `None` for `equals`/`not_equals`**: `_normalize_rule_operand(None)` returns `""` (lowercased empty string), so the comparison is against `""`.

---

## 3. Entity categories

The frontend classifies each entity into a category to restrict which operators the UI presents. The backend does not enforce categories — it evaluates any operator against any entity.

### Category assignment (`ruleEntityDescriptor` in `state/room-rules.js`)

| Domain / signal | Category |
|---|---|
| `binary_sensor`, `switch`, `input_boolean` | `boolean` |
| `select`, `input_select`, or entity has `options` attribute | `enum` |
| `number`, `input_number` | `numeric` |
| `sensor` with numeric state value | `numeric` |
| `sensor` with non-numeric state value | `text` |
| State is `"on"` or `"off"` (any domain) | `boolean` |
| Entity exists but no other match | `text` |
| No entity found | `unknown` |

### Operator lists per category

| Category | Available operators |
|---|---|
| `boolean` | `is_on`, `is_off`, `exists`, `missing` |
| `enum` | `equals`, `not_equals`, `in`, `not_in`, `exists`, `missing` |
| `numeric` | `equals`, `not_equals`, `gt`, `gte`, `lt`, `lte`, `exists`, `missing` |
| `text` | `equals`, `not_equals`, `in`, `not_in`, `exists`, `missing` |
| `unknown` | all operators |

### Value mode per operator

Within a category, the operator also controls which input widget the editor renders:

| Category + operator | Value mode | Widget |
|---|---|---|
| Any no-value operator (`is_on`, `is_off`, `exists`, `missing`) | `none` | (hidden) |
| `boolean` | `none` | (hidden) |
| `enum` + `equals`/`not_equals` | `single-select` | `<select>` from entity options |
| `enum` + `in`/`not_in` | `multi-select` | chip array from entity options |
| `numeric` | `number` | `<input type="number">` with min/max/step from entity attributes |
| `text` | `text` | `<input type="text">`, comma-separated hint for `in`/`not_in` |

**Enforcement**: category assignment and operator filtering happen entirely in the frontend. The backend accepts and evaluates any operator regardless of category.

---

## 4. Modifier settings

Six room settings can be overridden by a modifier rule. All live in `effect.changes`.

| Field | Type | Valid values |
|---|---|---|
| `clean_mode` | str | `"vacuum"`, `"mop"`, `"vacuum_mop"` |
| `fan_speed` | str | `"Quiet"`, `"Standard"`, `"Boost"`, `"Max"` |
| `water_level` | str | `"Off"`, `"Low"`, `"Medium"`, `"High"` |
| `clean_intensity` | str | `"Quick"`, `"Narrow"`, `"Deep"` |
| `clean_passes` | int | **1 or 2 only** |
| `edge_mopping` | bool | `true` or `false` |

Any field omitted from `changes` is not overridden — the room's saved profile value is used.

### The `clean_passes` 1-or-2 constraint

`clean_passes` is constrained at two points:

1. **Frontend (`_buildRulePayload`)** — only writes `clean_passes` to the payload when `Number(value) === 1 || Number(value) === 2`. Any other value is silently dropped.
2. **Frontend validation (`roomRulesDraftIsValid`)** — a modifier draft is invalid unless at least one meaningful change is present, and for `clean_passes` specifically, the value must be `1` or `2`.

The backend does not enforce this constraint itself — it copies whatever `clean_passes`
it receives, unclamped (a value injected server-side via the service reaches
`protected_room_config` as-is). **The "1 or 2" cap is an Eufy-oriented *frontend* limit**:
Eufy caps 2 passes but Roborock allows 1–3, so a valid Roborock 3-pass modifier is not
expressible through the rule editor today. (Separately, the *dispatch wire* clamps
`clean_times` to `[1, passes_max]` — see [07](07-queue-engine.md) §2 — so an out-of-range
value still can't reach an Eufy device.)

---

## 5. Evaluation pipeline

### When rules are evaluated

Rules are evaluated **once: at job start time**, inside
`RunPlanManager._build_effective_start_plan` (`planning/run_plan.py`). This
method is called by `get_start_status` (which drives the card's preflight
display) and again at the top of `start_selected_rooms` to produce the final
effective plan before the API call.

The only other evaluation site is `get_runtime_path_block_report` (also in
`RunPlanManager`), which re-evaluates **blocker rules only** mid-job as entity
states change (see section 7).

Rules are never evaluated when a room is toggled, when the user edits settings, or when `build_queue` / `build_room_payload` are called in isolation.

### `_room_rule_matches` (on `AccessGraphManager`): evaluation order

```
1. Fetch entity state from hass.states.get(entity_id)
2. If operator is "exists" → return entity is not None
3. If operator is "missing" → return entity is None
4. If entity is None → return False
5. Normalise state_value via _normalize_rule_operand
6. If operator is "is_on" → return str(state_value).strip().lower() == "on"
7. If operator is "is_off" → return str(state_value).strip().lower() == "off"
8. If operator is "equals"/"not_equals" → normalise both sides, compare
9. If operator is "in"/"not_in" → normalise each option, check membership
10. If operator is "gt"/"gte"/"lt"/"lte" → convert both to float, compare
11. Fall-through → return False
```

### `_build_effective_start_plan`: full algorithm

**Step 1 — Load rooms**

```python
managed_rooms = _normalized_managed_rooms_with_automation(...)
selected_rooms = [rooms where enabled == True], sorted by (order, name)
selected_room_ids = [int(room.room_id) for room in selected_rooms]
```

**Step 2 — Access graph guard**

`_access_graph_state` is checked. If it returns `"partial"`, the plan is blocked immediately with `reason: "incomplete_access_graph"` and rule evaluation is skipped. If it returns `"blank"` and any rooms have rules, it is blocked with `reason: "access_graph_required_for_rules"`.

Additionally, if any blocker rules exist but no room has a non-empty `grants_access_to`, the plan is blocked with `reason: "access_graph_required"`.

All three of these refusals also carry `reason_params` and `blocking_rooms`:

```python
"reason": "incomplete_access_graph",
"reason_params": {"rooms": ["Study"], "room_ids": ["3"]},
"blocking_rooms": [{"room_id": "3", "name": "Study"}],
"message": "Room access is incomplete for Study. Complete their access links, ...",
```

`reason_params.rooms` is a **list, never pre-joined** — the card joins it with the
locale's own separator (`common.list_separator`), because joining server-side would
bake an English list convention into all 18 shipped locales. `message` remains the
English response-service surface for non-card consumers and is the card's fallback
when it does not recognise the code.

The rooms are derived by `AccessGraphManager.access_graph_block_rooms`, the companion
to `access_graph_block_code`: the code answers *are runs blocked*, this answers
*because of which rooms*. A refusal that no single room causes (`missing_dock_room`)
yields an empty list and the generic sentence rather than a placeholder room.

**Step 3 — Evaluate all rules**

Iterates over **all** rooms (not just selected rooms):

```python
for room in all_rooms:
    for rule in room.get("rules", []):
        if not rule.get("enabled", True): continue
        if not rule.get("entity_id"): continue
        if not _room_rule_matches(rule): continue

        if rule.kind == "blocker":
            direct_blocked.setdefault(room_id, _build_blocked_room_entry(...))
            continue

        # Modifier — only applies to selected rooms
        if room_id not in selected_room_id_set: continue
        if rule.kind != "modifier": continue

        change_set = rule.effect.get("changes", {})
        modifier_matches.setdefault(room_id, _build_modified_room_entry(...))
        modifier_matches[room_id]["changes"].update(change_set)
        modifier_matches[room_id]["triggered_rule_ids"].append(rule.id)
```

Blocker rules are evaluated for **every room** on the map, not just selected ones, because a non-selected blocked room can still be a prerequisite for a selected room. Modifier rules are only applied to selected rooms.

**Step 4 — Compute accessible room IDs**

Starting set: all rooms with an empty `requires_map` entry (no prerequisites), minus any directly blocked rooms.

```python
accessible_room_ids = {room_id for room_id in all_rooms if not requires_map.get(room_id)}
accessible_room_ids -= set(direct_blocked)

changed = True
while changed:
    changed = False
    for room_id in all_rooms_by_id:
        if room_id in accessible_room_ids or room_id in direct_blocked:
            continue
        parent_ids = requires_map.get(room_id, [])
        if parent_ids and any(parent_id in accessible_room_ids for parent_id in parent_ids):
            accessible_room_ids.add(room_id)
            changed = True
```

This is an iterative graph propagation — not a traditional BFS/DFS. It continues until no new rooms can be added. A room becomes accessible if at least one of its parents is accessible. A blocked parent poisons all children (they can never enter `accessible_room_ids` through that parent).

**Step 5 — Build `blocked_rooms` list**

For each room in `selected_room_ids`:
- If the room is in `direct_blocked`: add it to `blocked_rooms` with `source: "direct_rule"`.
- If the room is not in `accessible_room_ids`: add it to `blocked_rooms` with `source: "access_dependency"` and `blocked_by_room_id` pointing to the inaccessible parent.
- Otherwise: the room is included.

**Step 6 — Apply modifier changes**

For each **selected** room: a **blocked** room is written into `effective_rooms` as
`{**room_data, "enabled": False}` and skipped. An **included** (non-blocked) room:

```python
updates = {"enabled": True, "order": next_order}
next_order += 1
if room_id in modifier_matches:
    updates.update(modifier_matches[room_id]["changes"])
updated_room = manager.protected_room_config({**room_data, **updates})
updated_room["profile_name"] = _match_profile_from_fields(updated_room) or "custom"
```

Two edges the merge introduces:

- **`protected_room_config` can silently drop modifier fields.** It clears
  `water_level` and `edge_mopping` whenever the effective `clean_mode` is **not** a mop
  mode, and force-downgrades a carpet room's `mop`/`vacuum_mop` → `vacuum` (then clears
  those two). So a modifier that sets `water_level`/`edge_mopping` but leaves the room in
  `vacuum` mode has those two changes **nullified**. (It is the public
  `manager.protected_room_config`, delegating to `profiles/_protected_room_config`.)
- **`profile_name` is recomputed** via `_match_profile_from_fields`; a modifier that
  pushes settings off any preset stamps the effective room `profile_name: "custom"`.

**Step 7 — Build queue and payload**

`build_queue_from_managed_rooms` produces `queue_state`; the `payload_state` comes from
the dispatch-engine **phase list** — `_build_steps_phases` (stepped runs with
charge/wait/zone) or `_build_dispatch_phases` — as `payload_state = phases[0]`
(byte-identical to `build_room_clean_payload` for atomic engines; see
[07](07-queue-engine.md)). `build_room_clean_payload` is **not** called directly here.

**Return shape.** `_build_effective_start_plan` returns a 6-key dict:
`{managed_rooms, effective_rooms, queue_state, payload_state, phases, preflight}`. The
two early-return **graph-blocked** paths (Step 2) return a different **4-key** shape —
`{managed_rooms, queue_state, payload_state, preflight}` with **no `effective_rooms` and
no `phases`** — building `payload_state` as `_build_dispatch_phases(...)[0]`.

### Multiple modifier merging: last-write-wins

When multiple modifier rules match the same room, their `changes` dicts are applied in the order rules are stored using `dict.update`:

```python
modifier_matches[room_id]["changes"].update(change_set)
```

This means the **last matching rule wins** for any field that appears in more than one rule's `changes`. Rule order is iteration order (i.e. the order in which rules appear in `room["rules"]`). There is no priority system beyond position.

Example: if Rule 1 sets `fan_speed: "Quiet"` and Rule 2 (later) sets `fan_speed: "Max"`, the result is `fan_speed: "Max"`.

### Modifier fan-out (Pass 2)

A modifier rule may declare an optional `fan_out_room_ids` list to apply its
effect to **additional rooms beyond the one that owns the rule**. The rule is
stored once on its owning room; no duplicate rule is created on the targets —
the effect is computed at planning time. (Only modifier rules can fan out;
blockers already cascade transitively through the access graph, so they have no
fan-out mechanism. See the user-facing write-up in
[advanced/06-room-rules](../advanced/06-room-rules.md#fan-out-apply-a-rule-to-additional-rooms).)

After the per-room modifier loop (Step 3) and the blocked-room computation
(Step 5), `_build_effective_start_plan` runs a dedicated **Pass 2 — rule
fan-out expansion** (`planning/run_plan.py`). It iterates every room's rules in
ascending source-room-id order and, for each enabled modifier rule with a
non-empty `fan_out_room_ids`, evaluates the rule's condition via
`_room_rule_matches` and merges its `changes` into each eligible target's
`modifier_matches` entry:

```python
for source_room_id in sorted(all_rooms_by_id):
    for rule in source_room.get("rules", []):
        if rule.kind != "modifier": continue
        if not rule.get("fan_out_room_ids"): continue
        if not _room_rule_matches(rule): continue          # condition is

        change_set = rule.effect.get("changes", {})
        if not change_set: continue
        for target_id in rule["fan_out_room_ids"]:
            if target_id not in all_rooms_by_id: continue   # stale ref dropped
            if target_id == source_room_id: continue        # self fan-out ignored
            if target_id not in selected_set: continue       # unselected skipped
            if target_id in blocked_set: continue            # blocked skipped

            entry = modifier_matches.setdefault(
                target_id,
                _build_modified_room_entry(room_id=target_id, derived=True,
                                           source_room_id=source_room_id, ...))
            for field, value in change_set.items():
                entry["changes"].setdefault(field, value)    # direct/earlier wins
            entry["triggered_rule_ids"].append(rule.id)
```

Semantics, all enforced in this pass:

- **Condition is evaluated independently of the owning room's selection.** If
  the rule's condition is true, fan-out targets receive the modifier even when
  the source room is excluded from the current run. The trigger is the watched
  entity, not the owner's queue state.
- **Direct rules (and earlier fan-out) win per field.** Merging uses
  `dict.setdefault`, so a field already set on the target — by the target's own
  direct modifier (Step 3) or by an earlier source room — is **not**
  overwritten. This is the inverse of the direct-modifier merge (§5
  last-write-wins): for fan-out it is first-write-wins per field. Because
  sources are iterated in ascending room-id order, the merge is deterministic.
- **Targets that are not selected, or are blocked, are skipped** — there is no
  point modifying a room that will not be cleaned. Unknown / non-numeric target
  IDs (e.g. stale references left after a room delete) are silently dropped, and
  self-fan-out is ignored.
- **Provenance.** When an entry is created purely by fan-out (no direct rule
  contributed first), `_build_modified_room_entry` flags it `derived: True` and
  records `source_room_id`, `source_room_name`, `source_rule_id`,
  `source_rule_name`. If a direct rule already populated the entry, `derived`
  stays `False` — direct rules win the entry-level attribution. Either way,
  every contributing rule is appended to `triggered_rule_ids`. These fields let
  the start-status panel show fan-out provenance (e.g. "via Bedroom 1's Quiet
  Mode").

Fan-out is one level, not transitive — a target room's own rules do not chain
further on top of a fan-out it received.

### The `preflight` object (full schema)

`_build_effective_start_plan` returns `preflight` — the dict the card renders and
`start_selected_rooms` gates on. Every field, with defaults:

| Field | Type | Default / note |
|---|---|---|
| `available` | bool | `True` |
| `blocked` | bool | `False` (True only on the graph-blocked early returns) |
| `requires_confirmation` | bool | `False` |
| `confirm_token` | str \| null | `None`; set only when `requires_confirmation` |
| `reason` | str | `"ready"` → `"rooms_blocked"` → `"confirmation_required"` (or a graph-block reason) |
| `message` | str | human string |
| `selected_room_ids` / `included_room_ids` / `blocked_room_ids` | list[int] | |
| `selected_room_count` / `included_room_count` / `blocked_room_count` | int | |
| `selected_expected_minutes` / `included_expected_minutes` / `blocked_expected_minutes` | float | `0.0` |
| `blocked_ratio_rooms` / `blocked_ratio_time` | float | `0.0`, 4-dp (§6) |
| `blocked_rooms` | list | blocked-room entries (below) |
| `modified_rooms` | list | modified-room entries (below) |
| `warnings` | list[str] | e.g. `["rooms_blocked"]` |
| `graph` | dict | `{valid, issues, grants_access_to, requires_access_from}` |
| `mop_carpet_warning` | dict \| null | **added only on the non-blocked path** (the closing `.update`) |
| `order_advisory` | dict \| null | likewise added only on the non-blocked path |

**`blocked_rooms[]` entry** (`_build_blocked_room_entry`): `{room_id, name, source
("direct_rule" | "access_dependency"), reason ("access_blocked" for a dependency block,
else the effect reason / label / entity_id / "rule_blocked"), triggered_rule_id,
trigger_entity_id (mid-job path only), blocked_by_room_id, blocked_by_room_name}`.

**`modified_rooms[]` entry** (`_build_modified_room_entry`): `{room_id, name, changes,
triggered_rule_ids, derived, source_room_id, source_room_name, source_rule_id,
source_rule_name}` (the `derived` / `source_*` fields carry fan-out provenance; §5 Pass 2).

---

## 6. The 20%/40% confirmation threshold

After blocked rooms are determined, two ratios are computed:

```python
blocked_ratio_time = blocked_expected_minutes / selected_expected_minutes
blocked_ratio_rooms = len(blocked_room_ids) / len(selected_room_ids)
```

`blocked_expected_minutes` and `selected_expected_minutes` come from the learning
subsystem's per-room time estimates. Both ratios are **rounded to 4 dp** and
**zero-guarded**: `blocked_ratio_rooms` is `0.0` when no rooms are selected;
`blocked_ratio_time` is `0.0` unless `selected_expected_minutes > 0`.

**Threshold:**
```python
requires_confirmation = bool(
    blocked_room_ids
    and (blocked_ratio_time >= 0.20 or blocked_ratio_rooms >= 0.40)
)
```

In plain terms:
- At least 20% of the expected job time will be removed, **or**
- At least 40% of the selected rooms will be skipped.

Both ratios are included in the preflight object (`blocked_ratio_time`, `blocked_ratio_rooms`) so the card can display them to the user.

When `requires_confirmation` is `True`:
- `preflight.requires_confirmation = True`
- `preflight.confirm_token` is set to a 12-character SHA-1 hex digest.
- `preflight.reason = "confirmation_required"`
- The message is: `"Start confirmation required: N% of expected job time will be removed by blockers."`

The caller must pass either `confirm_reduced_run=True` or the correct `confirm_token` in the `start_selected_rooms` call to proceed.

When blockers exist but stay **under** the threshold, `requires_confirmation` is `False`
but `preflight.reason` is `"rooms_blocked"` (with `warnings=["rooms_blocked"]` and an "`N`
room(s) are blocked and will be skipped." message); with no blockers the reason is
`"ready"`. The confirmation message's `N` is `round(blocked_ratio_time * 100)`.

---

## 7. Mid-job re-evaluation

Mid-job re-evaluation is handled by `get_runtime_path_block_report`. It is called by the automation subsystem when a watched entity changes state during an active job.

**What is re-evaluated**: **blocker rules only**. Modifier rules are never re-evaluated mid-job. The cleaning settings that were baked into the payload at job start are immutable for the duration of the job.

**How it works**:

1. The active job must be in `"started"` or `"paused"` status. Returns `None` otherwise.
2. Structural access graph issues abort the report (returns `None`).
3. The remaining room IDs (not yet completed) are extracted from `active_job["queue_room_ids"]` minus `active_job["completed_room_ids"]`.
4. Blocker rules for all queued rooms are re-evaluated against current HA state using `_room_rule_matches`.
5. The same accessibility propagation algorithm as `_build_effective_start_plan` is run over the remaining rooms.
6. A 16-char SHA-1 **dedup signature** over `trigger_entity_id | trigger_entity_state |
   affected_room_ids | sorted(triggered_rule_ids)` is computed; if it equals the active
   job's stored `last_path_block_signature`, the call returns `None` (no repeat report
   for the same block). Otherwise the new signature is **written back** into
   `data["active_jobs"][...]["last_path_block_signature"]`.

The report triggers pause / notify / an automated path-block action (per-job
`path_block_action`). It **does** persist the `last_path_block_signature` field on the
active job (popped again on the no-longer-blocked path), but it does **not** change the
queue or payload. Note the propagation is **queue-scoped** — parents outside
`queue_room_ids` are ignored and accessibility is seeded from `queue_room_ids` only,
unlike the start-plan version which uses the full room set. Extra early-`None` guards:
non-`started`/`paused` status, structural graph issues, blocker rules present but **no**
`grants_access_to` anywhere, and no affected remaining rooms.

**Return schema** (14 keys): `vacuum_entity_id, map_id, job_id, trigger_entity_id,
trigger_entity_state, affected_remaining_room_ids, affected_remaining_room_names,
directly_blocked_room_ids, indirectly_blocked_room_ids, remaining_room_ids, reason_codes,
affected_rooms, requires_attention (True), event_scope ("active_job_path_blocked")`.

> **See also:** [06-job-lifecycle](06-job-lifecycle.md) §3 for the monitoring loop (`get_runtime_path_block_report`) that triggers mid-job rule checks and §1 Preflight for the job-start evaluation site; [08-rooms-system](08-rooms-system.md) §6 for the room data model that rules operate on.

---

## 8. Backend wire format

### What `_buildRulePayload` produces

The frontend function `_buildRulePayload(draft, descriptor)` in `bindings/room-rules.js` serialises the editor draft into the persisted rule object:

```json
{
  "id": "abc123",
  "label": "Skip when door open",
  "entity_id": "binary_sensor.front_door",
  "kind": "blocker",
  "operator": "is_on",
  "enabled": true,
  "effect": {
    "action": "exclude",
    "reason": "Door open"
  }
}
```

For a modifier:

```json
{
  "id": "def456",
  "entity_id": "input_select.cleaning_mode",
  "kind": "modifier",
  "operator": "equals",
  "value": "quiet",
  "enabled": true,
  "effect": {
    "action": "mutate",
    "reason": null,
    "changes": {
      "fan_speed": "Quiet",
      "clean_passes": 1
    }
  }
}
```

**Serialisation rules:**

- `id` is included only when editing an existing rule (skipped for new rules — the backend assigns the ID).
- `label` is included only when non-empty after trim.
- `value` is omitted entirely for no-value operators (`is_on`, `is_off`, `exists`, `missing`), and omitted when `draft.value` is `null` **or when the serialised result is an empty array / blank string**.
- `value` is serialised through `_serializeRuleValue`: multi-select → normalised string array; number → JS `Number`; text → raw value.
- `effect.reason` is `null` when empty (not an empty string).
- `effect.changes` is built by iterating `draft.effect.changes`, skipping `null` values, and enforcing the 1-or-2 constraint on `clean_passes`.
- `effect.changes` is only present on modifier rules.
- `fan_out_room_ids` is an optional top-level array of integer room IDs to which a modifier rule's effect is fanned out (see §5, Pass 2). It is present only on modifier rules and only when non-empty.

### `fan_out_room_ids` normalization

`AccessGraphManager._normalize_room_rule` (`rooms/access_graph.py`) preserves
`fan_out_room_ids` on persisted rules, but only for modifier rules. The list is
sanitised on the way in: each entry is coerced to `int`, any value `<= 0` or any
duplicate is dropped (dedup via a `seen` set, original order preserved), and the
key is omitted from the normalized rule entirely when the cleaned list is empty.
Blocker rules never carry `fan_out_room_ids`. The field must survive
normalization because `_build_effective_start_plan` iterates the **normalized**
rule dict — if it were stripped, the Pass-2 fan-out would never run. Stale IDs
that survive normalization (e.g. a target room deleted later) are handled at
plan time by the runtime filter in Pass 2, not here.

A serialised modifier with fan-out:

```json
{
  "id": "ghi789",
  "entity_id": "input_boolean.quiet_mode",
  "kind": "modifier",
  "operator": "is_on",
  "enabled": true,
  "fan_out_room_ids": [3, 4],
  "effect": {
    "action": "mutate",
    "reason": "Quiet mode",
    "changes": { "fan_speed": "Quiet" }
  }
}
```

### Conditions serialisation

Conditions are flat on the rule object itself — `entity_id`, `operator`, and `value` are top-level fields, not nested under a `condition` key.

---

## 9. Adding a new operator

### Backend: `_room_rule_matches` in `rooms/access_graph.py` (`AccessGraphManager`)

**Step 0 (mandatory — the load-bearing step):** add `"<new_op>"` to the
`allowed_operators` set in `_normalize_room_rule` (`rooms/access_graph.py`). Any
operator **not** in that allowlist is rewritten to `"equals"` **at persist / normalize
time**, so without this step a rule authored with the new operator is silently stored as
`equals` and your new `_room_rule_matches` branch is never reached.

Then add a new `if operator == "<new_op>":` branch on the `_room_rule_matches`
method. Place it before the final `return False`. The branch receives:

- `state_value` — raw string from `hass.states.get(entity_id).state`
- `normalized_state` — the result of `_normalize_rule_operand(state_value)`
- `target_value` — `rule.get("value")`

Return `True` or `False`.

Example — a hypothetical `starts_with` operator:

```python
if operator == "starts_with":
    return str(state_value).lower().startswith(str(target_value or "").lower())
```

### Frontend: operator list in `state/room-rules.js`

1. Add the operator string to the relevant category constant (`BOOLEAN_OPERATORS`, `ENUM_OPERATORS`, `NUMERIC_OPERATORS`, or `TEXT_OPERATORS`), and to `ALL_OPERATORS`.
2. Add a `case` to the `ruleConditionSummary` switch statement to produce a human-readable display string.
3. If the operator requires a value: verify `NO_VALUE_OPERATORS` does not include it.
4. If the operator requires a special value mode, update `valueModeForOperator` in `ruleEntityDescriptor`.

### Frontend: operator group in `state/room-rules.js`

Add an entry to the `groups` array inside `ruleOperatorGroups` so the new operator appears in the editor's condition section. Place it in an existing group or add a new group:

```js
{
  label: "String",
  operators: [
    { value: "starts_with", label: "Starts with" },
  ],
},
```

### Frontend: serialisation in `bindings/room-rules.js`

If the new operator needs special value serialisation, add a case to `_serializeRuleValue`. Otherwise the default text path handles it.
