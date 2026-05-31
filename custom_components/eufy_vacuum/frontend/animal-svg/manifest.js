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

// 2. Load every animal listed in the auto-generated index.
const animalFiles = await fetch(new URL('animals/index.json', BASE).href).then(r => r.json());
await Promise.all(animalFiles.map(f => loadScript('animals/' + f)));
