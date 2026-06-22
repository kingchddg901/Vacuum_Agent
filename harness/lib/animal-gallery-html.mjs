/**
 * Static HTML for the /animals gallery — the index (faceted filter + search) and
 * the per-animal detail pages. Mirrors lib/gallery-html.mjs (the theme gallery)
 * but with animal facets: body plan, companion vs Rainbow Bridge, licence, source.
 * No Playwright dependency — preview-animals.mjs renders the PNGs and calls these.
 *
 * Security: author_url rides in from public submissions, so it goes through
 * safeHttpUrl() — only http(s) becomes a live link (a javascript:/data: href
 * would be a stored-XSS sink on the public Pages site). esc() escapes markup.
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

export const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

export function safeHttpUrl(url) {
  const u = String(url || "").trim();
  return /^https?:\/\//i.test(u) ? u : "";
}

/** The filter facets shown on the index. Each animal contributes the tokens it
 *  matches; only tokens that actually occur get a chip. */
export const ANIMAL_FACETS = [
  { key: "type", label: "Body", tags: ["quadruped", "parrot"] },
  { key: "group", label: "Group", tags: ["companion", "memorial"] },
  { key: "license", label: "Licence", tags: ["cc0-1.0", "cc-by-4.0", "mit", "apache-2.0"] },
  { key: "source", label: "Source", tags: ["community", "core"] },
];

const FACET_OF = (() => {
  const map = new Map();
  for (const f of ANIMAL_FACETS) for (const t of f.tags) map.set(t, f.key);
  return (t) => map.get(t) || "tag";
})();

/** The filter tokens for one animal (drives the facet chips + dataset). */
export function filterTokensFor(animal) {
  const toks = [
    animal.type,
    animal.memorial ? "memorial" : "companion",
    String(animal.license || "").toLowerCase(),
    animal.source || "community",
  ];
  return [...new Set(toks.filter(Boolean))];
}

const TAG_CSS = `
  .a-tags { display:flex; flex-wrap:wrap; gap:5px; margin:8px 0 0; }
  .a-tag { font-size:.7rem; line-height:1; padding:4px 7px; border-radius:999px; background:#1b212a; color:#aeb7c2; border:1px solid #2a323c; text-transform:capitalize; }
  .a-tag[data-facet="type"] { color:#9fc6ef; border-color:#2c3f56; background:#16222f; }
  .a-tag[data-facet="group"] { color:#cdbcf0; border-color:#3a3158; background:#241f33; }
  .a-tag[data-facet="license"] { color:#f0d79a; border-color:#574b2c; background:#2a2516; text-transform:none; }
  .a-tag[data-facet="source"] { color:#8fe0a8; border-color:#2c513a; background:#152619; }
  .a-tag[data-facet="tag"] { color:#9aa3ae; font-style:italic; text-transform:none; }
  .a-memorial { color:#cdbcf0; }
  .a-attr { color:#aeb7c2; font-size:.82rem; margin:8px 0 0; }
  .a-attr a { color:#5aa9ff; text-decoration:none; }
  .a-attr a:hover { text-decoration:underline; }`;

/** Author / source credit; the author links out only when author_url is http(s). */
export function attributionHtml(animal) {
  const bits = [];
  if (animal.author) {
    const href = safeHttpUrl(animal.author_url);
    const who = href
      ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer nofollow">${esc(animal.author)}</a>`
      : esc(animal.author);
    bits.push(`by ${who}`);
  }
  if (animal.submitted_by && animal.submitted_by !== animal.author) bits.push(`submitted by ${esc(animal.submitted_by)}`);
  return bits.length ? `<p class="a-attr">${bits.join(" · ")}</p>` : "";
}

function chipRowHtml(animal) {
  const toks = filterTokensFor(animal);
  const labels = {
    ...Object.fromEntries(toks.map((t) => [t, t])),
    memorial: "🌈 Rainbow Bridge",
    companion: "companion",
  };
  return `<div class="a-tags">${toks
    .map((t) => `<span class="a-tag" data-facet="${esc(FACET_OF(t))}">${esc(labels[t] || t)}</span>`)
    .join("")}${(animal.tags || [])
    .map((t) => `<span class="a-tag" data-facet="tag">${esc(t)}</span>`)
    .join("")}</div>`;
}

/** Per-animal detail page: the pose strip + metadata + a descriptor download. */
export function writeAnimalPage(dir, animal, poses, meta = {}) {
  const strip = poses
    .map(
      (p) => `        <figure>
          <figcaption>${esc(p.pose)}</figcaption>
          <a href="${esc(p.file)}"><img loading="lazy" src="${esc(p.file)}" alt="${esc(animal.name)} ${esc(p.pose)}"></a>
        </figure>`,
    )
    .join("\n");
  const themeable = Object.keys(animal.colors || {}).filter((k) => k !== "--animal-eye").length;
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(animal.name)} — Vacuum Agent animal</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#0b0d10; color:#e6e9ee; font:15px/1.5 system-ui,-apple-system,sans-serif; }
  header { padding:24px 24px 12px; border-bottom:1px solid #1c222a; }
  header .back { color:#5aa9ff; text-decoration:none; font-size:.85rem; }
  header h1 { margin:8px 0 4px; font-size:1.5rem; }
  .meta { color:#8b94a0; font-size:.84rem; margin:0 0 2px; }
  .desc { color:#cbd2da; font-size:.95rem; margin:8px 0 2px; }
  .dl-row { margin:10px 0 8px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .download-btn { display:inline-block; padding:8px 15px; border:1px solid #2f6dd0; border-radius:8px; background:#173455; color:#cfe2ff; text-decoration:none; font-size:.88rem; font-weight:600; }
  .download-btn:hover { background:#1d4474; }
  .dl-hint { color:#8b94a0; font-size:.82rem; }
  main { padding:8px 24px 48px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:18px; }
  figure { margin:0; }
  figcaption { font:12px/1.4 ui-monospace,SFMono-Regular,monospace; color:#8b94a0; padding:0 0 5px; }
  img { display:block; width:100%; height:auto; border:1px solid #232a32; border-radius:8px; background:#0b0d10; }
  footer { padding:0 24px 36px; color:#6b7480; font-size:.8rem; }
${TAG_CSS}
</style>
</head>
<body>
  <header>
    <a class="back" href="../index.html">← all animals</a>
    <h1>${esc(animal.name)}${animal.memorial ? ` <span class="a-memorial">· 🌈 Rainbow Bridge</span>` : ""}</h1>
    ${animal.description ? `<p class="desc">${esc(animal.description)}</p>` : ""}
    ${meta.download ? `<p class="dl-row"><a class="download-btn" href="${esc(meta.download)}" download="${esc(meta.download)}">⤓ Download descriptor (.json)</a> <span class="dl-hint">the source for the in-card companion</span></p>` : ""}
    <p class="meta">${esc(animal.type)} · ${themeable ? `${themeable} themeable colour${themeable === 1 ? "" : "s"}` : "baked (eye only)"} · licence ${esc(animal.license || "—")}</p>
    ${attributionHtml(animal)}
    ${chipRowHtml(animal)}
  </header>
  <main>
    <div class="grid">
${strip}
    </div>
  </main>
  <footer>Rendered through the real animal-svg framework — the same companion you pick in the card.</footer>
</body>
</html>
`;
  writeFileSync(join(dir, "index.html"), html);
}

/** The /animals gallery index over the rendered animals. */
export function writeAnimalIndex(entries, outDir) {
  const present = new Set();
  for (const e of entries) for (const t of e.filterTokens) present.add(t);

  const facetBar = ANIMAL_FACETS.map((f) => {
    const tags = f.tags.filter((t) => present.has(t));
    if (!tags.length) return "";
    return `      <div class="facet">
        <span class="facet-label">${esc(f.label)}</span>
        ${tags.map((t) => `<button class="chip" data-facet="${f.key}" data-tag="${esc(t)}">${esc(t === "memorial" ? "🌈 memorial" : t)}</button>`).join("\n        ")}
      </div>`;
  })
    .filter(Boolean)
    .join("\n");

  const cards = entries
    .map((e) => {
      const dir = encodeURIComponent(e.id);
      const a = e.animal;
      const dataTags = esc(e.filterTokens.join(" "));
      const dataText = esc([a.name, a.author || "", ...(a.tags || [])].join(" ").toLowerCase());
      const dl = e.download
        ? `<a class="card-dl" href="${dir}/${encodeURIComponent(e.download)}" download="${esc(e.download)}" title="Download this animal's descriptor (.json)">⤓ Download</a>`
        : "";
      return `      <article class="card" data-tags="${dataTags}" data-text="${dataText}">
        <a class="thumb" href="${dir}/index.html"><img loading="lazy" src="${dir}/thumb.png" alt="${esc(a.name)}"></a>
        <h2><a href="${dir}/index.html">${esc(a.name)}${a.memorial ? ` <span class="a-memorial">🌈</span>` : ""}</a></h2>
        <p class="meta">${esc(a.type)}</p>
        ${attributionHtml(a)}
        ${chipRowHtml(a)}
        ${dl}
      </article>`;
    })
    .join("\n");

  const repoSlug = process.env.GITHUB_REPOSITORY || "kingchddg901/Vacuum_Agent";
  const submitUrl = `https://github.com/${repoSlug}/issues/new?template=animal-submission.yml`;

  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vacuum Agent — animal gallery</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#0b0d10; color:#e6e9ee; font:15px/1.5 system-ui,-apple-system,sans-serif; }
  header { padding:28px 24px 8px; }
  header h1 { margin:0 0 4px; font-size:1.4rem; }
  header p { margin:0; color:#99a2ad; }
  a.submit { display:inline-block; margin-top:12px; padding:8px 16px; border:1px solid #2f6dd0; border-radius:8px; background:#173455; color:#cfe2ff; text-decoration:none; font-size:.9rem; font-weight:600; }
  a.submit:hover { background:#1d4474; }
  .toolbar { padding:6px 24px 12px; border-bottom:1px solid #1c222a; }
  .searchrow { display:flex; gap:12px; align-items:center; margin:0 0 12px; flex-wrap:wrap; }
  #search { flex:1; min-width:200px; max-width:420px; padding:9px 13px; border-radius:8px; border:1px solid #2a323c; background:#14181d; color:#e6e9ee; font:inherit; }
  #search:focus { outline:none; border-color:#2f6dd0; }
  #count { color:#8b94a0; font-size:.82rem; }
  #clear { display:none; background:none; border:1px solid #2a323c; color:#9fc6ef; border-radius:8px; padding:7px 13px; cursor:pointer; font:inherit; font-size:.82rem; }
  .facets { display:flex; flex-direction:column; gap:7px; }
  .facet { display:flex; flex-wrap:wrap; align-items:center; gap:6px; }
  .facet-label { color:#8b94a0; font-size:.72rem; text-transform:uppercase; letter-spacing:.04em; width:70px; flex:none; }
  .chip { font-size:.78rem; padding:5px 11px; border-radius:999px; border:1px solid #2a323c; background:#14181d; color:#aeb7c2; cursor:pointer; font:inherit; text-transform:capitalize; }
  .chip:hover { border-color:#3a4754; color:#e6e9ee; }
  .chip.on { background:#1d4474; border-color:#2f6dd0; color:#cfe2ff; }
  .chip[data-facet="license"] { text-transform:none; }
  main { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:18px; padding:20px 24px 40px; }
  .card { background:#14181d; border:1px solid #232a32; border-radius:12px; padding:12px; }
  .card h2 { margin:10px 0 2px; font-size:1.08rem; }
  .card h2 a { color:inherit; text-decoration:none; }
  .meta { margin:0; color:#8b94a0; font-size:.8rem; }
  .card img { display:block; width:100%; height:auto; border-radius:8px; border:1px solid #232a32; background:#0b0d10; }
  .card-dl { display:inline-block; margin:10px 0 0; font-size:.82rem; font-weight:600; color:#cfe2ff; text-decoration:none; padding:5px 11px; border:1px solid #2f6dd0; border-radius:7px; background:#173455; }
  .empty { grid-column:1 / -1; color:#8b94a0; padding:30px 4px; text-align:center; }
  footer { padding:0 24px 36px; color:#6b7480; font-size:.8rem; }
  footer code { color:#99a2ad; }
${TAG_CSS}
</style>
</head>
<body>
  <header>
    <h1>Vacuum Agent — animal gallery</h1>
    <p>${entries.length} companion${entries.length === 1 ? "" : "s"}, each rendered through the real animal-svg framework. Click one to see every pose, or <strong>⤓ Download</strong> its descriptor. Baked tributes live in <span class="a-memorial">🌈 Rainbow Bridge</span>.</p>
    <p><a class="submit" href="${submitUrl}">+ Submit an animal</a> <a class="submit" href="../">🎨 Theme gallery</a> <a class="submit" href="../docs/contributing/animal-authoring/">📖 Authoring guide</a></p>
  </header>
  <nav class="toolbar">
    <div class="searchrow">
      <input id="search" type="search" placeholder="Search name, author, or tag…" autocomplete="off">
      <span id="count">${entries.length} of ${entries.length}</span>
      <button id="clear" type="button">Clear filters</button>
    </div>
    <div class="facets">
${facetBar}
    </div>
  </nav>
  <main id="grid">
${cards}
    <p class="empty" id="empty" hidden>No animals match these filters.</p>
  </main>
  <footer>Generated by <code>harness/preview-animals.mjs</code>. Add one by submitting a descriptor or committing it to <code>gallery/animals/</code>.</footer>
  <script>
  (function () {
    var search = document.getElementById('search');
    var count = document.getElementById('count');
    var clearBtn = document.getElementById('clear');
    var empty = document.getElementById('empty');
    var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
    var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
    var active = new Map();
    function apply() {
      var q = (search.value || '').trim().toLowerCase();
      var shown = 0;
      for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        var tagSet = new Set((card.dataset.tags || '').split(' ').filter(Boolean));
        var ok = true;
        active.forEach(function (sel) {
          if (!ok || !sel.size) return;
          var any = false;
          sel.forEach(function (t) { if (tagSet.has(t)) any = true; });
          if (!any) ok = false;
        });
        if (ok && q) ok = (card.dataset.text || '').indexOf(q) !== -1;
        card.style.display = ok ? '' : 'none';
        if (ok) shown++;
      }
      count.textContent = shown + ' of ' + cards.length;
      empty.hidden = shown !== 0;
      var anyActive = !!q;
      active.forEach(function (sel) { if (sel.size) anyActive = true; });
      clearBtn.style.display = anyActive ? 'inline-block' : 'none';
    }
    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        var f = chip.dataset.facet, t = chip.dataset.tag;
        if (!active.has(f)) active.set(f, new Set());
        var sel = active.get(f);
        if (sel.has(t)) { sel.delete(t); chip.classList.remove('on'); }
        else { sel.add(t); chip.classList.add('on'); }
        apply();
      });
    });
    search.addEventListener('input', apply);
    clearBtn.addEventListener('click', function () {
      search.value = '';
      active.forEach(function (sel) { sel.clear(); });
      chips.forEach(function (chip) { chip.classList.remove('on'); });
      apply();
    });
    apply();
  })();
  </script>
</body>
</html>
`;
  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, "index.html"), html);
}
