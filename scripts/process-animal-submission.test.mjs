/**
 * Tests for the animal submission processor.
 *
 * The parse tests (PAS-1..4) are sync — run anywhere:
 *   node --test scripts/process-animal-submission.test.mjs
 * The full-flow tests (PAS-5..8) drive buildAnimal → the DOMPurify sanitiser,
 * so they need a Playwright browser (run in the pinned image). PAS-9 does not:
 * a colliding id is rejected by the contract gate before the sanitiser runs.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseAnimalIssue, processAnimalSubmission, FIELD } from "./process-animal-submission.mjs";
import { existingAnimalIds } from "./build-animal.mjs";
import { RESERVED_IDS } from "./animal-descriptor.mjs";

const PARTS_Q = {
  body: "<path d='M1,2 L3,4' fill='hsl(var(--animal-fur))'/>",
  frontLeftLeg: "<g class='cat-fl-lower'><line x1='1' y1='2' x2='3' y2='4' stroke='hsl(var(--animal-fur))'/></g>",
  frontRightLeg: "<g class='cat-fr-lower'><line x1='1' y1='2' x2='3' y2='4' stroke='hsl(var(--animal-fur))'/></g>",
  backLeftLeg: "<g class='cat-bl-lower'><line x1='1' y1='2' x2='3' y2='4' stroke='hsl(var(--animal-fur))'/></g>",
  backRightLeg: "<g class='cat-br-lower'><line x1='1' y1='2' x2='3' y2='4' stroke='hsl(var(--animal-fur))'/></g>",
  tail: "<path d='M1,2 L3,4' stroke='hsl(var(--animal-fur))' fill='none'/>",
  head: "<path d='M1,2 L3,4' fill='hsl(var(--animal-fur))'/>",
  eyes: "<circle cx='1' cy='2' r='3' fill='hsl(var(--animal-eye))'/>",
  face: "<path d='M1,2 L3,4' stroke='hsl(var(--animal-nose))' fill='none'/>",
};

const descriptor = (over = {}) => ({
  id: "testanimal",
  name: "Test Animal",
  type: "quadruped",
  license: "CC0-1.0",
  colors: { "--animal-eye": "40 30% 20%", "--animal-fur": "30 60% 70%" },
  parts: { ...PARTS_Q },
  ...over,
});

function issueBody(descriptorObj, fields = {}) {
  const fence = "```json\n" + JSON.stringify(descriptorObj, null, 2) + "\n```";
  const meta = Object.entries(fields)
    .map(([k, v]) => `### ${k}\n\n${v}`)
    .join("\n\n");
  return `### ${FIELD.descriptor}\n\n${fence}\n\n${meta}`;
}

test("[PAS-1] parses the descriptor + merges the author field", () => {
  const r = parseAnimalIssue(issueBody(descriptor(), { [FIELD.author]: "Pat", [FIELD.authorUrl]: "https://example.com/pat" }));
  assert.equal(r.ok, true);
  assert.equal(r.animal.id, "testanimal");
  assert.equal(r.animal.author, "Pat");
  assert.equal(r.animal.author_url, "https://example.com/pat");
});

test("[PAS-2] no descriptor + no SVG → fix-it report", () => {
  const r = parseAnimalIssue("### Animal descriptor JSON\n\n(forgot to paste)");
  assert.equal(r.ok, false);
  assert.equal(r.reason, "no_input");
  assert.match(r.report, /descriptor|Full SVG/i);
});

test("[PAS-3] malformed JSON → fix-it report", () => {
  const r = parseAnimalIssue("### x\n\n```json\n{ not json,, }\n```");
  assert.equal(r.ok, false);
  assert.equal(r.reason, "bad_json");
});

test("[PAS-4] envelope form { animal } is accepted", () => {
  const r = parseAnimalIssue(issueBody({ version: 1, kind: "animal", animal: descriptor() }));
  assert.equal(r.ok, true);
  assert.equal(r.animal.id, "testanimal");
});

test("[PAS-5] valid descriptor → validated, with envelope + module", async () => {
  const r = await processAnimalSubmission(issueBody(descriptor(), { [FIELD.author]: "Pat" }), 7, { existingIds: [] });
  assert.equal(r.ok, true, JSON.stringify(r.errors));
  assert.equal(r.slug, "testanimal");
  assert.equal(r.envelope.kind, "animal");
  assert.equal(r.envelope.animal.source, "community");
  assert.ok(r.moduleJs.includes('AnimalSVG.register("testanimal"'));
  assert.match(r.report, /Validated/);
});

test("[PAS-6] hostile descriptor → invalid report naming the vectors", async () => {
  const hostile = descriptor();
  hostile.parts.body += "<script>alert(1)</script>";
  hostile.parts.head = "<circle cx='1' cy='2' r='3' onload='x()'/>";
  const r = await processAnimalSubmission(issueBody(hostile), 8, { existingIds: [] });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "invalid");
  assert.match(r.report, /script/i);
  assert.match(r.report, /event handler/i);
});

const FULL_SVG = `<svg viewBox="-10 -10 500 340">
  <g data-slot="body"><path d="M1,2 L3,4" fill="hsl(var(--animal-fur))"/></g>
  <g data-slot="head"><path d="M1,2 L3,4" fill="hsl(var(--animal-fur))"/></g>
  <g data-slot="frontLeftLeg"><g class="cat-fl-lower"><line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/></g></g>
  <g data-slot="frontRightLeg"><g class="cat-fr-lower"><line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/></g></g>
  <g data-slot="backLeftLeg"><g class="cat-bl-lower"><line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/></g></g>
  <g data-slot="backRightLeg"><g class="cat-br-lower"><line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/></g></g>
  <g data-slot="tail"><path d="M1,2 L3,4" stroke="hsl(var(--animal-fur))" fill="none"/></g>
  <g data-slot="eyes"><circle cx="1" cy="2" r="3" fill="hsl(var(--animal-eye))" onload="evil()"/></g>
  <g data-slot="face"><path d="M1,2 L3,4" stroke="hsl(var(--animal-nose))" fill="none"/></g>
</svg>`;

function svgIssueBody(svg, fields = {}) {
  const f = { "Animal id": "svgfox", "Animal name": "SVG Fox", "Body plan": "quadruped", "Licence": "CC0-1.0", ...fields };
  const meta = Object.entries(f).map(([k, v]) => `### ${k}\n\n${v}`).join("\n\n");
  return `### ${FIELD.fullSvg}\n\n${svg}\n\n${meta}`;
}

test("[PAS-7] detects full-SVG mode + gathers the metadata fields", () => {
  const r = parseAnimalIssue(svgIssueBody(FULL_SVG));
  assert.equal(r.ok, true);
  assert.equal(r.mode, "svg");
  assert.match(r.svg, /<svg/);
  assert.equal(r.meta.id, "svgfox");
  assert.equal(r.meta.type, "quadruped");
  assert.equal(r.meta.license, "CC0-1.0");
});

test("[PAS-8] full-SVG submission -> validated, sanitised, safe descriptor echoed", async () => {
  const r = await processAnimalSubmission(svgIssueBody(FULL_SVG), 9, { existingIds: [] });
  assert.equal(r.ok, true, JSON.stringify(r.errors || r.report));
  assert.equal(r.slug, "svgfox");
  assert.ok(!/onload/i.test(r.envelope.animal.parts.eyes), "hostile attr stripped from the SVG");
  assert.match(r.report, /Built from your SVG/);
  assert.match(r.report, /```json/);
});

/* =========================================================
   COLLISION-GUARD WIRING  ·  [PAS-9]
   ========================================================= */

test("[PAS-9] the DEFAULT reads the real gallery — no opts needed", async () => {
  // THE WIRING, not the algorithm — [AD-16] already proves validateDescriptor
  // rejects a colliding id. What nothing covered is the `?? existingAnimalIds()`
  // in processAnimalSubmission's signature, and that is the ONLY thing arming the
  // guard for the live bot: the intake workflow calls it with two arguments, while
  // every other test here hands it `existingIds: []`. Flip that default to `?? []`
  // and this is the only test that goes red.
  //
  // The id is DERIVED, never hardcoded, for two separate reasons.
  //
  // 1. Half the set comes from animal-svg/animals/index.json, which .gitignore:58
  //    ignores because the integration generates it at HA startup — so it is absent
  //    on a runner, and existingAnimalIds() swallows that with a bare catch. A
  //    hardcoded "cat" would be a live test here and a vacuous one in CI: the same
  //    trap 7322b06e fixed in gallery-completeness.spec.mjs. Deriving inside the
  //    test process means each environment collides against ids it actually has.
  // 2. RESERVED_IDS is checked FIRST (it is an `else if`), so a bundled id like
  //    "cat" is rejected as built-in whether or not the guard is armed — it would
  //    survive the ablation. Only a NON-reserved existing id, i.e. one that reached
  //    the set from tracked gallery/animals/, can prove the wiring.
  const collidable = existingAnimalIds().filter((id) => !RESERVED_IDS.has(id));
  assert.ok(
    collidable.length > 0,
    "no non-reserved published animal id is visible here, so the default cannot be shown to guard " +
    "anything — gallery/animals/ is where a runner gets one (currently fox.json)",
  );

  const taken = collidable[0];
  const r = await processAnimalSubmission(issueBody(descriptor({ id: taken })), 9999);
  assert.equal(r.ok, false, `submitting the published id "${taken}" with no opts must still be rejected`);
  assert.equal(r.reason, "invalid");
  // Match the COLLISION message specifically: the reserved-id branch emits a
  // different string, and this is the only one that needs existingIds non-empty.
  assert.match(r.errors.join("\n"), new RegExp(`id "${taken}" already exists in the gallery`));
  assert.equal(
    r.errors.length, 1,
    `the fixture must be otherwise valid so the collision IS the rejection: ${r.errors.join(" | ")}`,
  );
});
