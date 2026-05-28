# Room Rules System

Room rules let you automate what happens to each room at job start. A rule watches a Home Assistant entity and, when its condition is true, either blocks the room entirely (a **Blocker**) or overrides its cleaning settings (a **Modifier**).

Source files:
- Backend evaluation: `custom_components/eufy_vacuum/core/manager.py`
- Frontend state: `src/state/room-rules.js`
- Frontend renderer: `src/renderers/room-rules.js`
- Frontend bindings: `src/bindings/room-rules.js`

---

## 1. Rule types

### Blocker

A Blocker removes the room from the cleaning queue for the current job when its condition is true.

- **Can**: exclude the room from the payload entirely.
- **Cannot**: change any cleaning settings; it has no `changes` dict.
- **Effect shape**: `{ "action": "exclude", "reason": "<optional human label>" }`

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

The backend does not enforce this constraint itself; it trusts the frontend to serialise only valid values.

---

## 5. Evaluation pipeline

### When rules are evaluated

Rules are evaluated **once: at job start time**, inside `_build_effective_start_plan`. This method is called by `get_start_status` (which drives the card's preflight display) and again at the top of `start_selected_rooms` to produce the final effective plan before the API call — see [queue-engine.md](queue-engine.md) for the queue and payload builders the effective plan feeds into.

The only other evaluation site is `get_runtime_path_block_report`, which re-evaluates **blocker rules only** mid-job as entity states change (see section 7).

Rules are never evaluated when a room is toggled, when the user edits settings, or when `build_queue` / `build_room_payload` are called in isolation.

### `_room_rule_matches`: evaluation order

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

For each included (non-blocked) selected room:

```python
updates = {"enabled": True, "order": next_order}
next_order += 1
if room_id in modifier_matches:
    updates.update(modifier_matches[room_id]["changes"])
updated_room = _protected_room_config({**room_data, **updates})
```

`_protected_room_config` enforces carpet/mop invariants (e.g. a carpet room cannot have `clean_mode = "mop"`).

**Step 7 — Build queue and payload**

`build_queue_from_managed_rooms` and `build_room_clean_payload` are called on the effective room set (blocked rooms disabled, modifier changes applied). These produce the final `queue_state` and `payload_state`.

### Multiple modifier merging: last-write-wins

When multiple modifier rules match the same room, their `changes` dicts are applied in the order rules are stored using `dict.update`:

```python
modifier_matches[room_id]["changes"].update(change_set)
```

This means the **last matching rule wins** for any field that appears in more than one rule's `changes`. Rule order is iteration order (i.e. the order in which rules appear in `room["rules"]`). There is no priority system beyond position.

Example: if Rule 1 sets `fan_speed: "Quiet"` and Rule 2 (later) sets `fan_speed: "Max"`, the result is `fan_speed: "Max"`.

### Rule fan-out — pass 2

A modifier rule may carry an optional `fan_out_room_ids: list[int]` field. When present and non-empty, the run-planning pipeline executes a second modifier-resolution pass after the blocker resolution finalises `blocked_room_ids`. This pass extends the rule's effect to additional rooms beyond the rule's owning room.

**Schema addition:**

```json
{
  "id": "rule_abc",
  "kind": "modifier",
  "entity_id": "input_boolean.bedroom_quiet_mode",
  "operator": "is_on",
  "effect": { "changes": { "fan_speed": "quiet" } },
  "fan_out_room_ids": [2, 3]
}
```

Only valid on `kind: "modifier"`. The card UI strips the field when a rule's kind is flipped to `blocker`. Absent / empty array = pre-fan-out behaviour (zero-risk additive change).

**Algorithm (pass 2):**

```python
selected_set = set(selected_room_ids)
blocked_set = set(blocked_room_ids)

for source_room_id in sorted(all_rooms_by_id.keys()):
    for rule in all_rooms_by_id[source_room_id].get("rules", []):
        if rule.kind != "modifier" or not rule.enabled: continue
        if not rule.get("fan_out_room_ids"): continue
        if not _room_rule_matches(rule): continue

        change_set = rule.effect.get("changes", {})
        if not change_set: continue

        for target_id in rule["fan_out_room_ids"]:
            if target_id not in all_rooms_by_id: continue   # runtime filter
            if target_id == source_room_id: continue        # defensive
            if target_id not in selected_set: continue
            if target_id in blocked_set: continue

            if target_id not in modifier_matches:
                modifier_matches[target_id] = _build_modified_room_entry(
                    room_id=target_id,
                    name=all_rooms_by_id[target_id].get("name"),
                    derived=True,
                    source_room_id=source_room_id,
                    source_room_name=...,
                    source_rule_id=rule.id,
                    source_rule_name=rule.label or rule.entity_id,
                )

            # Setdefault per field — direct rules win, fan-out fills gaps.
            for field, value in change_set.items():
                modifier_matches[target_id]["changes"].setdefault(field, value)

            triggered = modifier_matches[target_id]["triggered_rule_ids"]
            if rule.id not in triggered:
                triggered.append(rule.id)
```

**Locked design decisions** (spec 2026-05-28):

1. **The rule's condition is evaluated independently of the owning room's queue inclusion.** Whether Bedroom 1 itself is selected for the run has no effect on whether Bedroom 1's rule fans out to Hallway. The mental model is "when the trigger entity is on, those rooms get quieter" — orthogonal to which rooms the user picked for this specific run.
2. **Direct rules win per field.** `setdefault` is the merge primitive (not `update`). A target room's own direct-rule fields are preserved; fan-out only fills in fields the target has not already overridden.
3. **First-fan-out-wins among multiple sources** for the same target field. Source rooms are iterated in ascending `room_id` order so the result is deterministic regardless of `dict` insertion order. There is no priority knob.
4. **Targets not in the selection are skipped.** No point applying a modifier to a room that won't be cleaned in this run.
5. **Targets in `blocked_room_ids` are skipped.** Same logic as direct modifiers, which also bypass blocked rooms.
6. **Self-fan-out is silently ignored.** The card UI prevents authoring it, this is defence in depth.
7. **One level, not transitive.** Bedroom 1's rule fans out to Hallway. Hallway's own rules are evaluated in pass 1 (direct rules), not re-evaluated with fan-out semantics in pass 2. There is no recursion.

**Reporting:**

When an entry in `modifier_matches` is created entirely by pass 2 (no direct rule contributed first), the entry is flagged `derived: True` with `source_room_id`, `source_room_name`, `source_rule_id`, and `source_rule_name` populated. When a direct rule populated the entry in pass 1 first and pass 2 merges in additional fan-out fields, `derived` stays `False` — direct wins the entry-level attribution. Per-field provenance is intentionally out of scope; `triggered_rule_ids` lists every contributing rule for traceability.

The card's pre-start "Modified Rooms" preview surfaces the derived attribution as `<changes> (via <source_room_name>'s <source_rule_name>)` so users can trace why a room they didn't author a rule for is being modified.

**Out of scope:**

- Per-field provenance ("this field came from fan-out, that field came from direct rule")
- Fan-out for blockers (the access graph already handles transitive blocking)
- Delete-time cascade cleanup of stale target IDs (the runtime filter at the top of the target loop catches unknown IDs cheaply enough that the cascade pass is unnecessary)

---

## 6. The 20%/40% confirmation threshold

After blocked rooms are determined, two ratios are computed:

```python
blocked_ratio_time = blocked_expected_minutes / selected_expected_minutes
blocked_ratio_rooms = len(blocked_room_ids) / len(selected_room_ids)
```

`blocked_expected_minutes` and `selected_expected_minutes` come from the learning subsystem's per-room time estimates. If no estimates are available, both values are `0.0`.

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
6. The result is a path-block report listing which remaining rooms are now blocked and why.

The report is used to trigger pause, notify the user, or take an automated path-block action (configured per job via `path_block_action`). It does not mutate the job or payload.

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
- `value` is omitted entirely for no-value operators (`is_on`, `is_off`, `exists`, `missing`), and omitted when `draft.value` is `null`.
- `value` is serialised through `_serializeRuleValue`: multi-select → normalised string array; number → JS `Number`; text → raw value.
- `effect.reason` is `null` when empty (not an empty string).
- `effect.changes` is built by iterating `draft.effect.changes`, skipping `null` values, and enforcing the 1-or-2 constraint on `clean_passes`.
- `effect.changes` is only present on modifier rules.

### Conditions serialisation

Conditions are flat on the rule object itself — `entity_id`, `operator`, and `value` are top-level fields, not nested under a `condition` key.

---

## 9. Adding a new operator

### Backend: `_room_rule_matches` in `core/manager.py`

Add a new `if operator == "<new_op>":` branch. Place it before the final `return False`. The branch receives:

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
