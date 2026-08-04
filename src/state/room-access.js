/**
 * ============================================================
 * STATE: ROOM ACCESS MODAL
 * ============================================================
 *
 * PURPOSE
 * -------
 * Owns the lightweight working state for the room access modal.
 *
 * This file keeps access-graph editing separate from the main
 * room editor so infrequent advanced changes do not clutter the
 * everyday cleaning-settings modal.
 *
 * ============================================================
 */

import {
  graphFromRooms,
  offerableTargets,
  withEdges,
} from "./access-graph-model.js";

export function applyRoomAccessState(proto) {

  proto.openRoomAccess = function (roomId, mapId) {
    const room = this.getRoomsForMap(mapId).find(
      (entry) =>
        String(entry.id) === String(roomId) &&
        String(entry.mapId) === String(mapId)
    );

    if (!room) return;

    this._roomAccessRoomId = room.id;
    this._roomAccessMapId = room.mapId;
    this._roomAccessFields = {
      is_dock_room: room.isDockRoom ?? false,
      grants_access_to: [...(room.grantsAccessTo ?? [])],
    };
    this._roomAccessSaveError = null;
  };

  proto.closeRoomAccess = function () {
    this._roomAccessRoomId = null;
    this._roomAccessMapId = null;
    this._roomAccessFields = null;
    this._roomAccessSaveError = null;
  };

  proto.isRoomAccessOpen = function () {
    return this._roomAccessRoomId != null;
  };

  proto.activeAccessRoom = function () {
    if (!this._roomAccessRoomId || !this._roomAccessMapId) return null;

    return this.getRoomsForMap(this._roomAccessMapId).find(
      (room) =>
        String(room.id) === String(this._roomAccessRoomId) &&
        String(room.mapId) === String(this._roomAccessMapId)
    ) ?? null;
  };

  proto.roomAccessFields = function () {
    return this._roomAccessFields ?? { grants_access_to: [] };
  };

  proto.setRoomAccessSaveError = function (error) {
    this._roomAccessSaveError = error ?? null;
  };

  proto.roomAccessSaveError = function () {
    return this._roomAccessSaveError ?? null;
  };

  proto.accessEditableRooms = function () {
    const room = this.activeAccessRoom();
    if (!room) return [];

    const rooms = this.getRoomsForMap(room.mapId);

    // The modal edits ONE room against stored state, so the snapshot it asks
    // about is "the graph on disk, with this room's unsaved draft overlaid".
    // The builder (Wave C) will pass its whole-map draft to the same function —
    // that difference is the entire reason the question moved out of here and
    // into a pure model over an explicit snapshot.
    const graph = withEdges(
      graphFromRooms(rooms),
      room.id,
      this.roomAccessFields().grants_access_to
    );

    return offerableTargets(rooms, graph, room.id);
  };

  proto.accessInboundRooms = function () {
    const room = this.activeAccessRoom();
    if (!room) return [];

    const allRooms = this.getRoomsForMap(room.mapId);
    const targetId = String(room.id);

    // requiresAccessFrom is never stored on entities — derive it by finding
    // rooms whose grantsAccessTo contains this room's id.
    return allRooms
      .filter((candidate) =>
        this._normalizeRoomReferenceList(candidate.grantsAccessTo).includes(targetId)
      )
      .map((candidate) => ({
        id: String(candidate.id),
        name: candidate.name,
        missing: false,
      }));
  };

  proto.toggleRoomAccessTarget = function (targetRoomId) {
    if (!this._roomAccessFields) return;

    const target = String(targetRoomId ?? "").trim();
    if (!target) return;

    const current = new Set(this._normalizeRoomReferenceList(
      this._roomAccessFields.grants_access_to
    ));

    if (current.has(target)) {
      current.delete(target);
    } else {
      current.add(target);
    }

    this._roomAccessFields = {
      ...this._roomAccessFields,
      grants_access_to: Array.from(current),
    };

    this._roomAccessSaveError = null;
  };

  proto.toggleIsDockRoomField = function () {
    if (!this._roomAccessFields) return;

    this._roomAccessFields = {
      ...this._roomAccessFields,
      is_dock_room: !this._roomAccessFields.is_dock_room,
    };

    this._roomAccessSaveError = null;
  };

  proto.roomAccessValidation = function () {
    const room = this.activeAccessRoom();
    if (!room) {
      return {
        valid: false,
        issues: [{
          code: "missing_room",
          scope: "card",
          params: {},
          // A6-AGX-6 checked this literal and left it: it is the FALLBACK, not the
          // rendered string. `code` + `scope: "card"` resolves to
          // room_access.issue.card.missing_room in all 18 locales (A6-AGX-4), and
          // accessIssueLabel only reaches `message` when it has no translate fn.
          message: "No room is selected for access editing.",
        }],
        normalizedGrantsAccessTo: [],
      };
    }

    // Dock room has no dependency requirements — skip all graph validation.
    if (this.roomAccessFields().is_dock_room) {
      return {
        valid: true,
        issues: [],
        normalizedGrantsAccessTo: [],
      };
    }

    return this.validateRoomAccessUpdate(
      room.mapId,
      room.id,
      this.roomAccessFields().grants_access_to ?? []
    );
  };
}
