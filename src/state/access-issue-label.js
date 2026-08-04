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
 * A5-AG-2 moved the RESOLUTION into state/coded-label.js, because start block
 * reasons ask the identical question against a different namespace. What stays
 * here is the part that is genuinely about access issues: the scoped lookup.
 * `message` is still the backend's and still the last fallback — see the header
 * of coded-label.js for why it cannot move.
 *
 * ============================================================
 */

import { resolveCodedLabel } from "./coded-label.js";

/**
 * Resolve one access-graph issue to a user-facing string.
 *
 * SCOPED LOOKUP. Two codes mean different things depending on who raised them:
 * the backend's `missing_room` is "this room REFERENCES a room that is gone",
 * the card validator's is "the room you are editing is gone"; and the two
 * `multiple_inbound` sentences interpolate different params entirely.
 * Card-raised issues therefore resolve room_access.issue.card.* first, and fall
 * back to the shared key for codes where the meaning IS the same.
 *
 * @param {{code?: string, params?: object, message?: string, scope?: string}} issue
 * @param {(key: string, vars?: object) => string} t - the card's translate fn.
 * @returns {string}
 */
export function accessIssueLabel(issue, t) {
  return resolveCodedLabel(issue, t, {
    prefixes: issue?.scope === "card"
      ? ["room_access.issue.card.", "room_access.issue."]
      : ["room_access.issue."],
    // The access namespace carries its own separator key (shipped in all 18
    // packs before common.list_separator existed); it wins, then the shared one.
    separatorKeys: ["room_access.issue.list_separator", "common.list_separator"],
    genericKey: "room_access.invalid_graph",
  });
}
