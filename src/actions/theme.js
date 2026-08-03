// Thin service wrappers for theme library, active theme, working draft, and import/export.

import {
  DOMAIN,
  SERVICE_GET_THEME_LIBRARY,
  SERVICE_SAVE_THEME_AS_NEW,
  SERVICE_OVERWRITE_THEME,
  SERVICE_RENAME_THEME,
  SERVICE_SET_THEME_TAGS,
  SERVICE_DELETE_THEME,
  SERVICE_SET_ACTIVE_THEME,
  SERVICE_UPDATE_WORKING_DRAFT,
  SERVICE_REVERT_DRAFT,
  SERVICE_EXPORT_THEME,
  SERVICE_IMPORT_THEME,
} from "../constants.js";

export function applyThemeActions(proto) {
  // Single funnel every theme action method below routes through. Every
  // theme service's refusal rides {ok: false, reason: "<code>"} — a DIFFERENT
  // shape from callService's own {success: false} inspection (core.js), so
  // that generic check never fires for a theme call. Centralizing the {ok:
  // false} check HERE — once, at the shared funnel — means none of the ~11
  // action methods below (or their ~11 call sites) needs to repeat it; a
  // reason code always resolves through showServiceRefusalToast's
  // SERVICE_REASON_KEYS lookup (core.js) the same way an operational
  // job_control refusal does. Callers still get the full `result` back
  // unchanged — this only adds the missing toast.
  proto._callThemeService = async function (service, data = {}) {
    const result = await this.callService(DOMAIN, service, data, true);
    if (result && typeof result === "object" && result.ok === false) {
      this.showServiceRefusalToast(result.reason);
    }
    return result;
  };

  /* =========================================================
     LIBRARY
     ========================================================= */

  proto.getThemeLibrary = async function () {
    const result = await this._callThemeService(SERVICE_GET_THEME_LIBRARY, {});
    return result?.response ?? result;
  };

  /* =========================================================
     ACTIVE THEME
     ========================================================= */

  proto.setActiveTheme = async function (vacuumEntityId, themeId) {
    const data = { theme_id: themeId };

    if (vacuumEntityId) {
      data.vacuum_entity_id = vacuumEntityId;
    }

    const result = await this._callThemeService(SERVICE_SET_ACTIVE_THEME, data);
    return result?.response ?? result;
  };

  /* =========================================================
     WORKING DRAFT
     ========================================================= */

  proto.updateWorkingDraft = async function (vacuumEntityId, { tokens, colors, alpha } = {}) {
    const data = {
      vacuum_entity_id: vacuumEntityId,
    };

    if (tokens && Object.keys(tokens).length) {
      data.tokens = tokens;
    }

    if (colors && Object.keys(colors).length) {
      data.colors = colors;
    }

    if (alpha && Object.keys(alpha).length) {
      data.alpha = alpha;
    }

    const result = await this._callThemeService(SERVICE_UPDATE_WORKING_DRAFT, data);
    return result?.response ?? result;
  };

  proto.revertDraft = async function (vacuumEntityId) {
    const result = await this._callThemeService(SERVICE_REVERT_DRAFT, {
      vacuum_entity_id: vacuumEntityId,
    });
    return result?.response ?? result;
  };

  /* =========================================================
     SAVE / OVERWRITE
     ========================================================= */

  proto.saveThemeAsNew = async function (vacuumEntityId, name, setAsDefault = false) {
    const result = await this._callThemeService(SERVICE_SAVE_THEME_AS_NEW, {
      vacuum_entity_id: vacuumEntityId,
      name,
      set_as_default: Boolean(setAsDefault),
    });
    return result?.response ?? result;
  };

  proto.overwriteTheme = async function (vacuumEntityId, themeId) {
    const result = await this._callThemeService(SERVICE_OVERWRITE_THEME, {
      vacuum_entity_id: vacuumEntityId,
      theme_id: themeId,
    });
    return result?.response ?? result;
  };

  /* =========================================================
     LIBRARY MANAGEMENT
     ========================================================= */

  proto.renameTheme = async function (themeId, name) {
    const result = await this._callThemeService(SERVICE_RENAME_THEME, {
      theme_id: themeId,
      name,
    });
    return result?.response ?? result;
  };

  proto.deleteTheme = async function (themeId) {
    const result = await this._callThemeService(SERVICE_DELETE_THEME, {
      theme_id: themeId,
    });
    return result?.response ?? result;
  };

  proto.setThemeTags = async function (themeId, tags) {
    const result = await this._callThemeService(SERVICE_SET_THEME_TAGS, {
      theme_id: themeId,
      tags: Array.isArray(tags) ? tags : [],
    });
    return result?.response ?? result;
  };

  /**
   * Post a theme export to a Home Assistant persistent notification — a "deal
   * with it later" escape hatch for when both clipboard (insecure context) and
   * download are blocked. The JSON goes in a fenced code block so HA's markdown
   * renders it as a copyable block. One notification per theme (id keyed on the
   * theme), so re-exporting replaces rather than piling up duplicates.
   * @returns {Promise<boolean>} true on success.
   */
  proto.notifyThemeExport = async function (themeId, themeName, jsonText) {
    const safeName = String(themeName || themeId || "theme").trim() || "theme";
    const message = [
      "Import via the card's **Upload** / **Import**, or copy the JSON:",
      "",
      "```json",
      String(jsonText || ""),
      "```",
    ].join("\n");
    // callService returns null on failure, undefined on success (no response).
    const result = await this.callService(
      "persistent_notification",
      "create",
      {
        title: `Theme export: ${safeName}`,
        message,
        notification_id: `eufy_theme_export_${themeId || "theme"}`,
      },
    );
    return result !== null;
  };

  /* =========================================================
     IMPORT / EXPORT
     ========================================================= */

  proto.exportTheme = async function (themeId) {
    const result = await this._callThemeService(SERVICE_EXPORT_THEME, {
      theme_id: themeId,
    });
    return result?.response ?? result;
  };

  proto.importTheme = async function (payload, vacuumEntityId = null) {
    const data = { payload };
    // A SCOPED import targets the active theme of a specific vacuum; a full
    // import omits it (the backend adds a new library theme).
    if (vacuumEntityId) data.vacuum_entity_id = vacuumEntityId;
    const result = await this._callThemeService(SERVICE_IMPORT_THEME, data);
    return result?.response ?? result;
  };
}
