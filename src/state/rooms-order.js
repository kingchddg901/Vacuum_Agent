// Rooms order adapter: connects the shared ordering engine to the Rooms view room list.

export function applyRoomsOrderState(proto) {

  /**
   * Return the rooms adapter for the shared ordering engine.
   * @param {string} scope
   * @returns {object|null} adapter, or null when scope !== "rooms"
   */
  proto.getOrderAdapter = function (scope) {
    if (scope !== "rooms") return null;

    return {
      scope: "rooms",

      getItems: function () {
        const rooms = this.getRoomsForActiveMap();
        return Array.isArray(rooms) ? rooms : [];
      },

      getId: function (room) {
        return room?.id;
      },

      // Label shown in the shared move-to-position modal.
      getLabel: function (room) {
        return room?.name ?? "Room";
      },

      getOrder: function (room) {
        return room?.order;
      },

      // Returns a shallow clone — persistence happens via the actions layer.
      setOrder: function (room, order) {
        return {
          ...room,
          order,
        };
      },

      // Delegates to persistRoomOrdering so the integration stays source of truth.
      persist: async function (orderedRooms, meta = {}) {
        if (!this._actions?.persistRoomOrdering) {
          console.warn(
            "[eufy-vacuum-command-center] persistRoomOrdering not available"
          );
          return;
        }

        await this._actions.persistRoomOrdering(orderedRooms, meta);
      },
    };
  };
}
