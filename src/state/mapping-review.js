// Card-local state for the Map Bounds Review view: snapshot, filter, and pending action tracking.

const BOUNDS_FILTERS = { ALL: "all", HAS_BOUNDS: "has_bounds", NO_BOUNDS: "no_bounds" };

export function applyMappingReviewState(proto) {
  proto._ensureMappingReviewState = function () {
    if (!this._mappingReviewState) {
      this._mappingReviewState = {
        snapshot:            null,
        filter:              BOUNDS_FILTERS.ALL,
        pendingClearRoomId:  null,
        pendingJobAction:    null, // { roomId, jobIndex, action: "exclude"|"restore" }
        pendingRebuildRoomId: null,
      };
    }
    return this._mappingReviewState;
  };

  proto.mappingBoundsSnapshot = function () {
    return this._ensureMappingReviewState().snapshot ?? null;
  };

  proto.setMappingBoundsSnapshot = function (snapshot) {
    this._ensureMappingReviewState().snapshot = snapshot ?? null;
  };

  proto.mappingBoundsFilter = function () {
    return this._ensureMappingReviewState().filter;
  };

  proto.setMappingBoundsFilter = function (filter) {
    const s = this._ensureMappingReviewState();
    s.filter = Object.values(BOUNDS_FILTERS).includes(filter) ? filter : BOUNDS_FILTERS.ALL;
  };

  proto.beginMappingBoundsClear = function (roomId) {
    this._ensureMappingReviewState().pendingClearRoomId = String(roomId);
  };

  proto.endMappingBoundsClear = function () {
    this._ensureMappingReviewState().pendingClearRoomId = null;
  };

  proto.isMappingBoundsClearPending = function (roomId) {
    return this._ensureMappingReviewState().pendingClearRoomId === String(roomId);
  };

  proto.beginMappingJobAction = function (roomId, jobIndex, action) {
    this._ensureMappingReviewState().pendingJobAction = { roomId: String(roomId), jobIndex: Number(jobIndex), action };
  };

  proto.endMappingJobAction = function () {
    this._ensureMappingReviewState().pendingJobAction = null;
  };

  proto.isMappingJobActionPending = function (roomId, jobIndex) {
    const p = this._ensureMappingReviewState().pendingJobAction;
    return p !== null && p.roomId === String(roomId) && p.jobIndex === Number(jobIndex);
  };

  proto.beginMappingRebuild = function (roomId) {
    this._ensureMappingReviewState().pendingRebuildRoomId = String(roomId);
  };

  proto.endMappingRebuild = function () {
    this._ensureMappingReviewState().pendingRebuildRoomId = null;
  };

  proto.isMappingRebuildPending = function (roomId) {
    return this._ensureMappingReviewState().pendingRebuildRoomId === String(roomId);
  };

  // Returns only the stable filter values; the chip labels are localized at the
  // render site (`mapping_review.filter_*`), so no English text lives in state.
  proto.mappingBoundsFilterOptions = function () {
    return [
      { value: BOUNDS_FILTERS.ALL },
      { value: BOUNDS_FILTERS.HAS_BOUNDS },
      { value: BOUNDS_FILTERS.NO_BOUNDS },
    ];
  };
}
