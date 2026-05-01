/**
 * ============================================================
 * STATE: ROOM RULES
 * ============================================================
 *
 * PURPOSE
 * -------
 * Working state for the Room Rules view - per-room entity
 * rule editor (blockers and modifiers).
 *
 * Owns:
 * - active room sub-tab selection
 * - rule draft (new / edit)
 * - save error surface
 *
 * Does NOT own:
 * - persisted rule data (lives on room objects from rooms.js)
 * - service calls (live in actions/rooms.js)
 *
 * ============================================================
 */

const NO_VALUE_OPERATORS = new Set(["is_on", "is_off", "exists", "missing"]);
const BOOLEAN_OPERATORS = ["is_on", "is_off", "exists", "missing"];
const ENUM_OPERATORS = ["equals", "not_equals", "in", "not_in", "exists", "missing"];
const NUMERIC_OPERATORS = ["equals", "not_equals", "gt", "gte", "lt", "lte", "exists", "missing"];
const TEXT_OPERATORS = ["equals", "not_equals", "in", "not_in", "exists", "missing"];
const ALL_OPERATORS = [
  "is_on",
  "is_off",
  "exists",
  "missing",
  "equals",
  "not_equals",
  "gt",
  "gte",
  "lt",
  "lte",
  "in",
  "not_in",
];

function blankDraft() {
  return {
    id: null,
    label: "",
    entity_id: "",
    kind: "blocker",
    operator: "is_on",
    value: null,
    enabled: true,
    effect: {
      action: "exclude",
      reason: "",
      changes: {},
    },
  };
}

function isFiniteNumericValue(value) {
  if (value == null || value === "") return false;
  if (typeof value === "number") return Number.isFinite(value);
  const normalized = String(value).trim();
  if (!normalized) return false;
  return Number.isFinite(Number(normalized));
}

function normalizeRuleListValue(value) {
  if (Array.isArray(value)) {
    return value
      .map((entry) => String(entry ?? "").trim())
      .filter(Boolean);
  }

  const raw = String(value ?? "").trim();
  if (!raw) return [];

  return raw
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function normalizeRuleValueForDescriptor(value, descriptor, operator) {
  if (NO_VALUE_OPERATORS.has(String(operator ?? ""))) {
    return null;
  }

  const valueMode = descriptor?.valueModeForOperator?.(operator) ?? "text";

  if (valueMode === "multi-select") {
    return normalizeRuleListValue(value);
  }

  if (valueMode === "number") {
    if (value == null || value === "") return null;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : value;
  }

  return value;
}

function sanitizeRuleDraftForDescriptor(draft, descriptor) {
  if (!draft) return draft;

  const allowedOperators = descriptor?.operators ?? ALL_OPERATORS;
  const fallbackOperator = allowedOperators[0] ?? "equals";
  const operator = allowedOperators.includes(draft.operator) ? draft.operator : fallbackOperator;
  let value = normalizeRuleValueForDescriptor(draft.value, descriptor, operator);

  if (descriptor?.category === "enum") {
    const validOptions = new Set((descriptor.options ?? []).map((option) => String(option.value)));
    const valueMode = descriptor.valueModeForOperator?.(operator);

    if (valueMode === "single-select" && value != null && !validOptions.has(String(value))) {
      value = null;
    }

    if (valueMode === "multi-select") {
      value = normalizeRuleListValue(value).filter((entry) => validOptions.has(String(entry)));
    }
  }

  return {
    ...draft,
    operator,
    value,
  };
}

function formatRuleValueSummary(value) {
  return Array.isArray(value) ? value.join(", ") : value;
}

function scoreEntitySearch(entityId, friendlyName, query) {
  if (!query) return 0;

  const normalizedId = String(entityId ?? "").toLowerCase();
  const normalizedName = String(friendlyName ?? "").toLowerCase();

  if (normalizedId === query) return 100;
  if (normalizedName === query) return 95;
  if (normalizedId.startsWith(query)) return 80;
  if (normalizedName.startsWith(query)) return 70;
  if (normalizedId.includes(query)) return 50;
  if (normalizedName.includes(query)) return 40;
  return 0;
}

export function applyRoomRulesState(proto) {

  /* =========================================================
     ACTIVE ROOM SUB-TAB
     ========================================================= */

  proto.roomRulesActiveRoomId = function () {
    return this._roomRulesActiveRoomId ?? null;
  };

  proto.setRoomRulesActiveRoom = function (roomId) {
    const id = String(roomId ?? "").trim();
    this._roomRulesActiveRoomId = id || null;
    this._roomRulesDraft = null;
    this._roomRulesDraftMode = null;
    this._roomRulesSaveError = null;
  };

  /**
   * Returns the room object currently selected in the sub-tab.
   * Falls back to the first room if nothing is selected yet.
   */
  proto.resolvedRoomRulesRoom = function () {
    const rooms = this.getRoomsForActiveMap?.() ?? [];
    if (!rooms.length) return null;

    const activeId = this._roomRulesActiveRoomId;
    if (activeId) {
      const found = rooms.find((r) => String(r.id) === String(activeId));
      if (found) return found;
    }

    return rooms[0];
  };

  /* =========================================================
     RULES READ
     ========================================================= */

  proto.rulesForActiveRoomTab = function () {
    const room = this.resolvedRoomRulesRoom();
    if (!room) return [];
    return Array.isArray(room.rules) ? room.rules : [];
  };

  /* =========================================================
     DRAFT MANAGEMENT
     ========================================================= */

  proto.roomRulesDraft = function () {
    return this._roomRulesDraft ?? null;
  };

  proto.roomRulesDraftMode = function () {
    return this._roomRulesDraftMode ?? null;
  };

  proto.openNewRuleDraft = function () {
    this._roomRulesDraft = sanitizeRuleDraftForDescriptor(blankDraft(), this.ruleEntityDescriptor(""));
    this._roomRulesDraftMode = "new";
    this._roomRulesSaveError = null;
  };

  proto.openEditRuleDraft = function (rule) {
    if (!rule) return;
    this._roomRulesDraft = sanitizeRuleDraftForDescriptor({
      id: rule.id ?? null,
      label: rule.label ?? "",
      entity_id: rule.entity_id ?? "",
      kind: rule.kind ?? "blocker",
      operator: rule.operator ?? "is_on",
      value: rule.value ?? null,
      enabled: rule.enabled !== false,
      effect: {
        action: rule.effect?.action ?? (rule.kind === "modifier" ? "mutate" : "exclude"),
        reason: rule.effect?.reason ?? "",
        changes: { ...(rule.effect?.changes ?? {}) },
      },
    }, this.ruleEntityDescriptor(rule.entity_id ?? ""));
    this._roomRulesDraftMode = "edit";
    this._roomRulesSaveError = null;
  };

  proto.closeRulesDraft = function () {
    this._roomRulesDraft = null;
    this._roomRulesDraftMode = null;
    this._roomRulesSaveError = null;
  };

  proto.updateRuleDraftField = function (field, value) {
    if (!this._roomRulesDraft) return;

    if (field === "kind") {
      const kind = value === "modifier" ? "modifier" : "blocker";
      this._roomRulesDraft = sanitizeRuleDraftForDescriptor({
        ...this._roomRulesDraft,
        kind,
        effect: {
          ...this._roomRulesDraft.effect,
          action: kind === "modifier" ? "mutate" : "exclude",
          // Clear changes when switching to blocker.
          changes: kind === "blocker" ? {} : this._roomRulesDraft.effect.changes,
        },
      }, this.ruleEntityDescriptor(this._roomRulesDraft.entity_id));

    } else if (field === "operator") {
      this._roomRulesDraft = sanitizeRuleDraftForDescriptor({
        ...this._roomRulesDraft,
        operator: String(value ?? "is_on"),
        value: NO_VALUE_OPERATORS.has(String(value)) ? null : this._roomRulesDraft.value,
      }, this.ruleEntityDescriptor(this._roomRulesDraft.entity_id));

    } else if (field === "enabled") {
      this._roomRulesDraft = { ...this._roomRulesDraft, enabled: Boolean(value) };

    } else if (field === "entity_id") {
      this._roomRulesDraft = sanitizeRuleDraftForDescriptor({
        ...this._roomRulesDraft,
        entity_id: String(value ?? ""),
      }, this.ruleEntityDescriptor(value));

    } else if (field === "effect.reason") {
      this._roomRulesDraft = {
        ...this._roomRulesDraft,
        effect: { ...this._roomRulesDraft.effect, reason: String(value ?? "") },
      };

    } else if (field.startsWith("effect.changes.")) {
      const changeKey = field.slice("effect.changes.".length);
      const changes = { ...(this._roomRulesDraft.effect.changes ?? {}) };
      if (value == null) {
        delete changes[changeKey];
      } else {
        changes[changeKey] = value;
      }
      this._roomRulesDraft = {
        ...this._roomRulesDraft,
        effect: { ...this._roomRulesDraft.effect, changes },
      };

    } else {
      const descriptor = this.ruleEntityDescriptor(this._roomRulesDraft.entity_id);
      this._roomRulesDraft = {
        ...this._roomRulesDraft,
        [field]: field === "value"
          ? normalizeRuleValueForDescriptor(value, descriptor, this._roomRulesDraft.operator)
          : value,
      };
    }

    this._roomRulesSaveError = null;
  };

  /* =========================================================
     VALIDATION
     ========================================================= */

  proto.roomRulesDraftIsValid = function () {
    const draft = this._roomRulesDraft;
    if (!draft) return false;

    const entityId = String(draft.entity_id ?? "").trim();
    if (!entityId) return false;

    const descriptor = this.ruleEntityDescriptor(entityId);
    if (!descriptor.entityExists) return false;
    if (!(descriptor.operators ?? []).includes(draft.operator)) return false;

    if (!NO_VALUE_OPERATORS.has(String(draft.operator ?? ""))) {
      const valueMode = descriptor.valueModeForOperator?.(draft.operator) ?? "text";

      if (valueMode === "multi-select") {
        if (!normalizeRuleListValue(draft.value).length) return false;
      } else if (valueMode === "number") {
        if (!isFiniteNumericValue(draft.value)) return false;
      } else if (!String(draft.value ?? "").trim()) {
        return false;
      }
    }

    if (draft.kind === "modifier") {
      const changes = draft.effect?.changes ?? {};
      const meaningfulChanges = Object.entries(changes).filter(([key, value]) => {
        if (value == null) return false;
        if (key === "clean_passes") {
          return Number(value) === 1 || Number(value) === 2;
        }
        return true;
      });

      if (!meaningfulChanges.length) return false;
    }

    return true;
  };

  /* =========================================================
     SAVE ERROR
     ========================================================= */

  proto.roomRulesSaveError = function () {
    return this._roomRulesSaveError ?? null;
  };

  proto.setRoomRulesSaveError = function (error) {
    this._roomRulesSaveError = error ?? null;
  };

  /* =========================================================
     ENTITY-AWARE RULE HELPERS
     ========================================================= */

  proto.ruleEntityDescriptor = function (draftOrEntityId = null) {
    const entityId = typeof draftOrEntityId === "string"
      ? draftOrEntityId
      : draftOrEntityId?.entity_id ?? this._roomRulesDraft?.entity_id ?? "";

    const normalizedId = String(entityId ?? "").trim();
    const entityState = normalizedId ? this.entity?.(normalizedId) : null;
    const attrs = entityState?.attributes ?? {};
    const domain = normalizedId.includes(".") ? normalizedId.split(".")[0] : "";
    const stateValue = entityState?.state ?? null;
    const options = Array.isArray(attrs.options)
      ? attrs.options.map((option) => ({
          value: String(option ?? ""),
          label: String(option ?? ""),
        }))
      : [];

    let category = "unknown";

    if (["binary_sensor", "switch", "input_boolean"].includes(domain)) {
      category = "boolean";
    } else if (["select", "input_select"].includes(domain) || options.length) {
      category = "enum";
    } else if (["number", "input_number"].includes(domain)) {
      category = "numeric";
    } else if (domain === "sensor") {
      category = isFiniteNumericValue(stateValue) ? "numeric" : "text";
    } else if (String(stateValue ?? "").toLowerCase() === "on" || String(stateValue ?? "").toLowerCase() === "off") {
      category = "boolean";
    } else if (normalizedId) {
      category = "text";
    }

    const operators =
      category === "boolean" ? BOOLEAN_OPERATORS :
      category === "enum" ? ENUM_OPERATORS :
      category === "numeric" ? NUMERIC_OPERATORS :
      category === "text" ? TEXT_OPERATORS :
      ALL_OPERATORS;

    return {
      entityId: normalizedId,
      entityExists: !!entityState,
      entityLabel: String((attrs.friendly_name ?? normalizedId) || "Entity"),
      currentState: stateValue,
      category,
      operators,
      options,
      min: isFiniteNumericValue(attrs.min) ? Number(attrs.min) : null,
      max: isFiniteNumericValue(attrs.max) ? Number(attrs.max) : null,
      step: isFiniteNumericValue(attrs.step) ? Number(attrs.step) : null,
      unit: attrs.unit_of_measurement ?? null,
      valueModeForOperator(operator) {
        if (NO_VALUE_OPERATORS.has(String(operator ?? ""))) return "none";
        if (category === "boolean") return "none";
        if (category === "enum") {
          return operator === "in" || operator === "not_in" ? "multi-select" : "single-select";
        }
        if (category === "numeric") return "number";
        return "text";
      },
    };
  };

  proto.ruleOperatorGroups = function (draftOrEntityId = null) {
    const descriptor = this.ruleEntityDescriptor(draftOrEntityId);
    const allowed = new Set(descriptor.operators ?? ALL_OPERATORS);

    const groups = [
      {
        label: "State",
        operators: [
          { value: "is_on", label: "Is ON" },
          { value: "is_off", label: "Is OFF" },
        ],
      },
      {
        label: "Existence",
        operators: [
          { value: "exists", label: "Exists" },
          { value: "missing", label: "Missing" },
        ],
      },
      {
        label: "Equality",
        operators: [
          { value: "equals", label: "Equals" },
          { value: "not_equals", label: "Not equals" },
        ],
      },
      {
        label: "Numeric",
        operators: [
          { value: "gt", label: ">" },
          { value: "gte", label: "≥" },
          { value: "lt", label: "<" },
          { value: "lte", label: "≤" },
        ],
      },
      {
        label: "List",
        operators: [
          { value: "in", label: "In list" },
          { value: "not_in", label: "Not in list" },
        ],
      },
    ];

    return groups
      .map((group) => ({
        ...group,
        operators: group.operators.filter((operator) => allowed.has(operator.value)),
      }))
      .filter((group) => group.operators.length > 0);
  };

  proto.ruleEntitySearchResults = function (query = null, limit = 12) {
    const normalizedQuery = String(
      query ?? this._roomRulesDraft?.entity_id ?? ""
    ).trim().toLowerCase();

    if (normalizedQuery.length < 2) {
      return [];
    }

    const entries = Object.entries(this.hass?.states ?? {})
      .map(([entityId, entityState]) => {
        const friendlyName = String(entityState?.attributes?.friendly_name ?? "").trim();
        const score = scoreEntitySearch(entityId, friendlyName, normalizedQuery);
        if (score <= 0) return null;

        return {
          entity_id: entityId,
          friendly_name: friendlyName,
          state: entityState?.state ?? null,
          domain: entityId.split(".")[0] ?? "",
          score,
        };
      })
      .filter(Boolean)
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return a.entity_id.localeCompare(b.entity_id);
      });

    return entries.slice(0, Math.max(1, Number(limit) || 12));
  };

  /* =========================================================
     RULE LIST HELPERS (used by renderers)
     ========================================================= */

  /**
   * Returns all rules for the given room on the active map.
   */
  proto.roomRulesForRoom = function (roomId) {
    const rooms = this.getRoomsForActiveMap?.() ?? [];
    const room = rooms.find((r) => String(r.id) === String(roomId));
    if (!room) return [];
    return Array.isArray(room.rules) ? room.rules : [];
  };

  /**
   * Build a plain-text summary of a rule condition for display
   * in the rule list (e.g. "is ON", "= home", "> 25").
   */
  proto.ruleConditionSummary = function (rule) {
    const op = rule.operator ?? "";
    const value = formatRuleValueSummary(rule.value);

    switch (op) {
      case "is_on":      return "is ON";
      case "is_off":     return "is OFF";
      case "exists":     return "exists";
      case "missing":    return "is missing";
      case "equals":     return `= ${value ?? ""}`;
      case "not_equals": return `!= ${value ?? ""}`;
      case "gt":         return `> ${value ?? ""}`;
      case "gte":        return `>= ${value ?? ""}`;
      case "lt":         return `< ${value ?? ""}`;
      case "lte":        return `<= ${value ?? ""}`;
      case "in":         return `in [${value ?? ""}]`;
      case "not_in":     return `not in [${value ?? ""}]`;
      default:           return op;
    }
  };

  /**
   * Build a plain-text summary of a rule's effect for display.
   */
  proto.ruleEffectSummary = function (rule) {
    if (rule.kind === "blocker") {
      const reason = rule.effect?.reason;
      return reason ? `Exclude - ${reason}` : "Exclude room";
    }

    const changes = rule.effect?.changes ?? {};
    const parts = [];
    if (changes.clean_mode) parts.push(`mode: ${changes.clean_mode}`);
    if (changes.fan_speed) parts.push(`fan: ${changes.fan_speed}`);
    if (changes.water_level) parts.push(`water: ${changes.water_level}`);
    if (changes.clean_intensity) parts.push(`intensity: ${changes.clean_intensity}`);
    if (changes.clean_passes != null) parts.push(`passes: ${changes.clean_passes}`);
    if (changes.edge_mopping != null) parts.push(`edge mop: ${changes.edge_mopping ? "on" : "off"}`);
    return parts.length ? parts.join(", ") : "Modify settings";
  };
}
