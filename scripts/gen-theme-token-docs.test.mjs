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

function render(reverse) {
  const out = join(mkdtempSync(join(tmpdir(), "evcc-tk-")), reverse ? "rev" : "nat");
  mkdirSync(out, { recursive: true });
  const gen = "file:///" + join(ROOT, "scripts", "gen-theme-token-docs.mjs").split("\\").join("/");
  execFileSync(process.execPath, ["-e", `
    const fs = require("node:fs");
    const real = fs.readdirSync;
    fs.readdirSync = (...a) => { const r = real(...a); return ${reverse
      ? "Array.isArray(r) ? [...r].reverse() : r" : "r"}; };
    process.env.EVCC_GENDOC_OUT = ${JSON.stringify(out)};
    import(${JSON.stringify(gen)});
  `], { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  return readFileSync(join(out, "THEME_TOKEN_USAGE.md"), "utf8");
}

test("[TKD-1] the usage trace does not depend on directory order", () => {
  const natural = render(false);
  const reversed = render(true);
  assert.equal(
    natural, reversed,
    "reversing every directory listing changed the output — the generator is " +
    "filesystem-order dependent again, so Windows and Linux will disagree forever",
  );
});
