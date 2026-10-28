// Run: node --test src/renderers/profile-name-vocab.test.mjs
//
// PRF / EST / CHG — the saved-profile NAMES, and two derived codes printed bare.
//
// THE PROFILE HALF IS A ZERO-CALLER STORY, which is why it is worth a file of its own.
// `_builtInProfileI18nKey` maps exactly the seven saved-profile keys onto the seven
// translated `rooms.profile_*` values, and `_roomProfileLabel` wraps it. The map was
// reached from one place — the room editor's chip loop — and `_roomProfileLabel` was reached
// from NOWHERE. Three surfaces printed the backend's English profile names beside it:
//
//   review.js   the matcher chips          `match.label` = profile_labels[key], English
//   review.js   the profile FILTER chips   tVocab("profile_name", …) with no such family
//   room-editor the built-in meta sentence  thirty lines under a chip loop that localizes
//
// A correct function with no callers passes every audit. Same shape as the `device_id`
// filter behind #77, in a different subsystem, found by a census rather than by a user.
//
// The ORDER inside `_profileDisplayName` is the part that needed a decision, and it is not
// "localized first, always": a BUILT-IN's backend label is English so the key must beat it,
// while a USER-SAVED profile's label is the name somebody typed so it must beat a
// prettified slug. [PRF-1] and [PRF-2] are those two directions.
//
// Coverage:
//   [PRF-1] a built-in's key beats the backend's English label
//   [PRF-2] a user-saved profile keeps the typed label — the lookup invents nothing
//   [PRF-3] an unknown key with no label prettifies rather than printing a slug
//   [PRF-4] the helper is RAW, because all three call sites escape
//   [PRF-5] the review matcher chips render the localized name, English absent
//   [PRF-6] the review profile FILTER chips localize through the fallback arm
//   [PRF-7] the room editor localizes the BUILT-IN arm and leaves the custom arm alone
//   [PRF-8] _localizedProfile's fallback arm composes a name for a MULTI-ROOM job
//   [PRF-9] the water card and the Profiles tab agree on one snapshot row
//   [EST-1] the estimate SOURCE localizes on both of its twins
//   [CHG-1] the charge-ended reason localizes; an unknown value passes through

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { applySharedRenderers } from "./shared.js";
import { applyRoomsRenderers } from "./rooms.js";
import { applyMetricsRenderers } from "./metrics.js";
import { applyReviewRenderers } from "./review.js";
import { applyRoomEditorRenderer } from "./room-editor.js";
import { applyRoomEstimateRenderers } from "./room-estimate.js";
import { registerLocale, translate } from "../i18n/index.js";
import { flattenLocale } from "../i18n/flatten.js";
import { en as enCatalog } from "../i18n/en.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const LOCALES = join(HERE, "..", "..", "custom_components", "eufy_vacuum", "frontend", "locales");

function loadPack(code) {
  const nested = JSON.parse(readFileSync(join(LOCALES, `${code}.json`), "utf8"));
  const { flat } = flattenLocale(nested, enCatalog);
  registerLocale(code, flat, { status: "draft" });
  return flat;
}
const DE = loadPack("de");

function makeHost(lang = "de") {
  class H {}
  for (const apply of [applySharedRenderers, applyRoomsRenderers, applyMetricsRenderers,
                       applyReviewRenderers, applyRoomEditorRenderer, applyRoomEstimateRenderers]) {
    apply(H.prototype);
  }
  const h = new H();
  h.escapeHtml = (s) =>
    String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  h.t = (key, vars) => translate(lang, key, vars);
  h.tRaw = (key, vars) => translate(lang, key, vars, { raw: true });
  h.card = { _state: { dashboardSnapshot: () => ({ adapter_id: "eufy" }) } };
  return h;
}

/* ------------------------------------------------------------------- the name helper */

test("[PRF-1] a built-in's key beats the backend's English label", () => {
  const h = makeHost();
  for (const [key, i18nKey] of [
    ["vacuum_quick", "rooms.profile_vacuum_only_quick"],
    ["vacuum_deep", "rooms.profile_vacuum_only_deep"],
    ["vacuum_mop_quick", "rooms.profile_quick"],
    ["vacuum_mop_deep", "rooms.profile_deep"],
    ["user_1", "rooms.profile_user_1"],
    ["custom", "rooms.profile_custom"],
  ]) {
    assert.equal(h._profileDisplayName(key, "Vacuum Only Quick"), DE[i18nKey], key);
  }
});

test("[PRF-2] a user-saved profile keeps the typed label", () => {
  const h = makeHost();
  // The other direction, and the one a "localize everything" fix gets wrong: there is no
  // key for a name the user invented, and prettifying their slug would overwrite what they
  // typed. `profiles.room_profiles` is a global library, so these are arbitrary strings.
  assert.equal(h._profileDisplayName("weekend_deep", "Weekend deep"), "Weekend deep");
  assert.equal(h._profileDisplayName("après_midi", "Après-midi"), "Après-midi");
});

test("[PRF-3] an unknown key with no label prettifies", () => {
  const h = makeHost();
  assert.equal(h._profileDisplayName("weekend_deep", null), "Weekend Deep");
  assert.equal(h._profileDisplayName("weekend_deep", "   "), "Weekend Deep");
  // Empty input falls to the standard-profile key rather than returning blank.
  assert.equal(h._profileDisplayName("", null), DE["rooms.profile_standard"]);
});

test("[PRF-4] the helper returns RAW, because all three call sites escape", () => {
  const h = makeHost();
  // A translated profile name with an apostrophe is the input: the matcher chip, the filter
  // chips and the room editor's meta line all escape what they are handed, so a pre-escaped
  // return would render `&#39;` literally at each.
  registerLocale("xx-prof", { "rooms.profile_user_1": "Profil de l'utilisateur 1" }, { status: "custom" });
  const raw = makeHost("xx-prof")._profileDisplayName("user_1", "User Profile 1");
  assert.equal(raw, "Profil de l'utilisateur 1");
  assert.ok(!raw.includes("&#39;"), "pre-escaping here double-escapes at every call site");
});

/* ------------------------------------------------------------------------ call sites */

test("[PRF-5] the review matcher chips render the localized name", () => {
  const h = makeHost();
  const state = {
    reviewProfileMatcherFields: () => ({ clean_mode: "vacuum", fan_speed: "max", clean_intensity: "deep", clean_passes: 1 }),
    reviewProfileMatcherMatches: () => [{ profile_key: "vacuum_quick", label: "Vacuum Only Quick" }],
    learningHistoryFilters: () => ({ profile_key: "" }),
    cleanModeOptions: () => [], suctionLevelOptions: () => [], waterLevelOptions: () => [],
    cleanIntensityOptions: () => [], showReviewProfileMatcherWaterLevel: () => false,
  };
  const html = h._renderReviewProfileMatcher(state);
  assert.ok(html.includes(DE["rooms.profile_vacuum_only_quick"]), "the chip must localize");
  assert.ok(!html.includes(">Vacuum Only Quick<"), "the sensor's English label must not reach the chip");
});

test("[PRF-6] the review profile FILTER chips localize", () => {
  const h = makeHost();
  // There are no `vocab.profile_name.*` keys and there should not be — the names already
  // live under `rooms.profile_*`. So the localized name is passed as tVocab's FALLBACK,
  // which is the arm it was built around. Minting a parallel family would be a replica, and
  // the ratchet's own lesson is that a replica inherits its parent's errors.
  assert.ok(!Object.keys(enCatalog).some((k) => k.startsWith("vocab.profile_name.")),
    "if a vocab.profile_name.* family ever appears, this fix is the wrong one");
  const state = {
    learningHistoryProfileNames: () => [
      { value: "vacuum_mop_deep", label: "Deep" },
      { value: "weekend_deep", label: "Weekend deep" },
    ],
    learningHistoryFilters: () => ({}),
    learningHistoryStatusOptions: () => [],
    learningHistoryUsedOptions: () => [],
  };
  const html = h._renderReviewChipFilter(
    "L", "profile_name",
    state.learningHistoryProfileNames().map((opt) => ({
      ...opt,
      label: h._profileDisplayName(opt.value, opt.label),
      title: h._profileDisplayName(opt.value, opt.title ?? opt.label),
    })),
    "", "all",
  );
  assert.ok(html.includes(DE["rooms.profile_deep"]), "a built-in chip must localize");
  assert.ok(html.includes("Weekend deep"), "a user-saved chip must keep its own name");
});

test("[PRF-6b] and the real call site does that mapping", () => {
  // The mapping lives at the CALL SITE, so [PRF-6] above cannot see whether the renderer
  // actually does it — the same gap FTL-5 was added for. This reads the source.
  //
  // Anchored on `_renderReviewChipFilter(` and not on `"profile_name"`: a first draft
  // searched for the field name and landed on the COMMENT above the call, 400 characters
  // from the call itself, and reported the mapping missing when it was there.
  const src = readFileSync(join(HERE, "review.js"), "utf8");
  const calls = [...src.matchAll(/_renderReviewChipFilter\([\s\S]{0,700}?\)\}/g)].map((m) => m[0]);
  const profileCall = calls.find((c) => c.includes('"profile_name"'));
  assert.ok(profileCall, "the profile_name chip filter call was not found — did it move?");
  assert.ok(profileCall.includes("_profileDisplayName("),
    "the profile_name filter must map its option labels through _profileDisplayName");
  // The sibling filters must NOT have been swept into the same mapping — their option
  // values are statuses and booleans, which have their own vocab families.
  const others = calls.filter((c) => !c.includes('"profile_name"'));
  assert.ok(others.length >= 2, "there should still be other chip filters to compare against");
  for (const c of others) {
    assert.ok(!c.includes("_profileDisplayName("), `a non-profile filter was swept in: ${c.slice(0, 80)}`);
  }
});

test("[PRF-7] the room editor localizes the built-in arm and leaves custom alone", () => {
  const h = makeHost();
  const base = {
    isCustomProfile: () => false,
    // NON-EMPTY on purpose: `_renderProfileSelector` returns "" when the profile list is
    // empty, and the meta line under test sits BELOW that early return. A first draft of
    // this stub passed [] and asserted against an empty string, which is the #70 shape —
    // a test that verifies a line the real path never reaches.
    roomProfilesList: () => [{ name: "vacuum_deep", label: "Vacuum Only Deep" }],
    customRoomProfiles: () => [],
    roomProfileDefinition: () => ({ label: "Vacuum Only Deep" }),
  };
  const builtIn = h._renderProfileSelector({
    ...base,
    currentEditorManagedProfileName: () => "vacuum_deep",
    isProtectedRoomProfile: () => true,
  }, {}, {});
  assert.ok(builtIn.includes(DE["rooms.profile_vacuum_only_deep"]), "built-in must localize");
  assert.ok(!builtIn.includes("Vacuum Only Deep"), "its English label must not survive");

  const custom = h._renderProfileSelector({
    ...base,
    roomProfileDefinition: () => ({ label: "Weekend deep" }),
    currentEditorManagedProfileName: () => "weekend_deep",
    isProtectedRoomProfile: () => false,
  }, {}, {});
  assert.ok(custom.includes("Weekend deep"), "a custom profile keeps the name the user typed");
});

/* ------------------------------------------------- the multi-room composition */

test("[PRF-8] _localizedProfile composes a name for a MULTI-ROOM job", () => {
  const h = makeHost();
  // THE FALLBACK ARM IS EVERY MULTI-ROOM JOB. The backend attaches flat setting codes only
  // for a single-room job with an archived room, so a run over two rooms carries none and
  // this returned the backend's composed ENGLISH ("Kitchen Custom").
  const multi = h._localizedProfile({
    is_custom_profile: true,
    primary_room_label: "Küche",
    profile_label: "Kitchen Custom",
    profile_subtitle: "Vacuum Only Quick",
  });
  assert.equal(multi.label, `Küche ${DE["room_editor.custom"]}`);
  assert.ok(!multi.label.includes("Custom Profile"));
  // No room at all: still the translated word, never the English composition.
  const noRoom = h._localizedProfile({ is_custom_profile: true, profile_label: "Custom" });
  assert.equal(noRoom.label, DE["room_editor.custom"]);
  // A NAMED built-in with no codes resolves through its key.
  const named = h._localizedProfile({ profile_key: "vacuum_deep", profile_label: "Vacuum Only Deep" });
  assert.equal(named.label, DE["rooms.profile_vacuum_only_deep"]);
  // And a row with real setting codes still takes the composed path, untouched by this.
  const withCodes = h._localizedProfile({
    clean_mode: "vacuum_mop", clean_intensity: "deep", selected_profile_name: "vacuum_mop_deep",
    resolved_profile_name: "vacuum_mop_deep", room_label: "Küche",
  });
  assert.ok(withCodes.label.includes(DE["vocab.clean_mode.vacuum_mop"]));
});

test("[PRF-9] the water card and the Profiles tab agree on one snapshot row", () => {
  const h = makeHost();
  // Same row, two cards, two answers, one screen apart: the Profiles tab rendered it
  // through _localizedProfile while the water card printed `profile_label` directly.
  const row = {
    profile_key: "vacuum_mop_deep", profile_label: "Kitchen Deep",
    clean_mode: "vacuum_mop", clean_intensity: "deep", fan_speed: "max", water_level: "high",
    selected_profile_name: "vacuum_mop_deep", resolved_profile_name: "vacuum_mop_deep",
    room_label: "Küche", avg_total_water_used_ml: 120, avg_robot_water_used_ml: 100,
  };
  const water = h._renderMetricsWaterProfileCard(row);
  const expected = h._localizedProfile(row).label;
  assert.ok(expected, "the row must localize at all, or this test proves nothing");
  assert.ok(water.includes(h.escapeHtml(expected)), "the water card must use the same name");
  assert.ok(!water.includes("Kitchen Deep"), "the backend's English label must not reach the title");
});

/* ------------------------------------------------------- the two derived code families */

test("[EST-1] the estimate SOURCE localizes on both of its twins", () => {
  const h = makeHost();
  h._formatLearningMinutes = (m) => `${m}m`;
  h._formatLearningWallClock = (v) => String(v);
  h.renderConfidenceChip = () => "";
  // The modal row. The census found the rooms.js twin and missed this one.
  const modal = h.renderRoomEstimateModal({
    state: {
      isRoomEstimateModalOpen: () => true,
      activeRoomEstimateDetails: () => ({
        room: { id: 1, name: "Küche" }, entry: null,
        roomEstimate: { source: "learned", minutes: 12 }, plannedWaterRoom: null,
      }),
    },
  });
  assert.ok(modal.includes(DE["vocab.estimate_source.learned"]), "the Source row must localize");
  assert.ok(!modal.includes(">learned<"), "the raw code must not reach the row");
  // An unkeyed source still reads, rather than going blank.
  assert.equal(h.tVocabRaw("estimate_source", "imported", "imported"), "imported");
});

test("[CHG-1] the charge-ended reason localizes; an unknown value passes through", () => {
  const h = makeHost();
  // battery/manager.py is the sole producer and the set is one ternary, so it is exactly
  // these two — but the family keeps its fallback because a third value would otherwise
  // render blank, and `—` is what the row shows when there is no session at all.
  assert.equal(h.tVocabRaw("charge_ended_reason", "full", "full"), DE["vocab.charge_ended_reason.full"]);
  assert.equal(h.tVocabRaw("charge_ended_reason", "stopped", "stopped"), DE["vocab.charge_ended_reason.stopped"]);
  assert.equal(h.tVocabRaw("charge_ended_reason", "interrupted", "interrupted"), "interrupted");
  assert.equal(h.tVocabRaw("charge_ended_reason", null, "—"), "—");
  // The family is named for the CHARGE session, not for the `ended_reason` field, because
  // learning/history_store.py has its own `ended_reason` with a different vocabulary.
  assert.ok(!("vocab.ended_reason.full" in enCatalog),
    "a field-named family would collide with the learning history's own ended_reason");
});

test("[CHG-2] and the battery row actually calls it", () => {
  // The call-site gate, added because the ablation refused to go red without it: [CHG-1]
  // exercises the resolver and the resolver was never the broken part. The row lives deep
  // inside `_renderMetricsBatteryTab`, which needs a whole state object to render, so this
  // is a source anchor rather than a render — the same trade FTL-5 and PRF-6b make, and the
  // weaker tool for the same reason.
  const src = readFileSync(join(HERE, "metrics.js"), "utf8");
  const row = src.slice(
    src.indexOf('metrics.battery_row_ended'),
    src.indexOf('metrics.battery_row_ended') + 400,
  );
  assert.ok(row, "the battery_row_ended row was not found — did it move?");
  assert.ok(row.includes('tVocabRaw("charge_ended_reason"'),
    "the ended-reason row must resolve the code, not print it");
  assert.ok(!/battery_row_ended[\s\S]{0,120}escapeHtml\(\s*postJob\.ended_reason/.test(row),
    "the raw code must not reach the cell directly");
});
