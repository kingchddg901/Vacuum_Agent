// Helpers shared by the standalone Vacuum Agent Lovelace cards (the single-room
// room-card and the multi-room dashboard card). Kept small, pure, and DOM-light
// so both cards have ONE source of truth for escaping, vocab localization, the
// room-switch readers, and the chip-row markup.

import { translate, resolveLang, ensureLocalesLoaded } from "../i18n/index.js";

export { translate, resolveLang, ensureLocalesLoaded };

/** HTML-escape a value for safe interpolation into innerHTML. */
export function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Localize a setting VALUE through `vocab.<field>.<slug>`, falling back to a
 * provided label (escaped) when there's no catalog entry. `t` is the card's
 * bound translate function (locale already resolved).
 */
export function vocab(t, field, value, fallback) {
  if (value == null || value === "") return esc(fallback ?? "");
  const slug = String(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  const out = t(`vocab.${field}.${slug}`);
  return out === `vocab.${field}.${slug}` ? esc(fallback ?? String(value)) : out;
}

/**
 * Every per-room switch managed by one vacuum, read live from hass.states.
 * Each carries the room_id + the adapter-declared option lists + current
 * per-room settings as attributes (populated by the backend room entity).
 * @returns {Array<{entityId: string, state: string, attrs: object}>}
 */
export function roomSwitchesFor(hass, vacuumEntityId) {
  const states = hass?.states;
  if (!states || !vacuumEntityId) return [];
  return Object.entries(states)
    .filter(([id, s]) =>
      id.startsWith("switch.") &&
      s.attributes?.vacuum_entity_id === vacuumEntityId &&
      s.attributes?.room_id != null
    )
    .map(([id, s]) => ({ entityId: id, state: s.state, attrs: s.attributes ?? {} }));
}

/** Read an adapter-declared option list `[{value,label},…]` off switch attrs. */
export function adapterOptions(attrs, attrName) {
  const list = attrs?.[attrName];
  return Array.isArray(list) ? list : [];
}

/** The committed (saved) per-room field values off a room switch's attributes. */
export function committedRoomFields(attrs = {}) {
  return {
    clean_mode:      attrs.clean_mode      ?? "vacuum",
    fan_speed:       attrs.fan_speed       ?? null,
    water_level:     attrs.water_level     ?? null,
    clean_intensity: attrs.clean_intensity ?? null,
    clean_passes:    Number(attrs.clean_passes ?? 1),
    edge_mopping:    Boolean(attrs.edge_mopping ?? false),
  };
}

/** True for any mode whose name contains "mop" (vacuum_mop, mop, …). */
export function isMopMode(mode) {
  return String(mode ?? "").toLowerCase().replace(/[\s_-]/g, "").includes("mop");
}

/**
 * Build a chip-row of mutually-exclusive options. `tVocabFn(field, value, label)`
 * returns the localized chip label. `idPrefix` namespaces the data-attrs so a
 * card with many rows can route clicks back to the right room.
 */
export function chipRow(label, fieldKey, options, currentVal, tVocabFn, idPrefix = "") {
  if (!options.length) return "";
  const pre = idPrefix ? `data-scope="${esc(idPrefix)}" ` : "";
  return `
    <div class="field-group">
      <div class="field-label">${esc(label)}</div>
      <div class="chips">
        ${options.map((opt) => `
          <button
            class="chip ${String(currentVal ?? "").toLowerCase() === String(opt.value ?? "").toLowerCase() ? "active" : ""}"
            ${pre}data-field="${esc(fieldKey)}"
            data-value="${esc(opt.value)}"
          >${tVocabFn(fieldKey, opt.value, opt.label)}</button>
        `).join("")}
      </div>
    </div>
  `;
}

/**
 * Response-capable service call (snapshot / saved-profile reads). Mirrors the
 * panel's actions/core.js helper: target undefined, notifyOnError false,
 * returnResponse true. Returns the unwrapped `response` payload, or null on any
 * failure (never throws into the render cycle).
 */
export async function callResponse(hass, domain, service, data = {}) {
  if (!hass?.callService) return null;
  try {
    const res = await hass.callService(domain, service, data, undefined, false, true);
    return res?.response ?? res ?? null;
  } catch (err) {
    console.error(`[vacuum-agent] ${domain}.${service} failed`, { data, err });
    return null;
  }
}

/**
 * Drop keys whose value is null/undefined. A per-room draft is seeded from the
 * room's committed fields, which carry null for any unset setting (a vacuum-only
 * room has no water_level/clean_intensity). update_room_fields types those as
 * optional STRINGS and rejects a PRESENT null, which would abort the whole call —
 * so send only the fields that actually have a value (there's no UI to set null).
 */
export function stripNull(obj) {
  return Object.fromEntries(Object.entries(obj ?? {}).filter(([, v]) => v != null));
}

/** Register a card in window.customCards once (idempotent across reloads). */
export function registerCard(entry) {
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === entry.type)) {
    window.customCards.push(entry);
  }
}
