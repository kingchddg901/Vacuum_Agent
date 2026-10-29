/**
 * Single entry point — loads the custom element, then every registered animal.
 *
 * To add a new animal: drop a .js file in animals/ that calls
 * AnimalSVG.register(...) and restart Home Assistant. The integration
 * generates animals/index.json at startup from whatever .js files exist
 * in that directory — no edit to this file required.
 *
 * To remove an animal: delete its .js file and restart HA.
 *
 * Order matters only in that animal-svg.js MUST load first; among the animal
 * files, order is irrelevant.
 *
 * Usage:
 *   <script type="module" src="/local/animal-svg/manifest.js"></script>
 *   <animal-svg animal="cat" pose="walking"></animal-svg>
 *
 * Or as an HA Lovelace resource (Settings → Dashboards → Resources):
 *   URL:  /local/animal-svg/manifest.js
 *   Type: JavaScript Module
 */

const BASE = new URL('.', import.meta.url);

async function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = new URL(src, BASE).href;
    s.async = false; // preserve execution order
    s.onload = resolve;
    s.onerror = () => reject(new Error('Failed to load ' + s.src));
    document.head.appendChild(s);
  });
}

// 1. Load the element + registry first.
await loadScript('animal-svg.js');

// 2. Load every animal listed in the index.
//
// `animals/index.json` is generated at HA startup from whatever .js files are in
// that directory — that is what makes a drop-in animal work without editing this
// file — AND it is tracked and shipped, so it is present the moment a card-only
// update lands rather than after the next restart. It was gitignored until
// 2026-10-29, so a HACS update replaced the folder without it, this fetch got a
// 404 whose body is not JSON, the rejection was swallowed upstream, and the map's
// mascot was simply absent until HA restarted. See the note in .gitignore.
//
// `r.ok` is checked rather than parsing whatever came back, because the failure to
// handle was a 404 served as HTML.
const index = await fetch(new URL('animals/index.json', BASE).href)
  .then(r => (r.ok ? r.json() : null))
  .catch(() => null);
// Bare `<id>.js` names only. Each entry is interpolated into `animals/<entry>` below, so
// an entry carrying a path separator would load an arbitrary served file — and this index
// is one of the few paths a community animal PR is allowed to touch, which is precisely
// why the shape is enforced here as well as in that PR gate.
const animalFiles = Array.isArray(index)
  ? index.filter(f => typeof f === 'string' && /^[a-z0-9-]+\.js$/.test(f))
  : [];
if (Array.isArray(index) && index.length !== animalFiles.length) {
  console.warn('[animal-svg] ignored ' + (index.length - animalFiles.length) +
    ' index entr(y/ies) that are not bare "<id>.js" names');
}
if (!animalFiles.length) {
  console.warn('[animal-svg] animals/index.json missing, empty or unreadable — no animals loaded');
}

// allSettled, NOT all. The index is a snapshot of the directory taken at startup,
// so the two can disagree: delete an animal's .js and the shipped index still names
// it until HA restarts. Under Promise.all that one rejected load took down every
// other animal with it, turning a missing file into a missing mascot.
const settled = await Promise.allSettled(animalFiles.map(f => loadScript('animals/' + f)));
const failed = animalFiles.filter((_, i) => settled[i].status === 'rejected');
if (failed.length) {
  console.warn('[animal-svg] did not load: ' + failed.join(', ') +
    ' (listed in animals/index.json but not served) — the rest loaded');
}
