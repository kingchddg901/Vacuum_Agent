# Sharing Themes

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

Click a theme to open its detail page, which shows the *real card* recolored by
that theme:

- **All-states galleries** — room cards and the review / map-bounds badges in
  every colored state at once, so you can check that statuses stay readable.
- **Card tabs** — the full card across its tabs (maintenance, base station,
  metrics, and so on).

Every image is the real card rendered through the same engine the project uses
for its own testing, so what you see is what you'll get.

---

## Using a theme you found

Every gallery theme is published as an export file in the project repository
under [`gallery/themes/`](https://github.com/kingchddg901/Vacuum_Agent/tree/master/gallery/themes).
To use one:

1. Download the theme's `.json` from that folder (open the file on GitHub and use
   its download / raw button).
2. In the card's **Theme** tab, click **Upload** and pick the file — or
   **Import** to paste the JSON from your clipboard.
3. The theme is added to your library as a new theme; select it like any other.

Loading a theme only adds styling — it never touches your rooms, queue, or
settings. Full details are in
[Import and export](../advanced/05-theme-system.md#import-and-export).

---

## Sharing a theme you built

When you've made a theme you're happy with, submit it to the gallery:

1. In the **Theme** tab, click **Download** to save your theme's export file (or
   **Download Floor** to share just one floor type — for example "just my
   marble").
2. On the gallery, click **+ Submit a theme**. This opens a pre-filled submission
   form on the project's GitHub (you'll need a free GitHub account).
3. Paste your export JSON into the **Theme export JSON** box, tick the
   acknowledgement, and submit.

That's all you do. From there it's automatic:

- A bot validates your export — the same safety checks the card runs on import —
  and renders a preview of the real card recolored by your theme.
- It opens a pull request with that preview shown **inline**, and comments back
  on your submission with a link.
- A maintainer reviews the preview and merges it. Once merged, your theme is
  published to the gallery.

Nothing goes live automatically — a person always reviews it first. If your
export can't be read (say the JSON didn't paste cleanly), the bot comments
telling you what to fix; re-copy it from the **Download** button, then close and
reopen your submission to retry.

The mechanics of what happens behind the submission form — validation, preview
rendering, and publishing — are documented for maintainers in
[dev/27-render-harness](../dev/27-render-harness.md#8-theme-submission-issue--pr).
