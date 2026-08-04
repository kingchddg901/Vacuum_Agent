/**
 * ============================================================
 * ACCESS-GRAPH ISSUE LABELS
 * ============================================================
 *
 * A6-AGX-4. Every access-graph issue used to reach the user as ENGLISH PROSE
 * built in Python — `_format_access_graph_issue` composes ten sentences and the
 * card rendered `issue.message` verbatim. So the room-access modal and its save
 * refusals were the one place in the card that could not be translated, in an
 * integration that ships 18 locales.
 *
 * The backend now emits `params` beside the `code` it always carried: the values
 * the sentence interpolates, as strings, never pre-joined. This resolves that
 * pair to a translated phrase.
 *
 * `message` is DELIBERATELY still emitted by the backend and is still the last
 * fallback here. It is the documented response-service surface that automations
 * and non-card consumers read, and it is what keeps a code this card release has
 * never heard of from rendering blank — a newer backend can add an issue type
 * without the card going silent. Mirrors the BLOCK_REASON_CODES pattern in
 * renderers/rooms.js: known code -> translated, unknown -> pass the raw through.
 *
 * Pure function, no DOM and no `this`, so it is unit-testable directly.
 *
 * ============================================================
 */

/**
 * List-valued params (cycle chains, inbound sources, dock rooms) arrive as
 * arrays precisely so the CARD picks the separator — joining them in Python
 * would bake an English list convention into every locale. Everything else is
 * passed through untouched.
 *
 * @param {Record<string, unknown>} params
 * @param {(key: string) => string} t
 * @returns {Record<string, string>}
 */
function flattenParams(params, t) {
  const out = {};
  for (const [key, value] of Object.entries(params ?? {})) {
    if (Array.isArray(value)) {
      const sep = t("room_access.issue.list_separator");
      // A missing/echoed key must not become the separator itself.
      const glue = (!sep || sep === "room_access.issue.list_separator") ? ", " : sep;
      out[key] = value.map((entry) => String(entry)).join(glue);
    } else {
      out[key] = String(value ?? "");
    }
  }
  return out;
}

/**
 * Resolve one access-graph issue to a user-facing string.
 *
 * @param {{code?: string, params?: object, message?: string}} issue
 * @param {(key: string, vars?: object) => string} t - the card's translate fn.
 * @returns {string}
 */
export function accessIssueLabel(issue, t) {
  if (!issue || typeof issue !== "object") return String(issue ?? "");

  const code = String(issue.code ?? "").trim();
  if (code && typeof t === "function") {
    const vars = flattenParams(issue.params, t);
    // SCOPED LOOKUP. Two codes mean different things depending on who raised
    // them: the backend's `missing_room` is "this room REFERENCES a room that is
    // gone", the card validator's is "the room you are editing is gone"; and the
    // two `multiple_inbound` sentences interpolate different params entirely.
    // Card-raised issues therefore resolve room_access.issue.card.* first, and
    // fall back to the shared key for codes where the meaning IS the same.
    const keys = issue.scope === "card"
      ? [`room_access.issue.card.${code}`, `room_access.issue.${code}`]
      : [`room_access.issue.${code}`];
    for (const key of keys) {
      const resolved = t(key, vars);
      // The card's translate returns the KEY itself on a miss (a visible miss,
      // by design), so that is how an unknown code is detected — fall through
      // rather than showing a bare key to the user.
      if (resolved && resolved !== key) return resolved;
    }
  }

  if (issue.message) return String(issue.message);
  return typeof t === "function" ? t("room_access.invalid_graph") : "";
}
