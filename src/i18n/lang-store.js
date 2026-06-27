/**
 * ============================================================
 * I18N: PER-USER LANGUAGE STORE
 * ============================================================
 *
 * The in-card language control persists its choice SERVER-SIDE and PER-USER, so
 * it follows the user's HA login to every device (the "cross-device" promise).
 *
 * It rides Home Assistant's own frontend user-data store — the same mechanism
 * the core frontend uses for per-user preferences — via two websocket commands:
 *
 *   frontend/get_user_data  { key }            -> { value }
 *   frontend/set_user_data  { key, value }     -> (ack)
 *
 * No backend/integration code is needed: this is the blessed upstream way to keep
 * a frontend preference per-user across devices. The one tradeoff is that another
 * ALREADY-OPEN device updates on its next load/render, not in real time — fine for
 * a language preference.
 *
 * Everything here FAILS SOFT: any websocket error (no connection, command
 * unavailable, anonymous/long-lived-token session with no user, malformed value)
 * resolves to "no override" so the card keeps resolving language from the config
 * pin / system language exactly as before. A language toggle must never be able
 * to break rendering.
 *
 * ============================================================
 */

import { listBundledLocales } from "./index.js";

/**
 * The user-data key namespacing this card's per-user preferences. A single
 * object is stored under it (currently just `ui_language`) so future per-user
 * card prefs can join without a second key.
 */
export const USER_DATA_KEY = "eufy_vacuum_card";

/** Field within the user-data object holding the language choice. */
const FIELD = "ui_language";

/**
 * The set of language codes the control may persist: every bundled locale
 * (English + the AI-draft locales) plus the literal "auto" (defer to HA). An
 * unrecognised code is refused at write time — defence in depth so a corrupt or
 * tampered value never reaches the store (resolveLang/translate would fall back
 * to English anyway, but we keep the stored value clean).
 */
function allowedCodes() {
  const codes = new Set(["auto"]);
  for (const l of listBundledLocales()) codes.add(l.code);
  return codes;
}

/** Whether `hass` can issue websocket commands. */
function canWS(hass) {
  return !!(hass && typeof hass.callWS === "function");
}

/**
 * Read the per-user language choice. Resolves to a code, "auto", or null when
 * none is stored / anything goes wrong (caller treats null as "defer").
 *
 * @param {object} hass - Home Assistant connection.
 * @returns {Promise<string|null>}
 */
export async function getStoredLang(hass) {
  if (!canWS(hass)) return null;
  try {
    const res = await hass.callWS({
      type: "frontend/get_user_data",
      key: USER_DATA_KEY,
    });
    const value = res && res.value;
    const code = value && typeof value === "object" ? value[FIELD] : null;
    // Validate on READ too (the write path already validates): a value tampered
    // with directly in storage must not pass through — keep the override clean.
    return typeof code === "string" && code && allowedCodes().has(code) ? code : null;
  } catch (err) {
    console.warn(
      "[eufy-vacuum-command-center] i18n: could not read stored language (defaulting to auto):",
      err,
    );
    return null;
  }
}

/**
 * Persist the per-user language choice. Merges into the existing user-data
 * object so it never clobbers other keys stored under USER_DATA_KEY. Never
 * throws — a failed write just means the choice doesn't persist across reloads
 * (the in-memory override still applies for this session).
 *
 * @param {object} hass - Home Assistant connection.
 * @param {string} code - a bundled code or "auto".
 * @returns {Promise<boolean>} true if the write was acknowledged.
 */
export async function setStoredLang(hass, code) {
  if (!canWS(hass)) return false;
  const next = String(code || "auto");
  if (!allowedCodes().has(next)) {
    console.warn(
      `[eufy-vacuum-command-center] i18n: refusing to store unknown language "${next}"`,
    );
    return false;
  }
  try {
    // Merge into the existing object so sibling prefs survive.
    let current = {};
    try {
      const res = await hass.callWS({
        type: "frontend/get_user_data",
        key: USER_DATA_KEY,
      });
      if (res && res.value && typeof res.value === "object" && !Array.isArray(res.value)) {
        current = res.value;
      }
    } catch {
      // Read-before-write is best-effort; fall back to a fresh object.
    }
    await hass.callWS({
      type: "frontend/set_user_data",
      key: USER_DATA_KEY,
      value: { ...current, [FIELD]: next },
    });
    return true;
  } catch (err) {
    console.warn(
      "[eufy-vacuum-command-center] i18n: could not persist language choice:",
      err,
    );
    return false;
  }
}
