// Unit tests for the pure theme-editor selectors in src/state/theme.js.
//
// Coverage targets:
//   [RT-*]  resolvedTheme — 4-layer merge: (0) ROOM_FILL_PALETTE seed defaults ->
//           (1) active theme colors/alpha/tokens -> (2) working-draft overlay ->
//           (3) color+alpha combine via _hexWithAlpha; plus the `sources` provenance map.
//   [FT-*]  filteredThemeTokens — excludeKeys, modifiedOnly, group filter (incl. the
//           "modified" special case and the "Group — subgroup" prefix), global search.
//   [GS-*]  tokenMatchesGlobalThemeSearch — label/key/value/aliases/usage/affects, empty query.
//   [FP-*]  filteredPresetIds — OR-within-facet / AND-across-facets over derived tag sets,
//           name + tag substring search, and preserved library (Object.keys) order.
//
// Run: node --test src/state/theme-resolve.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";

import { applyThemeState } from "./theme.js";
import { ROOM_FILL_PALETTE } from "../cards/map-room-color.js";
import { FLOOR_TEXTURE_REGISTRY } from "../textures/floor-texture-registry.js";

// A minimal card whose _themeState is fully controllable. We never call
// _loadDeviceTheme's localStorage path in these tests because we seed
// this._themeState directly, bypassing _ensureThemeState's lazy init.
function makeCard() {
  const proto = {};
  applyThemeState(proto);
  return Object.create(proto);
}

// Build a card with an explicit theme state so _ensureThemeState returns ours
// (it only initializes when _themeState is falsy). `library`/`activeThemeId`/
// `workingDraft`/`presetFacets`/`presetSearchQuery`/filter fields are the knobs.
function cardWithState(over = {}) {
  const c = makeCard();
  c._themeState = {
    library: {},
    activeThemeId: null,
    workingDraft: { tokens: {}, colors: {}, alpha: {} },
    // UI-filter fields read by filteredThemeTokens
    tokenSearchQuery: "",
    modifiedOnly: false,
    selectedGroupFilter: "all",
    // preset-filter fields read by filteredPresetIds
    presetFacets: {},
    presetSearchQuery: "",
    _presetTags: null,
    // themeMode must NOT be "device" or effectiveActiveThemeId branches into it
    themeMode: "system",
    deviceThemeId: null,
    ...over,
  };
  return c;
}

/* =========================================================================
   resolvedTheme — the 4-layer deterministic merge
   ========================================================================= */

test("[RT-1] resolvedTheme seeds every room-fill token to the default palette with source 'default'", () => {
  const c = cardWithState();
  const { tokens, sources } = c.resolvedTheme();
  ROOM_FILL_PALETTE.forEach((hex, i) => {
    const key = `--evcc-room-fill-${i + 1}`;
    // _hexWithAlpha with null alpha returns the trimmed hex unchanged (6-char stays 6-char).
    assert.equal(tokens[key], hex, `${key} seed value`);
    assert.equal(sources[key], "default", `${key} seed source`);
  });
  // No active theme + no draft -> every resolved token is a SEED default
  // (room-fill palette + floor-texture material defaults) — none 'theme'/'draft'.
  assert.ok(Object.keys(sources).length >= ROOM_FILL_PALETTE.length);
  for (const src of Object.values(sources)) assert.equal(src, "default");
});

test("[RT-1b] resolvedTheme seeds floor-texture editor tokens from the render registry; computed -eff layers are skipped", () => {
  const c = cardWithState();
  const { tokens, sources } = c.resolvedTheme();

  // A representative NEW token: carpet_low weave color + its layer opacity, sourced
  // from the render registry so the editor swatch opens at the material's real value.
  const weave = FLOOR_TEXTURE_REGISTRY.carpet_low.layers.find(
    (l) => l.colorToken === "--evcc-floor-carpet-low-weave"
  );
  assert.ok(weave, "registry has the carpet-low weave layer");
  assert.equal(tokens["--evcc-floor-carpet-low-weave"], weave.colorDefault);
  assert.equal(sources["--evcc-floor-carpet-low-weave"], "default");
  assert.equal(tokens["--evcc-floor-carpet-low-weave-opacity"], String(weave.opacityDefault));
  assert.equal(sources["--evcc-floor-carpet-low-weave-opacity"], "default");

  // The other new material's detail color (granite aggregate) is seeded too.
  assert.equal(sources["--evcc-floor-granite-light-aggregate"], "default");

  // The computed marble vein "-eff" layers are NOT editor tokens (not in
  // THEME_TOKEN_MAP), so their oklch()/calc() defaults must NOT leak into the seed.
  assert.equal(sources["--evcc-floor-marble-vein-minor-color-eff"], undefined);
  assert.equal(tokens["--evcc-floor-marble-vein-minor-color-eff"], undefined);

  // The global map-texture rotation is seeded to "0" (neutral) so its editor slider centres.
  assert.equal(tokens["--evcc-floor-texture-map-rotate"], "0");
  assert.equal(sources["--evcc-floor-texture-map-rotate"], "default");
});

test("[RT-2] active theme overrides the palette seed and stamps source 'theme'", () => {
  const c = cardWithState({
    activeThemeId: "t1",
    library: {
      t1: {
        colors: { "--evcc-room-fill-1": "#111111", "--evcc-accent": "#222222" },
        tokens: { "--evcc-radius": "8px" },
      },
    },
  });
  const { tokens, sources } = c.resolvedTheme();
  assert.equal(tokens["--evcc-room-fill-1"], "#111111"); // theme beat the seed
  assert.equal(sources["--evcc-room-fill-1"], "theme");
  assert.equal(tokens["--evcc-accent"], "#222222");
  assert.equal(sources["--evcc-accent"], "theme");
  // A pure token (no color) passes through the tokens bucket untouched by the combine step.
  assert.equal(tokens["--evcc-radius"], "8px");
  assert.equal(sources["--evcc-radius"], "theme");
  // Untouched palette slots still carry the default.
  assert.equal(tokens["--evcc-room-fill-2"], ROOM_FILL_PALETTE[1]);
  assert.equal(sources["--evcc-room-fill-2"], "default");
});

test("[RT-3] working draft is the top layer — beats both seed and active theme", () => {
  const c = cardWithState({
    activeThemeId: "t1",
    library: { t1: { colors: { "--evcc-accent": "#aaaaaa" } } },
    workingDraft: {
      colors: { "--evcc-accent": "#bbbbbb", "--evcc-room-fill-1": "#cccccc" },
      alpha: {},
      tokens: {},
    },
  });
  const { tokens, sources } = c.resolvedTheme();
  assert.equal(tokens["--evcc-accent"], "#bbbbbb");        // draft > theme
  assert.equal(sources["--evcc-accent"], "draft");
  assert.equal(tokens["--evcc-room-fill-1"], "#cccccc");   // draft > seed
  assert.equal(sources["--evcc-room-fill-1"], "draft");
});

test("[RT-4] alpha is baked into the hex via _hexWithAlpha (0..1 -> 8-char)", () => {
  const c = cardWithState({
    activeThemeId: "t1",
    library: { t1: { colors: { "--evcc-accent": "#ff8800" }, alpha: { "--evcc-accent": 0.5 } } },
  });
  const { tokens } = c.resolvedTheme();
  // 0.5 * 255 = 127.5 -> round 128 -> 0x80.
  assert.equal(tokens["--evcc-accent"], "#ff880080");
});

test("[RT-5] an alpha-only draft change re-bakes the theme color (the bug the combine step defends)", () => {
  // Theme sets both color and full alpha; draft overrides ONLY alpha. The final
  // combine must apply the draft alpha to the theme color, not keep a stale bake.
  const c = cardWithState({
    activeThemeId: "t1",
    library: { t1: { colors: { "--evcc-accent": "#010203" }, alpha: { "--evcc-accent": 1 } } },
    workingDraft: { colors: {}, alpha: { "--evcc-accent": 0 }, tokens: {} },
  });
  const { tokens, sources } = c.resolvedTheme();
  assert.equal(tokens["--evcc-accent"], "#01020300"); // alpha 0 -> 00, color kept
  // Color came from theme, alpha overridden by draft -> alpha entry wins the source stamp.
  assert.equal(sources["--evcc-accent"], "draft");
});

test("[RT-6] alpha clamps to [0,1]; out-of-range and NaN handled", () => {
  const c = cardWithState({
    activeThemeId: "t1",
    library: {
      t1: {
        colors: { "--evcc-a": "#000000", "--evcc-b": "#000000", "--evcc-c": "#000000" },
        alpha: { "--evcc-a": 5, "--evcc-b": -2, "--evcc-c": "nope" },
      },
    },
  });
  const { tokens } = c.resolvedTheme();
  assert.equal(tokens["--evcc-a"], "#000000ff"); // clamp high -> 1.0 -> ff
  assert.equal(tokens["--evcc-b"], "#00000000"); // clamp low  -> 0.0 -> 00
  // NaN alpha -> _hexWithAlpha returns the trimmed input unchanged (the 6-char color).
  assert.equal(tokens["--evcc-c"], "#000000");
});

test("[RT-7] an 8-char color is re-based when an alpha is supplied; a non-hex color passes through", () => {
  const c = cardWithState({
    activeThemeId: "t1",
    library: {
      t1: {
        colors: { "--evcc-a": "#11223344", "--evcc-b": "rgb(1,2,3)" },
        alpha: { "--evcc-a": 1 },
      },
    },
  });
  const { tokens } = c.resolvedTheme();
  assert.equal(tokens["--evcc-a"], "#112233ff"); // existing alpha stripped, new one applied
  assert.equal(tokens["--evcc-b"], "rgb(1,2,3)"); // not 6/8-char hex -> unchanged
});

test("[RT-8] device-pinned theme with a valid library entry resolves via effectiveActiveThemeId", () => {
  const c = cardWithState({
    activeThemeId: "backend",
    themeMode: "device",
    deviceThemeId: "pinned",
    library: {
      backend: { colors: { "--evcc-accent": "#000001" } },
      pinned: { colors: { "--evcc-accent": "#000002" } },
    },
  });
  const { tokens } = c.resolvedTheme();
  assert.equal(tokens["--evcc-accent"], "#000002"); // the pinned device theme, not backend
});

/* =========================================================================
   filteredThemeTokens
   ========================================================================= */

const REG = [
  { key: "--evcc-accent", label: "Accent", group: "Shared Foundations" },
  { key: "--evcc-surface", label: "Surface", group: "Shared Foundations" },
  { key: "--evcc-cat-eye", label: "Cat Eye", group: "Animal Companion — Cat" },
  { key: "--evcc-dog-eye", label: "Dog Eye", group: "Animal Companion — Dog" },
];

// Resolve tokens/sources against a fixed active theme so `source`/`value` are known.
function ftCard(over = {}) {
  return cardWithState({
    activeThemeId: "t1",
    library: { t1: { colors: { "--evcc-accent": "#123456" } } },
    workingDraft: { colors: { "--evcc-surface": "#abcdef" }, alpha: {}, tokens: {} },
    ...over,
  });
}

test("[FT-1] excludeKeys drops matched tokens (only a real Set is honored)", () => {
  const c = ftCard();
  const keys = c
    .filteredThemeTokens(REG, { excludeKeys: new Set(["--evcc-accent"]) })
    .map((t) => t.key);
  assert.ok(!keys.includes("--evcc-accent"));
  assert.ok(keys.includes("--evcc-surface"));
  // A non-Set excludeKeys is ignored (falls back to an empty Set) -> nothing excluded.
  const all = c.filteredThemeTokens(REG, { excludeKeys: ["--evcc-accent"] }).map((t) => t.key);
  assert.ok(all.includes("--evcc-accent"));
});

test("[FT-2] modifiedOnly keeps only draft-sourced tokens", () => {
  const c = ftCard({
    activeThemeId: "t1",
    library: { t1: { colors: { "--evcc-accent": "#123456" } } },
    workingDraft: { colors: { "--evcc-surface": "#abcdef" }, alpha: {}, tokens: {} },
    modifiedOnly: true,
  });
  const keys = c.filteredThemeTokens(REG).map((t) => t.key);
  // --evcc-surface is draft-owned; --evcc-accent is theme; the rest are unset (source 'ha').
  assert.deepEqual(keys, ["--evcc-surface"]);
});

test("[FT-3] group filter 'modified' == draft-only (independent of modifiedOnly flag)", () => {
  const c = ftCard({ selectedGroupFilter: "modified" });
  const keys = c.filteredThemeTokens(REG).map((t) => t.key);
  assert.deepEqual(keys, ["--evcc-surface"]); // only the draft-sourced one
});

test("[FT-4] exact-group filter keeps that group AND its 'Group — subgroup' children", () => {
  const c = ftCard({ selectedGroupFilter: "Animal Companion" });
  const keys = c.filteredThemeTokens(REG).map((t) => t.key);
  // Neither def's group === "Animal Companion", but both start with the "— " prefix.
  assert.deepEqual(keys.sort(), ["--evcc-cat-eye", "--evcc-dog-eye"]);

  const shared = ftCard({ selectedGroupFilter: "Shared Foundations" });
  const sKeys = shared.filteredThemeTokens(REG).map((t) => t.key);
  assert.deepEqual(sKeys.sort(), ["--evcc-accent", "--evcc-surface"]);
});

test("[FT-5] 'all' filter keeps everything; global search narrows by label/key/value", () => {
  const c = ftCard();
  assert.equal(c.filteredThemeTokens(REG).length, REG.length); // 'all' default

  // Search on label substring.
  const byLabel = ftCard({ tokenSearchQuery: "cat" }).filteredThemeTokens(REG).map((t) => t.key);
  assert.deepEqual(byLabel, ["--evcc-cat-eye"]);

  // Search on the resolved value: --evcc-accent resolves to #123456 from the theme.
  const byValue = ftCard({ tokenSearchQuery: "123456" }).filteredThemeTokens(REG).map((t) => t.key);
  assert.deepEqual(byValue, ["--evcc-accent"]);

  // A query that matches nothing -> empty.
  assert.equal(ftCard({ tokenSearchQuery: "zzz-nomatch" }).filteredThemeTokens(REG).length, 0);
});

/* =========================================================================
   tokenMatchesGlobalThemeSearch  (also exercised through filteredThemeTokens)
   ========================================================================= */

test("[GS-1] empty query matches everything", () => {
  const c = makeCard();
  assert.equal(c.tokenMatchesGlobalThemeSearch({ key: "--x", label: "X" }, "val", ""), true);
  assert.equal(c.tokenMatchesGlobalThemeSearch({ key: "--x" }, "", null), true);
});

test("[GS-2] matches label, key, value, and each optional metadata array (case-insensitive)", () => {
  const c = makeCard();
  const def = {
    label: "Primary Accent",
    key: "--evcc-accent",
    aliases: ["Brand"],
    usage: ["buttons"],
    affects: ["Header"],
  };
  assert.equal(c.tokenMatchesGlobalThemeSearch(def, "", "PRIMARY"), true); // label, case-insens
  assert.equal(c.tokenMatchesGlobalThemeSearch(def, "", "accent"), true);  // key
  assert.equal(c.tokenMatchesGlobalThemeSearch(def, "#FF0000", "ff0000"), true); // value
  assert.equal(c.tokenMatchesGlobalThemeSearch(def, "", "brand"), true);   // alias
  assert.equal(c.tokenMatchesGlobalThemeSearch(def, "", "button"), true);  // usage
  assert.equal(c.tokenMatchesGlobalThemeSearch(def, "", "header"), true);  // affects
  assert.equal(c.tokenMatchesGlobalThemeSearch(def, "", "nomatch"), false);
});

test("[GS-3] missing/non-array metadata is treated as empty (no throw)", () => {
  const c = makeCard();
  // aliases/usage/affects absent, and a null tokenDef value slot.
  assert.equal(c.tokenMatchesGlobalThemeSearch({ label: "Foo" }, "", "foo"), true);
  assert.equal(c.tokenMatchesGlobalThemeSearch(null, "", "foo"), false); // null def, real query
  // A non-array `aliases` must not crash and must not match.
  assert.equal(c.tokenMatchesGlobalThemeSearch({ aliases: "brand" }, "", "brand"), false);
});

/* =========================================================================
   filteredPresetIds — facet AND/OR + search + order
   ========================================================================= */

// Themes with palettes whose derived tags are known (verified against the real
// deriveThemeTags): a light+blue theme, a dark+blue theme, and a light+red theme.
const LIGHT_BLUE = { "--evcc-surface-base": "#ffffff", "--evcc-accent": "#3b82f6", "--evcc-text-primary": "#000000" };
const DARK_BLUE  = { "--evcc-surface-base": "#000000", "--evcc-accent": "#3b82f6", "--evcc-text-primary": "#ffffff" };
const LIGHT_RED  = { "--evcc-surface-base": "#ffffff", "--evcc-accent": "#ff0000", "--evcc-text-primary": "#000000" };

function presetCard(over = {}) {
  return cardWithState({
    library: {
      lb: { name: "Aurora", colors: LIGHT_BLUE, source: "community", tags: ["cosmic"] },
      db: { name: "Midnight", colors: DARK_BLUE, source: "core" },
      lr: { name: "Sunset", colors: LIGHT_RED, source: "manual" },
    },
    ...over,
  });
}

test("[FP-0] library order (Object.keys insertion order) is preserved through the filter", () => {
  const c = presetCard();
  assert.deepEqual(c.filteredPresetIds(), ["lb", "db", "lr"]); // no filters -> all, in order
});

test("[FP-1] single facet is OR within itself (mode: light OR dark keeps both)", () => {
  const c = presetCard({ presetFacets: { mode: ["light", "dark"] } });
  // lb=light, db=dark, lr=light -> all three still match.
  assert.deepEqual(c.filteredPresetIds(), ["lb", "db", "lr"]);

  const onlyLight = presetCard({ presetFacets: { mode: ["light"] } });
  assert.deepEqual(onlyLight.filteredPresetIds(), ["lb", "lr"]); // db is dark -> dropped
});

test("[FP-2] facets AND across each other (mode=light AND accent=blue -> only lb)", () => {
  const c = presetCard({ presetFacets: { mode: ["light"], accent: ["blue"] } });
  // lb: light+blue -> keep. lr: light+red -> fails accent. db: blue but dark -> fails mode.
  assert.deepEqual(c.filteredPresetIds(), ["lb"]);
});

test("[FP-3] a facet with no matching theme drops everything", () => {
  const c = presetCard({ presetFacets: { accent: ["teal"] } });
  assert.deepEqual(c.filteredPresetIds(), []); // no theme is teal
});

test("[FP-4] an empty facet selection array is a no-op (the selected.length guard)", () => {
  // togglePresetFacet never leaves [] behind, but setting it directly must be inert.
  const c = presetCard({ presetFacets: { mode: [] } });
  assert.deepEqual(c.filteredPresetIds(), ["lb", "db", "lr"]);
});

test("[FP-5] `source` is a usable filter token (added by _presetTagsForLibrary)", () => {
  const c = presetCard({ presetFacets: { source: ["community"] } });
  assert.deepEqual(c.filteredPresetIds(), ["lb"]); // only the community theme
  const core = presetCard({ presetFacets: { source: ["core"] } });
  assert.deepEqual(core.filteredPresetIds(), ["db"]);
});

test("[FP-6] search matches the theme name; the setter case-folds the query", () => {
  const c = presetCard({ presetSearchQuery: "sunset" });
  assert.deepEqual(c.filteredPresetIds(), ["lr"]);
  // filteredPresetIds does a raw haystack.includes(query) — case-insensitivity is the
  // setter's job (it lowercases). Route an uppercase query through it to prove the path.
  const upper = presetCard();
  upper.setPresetSearchQuery("MID"); // -> stored as "mid"
  assert.deepEqual(upper.filteredPresetIds(), ["db"]); // matches "Midnight"
});

test("[FP-7] search matches a derived/vibe tag, and falls back to the id when name is absent", () => {
  // "cosmic" is a vibe tag only on lb.
  const byVibe = presetCard({ presetSearchQuery: "cosmic" });
  assert.deepEqual(byVibe.filteredPresetIds(), ["lb"]);

  // "red" is a derived accent tag only on lr.
  const byDerived = presetCard({ presetSearchQuery: "red" });
  assert.deepEqual(byDerived.filteredPresetIds(), ["lr"]);

  // No name -> the haystack uses the id. Query the id substring.
  const noName = cardWithState({
    library: { theme_xyz: { colors: LIGHT_BLUE } },
    presetSearchQuery: "xyz",
  });
  assert.deepEqual(noName.filteredPresetIds(), ["theme_xyz"]);
});

test("[FP-8] facet AND search combine (both must pass)", () => {
  // mode=light keeps lb+lr; search 'aurora' narrows to lb.
  const c = presetCard({ presetFacets: { mode: ["light"] }, presetSearchQuery: "aurora" });
  assert.deepEqual(c.filteredPresetIds(), ["lb"]);
  // Same facet but a search that matches only the DROPPED theme -> empty.
  const none = presetCard({ presetFacets: { mode: ["light"] }, presetSearchQuery: "midnight" });
  assert.deepEqual(none.filteredPresetIds(), []);
});

test("[FP-9] empty library -> empty result (no crash on the derived-tag cache)", () => {
  const c = cardWithState({ library: {} });
  assert.deepEqual(c.filteredPresetIds(), []);
});
