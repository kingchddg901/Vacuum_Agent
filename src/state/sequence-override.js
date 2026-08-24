/**
 * Sequence-override row state derivation — pure, testable.
 *
 * ⚠ This UI EDITS A PERSISTENT MAP-LEVEL SETTING IN THE VENDOR APP. See
 * FINDINGS-roborock-clean-sequence-2026-08-19.md for the design and the safety
 * arguments. Toggling the switch off deliberately does NOT clear the device;
 * Clear is EXPLICIT so a sequence the user set in their own Roborock app is
 * never destroyed by a stray toggle.
 *
 * Five row states, three verification signals (amber/green/grey — never two):
 *
 *   `absent`      — no capability (switch entity does not exist). Return {kind:"absent"};
 *                    the renderer emits nothing.
 *   `path_optimizing` — switch off, device order is empty. "Vacuum optimises the
 *                    path itself." Shown without a Clear button.
 *   `saved`       — switch off, device carries a saved order. Show the ordered
 *                    room names + a Clear button.
 *   `mismatch`    — switch on, device order != current queue. Amber, Apply button.
 *   `matching`    — switch on, device order == current queue. Green, no action.
 *   `unverifiable`— sensor state is `unknown`/`unavailable`/`never_read`. Grey,
 *                    "could not check". Start is not locked by this row.
 */

/**
 * @typedef {object} SequenceRowState
 * @property {"absent"|"path_optimizing"|"saved"|"mismatch"|"matching"|"unverifiable"} kind
 * @property {boolean} [overrideOn]       - Whether the persistent switch is on.
 * @property {number[]} [deviceOrder]     - Room ids the device has saved.
 * @property {string[]} [deviceNames]     - Names for `deviceOrder`, in order.
 * @property {number[]} [queueOrder]      - Room ids the current queue would dispatch.
 * @property {string[]} [queueNames]      - Names for `queueOrder`, in order.
 */

/**
 * Derive the row state.
 *
 * @param {object} inputs
 * @param {object|null} inputs.switchState - HA state of the override switch, or null.
 * @param {object|null} inputs.sensorState - HA state of the clean-order sensor, or null.
 * @param {Array<{room_id: (number|string), name?: string, on?: boolean}>} inputs.queueRooms
 *   - Rooms the current queue would dispatch, in order.
 * @returns {SequenceRowState}
 */
export function deriveSequenceRowState({ switchState, sensorState, queueRooms }) {
  // No switch entity at all -> the vacuum's adapter+model does not declare the
  // write half of device_clean_order. Absent by design; render nothing.
  if (!switchState) return { kind: "absent" };

  const overrideOn = String(switchState.state).toLowerCase() === "on";

  const sensorStatus = String(sensorState?.attributes?.status ?? "").toLowerCase();
  const rawState = String(sensorState?.state ?? "").toLowerCase();

  // Unverifiable: the sensor could not read the device. This is the THIRD
  // verification state, not a lock — Start must stay unlocked, and the row says
  // so plainly so the user can proceed with post-hoc comparison.
  const isUnverifiable = (
    rawState === "unknown" || rawState === "unavailable" || rawState === ""
    || sensorStatus === "unavailable" || sensorStatus === "never_read"
  );
  if (isUnverifiable) {
    return { kind: "unverifiable", overrideOn };
  }

  // Ids and names are PARALLEL ARRAYS the card renders index-by-index, so the
  // finite-filter has to drop the id and its name TOGETHER. Filtering only the
  // id array (the first cut of this function) silently shifts every later name
  // up by one the moment a single id fails Number.isFinite — the mismatch row
  // then names the wrong rooms while looking perfectly well-formed. Build each
  // pair in one pass so there is no shape in which they can disagree.
  const rawDeviceOrder = Array.isArray(sensorState?.attributes?.order)
    ? sensorState.attributes.order
    : [];
  const rawDeviceNames = Array.isArray(sensorState?.attributes?.order_names)
    ? sensorState.attributes.order_names
    : [];
  const devicePairs = rawDeviceOrder
    .map((v, i) => ({ id: Number(v), name: String(rawDeviceNames[i] ?? v ?? "") }))
    .filter((p) => Number.isFinite(p.id));
  const deviceOrder = devicePairs.map((p) => p.id);
  const deviceNames = devicePairs.map((p) => p.name);

  const queuePairs = (queueRooms || [])
    .filter((r) => r?.on !== false)
    .map((r) => ({ id: Number(r?.room_id), name: String(r?.name ?? r?.room_id ?? "") }))
    .filter((p) => Number.isFinite(p.id));
  const queueOrder = queuePairs.map((p) => p.id);
  const queueNames = queuePairs.map((p) => p.name);

  // Switch OFF branch: only two states, because comparison is meaningless without
  // the user's intent to override.
  if (!overrideOn) {
    if (deviceOrder.length === 0) {
      return { kind: "path_optimizing", overrideOn: false };
    }
    return {
      kind: "saved",
      overrideOn: false,
      deviceOrder,
      deviceNames,
    };
  }

  // Switch ON branch: comparison-first.
  const same = (
    deviceOrder.length === queueOrder.length
    && deviceOrder.every((v, i) => v === queueOrder[i])
  );
  if (same) {
    return { kind: "matching", overrideOn: true, deviceOrder, deviceNames, queueOrder, queueNames };
  }
  return {
    kind: "mismatch",
    overrideOn: true,
    deviceOrder, deviceNames,
    queueOrder, queueNames,
  };
}
