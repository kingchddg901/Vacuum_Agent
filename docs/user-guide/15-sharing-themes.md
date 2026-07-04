# 15 — Sharing Themes

The themes you build in the card (see [Theme system](../advanced/05-theme-system.md))
are portable — pure visual styling, with no reference to your rooms, entities, or
vacuum brand — so they're easy to pass around. There's a public **theme gallery**
where you can browse themes other people have made, load one into your own card,
and submit themes you've built.

The gallery is a web page published from the project repository:
**<https://kingchddg901.github.io/Vacuum_Agent/>**

Nothing in it installs itself — you choose what to download, and every submission
is reviewed by a person before it appears.

---

## Browsing the gallery

Open the gallery in any browser. The front page is a grid of every published
theme, each shown as a single **room card** rendered in that theme, so you can
see the actual colors and textures at a glance — not just a name.

### Filtering and searching

Above the grid there's a **filter bar** and a **search box** to narrow things down.

- **Facet chips** — the bar groups tags into labelled rows: **Mode**
  (dark / light), **Accent** (red, orange, gold, green, teal, cyan, blue, purple,
  pink, mono), **Temp**, **Surface**, **Contrast**, **Access**, **Best for**, and
  **Source**. Click chips to filter. The rule is **OR within a row, AND across
  rows** — picking `blue` and `purple` under Accent shows themes that are *either*,
  while also picking `dark` under Mode narrows that to ones that are *also* dark.
  Only chips that actually match a published theme appear, so an empty facet never
  clutters the bar.
- **Search box** — type to match a theme's name, its author, or any of its tags
  (including the free-text **vibe** words like `aurora` or `cozy`, which show on
  cards but don't get their own chips). Search and the facet chips stack — the grid
  shows themes that pass both.
- A live count (**"X of Y"**) tells you how many themes match, and a **Clear
  filters** button resets everything.

The **Access** row carries the `colorblind-safe` chip, and the **Best for** row
lets you filter to themes tuned for `red-green` or `blue-yellow` vision. Both are
system-verified — a theme only carries them if it actually passed the simulation,
so filtering on them is meaningful, not just a self-claim.

### Author credit

Each card shows a small credit line — `by <author>`, optionally `submitted by …`,
and a colored **Source** badge (core / community / generated / manual). When the
author included a profile or project link, their name is a clickable link;
otherwise it's shown as plain text.

### The detail page

Click a theme to open its detail page, which shows the *real card* recolored by
that theme:

- **All-states galleries** — room cards and the review / map-bounds badges in
  every colored state at once, so you can check that statuses stay readable.
- **Card tabs** — the full card across its tabs (maintenance, base station,
  metrics, and so on).
- For a colorblind-safe theme, a **◆ Colorblind-Safe** panel showing the color
  separation it achieved and which vision type it's strongest for.

Every image is the real card rendered through the same engine the project uses
for its own testing, so what you see is what you'll get.

---

## Using a theme you found

Every card has a one-click **⤓ Download** button, and so does each theme's detail
page — that's the quickest way to grab a theme. To use one:

1. Click **⤓ Download** on the card (or on the theme's detail page) to save its
   `.json` export.
2. In the card's **Theme** tab, click **Upload** and pick the file — or
   **Import** to paste the JSON from your clipboard.
3. The theme is added to your library as a new theme; select it like any other.

The downloaded file is exactly what the card's **Upload** imports — no conversion
needed. If you'd rather browse the raw files, every published export also lives in
the project repository under
[`gallery/themes/`](https://github.com/kingchddg901/Vacuum_Agent/tree/master/gallery/themes),
but the Download button is the main path.

Loading a theme only adds styling — it never touches your rooms, queue, or
settings. Full details are in
[Import and export](../advanced/05-theme-system.md#import-and-export).

---

## Sharing a theme you built

When you've made a theme you're happy with, submit it to the gallery. (New to
building them? [Authoring a theme](../contributing/theme-authoring.md) covers the
ways to make one and what makes a theme worth sharing.)

1. In the **Theme** tab, click **Download** to save your theme's export file (or
   **Download Floor** to share just one floor type — for example "just my
   marble").
2. On the gallery, click **+ Submit a theme**. This opens a pre-filled submission
   form on the project's GitHub (you'll need a free GitHub account).
3. Paste your export JSON into the **Theme export JSON** box, fill in any of the
   optional fields you like, tick the acknowledgement, and submit.

### The optional fields

None of these are required — a bare export is fine — but they make your theme
easier to find and credit:

- **Vibe tags** — free-text mood words like `aurora`, `cosmic`, `cozy`. They feed
  the gallery's search and filter. You don't need to add the obvious facet tags
  (dark/light, blue/warm, colorblind-safe…) — those are **derived automatically**
  from your palette, so adding them by hand does nothing.
- **Author** and **Author URL** — your credit in the gallery. The URL must be a
  **direct `http(s)` profile or project link** (your GitHub, your site). URL
  shorteners (bit.ly, t.co, …) and non-web links are not accepted; if you give
  one, your theme still ships, just with your name shown without a link.
- **Submitted by** — only if you're submitting on someone else's behalf.
- **Colorblind-safe claim** — a single checkbox. Tick it only if you believe the
  four status colors (success / warning / error / info) stay distinguishable
  under color blindness. The bot **verifies** the claim — see below.

That's all you do. From there it's automatic:

- A bot validates your export — the same safety checks the card runs on import —
  and **auto-tags** it: facet tags derived from the palette, plus your vibe
  words, so it lands in the right gallery filters.
- It **verifies colorblind-safety** by simulation. If you claimed it and it
  passes, it earns the badge. If it doesn't pass, that's **not** a rejection —
  your theme still ships without the badge, and the bot tells you which color
  pair collapsed so you can fix it if you want. If you *didn't* claim it but it
  passes anyway, you get the badge as a bonus.
- It renders a preview of the real card recolored by your theme, opens a pull
  request with that preview shown **inline**, and comments back on your
  submission with a link.
- A maintainer reviews the preview and merges it. Once merged, your theme is
  published to the gallery.

Nothing goes live automatically — a person always reviews it first. If your
export can't be read (say the JSON didn't paste cleanly), the bot comments
telling you what to fix; re-copy it from the **Download** button, then close and
reopen your submission to retry.

The mechanics of what happens behind the submission form — validation, preview
rendering, and publishing — are documented for maintainers in
[frontend/render-harness](../dev/frontend/render-harness.md#8-theme-submission-issue--pr).

---

## On a phone

Everything above works on mobile too. On a narrow screen (under 600px) the
**Theme** tab lives in the bottom nav's **More** overflow sheet rather than the
top tabs — see [the nav note in the overview](01-overview.md). The footer's
**Export**, **Import**, **Download**, and **Upload** buttons are all there, so
you can pick, activate, and share whole themes from your phone.

What's *not* on mobile is the fine editing. The phone Theme tab shows only the
preset grid — the **Palette** and **Tokens** editors are desktop-only — and the
footer drops the **Download Floor** button, the floor-preset selects, and the
**Save** / **Discard** controls that belong to those editors. So build and tweak
themes on a desktop; browse, switch, import, and export them anywhere.
