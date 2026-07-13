// Steps-queue order adapter: presents the live ad-hoc queue (enabled rooms + charge/wait
// breaks) as ONE reorderable list for the shared ordering engine, so the move-to-position
// modal shows rooms AND breaks as chips and reordering either kind flows through one path.
//
// The queue is DERIVED, not a stored array: room order lives on the per-room number entities,
// break positions in the manager's queue_breaks store (surfaced via get_queue_steps ->
// snapshot.queue_steps.breaks). So persist() splits the reordered list back to those two
// backings — room order (only when a room actually moved) and the full breaks list (always,
// since a room move can shift a break's after_index). Breaks carry their params through
// untouched, so a pure reorder never edits a value.
//
// Chains getOrderAdapter: scope "steps" here, everything else falls through to the prior
// (rooms) adapter, so this must be applied AFTER applyRoomsOrderState.

const ROOM = "room";
const BREAK = "break";

export function applyStepsQueueOrderState(proto) {
  const prevGetOrderAdapter = proto.getOrderAdapter;

  proto.getOrderAdapter = function (scope) {
    if (scope !== "steps") {
      return typeof prevGetOrderAdapter === "function"
        ? prevGetOrderAdapter.call(this, scope)
        : null;
    }

    return {
      scope: "steps",

      // this === state (the engine calls getItems.call(state)).
      getItems: function () {
        const snap = this.dashboardSnapshot?.();
        const rawBreaks = Array.isArray(snap?.queue_steps?.breaks)
          ? snap.queue_steps.breaks
          : [];
        const rooms = (this.getRoomsForActiveMap?.() || []).filter(
          (r) => r && r.enabled
        );
        const sortedRooms = [...rooms].sort(
          (a, b) => (Number(a?.order) || 999999) - (Number(b?.order) || 999999)
        );

        // Zone labels need saved-zone names (ids -> names); breaks carry their own value.
        const savedZones = this.savedZones?.() ?? [];
        const zoneNameById = {};
        (Array.isArray(savedZones) ? savedZones : []).forEach((z) => {
          if (z && z.id != null) zoneNameById[String(z.id)] = z.name;
        });
        const _breakLabel = (step) => {
          if (step.type === "charge_wait") return `⚡ ${Number(step.target_battery_percent ?? 100)}%`;
          if (step.type === "wait") return `⏱ ${Number(step.wait_minutes ?? 30)} min`;
          if (step.type === "zone") {
            const names = (Array.isArray(step.zone_ids) ? step.zone_ids : [])
              .map((id) => zoneNameById[String(id)] || "?")
              .join(", ");
            return `🎯 ${names}`;
          }
          return "•";
        };

        // Interleave: a break with after_index === K sits after the K-th room
        // (mirrors the backend get_queue_steps derivation).
        const items = [];
        let seq = 0;
        const emitBreaksAfter = (roomsSoFar) => {
          rawBreaks.forEach((b, bi) => {
            if ((Number(b?.after_index) || 0) !== roomsSoFar) return;
            const step = b?.step || {};
            seq += 1;
            items.push({
              kind: BREAK,
              breakIndex: bi,
              step,
              _id: `${BREAK}:${bi}`,
              _label: _breakLabel(step),
              _seq: seq,
            });
          });
        };

        let roomCount = 0;
        emitBreaksAfter(0); // clamped store never stores after_index 0; stay total anyway.
        for (const room of sortedRooms) {
          seq += 1;
          items.push({
            kind: ROOM,
            room,
            _id: `${ROOM}:${room.id}`,
            _label: room?.name ?? "Room",
            _seq: seq,
          });
          roomCount += 1;
          emitBreaksAfter(roomCount);
        }
        return items;
      },

      // Pure readers — the engine calls these detached (no `this`).
      getId: (item) => item?._id,
      getLabel: (item) => item?._label ?? "",
      getOrder: (item) => item?._seq,
      setOrder: (item, order) => ({ ...item, _seq: order }),

      // this === {_actions, state, hass} (the actions layer calls persist.call({...})).
      persist: async function (nextItems, meta = {}) {
        const items = Array.isArray(nextItems) ? nextItems : [];

        // Breaks: recompute after_index for each = number of rooms before it in the new order.
        let roomsBefore = 0;
        const breaks = [];
        for (const it of items) {
          if (it?.kind === ROOM) {
            roomsBefore += 1;
            continue;
          }
          if (it?.kind === BREAK) {
            const step = it.step || {};
            const entry = {
              after_index: Math.max(1, roomsBefore),
              break_type: step.type,
            };
            if (step.type === "charge_wait") {
              entry.target_battery_percent = step.target_battery_percent;
            } else {
              entry.wait_minutes = step.wait_minutes;
            }
            breaks.push(entry);
          }
        }

        // Room order only when a ROOM moved (a break move leaves room order intact, so we
        // avoid churning every room's number entity for a break reposition).
        const roomMoved = String(meta?.itemId ?? "").startsWith(`${ROOM}:`);
        if (roomMoved && this._actions?.persistRoomOrdering) {
          const orderedRooms = items
            .filter((it) => it?.kind === ROOM)
            .map((it, idx) => ({ ...it.room, order: idx + 1 }));
          await this._actions.persistRoomOrdering(orderedRooms);
        }

        // Breaks always: a room move can shift a break's after_index too.
        if (this._actions?.persistQueueBreaks) {
          await this._actions.persistQueueBreaks(breaks);
        }
      },
    };
  };
}
