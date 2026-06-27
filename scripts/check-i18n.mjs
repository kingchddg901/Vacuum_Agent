/**
 * ============================================================
 * I18N GATE — translate() contract + key cross-check
 * ============================================================
 *
 * One repeatable check for the card's i18n layer, run after every conversion
 * wave (and ideally in CI). It has two independent parts:
 *
 *   A. CONTRACT — exercises src/i18n/index.js `translate()` directly, asserting
 *      the behaviour the renderers depend on: locale -> base-language -> English
 *      -> key fallback, `{name}` interpolation, and — most importantly — TRUST
 *      MODEL B, where a (possibly community-contributed) catalog STRING is
 *      HTML-escaped by default and only the audited `raw` path keeps markup.
 *      The adversarial case is explicit: a locale value carrying `<script>` must
 *      come back neutralized, because locales ride the same untrusted-intake
 *      path as themes/animals. The visual harness only proves the English
 *      catalog renders byte-identical; it never sees a foreign locale or a
 *      hostile string, so this is where that boundary is actually verified.
 *
 *   B. KEYS — a static scan tying the two halves of the catalog together:
 *      every literal `t("…")` / `tRaw("…")` key used in src/ MUST exist in
 *      en.js (an orphan renders the raw key in the UI — a real bug, FATAL),
 *      and every en.js key MUST be reachable from source — proven three ways
 *      (literal call, key-as-data-value, or a `t(`…${…}…`)` template extracted
 *      from the code), never a hand-maintained allowlist. A key reachable by
 *      none is a dead key (dropped translator effort, reported).
 *
 * Exit code is non-zero iff a contract assertion fails or an orphan key exists.
 * Framework-free on purpose (node:assert + node:fs) so it runs anywhere node
 * does, with no dev-dependency and no build step.
 *
 * Run:  node scripts/check-i18n.mjs
 *
 * ============================================================
 */

import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join, relative } from "node:path";
import { translate, registerLocale, resolveLang, validateLocale, localeSource, loadLocale, loadDroppedLocales, listBundledLocales, listLocales } from "../src/i18n/index.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");
const SRC = join(REPO, "src");

let failures = 0;
const fail = (msg) => { failures += 1; console.error(`  ✗ ${msg}`); };

/* =========================================================
   A. translate() CONTRACT
   ========================================================= */
console.log("A. translate() contract");

// A throwaway locale + a deliberately hostile one, registered only for this run.
registerLocale("xx", {
  "rooms.empty": "Sala xx",
  "rooms.greeting": "Olá {name}",
});
registerLocale("ev", {
  // An attacker-supplied community locale value. Must never reach innerHTML raw.
  "rooms.empty": '<img src=x onerror="alert(1)">&"\'<b>',
  // A hostile PLURAL form — escaping must apply to the selected form too.
  "rooms.count_rooms": { other: '<b>{count}</b>' },
});
// A real multi-form language (Russian: one/few/many/other) drives the
// Intl.PluralRules selection path; "sv" (Swedish — deliberately a NON-BUNDLED
// locale, so it has no catalog) exercises the English-object cross-locale
// fallback; "pl" supplies only `other` (in-entry fallback when the chosen
// category is missing). NOTE: the fallback case must use a locale NOT bundled
// in CATALOGS (en/ru/de/fr/es/nl/it/pt) — a bundled one resolves to its own
// translation instead of falling back. Keep it a tier-absent code.
registerLocale("ru", {
  "rooms.count_rooms": {
    one: "{count} комната", few: "{count} комнаты",
    many: "{count} комнат", other: "{count} комнаты",
  },
});
registerLocale("pl", { "rooms.count_rooms": { other: "pokoje: {count}" } });

const check = (label, fn) => {
  try { fn(); console.log(`  ✓ ${label}`); }
  catch (e) { fail(`${label} — ${e.message}`); }
};

const checkAsync = async (label, fn) => {
  try { await fn(); console.log(`  ✓ ${label}`); }
  catch (e) { fail(`${label} — ${e.message}`); }
};

// 1. English base resolves (plain text -> escaping is a no-op -> identity).
check("en key resolves to its value", () => {
  assert.equal(translate("en", "rooms.empty"),
    "No rooms yet — open the Setup tab and run Import Active Map (the highlighted button), then Configure Rooms to get started.");
});

// 2. A registered locale wins over English for the same key.
check("registered locale overrides English", () => {
  assert.equal(translate("xx", "rooms.empty"), "Sala xx");
});

// 3. Missing key in a known locale falls back to English.
check("missing locale key falls back to English", () => {
  assert.equal(translate("xx", "common.cancel"), translate("en", "common.cancel"));
});

// 4. Regional code falls back to its base language (xx-YY -> xx).
check("regional code falls back to base language", () => {
  assert.equal(translate("xx-YY", "rooms.empty"), "Sala xx");
});

// 5. Entirely unknown language falls back to English.
check("unknown language falls back to English", () => {
  assert.equal(translate("zz", "rooms.empty"), translate("en", "rooms.empty"));
});

// 6. Missing English key renders the key itself (a VISIBLE miss, never blank).
check("missing key renders the key (visible miss)", () => {
  assert.equal(translate("en", "does.not.exist"), "does.not.exist");
});

// 7. null/undefined language defaults to English (no throw).
check("null language defaults to English", () => {
  assert.equal(translate(null, "rooms.empty"), translate("en", "rooms.empty"));
  assert.equal(translate(undefined, "rooms.empty"), translate("en", "rooms.empty"));
});

// 8. TRUST MODEL B — a hostile catalog string is HTML-escaped by default.
check("hostile locale string is escaped (trust model B)", () => {
  const out = translate("ev", "rooms.empty");
  assert.ok(!out.includes("<img"), "raw <img survived escaping");
  assert.ok(!out.includes("<b>"), "raw <b> survived escaping");
  assert.equal(out, "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&quot;&#39;&lt;b&gt;");
});

// 9. raw:true (the tRaw path) keeps authored markup intact.
check("raw option preserves markup", () => {
  const out = translate("ev", "rooms.empty", undefined, { raw: true });
  assert.equal(out, '<img src=x onerror="alert(1)">&"\'<b>');
});

// 10. Interpolation: {name} is replaced; the VALUE is inserted raw (the caller
//     escapes user data at the sink — the var XSS boundary is unchanged).
check("interpolation replaces {name}; value inserted raw", () => {
  assert.equal(translate("xx", "rooms.greeting", { name: "Ada" }), "Olá Ada");
  assert.equal(translate("xx", "rooms.greeting", { name: "<b>" }), "Olá <b>");
});

// 11. A missing interpolation var leaves its placeholder untouched.
check("missing interpolation var leaves placeholder", () => {
  assert.equal(translate("xx", "rooms.greeting", {}), "Olá {name}");
});

// --- Plurals (object-valued keys + Intl.PluralRules) ---------------------

// 12. English picks `one` for count===1 and `other` otherwise (CLDR English).
check("plural: English selects one vs other by count", () => {
  assert.equal(translate("en", "rooms.count_rooms", { count: 1 }), "1 room");
  assert.equal(translate("en", "rooms.count_rooms", { count: 5 }), "5 rooms");
  assert.equal(translate("en", "rooms.count_rooms", { count: 0 }), "0 rooms");
});

// 13. A real multi-form language selects the right CLDR category via Intl —
//     Russian: 1->one, 2->few, 5->many, 21->one (n%10==1 && n%100!=11).
check("plural: Intl.PluralRules drives multi-form selection (ru)", () => {
  assert.equal(translate("ru", "rooms.count_rooms", { count: 1 }), "1 комната");
  assert.equal(translate("ru", "rooms.count_rooms", { count: 2 }), "2 комнаты");
  assert.equal(translate("ru", "rooms.count_rooms", { count: 5 }), "5 комнат");
  assert.equal(translate("ru", "rooms.count_rooms", { count: 21 }), "21 комната");
});

// 14. A plural key called WITHOUT count falls to the `other` form (never blank).
check("plural: missing count falls to 'other'", () => {
  assert.equal(translate("en", "rooms.count_rooms"), "{count} rooms");
});

// 15. Partial locale (only `other`) uses its own `other` when the chosen
//     category is absent; a locale missing the key entirely falls to English.
check("plural: in-entry + cross-locale fallback", () => {
  assert.equal(translate("pl", "rooms.count_rooms", { count: 1 }), "pokoje: 1");
  // "sv" has no bundled catalog → cross-locale fallback to the English object,
  // with sv's own (one/other) Intl plural selection.
  assert.equal(translate("sv", "rooms.count_rooms", { count: 1 }), "1 room");
  assert.equal(translate("sv", "rooms.count_rooms", { count: 3 }), "3 rooms");
});

// 16. TRUST MODEL B holds for the SELECTED plural form — a hostile form is
//     escaped, and the count var is still inserted after escaping.
check("plural: selected form is escaped (trust model B)", () => {
  const out = translate("ev", "rooms.count_rooms", { count: 5 });
  assert.ok(!out.includes("<b>"), "raw <b> survived escaping in a plural form");
  assert.equal(out, "&lt;b&gt;5&lt;/b&gt;");
});

// --- resolveLang (the shared language resolver) --------------------------

// 17. config.i18n.locale PINS the language; "auto" / absent defers to hass.
check("resolveLang: config locale pins, auto/absent defers to hass", () => {
  // hass language "sv" is non-bundled (not draft-gated) so it passes through and
  // these assertions isolate the pin-vs-auto behavior from the draft-gate below.
  const hass = { locale: { language: "sv" } };
  assert.equal(resolveLang(hass, { i18n: { locale: "fr" } }), "fr");   // pinned wins (explicit, bypasses gate)
  assert.equal(resolveLang(hass, { i18n: { locale: "auto" } }), "sv"); // auto -> hass
  assert.equal(resolveLang(hass, {}), "sv");                            // no i18n -> hass
  assert.equal(resolveLang({ language: "sv" }, undefined), "sv");       // legacy hass.language
  assert.equal(resolveLang(undefined, undefined), "en");                // nothing -> en
});

// 17b. DRAFT-GATE: an unreviewed bundled locale must not auto-activate from the
//      system language (falls to English); an explicit pin still reaches it.
check("resolveLang: draft-gate blocks auto-activation, explicit pin bypasses", () => {
  // "de" is a bundled DRAFT — auto (system language) must fall back to English.
  assert.equal(resolveLang({ locale: { language: "de" } }, {}), "en");
  assert.equal(resolveLang({ locale: { language: "de" } }, { i18n: { locale: "auto" } }), "en");
  assert.equal(resolveLang({ locale: { language: "de-DE" } }, {}), "en"); // base-language gated too
  assert.equal(resolveLang({ language: "ru" }, undefined), "en");          // legacy field gated too
  // Explicit pin to a draft BYPASSES the gate (deliberate per-dashboard choice).
  assert.equal(resolveLang({ locale: { language: "de" } }, { i18n: { locale: "de" } }), "de");
  // Stable (en) auto-activates; non-bundled passes through unchanged.
  assert.equal(resolveLang({ locale: { language: "en" } }, {}), "en");
  assert.equal(resolveLang({ locale: { language: "sv" } }, {}), "sv");
});

// 17d. OVERRIDE: the in-card control's per-user choice is the most explicit
//      source — it wins over the config pin AND the system language, and (like
//      the pin) bypasses the draft-gate. "auto"/empty defers down the chain.
check("resolveLang: per-user override wins over pin + system, bypasses draft-gate", () => {
  const hass = { locale: { language: "sv" } };
  // Override beats a conflicting config pin.
  assert.equal(resolveLang(hass, { i18n: { locale: "fr" } }, "it"), "it");
  // Override beats the system language.
  assert.equal(resolveLang(hass, {}, "es"), "es");
  // Override to a DRAFT bypasses the gate even when the system language would be gated.
  assert.equal(resolveLang({ locale: { language: "en" } }, {}, "de"), "de");
  assert.equal(resolveLang({ locale: { language: "de" } }, {}, "ru"), "ru");
  // "auto" / empty override defers to the pin, then the system language.
  assert.equal(resolveLang(hass, { i18n: { locale: "fr" } }, "auto"), "fr");
  assert.equal(resolveLang(hass, {}, "auto"), "sv");
  assert.equal(resolveLang(hass, {}, ""), "sv");
  assert.equal(resolveLang(hass, {}, undefined), "sv");
  // An "auto" override over a draft system language is still gated (defers, then gate).
  assert.equal(resolveLang({ locale: { language: "de" } }, {}, "auto"), "en");
});

// 17e. The three language-control strings are defined in the English base
//      (the menu heading, button title, and the "Auto" row) — the control
//      renders keys, so a missing one would surface as a visible miss.
check("language control keys exist in en base", () => {
  for (const key of ["language.button_title", "language.heading", "language.auto"]) {
    assert.notEqual(translate("en", key), key, `${key} missing from en base`);
  }
});

// 17c. listBundledLocales: endonyms + localized draft tags for the override picker.
check("listBundledLocales: endonyms, localized draft tags, English first", () => {
  const list = listBundledLocales();
  assert.equal(list[0].code, "en");
  assert.equal(list[0].status, "stable");
  assert.equal(list[0].label, "English");
  const de = list.find((l) => l.code === "de");
  assert.equal(de.status, "draft");
  assert.equal(de.label, "Deutsch (Entwurf)");          // endonym + own word for draft
  assert.equal(list.find((l) => l.code === "ru").label, "Русский (черновик)");
});

// 17f. listLocales + draft-gate: a RUNTIME "custom" locale (a drop-in JSON,
//      registered with status:"custom") is SELECTABLE in the picker but, like a
//      bundled draft, reachable only by an explicit override/pin — never auto.
check("listLocales: a runtime custom locale is selectable + explicit-only", () => {
  registerLocale("eo", { "rooms.empty": "Neniu ĉambro" }, { status: "custom" });
  const eo = listLocales().find((l) => l.code === "eo");
  assert.ok(eo, "custom locale appears in listLocales");
  assert.equal(eo.status, "custom");
  assert.match(eo.label, /\(custom\)/);
  assert.equal(translate("eo", "rooms.empty"), "Neniu ĉambro");
  // Gated from auto-activation (system language); reachable by override / pin.
  assert.equal(resolveLang({ locale: { language: "eo" } }, {}), "en");
  assert.equal(resolveLang({}, {}, "eo"), "eo");
  assert.equal(resolveLang({}, { i18n: { locale: "eo" } }), "eo");
  // listLocales is a SUPERSET of the bundled set (English still first/present).
  assert.equal(listLocales()[0].code, "en");
});

// 17g. Shadow: a drop-in whose code matches a BUNDLED one overrides the catalog
//      (so you can fix a bundled draft locally) AND the picker reflects it as
//      custom — label + active strings agree, no silent divergence.
check("listLocales: a drop-in overriding a bundled code wins + shows custom", () => {
  registerLocale("nl", { "rooms.empty": "Aangepaste NL" }, { status: "custom" });
  assert.equal(translate("nl", "rooms.empty"), "Aangepaste NL");        // dropped catalog wins
  const nl = listLocales().find((l) => l.code === "nl");
  assert.equal(nl.status, "custom");                                     // honest, not "(draft)"
  assert.match(nl.label, /\(custom\)/);
  assert.equal(resolveLang({ locale: { language: "nl" } }, {}), "en");   // still gated (explicit-only)
});

// --- validateLocale (untrusted-locale gate) ------------------------------

// 18. A well-formed locale passes clean with no errors (strings + plural object).
check("validateLocale: well-formed locale passes clean", () => {
  const { clean, errors, warnings } = validateLocale(
    { "rooms.empty": "Keine Räume", "rooms.count_rooms": { one: "{count} Raum", other: "{count} Räume" } },
  );
  assert.equal(errors.length, 0);
  assert.equal(warnings.length, 0);
  assert.equal(clean["rooms.empty"], "Keine Räume");
  assert.deepEqual(clean["rooms.count_rooms"], { one: "{count} Raum", other: "{count} Räume" });
});

// 19. A non-object locale is rejected ENTIRELY (never throws).
check("validateLocale: non-object rejected entirely", () => {
  for (const bad of [null, undefined, "x", 42, ["a"]]) {
    const r = validateLocale(bad);
    assert.deepEqual(r.clean, {});
    assert.ok(r.errors.length >= 1, `expected error for ${JSON.stringify(bad)}`);
  }
});

// 20. Prototype-pollution keys are dropped (no pollution of the clean object).
check("validateLocale: unsafe keys dropped, no prototype pollution", () => {
  const hostile = JSON.parse('{"__proto__":{"polluted":1},"constructor":"x","rooms.empty":"ok"}');
  const { clean } = validateLocale(hostile);
  assert.equal(clean["rooms.empty"], "ok");
  assert.equal({}.polluted, undefined, "Object prototype was polluted");
  assert.ok(!Object.prototype.hasOwnProperty.call(clean, "__proto__"));
});

// 21. Bad value shapes (non-string/object, array, empty/non-string plural form)
//     are dropped with an error; valid siblings still load.
check("validateLocale: bad value shapes dropped", () => {
  const { clean, errors } = validateLocale({
    "a.num": 5,
    "a.arr": ["x"],
    "a.emptyobj": {},
    "a.badform": { one: "ok", other: 7 },
    "rooms.empty": "fine",
  });
  for (const k of ["a.num", "a.arr", "a.emptyobj", "a.badform"]) {
    assert.ok(!(k in clean), `${k} should be dropped`);
  }
  assert.equal(clean["rooms.empty"], "fine");
  assert.ok(errors.length >= 4);
});

// 22. Placeholder parity: a MISSING placeholder drops the key (a lost {name}
//     would render wrong); an EXTRA placeholder only warns (renders literally).
check("validateLocale: placeholder parity vs English", () => {
  // map.assign_link_to in en is "Link to {name}"; a translation dropping {name}
  // is an error (the link target would vanish).
  const missing = validateLocale({ "map.assign_link_to": "Verknüpfen" });
  assert.ok(!("map.assign_link_to" in missing.clean), "missing-{name} key should drop");
  assert.ok(missing.errors.some((e) => e.includes("map.assign_link_to")));
  // An extra placeholder is kept with a warning.
  const extra = validateLocale({ "rooms.empty": "Leer {oops}" });
  assert.equal(extra.clean["rooms.empty"], "Leer {oops}");
  assert.ok(extra.warnings.some((w) => w.includes("rooms.empty")));
});

// 23. An unknown key (not in English) is kept but warned; English fallback is
//     never removable (clean is only a subset — translate still falls back).
check("validateLocale: unknown key kept+warned; English fallback intact", () => {
  const { clean, warnings } = validateLocale({ "made.up.key": "x" });
  assert.equal(clean["made.up.key"], "x");
  assert.ok(warnings.some((w) => w.includes("made.up.key")));
  // A registered partial locale still falls back to English for absent keys.
  registerLocale("vv", { "rooms.empty": "VV empty" });
  assert.equal(translate("vv", "rooms.empty"), "VV empty");
  assert.equal(translate("vv", "common.cancel"), translate("en", "common.cancel"));
});

// --- localeSource + loadLocale (external intake) -------------------------

// 24. localeSource: url wins; else url_map[lang] then base-lang; else null.
check("localeSource: url / url_map resolution", () => {
  assert.equal(localeSource({ i18n: { url: "/a.json" } }, "de").url, "/a.json");
  assert.equal(localeSource({ i18n: { url_map: { de: "/de.json" } } }, "de-DE").url, "/de.json"); // base-lang
  assert.equal(localeSource({ i18n: { url_map: { ru: "/ru.json" } } }, "de"), null); // no entry
  assert.equal(localeSource({}, "de"), null);          // no i18n block
  assert.equal(localeSource(undefined, "de"), null);   // no config
  assert.equal(localeSource({ i18n: { url: "/a.json" } }, "de").key, "de|/a.json"); // one-shot identity
});

// 25. loadLocale: a valid file is fetched, validated, registered; the UI then
//     resolves the loaded strings and still falls back to English for the rest.
await checkAsync("loadLocale: valid file registers + UI switches", async () => {
  const fetchImpl = async () => ({ ok: true, status: 200, json: async () => ({ "common.cancel": "ZZcancel" }) });
  const r = await loadLocale("/x.json", "lz", { fetchImpl });
  assert.equal(r.ok, true);
  assert.equal(r.loaded, 1);
  assert.equal(translate("lz", "common.cancel"), "ZZcancel");
  assert.equal(translate("lz", "common.close"), translate("en", "common.close")); // fallback intact
});

// 26. loadLocale NEVER throws — !ok, non-JSON, and network errors all resolve to
//     ok:false and leave English untouched.
await checkAsync("loadLocale: failures keep English (never throws)", async () => {
  const notOk = await loadLocale("/x", "lf", { fetchImpl: async () => ({ ok: false, status: 404 }) });
  assert.equal(notOk.ok, false);
  const badJson = await loadLocale("/x", "lf", { fetchImpl: async () => ({ ok: true, status: 200, json: async () => { throw new Error("bad json"); } }) });
  assert.equal(badJson.ok, false);
  const netErr = await loadLocale("/x", "lf", { fetchImpl: async () => { throw new Error("network down"); } });
  assert.equal(netErr.ok, false);
  assert.equal(translate("lf", "common.cancel"), translate("en", "common.cancel")); // never registered
});

// 27. loadDroppedLocales: reads the auto-generated index, loads each file via
//     loadLocale, tags it "custom" (so it's gated), and surfaces it in the
//     picker. A missing index resolves soft (ok:false), never throws.
await checkAsync("loadDroppedLocales: discovers + loads drop-in files (custom-tagged)", async () => {
  const files = {
    "index.json": ["xx-drop.json", "skip.txt", "index.json"], // non-json + self ignored
    "xx-drop.json": { "rooms.empty": "Dropped room" },
  };
  const fetchImpl = async (url) => {
    const name = String(url).split("/").pop();
    if (!(name in files)) return { ok: false, status: 404 };
    return { ok: true, status: 200, json: async () => files[name] };
  };
  const report = await loadDroppedLocales("/eufy_vacuum/locales", { fetchImpl });
  assert.equal(report.ok, true);
  assert.deepEqual(report.loaded, ["xx-drop"]);
  assert.equal(translate("xx-drop", "rooms.empty"), "Dropped room");
  assert.ok(listLocales().some((l) => l.code === "xx-drop"), "drop-in appears in the picker");
  assert.equal(resolveLang({ locale: { language: "xx-drop" } }, {}), "en"); // custom -> gated
  assert.equal(resolveLang({}, {}, "xx-drop"), "xx-drop");                  // override reaches it

  // A missing index is soft (never throws).
  const missing = await loadDroppedLocales("/none", { fetchImpl: async () => ({ ok: false, status: 404 }) });
  assert.equal(missing.ok, false);

  // en.json is REFUSED — the English base is the fallback source of truth.
  const withEn = {
    "index.json": ["en.json", "yy-drop.json"],
    "en.json": { "rooms.empty": "HIJACKED" },
    "yy-drop.json": { "rooms.empty": "Y" },
  };
  const fetchEn = async (url) => {
    const name = String(url).split("/").pop();
    return name in withEn ? { ok: true, status: 200, json: async () => withEn[name] } : { ok: false, status: 404 };
  };
  const r2 = await loadDroppedLocales("/eufy_vacuum/locales", { fetchImpl: fetchEn });
  assert.ok(!r2.loaded.includes("en"), "en.json is refused");
  assert.notEqual(translate("en", "rooms.empty"), "HIJACKED");          // base intact
  assert.ok(r2.loaded.includes("yy-drop"));                            // others still load
});

/* =========================================================
   B. KEY CROSS-CHECK (used in src  <->  defined in en.js)
   ========================================================= */
console.log("\nB. key cross-check");

// REACHABILITY IS DERIVED FROM SOURCE — not a hand-maintained allowlist. A defined
// key counts as referenced if the code uses it one of three PROVABLE ways:
//   (1) a literal `t("KEY")` / `tRaw("KEY")` call (also the orphan source);
//   (2) the full key appears as a quoted string anywhere in src — i.e. it's a
//       DATA VALUE handed to t() through a variable (registry `titleKey:"…"`, a
//       nav `labelKey:"mobile.tab_…"`, etc.);
//   (3) it matches a `t(`…${…}…`)` TEMPLATE found in src, each `${…}` standing in
//       for one key segment (map.variant_${k}_label, maintenance.status_${s}, …).
// Because the template patterns are extracted from the code, deleting a
// construction site automatically un-exempts its keys — there is no trusted list.
const LIT = /\.t(?:Raw)?\("([^"]+)"/g;          // t("literal")
const TMPL = /\.t(?:Raw)?\(`([^`]+)`/g;          // t(`tmpl ${var}`)
const SKIP_I18N = `${join("src", "i18n")}`;

// Build a regex from a t(`…`) template: literal segments stay literal, each ${…}
// becomes one [A-Za-z0-9_] key segment. A template with no namespace anchor (no "."
// in its leading literal) is REJECTED so a pathologically dynamic `${a}.${b}` can
// never silently exempt the whole catalog.
const templateToRegex = (tmpl) => {
  const parts = tmpl.split(/\$\{[^}]*\}/);
  if (!parts[0].includes(".")) return null;
  const esc = parts.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return new RegExp(`^${esc.join("[A-Za-z0-9_]+")}$`);
};

const used = new Map();      // literal-used KEY -> file
const tmplRegexes = [];      // one regex per accepted t(`…`) template
let allSrc = "";             // concatenated src (for quoted-string reachability)
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { walk(p); continue; }
    if (!p.endsWith(".js") || p.includes(SKIP_I18N)) continue;
    const txt = readFileSync(p, "utf8");
    allSrc += `${txt}\n`;
    for (const m of txt.matchAll(LIT)) if (!used.has(m[1])) used.set(m[1], relative(REPO, p));
    for (const m of txt.matchAll(TMPL)) { const rx = templateToRegex(m[1]); if (rx) tmplRegexes.push(rx); }
  }
};
walk(SRC);

// Defined keys = top-level "key": entries in en.js.
const enTxt = readFileSync(join(SRC, "i18n", "en.js"), "utf8");
const defined = new Set([...enTxt.matchAll(/^\s*"([^"]+)":/gm)].map((m) => m[1]));

// A defined key is reachable iff one of the three provable forms references it.
const stringPresent = (k) => allSrc.includes(`"${k}"`) || allSrc.includes(`'${k}'`);
const templateMatch = (k) => tmplRegexes.some((rx) => rx.test(k));
const reachable = (k) => used.has(k) || stringPresent(k) || templateMatch(k);

const orphans = [...used.keys()].filter((k) => !defined.has(k)).sort();
const dead = [...defined].filter((k) => !reachable(k)).sort();
// "dynamic" = reachable but NOT via a literal t("…") — i.e. proven by data value or template.
const dynamicReached = [...defined].filter((k) => !used.has(k) && reachable(k)).length;

console.log(`  defined: ${defined.size}   literal-used: ${used.size}   reached via data/template: ${dynamicReached}   (templates: ${tmplRegexes.length})`);

if (orphans.length === 0) {
  console.log("  ✓ no orphan keys (every used key exists in en.js)");
} else {
  for (const k of orphans) fail(`orphan key "${k}" used in ${used.get(k)} but missing from en.js`);
}

if (dead.length === 0) {
  console.log("  ✓ no dead keys");
} else {
  console.log(`  ⚠ ${dead.length} dead key(s) in en.js (defined, never referenced):`);
  for (const k of dead) console.log(`      - ${k}`);
}

/* =========================================================
   C. BUNDLED LOCALE VALIDATION (every shipped locale vs English)
   ========================================================= */
// Any locale file bundled under src/i18n/ (a `ru.js` etc., beyond the English
// base) must pass validateLocale against English — placeholder parity, value
// shapes, no unsafe keys — so a broken committed translation fails the BUILD,
// not the user's render. No-op until the first locale lands.
console.log("\nC. bundled locale validation");
const i18nDir = join(SRC, "i18n");
const localeFiles = readdirSync(i18nDir).filter(
  (f) =>
    f.endsWith(".js") &&
    f !== "index.js" &&
    f !== "en.js" &&
    f !== "lang-store.js" && // helper module (WS user-data store), not a catalog
    !f.endsWith(".test.js"),
);
if (localeFiles.length === 0) {
  console.log("  ✓ no bundled locales beyond en (nothing to validate yet)");
} else {
  for (const f of localeFiles) {
    const mod = await import(pathToFileURL(join(i18nDir, f)).href);
    // The catalog is the largest object-valued export (e.g. `export const ru`).
    const cat = Object.values(mod)
      .filter((v) => v && typeof v === "object" && !Array.isArray(v))
      .sort((a, b) => Object.keys(b).length - Object.keys(a).length)[0];
    if (!cat) { fail(`locale ${f}: no catalog object export`); continue; }
    const { clean, warnings, errors } = validateLocale(cat);
    if (errors.length) {
      for (const e of errors) fail(`locale ${f}: ${e}`);
    } else {
      console.log(`  ✓ ${f}: ${Object.keys(clean).length} keys valid${warnings.length ? ` (${warnings.length} warning(s))` : ""}`);
    }
  }
}

/* ========================================================= */
console.log("");
if (failures > 0) {
  console.error(`FAIL — ${failures} problem(s).`);
  process.exit(1);
}
console.log("OK — i18n contract holds and all used keys are defined.");
