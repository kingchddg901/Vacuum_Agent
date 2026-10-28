// Run: node --test src/state/coded-label.test.mjs
//
// Coverage targets — A5-AG-2, src/state/coded-label.js
//   [CL-1]  a known code resolves against the caller's namespace, with params
//   [CL-2]  prefixes are tried in order; the first HIT wins
//   [CL-3]  an unknown code falls through to the backend's prose
//   [CL-4]  ...and with no prose either, to the generic key, then the raw code
//   [CL-5]  list params join with the locale's separator, first key that resolves
//   [CL-6]  a missing separator key never leaks into the joined string
//   [CL-7]  junk input never throws and never renders "undefined"
//   [CL-8]  LIVE: the access-graph refusal renders a translated sentence naming
//           the rooms — in English and in a non-English pack (the whole point)
//   [CL-9]  LIVE: a raw preflight warning CODE no longer reaches the user
//   [CL-10] LIVE: an unknown warning code still says the code, never blank

import { test } from "node:test";
import assert from "node:assert/strict";

import { readFileSync } from "node:fs";

import { resolveCodedLabel } from "./coded-label.js";
import { translate } from "../i18n/index.js";
import { flattenLocale } from "../i18n/flatten.js";
import { en as EN_MANIFEST } from "../i18n/en.js";

/**
 * A translate fn backed by a SHIPPED locale pack. The packs are fetched at
 * runtime (they are deliberately not bundled), so translate() alone only knows
 * English here — and a test that silently compared English to English would
 * have "passed" while proving nothing.
 */
function packT(code) {
  const raw = JSON.parse(
    readFileSync(
      new URL(
        `../../custom_components/eufy_vacuum/frontend/locales/${code}.json`,
        import.meta.url
      ),
      "utf-8"
    )
  );
  const { flat } = flattenLocale(raw, EN_MANIFEST);
  return (key, vars = {}) => {
    const entry = flat[key];
    if (entry == null) return key;
    return String(entry).replace(
      /\{(\w+)\}/g,
      (whole, name) => (name in vars ? String(vars[name]) : whole)
    );
  };
}

/** A translate stub with the card's real contract: a miss returns the key. */
function makeT(table) {
  return (key, vars = {}) => {
    if (!(key in table)) return key;
    return String(table[key]).replace(
      /\{(\w+)\}/g,
      (whole, name) => (name in vars ? String(vars[name]) : whole)
    );
  };
}

const T = makeT({
  "common.list_separator": ", ",
  "ns.specific.dup": "SPECIFIC",
  "ns.dup": "SHARED",
  "ns.plain": "Plain sentence.",
  "ns.with_list": "Blocked for {rooms}.",
  "ns.generic": "Something is wrong.",
});

const BLOCK = (k, v) => translate("en", k, v, { raw: true });

test("[CL-1] a known code resolves with its params", () => {
  assert.equal(
    resolveCodedLabel({ code: "with_list", params: { rooms: ["Hall"] } }, T, {
      prefixes: ["ns."],
    }),
    "Blocked for Hall."
  );
});

test("[CL-2] prefixes are tried in order and the first hit wins", () => {
  assert.equal(
    resolveCodedLabel({ code: "dup" }, T, { prefixes: ["ns.specific.", "ns."] }),
    "SPECIFIC"
  );
  // Reversed, the shared one wins — proving the order is what decides, not luck.
  assert.equal(
    resolveCodedLabel({ code: "dup" }, T, { prefixes: ["ns.", "ns.specific."] }),
    "SHARED"
  );
  // A code with no specific variant degrades to the shared prefix.
  assert.equal(
    resolveCodedLabel({ code: "plain" }, T, { prefixes: ["ns.specific.", "ns."] }),
    "Plain sentence."
  );
});

test("[CL-3] an unknown code falls back to prose, never a bare key", () => {
  const label = resolveCodedLabel(
    { code: "some_future_reason", message: "A newer backend said this." },
    T,
    { prefixes: ["ns."] }
  );
  assert.equal(label, "A newer backend said this.");
  assert.ok(!label.includes("ns."), "a raw key must never reach the user");
});

test("[CL-4] no key and no prose -> the generic, then the raw code", () => {
  assert.equal(
    resolveCodedLabel({ code: "unheard_of" }, T, {
      prefixes: ["ns."],
      genericKey: "ns.generic",
    }),
    "Something is wrong."
  );
  // Without a generic key the CODE is still better than blank: it names the
  // condition, and a blank refusal reads as a silent success.
  assert.equal(
    resolveCodedLabel({ code: "unheard_of" }, T, { prefixes: ["ns."] }),
    "unheard_of"
  );
});

test("[CL-5] list params use the locale's separator, first key that resolves", () => {
  const issue = { code: "with_list", params: { rooms: ["Hall", "Kitchen"] } };
  assert.equal(
    resolveCodedLabel(issue, T, { prefixes: ["ns."] }),
    "Blocked for Hall, Kitchen."
  );

  const ja = makeT({
    "common.list_separator": ", ",
    "custom.sep": "、",
    "ns.with_list": "Blocked for {rooms}.",
  });
  assert.equal(
    resolveCodedLabel(issue, ja, {
      prefixes: ["ns."],
      separatorKeys: ["custom.sep", "common.list_separator"],
    }),
    "Blocked for Hall、Kitchen."
  );
});

test("[CL-6] a missing separator key never becomes the separator", () => {
  const bare = makeT({ "ns.with_list": "Blocked for {rooms}." });
  const label = resolveCodedLabel(
    { code: "with_list", params: { rooms: ["Hall", "Kitchen"] } },
    bare,
    { prefixes: ["ns."], separatorKeys: ["absent.key"] }
  );
  assert.equal(label, "Blocked for Hall, Kitchen.");
  assert.ok(!label.includes("absent.key"));
});

test("[CL-7] junk never throws and never renders undefined", () => {
  assert.equal(resolveCodedLabel(null, T, { prefixes: ["ns."] }), "");
  assert.equal(resolveCodedLabel(undefined, T, { prefixes: ["ns."] }), "");
  assert.equal(resolveCodedLabel("a plain string", T, { prefixes: ["ns."] }), "a plain string");
  assert.equal(resolveCodedLabel({}, T, { prefixes: ["ns."] }), "");
  // no translate function at all must not throw
  assert.equal(resolveCodedLabel({ code: "x", message: "raw" }, undefined, {}), "raw");
  for (const out of [
    resolveCodedLabel({ code: "with_list", params: null }, T, { prefixes: ["ns."] }),
    resolveCodedLabel({ code: "with_list", params: { rooms: [] } }, T, { prefixes: ["ns."] }),
  ]) {
    assert.ok(!String(out).includes("undefined"), `leaked undefined: ${out}`);
  }
});

test("[CL-8] LIVE: the access-graph refusal names its rooms, in EN and non-EN", () => {
  // The finding: "no shipped surface names the offending room". This is that
  // surface, resolved through the real catalog rather than a stub.
  const descriptor = {
    code: "incomplete_access_graph",
    params: { rooms: ["Hallway", "Study"] },
    message: "Room access graph is partially configured.",
  };

  const enLabel = resolveCodedLabel(descriptor, BLOCK, { prefixes: ["rooms.block_reason."] });
  assert.ok(enLabel.includes("Hallway"), enLabel);
  assert.ok(enLabel.includes("Study"), enLabel);
  assert.notEqual(enLabel, descriptor.message, "the code must win over the English prose");

  const de = resolveCodedLabel(descriptor, packT("de"), {
    prefixes: ["rooms.block_reason."],
  });
  assert.ok(de.includes("Hallway") && de.includes("Study"), de);
  assert.notEqual(de, enLabel, "a non-English install must not get the English sentence");
  assert.notEqual(de, descriptor.message, de);
  assert.ok(!de.includes("rooms.block_reason"), de);

  // The separator is the LOCALE's: Japanese joins with a full-width comma.
  const ja = resolveCodedLabel(descriptor, packT("ja"), {
    prefixes: ["rooms.block_reason."],
  });
  assert.ok(ja.includes("Hallway、Study"), ja);
});

test("[CL-9] LIVE: a preflight warning code no longer renders as a raw identifier", () => {
  // Before A5-AG-2 the reduced-run confirmation panel printed these verbatim,
  // so the user read "rooms_blocked" under a heading that said "Warnings".
  for (const code of [
    "rooms_blocked",
    "incomplete_access_graph",
    "access_graph_required",
    "access_graph_required_for_rules",
  ]) {
    const label = resolveCodedLabel({ code }, BLOCK, {
      prefixes: ["rooms.block_reason."],
    });
    assert.notEqual(label, code, `${code} still renders as its own identifier`);
    assert.ok(!label.includes("_"), `${code} -> ${label} still looks like a code`);
  }
});

/**
 * The backend's own start-protection codes, with the English sentence it sends alongside
 * each one. The MESSAGE is what the user saw: the resolver worked, found no key, and fell
 * through to it — in all 17 languages, for every one of these.
 */
const BACKEND_BLOCK_REASONS = [
  ["no_target_map", "Select a target map first."],
  ["map_mismatch", "The selected map does not match the vacuum's active map."],
  ["no_rooms_selected", "Select at least one room first."],
  ["invalid_payload", "Room-clean payload is missing or invalid."],
  ["mid_job_service", "System is servicing the active job before cleaning continues."],
  ["active_job_running", "A room-clean job is currently active."],
  ["vacuum_busy", "Vacuum is busy and cannot start a new room job."],
  ["dock_drying", "Dock is currently drying pads, but start is allowed."],
  ["all_selected_rooms_blocked", "All selected rooms are currently blocked."],
  ["blocked", "Start is blocked."],
  ["not_enough_clean_water", "Not enough clean water is estimated to complete the selected job."],
  ["low_clean_water_margin", "This job is estimated to leave very little clean water remaining."],
];

test("[CL-11] LIVE: the BACKEND's start-protection codes resolve to the card's sentence", () => {
  // Fourteen `rooms.block_reason.*` keys existed before 2.5.3 and all fourteen were either
  // card-local (state/rooms.js) or access-graph. Not one of these twelve had a key, so the
  // backend's `message` won every time — and because the fallback is deliberate and
  // correct, nothing anywhere went red.
  // ⚠ NO `message` IS PASSED, and that is the whole design of this case. A first draft
  // passed one and asserted the result differed from it — which fails on the four codes
  // whose card wording deliberately MATCHES the backend's, because that wording was already
  // good user-facing English and the key's job there is translation, not rewording. Without
  // a message, a fall-through returns the CODE, so "not the code" means "the key resolved".
  for (const [code] of BACKEND_BLOCK_REASONS) {
    const label = resolveCodedLabel({ code }, BLOCK, {
      prefixes: ["rooms.block_reason."],
    });
    assert.notEqual(label, code, `${code} has no key — it still renders as its own identifier`);
    assert.ok(!label.includes("rooms.block_reason"), `${code} leaked a bare key`);
    assert.ok(!label.includes("_"), `${code} -> ${label} still looks like a code`);
  }
  // tests/unit/test_block_reason_keys.py is the other half: it derives the code set by
  // CALLING the producer, so a new branch cannot be added without a key. This half checks
  // the join those keys sit in.
});

test("[CL-12] LIVE: and they are TRANSLATED, not merely present", () => {
  // The whole point. A key that exists in en.js and nowhere else resolves to English and
  // passes [CL-11] — so this reads a shipped non-English pack and requires the sentence to
  // differ from the English one.
  const de = packT("de");
  for (const [code, message] of BACKEND_BLOCK_REASONS) {
    const label = resolveCodedLabel({ code, message }, de, {
      prefixes: ["rooms.block_reason."],
    });
    const english = resolveCodedLabel({ code, message }, BLOCK, {
      prefixes: ["rooms.block_reason."],
    });
    assert.notEqual(label, message, `${code}: de fell through to the backend's English`);
    assert.notEqual(label, english, `${code}: de holds the English sentence`);
  }
});

test("[CL-10] LIVE: an unknown warning code still says something", () => {
  const label = resolveCodedLabel({ code: "reason_from_a_newer_backend" }, BLOCK, {
    prefixes: ["rooms.block_reason."],
  });
  assert.equal(label, "reason_from_a_newer_backend");
  assert.ok(!label.includes("rooms.block_reason"), "never a bare key");
});
