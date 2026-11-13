// Run: node --test src/renderers/theme-preview-user-materials.test.mjs
//
// A TOKEN GROUP WITH NO PREVIEW IS A CONTROL SURFACE THAT ANSWERS NOTHING.
//
// A dropped-in material mints its own editor group and its own 14 tokens, and all of
// that worked: the facet chip appeared, the group listed its controls, the sliders
// moved real custom properties. But THEME_PREVIEW_REGISTRY is a static map keyed by
// group NAME enumerating the seven shipped floor types, so the drop-in's group had no
// entry — no contextual preview mounted beside its controls, and the Floor Texture
// Preview grid (a hand-curated order, also shipped-only) had no swatch for it either.
//
// The result reads as "the render is not driving": every control present, nothing on
// screen responding. Nothing errors, because a missing registry key is simply a group
// with no preview — which is the correct, quiet behaviour for the many groups that
// genuinely have none.
//
// The animals solved this exact problem first (their names are not known at authoring
// time either) with a parameterized renderer + methodArgs + a live rebuild on a
// document event. These tests pin that the floors now follow it, and would have caught
// the gap: [TPU-1] fails without the dynamic entry, [TPU-2] without the renderer,
// [TPU-4] without the grid append.
//
// Coverage:
//   [TPU-1] a drop-in gets a registry entry under its EXACT editor group label
//   [TPU-2] the entry names a method the preview proto actually defines
//   [TPU-3] the entry passes the material id through methodArgs
//   [TPU-4] the preview grid renders a card for the drop-in, after the shipped ones
//   [TPU-5] the i18n keys the entry names exist in en.js

import { test } from "node:test";
import assert from "node:assert/strict";

import { setUserMaterials } from "../textures/user-materials.js";
import { userFloorGroupLabel } from "../theme-tokens/user-floors.js";
import { en as EN } from "../i18n/en.js";

// A drop-in, shaped exactly as mergeUserMaterials builds one. Declared and installed
// BEFORE the registry module is imported: the registry builds at module-evaluation
// time and node has no `document`, so the live rebuild listener never attaches here.
const SLATEY = {
  id: "slatey",
  key: "slatey",
  name: "Slatey",
  entry: {
    opacityDefault: 0.99,
    layers: [
      {
        url: "/eufy_vacuum/user_materials/slatey/face.png",
        role: "base",
        colorToken: "--evcc-floor-slatey-base",
        colorDefault: "#555B60",
        opacityToken: "--evcc-floor-slatey-base-opacity",
        opacityDefault: 0.95,
        primary: true,
      },
    ],
    masks: [{ url: "/eufy_vacuum/user_materials/slatey/face.png" }],
    baseTexture: "/eufy_vacuum/user_materials/slatey/face.png",
    userMaterial: true,
  },
};

setUserMaterials([SLATEY]);

const { THEME_PREVIEW_REGISTRY } = await import("./theme-preview-registry.js");
const { applyThemePreviewRenderers } = await import("./theme-preview.js");

const GROUP = userFloorGroupLabel(SLATEY);

test("[TPU-1] a drop-in gets a preview entry under its exact editor group label", () => {
  // The label is the contract between the token layer and the preview layer. Both
  // import userFloorGroupLabel rather than restating it, because a mismatch here is
  // invisible: the group renders, the preview is just silently absent.
  assert.equal(GROUP, "Floor Textures — Slatey");
  assert.ok(
    Object.prototype.hasOwnProperty.call(THEME_PREVIEW_REGISTRY, GROUP),
    `no preview entry for ${GROUP} — its controls would mount with nothing beside them`,
  );
});

test("[TPU-2] the entry names a method the preview proto actually defines", () => {
  // An entry pointing at a method that does not exist is the same defect wearing a
  // registry key: present, routed, renders nothing.
  const proto = {};
  applyThemePreviewRenderers(proto);
  const { method } = THEME_PREVIEW_REGISTRY[GROUP];
  assert.equal(typeof proto[method], "function",
    `${GROUP} routes to ${method}, which the preview proto does not define`);
});

test("[TPU-3] the entry passes the material id through methodArgs", () => {
  // One parameterized renderer serves every drop-in, so the id is the only thing
  // telling it WHICH material to draw. Without it every drop-in previews the same one.
  const entry = THEME_PREVIEW_REGISTRY[GROUP];
  assert.deepEqual(entry.methodArgs, ["slatey"]);
});

test("[TPU-4] the grid renders a card for the drop-in, after the shipped ones", () => {
  const proto = {};
  applyThemePreviewRenderers(proto);

  // A card is identified by whichever SLOT carries its key: a shipped type goes in
  // floor_type, a drop-in in floor_material, because resolveFloorType honours a
  // drop-in id only there. Reading floor_type alone would report the drop-in as
  // missing even when it rendered correctly — [CFM-5] pins the slots themselves.
  const seen = [];
  const card = {
    t: (k) => k,
    tVocabRaw: (_f, v, fb) => fb ?? String(v),
    renderRoomCard: (room) => {
      const key = room.floor_material || room.floor_type;
      seen.push(key);
      return `<div data-ft="${key}"></div>`;
    },
  };
  Object.setPrototypeOf(card, proto);

  const html = card._renderThemePreviewFloorTextures();
  assert.ok(seen.includes("slatey"),
    `the preview grid omitted the drop-in; it rendered: ${seen.join(", ")}`);
  assert.ok(html.includes('data-ft="slatey"'));

  // Appended, not interleaved: the shipped order is a curated look decision (roughly
  // hard to soft) and a user-supplied material cannot be placed in it by rule.
  assert.equal(seen[seen.length - 1], "slatey");
  assert.equal(seen[0], "tile", "the curated order must still lead");

  // The drop-in takes the SAME render path a real room does — a preview down a
  // different path would not be previewing the thing being tuned.
  assert.ok(seen.length >= 8, "shipped types plus the drop-in");
});

test("[TPU-5] the i18n keys the entry names exist in en.js", () => {
  // A titleKey that resolves to nothing renders the raw key to the user, which looks
  // like a different bug entirely.
  const { titleKey, descKey } = THEME_PREVIEW_REGISTRY[GROUP];
  for (const key of [titleKey, descKey]) {
    assert.ok(key in EN, `${key} is named by the preview entry but missing from en.js`);
  }
  // The name is substituted, not baked: one pair of keys serves every drop-in.
  assert.ok(EN[titleKey].includes("{material}"));
});
