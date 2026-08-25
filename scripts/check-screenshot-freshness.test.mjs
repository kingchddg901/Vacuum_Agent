/**
 * CI gate for the screenshot-freshness check.
 *
 * `node-tests.yml` runs `node --test scripts/*.test.mjs`, so this file is what makes
 * the check actually RUN on every push. The checker itself is a CLI; without a test
 * wrapper it would sit in the repo being correct and never being executed — which is
 * the same shape as the failure it exists to catch.
 *
 * The second test is a BITE TEST. The first one passes whenever the manifest agrees
 * with en.js, and it would go on passing if the comparison were gutted to `return
 * true` — so on its own it proves nothing about whether a real string change is
 * detectable. This drives the checker against a throwaway manifest holding a
 * deliberately wrong fingerprint and asserts it fails, naming the key.
 */
import { strict as assert } from "node:assert";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCRIPT = join(ROOT, "scripts", "check-screenshot-freshness.mjs");
const MANIFEST = join(ROOT, "scripts", "screenshot-i18n-manifest.json");

/** Run the checker; return {code, out}. Never throws on a non-zero exit. */
function run(env = {}) {
  try {
    const out = execFileSync(process.execPath, [SCRIPT], {
      cwd: ROOT, encoding: "utf8", stdio: "pipe", env: { ...process.env, ...env },
    });
    return { code: 0, out };
  } catch (err) {
    return { code: err.status ?? 1, out: `${err.stdout ?? ""}${err.stderr ?? ""}` };
  }
}

test("every committed screenshot still matches the strings it renders", () => {
  const { code, out } = run();
  assert.equal(
    code, 0,
    `A string under a committed screenshot changed. Re-shoot the listed images from\n` +
    `the pinned language wall, then run:\n` +
    `  node scripts/check-screenshot-freshness.mjs --update\n\n${out}`,
  );
});

test("[BITE] a changed string is actually detected", () => {
  // Corrupt ONE fingerprint in a copy of the manifest and point the checker at it.
  // en.js is never touched: a test that edits a shipped source file leaves the repo
  // dirty when it fails midway, and this one is meant to fail on purpose.
  const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));
  const [famName, fam] = Object.entries(manifest.families)[0];
  const victim = Object.keys(fam.keys)[0];
  assert.ok(victim, "manifest has no recorded fingerprints — nothing to verify against");
  fam.keys[victim] = "deadbeef";

  const dir = mkdtempSync(join(tmpdir(), "evcc-fresh-"));
  const tmpManifest = join(dir, "screenshot-i18n-manifest.json");
  writeFileSync(tmpManifest, JSON.stringify(manifest), "utf8");
  try {
    const { code, out } = run({ EVCC_SCREENSHOT_MANIFEST: tmpManifest });
    assert.equal(code, 1, `checker did not fail on a corrupted fingerprint:\n${out}`);
    assert.match(out, new RegExp(victim.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
      `it failed, but never named the key that moved:\n${out}`);
    assert.match(out, /CHANGED/, `no CHANGED line, so the reason is not reported:\n${out}`);
    assert.ok(out.includes(fam.files[0]), `it named the key but not the image to re-shoot:\n${out}`);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
