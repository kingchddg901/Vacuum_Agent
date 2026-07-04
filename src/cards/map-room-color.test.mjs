import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ROOM_FILL_PALETTE, ROOM_FILL_N,
  roomFillTokenName, roomFillDefault, roomFillCss, hexToRgb, roomFillRgb,
  normalizeHex, roomOverrideRgb,
} from "./map-room-color.js";

test("[MRC-1] token name is 1-based and wraps the palette", () => {
  assert.equal(roomFillTokenName(0), "--evcc-room-fill-1");
  assert.equal(roomFillTokenName(11), "--evcc-room-fill-12");
  assert.equal(roomFillTokenName(12), "--evcc-room-fill-1");   // wraps
  assert.equal(roomFillTokenName(-1), "--evcc-room-fill-12");  // negative wraps
});

test("[MRC-2] default hex tracks the palette (net-zero anchor)", () => {
  assert.equal(roomFillDefault(0), ROOM_FILL_PALETTE[0]);
  assert.equal(roomFillDefault(ROOM_FILL_N), ROOM_FILL_PALETTE[0]);  // wraps
  assert.equal(roomFillDefault(5), "#a78bfa");
});

test("[MRC-3] roomFillCss = var(token, default) so SVG rides the cascade", () => {
  assert.equal(roomFillCss(0), "var(--evcc-room-fill-1, #00e5ff)");
  assert.equal(roomFillCss(11), "var(--evcc-room-fill-12, #f97316)");
});

test("[MRC-7] normalizeHex canonicalizes valid hex, else null", () => {
  assert.equal(normalizeHex("#00E5FF"), "#00e5ff");     // lowercased
  assert.equal(normalizeHex("00e5ff"), "#00e5ff");      // leading # optional
  assert.equal(normalizeHex("#0f0"), "#00ff00");        // #rgb expands
  assert.equal(normalizeHex("  #abcdef  "), "#abcdef"); // trims
  assert.equal(normalizeHex(""), null);
  assert.equal(normalizeHex("red"), null);              // named color -> null
  assert.equal(normalizeHex("#12"), null);              // wrong length
  assert.equal(normalizeHex(null), null);
  assert.equal(normalizeHex(undefined), null);
  assert.equal(normalizeHex(123), null);                // non-string
});

test("[MRC-8] roomFillCss: a valid override wins, an invalid one falls through", () => {
  // Override present + valid -> concrete hex (short-circuits the theme token).
  assert.equal(roomFillCss(0, "#123456"), "#123456");
  assert.equal(roomFillCss(5, "aabbcc"), "#aabbcc");    // normalized
  // Invalid / cleared override -> the Phase-1 var(token, default) cascade.
  assert.equal(roomFillCss(0, null), "var(--evcc-room-fill-1, #00e5ff)");
  assert.equal(roomFillCss(0, ""), "var(--evcc-room-fill-1, #00e5ff)");
  assert.equal(roomFillCss(0, "not-a-color"), "var(--evcc-room-fill-1, #00e5ff)");
});

test("[MRC-9] roomOverrideRgb: valid hex -> rgb, else null (falls through to palette)", () => {
  assert.deepEqual(roomOverrideRgb("#00e5ff"), [0, 229, 255]);
  assert.deepEqual(roomOverrideRgb("0f0"), [0, 255, 0]);
  assert.equal(roomOverrideRgb(null), null);
  assert.equal(roomOverrideRgb(""), null);
  assert.equal(roomOverrideRgb("garbage"), null);       // NOT grey — null so caller uses palette
});

test("[MRC-4] hexToRgb parses #rrggbb + #rgb, greys anything else", () => {
  assert.deepEqual(hexToRgb("#00e5ff"), [0, 229, 255]);
  assert.deepEqual(hexToRgb("00e5ff"), [0, 229, 255]);
  assert.deepEqual(hexToRgb("#0f0"), [0, 255, 0]);
  assert.deepEqual(hexToRgb("rgb(1,2,3)"), [128, 128, 128]);  // non-hex -> grey
  assert.deepEqual(hexToRgb(null), [128, 128, 128]);
});

test("[MRC-5] roomFillRgb with no host = the default palette RGB (themeless net-zero)", () => {
  // No getComputedStyle host -> the default hex for that slot.
  assert.deepEqual(roomFillRgb(0), hexToRgb(ROOM_FILL_PALETTE[0]));
  assert.deepEqual(roomFillRgb(11), hexToRgb(ROOM_FILL_PALETTE[11]));
  assert.deepEqual(roomFillRgb(12), hexToRgb(ROOM_FILL_PALETTE[0]));  // wraps
});

test("[MRC-6] roomFillRgb reads a token off a host, else falls back", () => {
  // Fake host: getComputedStyle is global; stub via a minimal object path is awkward, so
  // just verify the fallback path when the host has no CSSOM (throws -> default).
  const brokenHost = {};  // getComputedStyle(brokenHost) throws in node -> default
  assert.deepEqual(roomFillRgb(3, brokenHost), hexToRgb(ROOM_FILL_PALETTE[3]));
});
