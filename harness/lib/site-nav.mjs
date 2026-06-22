/**
 * Shared site navigation for the Pages site (landing + the two galleries).
 * One bar, depth-aware relative links, so every generated page links to all the
 * others. The docs (MkDocs) add their own equivalent nav in mkdocs.yml.
 *
 * Site layout (GitHub Pages):
 *   /            landing      depth 0
 *   /themes/     theme index  depth 1   ·  /themes/<slug>/   depth 2
 *   /animals/    animal index depth 1   ·  /animals/<slug>/  depth 2
 *   /docs/       docs (MkDocs)
 */
export const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

export const SITE_NAV_CSS = `
  .site-nav { display:flex; gap:4px; flex-wrap:wrap; align-items:center; padding:9px 24px; background:#0e1116; border-bottom:1px solid #1c222a; position:sticky; top:0; z-index:20; }
  .site-nav .brand { color:#e6e9ee; font-weight:700; margin-right:10px; text-decoration:none; }
  .site-nav a { color:#aeb7c2; text-decoration:none; font-size:.85rem; font-weight:600; padding:6px 12px; border-radius:8px; }
  .site-nav a:hover { background:#1b212a; color:#e6e9ee; }
  .site-nav a.active { color:#cfe2ff; background:#173455; }`;

/**
 * @param {number} depth   how many levels deep the page is (0 = root landing).
 * @param {string} active  one of: home | themes | animals | docs
 */
export function siteNav(depth = 0, active = "") {
  const p = "../".repeat(depth);
  const link = (href, label, key) =>
    `<a href="${p}${href}"${active === key ? ' class="active"' : ""}>${label}</a>`;
  return `<nav class="site-nav">
    <a class="brand" href="${p || "."}/">Vacuum Agent</a>
    ${link("", "Home", "home")}
    ${link("themes/", "🎨 Themes", "themes")}
    ${link("animals/", "🦊 Animals", "animals")}
    ${link("docs/", "📖 Docs", "docs")}
  </nav>`;
}
