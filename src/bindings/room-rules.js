/**
 * ============================================================
 * BINDINGS: ROOM RULES
 * ============================================================
 *
 * Wires all interactions in the Room Rules view — tab selection,
 * rule create/edit/delete, field inputs, and save flow.
 *
 * ============================================================
 */

/**
 * Mix room rules binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyRoomRulesBindings(proto) {
  /**
   * Bind the Room Rules view on the shadow root.
   */
  proto._bindRoomRules = function () {
    const root = this.card.shadowRoot;
    if (!root) return;

    /* -------------------------------------------------------
       SUB-TAB SELECTION
       ------------------------------------------------------- */
    root.querySelectorAll("[data-action='set-room-rules-tab']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const roomId = btn.dataset.roomId;
        if (!roomId) return;
        this.card._state.setRoomRulesActiveRoom?.(roomId);
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       OPEN NEW RULE FORM
       ------------------------------------------------------- */
    root.querySelectorAll("[data-action='open-new-rule']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.openNewRuleDraft?.();
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       EDIT EXISTING RULE
       ------------------------------------------------------- */
    root.querySelectorAll("[data-action='edit-rule']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const ruleId = btn.dataset.ruleId;
        const room = this.card._state.resolvedRoomRulesRoom?.();
        if (!room) return;

        const rules = this.card._state.roomRulesForRoom?.(room.id) ?? [];
        const rule = rules.find((entry) => String(entry.id) === String(ruleId));
        if (!rule) return;

        this.card._state.openEditRuleDraft?.(rule);
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       DELETE RULE
       ------------------------------------------------------- */
    root.querySelectorAll("[data-action='delete-rule']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const ruleId = btn.dataset.ruleId;
        const room = this.card._state.resolvedRoomRulesRoom?.();
        if (!room || !ruleId) return;

        const existing = this.card._state.roomRulesForRoom?.(room.id) ?? [];
        const updated = existing.filter((rule) => String(rule.id) !== String(ruleId));

        try {
          await this.card._actions.saveRoomRules?.(room.mapId, room.id, updated);
          await this.card.refreshDashboardSnapshot?.();
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Failed to delete rule:", err);
        }
      });
    });

    /* -------------------------------------------------------
       CANCEL RULE EDITOR
       ------------------------------------------------------- */
    root.querySelectorAll("[data-action='cancel-rule-editor']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.closeRulesDraft?.();
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       RULE FIELD CHIP CLICKS
       ------------------------------------------------------- */
    root.querySelectorAll("[data-rule-field]").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const field = btn.dataset.ruleField;
        let rawValue = btn.dataset.ruleValue;
        if (field == null) return;

        let value;
        if (rawValue === "") {
          value = null;
        } else if (rawValue === "true") {
          value = true;
        } else if (rawValue === "false") {
          value = false;
        } else if (field === "effect.changes.clean_passes") {
          value = Number(rawValue);
        } else {
          value = rawValue;
        }

        this.card._state.updateRuleDraftField?.(field, value);
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       RULE TEXT INPUTS
       ------------------------------------------------------- */
    root.querySelectorAll("[data-rule-input]").forEach((input) => {
      this.card._on(input, "input", () => {
        const field = input.dataset.ruleInput;
        if (!field) return;
        this.card._state.updateRuleDraftField?.(field, input.value);
      });
      this.card._on(input, "change", () => {
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       RULE SELECT INPUTS
       ------------------------------------------------------- */
    root.querySelectorAll("[data-rule-select]").forEach((input) => {
      this.card._on(input, "change", () => {
        const field = input.dataset.ruleSelect;
        if (!field) return;
        this.card._state.updateRuleDraftField?.(field, input.value || null);
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       RULE NUMBER INPUTS
       ------------------------------------------------------- */
    root.querySelectorAll("[data-rule-number-input]").forEach((input) => {
      this.card._on(input, "input", () => {
        const field = input.dataset.ruleNumberInput;
        if (!field) return;
        const rawValue = input.value;
        this.card._state.updateRuleDraftField?.(
          field,
          rawValue === "" ? null : Number(rawValue)
        );
      });
      this.card._on(input, "change", () => {
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       RULE MULTI-SELECT VALUE CHIPS
       ------------------------------------------------------- */
    root.querySelectorAll("[data-rule-multivalue]").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const rawValue = String(btn.dataset.ruleMultivalue ?? "").trim();
        if (!rawValue) return;

        const draft = this.card._state.roomRulesDraft?.();
        const current = _normalizeRuleListValue(draft?.value);
        const next = current.includes(rawValue)
          ? current.filter((entry) => entry !== rawValue)
          : [...current, rawValue];

        this.card._state.updateRuleDraftField?.("value", next);
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       RULE ENTITY SEARCH RESULTS
       ------------------------------------------------------- */
    root.querySelectorAll("[data-rule-entity-select]").forEach((btn) => {
      this.card._on(btn, "click", () => {
        const entityId = String(btn.dataset.ruleEntitySelect ?? "").trim();
        if (!entityId) return;
        this.card._state.updateRuleDraftField?.("entity_id", entityId);
        this.card._scheduleRender();
      });
    });

    /* -------------------------------------------------------
       SAVE RULE
       ------------------------------------------------------- */
    root.querySelectorAll("[data-action='save-rule']").forEach((btn) => {
      this.card._on(btn, "click", async () => {
        const state = this.card._state;
        if (!state.roomRulesDraftIsValid?.()) return;

        const room = state.resolvedRoomRulesRoom?.();
        const draft = state.roomRulesDraft?.();
        const mode = state.roomRulesDraftMode?.();
        if (!room || !draft) return;

        const descriptor = state.ruleEntityDescriptor?.(draft);
        const existing = state.roomRulesForRoom?.(room.id) ?? [];

        let updated;
        if (mode === "edit" && draft.id) {
          updated = existing.map((rule) =>
            String(rule.id) === String(draft.id)
              ? _buildRulePayload(draft, descriptor)
              : rule
          );
        } else {
          updated = [...existing, _buildRulePayload(draft, descriptor)];
        }

        try {
          const result = await this.card._actions.saveRoomRules?.(room.mapId, room.id, updated);

          if (result?.ok === false || result?.updated === false) {
            const message =
              result?.reason_detail ??
              result?.message ??
              result?.reason ??
              "The backend rejected this rule.";
            state.setRoomRulesSaveError?.(message);
            this.card._scheduleRender();
            return;
          }

          state.closeRulesDraft?.();
          await this.card.refreshDashboardSnapshot?.();
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Failed to save rule:", err);
          state.setRoomRulesSaveError?.("Failed to save rule. Check Home Assistant logs.");
          this.card._scheduleRender();
        }
      });
    });
  };
}

/* =========================================================
   HELPERS
   ========================================================= */

/**
 * Build the persisted rule payload from the current draft and entity descriptor.
 *
 * @param {object} draft - Current rule draft from state.
 * @param {object|null} descriptor - Entity descriptor for value-mode resolution.
 * @returns {object} Rule payload ready for the save service.
 */
function _buildRulePayload(draft, descriptor) {
  const payload = {
    entity_id: String(draft.entity_id ?? "").trim(),
    kind: draft.kind ?? "blocker",
    operator: draft.operator ?? "is_on",
    enabled: draft.enabled !== false,
    effect: {
      action: draft.kind === "modifier" ? "mutate" : "exclude",
      reason: String(draft.effect?.reason ?? "").trim() || null,
    },
  };

  if (draft.id) payload.id = draft.id;
  if (draft.label?.trim()) payload.label = draft.label.trim();

  if (!NO_VALUE_OPERATORS.has(payload.operator) && draft.value != null) {
    const serializedValue = _serializeRuleValue(draft.value, descriptor, payload.operator);
    if (Array.isArray(serializedValue) ? serializedValue.length : String(serializedValue).trim()) {
      payload.value = serializedValue;
    }
  }

  if (draft.kind === "modifier") {
    const changes = draft.effect?.changes ?? {};
    const cleaned = {};
    for (const [key, value] of Object.entries(changes)) {
      if (value == null) continue;
      if (key === "clean_passes") {
        const normalizedPasses = Number(value);
        if (normalizedPasses === 1 || normalizedPasses === 2) {
          cleaned[key] = normalizedPasses;
        }
        continue;
      }
      cleaned[key] = value;
    }
    payload.effect.changes = cleaned;

    // Rule fan-out: pass through the saved target list, normalized to
    // numeric IDs. Only set the field when non-empty so a brand-new
    // rule with no fan-out doesn't carry an empty array around the
    // wire — keeps stored rule shape clean.
    const fanOutRaw = Array.isArray(draft.fan_out_room_ids) ? draft.fan_out_room_ids : [];
    const fanOut = fanOutRaw.map(Number).filter((n) => Number.isFinite(n) && n > 0);
    if (fanOut.length) {
      payload.fan_out_room_ids = fanOut;
    }
  }

  return payload;
}

/**
 * Serialize a raw draft value to its wire format based on the operator's value mode.
 *
 * @param {*} value - Raw draft value.
 * @param {object|null} descriptor - Entity descriptor.
 * @param {string} operator - Rule operator (e.g. "equals", "in_list").
 * @returns {*} Serialized value.
 */
function _serializeRuleValue(value, descriptor, operator) {
  const valueMode = descriptor?.valueModeForOperator?.(operator) ?? "text";

  if (valueMode === "multi-select") {
    return _normalizeRuleListValue(value);
  }

  if (valueMode === "number") {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : value;
  }

  return value;
}

/**
 * Normalize a rule value to a trimmed string array.
 * Accepts existing arrays or comma-separated strings.
 *
 * @param {string|string[]|null|undefined} value - Raw value to normalize.
 * @returns {string[]} Normalized string array.
 */
function _normalizeRuleListValue(value) {
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

const NO_VALUE_OPERATORS = new Set(["is_on", "is_off", "exists", "missing"]);
