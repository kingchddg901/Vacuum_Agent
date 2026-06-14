/**
 * Static HTML generation for the theme gallery — the index (with the faceted
 * filter bar + search) and the per-theme detail pages. Split out of preview.mjs
 * so it has NO Playwright dependency: the real generator (preview.mjs) renders
 * the PNGs and calls these, while a fast dry-run can call the SAME functions over
 * the committed theme JSONs to preview the filter bar without re-rendering.
 *
 * Tags + attribution come from the shared theme-tags core, so the gallery and the
 * in-card picker show an identical taxonomy.
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { FACETS, facetOf, orderTags } from "../../src/theme-tags/index.mjs";

export const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---- Tag / attribution rendering (shared by the index and per-theme pages) ---- */

// One stylesheet for tag chips, author credit, and the colour-vision note —
// injected into both pages so chips look identical wherever they appear.
export const TAG_CSS = `
  .evcc-tags { display:flex; flex-wrap:wrap; gap:5px; margin:8px 0 0; }
  .evcc-tag { font-size:.7rem; line-height:1; padding:4px 7px; border-radius:999px; background:#1b212a; color:#aeb7c2; border:1px solid #2a323c; white-space:nowrap; text-transform:capitalize; }
  .evcc-tag[data-facet="accent"] { color:#cdbcf0; border-color:#3a3158; background:#241f33; }
  .evcc-tag[data-facet="mode"] { color:#9fc6ef; border-color:#2c3f56; background:#16222f; }
  .evcc-tag[data-facet="a11y"] { color:#8fe0a8; border-color:#2c513a; background:#152619; }
  .evcc-tag[data-facet="source"] { color:#f0d79a; border-color:#574b2c; background:#2a2516; }
  .evcc-tag[data-facet="vibe"] { color:#9aa3ae; font-style:italic; text-transform:none; }
  .evcc-attr { color:#aeb7c2; font-size:.82rem; margin:8px 0 0; }
  .evcc-attr a { color:#5aa9ff; text-decoration:none; }
  .evcc-attr a:hover { text-decoration:underline; }
  .evcc-source { text-transform:capitalize; padding:1px 7px; border-radius:5px; font-size:.72rem; background:#222a33; color:#cbd2da; }
  .evcc-source--core { background:#3a2f12; color:#f0d79a; }
  .evcc-source--community { background:#16263a; color:#9fc6ef; }
  .evcc-source--generated { background:#241f33; color:#cdbcf0; }
  .evcc-cb-detail { display:inline-flex; flex-direction:column; gap:3px; margin:10px 0 0; padding:9px 13px; border-radius:8px; background:#152619; border:1px solid #2c513a; font-size:.82rem; }
  .evcc-cb-detail-title { color:#8fe0a8; font-weight:600; font-size:.8rem; margin-bottom:1px; }
  .evcc-cb-detail-row { color:#cbd2da; }
  .evcc-cb-detail-row .k { color:#8b94a0; display:inline-block; min-width:64px; }
  .evcc-cb-detail-row strong { color:#e6e9ee; }`;

/** A theme's own tags as small facet-coloured chips. */
export function tagChipsHtml(tags) {
  if (!tags || !tags.length) return "";
  return `<div class="evcc-tags">${orderTags(tags)
    .map((t) => `<span class="evcc-tag" data-facet="${esc(facetOf(t))}">${esc(t)}</span>`)
    .join("")}</div>`;
}

// author_url is untrusted (it rides in from a public submission). esc() escapes
// markup but NOT dangerous URL schemes, so a `javascript:`/`data:` href would be a
// stored-XSS sink on the public Pages site. Only http(s) becomes a live link;
// anything else is dropped (the author still renders as plain text).
function safeHttpUrl(url) {
  const u = String(url || "").trim();
  return /^https?:\/\//i.test(u) ? u : "";
}

/** Author / source credit line; the author name links out when author_url is set. */
export function attributionHtml(attr) {
  if (!attr) return "";
  const bits = [];
  if (attr.author) {
    // author_url can come from an untrusted submission — open isolated, no referrer, no rank pass.
    const href = safeHttpUrl(attr.authorUrl);
    const who = href
      ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer nofollow">${esc(attr.author)}</a>`
      : esc(attr.author);
    bits.push(`by ${who}`);
  }
  if (attr.submittedBy && attr.submittedBy !== attr.author) bits.push(`submitted by ${esc(attr.submittedBy)}`);
  if (attr.source) bits.push(`<span class="evcc-source evcc-source--${esc(attr.source)}">${esc(attr.source)}</span>`);
  return bits.length ? `<p class="evcc-attr">${bits.join(" · ")}</p>` : "";
}

// NOTE: a theme that claimed `colorblind-safe` but failed verification simply
// doesn't carry the tag here — effectiveThemeTags strips it silently. The gallery
// is the published store and never calls out a merged theme's failure; the "why
// it failed" feedback lives in the submission/ingest path, surfaced to the author.

/** For a colorblind-safe theme, the separation breakdown: Min ΔE, the weakest
 *  pair (with the layman bucket + precise medical type), and the bucket it's most
 *  robust for. Positive info on the per-theme page — only when it passes. */
export function cbDetailHtml(cb) {
  if (!cb || !cb.verified || !cb.weakest || !cb.bestBucket) return "";
  const w = cb.weakest;
  const bestMin = cb.buckets?.[cb.bestBucket]?.min;
  return `<div class="evcc-cb-detail">
      <span class="evcc-cb-detail-title">◆ Colorblind-Safe</span>
      <span class="evcc-cb-detail-row"><span class="k">Min ΔE</span><strong>${cb.minDeltaE}</strong></span>
      <span class="evcc-cb-detail-row"><span class="k">Weakest</span>${esc(w.pair.join("/"))} for ${esc(w.bucket)} (${esc(w.cvd)})</span>
      <span class="evcc-cb-detail-row"><span class="k">Best for</span>${esc(cb.bestBucket)} vision${bestMin != null ? ` (ΔE ${bestMin})` : ""}</span>
    </div>`;
}

/** Per-theme detail page: the renders grouped into sections (galleries vs
 *  tabs) plus the ingest report. Written as <name>/index.html so the top
 *  index links to it. */
export function writeThemePage(dir, themeName, scope, report, shots, meta = {}) {
  const galleries = shots.filter((s) => !s.id.startsWith("tab-"));
  const tabs = shots.filter((s) => s.id.startsWith("tab-"));
  const section = (title, list) =>
    !list.length
      ? ""
      : `    <section>
      <h2>${esc(title)}</h2>
      <div class="grid">
${list
  .map(
    (s) => `        <figure>
          <figcaption>${esc(s.id)}</figcaption>
          <a href="${esc(s.id)}.png"><img loading="lazy" src="${esc(s.id)}.png" alt="${esc(s.id)}"></a>
        </figure>`,
  )
  .join("\n")}
      </div>
    </section>`;
  const skipped = report.skippedKeys.length ? esc(report.skippedKeys.join(", ")) : "none";
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(themeName)} — EVCC theme preview</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#0b0d10; color:#e6e9ee; font:15px/1.5 system-ui,-apple-system,sans-serif; }
  header { padding:24px 24px 12px; border-bottom:1px solid #1c222a; }
  header .back { color:#5aa9ff; text-decoration:none; font-size:.85rem; }
  header h1 { margin:8px 0 4px; font-size:1.5rem; }
  .meta { color:#8b94a0; font-size:.84rem; margin:0 0 2px; }
  .meta a { color:#5aa9ff; }
  .dl-row { margin:10px 0 8px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .download-btn { display:inline-block; padding:8px 15px; border:1px solid #2f6dd0; border-radius:8px; background:#173455; color:#cfe2ff; text-decoration:none; font-size:.88rem; font-weight:600; }
  .download-btn:hover { background:#1d4474; }
  .dl-hint { color:#8b94a0; font-size:.82rem; }
  .dl-hint strong { color:#cbd2da; }
  main { padding:8px 24px 48px; }
  section h2 { font-size:1.02rem; margin:26px 0 12px; color:#cbd2da; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:18px; }
  figure { margin:0; }
  figcaption { font:12px/1.4 ui-monospace,SFMono-Regular,monospace; color:#8b94a0; padding:0 0 5px; }
  img { display:block; width:100%; height:auto; border:1px solid #232a32; border-radius:8px; background:#0b0d10; }
  footer { padding:0 24px 36px; color:#6b7480; font-size:.8rem; }
${TAG_CSS}
</style>
</head>
<body>
  <header>
    <a class="back" href="../index.html">← all themes</a>
    <h1>${esc(themeName)}</h1>
    ${meta.download ? `<p class="dl-row"><a class="download-btn" href="${esc(meta.download)}" download="${esc(meta.download)}">⤓ Download theme (.json)</a> <span class="dl-hint">then import it via the card's <strong>Upload</strong> button</span></p>` : ""}
    <p class="meta">scope: ${scope.length ? esc(scope.join(", ")) : "full"} · ${report.keyCount} tokens · ${report.clamped} clamped · ${report.skippedKeys.length} skipped</p>
    <p class="meta">skipped keys: ${skipped} · <a href="ingest-report.json">ingest report</a> · <a href="_contact-sheet.png">contact sheet</a></p>
    ${attributionHtml(meta.attr)}
    ${tagChipsHtml(meta.tags)}
    ${cbDetailHtml(meta.colorblind)}
  </header>
  <main>
${section("All-states galleries", galleries)}
${section("Card tabs", tabs)}
  </main>
  <footer>The real card recolored by this export, rendered through the harness ingest gate.</footer>
</body>
</html>
`;
  writeFileSync(join(dir, "index.html"), html);
}

/** Write a self-contained static gallery index over the rendered themes. */
export function writeIndex(entries, outDir) {
  // Which tokens actually occur — so the filter bar only shows chips that match
  // something (an empty facet never appears).
  const present = new Set();
  for (const e of entries) for (const t of e.filterTokens) present.add(t);

  // Faceted filter bar: a labelled row per facet, chips for present tags only.
  const facetBar = FACETS.map((f) => {
    const tags = f.tags.filter((t) => present.has(t));
    if (!tags.length) return "";
    return `      <div class="facet">
        <span class="facet-label">${esc(f.label)}</span>
        ${tags.map((t) => `<button class="chip" data-facet="${f.key}" data-tag="${esc(t)}">${esc(t)}</button>`).join("\n        ")}
      </div>`;
  })
    .filter(Boolean)
    .join("\n");

  const cards = entries
    .map((e) => {
      const dir = encodeURIComponent(e.name);
      const meta = `${e.scope.length ? esc(e.scope.join(", ")) : "full"} · ${e.report.keyCount} tokens`;
      // data-tags drives the facet filter; data-text drives the search box
      // (name + author + every tag, incl. free-text vibe tags).
      const dataTags = esc(e.filterTokens.join(" "));
      const dataText = esc([e.themeName, e.attr?.author || "", ...(e.tags || [])].join(" ").toLowerCase());
      const dl = e.download
        ? `<a class="card-dl" href="${dir}/${encodeURIComponent(e.download)}" download="${esc(e.download)}" title="Download this theme (.json) to import in the card">⤓ Download</a>`
        : "";
      return `      <article class="card" data-tags="${dataTags}" data-text="${dataText}">
        <a class="thumb" href="${dir}/index.html"><img loading="lazy" src="${dir}/thumb.png" alt="${esc(e.themeName)} room card"></a>
        <h2><a href="${dir}/index.html">${esc(e.themeName)}</a></h2>
        <p class="meta">${meta}</p>
        ${attributionHtml(e.attr)}
        ${tagChipsHtml(e.tags)}
        ${dl}
      </article>`;
    })
    .join("\n");

  const repoSlug = process.env.GITHUB_REPOSITORY || "kingchddg901/Vacuum_Agent";
  const submitUrl = `https://github.com/${repoSlug}/issues/new?template=theme-submission.yml`;

  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EVCC theme gallery</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; background: #0b0d10; color: #e6e9ee; font: 15px/1.5 system-ui, -apple-system, sans-serif; }
  header { padding: 28px 24px 8px; }
  header h1 { margin: 0 0 4px; font-size: 1.4rem; }
  header p { margin: 0; color: #99a2ad; }
  a.submit { display: inline-block; margin-top: 12px; padding: 8px 16px; border: 1px solid #2f6dd0; border-radius: 8px; background: #173455; color: #cfe2ff; text-decoration: none; font-size: 0.9rem; font-weight: 600; }
  a.submit:hover { background: #1d4474; }
  .toolbar { padding: 6px 24px 12px; border-bottom: 1px solid #1c222a; }
  .searchrow { display: flex; gap: 12px; align-items: center; margin: 0 0 12px; flex-wrap: wrap; }
  #search { flex: 1; min-width: 200px; max-width: 420px; padding: 9px 13px; border-radius: 8px; border: 1px solid #2a323c; background: #14181d; color: #e6e9ee; font: inherit; }
  #search:focus { outline: none; border-color: #2f6dd0; }
  #count { color: #8b94a0; font-size: 0.82rem; }
  #clear { display: none; background: none; border: 1px solid #2a323c; color: #9fc6ef; border-radius: 8px; padding: 7px 13px; cursor: pointer; font: inherit; font-size: 0.82rem; }
  #clear:hover { border-color: #3a4754; }
  .facets { display: flex; flex-direction: column; gap: 7px; }
  .facet { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .facet-label { color: #8b94a0; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; width: 70px; flex: none; }
  .chip { font-size: 0.78rem; padding: 5px 11px; border-radius: 999px; border: 1px solid #2a323c; background: #14181d; color: #aeb7c2; cursor: pointer; font: inherit; text-transform: capitalize; }
  .chip:hover { border-color: #3a4754; color: #e6e9ee; }
  .chip.on { background: #1d4474; border-color: #2f6dd0; color: #cfe2ff; }
  main { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; padding: 20px 24px 40px; }
  .card { background: #14181d; border: 1px solid #232a32; border-radius: 12px; padding: 12px 12px 12px; }
  .card h2 { margin: 10px 0 2px; font-size: 1.08rem; }
  .card h2 a { color: inherit; text-decoration: none; }
  .card .thumb { display: block; }
  .meta { margin: 0; color: #8b94a0; font-size: 0.8rem; }
  .card img { display: block; width: 100%; height: auto; border-radius: 8px; border: 1px solid #232a32; background: #0b0d10; }
  .card-dl { display: inline-block; margin: 10px 0 0; font-size: 0.82rem; font-weight: 600; color: #cfe2ff; text-decoration: none; padding: 5px 11px; border: 1px solid #2f6dd0; border-radius: 7px; background: #173455; }
  .card-dl:hover { background: #1d4474; }
  .empty { grid-column: 1 / -1; color: #8b94a0; padding: 30px 4px; text-align: center; }
  .links { margin: 8px 0 0; font-size: 0.8rem; }
  .links a, header a { color: #5aa9ff; }
  footer { padding: 0 24px 36px; color: #6b7480; font-size: 0.8rem; }
  footer code { color: #99a2ad; }
${TAG_CSS}
</style>
</head>
<body>
  <header>
    <h1>EVCC theme gallery</h1>
    <p>${entries.length} theme${entries.length === 1 ? "" : "s"} rendered through the harness ingest gate — each is the real card recolored by a committed export. Click a theme to open its full preview, or <strong>⤓ Download</strong> any theme and import it via the card's Upload button.</p>
    <p><a class="submit" href="${submitUrl}">+ Submit a theme</a> <a class="submit" href="docs/">📖 Documentation</a></p>
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
    <p class="empty" id="empty" hidden>No themes match these filters.</p>
  </main>
  <footer>Generated by <code>harness/preview.mjs</code>. Filters: tags are auto-derived from each palette; <code>colorblind-safe</code> is system-verified. Add a theme by committing its export to <code>gallery/themes/</code>.</footer>
  <script>
  (function () {
    var search = document.getElementById('search');
    var count = document.getElementById('count');
    var clearBtn = document.getElementById('clear');
    var empty = document.getElementById('empty');
    var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
    var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
    var active = new Map(); // facet -> Set(selected tags)

    function apply() {
      var q = (search.value || '').trim().toLowerCase();
      var shown = 0;
      for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        var tagSet = new Set((card.dataset.tags || '').split(' ').filter(Boolean));
        var ok = true;
        // AND across facets, OR within a facet.
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
      clearBtn.style.display = anyActive ? 'inline-block' : 'none'; // '' would revert to the CSS 'none'
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
