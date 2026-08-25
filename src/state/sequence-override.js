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
  if (!switchState) return { kind: "absent", canApply: false };

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
  // Counted before the unverifiable early-return, which happens above the pair-wise
  // build below and would otherwise have no view of the queue at all.
  const queueOrderCount = (queueRooms || [])
    .filter((r) => r?.on !== false && Number.isFinite(Number(r?.room_id)))
    .length;

  if (isUnverifiable) {
    // ⚠ APPLY IS OFFERED HERE, and that is the whole point of `canApply`.
    // Until 2026-08-24 this state rendered no action at all, which DEADLOCKED the
    // feature on every install: the sensor starts `never_read`, never_read forces
    // this branch, this branch showed no Apply, and Apply is the only thing that
    // writes — so nothing could ever populate the cache and the row was permanently
    // grey. Withholding Apply because we cannot verify is backwards: APPLY IS HOW
    // VERIFICATION IS OBTAINED. You write, the device acks, and now you know.
    // Grey means "we do not know the device's order", never "you may not act".
    // ⚠ AND NOT WITH AN EMPTY QUEUE. `apply_current_queue` REFUSES that outright —
    // `{status: "refused", reason: "empty_queue"}` — because writing [] would wipe a
    // sequence the user may have set in their own app. But the refusal is a RETURN
    // value, not a raise, and both surfaces discard the service result, so offering
    // Apply here produced a button that could be pressed forever with no write, no
    // error and no feedback. The manager's own comment promised "a visible refusal";
    // there was no surface to make it visible on. Cheaper and honester to not offer
    // an action that is already known to be refused.
    return { kind: "unverifiable", overrideOn, canApply: overrideOn && queueOrderCount > 0 };
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
      return { kind: "path_optimizing", overrideOn: false, canApply: false };
    }
    return {
      kind: "saved",
      overrideOn: false,
      canApply: false,        // the switch gates the write; it is off here
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
    return { kind: "matching", overrideOn: true, canApply: false, deviceOrder, deviceNames, queueOrder, queueNames };
  }
  return {
    kind: "mismatch",
    overrideOn: true,
    // Same rule as the unverifiable branch: an empty queue is refused by the
    // service, so do not offer the button that triggers the refusal.
    canApply: queueOrder.length > 0,
    deviceOrder, deviceNames,
    queueOrder, queueNames,
  };
}

/**
 * Find this vacuum's Override Order switch in `hass.states`, or null.
 *
 * TWO-TIER, and the fallback is the load-bearing half. Lives HERE rather than on
 * either card because there are TWO surfaces that render this row — the standalone
 * dashboard card and the panel's rooms view — and a lookup copied into both is a
 * lookup that will diverge. The row was shipped on only one of them on 2026-08-24;
 * a shared helper is what stops the next feature landing on one surface only.
 *
 * ⚠ THE CONSTRUCTED ID IS A GUESS, NOT A CONTRACT. The switch sets
 * `_attr_has_entity_name` + a `translation_key`, so Home Assistant builds its
 * entity_id from the device name plus the entity NAME — and the name is not
 * resolvable at the moment the platform ADDS the entity. Measured on the live box:
 * the registry held `original_name: 'Clean Order Override'` while `entity_id` was
 * bare `switch.ivy`, and entity_ids are STICKY, so it never self-corrects. Where the
 * name DOES resolve in time the slug comes from the TRANSLATED name, so the guess is
 * wrong in another language instead.
 *
 * `role` is the discriminator and it is a SLUG on purpose: ~20 other switches carry
 * `vacuum_entity_id` (every per-room one), and matching the friendly name would fail
 * in exactly the non-English case this fallback exists for.
 *
 * @param {object} hass
 * @param {string} vacuumEntityId
 * @returns {object|null}
 */
/**
 * The clean-order SENSOR for a vacuum, by convention first and by attribute scan
 * after — the same two tiers `findOverrideSwitch` uses, and for the same reason.
 *
 * ⚠ THE CONVENTIONAL ID IS NOT RELIABLE, and this was found in production. The
 * sensor sets `_attr_has_entity_name` with a `translation_key`, so Home Assistant
 * composes its entity_id from its NAME — and the name is TRANSLATED. Eight of the
 * eighteen shipped packs give it one, so a German install registers
 * `sensor.<device>_reinigungsreihenfolge`. Guessing `sensor.<object_id>_clean_order`
 * misses there, the row never sees a sensor, and it sits permanently grey while
 * everything underneath works perfectly.
 *
 * Both surfaces guessed with no fallback until 2026-08-24, even though the sibling
 * switch beside them had carried this exact fallback since the same class of bug was
 * fixed there. Fixing one entity and not the one next to it is the shape to watch.
 */
export function findCleanOrderSensor(hass, vacuumEntityId) {
  if (!hass || !vacuumEntityId) return null;
  const objectId = String(vacuumEntityId).split(".")[1];
  const primary = hass.states?.[`sensor.${objectId}_clean_order`];
  if (primary) return primary;
  return (
    Object.values(hass.states || {}).find(
      (s) =>
        s.entity_id.startsWith("sensor.") &&
        s.attributes?.vacuum_entity_id === vacuumEntityId &&
        s.attributes?.role === "clean_order",
    ) ?? null
  );
}

export function findOverrideSwitch(hass, vacuumEntityId) {
  if (!hass || !vacuumEntityId) return null;
  const objectId = String(vacuumEntityId).split(".")[1];
  const primary = hass.states?.[`switch.${objectId}_clean_order_override`];
  if (primary) return primary;
  return (
    Object.values(hass.states || {}).find(
      (s) =>
        s.entity_id.startsWith("switch.") &&
        s.attributes?.vacuum_entity_id === vacuumEntityId &&
        s.attributes?.role === "clean_order_override",
    ) ?? null
  );
}
