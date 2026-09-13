// Unit tests for the guide KEY-pack loader (src/i18n/guide-loader.js).
// Run: node --test src/i18n/guide-loader.test.mjs
//
// ⚠ REWRITTEN 2026-09-12. These were [GL-1..7] against the per-FAMILY prose catalogs
// (`guideCatalog` / `loadGuideCatalog` / `ensureGuideLanguage`), which were deleted when the
// last adapter moved to key routing. The contract they guarded did not go anywhere — bundled
// English, serve the rest, fail soft, never override the bundle, add the base for a regional
// tag — it just belongs to the KEY packs now, and the key half had NO tests of its own. So the
// coverage is carried across rather than dropped with its old subject.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  guideKeyPack,
  registerGuideKeyPack,
  loadGuideKeyPack,
  ensureGuideKeyLanguage,
} from "./guide-loader.js";

const ZZ = { "rinse.clean_water_only": "zz rinse", "dry.fully_before_refit": "zz dry" };
const okResp = (obj) => ({ ok: true, json: async () => obj });

test("[GL-1] en is available synchronously from the bundle", () => {
  const en = guideKeyPack("en");
  assert.ok(en && typeof en === "object", "the bundled English pack must be sync-available");
  assert.equal(typeof en["rinse.clean_water_only"], "string");
});

test("[GL-2] loadGuideKeyPack registers a served pack", async () => {
  const ok = await loadGuideKeyPack("served:zz", "zz", { fetchImpl: async () => okResp(ZZ) });
  assert.equal(ok, true);
  assert.deepEqual(guideKeyPack("zz"), ZZ);
});

test("[GL-3] en is refused by register and load (the bundled base is not overridable)", async () => {
  const before = guideKeyPack("en");
  assert.equal(registerGuideKeyPack("en", { "rinse.clean_water_only": "clobbered" }), false);
  assert.equal(
    await loadGuideKeyPack("served:en", "en", { fetchImpl: async () => okResp({ x: "y" }) }),
    false,
  );
  assert.deepEqual(guideKeyPack("en"), before, "the bundle is the floor and must survive");
});

test("[GL-4] a failed fetch fails soft and leaves the registry intact", async () => {
  const before = guideKeyPack("en");
  const ok = await loadGuideKeyPack("served:boom", "boom", {
    fetchImpl: async () => { throw new Error("network"); },
  });
  assert.equal(ok, false);
  assert.equal(guideKeyPack("boom"), undefined);
  assert.deepEqual(guideKeyPack("en"), before, "a guide translation must never break render");
});

test("[GL-5] a non-object pack is rejected", () => {
  assert.equal(registerGuideKeyPack("nope", "not an object"), false);
  assert.equal(registerGuideKeyPack("nope2", null), false);
  assert.equal(guideKeyPack("nope"), undefined);
});

test("[GL-6] ensureGuideKeyLanguage fetches only the active language", async () => {
  const asked = [];
  await ensureGuideKeyLanguage("aa", () => {}, {
    fetchImpl: async (url) => { asked.push(String(url)); return okResp(ZZ); },
  });
  assert.equal(asked.length, 1, `fetched ${asked.length} packs, expected 1: ${asked}`);
  assert.ok(asked[0].includes("aa"), asked[0]);
});

test("[GL-7] ensureGuideKeyLanguage adds the base for a regional tag, and skips en/loaded", async () => {
  const asked = [];
  const fetchImpl = async (url) => { asked.push(String(url)); return okResp(ZZ); };

  // THE BUG THIS SHAPE GUARDS, one layer down from [LG-*]: a regional tag must fetch BOTH its
  // full form and its base, or a pack published only as `pt` never loads for a `pt-BR` reader.
  await ensureGuideKeyLanguage("pt-BR", () => {}, { fetchImpl });
  assert.ok(asked.some((u) => u.includes("pt-BR")), `no pt-BR fetch: ${asked}`);
  assert.ok(asked.some((u) => /pt(?!-)/.test(u)), `no base pt fetch: ${asked}`);

  asked.length = 0;
  await ensureGuideKeyLanguage("en", () => {}, { fetchImpl });
  assert.equal(asked.length, 0, "en is bundled and must never be fetched");

  asked.length = 0;
  await ensureGuideKeyLanguage("pt-BR", () => {}, { fetchImpl });
  assert.equal(asked.length, 0, "an already-requested language must not refetch");
});
