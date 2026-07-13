// All side-effecting actions for the Rooms view: toggle, start, clear, save fields, and ordering.

import {
  DOMAIN,
  SERVICE_GET_START_STATUS,
  SERVICE_START_SELECTED_ROOMS,
  SERVICE_CLEAR_QUEUE,
  SERVICE_UPDATE_ROOM_FIELDS,
  SERVICE_ADD_QUEUE_BREAK,
  SERVICE_ADD_QUEUE_ZONE,
  SERVICE_CLEAR_QUEUE_BREAKS,
  SERVICE_REMOVE_QUEUE_BREAK,
  SERVICE_SET_QUEUE_BREAKS,
} from "../constants.js";
import { normalizeHex } from "../cards/map-room-color.js";

export function applyRoomsActions(proto) {
  /**
   * Toggle one room's switch entity on or off.
   * @param {string} mapId
   * @param {number} roomId
   * @param {boolean} currentEnabled - current state; toggled to its opposite
   */
  proto.toggleRoomEnabled = async function (mapId, roomId, currentEnabled) {
    // Hand-editing the room selection diverges from any applied stepped profile, so a
    // subsequent Start runs the FLAT selection, not the profile's steps.
    this.state.clearAppliedRunProfile?.();
    const switchEntityId = this.state.findRoomSwitchEntityId(mapId, roomId);

    if (!switchEntityId) {
      console.warn(
        `[eufy-vacuum-command-center] Switch entity not found for room ${roomId} on map ${mapId}. ` +
          `Check that eufy_vacuum switch entities are loaded in HA. ` +
          `Available switches:`,
        this.state._findRoomSwitchEntities().map((s) => s.entityId),
      );
      return;
    }

    await this.callHA(currentEnabled ? "turn_off" : "turn_on", switchEntityId);
  };

  /**
   * Execute the full start flow: confirm start status, call start_selected_rooms,
   * run learning estimate, and enter active job mode.
   * RULES:
   * - run_learning_estimate is called after start succeeds
   * - start_selected_rooms must NOT use returnResponse=true (HA rejects it for non-response-capable actions)
   * @param {object} [options]
   * @param {boolean} [options.confirmReducedRun]
   * @param {string}  [options.confirmToken]
   * @returns {Promise<object>} start response or blocking status
   */
  proto.startCleaning = async function (options = {}) {
    const vacuumEntityId = this.state.vacuumEntityId();
    const mapId = this.state.activeMapId();
    if (!vacuumEntityId || !mapId) return;

    const payload = {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
    };

    // ------------------------------------------------------
    // 1) Confirm start status against backend truth
    // ------------------------------------------------------
    const startStatusResult = await this.callService(
      DOMAIN,
      SERVICE_GET_START_STATUS,
      payload,
      true,
    );

    const startStatus = startStatusResult?.response ?? startStatusResult;
    if (startStatus) {
      this.state.setStartStatus(startStatus);
    }

    if (startStatus?.blocked) {
      this.state.clearStartConfirmation();
      return startStatus;
    }

    // ------------------------------------------------------
    // 2) Start selected rooms
    // ------------------------------------------------------
    const startRequest = {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
    };

    if (options.confirmReducedRun) {
      startRequest.confirm_reduced_run = true;
    }

    if (options.confirmToken) {
      startRequest.confirm_token = options.confirmToken;
    }

    // Opt-in strict room order (per-run): clean one room at a time in the queue
    // order on brands that otherwise path-optimize. No-op for order-honoring
    // brands (the backend gates it on honors_clean_order). Off by default.
    if (this.state.strictOrder?.()) {
      startRequest.strict_order = true;
    }

    // Fresh trace for this clean (state.resetLiveTrail) — a whole multi-room run is ONE trace;
    // mid-clean docks (recharge / strict-order return) don't call this, so they never split it.
    this.state.resetLiveTrail?.();
    const startResult = await this.callService(
      DOMAIN,
      SERVICE_START_SELECTED_ROOMS,
      startRequest,
      false,
    );

    const startResponse = startResult?.response ?? startResult ?? {};

    if (
      startResponse?.started === false &&
      startResponse?.reason === "confirmation_required"
    ) {
      this.state.setStartConfirmation(
        startResponse?.preflight ?? startStatus?.preflight ?? startStatus ?? null,
        startResponse?.confirm_token ?? null,
      );
      return startResponse;
    }

    if (startResponse?.started === false) {
      this.state.clearStartConfirmation();
      return startResponse;
    }

    this.state.clearStartConfirmation();
    this.state.clearCancelRunConfirmation();

    // ------------------------------------------------------
    // 3) Run learning estimate and store the full payload
    // ------------------------------------------------------
    const estimate = await this.runLearningEstimate({
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
      current_battery: this.state.batteryLevel(),
    });

    this.state.setLearningEstimate(estimate ?? null);

    // Reset any stale live-job fields before a new run starts.
    this.state.setLearningReanchored(null);
    this.state.setLearningCompletedRooms([]);
    this.state.setLearningNextRoom(null);
    this.state.setLearningJobActive(false);

    // ------------------------------------------------------
    // 4) Enter active learning-job mode
    // ------------------------------------------------------
    this.state.beginLearningJob();

    // Resolve the first banner state immediately from the
    // initial anchor when an estimate exists.
    if (this.state.learningReanchored()) {
      const nextRoom = await this.getNextLearningRoom({
        reanchored_estimate: this.state.learningReanchored(),
      });

      this.state.setLearningNextRoom(
        nextRoom && Object.keys(nextRoom).length ? nextRoom : {},
      );
    }

    return startResponse ?? { started: true };
  };

  /**
   * Enable only the missed rooms and disable all others so the user can start a retry.
   * Does not start the job — leaves that to the user via the normal start button.
   * @param {number[]} missedRoomIds - from the incomplete run log
   */
  proto.retryMissedRooms = async function (missedRoomIds) {
    if (!Array.isArray(missedRoomIds) || missedRoomIds.length === 0) return;

    const rooms = this.state.getRoomsForActiveMap();
    const missedSet = new Set(missedRoomIds.map(String));

    await Promise.all(
      rooms.map((r) => {
        const isMissed = missedSet.has(String(r.id));
        if (isMissed && !r.enabled) {
          return this.toggleRoomEnabled(r.mapId, r.id, false); // enable
        }
        if (!isMissed && r.enabled) {
          return this.toggleRoomEnabled(r.mapId, r.id, true);  // disable
        }
        return Promise.resolve();
      })
    );
  };

  /** Disable all enabled rooms and call clear_queue on the backend. */
  proto.clearQueue = async function () {
    const vacuumEntityId = this.state.vacuumEntityId();
    const mapId = this.state.activeMapId();
    if (!vacuumEntityId || !mapId) return;

    const rooms = this.state.getRoomsForActiveMap();
    await Promise.all(
      rooms
        .filter((r) => r.enabled)
        .map((r) => this.toggleRoomEnabled(r.mapId, r.id, true)),
    );

    await this.callService(DOMAIN, SERVICE_CLEAR_QUEUE, {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
    });

    this.state.clearStartConfirmation();
    this.state.clearCancelRunConfirmation();

    // Queue invalidation should clear queue-derived learning
    // state while preserving queue-independent helper chips.
    this.state.clearLearningJobContext();
  };

  /**
   * Add a charge/wait break to the live queue, turning it into a stepped run.
   * Defaults to a mid-queue slot (the backend clamps to an interior position);
   * charge defaults to 90%, wait to 20 min. Same pattern any future step type
   * (empty_dust, zone) will reuse — just another break_type.
   */
  proto.addQueueBreak = async function (breakType, opts = {}) {
    const vacuumEntityId = this.state.vacuumEntityId();
    const mapId = this.state.activeMapId();
    if (!vacuumEntityId || !mapId) return;
    const enabledCount = this.state.enabledRoomCount?.() ?? 0;
    const data = {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
      break_type: breakType,
      after_index: opts.afterIndex ?? Math.max(1, Math.floor(enabledCount / 2)),
    };
    if (breakType === "charge_wait") {
      data.target_battery_percent = opts.targetBatteryPercent ?? 90;
    } else {
      data.wait_minutes = opts.waitMinutes ?? 20;
    }
    await this.callService(DOMAIN, SERVICE_ADD_QUEUE_BREAK, data);
  };

  /**
   * Insert a zone step — clean the named saved zones together in one phase, at a
   * default mid-queue slot (backend clamps to an interior position). The same
   * inserted-step path as a break, so it reorders/removes through the P3b machinery.
   */
  proto.addQueueZone = async function (zoneIds, opts = {}) {
    const vacuumEntityId = this.state.vacuumEntityId();
    const mapId = this.state.activeMapId();
    if (!vacuumEntityId || !mapId) return;
    const ids = (Array.isArray(zoneIds) ? zoneIds : []).map(String).filter(Boolean);
    if (!ids.length) return;
    const enabledCount = this.state.enabledRoomCount?.() ?? 0;
    await this.callService(DOMAIN, SERVICE_ADD_QUEUE_ZONE, {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
      after_index: opts.afterIndex ?? Math.max(1, Math.floor(enabledCount / 2)),
      zone_ids: ids,
    });
  };

  /** Remove all queue breaks — the queue drops back to a flat clean. */
  proto.clearQueueBreaks = async function () {
    const vacuumEntityId = this.state.vacuumEntityId();
    const mapId = this.state.activeMapId();
    if (!vacuumEntityId || !mapId) return;
    await this.callService(DOMAIN, SERVICE_CLEAR_QUEUE_BREAKS, {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
    });
  };

  /** Remove a single break by its index in the ordered break list. */
  proto.removeQueueBreak = async function (index) {
    const vacuumEntityId = this.state.vacuumEntityId();
    const mapId = this.state.activeMapId();
    if (!vacuumEntityId || !mapId) return;
    await this.callService(DOMAIN, SERVICE_REMOVE_QUEUE_BREAK, {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
      index,
    });
  };

  /**
   * Replace ALL queue breaks in one call — the primitive behind reordering (from the
   * steps order adapter's persist) and param-edit. `breaks` is the full desired list of
   * {after_index, break_type, target_battery_percent?|wait_minutes?}; the backend clamps
   * and re-sorts.
   */
  proto.persistQueueBreaks = async function (breaks) {
    const vacuumEntityId = this.state.vacuumEntityId();
    const mapId = this.state.activeMapId();
    if (!vacuumEntityId || !mapId) return;
    await this.callService(DOMAIN, SERVICE_SET_QUEUE_BREAKS, {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
      breaks: Array.isArray(breaks) ? breaks : [],
    });
  };

  /**
   * Edit one break's value (charge % or wait minutes). The queue is wholesale, so read the
   * current breaks off the snapshot, swap the one field, and resend the full list.
   */
  proto.updateQueueBreakParam = async function (breakIndex, { targetBatteryPercent, waitMinutes } = {}) {
    const current = this.state.dashboardSnapshot?.()?.queue_steps?.breaks;
    if (!Array.isArray(current)) return;
    const breaks = current.map((entry, i) => {
      const step = entry?.step || {};
      const out = {
        after_index: entry?.after_index,
        break_type: step.type,
      };
      if (step.type === "charge_wait") {
        out.target_battery_percent =
          i === breakIndex && targetBatteryPercent != null
            ? targetBatteryPercent
            : step.target_battery_percent;
      } else if (step.type === "wait") {
        out.wait_minutes =
          i === breakIndex && waitMinutes != null ? waitMinutes : step.wait_minutes;
      } else if (step.type === "zone") {
        // A zone has no editable value here, but its ids must survive a wholesale resend
        // (editing a DIFFERENT break rebuilds the full list) or the backend drops the zone.
        out.zone_ids = step.zone_ids;
      }
      return out;
    });
    await this.persistQueueBreaks(breaks);
  };

  /** Enable all rooms that are currently disabled. */
  proto.selectAllRooms = async function () {
    const rooms = this.state.getRoomsForActiveMap();
    await Promise.all(
      rooms
        .filter((r) => !r.enabled)
        .map((r) => this.toggleRoomEnabled(r.mapId, r.id, false)),
    );
  };

  /**
   * Force a fresh room-estimate pull.
   * WHY: an explicit save is a strong user action; chips must not show stale data after it.
   */
  proto.refreshRoomLearningEstimates = async function (options = {}) {
  const vacuumEntityId = options.vacuum_entity_id ?? this.state.vacuumEntityId();
  const mapId = options.map_id ?? this.state.activeMapId();
  if (!vacuumEntityId || !mapId) return null;

  const result = await this.callService(
    DOMAIN,
    "get_room_learning_estimates",
    {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
    },
    true,
  );

  const response = result?.response ?? result ?? null;
  if (response) {
    this.state.setRoomEstimates?.(response);
  }

  return response;
};

  /**
   * Persist room field overrides and refresh the room estimate cache.
   * RULES: null optional fields (water_level, profile_name) must be omitted from the
   *        payload — sending null causes HA service schema validation failures.
   * @param {number} roomId
   * @param {object} fields
   * @returns {Promise<object|null>}
   */
  proto.updateRoomFields = async function (roomId, fields = {}) {
    const vacuumEntityId = this.state.vacuumEntityId();
    const mapId = this.state.activeMapId();
    if (!vacuumEntityId || !mapId || roomId == null) return null;

    // Hand-editing a room's fields diverges from any applied stepped profile, so a
    // subsequent Start runs the FLAT just-edited selection, not the profile's steps.
    // (Shared path for saveRoomEditor / applyRoomProfile / saveRoomTransition / saveRoomAccess.)
    this.state.clearAppliedRunProfile?.();

    const cleanedFields = { ...fields };

    if (
      cleanedFields.water_level == null ||
      String(cleanedFields.water_level).trim() === ""
    ) {
      delete cleanedFields.water_level;
    }

    if (
      cleanedFields.profile_name == null ||
      String(cleanedFields.profile_name).trim() === ""
    ) {
      delete cleanedFields.profile_name;
    }

    const payload = {
      vacuum_entity_id: vacuumEntityId,
      map_id: mapId,
      room_id: roomId,
      ...cleanedFields,
    };

    const result = await this.callService(
      DOMAIN,
      SERVICE_UPDATE_ROOM_FIELDS,
      payload,
      true,
    );

    const response = result?.response ?? result ?? null;

    if (response) {
      try {
        await this.refreshRoomLearningEstimates({
          vacuum_entity_id: vacuumEntityId,
          map_id: mapId,
        });
      } catch (err) {
        console.warn(
          "[eufy-vacuum-command-center] Failed to refresh room learning estimates after save",
          err,
        );
      }
    }

    return response;
  };

  /** Persist the current room editor working fields via updateRoomFields. */
  proto.saveRoomEditor = async function () {
    const room = this.state.activeEditorRoom?.();
    const fields = this.state.editorFields?.();
    if (!room || !fields) return null;

    const payload = {
      clean_mode: fields.clean_mode,
      fan_speed: fields.fan_speed,
      clean_intensity: fields.clean_intensity,
      clean_passes: fields.clean_passes,
    };

    if (
      this.state.showWaterLevel() &&
      fields.water_level != null &&
      String(fields.water_level).trim() !== ""
    ) {
      payload.water_level = fields.water_level;
    }

    if (this.state.showEdgeMopping()) {
      payload.edge_mopping = Boolean(fields.edge_mopping);
    }

    // Per-room map fill override. Always sent (canonical hex, or null to clear) — the editor is the
    // source of truth for this room's color, so a reset must persist as an explicit clear. The
    // backend only writes color when the key is present, so this never clobbers other callers.
    payload.color = normalizeHex(fields.color);

    return this.updateRoomFields(room.id, payload);
  };

  /**
   * Persist a named preset profile selection for a room.
   * @param {number} roomId
   * @param {string} profileName
   */
  proto.applyRoomProfile = async function (roomId, profileName) {
    return this.updateRoomFields(roomId, {
      profile_name: profileName,
    });
  };

  /** Persist the is_transition flag for a room. */
  proto.saveRoomTransition = async function (roomId, isTransition) {
    return this.updateRoomFields(roomId, {
      is_transition: isTransition,
    });
  };

  /** Persist access graph fields (grants_access_to, is_dock_room) for a room. */
  proto.saveRoomAccess = async function (roomId, grantsAccessTo, isDockRoom) {
    return this.updateRoomFields(roomId, {
      grants_access_to: grantsAccessTo,
      is_dock_room:     isDockRoom,
    });
  };

  /** Send the vacuum back to base and clear any pending start/cancel confirmation state. */
  proto.cancelActiveRun = async function () {
    const vacuumEntityId = this.state.vacuumEntityId();
    if (!vacuumEntityId) return;

    await this.callService("vacuum", "return_to_base", {
      entity_id: vacuumEntityId,
    });

    this.state.clearCancelRunConfirmation?.();
    this.state.clearStartConfirmation?.();
  };

  /**
   * Write new order values to the per-room HA number entities.
   * WHY number entities: keeps ordering visible and editable from the integration side.
   * @param {object[]} rooms - ordered room list
   */
  proto.persistRoomOrdering = async function (rooms) {
    const mapId = this.state.activeMapId();
    if (!mapId || !Array.isArray(rooms)) return;

    // Reordering rooms diverges from any applied stepped profile, so a subsequent Start
    // runs the FLAT just-reordered selection, not the profile's saved step sequence.
    this.state.clearAppliedRunProfile?.();

    await Promise.all(
      rooms.map(async (room, index) => {
        const entityId = this.state.findRoomOrderNumberEntityId(mapId, room.id);
        if (!entityId) return;

        await this.callService("number", "set_value", {
          entity_id: entityId,
          value: index + 1,
        });
      }),
    );
  };
}