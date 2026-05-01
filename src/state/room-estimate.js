/**
 * ============================================================
 * STATE: ROOM ESTIMATE MODAL
 * ============================================================
 *
 * PURPOSE
 * -------
 * Owns the lightweight state for the queue-chip estimate modal.
 *
 * This keeps the estimate-detail surface separate from the room
 * editor so queue interactions can stay quick and predictable.
 *
 * ============================================================
 */

export function applyRoomEstimateState(proto) {
  proto.openRoomEstimateModal = function (roomId, mapId) {
    const room = this.getRoomsForMap(mapId).find(
      (entry) =>
        String(entry.id) === String(roomId) &&
        String(entry.mapId) === String(mapId)
    );

    if (!room) return;

    this._roomEstimateModalRoomId = room.id;
    this._roomEstimateModalMapId = room.mapId;
  };

  proto.closeRoomEstimateModal = function () {
    this._roomEstimateModalRoomId = null;
    this._roomEstimateModalMapId = null;
  };

  proto.isRoomEstimateModalOpen = function () {
    return this._roomEstimateModalRoomId != null;
  };

  proto.activeRoomEstimateRoom = function () {
    if (!this._roomEstimateModalRoomId || !this._roomEstimateModalMapId) return null;

    return this.getRoomsForMap(this._roomEstimateModalMapId).find(
      (room) =>
        String(room.id) === String(this._roomEstimateModalRoomId) &&
        String(room.mapId) === String(this._roomEstimateModalMapId)
    ) ?? null;
  };

  proto.activeRoomEstimateDetails = function () {
    const room = this.activeRoomEstimateRoom?.();
    if (!room) return null;

    const roomId = String(room.id);
    const timeline = Array.isArray(this.learningRoomTimeline?.())
      ? this.learningRoomTimeline()
      : [];

    const entry = timeline.find((item) => String(item?.room_id) === roomId) ?? null;
    const roomEstimate = this.roomEstimateForRoom?.(room.id) ?? null;
    const plannedWaterRoom =
      this.dashboardPlannedWaterRoomForRoom?.(room.id, room.slug) ?? null;

    return {
      room,
      entry,
      roomEstimate,
      plannedWaterRoom,
      confidenceBreakpoint:
        entry?.confidence_breakpoint ??
        roomEstimate?.confidence_breakpoint ??
        null,
      confidenceLabel:
        entry?.confidence_label ??
        roomEstimate?.confidence_label ??
        null,
    };
  };
}
