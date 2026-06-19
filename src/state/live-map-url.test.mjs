// Unit tests for _liveMapImageUrl — the live-map backdrop URL + camera cache-bust.
// A camera entity's entity_picture token is stable, so we append last_updated to
// force <img> refetches at frame cadence; an image entity's URL already rotates.
// Run: node --test src/state/live-map-url.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState(overrides) {
  const proto = {};
  applyMapState(proto);
  const s = Object.create(proto);
  Object.assign(s, overrides);
  return s;
}

test("[LMU-1] camera backdrop gets a last_updated cache-bust appended", () => {
  const s = makeState({
    liveMapImageEntity: () => "camera.alfred_map",
    entity: (eid) =>
      eid === "camera.alfred_map"
        ? {
            attributes: { entity_picture: "/api/camera_proxy/camera.alfred_map?token=abc" },
            last_updated: "2026-06-16T00:00:02.000Z",
          }
        : null,
  });
  const url = s._liveMapImageUrl();
  assert.ok(url.startsWith("/api/camera_proxy/camera.alfred_map?token=abc&_="));
  assert.equal(url.split("&_=")[1], String(Date.parse("2026-06-16T00:00:02.000Z")));
});

test("[LMU-2] a picture URL with no query gets ?_= (not &_=)", () => {
  const s = makeState({
    liveMapImageEntity: () => "image.alfred_6",
    entity: () => ({
      attributes: { entity_picture: "/foo/bar.png" },
      last_updated: "2026-06-16T00:00:00.000Z",
    }),
  });
  assert.ok(s._liveMapImageUrl().startsWith("/foo/bar.png?_="));
});

test("[LMU-3] no live entity / no picture -> null", () => {
  assert.equal(
    makeState({ liveMapImageEntity: () => null, entity: () => null })._liveMapImageUrl(),
    null,
  );
  assert.equal(
    makeState({
      liveMapImageEntity: () => "camera.x",
      entity: () => ({ attributes: {} }),
    })._liveMapImageUrl(),
    null,
  );
});

test("[LMU-4] missing last_updated -> URL returned unbusted", () => {
  const s = makeState({
    liveMapImageEntity: () => "camera.x",
    entity: () => ({ attributes: { entity_picture: "/p?token=z" } }),
  });
  assert.equal(s._liveMapImageUrl(), "/p?token=z");
});

test("[LMU-5] camera URL advances on bumpLiveMapTick (poll refresh); image.* unaffected", () => {
  const cam = makeState({
    liveMapImageEntity: () => "camera.alfred_map",
    entity: () => ({
      attributes: { entity_picture: "/api/camera_proxy/camera.alfred_map?token=abc" },
      last_updated: "2026-06-16T00:00:02.000Z",
    }),
  });
  const camBefore = cam._liveMapImageUrl();
  cam.bumpLiveMapTick();
  assert.notEqual(cam._liveMapImageUrl(), camBefore); // a poll changes the URL -> <img> refetches

  // image.* rotates its own token per frame, so the tick must NOT alter its URL.
  const img = makeState({
    liveMapImageEntity: () => "image.alfred_6",
    entity: () => ({
      attributes: { entity_picture: "/p?token=t" },
      last_updated: "2026-06-16T00:00:02.000Z",
    }),
  });
  const imgBefore = img._liveMapImageUrl();
  img.bumpLiveMapTick();
  assert.equal(img._liveMapImageUrl(), imgBefore);
});

test("[LIVE-1] a live-pinned layout shows the live URL, ignoring any uploaded variant", () => {
  const s = makeState();
  s._mapSegmentsData = {
    segmentation_mode: "custom",
    custom_layouts: [{ id: "L1", name: "Live map", backdrop_source: "live" }],
    active_custom_layout_id: "L1",
    image_variants: { custom_L1: { browser_url: "/uploaded.png" } }, // must be ignored
  };
  s.liveMapImageEntity = () => "camera.alfred_map";
  s.entity = () => ({
    attributes: { entity_picture: "/api/camera_proxy/camera.alfred_map?token=t" },
    last_updated: "2026-06-16T00:00:02.000Z",
  });
  assert.ok(s.mapImageUrl().startsWith("/api/camera_proxy/camera.alfred_map?token=t&_="));
  assert.equal(s.isLiveBackdropActive(), true);
});

test("[LIVE-2] a normal layout with an uploaded backdrop is NOT live-backed", () => {
  const s = makeState();
  s._mapSegmentsData = {
    segmentation_mode: "custom",
    custom_layouts: [{ id: "L2", name: "Blueprint", backdrop_variant: "custom_L2" }],
    active_custom_layout_id: "L2",
    image_variants: { custom_L2: { browser_url: "/uploaded.png" } },
  };
  s.liveMapImageEntity = () => "camera.alfred_map";
  s.entity = () => ({ attributes: { entity_picture: "/p?token=t" }, last_updated: "2026-06-16T00:00:00Z" });
  assert.equal(s.mapImageUrl(), "/uploaded.png");
  assert.equal(s.isLiveBackdropActive(), false);
});
