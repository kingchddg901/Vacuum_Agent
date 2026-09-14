/**
 * The theme-token docs must not depend on filesystem order.
 *
 * `readdirSync` returns NTFS order on Windows and ext4 hash order on Linux, and each
 * token's consumer list is built in walk order — so THEME_TOKEN_USAGE.md regenerated
 * differently on the two platforms with no source change at all. Nine consecutive CI
 * runs failed the staleness gate on a file that was correct every time.
 *
 * The gate caught it only by accident: the maintainer works on Windows and CI runs
 * Linux. Had both been the same platform it would have stayed hidden and simply
 * produced churn whenever a second person regenerated. This asserts the property
 * directly — reverse every directory listing and the output must not move, because
 * an ext4 hash order is just another shuffle.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync, mkdtempSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

function render({ reverse = false, shiftLines = 0 } = {}) {
  const out = join(mkdtempSync(join(tmpdir(), "evcc-tk-")), `r${reverse ? 1 : 0}s${shiftLines}`);
  mkdirSync(out, { recursive: true });
  const gen = "file:///" + join(ROOT, "scripts", "gen-theme-token-docs.mjs").split("\\").join("/");
  execFileSync(process.execPath, ["-e", `
    const fs = require("node:fs");
    const real = fs.readdirSync;
    fs.readdirSync = (...a) => { const r = real(...a); return ${reverse
      ? "Array.isArray(r) ? [...r].reverse() : r" : "r"}; };
    const realRead = fs.readFileSync;
    fs.readFileSync = (p, ...a) => {
      const v = realRead(p, ...a);
      // Prepend comment lines to every scanned source. Every token reference in the
      // file moves down by exactly ${shiftLines}; not one fact about token usage changes.
      // BACKSLASH-FREE on purpose: this source is embedded in a template literal and
      // then eval'd, so a regex literal with an escape does not survive the trip.
      const SEP = String.fromCharCode(92);
      const sp = String(p).split(SEP).join("/");
      if (${shiftLines} > 0 && typeof v === "string" && sp.includes("/src/styles/")) {
        return ("/* shift */" + String.fromCharCode(10)).repeat(${shiftLines}) + v;
      }
      return v;
    };
    process.env.EVCC_GENDOC_OUT = ${JSON.stringify(out)};
    import(${JSON.stringify(gen)});
  `], { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  return readFileSync(join(out, "THEME_TOKEN_USAGE.md"), "utf8");
}

test("[TKD-1] the usage trace does not depend on directory order", () => {
  const natural = render();
  const reversed = render({ reverse: true });
  assert.equal(
    natural, reversed,
    "reversing every directory listing changed the output — the generator is " +
    "filesystem-order dependent again, so Windows and Linux will disagree forever",
  );
});

test("[TKD-2] the usage trace does not depend on WHERE in a file a token sits", () => {
  // The content is the fact; the line number is an accident of layout. Adding a
  // comment above a rule used to shift every reference below it, so a change that
  // touched no token at all arrived as a ~98-line diff and turned the staleness
  // gate red. A gate whose diff is almost entirely noise stops being read: it gets
  // regenerated unexamined, and a REAL token change rides in unnoticed alongside.
  //
  // Sibling of [TKD-1]: same defect class, different axis. That one was the output
  // moving with directory order, this one is the output moving with line position.
  const flat = render();
  const shifted = render({ shiftLines: 20 });
  assert.equal(
    flat, shifted,
    "pushing every src/styles source down 20 lines changed the usage trace — it is " +
    "line-position dependent again, so any added comment will show up as churn and " +
    "bury the real token changes in it",
  );
});
