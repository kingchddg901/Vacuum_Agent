// Pure step-mutation helpers for the run-profile STEPS editor.
//
// A step is {type:"room_group", rooms:[...]} or {type:"charge_wait", target_battery_percent:1..100}.
// These own no card state: the editor holds a draft steps array and calls these to derive the NEXT
// array immutably (never mutate in place), then persists it via setRunProfileSteps. They are
// deliberately mode-agnostic — they reorder/insert/delete/retarget at the STEP level and never touch
// a room_group's internals, so they are unaffected by how per-room settings are modelled.
//
// sanitizeStepsForSave mirrors the backend normalize (profiles/manager.normalize_run_profile_steps)
// so the service receives already-clean data.

export const CHARGE_TARGET_MIN = 1;
export const CHARGE_TARGET_MAX = 100;
export const DEFAULT_CHARGE_TARGET = 95;

export function clampChargeTarget(value, fallback = DEFAULT_CHARGE_TARGET) {
  // null / undefined / "" mean "no input" -> fallback (Number() would coerce them to 0/NaN).
  if (value === null || value === undefined || value === "") return fallback;
  const n = Math.round(Number(value));
  if (!Number.isFinite(n)) return fallback;
  return Math.max(CHARGE_TARGET_MIN, Math.min(n, CHARGE_TARGET_MAX));
}

export function isRoomGroupStep(step) {
  return !!step && step.type === "room_group";
}

export function isChargeStep(step) {
  return !!step && step.type === "charge_wait";
}

export function isWaitStep(step) {
  return !!step && step.type === "wait";
}

export function isZoneStep(step) {
  return !!step && step.type === "zone";
}

export const WAIT_MIN_MINUTES = 1;
export const WAIT_MAX_MINUTES = 1440;
export const DEFAULT_WAIT_MINUTES = 30;

export function clampWaitMinutes(value, fallback = DEFAULT_WAIT_MINUTES) {
  if (value === null || value === undefined || value === "") return fallback;
  const n = Math.round(Number(value));
  if (!Number.isFinite(n)) return fallback;
  return Math.max(WAIT_MIN_MINUTES, Math.min(n, WAIT_MAX_MINUTES));
}

// Clamp an index into [0, max]; non-finite -> 0.
function clampIndex(index, max) {
  const n = Math.trunc(Number(index));
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(n, Math.max(0, max)));
}

// Move the step at fromIndex to toIndex (both clamped). Returns a fresh array.
export function moveStep(steps, fromIndex, toIndex) {
  const arr = Array.isArray(steps) ? [...steps] : [];
  if (!arr.length) return arr;
  const from = clampIndex(fromIndex, arr.length - 1);
  const to = clampIndex(toIndex, arr.length - 1);
  const [moved] = arr.splice(from, 1);
  arr.splice(to, 0, moved);
  return arr;
}

// Insert a charge_wait step at atIndex (0..length). Returns a fresh array.
export function insertChargeStep(steps, atIndex, target = DEFAULT_CHARGE_TARGET) {
  const arr = Array.isArray(steps) ? [...steps] : [];
  const at = clampIndex(atIndex, arr.length);
  arr.splice(at, 0, {
    type: "charge_wait",
    target_battery_percent: clampChargeTarget(target),
  });
  return arr;
}

// Remove the step at index (no-op if out of range). Returns a fresh array.
export function removeStep(steps, index) {
  const arr = Array.isArray(steps) ? [...steps] : [];
  if (!arr.length) return arr;
  const at = clampIndex(index, arr.length - 1);
  arr.splice(at, 1);
  return arr;
}

// Update the target of the charge step at index; no-op if it is not a charge_wait. Fresh array.
export function setChargeTarget(steps, index, target) {
  const arr = Array.isArray(steps) ? [...steps] : [];
  if (!arr.length) return arr;
  const at = clampIndex(index, arr.length - 1);
  const step = arr[at];
  if (!isChargeStep(step)) return arr;
  arr[at] = {
    ...step,
    target_battery_percent: clampChargeTarget(target, step.target_battery_percent),
  };
  return arr;
}

// Insert a wait step at atIndex (0..length). Returns a fresh array.
export function insertWaitStep(steps, atIndex, minutes = DEFAULT_WAIT_MINUTES) {
  const arr = Array.isArray(steps) ? [...steps] : [];
  const at = clampIndex(atIndex, arr.length);
  arr.splice(at, 0, { type: "wait", wait_minutes: clampWaitMinutes(minutes) });
  return arr;
}

// Update the minutes of the wait step at index; no-op if it is not a wait. Fresh array.
export function setWaitMinutes(steps, index, minutes) {
  const arr = Array.isArray(steps) ? [...steps] : [];
  if (!arr.length) return arr;
  const at = clampIndex(index, arr.length - 1);
  const step = arr[at];
  if (!isWaitStep(step)) return arr;
  arr[at] = { ...step, wait_minutes: clampWaitMinutes(minutes, step.wait_minutes) };
  return arr;
}

export function stepsHaveRoomGroup(steps) {
  return Array.isArray(steps) && steps.some(isRoomGroupStep);
}

export function stepsHaveChargeStep(steps) {
  return Array.isArray(steps) && steps.some(isChargeStep);
}

// Snapshot the current room setup (card rooms from getRoomsForActiveMap, camelCase) into a
// room_group step with backend-shaped (snake_case) per-room settings. Only ENABLED rooms are
// included. Null/unset fields are OMITTED so they fall through to the global room settings at
// dispatch (the per-group overlay only overrides what is actually set) — never clobber a real
// global value with null.
export function roomsToGroupStep(rooms) {
  const groupRooms = (Array.isArray(rooms) ? rooms : [])
    .filter((r) => r && r.enabled && r.id != null)
    .map((r) => {
      const room = { room_id: Number(r.id) };
      if (r.cleanMode != null) room.clean_mode = r.cleanMode;
      if (r.fanSpeed != null) room.fan_speed = r.fanSpeed;
      if (r.waterLevel != null) room.water_level = r.waterLevel;
      if (r.cleanIntensity != null) room.clean_intensity = r.cleanIntensity;
      if (r.cleanPasses != null) room.clean_passes = Number(r.cleanPasses);
      if (r.edgeMopping != null) room.edge_mopping = Boolean(r.edgeMopping);
      return room;
    });
  return { type: "room_group", rooms: groupRooms };
}

// Drop invalid/empty steps + strip client-only fields, mirroring the backend normalize, so the
// service receives already-clean data. A room_group needs a non-empty rooms list; a charge_wait
// needs a clamped integer target. Returns a fresh array.
export function sanitizeStepsForSave(steps) {
  const out = [];
  for (const step of Array.isArray(steps) ? steps : []) {
    if (isRoomGroupStep(step) && Array.isArray(step.rooms) && step.rooms.length) {
      out.push({ type: "room_group", rooms: [...step.rooms] });
    } else if (isChargeStep(step)) {
      out.push({
        type: "charge_wait",
        target_battery_percent: clampChargeTarget(step.target_battery_percent),
      });
    } else if (isWaitStep(step)) {
      out.push({ type: "wait", wait_minutes: clampWaitMinutes(step.wait_minutes) });
    } else if (isZoneStep(step)) {
      // Preserve a zone step's saved-zone ids (dedup, non-empty strings) — mirrors the
      // backend normalize; without this, editing + saving a profile drops the zone.
      const ids = [
        ...new Set(
          (Array.isArray(step.zone_ids) ? step.zone_ids : [])
            .map((z) => String(z).trim())
            .filter(Boolean)
        ),
      ];
      if (ids.length) out.push({ type: "zone", zone_ids: ids });
    }
  }
  return out;
}
