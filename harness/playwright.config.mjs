import { defineConfig, devices } from "@playwright/test";

/**
 * Harness test runner. Hosts every harness test: smoke (Wave 1),
 * gallery completeness (Wave 2), visual-regression (Wave 3), CVD
 * (Wave 4), intake gate (Wave 5).
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  // Visual baselines are a single platform-agnostic set, generated in the
  // pinned Playwright Linux image (harness/README.md) so local-Docker and CI
  // share them. No {platform} segment on purpose.
  snapshotPathTemplate: "{testDir}/__screenshots__/{testFileName}/{arg}{ext}",
  expect: {
    toHaveScreenshot: {
      // JI#2 (diff threshold + masking). Calibrated against the pinned-image
      // baselines: the env is pixel-deterministic, so we use an ABSOLUTE
      // pixel budget — NOT a ratio. A ratio lets a small colored-region
      // change hide inside a tall image (proven: a recolored confidence chip
      // slipped under 1%), which is exactly the regression this gate exists
      // to catch. threshold = per-pixel YIQ tolerance.
      threshold: 0.1,
      maxDiffPixels: 60,
      animations: "disabled",
    },
  },
  use: {
    ...devices["Desktop Chrome"],
    deviceScaleFactor: 1,
    viewport: { width: 1000, height: 1400 },
  },
});
