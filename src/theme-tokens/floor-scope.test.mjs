// Run: node --test src/theme-tokens/floor-scope.test.mjs
//
// Coverage targets (src/theme-tokens/floor-scope.js):
//   [FS-1..3]  detectFloorScope     - {known,unknown} partition; longest/whole-name resolve;
//                                      spans tokens/colors/alpha; bare-theme + envelope; dedup+sort.
//   [FS-4..6]  sliceThemeByTypes    - keeps only wanted types across all three sections;
//                                      never dash-splits; string|array names; envelope metadata.
//   [FS-7..9]  clampThemeScalars    - clamps bounded scalars to [min,max]; colors/rangeless
//                                      pass through; {envelope,corrected} count; only min or only max.
//   Internal invariants typeOfFloorKey / keyInType / floorTypeNames are reached transitively
//   through the exported entry points above (no source change).
//
// Real registry floor types (src/textures/floor-texture-registry.js), _->-, "default" dropped, sorted:
//   ["carpet-high","carpet-low","concrete","granite-light","marble","tile","wood"]

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  floorTypeNames,
  floorTypePrefix,
  keyInType,
  detectFloorScope,
  sliceThemeByTypes,
  themeKeyCount,
  clampThemeScalars,
} from "./floor-scope.js";

// ---------------------------------------------------------------------------
// floorTypeNames / prefixes / keyInType (whole-name, never dash-split)
// ---------------------------------------------------------------------------

test("[FS-0] floorTypeNames = registry types, _->-, 'default' excluded, sorted", () => {
  assert.deepEqual(floorTypeNames(), [
    "carpet-high",
    "carpet-low",
    "concrete",
    "granite-light",
    "marble",
    "tile",
    "wood",
  ]);
});

test("[FS-0b] floorTypePrefix / keyInType is a raw '{name}-' prefix check", () => {
  assert.equal(floorTypePrefix("carpet-low"), "--evcc-floor-carpet-low-");
  // A carpet-low key belongs to carpet-low.
  assert.equal(keyInType("--evcc-floor-carpet-low-base", "carpet-low"), true);
  // NOTE the real contract: keyInType is a *plain* prefix check, so passing the
  // shorter "carpet" DOES match "--evcc-floor-carpet-low-*". The whole-name /
  // longest-wins protection lives in typeOfFloorKey (exercised via detectFloorScope
  // in FS-2), which only ever tries VALID registry names ("carpet" is not one).
  assert.equal(keyInType("--evcc-floor-carpet-low-base", "carpet"), true);
  // A different real type does NOT match a carpet-low key.
  assert.equal(keyInType("--evcc-floor-carpet-low-base", "tile"), false);
  // keyInType is defensive about non-strings.
  assert.equal(keyInType(null, "tile"), false);
  assert.equal(keyInType(123, "tile"), false);
});

// ---------------------------------------------------------------------------
// detectFloorScope — known/unknown partition
// ---------------------------------------------------------------------------

test("[FS-1] detectFloorScope: known types across all 3 sections, deduped + sorted", () => {
  const envelope = {
    theme: {
      tokens: { "--evcc-floor-tile-face-opacity": 0.87, "--evcc-unrelated": 5 },
      colors: { "--evcc-floor-tile-base": "#D4AF37", "--evcc-floor-wood-base": "#7A4010" },
      alpha:  { "--evcc-floor-marble-base-opacity": 0.97 },
    },
  };
  const { known, unknown } = detectFloorScope(envelope);
  // tile appears in tokens AND colors -> deduped to one entry; sorted.
  assert.deepEqual(known, ["marble", "tile", "wood"]);
  assert.deepEqual(unknown, []);
});

test("[FS-2] detectFloorScope: longest-name-wins / never dash-split -> carpet-low, not carpet", () => {
  const envelope = {
    theme: {
      tokens: {
        "--evcc-floor-carpet-low-weave-opacity": 1,
        "--evcc-floor-carpet-high-weave-opacity": 1,
      },
    },
  };
  const { known, unknown } = detectFloorScope(envelope);
  // Resolves to the FULL multi-segment type names, never the "carpet" head segment.
  assert.deepEqual(known, ["carpet-high", "carpet-low"]);
  assert.equal(known.includes("carpet"), false);
  assert.deepEqual(unknown, []);
});

test("[FS-3] detectFloorScope: unknown --evcc-floor-* namespaces surfaced (head-segment label)", () => {
  const envelope = {
    theme: {
      // 'terrazzo' is not in this build's registry -> unknown; label is head segment.
      tokens: { "--evcc-floor-terrazzo-speckle-opacity": 0.5 },
      colors: { "--evcc-floor-tile-base": "#111", "--evcc-floor-terrazzo-base": "#222" },
    },
  };
  const { known, unknown } = detectFloorScope(envelope);
  assert.deepEqual(known, ["tile"]);
  // Both terrazzo keys collapse to the single "terrazzo" display hint.
  assert.deepEqual(unknown, ["terrazzo"]);
});

test("[FS-3b] detectFloorScope: bare theme (no .theme wrapper) and empty/garbage inputs", () => {
  // Bare theme accepted directly.
  const bare = { colors: { "--evcc-floor-wood-base": "#7A4010" } };
  assert.deepEqual(detectFloorScope(bare).known, ["wood"]);
  // Non-floor keys and missing/typed-wrong sections are ignored, not thrown on.
  const noisy = { theme: { tokens: { "--evcc-accent": 1 }, colors: null, alpha: 42 } };
  assert.deepEqual(detectFloorScope(noisy), { known: [], unknown: [] });
  // Null / undefined envelope -> empty partition, no throw.
  assert.deepEqual(detectFloorScope(null), { known: [], unknown: [] });
  assert.deepEqual(detectFloorScope(undefined), { known: [], unknown: [] });
});

// ---------------------------------------------------------------------------
// sliceThemeByTypes — keep only wanted types across the 3 sections
// ---------------------------------------------------------------------------

test("[FS-4] sliceThemeByTypes: keeps only wanted types, drops others + non-floor keys", () => {
  const envelope = {
    version: 2,
    exported_at: "2026-07-04T00:00:00Z",
    theme: {
      name: "Studio",
      tokens: {
        "--evcc-floor-tile-face-opacity": 0.87,
        "--evcc-floor-wood-grain-opacity": 0.84,
        "--evcc-not-a-floor": 9,
      },
      colors: {
        "--evcc-floor-tile-base": "#D4AF37",
        "--evcc-floor-wood-base": "#7A4010",
      },
      alpha: {
        "--evcc-floor-marble-base-opacity": 0.97,
      },
    },
  };
  const out = sliceThemeByTypes(envelope, ["tile"]);
  // Envelope metadata preserved; scope records the request.
  assert.equal(out.ok, true);
  assert.equal(out.version, 2);
  assert.equal(out.exported_at, "2026-07-04T00:00:00Z");
  assert.deepEqual(out.scope, ["tile"]);
  assert.equal(out.theme.name, "Studio");
  // Only tile survives, across the sections it appears in.
  assert.deepEqual(out.theme.tokens, { "--evcc-floor-tile-face-opacity": 0.87 });
  assert.deepEqual(out.theme.colors, { "--evcc-floor-tile-base": "#D4AF37" });
  assert.deepEqual(out.theme.alpha, {});                // no tile alpha in source
  assert.equal(themeKeyCount(out), 2);
});

test("[FS-5] sliceThemeByTypes: string name accepted; carpet-low kept, carpet-high dropped", () => {
  const envelope = {
    theme: {
      tokens: {
        "--evcc-floor-carpet-low-weave-opacity": 1,
        "--evcc-floor-carpet-high-weave-opacity": 1,
      },
      colors: {
        "--evcc-floor-carpet-low-base": "#0d0c0c",
        "--evcc-floor-carpet-high-base": "#0a0a0a",
      },
    },
  };
  // Single string (not array) is normalized to [name].
  const out = sliceThemeByTypes(envelope, "carpet-low");
  assert.deepEqual(out.scope, ["carpet-low"]);
  // Whole-name prefix match: carpet-high is NOT captured by a carpet-low request.
  assert.deepEqual(out.theme.tokens, { "--evcc-floor-carpet-low-weave-opacity": 1 });
  assert.deepEqual(out.theme.colors, { "--evcc-floor-carpet-low-base": "#0d0c0c" });
  assert.equal(themeKeyCount(out), 2);
});

test("[FS-6] sliceThemeByTypes: defaults for missing metadata; falsy names filtered", () => {
  // Missing version/exported_at/name -> stable defaults; null/"" names dropped.
  const out = sliceThemeByTypes({ theme: {} }, ["wood", null, "", false]);
  assert.equal(out.version, 1);
  assert.equal(out.exported_at, null);
  assert.equal(out.theme.name, "");
  assert.deepEqual(out.scope, ["wood"]);               // only the truthy name survives
  assert.deepEqual(out.theme.tokens, {});
  assert.deepEqual(out.theme.colors, {});
  assert.deepEqual(out.theme.alpha, {});
});

// ---------------------------------------------------------------------------
// clampThemeScalars — clamp bounded scalars, pass colors/rangeless through
// ---------------------------------------------------------------------------

test("[FS-7] clampThemeScalars: bounded scalars clamped to [min,max]; corrected counts them", () => {
  const tokenMap = {
    "--evcc-floor-tile-face-opacity": { min: 0, max: 1 },
    "--evcc-floor-wood-grain-opacity": { min: 0, max: 1 },
  };
  const envelope = {
    theme: {
      tokens: {
        "--evcc-floor-tile-face-opacity": 1.5,   // above max -> 1
        "--evcc-floor-wood-grain-opacity": -0.3, // below min -> 0
      },
    },
  };
  const { envelope: out, corrected } = clampThemeScalars(envelope, tokenMap);
  assert.equal(out.theme.tokens["--evcc-floor-tile-face-opacity"], 1);
  assert.equal(out.theme.tokens["--evcc-floor-wood-grain-opacity"], 0);
  assert.equal(corrected, 2);
});

test("[FS-7b] clampThemeScalars: in-range value untouched -> not counted; string number coerced", () => {
  const tokenMap = { "--evcc-floor-tile-face-opacity": { min: 0, max: 1 } };
  // In range: passes through, corrected stays 0.
  const inRange = clampThemeScalars(
    { theme: { tokens: { "--evcc-floor-tile-face-opacity": 0.5 } } },
    tokenMap,
  );
  assert.equal(inRange.envelope.theme.tokens["--evcc-floor-tile-face-opacity"], 0.5);
  assert.equal(inRange.corrected, 0);
  // Numeric string above max: Number("2") coerces, clamps to 1, counts as a correction.
  const strOver = clampThemeScalars(
    { theme: { tokens: { "--evcc-floor-tile-face-opacity": "2" } } },
    tokenMap,
  );
  assert.equal(strOver.envelope.theme.tokens["--evcc-floor-tile-face-opacity"], 1);
  assert.equal(strOver.corrected, 1);
});

test("[FS-8] clampThemeScalars: colors / rangeless / non-numeric pass through unchanged", () => {
  const tokenMap = {
    "--evcc-floor-tile-face-opacity": { min: 0, max: 1 },   // bounded
    "--evcc-floor-tile-base": {},                            // color: no min/max
    "--evcc-floor-tile-count": { min: 0 },                   // only min (still bounded, see FS-9)
  };
  const envelope = {
    theme: {
      colors: {
        "--evcc-floor-tile-base": "#D4AF37",   // hex, no spec range -> untouched
        "--evcc-floor-marble-base": "#e9e8e8", // not in map at all -> untouched
      },
      alpha: {
        "--evcc-floor-tile-face-opacity": "notanumber", // NaN -> passes through as-is
      },
    },
  };
  const { envelope: out, corrected } = clampThemeScalars(envelope, tokenMap);
  assert.equal(out.theme.colors["--evcc-floor-tile-base"], "#D4AF37");
  assert.equal(out.theme.colors["--evcc-floor-marble-base"], "#e9e8e8");
  // Non-numeric value with a bounded spec: Number("notanumber") is NaN -> not finite -> pass-through.
  assert.equal(out.theme.alpha["--evcc-floor-tile-face-opacity"], "notanumber");
  assert.equal(corrected, 0);
});

test("[FS-9] clampThemeScalars: only-min or only-max spec clamps just that bound", () => {
  const tokenMap = {
    "--evcc-floor-a": { min: 0 },   // no max: values above stay, below 0 -> 0
    "--evcc-floor-b": { max: 10 },  // no min: values below stay, above 10 -> 10
  };
  const envelope = {
    theme: {
      tokens: {
        "--evcc-floor-a": -5,   // below min -> 0
        "--evcc-floor-b": 42,   // above max -> 10
      },
      alpha: {
        "--evcc-floor-a": 999,  // no max cap -> unchanged
        "--evcc-floor-b": -999, // no min floor -> unchanged
      },
    },
  };
  const { envelope: out, corrected } = clampThemeScalars(envelope, tokenMap);
  assert.equal(out.theme.tokens["--evcc-floor-a"], 0);
  assert.equal(out.theme.tokens["--evcc-floor-b"], 10);
  assert.equal(out.theme.alpha["--evcc-floor-a"], 999);
  assert.equal(out.theme.alpha["--evcc-floor-b"], -999);
  assert.equal(corrected, 2); // only the two out-of-bound entries corrected
});

test("[FS-9b] clampThemeScalars: non-finite spec bounds ignored; envelope metadata spread through", () => {
  // Infinity / NaN bounds are NOT Number.isFinite -> treated as rangeless (pass-through).
  const tokenMap = { "--evcc-floor-x": { min: -Infinity, max: NaN } };
  const src = {
    ok: true,
    version: 7,
    theme: { name: "Keep", tokens: { "--evcc-floor-x": 123 } },
  };
  const { envelope: out, corrected } = clampThemeScalars(src, tokenMap);
  assert.equal(out.theme.tokens["--evcc-floor-x"], 123); // untouched
  assert.equal(corrected, 0);
  // Top-level envelope fields are preserved via spread.
  assert.equal(out.ok, true);
  assert.equal(out.version, 7);
  assert.equal(out.theme.name, "Keep");
});
