#!/usr/bin/env node
/**
 * Write the Pages landing page (the site root hub) after the galleries render.
 * Counts come from the committed gallery sources so the hub shows live totals.
 *
 *   node harness/build-landing.mjs   ->  harness/out/preview/index.html
 */
import { readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { writeLanding } from "./lib/landing-html.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..");
const OUT = join(repo, "harness", "out", "preview");

const count = (dir) => (existsSync(dir) ? readdirSync(dir).filter((f) => f.endsWith(".json")).length : 0);
const themeCount = count(join(repo, "gallery", "themes"));
const animalCount = count(join(repo, "gallery", "animals"));
const repoUrl = process.env.GITHUB_REPOSITORY
  ? `https://github.com/${process.env.GITHUB_REPOSITORY}`
  : "https://github.com/kingchddg901/Vacuum_Agent";

writeLanding(OUT, { themeCount, animalCount, repoUrl });
console.log(`landing -> harness/out/preview/index.html (${themeCount} theme(s), ${animalCount} animal(s))`);
