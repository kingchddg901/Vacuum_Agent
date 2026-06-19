// Unit tests for the Phase B live-pose merge — setLivePose/livePose/mapOverlayData.
// The fork's fresh in-memory pose (polled ~2s) overrides ONLY the moving overlay fields
// (robot/dock/current-room/heading/path) while the static segmentation (rooms/area/
// hazards/image_size) stays from the slower snapshot. Run: node --test src/state/live-pose-overlay.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";

function makeState(mss) {
  const proto = {};
  applyMapState(proto);
  const s = Object.create(proto);
  s.dashboardSnapshot = () => ({ map_state_source: mss });
  return s;
}

test("[LP-1] no live pose -> overlay data is the snapshot map_state_source unchanged", () => {
  const mss = { present: true, robot_anchor: [0.1, 0.2], current_room: 2, image_size: [10, 20] };
  const s = makeState(mss);
  assert.equal(s.livePose(), null);
  assert.deepEqual(s.mapOverlayData(), mss);
});

test("[LP-2] live pose overrides ONLY the moving fields; static segmentation stays", () => {
  const mss = {
    present: true, robot_anchor: [0.1, 0.2], dock_anchor: [0.3, 0.4],
    current_room: 2, image_size: [10, 20], rooms: [{ number: 5 }],
  };
  const s = makeState(mss);
  s.setLivePose({
    present: true, robot_anchor: [0.8, 0.55], dock_anchor: [0.7, 0.34],
    current_room: 5, robot_heading: 90, path: [[0, 0], [1, 1]],
  });
  const ov = s.mapOverlayData();
  assert.deepEqual(ov.robot_anchor, [0.8, 0.55]);
  assert.deepEqual(ov.dock_anchor, [0.7, 0.34]);
  assert.equal(ov.current_room, 5);
  assert.equal(ov.robot_heading, 90);
  assert.deepEqual(ov.path, [[0, 0], [1, 1]]);
  assert.deepEqual(ov.image_size, [10, 20]);     // static — untouched
  assert.deepEqual(ov.rooms, [{ number: 5 }]);   // static — untouched
  assert.notEqual(ov, mss);                      // a copy, not the snapshot object
});

test("[LP-3] docked pose: robot anchor snaps to the dock + robot_docked, killing the stale ghost", () => {
  const mss = { present: true, robot_anchor: [0.1, 0.9], current_room: 1, image_size: [10, 10] };
  const s = makeState(mss);
  s.setLivePose({
    present: true, robot_anchor: [0.7, 0.34], dock_anchor: [0.7, 0.34],
    current_room: 7, robot_docked: true,
  });
  const ov = s.mapOverlayData();
  assert.deepEqual(ov.robot_anchor, [0.7, 0.34]);   // no longer the stale [0.1, 0.9]
  assert.equal(ov.current_room, 7);
  assert.equal(ov.robot_docked, true);
});

test("[LP-4] setLivePose(absent) clears the override -> back to the snapshot", () => {
  const mss = { present: true, robot_anchor: [0.1, 0.2] };
  const s = makeState(mss);
  s.setLivePose({ present: true, robot_anchor: [0.8, 0.8] });
  assert.deepEqual(s.mapOverlayData().robot_anchor, [0.8, 0.8]);
  s.setLivePose({ present: false, reason: "no_pose" });
  assert.equal(s.livePose(), null);
  assert.deepEqual(s.mapOverlayData().robot_anchor, [0.1, 0.2]);
});

test("[LP-5] no map_state_source present -> nothing to merge onto, base passes through", () => {
  const s = makeState(null);
  s.setLivePose({ present: true, robot_anchor: [0.8, 0.8] });
  assert.equal(s.mapOverlayData(), null);
  const s2 = makeState({ present: false });
  s2.setLivePose({ present: true, robot_anchor: [0.8, 0.8] });
  assert.deepEqual(s2.mapOverlayData(), { present: false });
});

test("[LP-6] partial live pose keeps NON-owned fields but the live pose OWNS current_room + path", () => {
  const mss = {
    present: true, robot_anchor: [0.1, 0.2], dock_anchor: [0.3, 0.4],
    current_room: 2, path: [[0.1, 0.1]],
  };
  const s = makeState(mss);
  s.setLivePose({ present: true, robot_anchor: [0.9, 0.9] }); // no dock/current_room/path
  const ov = s.mapOverlayData();
  assert.deepEqual(ov.robot_anchor, [0.9, 0.9]);   // overridden
  assert.deepEqual(ov.dock_anchor, [0.3, 0.4]);    // non-owned -> kept from snapshot
  assert.equal(ov.current_room, undefined);        // OWNED + omitted by live pose -> stale cleared
  assert.equal(ov.path, undefined);                // OWNED + omitted by live pose -> stale cleared
});

test("[LP-7] docked live pose with no resolvable room clears the stale snapshot current_room", () => {
  // the exact ghost: robot docked, dock cell has no room -> live pose omits current_room,
  // and the lagged snapshot still says 'kitchen'. The merge must not keep it.
  const mss = { present: true, current_room: 5, path: [[0.1, 0.9]], image_size: [10, 10] };
  const s = makeState(mss);
  s.setLivePose({ present: true, robot_anchor: [0.7, 0.34], dock_anchor: [0.7, 0.34], robot_docked: true });
  const ov = s.mapOverlayData();
  assert.equal(ov.current_room, undefined);        // no stale highlight
  assert.equal(ov.path, undefined);                // no stale trail
  assert.deepEqual(ov.robot_anchor, [0.7, 0.34]);  // robot still on the dock
  assert.equal(ov.robot_docked, true);
});
