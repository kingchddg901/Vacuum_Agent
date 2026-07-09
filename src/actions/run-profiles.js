// Service wrappers for saved run profile CRUD (get, save, overwrite, apply, rename, delete).

import {
  DOMAIN,
  SERVICE_GET_SAVED_RUN_PROFILES,
  SERVICE_SAVE_RUN_PROFILE,
  SERVICE_SET_RUN_PROFILE_STEPS,
  SERVICE_OVERWRITE_RUN_PROFILE,
  SERVICE_APPLY_RUN_PROFILE,
  SERVICE_RENAME_RUN_PROFILE,
  SERVICE_DELETE_RUN_PROFILE,
} from "../constants.js";

export function applyRunProfilesActions(proto) {
  /**
   * Fetch the saved run profile library for a specific vacuum and map.
   * @param {object} [opts]
   * @param {string} [opts.vacuum_entity_id]
   * @param {string} [opts.map_id]
   * @returns {Promise<object|null>}
   */
  proto.getSavedRunProfiles = async function ({ vacuum_entity_id, map_id } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_GET_SAVED_RUN_PROFILES,
      {
        vacuum_entity_id,
        map_id,
      },
      true
    );

    return result?.response ?? result;
  };

  /**
   * Create a new named run profile from the current room selection.
   * @param {object} opts
   * @param {string} opts.vacuum_entity_id
   * @param {string} opts.map_id
   * @param {string} opts.name
   * @param {boolean} [opts.expose_as_button]
   * @returns {Promise<object|null>}
   */
  proto.saveRunProfile = async function ({
    vacuum_entity_id,
    map_id,
    name,
    expose_as_button,
  } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SAVE_RUN_PROFILE,
      {
        vacuum_entity_id,
        map_id,
        name,
        expose_as_button: Boolean(expose_as_button),
      },
      true
    );

    return result?.response ?? result;
  };

  /**
   * Overwrite an existing run profile's room snapshot or metadata.
   * @param {object} opts
   * @param {string} opts.vacuum_entity_id
   * @param {string} opts.map_id
   * @param {string} opts.profile_id
   * @param {string} [opts.name]
   * @param {boolean} [opts.expose_as_button]
   * @returns {Promise<object|null>}
   */
  proto.overwriteRunProfile = async function ({
    vacuum_entity_id,
    map_id,
    profile_id,
    name,
    expose_as_button,
  } = {}) {
    const payload = {
      vacuum_entity_id,
      map_id,
      profile_id,
    };

    if (name != null) {
      payload.name = name;
    }

    if (expose_as_button != null) {
      payload.expose_as_button = Boolean(expose_as_button);
    }

    const result = await this.callService(
      DOMAIN,
      SERVICE_OVERWRITE_RUN_PROFILE,
      payload,
      true
    );

    return result?.response ?? result;
  };

  /**
   * Apply a saved run profile (restores saved room selection and settings).
   * @param {object} opts
   * @param {string} opts.vacuum_entity_id
   * @param {string} opts.map_id
   * @param {string} opts.profile_id
   * @returns {Promise<object|null>}
   */
  proto.applyRunProfile = async function ({
    vacuum_entity_id,
    map_id,
    profile_id,
  } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_APPLY_RUN_PROFILE,
      {
        vacuum_entity_id,
        map_id,
        profile_id,
      },
      true
    );

    return result?.response ?? result;
  };

  /**
   * Replace a saved run profile's ordered steps (room_group | charge_wait).
   * @param {object} opts
   * @param {string} opts.vacuum_entity_id
   * @param {string} opts.map_id
   * @param {string} opts.profile_id
   * @param {Array<object>} opts.steps  Ordered steps; each {type:"room_group", rooms:[...]}
   *   or {type:"charge_wait", target_battery_percent:1..100}.
   * @returns {Promise<object|null>}
   */
  proto.setRunProfileSteps = async function ({
    vacuum_entity_id,
    map_id,
    profile_id,
    steps,
  } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_SET_RUN_PROFILE_STEPS,
      {
        vacuum_entity_id,
        map_id,
        profile_id,
        steps,
      },
      true
    );

    return result?.response ?? result;
  };

  /**
   * Rename a saved run profile.
   * @param {object} opts
   * @param {string} opts.vacuum_entity_id
   * @param {string} opts.map_id
   * @param {string} opts.profile_id
   * @param {string} opts.name
   * @returns {Promise<object|null>}
   */
  proto.renameRunProfile = async function ({
    vacuum_entity_id,
    map_id,
    profile_id,
    name,
  } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_RENAME_RUN_PROFILE,
      {
        vacuum_entity_id,
        map_id,
        profile_id,
        name,
      },
      true
    );

    return result?.response ?? result;
  };

  /**
   * Delete a saved run profile.
   * @param {object} opts
   * @param {string} opts.vacuum_entity_id
   * @param {string} opts.map_id
   * @param {string} opts.profile_id
   * @returns {Promise<object|null>}
   */
  proto.deleteRunProfile = async function ({
    vacuum_entity_id,
    map_id,
    profile_id,
  } = {}) {
    const result = await this.callService(
      DOMAIN,
      SERVICE_DELETE_RUN_PROFILE,
      {
        vacuum_entity_id,
        map_id,
        profile_id,
      },
      true
    );

    return result?.response ?? result;
  };
}
