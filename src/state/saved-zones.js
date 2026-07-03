// State accessors for saved zones (Wave 3b). The list rides on every
// get_map_segments response (saved_zones[]); grouped by the room each zone is
// FILED under (room_number), in map order, with an Unassigned bucket last.

export function applySavedZonesState(proto) {
  // Isolated slot fed by refreshSavedZones -> getSavedZones. It NEVER mutates the shared
  // _mapSegmentsData (which resets the map's optimistic overlays), so a background
  // refresh can't snap a mid-drag hidden-region / area-label edit back. Falls back to
  // the map-segments copy for the first paint in map view before the library populates.
  proto.savedZones = function () {
    return this._savedZonesLibrary ?? this._mapSegmentsData?.saved_zones ?? [];
  };

  proto.setSavedZonesLibrary = function (zones) {
    this._savedZonesLibrary = Array.isArray(zones) ? zones : [];
    // Prune the multi-select of any ids that no longer exist (deleted / re-mapped away),
    // so "Clean N selected" never carries a stale id that the service would refuse.
    if (this._savedZoneSelection && this._savedZoneSelection.size) {
      const live = new Set(this._savedZonesLibrary.map((z) => String(z.id)));
      for (const id of [...this._savedZoneSelection]) {
        if (!live.has(id)) this._savedZoneSelection.delete(id);
      }
    }
  };

  // ---- Panel multi-select (Cut 2) --------------------------------------------
  // The selected set is the "will be cleaned" set; "Clean N selected" dispatches it in
  // one call. Kept as a Set of string ids in card state (transient, not persisted).
  proto.isSavedZoneSelected = function (id) {
    return !!this._savedZoneSelection && this._savedZoneSelection.has(String(id));
  };

  proto.toggleSavedZoneSelection = function (id) {
    if (!this._savedZoneSelection) this._savedZoneSelection = new Set();
    const key = String(id);
    if (this._savedZoneSelection.has(key)) this._savedZoneSelection.delete(key);
    else this._savedZoneSelection.add(key);
  };

  proto.clearSavedZoneSelection = function () {
    this._savedZoneSelection = new Set();
  };

  /** The selected ids, in the map/group order the panel shows them. */
  proto.selectedSavedZoneIds = function () {
    if (!this._savedZoneSelection || !this._savedZoneSelection.size) return [];
    const sel = this._savedZoneSelection;
    return this.savedZones()
      .map((z) => String(z.id))
      .filter((id) => sel.has(id));
  };

  proto.selectedSavedZoneCount = function () {
    return this.selectedSavedZoneIds().length;
  };

  // ---- Collapsible section (Cut 2) -------------------------------------------
  proto.savedZonesCollapsed = function () {
    return this._savedZonesCollapsed ?? false;
  };

  proto.setSavedZonesCollapsed = function (collapsed) {
    this._savedZonesCollapsed = !!collapsed;
  };

  /**
   * Group saved zones for the panel: one group per room that has zones (in map
   * order), then an "Unassigned" group last for zones whose room_number is null
   * or is not a room on the current map (re-map / deleted room). Room name is the
   * live room's user-set name; the Unassigned header is i18n (rendered later).
   *
   * @returns {{room_id: (number|null), name: (string|null), zones: object[]}[]}
   */
  proto.savedZonesGrouped = function () {
    const zones = this.savedZones();
    if (!zones.length) return [];

    const rooms = this.getRoomsForActiveMap?.() ?? [];
    const roomById = new Map(rooms.map((r) => [String(r.room_id), r]));

    const byRoom = new Map();
    const unassigned = [];
    for (const z of zones) {
      const key = z?.room_number == null ? null : String(z.room_number);
      if (key != null && roomById.has(key)) {
        if (!byRoom.has(key)) byRoom.set(key, []);
        byRoom.get(key).push(z);
      } else {
        unassigned.push(z);
      }
    }

    const groups = [];
    for (const room of rooms) {
      const key = String(room.room_id);
      if (byRoom.has(key)) {
        groups.push({ room_id: room.room_id, name: room.name, zones: byRoom.get(key) });
      }
    }
    if (unassigned.length) {
      groups.push({ room_id: null, name: null, zones: unassigned });
    }
    return groups;
  };
}
