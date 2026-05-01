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

    const allRooms = this.getRoomsForMap(room.mapId);
    const selectedIds = new Set(
      this._normalizeRoomReferenceList(this.roomAccessFields().grants_access_to)
    );

    // Build map of target -> claimant for all OTHER rooms (excluding this one).
    const claimedByOther = this._buildClaimedTargetMap(allRooms, String(room.id));

    const rooms = allRooms
      .filter((entry) => {
        if (String(entry.id) === String(room.id)) return false;
        if (entry.isDockRoom) return false;

        const id = String(entry.id);
        const claimedBy = claimedByOther.get(id);
        // Hide rooms claimed by another room unless already selected by this room.
        return selectedIds.has(id) || !claimedBy;
      })
      .map((entry) => ({
        id: String(entry.id),
        name: entry.name,
        missing: false,
        available: true,
        claimedBy: null,
      }));

    const knownRoomIds = new Set(rooms.map((entry) => entry.id));
    const missingSelections = Array.from(selectedIds)
      .filter((entry) => !knownRoomIds.has(String(entry)))
      .map((entry) => ({
        id: String(entry),
        name: `Missing Room ${entry}`,
        missing: true,
        available: true,
        claimedBy: null,
      }));

    return [...rooms, ...missingSelections];
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
