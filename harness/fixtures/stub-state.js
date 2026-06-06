/**
 * ============================================================
 * HARNESS FIXTURE: STUB STATE
 * ============================================================
 *
 * PURPOSE
 * -------
 * A headless stand-in for the live `VacuumCardState` accessor
 * object (src/state/index.js) so a tab's pure `render(ctx)` can
 * run with NO Home Assistant runtime.
 *
 * WHY A NULL-OBJECT
 * -----------------
 * Renderers read ~184 distinct `state.foo()` accessors across the
 * nine tabs. Wave 1's job is the SMOKE contract — "every tab
 * renders from the stub without throwing" — not realistic data.
 * Hand-typing 184 empties would be throwaway work: Wave 2 fixtures
 * replace them with real per-tab data anyway.
 *
 * So any accessor we don't explicitly define returns a recording
 * NULL-OBJECT: callable, indexable, iterable (empty), and string/
 * number coercible — it survives `.map()`, `.length`, property
 * chains, and template interpolation without throwing. Every access
 * path it sees is recorded, so the smoke run doubles as a census of
 * the accessor surface each tab actually touches (the seed list for
 * Wave 2 fixtures).
 *
 * This is a test-harness null-object, not production code. A throw
 * here still means something real: a renderer reached OUTSIDE its
 * `state`/`ctx` contract (a true global, the DOM) — exactly the
 * contract breach the smoke test exists to catch.
 *
 * ============================================================
 */

// Array methods that must hand back a real, empty result so callers
// can keep chaining (`.map(...).join("")`, spread, `.length`, etc.).
const ARRAY_EMPTY = new Set([
  "map", "filter", "slice", "concat", "flat", "flatMap", "sort", "reverse",
]);

/**
 * Build a recursive, recording null-object. Any property access returns
 * another null-object (recording its path); any call returns itself.
 *
 * @param {Set<string>|null} record - sink for accessed paths (or null).
 * @param {string} path - dotted access path so far, for the census.
 * @returns {*} a proxy that absorbs reads/calls without throwing.
 */
export function makeNullObject(record, path = "") {
  const target = function nullObject() {};
  const obj = new Proxy(target, {
    apply: () => obj,
    construct: () => obj,
    get(t, prop) {
      switch (prop) {
        case Symbol.toPrimitive: return (hint) => (hint === "number" ? 0 : "");
        case Symbol.iterator:    return function* empty() {};
        case Symbol.asyncIterator: return undefined;
        case "toString":         return () => "";
        case "valueOf":          return () => 0;
        case "length":           return 0;
        case "then":             return undefined;        // never thenable
        case "toJSON":           return () => null;
        case "name": case "prototype": case "constructor":
          return Reflect.get(t, prop);
      }
      if (typeof prop === "symbol") return undefined;
      // Array-shaped helpers → empty results so chaining keeps working.
      if (ARRAY_EMPTY.has(prop)) return () => [];
      if (prop === "join")    return () => "";
      if (prop === "forEach") return () => {};
      if (prop === "reduce")  return (_fn, init) => init;
      if (prop === "find" || prop === "at") return () => undefined;
      if (prop === "some" || prop === "every" || prop === "includes") return () => false;
      if (prop === "indexOf" || prop === "findIndex") return () => -1;
      if (prop === "keys" || prop === "values" || prop === "entries") return () => [][prop]();
      // Anything else: record the path, hand back another null-object.
      const next = path ? `${path}.${String(prop)}` : String(prop);
      if (record) record.add(next);
      return makeNullObject(record, next);
    },
  });
  return obj;
}

/**
 * Build a stub `state` accessor object.
 *
 * The header / render-context essentials are made REAL so the card
 * chrome renders honestly (name, status dots, battery). Everything
 * else falls through to a recording null-object.
 *
 * @param {object}  [opts]
 * @param {object}  [opts.overrides] - per-accessor real returns (Wave 2 fixtures).
 * @param {Set<string>} [opts.record] - census sink for unstubbed accessors.
 * @returns {Proxy} stub state.
 */
export function makeStubState({ overrides = {}, record = null } = {}) {
  // Called WITHOUT optional chaining by buildRenderContext / renderHeader,
  // so these must exist and return sensible, typed values.
  const essentials = {
    vacuumDisplayName: () => "Alfred",
    vacuumObjectId:    () => "alfred",
    vacuumState:       () => "docked",
    vacuumStateLabel:  () => "Docked",
    batteryLevel:      () => 100,
    dockStatus:        () => "charging",
    dockStatusLabel:   () => "Charging",
    isMobileViewport:  () => false,
    isMapViewActive:   () => false,
  };

  const base = { ...essentials, ...overrides };

  return new Proxy(base, {
    get(t, prop) {
      if (prop in t) return Reflect.get(t, prop);
      if (typeof prop === "symbol") return undefined;
      if (record) record.add(String(prop));
      // Unstubbed accessor: a callable null-object (so `state.x()` and
      // `state.x?.()` both yield an absorbing value).
      return makeNullObject(record, String(prop));
    },
  });
}
