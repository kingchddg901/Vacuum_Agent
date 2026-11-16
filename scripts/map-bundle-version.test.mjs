// Run: node --test scripts/map-bundle-version.test.mjs
//
// [MAPV-*] THE ONE BUNDLE NOTHING COULD CACHE-BUST.
//
// The panel and cards bundles reach the browser through `_frontend_url.py`, which appends
// `?v=<mtime>` when Home Assistant mints their URLs. The map bundle is not minted by HA at
// all: the dashboard card pulls it in with a runtime
// `import("/eufy_vacuum/frontend/eufy-vacuum-map.js")` — a URL hard-coded in JS, carrying
// no version. A deploy that changed that 1.5 MB bundle therefore left every browser on the
// old copy, and nothing in the repo could tell.
//
// IT WAS NOT A SERVICE WORKER, which is the belief this sat behind for a long time and the
// reason it went unfixed. Measured 2026-11-16 on the live box at http://192.168.4.104:8123:
// `isSecureContext` false, `serviceWorker` absent from `navigator`, `caches` undefined — a
// LAN IP over plain HTTP is not a secure context, so no worker can register and none does.
// It was ordinary HTTP caching of a URL that never moved. The symptom is identical either
// way, which is exactly why the wrong cause survived being repeated.
//
// Coverage
// --------
// [MAPV-1] the import carries a version, and takes it from the build-injected token
// [MAPV-2] the build defines __MAP_VER__ for the bundles that CONSUME the map, not for it
// [MAPV-3] the map host is built BEFORE its consumers — the hash depends on that order

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const BUILD = readFileSync("scripts/build-card.mjs", "utf8");
const CARD = readFileSync("src/cards/dashboard-card.js", "utf8");

test("[MAPV-1] the map import is versioned from the build-injected token", () => {
  // THE RED INPUT is dropping the query string — which is what shipped, and which looks
  // perfectly correct in review because the URL is right and the module loads.
  assert.match(
    CARD,
    /import\(\s*`\/eufy_vacuum\/frontend\/eufy-vacuum-map\.js\?v=\$\{MAP_VER\}`/,
    "the lazily-imported map bundle must carry ?v=${MAP_VER}; without it a deploy cannot " +
    "reach a browser that already has the old copy",
  );

  // And MAP_VER must degrade to a literal when unbundled, the way _ASSET_VER and
  // SHIPPED_LOCALE_VER do — an undefined identifier here would throw at import time in
  // any context esbuild did not define it for.
  assert.match(
    CARD,
    /const MAP_VER\s*=\s*\(typeof __MAP_VER__ !== "undefined"\)\s*\?\s*__MAP_VER__\s*:\s*"dev"/,
    "MAP_VER must fall back to \"dev\" when the define is absent",
  );
});

test("[MAPV-2] the build injects __MAP_VER__ into the consumers", () => {
  assert.match(BUILD, /__MAP_VER__:\s*JSON\.stringify\(mapVer\)/,
    "the token must be injected as a compile-time define, like __ASSET_VER__");

  // Hashed from the OUTPUT, not from sources. Hashing src/ would bust a 1.5 MB bundle on
  // any source change anywhere, including ones that cannot reach it.
  assert.match(BUILD, /createHash\("sha256"\)\.update\(readFileSync\(mapOut\)\)/,
    "the token must be a function of the bytes actually served");
});

test("[MAPV-3] the map host is built BEFORE the bundles that import it", () => {
  // THE SUBTLE ONE. The hash reads the map bundle off disk, so building it after its
  // consumers would hash the PREVIOUS run's output — a token that is stale by exactly one
  // build, and correct-looking in every log. On a clean tree it would throw instead, which
  // is the lucky case; on a warm tree it silently ships yesterday's version.
  const mapBuild = BUILD.indexOf('entryPoints: ["src/cards/vacuum-map-host.js"]');
  const hash = BUILD.indexOf("createHash(");
  const cards = BUILD.indexOf('entryPoints: ["src/cards-standalone.js"]');
  const panel = BUILD.indexOf('entryPoints: ["src/all-cards.js"]');

  assert.ok(mapBuild > 0 && hash > 0 && cards > 0 && panel > 0, "all four sites must exist");
  assert.ok(mapBuild < hash, "the map bundle must be BUILT before it is hashed");
  assert.ok(hash < cards && hash < panel,
    "it must be hashed before the bundles that embed the token are built; reorder these " +
    "and the token silently becomes the previous build's");
});
