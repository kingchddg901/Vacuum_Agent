// Run: node --test src/renderers/theme-preview-coverage.test.mjs
//
// [TPC-*] EVERY TOKEN GROUP HAS A PREVIEW, OR SAYS WHY NOT.
//
// WHY THIS EXISTS. `_renderThemePreviewPane` returns "" for a group with no entry in
// THEME_PREVIEW_REGISTRY, and the pane then renders nothing at all. That is a silent,
// correct-looking outcome: the editor shows the group's controls with an empty column
// beside them, which is indistinguishable from a group whose preview simply has little
// to draw. So "Map" — the LARGEST group at 34 of 434 tokens — has had no preview since
// the pane was built, and nobody noticed.
//
// The value here is not Map. Map is allowlisted below with its reason. The value is the
// NEXT group someone adds: "Dashboard Cards" was added in this same body of work and
// would have shipped previewless but for a deliberate decision to build one. Nothing
// would have said so.
//
// WHY A NODE TEST AND NOT A HARNESS SPEC. This is two registries compared. It needs no
// browser, so it belongs in `npm run test:units`, which CI already runs — a spec would
// have needed its own line in card-visual.yml, and the whole point is a gate nobody has
// to remember to wire.
//
// SCOPE, stated because it is a real limit. The two DYNAMIC group families — animals and
// user floor materials — are built from the same roster as their preview entries
// (buildAnimalSubgroupEntries, and the userFloorGroupLabel loop in
// theme-preview-registry.js), so they cannot drift apart by construction and are not
// what this guards. At import time, with no user materials present, this sees the static
// set plus the bundled-animal fallback. That is also what CI sees.
//
// Coverage
// --------
// [TPC-1] every live group has a preview entry, or an ALLOWLIST entry with a reason
// [TPC-2] no preview entry points at a group that no longer exists
// [TPC-3] allowlist hygiene — an entry that is now covered, or is no longer a group

import { test } from "node:test";
import assert from "node:assert/strict";
import { THEME_TOKEN_REGISTRY, THEME_GROUPS } from "../theme-tokens/index.js";
import { THEME_PREVIEW_REGISTRY } from "./theme-preview-registry.js";

/**
 * Groups that deliberately have no preview. Each MUST carry a reason, and the reason
 * must be about the SURFACE, not about effort — "nobody got round to it" is what
 * [TPC-1] exists to surface rather than record.
 */
const ALLOWLIST = {
  "Map": "The map is a canvas painted from live raster data — room pixels, a floor " +
    "texture atlas and the robot's own path — none of which the editor has. The other " +
    "26 previews render a real surface from a small fixture; a map preview would need " +
    "a fixture map, and a drawn mock of one would be the facsimile trap this file's " +
    "siblings exist to avoid (see docs/dev/00c-replicas.md RNJE1GDZ). Its 34 tokens " +
    "are previewed, in effect, by the live map one tab away.",
};

const tokensPerGroup = THEME_TOKEN_REGISTRY.reduce((acc, t) => {
  acc[t.group] = (acc[t.group] ?? 0) + 1;
  return acc;
}, {});

test("[TPC-1] every token group has a preview, or a reasoned allowlist entry", () => {
  // THE RED INPUT: add a group to src/theme-tokens/groups.js without adding a row to
  // THEME_PREVIEW_REGISTRY. That is exactly what happened with "Dashboard Cards", and
  // the only thing that caught it was deciding to build the preview anyway.
  const covered = new Set(Object.keys(THEME_PREVIEW_REGISTRY));
  const allowed = new Set(Object.keys(ALLOWLIST));

  const uncovered = THEME_GROUPS
    .filter((g) => !covered.has(g) && !allowed.has(g))
    .map((g) => `${g} (${tokensPerGroup[g] ?? 0} tokens)`);

  assert.deepEqual(uncovered, [],
    "these groups render an EMPTY preview pane, which looks the same as a sparse one.\n" +
    "Add a THEME_PREVIEW_REGISTRY entry, or an ALLOWLIST entry stating what about the\n" +
    "SURFACE makes it unpreviewable:\n  " + uncovered.join("\n  "));
});

test("[TPC-2] no preview entry points at a group that no longer exists", () => {
  // THE RED INPUT: rename a group in groups.js and leave its preview row behind. The
  // orphaned row is unreachable — currentThemePreviewGroup() can only return a live
  // group name — so it is dead weight that reads as coverage. [TPC-1] cannot see this
  // direction at all: it only asks whether groups have previews, never the reverse.
  const live = new Set(THEME_GROUPS);
  const orphans = Object.keys(THEME_PREVIEW_REGISTRY).filter((g) => !live.has(g));
  assert.deepEqual(orphans, [],
    "preview entries for groups that are not in THEME_GROUPS — unreachable, and they\n" +
    "make the coverage count look better than it is:\n  " + orphans.join("\n  "));
});

test("[TPC-3] the allowlist has no stale entries", () => {
  // THE RED INPUT: build a preview for an allowlisted group and leave the allowlist
  // entry, or rename the group. Both leave a standing excuse for a problem that no
  // longer exists, which is how an allowlist quietly becomes a list of things nobody
  // rechecks. Same hygiene clause as gallery-completeness.spec.mjs.
  const live = new Set(THEME_GROUPS);
  const covered = new Set(Object.keys(THEME_PREVIEW_REGISTRY));

  const notAGroup = Object.keys(ALLOWLIST).filter((g) => !live.has(g));
  assert.deepEqual(notAGroup, [],
    "allowlisted names that are not groups any more:\n  " + notAGroup.join("\n  "));

  const nowCovered = Object.keys(ALLOWLIST).filter((g) => covered.has(g));
  assert.deepEqual(nowCovered, [],
    "allowlisted groups that DO have a preview now — delete the excuse:\n  " +
    nowCovered.join("\n  "));

  for (const [group, reason] of Object.entries(ALLOWLIST)) {
    assert.ok(reason && reason.length > 40,
      `${group}: an allowlist entry needs a reason about the surface, not a placeholder`);
  }
});
