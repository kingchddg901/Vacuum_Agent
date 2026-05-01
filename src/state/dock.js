// Card-local state for dock actions, pending action tracking, and pause-timeout settings.

export function applyDockState(proto) {
  proto._ensureDockState = function () {
    if (!this._dockState) {
      this._dockState = {
        actionStatus: null,
        pendingAction: "",
        pauseTimeoutSettings: null,
      };
    }

    return this._dockState;
  };

  proto.setDockActionStatus = function (payload) {
    this._ensureDockState().actionStatus = payload ?? null;
  };

  proto.dockActionStatus = function () {
    return this._ensureDockState().actionStatus ?? null;
  };

  proto.beginDockAction = function (action) {
    this._ensureDockState().pendingAction = String(action ?? "");
  };

  proto.endDockAction = function () {
    this._ensureDockState().pendingAction = "";
  };

  proto.pendingDockAction = function () {
    return this._ensureDockState().pendingAction ?? "";
  };

  proto.isDockActionPending = function (action) {
    return this.pendingDockAction() === String(action ?? "");
  };

  proto.dockActionGate = function (action) {
    return this.dockActionStatus()?.actions?.[action] ?? null;
  };

  proto.dockActionAllowed = function (action) {
    const gate = this.dockActionGate(action);
    return gate?.allowed === true;
  };

  proto.dockStatus = function () {
    return this.dockActionStatus()?.dock_status
      ?? this.dashboardUpkeep?.()?.dock_status
      ?? null;
  };

  proto.dockStatusLabel = function () {
    return this.dockActionStatus()?.dock_status_label
      ?? this.dashboardUpkeep?.()?.dock_status_label
      ?? null;
  };

  proto.dockLifecycleState = function () {
    return this.dockActionStatus()?.lifecycle_state ?? null;
  };

  proto.dockLifecycleStateLabel = function () {
    return this.dockActionStatus()?.lifecycle_state_label ?? null;
  };

  proto.dockTaskStatus = function () {
    return this.dockActionStatus()?.task_status
      ?? this.dockActionStatus()?.active_job_status
      ?? null;
  };

  proto.dockTaskStatusLabel = function () {
    return this.dockActionStatus()?.task_status_label
      ?? this.dockActionStatus()?.active_job_status_label
      ?? null;
  };

  proto.isDocked = function () {
    return this.dockActionStatus()?.docked === true;
  };

  proto.stationWaterLabel = function () {
    return this.dashboardUpkeep?.()?.station_water_label ?? null;
  };

  proto.setPauseTimeoutSettings = function (payload) {
    this._ensureDockState().pauseTimeoutSettings = payload ?? null;
  };

  proto.pauseTimeoutSettings = function () {
    return this._ensureDockState().pauseTimeoutSettings ?? null;
  };

  proto.pauseTimeoutMinutesDefault = function () {
    const payload = this.pauseTimeoutSettings?.();
    const minutes = Number(payload?.pause_timeout_minutes_default);
    return Number.isFinite(minutes) ? minutes : null;
  };
}
