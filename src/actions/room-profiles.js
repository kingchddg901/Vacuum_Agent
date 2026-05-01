// Service wrappers for room profile CRUD (get, save, overwrite, rename, delete, apply).
import {
  DOMAIN,
  SERVICE_GET_ROOM_PROFILES,
  SERVICE_SAVE_USER_ROOM_PROFILE,
  SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM,
  SERVICE_OVERWRITE_ROOM_PROFILE,
  SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM,
  SERVICE_RENAME_ROOM_PROFILE,
  SERVICE_DELETE_ROOM_PROFILE,
  SERVICE_APPLY_ROOM_PROFILE,
} from "../constants.js";

export function applyRoomProfilesActions(proto) {
  proto.getRoomProfiles = async function () {
    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_ROOM_PROFILES,
      {},
      true
    );

    return result?.response ?? result ?? null;
  };

  proto.saveUserRoomProfile = async function (payload = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SAVE_USER_ROOM_PROFILE,
      payload,
      true
    );

    return result?.response ?? result ?? null;
  };

  proto.saveRoomProfileFromRoom = async function ({
    vacuum_entity_id,
    map_id,
    room_id,
    label,
    profile_name,
  } = {}) {
    const payload = {
      vacuum_entity_id,
      map_id,
      room_id,
      label,
    };

    if (profile_name != null && String(profile_name).trim() !== "") {
      payload.profile_name = String(profile_name).trim();
    }

    const result = await this.callService(
      DOMAIN,
      SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM,
      payload,
      true
    );

    return result?.response ?? result ?? null;
  };

  proto.overwriteRoomProfile = async function (payload = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_OVERWRITE_ROOM_PROFILE,
      payload,
      true
    );

    return result?.response ?? result ?? null;
  };

  proto.overwriteRoomProfileFromRoom = async function ({
    vacuum_entity_id,
    map_id,
    room_id,
    profile_name,
    label,
  } = {}) {
    const payload = {
      vacuum_entity_id,
      map_id,
      room_id,
      profile_name,
    };

    if (label != null && String(label).trim() !== "") {
      payload.label = String(label).trim();
    }

    const result = await this.callService(
      DOMAIN,
      SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM,
      payload,
      true
    );

    return result?.response ?? result ?? null;
  };

  proto.renameRoomProfile = async function ({
    profile_name,
    new_profile_name,
    label,
  } = {}) {
    const payload = {
      profile_name,
    };

    if (new_profile_name != null && String(new_profile_name).trim() !== "") {
      payload.new_profile_name = String(new_profile_name).trim();
    }

    if (label != null && String(label).trim() !== "") {
      payload.label = String(label).trim();
    }

    const result = await this.callService(
      DOMAIN,
      SERVICE_RENAME_ROOM_PROFILE,
      payload,
      true
    );

    return result?.response ?? result ?? null;
  };

  proto.deleteRoomProfile = async function ({ profile_name } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_DELETE_ROOM_PROFILE,
      { profile_name },
      true
    );

    return result?.response ?? result ?? null;
  };

  proto.applyRoomProfile = async function ({
    vacuum_entity_id,
    map_id,
    room_ids,
    profile_name,
  } = {}) {
    const normalizedRoomIds = Array.isArray(room_ids)
      ? room_ids
          .map((roomId) => {
            if (typeof roomId === "number") return roomId;

            const raw = String(roomId ?? "").trim();
            if (!raw) return null;

            const numeric = Number(raw);
            return Number.isNaN(numeric) ? raw : numeric;
          })
          .filter((roomId) => roomId != null)
      : [];

    const result = await this.callService(
      DOMAIN,
      SERVICE_APPLY_ROOM_PROFILE,
      {
        vacuum_entity_id,
        map_id,
        room_ids: normalizedRoomIds,
        profile_name,
      },
      true
    );

    return result?.response ?? result ?? null;
  };
}
