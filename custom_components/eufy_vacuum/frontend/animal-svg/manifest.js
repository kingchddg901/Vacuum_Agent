/**
 * Single entry point — loads the custom element, then every registered animal.
 *
 * To enable / disable an animal: comment out or remove its line.
 * To add a new animal: drop a file in animals/ that calls AnimalSVG.register(...)
 * and add a corresponding line below.
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

// 2. Load each animal. Edit this list to add/remove animals.
await Promise.all([
  loadScript('animals/cat.js'),
  loadScript('animals/dog.js'),
  loadScript('animals/raccoon.js'),
  loadScript('animals/parrot.js'),
  loadScript('animals/snake.js'),
]);
