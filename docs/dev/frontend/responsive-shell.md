# Responsive shell — viewport decision, compact chrome, landscape

How the card decides which shell to render, what that decision drives, and how
the shell chrome gets out of the way when there is no room for it.

Three files own this between them, and they must agree:

| file | owns |
|---|---|
| `src/state/viewport.js` | the mobile-vs-desktop decision |
| `src/styles/mobile.js` | ~96 rules keyed on `data-viewport="mobile"` |
| `src/main.js` | scroll handling, the chrome auto-hide, the panel offset |

---

## 1. The decision: narrow **or** short

```js
width < 600 || height < 500   →   "mobile"
```

`setViewportFromSize(widthPx, heightPx)` (`state/viewport.js`). **Width is the
card's own measured width** — a card in a narrow grid cell should render compact
even on a wide screen. **Height is the WINDOW's**, deliberately: as a dashboard
card the host's height is content-driven, so measuring it would feed the layout
its own output. In panel mode the window *is* the card.

Height is optional; a caller without a window (tests, SSR) keeps width-only
behaviour rather than being forced into a guess.

### Why the height clause exists

It was width-only, and the original comment had considered landscape and got it
backwards in writing: *"landscape proportions are desktop-like even on a
phone."* Desktop-like in **aspect**; the opposite of desktop in the dimension
the compact shell exists for.

Rotating a 390×844 phone gives ~844×390. That clears the 600px width gate, so
the card rendered the **desktop** shell in the case with the least height it
ever sees — dropping the mobile header, the 44px tap floors, the 22vh preview
cap and the bounded chip band exactly where vertical room had collapsed.

**500px of height** clears a landscape phone (~390–430) without catching a
normal desktop window. A desktop browser dragged shorter than that *does* get
the compact shell, and that is intended rather than a side effect — it has no
vertical room either.

**Reuse this threshold.** A second definition of "short" would drift from this
one, so reuse the value rather than restating it. `(max-height: 500px)` is not
confined to this file: measured 2026-08-24 it is in **seven** live `@media`
queries across four files — `src/styles/mobile.js` (2),
`src/styles/theme-preview.js` (3), `src/styles/modal-host.js` (1) and
`src/styles/theme.js` (1) — with five further mentions inside comments
(`src/renderers/theme.js` and the same style files).

⚠ Was: *"also appears in three media queries."* True when written, then wrong.
This count is the perishable part of the paragraph and it has moved more than
once: an intermediate correction naming `src/styles/index.js` among the carriers
is also dead, since that file now contains the string zero times. **Recount
before you cite the number**; the reuse rule above does not perish, the figure
does.

---

## 2. Two axes, not one boolean

The single `mobile` label conflates two independent questions, and treating them
as one produced a real defect:

| axis | follows | means |
|---|---|---|
| **chrome density** | height | compact when short |
| **layout direction** | width | side by side when there is room |

Landscape needs *both* answers, and they differ: compact chrome (it is short)
**and** side-by-side layout (it is wide).

The theme editor stacks its preview above the editor below 1100px, which buys
horizontal room by spending vertical. Right on a portrait phone where width is
scarce; exactly backwards in landscape where width is abundant and height is
gone. At 844×390 that stacking left **26px of editor**.

`styles/theme-preview.js` therefore un-stacks for short-and-wide:

```css
@media (max-height: 500px) and (min-width: 640px) { … flex-direction: row … }
```

`min-width: 640` is what side-by-side actually needs — a 320px preview column,
the 16px gap, and ~300px of editor. Below that, stacking really is the better of
two bad options and the block correctly does not apply.

Measured after: editor **26px → 124px**; portrait and desktop unchanged.

---

## 3. Chrome auto-hide (landscape)

The status pane and bottom nav are **89px of a 360px landscape viewport — 25%**,
both already in their `--compact` variants, so that is the floor without hiding
them. Hiding both takes the view stage 270px → 359px.

**Scroll down hides, a deliberate flick up reveals.** Chosen over a
taskbar-style hidden edge: reversing a scroll is reflex where finding an
invisible strip is a discovery, and a strip thin enough to be worth hiding is
thinner than the 44px tap floor (`styles/mobile.js`).

### What may drive it

`CHROME_SCROLL_SOURCES` in `main.js` is an **allowlist**:

```
.evcc-view-stage
.evcc-theme-editor-scrollbox
```

Everything else — the preview pane, the group-filter chip band, a modal body —
is a **panel**: it scrolls its own content and must not move the shell around
it. The first version listened in capture phase and reacted to *any* scroll, so
nudging a panel toggled the chrome, changed every height mid-gesture, and made
two independent scrollers read as one linked thing.

An allowlist rather than a denylist because panels get added often and content
scrollers almost never — **a new panel is inert here by default**, which is the
safe direction to be wrong in.

*Not yet allowlisted, and each is genuinely main content:*
`.evcc-room-rules-content`, `.evcc-map-config-body`, `.evcc-preset-scroll`.
*Must stay out:* `.evcc-modal-body` (chrome sliding under an open modal is worse
than chrome you can see), `.evcc-map-config-side-panel`, `.evcc-lang-menu`,
`.evcc-zone-picker-list`.

### Thresholds

| constant | value | why |
|---|---|---|
| `CHROME_TOP_ZONE` | 24px | at the top the chrome always shows — nothing above to reveal, and someone at the top is orienting rather than reading |
| `CHROME_REVEAL_TRAVEL` | 140px | accumulated upward travel needed to reveal mid-list, reset on any downward movement |

Revealing on *any* upward movement was too eager: the landscape editor is
~129px, so reaching a control means scrolling up constantly and every one of
those restored the chrome and took 89px away again, mid-edit. Position alone
("only reveal at the very top") would have stopped the flapping and replaced it
with a trap — stranded at the bottom of a 53,000px token list with no gesture
that brings the nav back.

### Hidden by default — but only when something scrolls

The chrome starts hidden in landscape, applied on *entering* short mode rather
than per render so a re-render never undoes a reveal.

**Gated on an allowlisted scroller actually overflowing.** Hiding the nav where
nothing scrolls stages the one failure this design exists to avoid: navigation
gone, and no gesture in the view that can bring it back.

Two ways that gate went wrong, both silent:

- `querySelector` returns the **first** allowlisted match — `.evcc-view-stage` —
  which is `overflow: hidden` in the theme editor, where the box nested inside
  it does the scrolling. It answered "nothing scrolls here" about the one view
  that scrolls 53,000px. Ask **every** allowlisted scroller.
- The short-mode flag latched on the **first render**, before content existed to
  overflow, so the default resolved to "stay visible" and every later render
  returned early still holding that verdict. Latch only once the question can
  be answered.

### Pinned while a job is in flight

The status pane stays when `hasActiveJob()` is true — the 33px is worth paying
exactly when the numbers behind it are moving. The nav still hides; navigation
is not live information.

The signal needed no inventing. `jobs/active_job.py` →
`core/manager.py` sets `live_queue.active` from `status in {"started",
"paused"}` → `state/learning.js:hasActiveJob()` surfaces it. **Paused counts**,
which is the right semantics: a job paused mid-room is when a user most wants
status on screen.

Implemented as `:not([data-chrome-pin-status])` on the *hide* rule rather than a
second rule restoring values. The first attempt restored `padding-block: 10px`
by hand — the base padding, not the `--compact` one — so a pinned header
rendered 41px against its natural 33. **A rule that never matches cannot restore
the wrong value.**

---

## 4. THE PREVIEW-SPECIMEN RULE

> **The theme editor previews render REAL components. Any rule aimed at a real
> component also hits the specimen. Every selector targeting shell chrome needs
> a guard.**

This bit twice in one session:

1. **z-index.** The shell preview renders the real mobile header, which is
   `position: sticky; z-index: 9` so its own dropdown clears the view-stage.
   Rendered as a specimen it brought that z-index *inside* the view-stage: two
   elements at 9, the specimen later in DOM order, so the preview card painted
   over the real language menu. Fixed with `isolation: isolate` on the preview
   frames, which spends a descendant's z-index inside its frame.

2. **The auto-hide.** There are **two** `.evcc-mobile-header` elements in the
   shell — the real one and the preview's specimen — so the descendant selector
   collapsed both. Hiding the chrome emptied the preview pane (measured: frame
   `h=1`, its header `maxH=0`). Fixed with
   `:not(.evcc-theme-preview-shell-frame *)` on all three chrome rules.

Neither was visible in a screenshot as *its own* symptom; both presented as
something else (a stacking glitch, a scrolling fault).

---

## 5. Panel mode sizing

`:host([data-evcc-panel])` sizes itself as `100dvh` minus **a measured offset**,
not a guessed toolbar:

```css
height: calc(100dvh - var(--evcc-panel-offset, var(--header-height, 56px)))
```

`main.js:_syncPanelOffset` publishes `--evcc-panel-offset` from the host's own
`getBoundingClientRect().top`. The integration registers through
`panel_custom` with `embed_iframe=False`, so HA renders it in `ha-panel-custom`
— which hands the panel the whole area and draws **no toolbar**. The old
`--header-height` subtraction removed ~56px for chrome that was never on screen.

Writes only on change, and rounds first: the property feeds a height and the
ResizeObserver that calls it watches that height, so an unconditional write
would re-arm the observer every frame.

---

## 6. Measuring this

**The harness under-reports mobile chrome.** See
`.claude/notes/reference_harness_mobile_measurement.md`: `ha-*` components
render 0×0 there (they are Home Assistant's own elements) and `.evcc-chip` is
exempt from the 44px tap floor. Its heights for chrome are a **floor**, not the
figure.

**Landscape has baseline coverage, from exactly one spec.**
`harness/tests/theme-mobile-layout.spec.mjs` runs its layout cases over
`[[390, 900], [500, 900], [720, 344]]`, so the `720x344` case is **below** the
500px threshold and the `(max-height: 500px)` rules DO fire in the visual gate —
for the theme editor's `tokens` and `palette` tabs. Every other harness spec sets
its viewport to height 780, 800 or 844, so a short-viewport rule anywhere OUTSIDE
the theme editor is still device-only and must be checked on a device or in
device emulation.

⚠ **Was, until 2026-08-24:** *"The shortest viewport any harness test uses is
**780px**, so none of the `(max-height: 500px)` rules fire in the visual gate —
landscape has no baseline coverage and must be checked on a device."* False since
2026-08-14, when `34f8bc9e` added the `720x344` case; this doc was written
2026-08-13 and went stale the next day. The test's own comment says it exists
precisely because *"LANDSCAPE is a viewport this gate could not see"*. A stale
COVERAGE claim is the worst kind to leave standing — a stale constant is merely
wrong, but a coverage claim DIRECTS BEHAVIOUR: it told readers to distrust a gate
that works and to go re-test by hand.
