/**
 * ============================================================
 * I18N — English base catalog (source of truth)
 * ============================================================
 *
 * Every user-facing string key the card renders, in English. This is the
 * reference for translators and the fallback for all other locales — if a
 * locale is missing a key, English is used; if English is missing it, the key
 * itself shows (a visible miss).
 *
 * Conventions:
 *   - Keys are dot-namespaced by surface: `<view>.<name>`.
 *   - Interpolation uses `{name}` placeholders, e.g. "{count} rooms selected".
 *   - Keep entries grouped by surface and in lock-step with the markup that
 *     calls `this.t(key)`; a key with no caller is dead, a caller with no key
 *     renders the raw key.
 *
 * Scaffold seed: only the strings converted so far. Populated surface-by-
 * surface as renderers are migrated (Phase 1: Setup + Rooms + shell/errors).
 *
 * ============================================================
 */

export const en = {
  // --- Rooms view ---
  "rooms.empty":
    "No rooms yet — open the Setup tab and run Import Active Map (the highlighted button), then Configure Rooms to get started.",

  // --- Room Rules view ---
  "room_rules.empty":
    "No rooms yet — set up rooms first under Setup → Import Active Map (the highlighted button) → Configure Rooms, then add rules here.",
};
