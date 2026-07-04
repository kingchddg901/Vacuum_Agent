// Run: node --test src/bindings/room-rules-payload.test.mjs
//
// Coverage targets — src/bindings/room-rules.js :: _buildRulePayload
//   [BRP-1]  action mapping: kind "modifier" -> "mutate", else "exclude"
//   [BRP-2]  base-field defaults + trims (entity_id, kind, operator, enabled, reason)
//   [BRP-3]  id / label inclusion gates (truthy id, trimmed non-empty label)
//   [BRP-4]  NO_VALUE_OPERATORS drop value; value-operators keep serialized value
//   [BRP-5]  value inclusion gate: null/empty-after-serialize dropped, else kept
//   [BRP-6]  clean_passes gate: keeps ONLY values normalizing to 1 or 2, drops others
//   [BRP-7]  modifier changes: null skipped, other keys pass through untouched
//   [BRP-8]  fan_out_room_ids: Number + isFinite && >0 filter; set only when non-empty
//   [BRP-9]  non-modifier kinds never get effect.changes / fan_out_room_ids

import { test } from "node:test";
import assert from "node:assert/strict";

import { _buildRulePayload } from "./room-rules.js";

// A descriptor whose valueModeForOperator forces a given mode, so we can
// exercise the number/multi-select serialize branches deterministically.
const descriptorForMode = (mode) => ({
  valueModeForOperator: () => mode,
});

test("[BRP-1] effect.action: modifier -> mutate, everything else -> exclude", () => {
  assert.equal(
    _buildRulePayload({ kind: "modifier", entity_id: "sensor.x" }, null).effect.action,
    "mutate"
  );
  assert.equal(
    _buildRulePayload({ kind: "blocker", entity_id: "sensor.x" }, null).effect.action,
    "exclude"
  );
  // Unknown / absent kind is NOT "modifier" -> exclude (default kind is "blocker").
  assert.equal(
    _buildRulePayload({ entity_id: "sensor.x" }, null).effect.action,
    "exclude"
  );
  assert.equal(
    _buildRulePayload({ kind: "whatever", entity_id: "sensor.x" }, null).effect.action,
    "exclude"
  );
});

test("[BRP-2] base fields: defaults, trims, enabled !== false", () => {
  const p = _buildRulePayload(
    { entity_id: "  sensor.trim  ", effect: { reason: "  because  " } },
    null
  );
  assert.equal(p.entity_id, "sensor.trim"); // trimmed
  assert.equal(p.kind, "blocker"); // default
  assert.equal(p.operator, "is_on"); // default
  assert.equal(p.enabled, true); // undefined !== false -> true
  assert.equal(p.effect.reason, "because"); // trimmed

  // enabled defaulting: only an explicit false disables.
  assert.equal(_buildRulePayload({ entity_id: "a", enabled: false }, null).enabled, false);
  assert.equal(_buildRulePayload({ entity_id: "a", enabled: true }, null).enabled, true);
  assert.equal(_buildRulePayload({ entity_id: "a", enabled: 0 }, null).enabled, true); // 0 !== false

  // Whitespace-only / missing reason -> null (not empty string).
  assert.equal(_buildRulePayload({ entity_id: "a" }, null).effect.reason, null);
  assert.equal(
    _buildRulePayload({ entity_id: "a", effect: { reason: "   " } }, null).effect.reason,
    null
  );

  // entity_id defaults to "" when absent.
  assert.equal(_buildRulePayload({}, null).entity_id, "");
});

test("[BRP-3] id and label inclusion gates", () => {
  const withId = _buildRulePayload({ entity_id: "a", id: "rule-7" }, null);
  assert.equal(withId.id, "rule-7");

  const noId = _buildRulePayload({ entity_id: "a" }, null);
  assert.ok(!("id" in noId)); // absent, not undefined

  // Falsy id (empty string) is NOT copied.
  assert.ok(!("id" in _buildRulePayload({ entity_id: "a", id: "" }, null)));

  // Label is trimmed and only kept when non-empty after trim.
  assert.equal(_buildRulePayload({ entity_id: "a", label: "  Hi  " }, null).label, "Hi");
  assert.ok(!("label" in _buildRulePayload({ entity_id: "a", label: "   " }, null)));
  assert.ok(!("label" in _buildRulePayload({ entity_id: "a" }, null)));
});

test("[BRP-4] NO_VALUE_OPERATORS drop value; value-operators keep it", () => {
  // is_on/is_off/exists/missing are in NO_VALUE_OPERATORS -> value never set.
  for (const op of ["is_on", "is_off", "exists", "missing"]) {
    const p = _buildRulePayload({ entity_id: "a", operator: op, value: "42" }, null);
    assert.ok(!("value" in p), `operator ${op} must drop value`);
  }

  // A value-operator with text mode (no descriptor) keeps the raw value.
  const kept = _buildRulePayload(
    { entity_id: "a", operator: "equals", value: "living_room" },
    null
  );
  assert.equal(kept.value, "living_room");
});

test("[BRP-5] value inclusion gate on serialized emptiness", () => {
  // draft.value == null -> skipped even for a value-operator.
  assert.ok(
    !("value" in _buildRulePayload({ entity_id: "a", operator: "equals", value: null }, null))
  );
  assert.ok(
    !(
      "value" in
      _buildRulePayload({ entity_id: "a", operator: "equals", value: undefined }, null)
    )
  );

  // Text value that serializes to whitespace-only -> String(v).trim() falsy -> dropped.
  assert.ok(
    !("value" in _buildRulePayload({ entity_id: "a", operator: "equals", value: "   " }, null))
  );

  // multi-select mode: empty array after normalize -> length 0 -> dropped.
  assert.ok(
    !(
      "value" in
      _buildRulePayload(
        { entity_id: "a", operator: "in_list", value: ["", "  "] },
        descriptorForMode("multi-select")
      )
    )
  );

  // multi-select mode: non-empty list kept, normalized to trimmed strings.
  const multi = _buildRulePayload(
    { entity_id: "a", operator: "in_list", value: [" kitchen ", "den", ""] },
    descriptorForMode("multi-select")
  );
  assert.deepEqual(multi.value, ["kitchen", "den"]);

  // number mode: finite numeric serialized to a Number, kept (non-empty string form).
  const num = _buildRulePayload(
    { entity_id: "a", operator: "gt", value: "5" },
    descriptorForMode("number")
  );
  assert.equal(num.value, 5);
  assert.equal(typeof num.value, "number");

  // number mode with 0: Number(0) is finite -> value 0. String(0).trim() = "0" (truthy) -> kept.
  const zero = _buildRulePayload(
    { entity_id: "a", operator: "gt", value: 0 },
    descriptorForMode("number")
  );
  assert.equal(zero.value, 0);
});

test("[BRP-6] clean_passes gate keeps ONLY values normalizing to 1 or 2", () => {
  const build = (passes) =>
    _buildRulePayload(
      { entity_id: "a", kind: "modifier", effect: { changes: { clean_passes: passes } } },
      null
    );

  assert.equal(build(1).effect.changes.clean_passes, 1);
  assert.equal(build(2).effect.changes.clean_passes, 2);
  // String forms that Number()-normalize to 1/2 are accepted and coerced to Number.
  assert.equal(build("1").effect.changes.clean_passes, 1);
  assert.equal(build("2").effect.changes.clean_passes, 2);

  // Out-of-range / non-normalizing -> key dropped entirely.
  assert.ok(!("clean_passes" in build(3).effect.changes));
  assert.ok(!("clean_passes" in build(0).effect.changes));
  assert.ok(!("clean_passes" in build(1.5).effect.changes));
  assert.ok(!("clean_passes" in build("2x").effect.changes)); // Number("2x") = NaN
  assert.ok(!("clean_passes" in build("").effect.changes)); // Number("") = 0, not 1/2

  // null value is skipped by the earlier `value == null` guard (no key).
  assert.ok(!("clean_passes" in build(null).effect.changes));
});

test("[BRP-7] modifier changes: null skipped, other keys pass through untouched", () => {
  const p = _buildRulePayload(
    {
      entity_id: "a",
      kind: "modifier",
      effect: {
        changes: {
          fan_speed: "max",
          water_level: null, // skipped (value == null)
          mop_mode: "deep",
          clean_passes: 2,
        },
      },
    },
    null
  );
  assert.deepEqual(p.effect.changes, {
    fan_speed: "max",
    mop_mode: "deep",
    clean_passes: 2,
  });
  assert.ok(!("water_level" in p.effect.changes));

  // No changes object -> empty cleaned object.
  const empty = _buildRulePayload({ entity_id: "a", kind: "modifier" }, null);
  assert.deepEqual(empty.effect.changes, {});
});

test("[BRP-8] fan_out_room_ids: Number+isFinite&&>0 filter, set only when non-empty", () => {
  const build = (ids) =>
    _buildRulePayload({ entity_id: "a", kind: "modifier", fan_out_room_ids: ids }, null);

  // Mixed input: strings coerce, non-positive / non-finite / zero dropped.
  const p = build(["1", 2, "3", 0, -4, "x", null, NaN, 5.5]);
  assert.deepEqual(p.fan_out_room_ids, [1, 2, 3, 5.5]);

  // All-invalid -> field omitted (empty after filter).
  assert.ok(!("fan_out_room_ids" in build([0, -1, "nope", null])));

  // Missing / non-array -> field omitted.
  assert.ok(!("fan_out_room_ids" in _buildRulePayload({ entity_id: "a", kind: "modifier" }, null)));
  assert.ok(
    !(
      "fan_out_room_ids" in
      _buildRulePayload({ entity_id: "a", kind: "modifier", fan_out_room_ids: "1,2" }, null)
    )
  );
});

test("[BRP-9] non-modifier kinds get no changes / fan_out fields", () => {
  const p = _buildRulePayload(
    {
      entity_id: "a",
      kind: "blocker",
      effect: { changes: { fan_speed: "max" } }, // ignored for non-modifier
      fan_out_room_ids: [1, 2, 3], // ignored for non-modifier
    },
    null
  );
  assert.ok(!("changes" in p.effect)); // effect.changes only added in the modifier branch
  assert.ok(!("fan_out_room_ids" in p));
});
