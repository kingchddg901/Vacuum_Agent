/**
 * WAVE 5 — THEME INTAKE GATE
 * An uploaded theme export is DATA, not code. The ingest gate keeps only
 * known registry `--evcc-*` keys, clamps bounded scalars to range, drops
 * non-primitive values, and rejects malformed / unknown-namespace exports —
 * the entire reason running a stranger's theme in CI is safe. Reuses the same
 * clampThemeScalars path as import_theme.
 *
 * Deterministic (pure data) → runs everywhere.
 */
import { test, expect } from "@playwright/test";
import { mountHarness } from "../lib/mount-page.mjs";

const ingest = (page, envelope) =>
  page.evaluate((env) => window.__evcc.ingestTheme(env), envelope);

test.describe("theme intake gate", () => {
  test.beforeEach(async ({ page }) => { await mountHarness(page); });

  test("malformed exports are rejected, not rendered", async ({ page }) => {
    for (const bad of [null, 5, "x", {}, { theme: null }, { theme: 5 }, []]) {
      const r = await ingest(page, bad);
      expect(r.report.ok, `should reject ${JSON.stringify(bad)}`).toBe(false);
      expect(Object.keys(r.bundle).length).toBe(0);
    }
  });

  test("unknown keys and unknown floor namespaces are skipped", async ({ page }) => {
    const r = await ingest(page, {
      theme: {
        colors: {
          "--evcc-sem-success": "#0c8f86",         // known → kept
          "--evcc-bogus-xyz": "#ffffff",            // unknown token key → skipped
          "--evcc-floor-terrazzo-tint": "#abcdef",  // unknown floor namespace → skipped
          "evil": "anything",                        // not a token → skipped
        },
      },
    });
    expect(r.report.ok).toBe(true);
    expect(r.bundle["--evcc-sem-success"]).toBe("#0c8f86");
    expect(r.bundle["--evcc-bogus-xyz"]).toBeUndefined();
    expect(r.bundle["--evcc-floor-terrazzo-tint"]).toBeUndefined();
    expect(r.report.skippedKeys).toEqual(
      expect.arrayContaining(["--evcc-bogus-xyz", "--evcc-floor-terrazzo-tint", "evil"]),
    );
  });

  test("non-primitive values are dropped (no object/function injection)", async ({ page }) => {
    const r = await ingest(page, {
      theme: { colors: { "--evcc-sem-error": { nope: 1 }, "--evcc-sem-warning": "#e9a100" } },
    });
    expect(r.bundle["--evcc-sem-error"]).toBeUndefined();
    expect(r.bundle["--evcc-sem-warning"]).toBe("#e9a100");
  });

  test("every ingested bounded scalar lands inside its clamp", async ({ page }) => {
    const bounded = await page.evaluate(() => {
      const map = window.__evcc.tokenMap;
      const e = Object.entries(map).find(([, t]) => Number.isFinite(t.min) && Number.isFinite(t.max));
      return e ? { key: e[0], min: e[1].min, max: e[1].max } : null;
    });
    expect(bounded, "registry should expose at least one bounded scalar").toBeTruthy();

    const over = await ingest(page, { theme: { tokens: { [bounded.key]: bounded.max + 1000 } } });
    expect(Number(over.bundle[bounded.key])).toBe(bounded.max);
    expect(over.report.clamped).toBeGreaterThan(0);

    const under = await ingest(page, { theme: { tokens: { [bounded.key]: bounded.min - 1000 } } });
    expect(Number(under.bundle[bounded.key])).toBe(bounded.min);
  });
});
