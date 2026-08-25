# Deferred past v2.1.0 — decided during the release, not discovered after it

Everything here was **found while cutting 2.1.0, judged, and deliberately left**. That is the
point of the file: each item already has a ruling, so the window after the tag does not open by
re-deriving whether these are real or arguing about them again.

**Every one of these has already been re-raised at least once by an audit.** Five 5-dimensional
audits ran against this release; the "deliberate — do not report" brief grew every round. If you
run another audit, feed it this list or it will spend agents rediscovering settled questions.

---

## 1. The mobile harness renders fixture artifacts into its own shots

**Ruling (Chris): after the release. Real phone screenshots carry the README instead.**

`harness/shoot-hero-mobile.mjs` exists to produce release-note captures and its frames are not
publishable. Two artifacts, both from the same cause:

* a phantom **empty amber warning banner** — `rooms-active` never defines `startMopCarpetWarning`
  (`src/renderers/rooms.js:548`), and the stub's recording null-object is **truthy**, so the
  `${mopCarpetWarning ? ... : ""}` guard fires on nothing;
* the literal text **`nullObject`**, twice, in the Run Profiles block — the same null-object is
  also **string-coercible**, so an undefined accessor renders its own name.

Not a product bug. It is the harness's documented null-object doing exactly what it was designed
to do, in a place that screenshots it.

**The fix is NOT to fill `harness/fixtures/gallery.js`.** `rooms-active` is consumed by
`visual.spec.mjs:43`, so editing it churns four committed baselines (`gallery-rooms-active`,
`-cyrillic`, `-opendyslexic`, `tab-rooms`) that are generated in the pinned Linux image. Instead
add a per-shot override passthrough to `renderGallery` (`harness/mount-entry.js:372` — it
currently passes `overrides: entry.state` and nothing else) and null the two accessors in the
shooter only. ~10 lines, zero baseline movement.

Context: `8bb95eb6`.

---

## 2. The sequence-override row has TWO independent renderings

**Status: structural, no ruling yet. Flagged repeatedly; nothing decided.**

`_renderPanelSequenceOverride` (`src/renderers/rooms.js`) and the `.soro-*` block consumed by
`src/cards/dashboard-card.js` are separate implementations of one feature. Chris ruled the panel
and the standalone cards are **separate items** and two copies of the STYLING is correct — that
ruling stands and is not what this entry questions.

What is unresolved is **behavioural** divergence. Three audit rounds reconciled them one axis at a
time, each time finding the next one:

| axis | how it diverged | fixed in |
|---|---|---|
| colour | panel unstyled, card unstyled-but-differently | `147ec69a`, `0c80f7a7`, `e2de8159` |
| queue order | card compared against `hass.states` insertion order | `e2de8159` |
| Clear gating | panel offered Clear only in `saved` | `e2de8159` |

Three axes, three rounds, each found only because someone went looking. The open question is
whether a fourth exists. Only the panel has `[LR-6]`-style coverage; the card got its first
harness mount at all in `147ec69a`.

---

## 3. `_render()` has no try/catch on the dashboard card

**Status: reported non-blocking by two separate audits. Needs a decision, not a fix.**

This is how 21 calls to a non-existent `this.escapeHtml` took the **whole card** down for any
owner whose override switch existed (`4f29e92d`). One renderer throwing kills the entire card,
not just its row.

The decision is genuinely two-sided and that is why it is here rather than done: a `try/catch`
per renderer turns a dead card into a card with one missing section, which is better for the
user and worse for the developer, because the section silently vanishes instead of failing
loudly. Whichever way it goes, it should be a decision that gets written down.

---

## 4. `[SEQ-ORDER-0]` cannot see the sort it exists to protect

`harness/tests/sequence-override.spec.mjs` pins that a room with `order: 0` is not reshuffled to
the end. It bites if the `|| 999999` re-sort returns to `src/renderers/rooms.js` — but because it
**stubs `getRoomsForActiveMap`**, it cannot detect the sort disappearing from
`src/state/rooms.js:539-543`, which is where the ordering actually lives now.

The guard protects the place the bug WAS, not the place the behaviour IS. Noted by the audit;
left because the fix means un-stubbing an accessor the spec deliberately controls.

---

## Not on this list, and deliberately

* The **incomplete-run banner's ✕ does not persist** — it clears client-side only
  (`src/state/learning.js:497`). **Ruling (Chris): leave it.** The backend deletes the log on any
  normal completion, so a vacuum in regular rotation clears it by itself; it lingers on Ivy
  because she is third in line behind two other machines. Working as intended for the common case.
* The **four hand-mixed success surfaces** (`learning.js:300`, `rooms.js:959`, `rooms.js:1060`,
  `theme.js:624`) — zone / selection / tag-family semantics, not status. Converting them would
  couple unrelated concepts to the Surface Success control. Already ruled; do not re-sweep.
