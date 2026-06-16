# Room Rules

Room rules are per-room conditional logic that tell the integration what to do with a room based on the live state of a Home Assistant entity at the moment a job starts. Each rule watches one entity, evaluates a condition against its current state, and either skips the room entirely or temporarily overrides its cleaning settings.

Rules are not evaluated in the background or on a schedule. They are evaluated at job start time, immediately before the vacuum begins cleaning. This means the decision is always based on what is actually happening right now, not on some cached snapshot.

---

## What a Rule Is

A rule has three parts:

- **A condition.** An entity ID plus an operator (and sometimes a value) that is checked against the entity's current state in HA.
- **A kind.** Either `blocker` or `modifier`, which determines what happens when the condition is true.
- **An effect.** What actually happens to the room if the condition matches.

Rules are stored on the room object itself, not as a separate HA entity or automation. You manage them entirely inside the card's Room Rules view.

---

## Rule Kinds

### Blockers

A blocker removes the room from the cleaning job when its condition is true. The room is skipped completely — it will not appear in the queue the vacuum receives.

Use a blocker when the room should not be cleaned at all under certain conditions. Examples:

- Skip the living room when `binary_sensor.living_room_door` is `on` (door is open, pet or child might be in there).
- Skip the hallway when `input_boolean.guests_staying` is `on`.
- Skip the kitchen when `person.you` is `home` (you are cooking).

When a room is blocked, any rooms that depend on it for access are also blocked. If the vacuum can only reach the bedroom by passing through the office, and the office is blocked, the bedroom is blocked too. This dependency resolution is handled automatically by the access graph.

### Modifiers

A modifier changes the cleaning settings for the room when its condition is true, but does not skip it. The room stays in the queue; it just runs with different parameters.

You must configure at least one setting override for a modifier to be valid. The overridable settings are:

| Setting | Options |
|---|---|
| Clean Mode | Vacuum, Mop, Vacuum & Mop |
| Fan Speed | Quiet, Standard, Boost, Max |
| Water Level | Off, Low, Medium, High |
| Clean Intensity | Quick, Narrow, Deep |
| Clean Passes | 1 or 2 |
| Edge Mopping | On or Off |

For each setting, the `-` option means "keep the room's saved setting." You only need to set the ones you want to override.

Which override fields appear depends on the vacuum's adapter capabilities. On brands without per-room water, passes, or edge control — for example the Roborock S6, where water level is app-controlled, clean passes are global (one batch value for the whole run), and edge mopping is not exposed — those controls are hidden, and you can only override the settings the device exposes per-room (on the S6, fan speed).

Use a modifier when the room should still be cleaned but with different behavior. Examples:

- Switch to Mop-only mode in the bathroom when `input_boolean.mop_day` is `on`.
- Reduce fan speed to Quiet in the bedroom when `binary_sensor.baby_sleeping` is `on`.
- Increase clean passes to 2 in the kitchen when `sensor.cooking_mess_level` is above a threshold.

Multiple modifier rules can match for the same room. When that happens, each matching rule's changes are merged in the order the rules are evaluated. Later rules overwrite earlier ones for the same setting. There is no explicit priority system — if you need a specific setting to "win," put that rule later in the room's rule list.

#### Fan-out: apply a rule to additional rooms

A modifier rule can optionally extend its effect to other rooms beyond the one that owns the rule. This is useful when one condition should change settings in several related rooms — for example, when "quiet mode" should affect not just the bedroom that authored the rule but also the hallway outside it and the adjacent bedroom.

To configure fan-out, open the modifier rule's editor and use the **Also apply to** section. Tap any room to toggle whether it receives this rule's effect. Mobile users can pick from a chip list; desktop users see the same chips.

How fan-out behaves:

- **One authored rule, many effective consequences.** The rule is stored once on its owning room. The selected target rooms do not get a hidden duplicate rule — the effect is computed at run-planning time.
- **The owning room's queue state is irrelevant to fan-out targets.** If the rule's condition is true, fan-out targets get the modifier regardless of whether the owning room is included in the current run.
- **Each target room's own rules still win.** Fan-out fills in fields the target room hasn't already overridden through its own direct rules. If the bathroom has its own rule setting Fan Speed to Boost, a fan-out from the bedroom trying to set Fan Speed to Quiet on the bathroom will be ignored for that field — but other fields the bathroom doesn't override still apply.
- **Blocked rooms are skipped.** A fan-out target that is excluded from the run by a blocker (its own, or via the access graph) does not receive the modifier — there's no point modifying a room that won't be cleaned.
- **Fan-out is one level, not transitive.** Bedroom 1's rule can fan out to Hallway, but Hallway's own rules do not chain further on top of that fan-out.

When a room appears in the pre-start "Modified Rooms" preview because of a fan-out, the entry says so — for example, `Hallway: fan_speed (via Bedroom 1's Quiet Mode)` — so the source rule is always traceable from the start-status panel.

Fan-out is only available for modifier rules. Blockers already have transitive behavior through the access graph (if A is blocked and B requires A, B is blocked too); they do not need a separate fan-out mechanism.

---

## Operators

The operator determines how the entity's current state is compared. The operators available for a rule depend on the type of entity you pick:

| Category | Available Operators |
|---|---|
| Boolean (`binary_sensor`, `switch`, `input_boolean`) | Is ON, Is OFF, Exists, Missing |
| Enum (`select`, `input_select`, or any entity with an `options` attribute) | Equals, Not equals, In list, Not in list, Exists, Missing |
| Numeric (`number`, `input_number`, or a `sensor` with a numeric state) | Equals, Not equals, >, ≥, <, ≤, Exists, Missing |
| Text (any other entity) | Equals, Not equals, In list, Not in list, Exists, Missing |

**Is ON / Is OFF** — checks whether the entity's state string is literally `on` or `off`. No value field is needed.

**Exists / Missing** — checks whether the entity is currently available in HA at all. Useful for entities that go unavailable when a device is offline.

**Equals / Not equals** — compares the entity's state to a single value you provide. String comparison is case-insensitive. Numeric states are compared as numbers.

**In list / Not in list** — compares the entity's state against a list of values. For enum entities, you pick from chips. For text entities, you type a comma-separated list.

**Numeric comparisons (>, ≥, <, ≤)** — only available when the entity is recognized as numeric. Both sides are cast to float; if either side can't be parsed as a number, the condition evaluates to false.

---

## Accessing and Configuring Rules in the Card

Open the card and navigate to the Room Rules view (it is one of the main tabs or sub-tabs depending on your card layout). You will see a tab strip across the top with one tab per room. Each tab shows a badge with the number of rules already configured for that room.

Select a room to see its rule list. Each rule card shows:

- The kind badge (Blocker or Modifier).
- The rule's label (if you set one) or the entity ID.
- A one-line condition summary, such as `is ON` or `>= 25`.
- A one-line effect summary, such as `Exclude room` or `fan: Quiet, passes: 2`.
- Whether the rule is disabled.

### Adding a Rule

Click **+ Add Rule** at the bottom of the list. The inline editor opens above the list.

1. **Rule Type** — choose Blocker or Modifier.
2. **Label** (optional) — a human-readable name. If you set one, it appears in the rule card and is used as the reason text if the room is blocked.
3. **Entity ID** — type an entity ID or partial name. As you type, the card searches your live HA entity list and shows matches. Click a suggestion to select it. The card reads the entity's domain, current state, attributes, and option list to determine its category and constrain the available operators and value controls.
4. **Condition** — pick an operator. Only the operators valid for the entity's category are shown.
5. **Value** — appears when the operator requires one. The input adapts to the entity:
   - Boolean entities: no value field (the operator already encodes the comparison).
   - Enum entities with Equals/Not equals: a dropdown of the entity's declared options.
   - Enum entities with In/Not in list: chip toggles for multi-selection.
   - Numeric entities: a number input, with min/max/step pulled from the entity's attributes.
   - Text entities: a free text input. For In/Not in list, type comma-separated values.
6. **Enabled** — defaults to Yes. Set to No to disable the rule without deleting it.
7. **Reason** (optional) — a short note recorded in the preflight report when the rule fires. For blockers, this text appears in any "rooms blocked" messages.
8. **Setting Overrides** (modifier only) — set each setting you want to override. Leave it on `-` for settings you do not want to touch.

Click **Add Rule** to save. The rule is immediately persisted to the backend via the `update_room_fields` service. The card then refreshes the dashboard snapshot so the preflight state reflects the new rule.

### Editing a Rule

Click **Edit** on any rule card to open it in the inline editor. The form is pre-populated with the current values. Make your changes and click **Save Rule**.

### Deleting a Rule

Click **Delete** on the rule card. The deletion is immediate — there is no confirmation prompt. The card re-saves the room's full rule list (minus the deleted rule) to the backend.

### Disabling a Rule Without Deleting It

Open the rule editor and set **Enabled** to No. Disabled rules are shown in the list with a "Disabled" tag and a muted appearance. They are skipped entirely during evaluation.

---

## How Rules Interact with the Queue and Cleaning Order

Rules are evaluated in `_build_effective_start_plan`, which runs at job start time (when you press the Start button or the job fires from an automation). The evaluation sequence is:

1. All rooms currently enabled in the queue are collected and sorted by their configured order.
2. Blocker rules are evaluated across every room in the map (not just enabled ones). A room whose blocker condition matches is marked as directly blocked. Only enabled rooms are checked for modifier rules.
3. The access graph is applied: if a directly blocked room is a gateway to other rooms, those downstream rooms are also removed from the run.
4. The cleaned list of rooms — with any modifier changes applied — is built into the effective queue that is sent to the vacuum.

The original queue (which rooms are enabled, their order) is not permanently changed. Blockers and modifiers are applied dynamically at run time. When the conditions clear, the next job will include those rooms again without you having to re-enable anything.

Modifier changes are applied on top of the room's saved settings. If a room is set to Vacuum mode and a modifier rule fires that says Mop, the effective run uses Mop. The room's saved setting is unchanged for future runs when the condition does not match.

### Mid-Job Re-evaluation

Blocker rules are also re-evaluated during an active job via `get_runtime_path_block_report`. If entity states change while the vacuum is running — a door opens, someone comes home — the integration can detect that a room that was included at start time would now be blocked. The mid-job report only evaluates blocker rules, not modifiers (the job payload has already been sent to the vacuum for the rooms it is cleaning).

---

## Confirmation for Large Blocks

If blocked rooms represent 20% or more of the job's expected cleaning time, or 40% or more of the total room count, the card will ask you to confirm before starting. You will see a message explaining how much of the expected run time is being removed. This prevents silent large reductions to a run when conditions change unexpectedly.

---

## Access Graph Prerequisite

Blocker rules require a complete room access graph to function. The integration needs to know the room topology so it can propagate blocks through access dependencies. If you have blocker rules configured but no access graph, the preflight check will block all runs and tell you why.

Modifier rules do not have this requirement. They work even with no access graph configured.

---

## Practical Examples

**Skip the cat's room when the cat is not inside**

- Entity: `binary_sensor.cat_flap_open`
- Kind: Blocker
- Operator: Is ON
- Reason: Cat flap open

**Quiet mode for the bedroom when someone is sleeping**

- Entity: `input_boolean.bedroom_do_not_disturb`
- Kind: Modifier
- Operator: Is ON
- Fan Speed override: Quiet
- Clean Intensity override: Quick

**Skip the garden entrance when it is raining**

- Entity: `sensor.outdoor_weather`
- Kind: Blocker
- Operator: Equals
- Value: `rainy`
- Reason: Muddy footprints expected

**Increase kitchen passes on high-traffic days**

- Entity: `sensor.weekly_cooking_count`
- Kind: Modifier
- Operator: >=
- Value: `5`
- Clean Passes override: 2

**Different mode depending on the day's schedule**

- Entity: `input_select.cleaning_mode`
- Kind: Modifier
- Operator: Equals
- Value: `deep_clean`
- Fan Speed override: Max
- Clean Intensity override: Deep
- Clean Passes override: 2
