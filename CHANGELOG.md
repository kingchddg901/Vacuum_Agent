# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow semantic-ish versioning.

Releases before 0.9.10 are recorded as
[GitHub tags/releases](https://github.com/kingchddg901/Vacuum_Agent/releases)
only.

## [Unreleased]

### Fixed
- **Rotating a phone to landscape no longer breaks the layout.** The card chose its shell on
  width alone, so a rotated 390×844 phone — about 844×390 — cleared the 600px threshold and
  rendered the desktop layout at the moment it had the least height of any case: full-size
  chrome, no touch targets, and a preview stacked above an editor that was left 26px tall. The
  decision is now **narrow *or* short**, and layout direction is separated from chrome density:
  a short-but-wide viewport keeps the compact chrome while placing the preview *beside* the
  editor rather than above it, since stacking spends the axis that has run out. The editor goes
  from 26px to 124px. Landscape is now a cramped but coherent layout rather than a broken one;
  portrait and desktop are unchanged, measured.
- **Animal colours no longer turn the animal black.** Setting any Animal Companion colour —
  fur, eyes, pupil, anything — painted that part of the animal black instead of the chosen
  colour, and had done since the tokens became editable. The animal SVGs consume their
  variables as bare HSL components (`fill="hsl(var(--animal-fur))"`, 332 of 332 uses), while
  the theme editor stores every colour as hex; the cascade therefore produced
  `hsl(#e8e800e0)`, which is invalid CSS, and an invalid `fill` falls back to SVG's initial
  value — black. Untouched animals looked correct because their built-in defaults were
  already components, so the failure read as a bad colour choice rather than a bug. The theme
  layer now converts these tokens on the way to the DOM, alpha included. **Existing themes
  need no repair** — the stored values were always right, and they start working again on
  upgrade.
- **The panel no longer leaves a strip of dead space below the bottom nav.** In panel mode the
  card sized itself as `100dvh` minus Home Assistant's dashboard toolbar, but this integration
  registers through `panel_custom`, which hands the panel the whole area and draws no toolbar
  — so roughly 56px was subtracted for chrome that was never on screen. The offset is now
  measured from where the card actually starts, so a toolbar being present, absent, themed, or
  moved by a future HA layout all resolve correctly.
- **Long translations no longer drag the theme editor sideways.** The per-row colour hint was
  set to `nowrap` and nothing clipped it, so in longer locales it pushed past the card and the
  whole editor pane could be scrolled horizontally, carrying the group header and search box
  off screen. Both the editor list and the group-chip band declared only a vertical overflow,
  which silently makes the horizontal axis scrollable; both now state it explicitly.
- **The Animal Companion preview is legible on a phone.** The parent group drew every
  registered animal side by side, with the column count derived from available width while the
  animals came from a live registry a user can extend — so at phone width the matrix spilled
  into ragged rows with labels sitting over nothing. It now previews a single representative
  animal across the five battery bands; the per-animal sub-groups are where one animal is
  inspected.
- **Selecting a token group no longer scrolls the group chips out of view.** The chip band kept
  its scroll position across ordinary re-renders but reset to the top when a chip was selected,
  so a chip you scrolled down to find left the screen at the moment you tapped it.

### Changed
- **The theme editor's search row collapses on a phone.** Search and "Modified Only", plus the
  Themes/Palette/Tokens strip, fold behind a caret that names the section you are in and shows
  which filter is running, so a collapsed control never hides why the token list is short.
  Expanded by default on desktop, where the space is free.
- **The colour hint is stated once instead of on every row.** "Drag for opacity · Double tap
  for color" rendered inside all 303 colour rows on its own line — measured at 3,636px of extra
  scrolling on a 390px screen. It is now a single sticky line at the top of the token list,
  which also lets longer translations wrap and be read in full rather than being clipped to
  fit beside an input.

## [2.0.1] - 2026-08-10

### Fixed
- **Companion entities on a second device or a renamed device now resolve.** Adapters build
  entity IDs from the vacuum's own name (`sensor.<vacuum>_battery`), which assumes one
  device per vacuum. Eufy's dock is a *separate* device, so dock-owned entities are named
  for it instead — on live hardware `sensor.<vacuum>_total_cleaning_area` was absent while
  `sensor.<area>_<vacuum>_total_cleaning_area` sat right there with a value. Lifetime
  cleaning area/time/count and dock firmware version had therefore never resolved, and
  renaming a vacuum or its device broke every derived ID at once. Vacuum Agent now searches
  the vacuum's own config entry for the real entity when a derived ID doesn't resolve.

  It only touches IDs that already fail, refuses to act when two candidates are
  indistinguishable, and logs every repair — so a working install cannot be changed by it,
  and a rescued one says so in the log rather than looking as though it was always right.

  This matters more on Home Assistant 2026.8, which removed `battery_level` from the vacuum
  entity: the fallback that used to hide a missed battery sensor is gone, leaving the
  derived ID as the only source ([#49](https://github.com/kingchddg901/Vacuum_Agent/issues/49)).

- **Diagnostics downloads now answer these questions themselves.** The dump probed only
  the roles capability-detection found, so adapter-declared ones — battery, charging, the
  dock counters — were never checked, and it reported whether an entity had a *state*
  without saying whether it was *registered*. Two support reports in a row turned on
  exactly those gaps and had to be reproduced on other hardware instead of read off the
  attachment. The dump now covers every declared role and reports `registered` beside
  `exists`, which separates "never created" from "correct ID, entity absent"
  ([#46](https://github.com/kingchddg901/Vacuum_Agent/issues/46),
  [#49](https://github.com/kingchddg901/Vacuum_Agent/issues/49)).

### Changed
- `NOTICE` now carries proper third-party attribution: eufy-clean (Copyright (c) Martijn
  Poppen, Eufy-Clean License v1.0, consumed via the jeppesens fork) and python-roborock
  (Apache-2.0), each with the notice its licence requires and a pointer to where our
  modifications are marked in the source.

## [2.0.0] - 2026-08-09

**The Phoenix Release.** A hostile audit campaign ran against the whole tree and
produced **484 verified findings** — 18 critical, 88 high, 173 medium, 205 low.
Those collapsed into 33 accepted repair families (6 candidate families rejected)
resting on eight structural invariants, executed as 60 landed packets. Almost
none of it had been reported by anyone: the dominant failure shape was a setting
that silently did nothing, which is indistinguishable from a setting that works.
New features shipped alongside the repairs.

The bound is stated rather than rounded off. 36 of the 484 findings carry
executed evidence; the rest were verified by two independent source-reading
passes. The CV segmentor is excluded by design, because its correctness is
empirical rather than textual and this method cannot falsify it. Method,
findings and the open remainder are written up in `docs/how-this-was-audited.md`
and `docs/audit-1-closeout.md`, whose §8 lists every open item
with the specific thing that would close it.

### Breaking changes

- **Per-room settings on disk are repaired, once, on update.**
  `rooms/vocabulary_migration.py` runs one-shot on the `room_vocabulary_v1` key,
  after adapter registration, and judges every stored room against what its
  brand's adapter *declares*: a field no declared profile carries is **dropped**,
  and a value absent from the brand's declared options is **reset** to that
  brand's `default_profile` value — consulting the brand's declared aliases
  first, so a retired name keeps its meaning instead of falling back. There is no
  nearest-match: declared option lists are unordered sets. The call site moved
  from `async_setup_entry` to `async_at_started`, and a vacuum whose own
  integration has not finished loading is now **deferred**, not counted as
  repaired — see *Fixed* below.
- **The paused-job timeout now defaults to 15 minutes, and a stored `0` is
  raised to 15 once, on update.** `pause_timeout_minutes_default` fell back to
  `0` — the timeout OFF — and `get_pause_timeout_settings` *persisted* its own
  fallback on read, so the first time anything asked, a hard `0` was stamped
  into the store; after that "never configured" and "deliberately disabled" were
  byte-identical, and no change of default could ever reach the install. A
  paused job is owned by the pause reaper and nothing else, so with the timeout
  off a paused run sat open indefinitely. `core/pause_timeout_migration.py` runs
  one-shot on the `pause_timeout_default_v1` key and lifts an explicit `0` to
  15; an absent value is left absent, so it inherits the default rather than
  being stamped again. This knowingly overwrites a `0` somebody may have chosen:
  after updating, **a run left paused for 15 minutes is cancelled and the robot
  is sent home.** The control moved out of the capability-gated Base Station tab
  into the rooms sidebar and gained an explicit Off chip, so `0` is now a
  visible choice — set it back there, or with `set_pause_timeout_settings`.
- **`set_area_label_anchor` is removed**, along with its schema, handler,
  registration, `services.yaml` block, card action, and the only writer of the
  `label_anchor` room field. Area-chip positions are now device-local
  (`localStorage`), matching the room-name labels beside them; positions dragged
  before this release are seeded once per device from the backend payload and
  owned locally thereafter. The seed marker is persisted, so clearing an anchor
  is not undone by the next page load. `resolve_area_label_anchors` survives on
  both read paths for that seed.
- **An adapter that declares no `room_profiles` block can no longer resolve a
  single room.** A *stored* adapter config (UI- or service-authored,
  `source: "config"`) missing the block is refused at registration outright. A
  *code* adapter — the shipped brands, and a brand port — is reported as a
  registration validation issue and then fails at first profile resolution
  rather than degrading. Core owns the key space — the four protected profile
  names and `default_profile` — and none of a brand's words. There is no
  framework catalog to inherit and no per-key merge: an undeclared key resolves
  EMPTY, and resolution raises `UndeclaredProfileCatalogError` naming the
  missing declaration rather than a bare `KeyError`. Eufy's catalog moved to
  `adapters/eufy/room_profiles.py`. Absent and declared-empty stay
  distinguishable so "this brand has none" and "the porter forgot" cannot
  collapse into one state.
- **`map_state_source.live_pose` must declare a `backend`.** Core owns the pose
  shapes — `inmem_pixel_pose` and `parsed_mapdata` — and a `live_pose` block
  without one now yields no pose rather than falling through to the Eufy fork's
  reader, which would walk an unrelated provider's internals and find nothing.
  Neither shape is a default; the absent-default is what made "declares no pose
  shape" and "has no position" the same answer, and cost Roborock its dot while
  the position sat live on the map the card was already rendering. Both shipped
  adapters declare theirs. A brand port must, and the adapter-contract suite
  fails it per brand rather than skipping a brand that declares nothing.
- **Eufy suction: `Boost` is replaced by `Turbo`.** `fan_speed` resolves by index
  into the upstream speed list, `boost` is absent from it, and selecting Boost
  therefore applied no suction at all. BoostIQ is the auto carpet-boost switch on
  DPS 118, not a fifth speed. `Turbo` is the device's real second-highest suction
  and was unreachable. No dedicated migration is needed: the one-shot repair above
  already covers rooms. `Boost` is absent from the declared options, so any room
  still carrying it is **reset** to this brand's `default_profile` suction,
  `Standard` — re-pick `Turbo` on those rooms if that is what you wanted. A `Boost`
  held in a saved room profile or a run profile is not visited by the repair and
  continues to be discarded on the wire. The author's own store carried it nowhere.
  `fan_speed_aliases` still folds `boost iq` onto `boost`; that feeds learning
  bucket labels rather than dispatch and is deliberately left for its own look.
- **Eufy `clean_intensity` reaches the wire through a declared `value_map`** —
  `{"Narrow": "normal", "Deep": "narrow"}`. Sent unmapped, Narrow and Deep
  collapsed onto the same device density and the middle one (the Eufy app's
  "Medium") was impossible to select. Stored values do not move; only the
  dispatched word changes. Hardware-verified against `clean_param_pb2`
  (`NORMAL=0`, `NARROW=1`, `QUICK=2`) — an arbitrary enum, not an ordinal, so
  nothing may interpolate on it. The map is exact-match-then-passthrough and
  therefore **case-sensitive**: the two vocabularies share the word "narrow" at
  opposite ends of the scale, and case is the only discriminator.
- **`path_type` is no longer a canonical axis, and Eufy no longer declares it.**
  Pass density was declared under two names and rode the same room object on the
  wire, with every stored room holding the literal string `"None"` — in no
  brand's vocabulary, so the device discarded it and `clean_intensity` won by
  accident. Core stops backfilling the key and stops supplying a `"wide"`
  default at all four sites; an unsupported device now has the field **omitted**
  rather than clamped, and `RoomConfig.path_type` defaults to `""` so a round
  trip cannot mint a value. Eufy drops it from all five profiles and from
  `room_fields`. Roborock keeps it, and gains `path_type_options` plus per-model
  `has_path_control` (False everywhere until verified on hardware).
- **Room rejection is per-map, and an unqualified rejection is refused.**
  Rejections were stored as one flat per-vacuum list, so rejecting a ghost id 3
  downstairs made the real id 3 upstairs permanently unconfigurable and
  invisible. New rejections land in `rejected_rooms_by_map` and apply to their
  own map only. Omitting `map_id` now means "the only map" and **refuses** on a
  multi-map vacuum rather than applying vacuum-globally. The legacy flat list is
  still read and applied to every map, and once a vacuum has a stored map,
  nothing is ever appended to it again.
- **`manifest.json` declares requirements for the first time**: `fonttools>=4.47.0`
  and `brotli>=1.1.0`, which back the drop-in typeface trust chain. The CV stack
  (numpy / Pillow / scipy) remains optional; stall capture degrades to no image
  when Pillow is absent.
- **`dev_inject_stall` is registered, and is a maintainer tool, not a feature.**
  It fires a synthetic `EVENT_STALL_DETECTED` for a vacuum that is currently
  cleaning a room, using its real map and room, so every consumer downstream runs
  for real. It is deliberately *not* hidden behind a dev-mode marker file — a
  conditionally registered service is one nobody can find when they need it and
  nobody is warned about when they don't — so the hazard is stated where a caller
  reads it, in the `services.yaml` description: the event is not private to stall
  capture, it also reaches `detect_run_anomalies` and therefore the card's
  snapshot, so an injected stall makes a clean run report as anomalous. It
  commands no hardware and refuses unless the vacuum is actually cleaning a room.

### Added
- **Stuck detection — two triggers, because a robot gets stuck two ways.** Both
  designed against hardware, by deliberately trapping a Roborock S6 twice.
  - The **error edge** fires as soon as the robot reports an un-recovered fault. Fast
    and precise, but it only fires when the robot knows it is beaten.
  - The **area gate** fires when the swept area has not moved for 15 minutes while
    the run still looks alive. It catches what the robot never reports: a vacuum
    grinding against a corner, *moving the whole time*, covering no floor. No error
    code fires in that case and the vacuum entity reads `cleaning` throughout — a
    detector built on the robot's own state, or on pose movement, calls it healthy.
  - Neither trigger commands the robot. Not `return_to_base`, not anything. A stuck
    robot cannot drive out — for `bumper_stuck` the firmware will not release until
    the bumper is physically actuated — and a run the integration did not dispatch is
    not its to redirect. Every stuck state gets the same answer: you are told, you go
    get it. (The pause-timeout path still sends a *paused* robot home; a paused robot
    can move, and that timeout is one the user can see and change — see *Breaking
    changes*, where a stored timeout of `0` is raised to 15 minutes once, on update.)
  - Both feed the existing stall-capture consumer, so an armed vacuum whose run has
    a resolved current room gets the room picture, the notification and the event.
    `eufy_vacuum_stall_detected` now carries
    `trigger` (`timing` / `error` / `area`) so an automation can tell them apart.
  - The window is 15 minutes deliberately: the trapped robot freed itself after ~3,
    and a shorter window would report a stall on a robot that was going to be fine.
    It must also stay longer than the 5-minute stranded-reap grace, or the two fight
    over the same run.

- **Roborock gets stall detection at all.** It was gated behind
  `honors_clean_order`, which asks whether the robot obeys the dispatched room
  *order* — Roborock's path optimiser does not, so the entire stall path was dead on
  that brand. The two facts are unrelated: whether a robot cleans rooms in the order
  you asked says nothing about whether it is wedged against a chair leg. There were
  **two** such gates, one of which silently zeroed the detector's input, so removing
  only the visible one would have shipped a fix that read correctly and did nothing.
  The skipped-room branch keeps its gate, correctly — that one really is queue-order
  arithmetic.

- **Accessible typefaces, including OpenDyslexic.** Pick a typeface for the whole
  card from the theme panel, with preset chips. Custom faces are drop-in:
  `config/eufy_vacuum/fonts/<id>/` holds `font.json`, the woff2 files and a
  licence, and they appear in the picker after a restart — no release required,
  and they survive HACS updates. The **backend** owns the trust chain
  (`user_fonts.py`): descriptor validation, cmap parsing via fontTools, and
  per-locale verification against the shipped locale catalogues, with GSUB
  required for shaping locales. The descriptor cannot claim locales — the font
  file is the evidence — and `catalog.json` is the canonical response the card
  consumes generically. There is no browser render-verification anywhere:
  rendered-text checks lie through per-glyph fallback.
- **A live-pose backend is declared, so any brand can have a dot.** The pose
  accessor used to BE the Eufy fork's reader wearing a generic name: it required
  a `live_pose` block whose every key described the fork's in-memory pixel
  coordinator, so a brand that could not describe itself in those terms got
  `not_configured` — an answer indistinguishable from "this brand has no
  position". Roborock hit exactly that, with its position sitting live on the
  parsed map the card rendered every refresh while the stall capture drew an
  empty room. `map_state_source.live_pose.backend` now names one of core's
  shapes — `inmem_pixel_pose` (a provider-held pixel pose normalised against a
  separately-loaded geometry) or `parsed_mapdata` (a pose already in the
  rendered frame). Neither is a default, and the absent-default was the bug.
  The trail followed for one conditional: `pose_sampler` wrote `"anchor": None`
  as a literal for the `native_current_room` source mode, on the rationale that
  it has no pixel pose — true of the NAME entity, false of the brand. WHICH room
  and WHERE are independent axes now.
- **A stall capture shows which way the robot was travelling.** The observed
  positions are connected in order with chevrons along the path, and the
  observations fade from the room fill to full strength so the newest sits
  beside the robot dot. Chevrons are spaced by arc length rather than per
  sample, which is what lets one implementation serve a 2-second pose and a
  30-second one; and both cues are wordless by necessity, because a legend
  would be the first English baked into a PNG in an 18-language product. Time
  is lightness, not hue, so the order survives colour-blindness. A coarse brand
  additionally marks each observation on the line — at thirty seconds apart the
  robot covers several metres and certainly turned, so each sample is a fact
  worth showing rather than a route worth inventing.
- **Stall capture** ([#47]). Opt-in per vacuum. On a stall, the room the robot
  stopped in is rendered — silhouette, the path it took with direction marked, a
  dot for where it came to rest, and a name pill — written to
  `config/eufy_vacuum/learning/<vacuum>/stall/<map_id>.png`, with a persistent
  notification naming the room and map and an `eufy_vacuum_stall_captured` event
  carrying the path so an automation can forward it. Armed with
  `set_stall_capture` or from the rooms toolbar; absent arming is OFF, never
  inherited by an upgrade. Deliberately **not** under `www/`, which is served at
  `/local/` without authentication and would publish a floor plan of the user's
  home at a fetchable URL on every stall. One file per (vacuum, map),
  overwritten, written tmp-then-`os.replace`. It is a *consumer* of
  `EVENT_STALL_DETECTED` rather than its owner, so turning it off cannot disable
  run-anomaly reporting.
- **Faults have names, on both brands, in all 18 languages, on history already on
  disk.** 189 Eufy fault labels and 48 Roborock ones, resolved at **read time**
  from the raw vendor code every record has always carried — so every historical
  job is named the moment this ships, with no migration. `error_label_key` and
  `error_source_for_code` read the adapter's declaration; core never learns a
  brand's codes, and `None` is a real answer that renders the raw number rather
  than an invented label. Each row carries code, label key, source (dock / robot
  / unknown), recovered, capture time and room id. A warning triangle marks a
  faulted run in the list.
- **Job Summary.** Tapping a completed run — the row body or its warning badge,
  deliberately the same modal — shows what the run was asked to do, what happened
  in each room, and any faults, named and attributed. All three sections read
  fields the backend derives on read, so older records gain them too, including a
  recharge line without which a run that drew 55% reports "11% used". Omit,
  never zero: a null battery reading is dropped rather than rendered as 0, a room
  with settings and no result reads "Not reached", and a fault that did not clear
  reads "Not recovered" — nothing establishes that a fault *ended* a run.
- **A group phase's rooms get measured timings, not an even split.** A multi-room
  `room_group` phase used to record one row per member with the group's totals
  divided by N, `allocated=true` — and `cleaning_wall_seconds`, which learning
  actually consumes, was not even the room's share but the whole phase's wall
  repeated for every member. Members are now segmented out of the counter stream
  behind three gates, each falling back to the even split: the brand must declare
  `honors_clean_order`, the segmenter must return exactly n bouts, and the
  rebased parts must reconcile to the group's measured totals within a second /
  0.05 m² per member.
- **Room access graph.** Describe which rooms a vacuum must pass through to reach
  others. `set_room_access_graph` does build, rebuild and clear in one atomic
  replace-all write — clearing is the same call with no dock room and no edges,
  so there is no separate clear service to drift against it. Edges are
  order-independent `{from, to}` pairs. It refuses structural illegality (loop,
  multiple-inbound, unknown room) and writes nothing; incompleteness is
  *reported* with the rooms named, not refused, so a graph can be built in
  stages. The response carries `block_code_before`/`after`, because clearing does
  not always unlock. A missing dock room is now refused on the per-room access
  editor: an edit that changes links while no room is marked as the dock is
  rejected with `no_dock_room` and rolled back. `multiple_dock_rooms` had always
  been in the structural set while `missing_dock_room` never was, so too many
  docks refused and zero docks was allowed. `set_room_access_graph` itself still
  reports a dockless graph through `block_code_after` rather than refusing it.
- **The estimate panel freezes the plan at dispatch.** `get_planned_job_estimate`
  computes from the payload state and job start clears the payload, so the panel
  went blank exactly when the user most wanted to see what they had asked for.
  It now serves the dispatch-time estimate already written into the live job
  snapshot — the same object the user approved, so the two cannot disagree —
  matched on `job_id`, tagged `frozen_at_dispatch` / `source: "dispatch_snapshot"`,
  falling through to the live recompute when there is no snapshot and thawing on
  any terminal status.
- **`setup_unreject_rooms`** — an un-reject path, which did not exist from
  anywhere. It refuses an unqualified call on a multi-map vacuum for the same
  reason rejection does: the entry it would clear is the vacuum-global one.
- **A `services.yaml` ↔ registration parity gate**
  (`tests/unit/test_service_declaration_parity.py`). It discovers the registered
  surface by AST-walking every `hass.services.async_register(...)` call rather
  than from a hand-maintained checklist, then asserts every registration has a
  schema, every service is documented or on a reviewed `INTERNAL_SERVICES`
  allowlist, every `services.yaml` field exists in its schema with matching
  required-ness in both directions, and no dead schema constants survive. A fifth
  test guards the expected-failure list against rot, failing if an allowlisted
  violation has quietly started passing.
- **Learning stores are repairable.** `accuracy_stats`, the incremental
  accumulators, the battery drain aggregates and `learned_zones` can all now be
  rebuilt from the completed-job archive; every durable learning store is either
  rebuildable or explicitly registered as raw evidence with no rebuilder.
- **Real-frame render harness** (`mountRealCard()`, opt-in). Every prior spec
  rendered stub state into the renderers and wrapped it in a synthetic frame, so
  nothing `main.js` owns — shell construction, viewport detection, the
  `ResizeObserver`, sticky mobile chrome, the typeface chain on the real shell —
  could be asserted. It found within minutes that `mobile_shell` had never worked
  on a normal mount.

### Fixed

#### `clean_mode` — the second question nobody owned

A direct search for anything still testing `clean_mode` outside the owner found
twelve sites. All twelve were correct, and reading them is what mattered: four were
asking a **different question**, and converting them would have been a regression
dressed as consolidation.

- `is_mop_clean_mode` — *is this canonically a mop mode.* Strict. Decides what the
  framework **does**: gate a payload, downgrade for a device without mop hardware,
  match a preset. An unrecognised mode answers False, which is right — do not send
  mop settings on a guess.
- `may_wet_floor` — *might this put water on the floor.* Tolerant, and new. Every
  water-related site was spelled `"mop" in clean_mode`, and in each one **inclusion
  is the safe direction**: counting a doubtful mode as wet over-protects, while
  narrowing it dispatches a wet mop at a vacuum room's water level.

Five sites now share the tolerant owner (safest-water choice for a mixed batch,
water accounting, the post-job water amendment, water allocation, job metadata).
They all agreed on every value that exists, which is exactly why five copies of one
question survived unnoticed.

Also fixed in the same sweep: a dead `{"mop", "vacuum_mop"}` arm that was, character
for character, the expression that lost Edge Mopping — kept alive only by the
substring test beside it, so deleting the "redundant" half would have reintroduced
the bug; a set membership that was correct only because the line above it
canonicalized first, so reordering two lines would have broken it silently; and a
card predicate where the vacuum-only test was exact while the mop test beside it
carried two substring fallbacks, leaving a differently-spelled mode neither
vacuum-only nor mop-capable.

#### `clean_mode` — one predicate, ten sites ([#48])

The card writes `clean_mode` as a **display label** (`Vacuum and mop`); the
framework's canonical token is `vacuum_mop`. Every site that asked "is this a mop
mode?" carried its own spelling of the answer, and they disagreed.
`canonical_clean_mode` and `is_mop_clean_mode` in `profiles/room_profiles.py` are
now the single backend owner, and `canonicalCleanMode` in `src/clean-mode.js` —
dependency-free, so even the import-free steps-manifest builder can reach it — is
its card-side mirror; the two are separate languages, cannot share code, and are
pinned to each other alias for alias by test. The question is normalized at each
site rather than the value, because canonicalizing the value would lowercase
brand vocabulary on its way to a case-sensitive wire map. The class survived
4,000-plus passing tests because
every existing pin fed `"vacuum_mop"`, the one spelling that never broke; the
pins now parameterise over the spellings the card can actually store, and both
wrong answers are mutation-verified.

- **The read path** — the original report. Edge mopping was zeroed on every read,
  because two predicates disagreed about what counts as a mop mode and one of
  them was case-sensitive, so the display spelling the card actually stores read
  as *not a mop mode* and wiped a correctly-saved value.
- **The capability gate** (`apply_capability_gate`) under-fired in both
  directions from one root. A device with no mop hardware, handed the label
  `Vacuum and mop` or `Mop`, was **not downgraded** and was sent a mop payload; a
  vacuum-only room stored as `Vacuum` did not have water level and edge mopping
  cleared and dispatched carrying both, where nothing downstream would refuse
  them. The live store held 31 rooms in that state.
- **The wire payload** (`build_room_clean_payload` in `queue/queue_engine.py`) —
  the worst copy. Both gates were the same exact, case-sensitive set, fed a value
  the capability gate re-emits untouched. A mop-capable vacuum cleaning a room
  stored as `Vacuum and mop` had `water_level` and `edge_mopping` **omitted from
  the dispatched payload** while `resolved_rooms` recorded them as applied, so
  the card, the history record and learning all agreed a setting had been sent
  that never went out. The comment above it claimed the gates checked "the
  canonical value" — it meant only *pre-wire-rename*, and that reading is what
  let the site survive the first sweep. Corrected in place.
- **Profile matching** (`profiles/manager.py`). `_normalize_profile_match_value`
  folds case and the off/true/false/numeric literals and nothing else, so it
  compared `vacuum and mop` against `vacuum_mop` and returned unequal: every
  card-saved **non-carpet mop room** failed to match any preset and was stamped
  `profile_name: custom`, losing its preset binding and resolving back through
  the `default_profile` fallback as a vacuum-only preset it was never set to.
  Carpet rooms escaped only because the carpet guard downgrades them first. Only
  the `clean_mode` leg is canonicalized — the other five compare a brand's
  vocabulary, which core does not own.
- **The standalone room card** (`src/cards/_shared.js`, `src/room-card.js`). The
  chip-active test lowercased both sides and compared identity, so
  `vacuum and mop` matched none of `vacuum` / `mop` / `vacuum_mop` and **all
  three mode chips rendered inactive** — a correctly configured room reading as
  "no cleaning mode selected". The card contradicted itself, because the mop test
  two lines up uses a substring fold and correctly showed the water level and
  edge mopping rows.
- **The estimator** (`learning/estimator.py`). Fed a lowercased but
  un-canonicalized mode, so a 100%-mop job accumulated no mop minutes
  and reported `overhead.mop_wash_minutes` as `0.0`, with the ETA short by the whole wash
  allowance. The file contradicted itself within six lines: the same variable
  goes into `_find_room_match`, whose predicate canonicalizes both sides, so the
  room matched its learned stats and got correct minutes while `is_mop` said it
  was not a mop room.
- **Battery metrics** (`battery/job_metrics.py`). `_bucket_key` folds case only,
  so two spellings of one mode made `len(by_clean_mode) == 2`, flipped
  `is_single_clean_mode` to False, and **dropped a genuinely single-mode run out
  of per-mode battery-drain learning entirely**. Not hypothetical: a read-only
  survey of 103 job records on a live install found keys
  `{'vacuum': 97, 'vacuum and mop': 5}`. Canonicalized at the clean-mode call
  site, not inside the helper, which also buckets `fan_speed` and `water_level`.
  Records already written keep their old keys, so the card's existing fold stays.
- **The run-steps manifest** (`src/state/steps-manifest.js`,
  `src/renderers/run-profiles.js`). Raw string identity over a `Set`, so two
  rooms genuinely in the same mode but stored with different spellings gave
  `size === 2` and the mode chip was **omitted**, making an all-same-mode group
  render identically to a genuinely mixed one. Directional and therefore never
  wrong in the other direction — it could only ever drop a chip.
- **`learning/utils.py` now genuinely delegates.** The read-path fix documented it
  as delegating to the shared owner; it did not, and the second table was still
  there. Behaviour is identical — both tables and both fallbacks matched — which
  is exactly how this class starts. The private name stays: three learning modules
  import it and a fourth defines and uses it, and its passthrough of unknown brand
  modes is load-bearing for
  bucketing, since two brand modes that both mention mopping are different runs
  with different durations.
- **`get_effective_room_details`** derived `mop_required` from its own substring
  test while `_protected_room_config`, in the same file and reading the same dict
  a few lines earlier, asked through the shared owner. Two answers to one
  question at arm's length — the same shape, not yet diverged enough to break
  anything. The live store was enumerated before changing a predicate that newly
  activates over stored data: it holds exactly `Vacuum` (31), `vacuum` (22) and
  `Vacuum and mop` (3), and old and new agree on all three.

#### Reported issues

- **Map import no longer requires a map-selector entity** ([#46]). Home Assistant
  2026.7 changed which entities the core Roborock integration creates, and on a
  single-map vacuum `select.<vac>_selected_map` is not created at all — so every
  branch of `get_active_map_id` returned `None` and setup refused, while the
  vacuum's rooms had been decoding perfectly the whole time. Two things had to
  change together: `import_active_map` now refreshes the room source **before**
  the map-id gate rather than below it (the existing single-map fallback was
  unreachable), and `get_active_map_id` gained `_single_cached_map_id`, the
  service-response sibling of the attribute-mode implicit path. The inference is
  deliberately narrow — service-response source only, exactly one cached map,
  and that map must carry at least one room-shaped row; two or more maps refuse
  rather than guess. The refusal message is now brand-aware and keyed off the
  six named exits of the room-source refresh, so a Roborock owner is no longer
  told to go and check the Eufy app.

#### Per-room settings that never reached the device

- **A one-shot store repair could mark itself finished having repaired nothing.**
  The migration judges rooms against what each brand's adapter declares, and
  adapters are registered from vacuum entities owned by *other* integrations; on
  an ordinary cold boot those may not have finished setting up, so every vacuum
  was skipped for want of a declaration and the completion flag was set anyway —
  permanently, and silently, because the skip logs at DEBUG. Absence of required
  runtime information is now DEFERRED, never SUCCESS: a migration is complete
  only when every target it is responsible for has reached a terminal
  disposition. "Latch if any adapter answered" is the tempting near-miss and is
  also wrong — with two vacuums on two providers it repairs the ready brand and
  abandons the slower one for good.
- **"Standard" intensity meant the *middle* density and was being changed to the
  fastest.** An earlier repair folded `Standard` / `Normal` onto `Quick` on the
  premise that they were never real values. The original setup document
  disproves it: `[Fast, Standard, Deep]` with `initial: Standard`, and upstream
  still maps `standard` to the middle extent. The fold therefore moved every
  affected room from the middle density to the fastest — less cleaning, chosen by
  nobody, and undetectable afterwards because the result was a legal option.
  Aliases now map what those names *meant* (`fast → quick`, `standard → narrow`,
  `normal → narrow`), and the migration's RESET consults declared aliases before
  falling back to the default.
- **A room save no longer re-adds an axis its brand does not have**, and a new
  room's settings come from its **own** brand's default profile.

#### The card on a phone

- **The card never sized itself in panel mode.** `ha-panel-custom` gives its child
  no height — a panel is expected to own its viewport — so `height: 100%` on
  `:host` resolved against an auto-height parent and the shell collapsed to
  content: 209px measured in a 780px viewport. The mobile nav then landed
  wherever content ended and the view stage never became a scroll container,
  leaving the sticky mobile header with nothing to stick against. Both reported
  symptoms, one cause. The card already knew: `set panel()` had stored the flag
  for as long as it has existed and nothing ever read it. It now stamps
  `data-evcc-panel` and the sizing hangs off that attribute, scoped so a
  dashboard card still defers to the height its host supplies.
- **The rooms toolbar stays on screen at any width.** It was a single unwrappable
  flex line — roughly 500px of content in a 390px viewport once the six icon
  buttons at the 44px thumb minimum, the Configure label and the mascot controls
  were counted — and the surplus simply left the screen. The row now wraps, on
  the **base** rule rather than behind the mobile-shell attribute, because a
  narrow Lovelace column the shell still calls desktop needs it just as much.
  `flex-shrink: 0` is gone with it; it pinned the row at max-content, which is
  what stopped it wrapping. The mascot controls ship inside one wrapper so a wrap
  boundary cannot fall between the animal select and its size slider.
- **Configure goes icon-only on mobile**, which settles the bar at two rows
  instead of three. Only the painted text is dropped — the button already carried
  `title` and `aria-label`, so its accessible name is untouched.
- **The mobile header labels the battery** and reads the same low/critical bands
  the desktop header does. An earlier fix reached one of two header renderers, so
  the mobile shell rendered a naked percent and a critical battery read exactly
  like a full one.
- **The maintenance card header stacks** instead of clipping its own status. The
  title had no `min-width` and so refused to shrink below its min-content width,
  so German cut "Warnung" to "Warn". Two side-by-side fixes were tried first:
  `min-width: 0` plus `overflow-wrap: anywhere`, which *caused* the Russian
  column — "Фильтр" squeezed under one glyph and rendered one character per
  line — and then a wrap plus a min-width floor, correct but dependent on whether
  a given translation crosses the threshold. Stacking unconditionally means
  neither failure can recur in any locale at any width. The maintenance frequency formatter, which had been dead by construction
  (`guide?.frequency || _format(guide?.frequency)` only reaches the formatter when
  its own input is falsy, and the formatter returns `""` for falsy input), now
  always runs — locale-aware, raising only the first character, and preserving
  hyphens so "every 3-6 months" survives.
- **`mobile_shell` had never worked on a normal mount.** Four call sites reach
  `setViewportFromWidth`; three guard the override and `connectedCallback`'s did
  not, and `setConfig` runs first in Lovelace, so the re-measure landed after the
  override and silently overwrote it — while the option was documented as the way
  to force the mobile layout. Viewport detection itself is correct from card
  width, in both directions.

#### Jobs, dispatch and lifecycle

- **A trapped robot is now reapable as a stranded run.** The strand predicate left
  an errored robot alone, on the reasoning that it might recover — but neither
  shipped brand resumes itself after a trap, so that traded every real trap for a
  rare case. An errored run is now finalized as *interrupted* once the existing
  five-minute grace elapses. No hardware command is sent. What changes for you:
  `eufy_vacuum_job_finished` and, where rooms were left, `eufy_vacuum_run_incomplete`
  now fire on runs whose robot was never freed and never returned to the dock — so
  a `retry_missed_rooms` automation will see them, and will run against a robot that
  still cannot move.
- **A job's paused flag now tracks the robot, not just our own service.** Nothing
  marked the job when the vacuum was paused by any other route — the HA vacuum
  card, the vendor app, the button on the robot — and the pause-timeout report
  requires `status == "paused"`, so a pause that did not come through the service
  armed nothing and the job sat paused indefinitely. The flag is reconciled
  against the robot's own state at the top of the existing one-minute reaper
  tick, with `paused_at` taken from the state's `last_changed` rather than `now()`
  so the interval costs detection latency and never accuracy. Both edges: a job
  left marked paused after an app-side resume would otherwise be cancelled
  mid-clean, and the clear path goes through the resume service so paused
  wall-clock accumulates identically.
- **Cancellation is effective at the last suspension point before the wire send.**
  It was read once and never re-checked across four awaits, so a cancelled robot
  returned to base and then drove back out.
- **A job could be finalized twice, or lose its "finished" mark entirely.**
  Success permanence is now written inside the protected window, so no observer
  can see claim-released but finalized-unset. This was the campaign's
  hardware-proven critical.
- **A dispatch guard with no `try/finally` left a job permanently un-reapable.**
  Every watchdog exit now resolves the pending flag or converts it into a
  reapable state with a timestamp.
- **"Is a job running?" was answered four different ways in four places.** Every
  asker now points at one pair of owned helpers; robot questions and queue
  questions are different questions.
- **Room attribution kept running after its job ended.** The tracker's lifecycle
  mirrors the job's, and every terminal path releases it.
- **Stale room ids could be dispatched after a re-segment.** Dispatch may send
  only ids resolved against a live source proven fresh; a total resolution miss
  refuses with a visible reason.
- **Declared per-brand caps were enforced on some code paths and not others.**
  Every declared cap is now enforced at dispatch on every branch,
  advisory-checked at author time, and reported to the card from the same
  declaration.
- **Authored run structure — groups, breaks, zones — was flattened by the
  engines.** The phase list preserves structure end to end, and an empty phase
  list is a refusal rather than a crash. A group phase marks all of its rooms
  current, not `rooms[0]`, and the progress snapshot presents the phase.

#### Stores and durable state

- **An empty discovery result could wipe your saved rooms.** A destructive
  replace of a non-empty room store now requires affirmative evidence — a
  non-empty, map-matching snapshot. No evidence, no write. Five criticals sat at
  this one seam.
- **A file that failed to read was treated as a file that was empty.** Absent,
  unreadable and failure-shaped are three distinct states; only *absent* may seed
  an empty store, and a failed read can never be cached as a permanent answer. A
  failed setup could also wipe the entire store.
- **Entities were owned by string-prefix matching**, so deleting one vacuum's map
  could delete another vacuum's entities — proven, not theorised. Ownership is
  now answered by structured identity, never by prefix over a non-injective join.
- **Settings were written to disk before the operation was authorised.** A
  refused operation now leaves the store byte-identical.
- **Renaming or deleting something left dangling references behind.** Destructive
  renames migrate or clear every durable referrer, or report the count and
  refuse. Deleting a map now takes its rejections with it.
- **Durable state was minted for vacuums and maps that do not exist.** Per-(vacuum,
  map) state is created only for managed vacuums and imported maps; read paths
  never create. A stored map bucket is not a map, and that predicate is now
  centralized.
- **Room identity did not survive a re-segment**, and two rooms could derive the
  same slug. Slug derivation happens once, at one admission boundary, with
  deterministic disambiguation and an empty slug refused there; carry-over is
  slug-led with id fallback, every id-keyed store is covered by the remap walker,
  and new rooms enter disabled and unconfirmed.
- **Map and pose data weren't bound to the device they came from.** Every payload
  is bound to (device, map, content) at production, and every reader checks the
  binding. Held stale data is either withheld from anything that acts on it or
  delivered with a staleness contract the consumer must consume.
- **A rejection must never delete a room** — a regression from wiring the
  rejection exclusion, caught before it reached a real install.

#### Learning, estimates and history

- **A multi-room phase credited all of its time, area and battery to the first
  room.** A phased job's record is assembled from phase-scoped evidence, with a
  job-cumulative completed set and the job's own frozen queue. A phase's counters
  are progress since *that* phase, and rounding jitter is no longer read as a
  counter reset.
- **`transit_seconds` counted cleaning as travel — 83% over.**
- **A mid-job recharge no longer corrupts room attribution.**
- **A stalled or frozen run skewed estimates.** Corrections across the ETA
  cluster, with dead time carved out of segment timing.
- **The segmenter now persists the boundaries it selected**, not just the
  survivors.
- **Impossible battery values are rejected by value, not by interval** — the
  charge-rate and regime-speed guards.
- **The review Profile filter is keyed on the saved profile**, not on a room
  signature, and no longer eats its own options.

#### Failures you could not see

- **Refusals were computed and then dropped at the service and card boundaries —
  the caller saw success.** A mutation service now either raises or returns a
  response whose failure flag is exposed, and handlers gate on flags rather than
  on prose.
- **`unavailable` was compared as if it were a value**, fabricating numeric
  defaults that then fed statistics. An unreadable entity yields *indeterminate*,
  which never satisfies a negating operator and never invents a number. An absent
  battery reading stops rendering as "Battery 0".
- **The diagnostic instruments lied about their own state.** Every sink applies
  the same redaction, reports its own state truthfully, and classifies permanent
  misconfiguration as permanent. A failed capability resolution is now
  distinguishable from an absent capability, and the decision log is selectable
  in the flight recorder.
- **Companion entities resolve by device as well as by derived name.** Resolution
  derived companion names by string surgery and gave up when they did not match —
  a scheme the author's own install produces, where companions carry an area
  prefix, and which had gone unnoticed rather than unbroken.
- **The accessibility typeface never applied**, through three stacked causes:
  `@font-face` was never registered on the *document*, the typeface read was on a
  phantom selector and then lost to the theme, and a fallback-less paper variable
  poisoned the token to a guaranteed-invalid value. The harness gate that should
  have caught it never rendered the typeface at all.
- **Stray timers survived teardown**, and the guard that "covered" them was
  vacuous. Every loop-lifetime task, timer, listener and service is now attached
  to a teardown ledger that unload fully drains.
- **Blocking file I/O at startup and on hot read paths** is gone; snapshot
  composition is pure and single, and high-frequency writes are debounced.
- **Deleted files were still running on the live box** — the deploy path now
  purges.

### Changed
- **`awaiting_bounds_exit` is now `current_room_overdue`** (dashboard snapshot key
  included). The old name was a fossil of the retired bounds system, from when it
  meant "the robot has not yet left this room's bounding box". That subsystem is
  gone and no geometry is read anywhere in the derivation — what survived is a pure
  timing signal. Renamed before the stuck-detection work built on it, so new code
  did not inherit a name describing a subsystem that no longer exists.

- **A new brand mark, and a wordmark that reads the right way round.** The logo
  had said AGENT VACUUM — the words reversed — in every release to date. The
  product is Vacuum Agent. The mark gains phoenix wings. Assets are served by
  Home Assistant's own brands endpoint straight off disk; the public CDN does not
  accept custom integrations, so surfaces that resolve against it (HACS's
  repository list) still show a placeholder.
- **Brand selection is a declared registrar table, not an `if/else` in core.**
  `adapters/brands.py` holds an ordered `BRAND_REGISTRARS` of
  `(brand_id, detect, register, is_default)`; `resolve_brand` reports which of
  the three routes was taken — explicit per-vacuum override, first positive
  detect, or the declared default arm — and core logs it. Adding a brand is a row
  plus a package. The default arm stays Eufy deliberately, preserved
  byte-for-byte because the device registry is sparse on real installs, but it is
  now declared, greppable, testable, and logged at INFO when reached; previously
  "this is a Eufy" and "we could not tell, so we assumed Eufy" were
  indistinguishable and silent.
- **The backend returns codes and parameters; the card translates.** Backend
  English was leaking into an 18-language product. Home Assistant's own surfaces
  gained 17 locale files, and `strings.json` gained an `exceptions` block,
  covering the config flow, entities and exceptions.
- **Registered services are documented or explicitly internal.** The parity gate's
  first run found 75 violations, including 27 registered services with no
  `services.yaml` entry; each was either documented or adjudicated onto the
  reviewed `INTERNAL_SERVICES` allowlist. 19 dead schema constants and 4 dead
  `const.py` entries went with them — three of those were service names for
  services that were never registered, sitting in the file a brand port is told
  to consult and reading as capability that does not exist.
- **Themes** — provenance, draft lifecycle, notification parity and import
  validation; core entries are immutable in place.
- **Profile resolution precedence** is uniform, with the floor-safety clamp only
  ever *reducing* risk and never rewriting the selected profile's identity.
- **Dock events** — a dock event is a transition *from* a known non-trigger state;
  debounce, timestamp and counter commit atomically.
- **Adapter config** — a stored config is validated against the full contract
  before it may shadow the code adapter.
- **One label-anchor implementation instead of two.** The room-name label wrote
  `localStorage` while the m² area chip round-tripped through a backend service
  and a room field no writer carried through `RoomConfig`, so a dragged position
  was silently dropped on any room re-save or map rebuild. The fragile one was
  the one that looked robust.

[#46]: https://github.com/kingchddg901/Vacuum_Agent/issues/46
[#47]: https://github.com/kingchddg901/Vacuum_Agent/issues/47
[#48]: https://github.com/kingchddg901/Vacuum_Agent/issues/48

## [1.11.0] - 2026-07-29

### Added
- **Ten more languages — 18 in total.** Arabic & Hebrew (with full right-to-left
  layout), Japanese, Korean, Chinese (Simplified & Traditional), Polish, Czech,
  Turkish, Indonesian — on top of the eight already shipped (English, Russian,
  German, French, Spanish, Dutch, Italian, Portuguese). Pick any from the
  per-user language globe; drop-in custom locales are still supported. New packs
  are AI-drafted and ship as `draft` (chosen from the globe, never auto-activated
  from your Home Assistant language) until a native speaker reviews them.
- **Localized maintenance guides.** Upkeep steps, notes, and service intervals now
  render in your language for both Eufy and Roborock — verbatim from the official
  manuals where they exist, AI-drafted otherwise.
- **Right-to-left support.** The whole card mirrors correctly for Arabic & Hebrew.

### Fixed
- Maintenance interval override is no longer lost after a reset.
- Setup honors a low discovery confirmation-pass count, and re-opens Configure
  Rooms when the active map has no configured rooms yet.
- Run profiles: a vacuum's rooms match their saved preset instead of always
  showing "custom"; several profile edge cases resolved.
- Room configuration state is preserved across a map rebuild.
- Eufy clean-pass counts are clamped to a valid range on the wire.
- A "run incomplete" event now fires from involuntary reapers and cancels.
- Learning accuracy: a stalled-pose tail is coalesced and interior freeze
  dead-time is carved out of segment timing, so a frozen run can't skew estimates.

### Changed
- Developer documentation hardened to a disaster-recovery-grade standard
  (internal; no runtime impact).

## [1.10.0] - 2026-07-20

### Added
- **Switch maps from Vacuum Agent.** If your vacuum stores more than one map (upstairs /
  downstairs), the map picker now lives in the panel header — and in the eufy-clean card —
  so you can change the loaded map without leaving for the Eufy app.
- **Post-switch safety gate on the map.** After you switch maps the robot keeps reporting
  its position in the *old* map's coordinates until it moves and re-localizes, so a zone
  drawn in that window would have been cleaned in the wrong place. Drawing and map taps are
  now blocked, with an explanation, until the robot re-localizes — it clears itself as soon
  as the vacuum moves. If you know better, `acknowledge_map_frame` overrides it.
- **Debug flight recorder.** A switch and a target select that silently capture DEBUG-level
  detail for a chosen integration into a ring buffer, then dump it on demand — so a bug that
  only shows up once can be captured without leaving debug logging on permanently.
- **Better room guesses on a brand-new map.** When a run is picked up that Vacuum Agent
  didn't start, it has to work out which room was cleaned. On a fresh or re-mapped map
  nothing has been learned yet, so it now falls back to each room's size as drawn on the map
  — a 4 m² run matches the 3.9 m² kitchen, not the 9.7 m² bedroom. Learned times still win
  once they exist.

### Fixed
- **"Configure Rooms" re-opens when the active map has no rooms set up.** Switching to (or
  creating) a map with no configured rooms left setup showing complete while the map was
  unusable.
- **Diagnostics no longer claim a device works when it can't import rooms** ([#44]). The
  self-check reported *"maps, rooms and the live map all work"* whenever the `active_map`
  entity merely existed — even when it reported `unavailable` and no rooms were visible, so
  models whose vacuum integration doesn't deliver map data yet (Eufy C20 / C10 / E20) were
  told everything was fine and then hit a hard failure. It now reads the entity's actual
  state, says plainly that there's no map to import, and warns with the entity and value.

[#44]: https://github.com/kingchddg901/Vacuum_Agent/issues/44

## [1.9.0] - 2026-07-13

### Added
- **Zone steps — clean a saved zone as part of a room run.** A saved zone can now be
  dropped into a cleaning run as a sequenced **step** (the **+ Zone** chip), alongside
  charge and wait stops: *vacuum the kitchen, then clean the stove zone, then mop* runs as
  one job. Works in an ad-hoc queue or saved into a run profile, on Eufy and Roborock.
- **Zone learning.** The integration learns how long each saved zone takes — as a
  wall-clock total, so a small mop zone's dock-prep and pad-wash count toward its estimate.
  The zone's ETA gets more accurate every run (and starts from the zone's size before the
  first run).
- **The live queue.** While a job runs, the whole sequence shows as one collapsible chip
  row — every room plus each charge, wait, and zone stop, marked done / current / upcoming
  as the vacuum works through it.
- **Zone automation recipes** (docs) — fire a saved zone from an automation
  (`clean_saved_zone` / `clean_saved_zones`), and express "charge first / off-peak /
  delayed" as start conditions rather than internal steps.

### Fixed
- **Re-queuing rooms mid-run no longer corrupts the finished run's record.** A completed
  job records exactly what it cleaned, even if you start building the next queue while it's
  still running.
- **A rooms-then-zone run no longer loses room learning.** The finished record
  reconstructs its rooms from every phase, so a run that ends on a zone still learns its
  rooms.
- **A saved rooms-plus-zone profile started from an automation no longer drops the zone.**
- **The "Cleaning zone" banner clears when the zone finishes** instead of lingering through
  mop drying.
- The queue is locked while a job runs, so an accidental toggle can't disturb the run in
  progress.

### Changed
- Documentation reconciled end-to-end for the zone feature — a new **Zones** user-guide
  page, plus updated queue / live-monitoring / learning / automation references and the
  developer docs.

## [1.8.0] - 2026-07-11

### Added
- **Room attribution for app-started AND dispatched runs, on both Eufy and Roborock.** The
  integration now recovers *which* rooms a run actually cleaned from the live room signal
  (Roborock's native current-room, Eufy's decoded-map pose) plus the swept-area counter. An
  external (app-started) clean opens the review wizard pre-answered instead of blank; a dispatched
  clean whose vacuum deviated from the planned order gets its per-room identity corrected.
  Validated live across simultaneous multi-room runs on both robots.
- **Review card — Origin filter.** Filter the run history by **External** (app-started) vs
  **Dispatched** (started by this integration).
- **Review card — "Room Mismatch" badge.** On a dispatched run where the live room signal
  disagreed with the assigned room for part of the run, the run is flagged for review — the
  assignment is kept, never silently overridden.
- **Review card — custom exclude reason.** A "Custom…" chip reveals a free-text field so you can
  exclude a run with your own reason, alongside the presets.
- **Review card — Area Cleaned + External badge.** External runs now show the floor area cleaned
  (single and multi-room) and read as "External" rather than borrowing a sanity/learning verdict.
- **Learning-processing toggle.** Collect run data always, process on demand — run collect-only on
  a low-power box and catch up when convenient, with a "Process pending runs" action and a
  pending-count display.
- **Diagnostics — cleaning_area unit report.** Each vacuum's diagnostics show the currently
  detected `cleaning_area` unit and its normalized m² value, so a mismatched/toggled unit is
  visible at a glance.

### Fixed
- **`cleaning_area` is now normalized to square meters by the sensor's own unit.** On an imperial
  Home Assistant, Eufy's area sensor reports square *feet* while Roborock's reports square meters;
  the value was read as m² regardless, inflating Eufy areas ~10.76×. Areas are now converted to a
  canonical m² by each sensor's `unit_of_measurement`, read live so a unit toggle is handled.
- **Roborock `cleaning_time`** (a bare number of minutes) was stored as seconds — 60× too low; now
  converted by the declared unit.
- **Stranded dispatched runs now recover.** A run interrupted by power loss / a mid-run restart /
  a firmware hang no longer vanishes (or corrupts a later run's record) — it's finalized as
  `interrupted` into the same review flow, brand-aware.
- **Extreme unexplained-idle runs are held from learning** (restorable) so they can't skew baselines.
- **Swept-area attribution handles a non-monotonic `cleaning_area`** — some sensors reset/drop
  mid-run; per-room area now sums positive increments so a reset is re-baselined, not double-counted.
- External runs are no longer mislabeled "Sanity Failed" in the review list.

### Changed
- **Removed the learned room-boundary (vacuum-coordinate) subsystem.** Room tracking now runs
  entirely off the device's native current-room signal and the live map — the drift-prone
  coordinate-based boundary machinery is gone.

## [1.7.3] - 2026-07-11

### Fixed
- Scalar/Tuya-transport Eufy (e.g. X10 Pro) room clean no longer crashes on the implicit "main"
  map id — the dispatch omits a non-numeric map id so robovac_mqtt falls back to map 1.

## [1.7.2] - 2026-07-10

### Added
- Theme-completeness guard (`check-styles` theme-lint) + a full `styles/` token sweep (98.9% CSS
  coverage), so an un-tokenized color fails the build.

## [1.7.1] - 2026-07-10

### Added
- **Profile Run Card** (`vacuum-agent-profile-card`) — inspect and run a single saved profile,
  with a shared step-manifest seam and per-user globe localization.

## [1.7.0] - 2026-07-10

### Added
- **Native charge-to-X% and wait steps in a run profile** — vacuum → charge → mop captured as one
  learned job with charge/wait break-phases (Roborock + settable-mop models included).

## [1.6.7] - 2026-07-07

### Fixed
- **The cleaning tray now appears only under Maintenance, not Replacements.** The
  1.6.6 reclassification didn't take effect because the Eufy adapter rebuilds each
  maintenance component from a fixed set of keys and silently dropped the new
  `maintenance_only` flag before the card saw it. The flag now survives the adapter
  config build, with a regression test that exercises the real path. (The 1.6.6 fix
  for the phantom "Warning" was unaffected.)

## [1.6.6] - 2026-07-07

### Fixed
- **A freshly-reset "Cleaning Tray" no longer shows a permanent "Warning"** (#38).
  Replacement-item status was bucketed from absolute remaining hours, so any part
  whose entire service life sat under the warning threshold — like the 30-hour
  cleaning tray — could never read "good," even at 100%. Status is now judged on
  percentage of total service life, so a full part reads good regardless of how
  long its life is. Thanks **@fhteagle** for the report and diagnostics.

### Changed
- **The cleaning tray is now a Maintenance item, not a Replacement item** — it's a
  cleanable, not a service-life wear part, so it no longer appears in the
  Replacement group.

### Added
- **Eufy Omni E28 (T2352)** is now recognized by name in the UI instead of showing
  its raw model code.
- **Diagnostics now report dock-control entities** (mop wash / dry / dust empty),
  resolved independently of capability detection, making it clear which dock
  actions a device physically exposes.

## [1.6.5] - 2026-07-06

### Fixed
- **Theme editor's per-group token search no longer loses focus or gets stuck.**
  Typing in a group's search box and narrowing it to zero matches used to drop
  focus (letting stray keys trigger Home Assistant's global shortcuts, e.g. opening
  Assist) and left the group empty with no way to clear the search short of a reload.
  The search box now stays put while you type, so you can always backspace to bring
  the tokens back — and a "no match" hint now shows too.

## [1.6.4] - 2026-07-06

### Fixed
- **Editing a saved run profile's name no longer loses focus after each keystroke**
  (#37). The panel's focus-restore only recognized a fixed set of fields, so text
  inputs it didn't know about — like the run-profile **Name** field — dropped focus
  and cursor on every re-render, which also let stray keys reach Home Assistant's
  global shortcuts (opening Assist, etc.). Thanks **@fhteagle** for the clear report
  and diagnostics.

## [1.6.3] - 2026-07-05

Bug fixes for **Roborock** — a few spots where brand-agnostic code still assumed
Eufy's limits and quietly mis-handled Roborock. All are no-ops on Eufy.

### Fixed
- **Roborock multi-pass learning is no longer mis-bucketed.** The learning system
  clamped cleaning passes to Eufy's 1–2, collapsing a Roborock 3-pass run into the
  1-pass bucket (and never matching its learned stats back). It now keeps the real
  pass count. Run **Rebuild learning stats** once to re-file existing history.
- **Roborock room profiles keep their own defaults.** Applying a room profile filled
  any omitted suction / water / intensity from Eufy's defaults (Max / Off / Standard);
  it now uses your vacuum's actual defaults.
- **Zone-clean repeats and limits are per-brand.** The zone repeat count is read from
  your vacuum's adapter instead of a hardcoded Eufy cap, and the pass-count input no
  longer imposes a made-up ceiling.

## [1.6.2] - 2026-07-05

A localization patch — three spots that were still showing English inside otherwise-translated screens.

### Fixed
- **Filter maintenance notes now translate** (German). The two notes in the Filter
  maintenance guide ("don't use a brush / hot water / detergent" and the replacement
  interval) were showing in English inside an otherwise-German modal.
- **Room-profile preset chips translate in every language.** The Deep / Quick / Vacuum
  Only Deep / Vacuum Only Quick chips in the room settings modal rendered in English
  instead of your card's language (the translations already existed — the chips just
  weren't using them).
- **Cleaning-history profile labels translate.** The profile shown on each job card in
  the Cleanings / history view now follows your card language, matching the filter chips,
  instead of showing the English snapshot.

## [1.6.1] - 2026-07-05

A handful of small fixes and tweaks on top of 1.6.0 — no new headline features.

### Added
- **Card suggestions.** Adding one of your vacuums to a dashboard now surfaces the
  Vacuum Agent **Dashboard** and **Room** cards in Home Assistant's card picker, so you
  don't have to hunt for them (requires HA 2026.6+). The full command center stays in the
  sidebar where it belongs.

### Fixed
- **Mascots face the way they're travelling** instead of always sliding backward — plus a
  **Moonwalk** toggle if you preferred the moonwalk. The live cleaning trail now follows the
  robot reliably and stays on screen between cleans, so you can see what was just cleaned.
- **Granite and concrete floors stay put.** Applying a room profile no longer quietly
  reverts those floor types back to hardwood.

## [1.6.0] - 2026-07-05

**Floor textures, saved zones, and Roborock room rendering.** The biggest visual and
control update yet: your map floors look like your real floors, you can save and reuse
zones, and Roborock gets the full per-room map treatment.

### Added
- **Floor textures on the map.** Each room paints with its floor type's material — wood
  planks, tile + grout, marble veining, concrete, granite, and low-/high-pile carpet —
  reading as one continuous floor across rooms of the same type. Toggle with the **▨**
  button once the rendered map is on; floor types come from what you set in the Eufy app.
  Works on both Eufy and Roborock.
- **Tune every material to your real floors.** In **Theme editor → Floor Textures**, each
  material has base + detail colours (wood grain/seams, carpet weave, granite aggregate)
  and per-layer opacities, plus a new **Map Texture Rotation** control that turns the whole
  grid so planks and grout run the way they do in your home.
- **Saved zones — named areas you keep and reuse.** Beyond one-off draw-a-box cleaning,
  draw a zone, name it, and file it under a room, then clean it again any time. A
  collapsible **Saved Zones** panel lets you multi-select several, apply shared suction/mop
  settings, and clean the whole selection at once (Eufy: up to 10 zones, each 0.5–10 m per
  side). Six new services back it — `create_saved_zone`, `rename_saved_zone`,
  `delete_saved_zone`, `set_saved_zone_room`, `clean_saved_zone`, and `clean_saved_zones`.
- **Roborock room rendering — parity with Eufy.** A new v1 raw-map decoder gives Roborock
  (the S6, and likely other v1 models) the same per-room map: per-room colours, floor
  textures, pixel-exact tap targets, draggable room-name labels, and zone cleaning drawn
  over the rendered map. Suction for a zone/clean run is now adjustable from the card even
  on brands that don't expose a dedicated fan-speed select entity.
- **Custom room colours.** Give any room its own fill colour on the live map, or recolour
  the whole 12-colour room palette from the theme editor.
- New floor-texture, saved-zone, and room-colour strings — and every new material control
  label — are translated across all 7 languages (de / es / fr / it / nl / pt / ru).

### Fixed
- **Dashboard card on multi-map vacuums** — the room list and Start now target the **active
  map only**, so a vacuum with several maps no longer lists every map's rooms (and a Start
  can't hit an off-map room).
- **The map no longer blanks on a brief signal drop** — it holds the last good map through a
  transient source dropout instead of going empty.

## [1.5.1] - 2026-07-02

A couple of fixes for the new dashboard card, both reported after 1.5.0.

### Fixed
- **The card's map no longer flips back to rendered on reload.** The dashboard card's
  map is now **VA-render only** — the "toggle rendered map" button has been removed,
  because the raw camera map is too busy at the small card size. The card always shows
  the clean VA-rendered map; the render ↔ raw toggle stays on the sidebar panel, which
  has room for it. (Thanks @Pistakkio — [#35](https://github.com/kingchddg901/Vacuum_Agent/issues/35).)
- **Per-vacuum map preferences no longer bleed between vacuums.** On a multi-vacuum
  setup, per-vacuum settings saved in the browser — pinned map pan/zoom, the map
  companion (species/scale/follow), floor textures, the panel's VA-render toggle, the
  last-open tab, moved room-name labels, and label visibility — were being shared across
  all your vacuums (e.g. re-centering one vacuum's map moved another's). They're now
  correctly per-vacuum. A one-time migration carries your current values over, so nothing
  resets.

## [1.5.0] - 2026-06-28

**Drive your vacuum from your own dashboard.** Beyond the sidebar panel, the
integration now ships **two drop-in Lovelace cards** you add to your normal
dashboards straight from the card picker — no resources to register. The **Vacuum
Agent — Dashboard Mode** card is a compact multi-room control surface (pick rooms +
their settings, run a saved profile or an Eufy app scene, see the map, Start / Dock);
the **Eufy Room Card** is one card per room. Both carry the per-user language globe,
and the embedded map is the full map from the panel. Thanks to
[@Pistakkio](https://github.com/Pistakkio) for the request
([#34](https://github.com/kingchddg901/Vacuum_Agent/issues/34)).

### Added
- **Dashboard Mode card** (`vacuum-agent-dashboard`) — a compact, embeddable
  multi-room control card: a status header, a collapsible map, a collapsing per-room
  accordion (toggle a room, expand it to set that room's own mode / suction / water /
  path / passes), a run-launcher for your saved profiles and (Eufy) app scenes, and
  Start / Dock. **Arm-then-Start:** choosing rooms, a profile, or a scene is inert —
  nothing runs until you press Start. Hide any section from the visual editor.
- **Embedded map in the cards.** The full map — the VA-rendered room-blob backdrop,
  rotate, pan/zoom, overlay layers, the map companion, and "draw a box" zone clean —
  now runs inside the dashboard card too, not just the panel (lazily loaded so the
  card stays light until the map is shown).
- **Pin your map view.** The map remembers your pan and zoom between reloads (per
  device); the fit button resets it.
- **Move room names.** Drag a room's name label anywhere on the map (handy when a name
  sits over a doorway); drag it back to the room's centre to restore automatic
  placement.
- **Language globe in both cards.** The same per-user language picker the panel has —
  your choice follows you across devices.
- **Strict cleaning order (Roborock).** When a vacuum cleans rooms in a fixed order
  rather than path-optimising, the card offers a "use strict order" toggle.

### Fixed
- **Translations render correctly.** Fixed a double-escaping bug where a translated
  string containing an apostrophe (e.g. French *"Niveau d'aspiration"*) showed the raw
  `&#39;` entity, and a stale-cache bug where a freshly translated locale could load an
  old copy (newly added keys falling back to English). Translated the new card strings
  into all seven shipped languages.
- **Map view stays put.** The pinned pan/zoom is no longer wiped on first load, and a
  window/container resize can no longer scroll the map off-screen.
- **Eufy scene picker.** The Eufy app-scene dropdown no longer lists the placeholder
  "None" option, and hides entirely when there's nothing to pick.
- **Room card vacuum swap.** Changing the vacuum in a Room card's editor now correctly
  refreshes its room list.

### Changed
- The map and the Rooms list in the dashboard card are **collapsible**, to keep the
  card compact.

### Documentation
- New **[Dashboard & Room cards](docs/user-guide/20-dashboard-and-room-cards.md)** user
  guide; the developer **card-architecture** reference gained a section on the
  standalone cards, the three-bundle build, and the `<eufy-vacuum-map>` host.

## [1.4.1] - 2026-06-28

### Fixed
- **Removing the original (config-flow) vacuum no longer brings it back.**
  Deleting the vacuum the integration was first set up with now also clears it
  from the config entry, so it doesn't reappear on the next reload/restart.
  (1.4.0 dropped the vacuum's data but left it in `CONF_VACUUM_ENTITY_ID`, which
  setup re-created on load — thanks to Pistakkio for catching it.)

## [1.4.0] - 2026-06-28

**Remove one vacuum, not the whole integration.** You can now delete a single
managed vacuum from its device page — its panel, entities, and data are removed
while your other vacuums keep running. Plus documentation refreshes.

### Added
- **Remove a single vacuum.** Deleting a managed vacuum's device in
  **Settings → Devices & Services → Vacuum Agent** now removes just that vacuum
  (its sidebar panel, entities, trackers, and stored data) instead of only
  offering "Disable." The other managed vacuums are left untouched, and its
  learning history and saved map images are retained on disk so re-adding the
  same vacuum restores them. (Implements Home Assistant's
  `async_remove_config_entry_device` hook.)

### Documentation
- README refreshed: a **Contributors** section (thanks @Nebr88 for the Roborock
  duration / live-room fixes), the language packs surfaced, the live-map
  prerequisite corrected to **eufy-clean v1.11.1+** (now in jeppesens mainline —
  no fork), and the battery / map-tools wording tightened.
- Developer docs: corrected the Eufy live-map sourcing throughout (jeppesens
  mainline, not a community fork).

## [1.3.0] - 2026-06-27

**The card speaks your language.** The whole card UI is now localizable — every
tab, the adapter vocabulary, relative timestamps, toasts, and the maintenance
guides all read from a translation catalog instead of hardcoded English. This
release ships **seven languages** (German, French, Spanish, Dutch, Italian,
Portuguese, Russian), a per-user language picker in the card header, a per-user
localized upkeep guide, and a security gate that lets you safely drop in your own
translations. Plus: Eufy scalar/Tuya device support, and Roborock duration /
live-room fixes from an external contributor.

### Added
- **Pick your card language.** A language globe in the card header lets each user
  switch the card's display language on the fly. The choice is saved per-user on
  the server (Home Assistant frontend user-data), so it follows you across every
  device and browser; **Auto** defers to your Home Assistant language. A
  per-dashboard **Display language** override is also available in YAML
  (`config.i18n.locale`) and as a dropdown in the visual config editor, so one
  dashboard can force a specific language (or English) regardless of the system
  language.
- **Seven languages, full parity.** German (de), French (fr), Spanish (es), Dutch
  (nl), Italian (it), Portuguese (pt), and Russian (ru) — each a complete
  translation with **English filling in automatically** for anything a locale
  leaves untranslated. Essentially the entire card is covered: Setup and Rooms
  onboarding, the shell/header, the live Map and mapping-review, Upkeep/Maintenance
  and Base Station, the Room rule editor, Metrics, Learning Review/History,
  External Jobs, the Theme editor and preview, and the standalone room card.
- **Localized adapter vocabulary.** Clean mode, fan speed, water level, clean
  intensity, run status, sort/filter chips, confidence/trust tiers, maintenance
  labels, and theme-editor token/group/facet/tag names now render in the card
  language rather than the backend's English (any unkeyed value safely falls back
  to its English label). Relative timestamps ("just now", "yesterday", "5m ago")
  and the fresh-install "setup needed" placeholder are localized too, and
  event-driven toasts, confirmations, and inline errors now appear in your
  language.
- **Localized maintenance guides, following the card language.** The cleaning
  steps, notes, and recommended frequencies for the filter, rolling brush, side
  brush, sensors, and dust collector now appear in your language — sourced verbatim
  from Eufy's official X10 Pro Omni (T2351) manuals for de/es/fr/nl/it/pt, with
  Russian translated and cross-checked against those official versions (Eufy
  publishes no Russian manual). The guide now follows the **per-user** language
  globe, fixing a reported split where ~95% of the card followed the user's
  language but the guide stayed on the Home Assistant instance language; 286
  missing frequency phrases were back-filled across all model families.
- **Per-language plurals.** Count-driven strings now use each language's own
  grammar via `Intl.PluralRules`, so a translation supplies as many plural forms
  as its language needs (Russian's one/few/many/other, Arabic's six) and the right
  form is chosen by count automatically.
- **Bring your own language.** Drop a JSON locale into
  `config/eufy_vacuum/locales/` and the integration auto-discovers and serves it;
  the card lists it in the language globe under its native name. A locale can also
  be pointed at by URL from the dashboard config (single `url` or a per-language
  `url_map`), fetched and validated at runtime (same-origin only). A generated
  translator reference (`en.reference.jsonc`) ships alongside the locales with the
  full key structure, the English value, and an inline context note per string
  (1,373 keys, 533 with notes) as a copy-from template that is never itself loaded.
  Translators author in a readable nested structure with shared `commons`; the card
  flattens it at load time, so the organization costs nothing at render.
- **Documentation.** A user guide for choosing a language, and a contributor
  translating guide covering the authoring format, plural rules, dropping in your
  own locale, the draft-to-stable review path, and exactly what the intake gate
  allows, scrubs, and quarantines.
- **The learning data reads your language too.** The Learning Review job cards —
  the auto-exclude suggestion badges and the per-run "this run …" explanation — the
  composed room-profile labels in the Metrics and Learning Review filters, chips,
  and cards, and the fallback label for an unnamed map all localize now. Each is
  keyed on a stable backend code with the English text as a per-value fallback, so
  a code we haven't translated still reads in English rather than a raw key.

### Changed
- **Drafts don't activate automatically.** The seven new languages ship as
  AI-assisted drafts pending native-speaker review, and are draft-gated: a draft
  language reached via your Home Assistant system language quietly falls back to
  English until it is native-reviewed. You can still explicitly opt into any
  language (or force English) from the globe or the dashboard config, which
  bypasses the gate. Russian is the live pilot under native review.
- **Pickers always read in their own script.** The language menu and draft tags
  render in each language's own name and script (for example "Deutsch (Entwurf)",
  "Русский (черновик)"), so the menu stays readable even from inside an unfamiliar
  translation.
- **Untrusted translations are hardened on two independent layers.** Every catalog
  string is HTML-escaped by default at the rendering sink, so a translation value
  can never inject markup; custom drop-in locales additionally pass through a
  sanitize-or-quarantine intake gate (below) before being registered. The first-
  party locales shipped with the card are vetted at build time and are unaffected.
- **Drop-in locales get three clear outcomes.** A dropped-in locale loads as-is if
  clean, loads with disallowed formatting scrubbed (a friendly allowlist keeps
  `<strong>`, `<em>`, `<code>`, and `<a>` links to github.com /
  kingchddg901.github.io, showing other tags as visible literal text so a
  translator sees the mistake), or is rejected wholesale if it contains active
  content (`script`/`iframe`, `on*` handlers, or `javascript:`/`data:`/protocol-
  relative URLs). The gate parses strings through the same browser HTML parser the
  display code uses, so encoded evasion like `java&#9;script:` is caught for what it
  really is. Rejected files are remembered by content hash and skipped silently on
  reload; fixing the file clears it, and a diagnostics report shows what was
  quarantined and why.
- **Translations are layout-gated in CI.** Every shipped locale is rendered under
  deliberately lengthened text (desktop and mobile) and the build fails if any
  translated string breaks the layout, so a card in your language stays usable and
  free of unwanted horizontal scrolling.
- **Maintenance values prefer structured backend fields.** Percent remaining,
  hours, and used-since-reset are now read as structured fields (instead of echoing
  a pre-built English summary), so numbers and units format correctly in each
  language; trust-reason and dock action-gate messages are keyed on stable reason
  codes so they localize cleanly. Animal/companion names and the "Rainbow Bridge"
  idiom translate via established renderings, while protected proper names (e.g. the
  "Rainbow Bridge — Mittens" memorial) stay untranslated.
- **Deleting an unnamed map is now a one-click confirm.** The backend no longer
  synthesizes an English "Map 6" name for an unnamed map — which leaked English in
  every language and forced you to type an English token to delete it. Unnamed maps
  render the localized "Map {id}" label and drop their high-protection delete from
  "type the exact name" to a single explicit confirm; named maps still require
  typing their (locale-invariant) stored name.

### Fixed
- **The renderer now actually switches language.** A renderer-layer bug read the
  wrong Home Assistant handle and always fell through to English, silently making
  roughly 1,350 translated keys inert for language switching; the entire tab UI had
  been rendering in English regardless of your chosen language. A standalone
  room-card placed without a main card had the same problem (the runtime locale
  load was only wired into the main card). Both are fixed.
- **German "fan speed."** Corrected "Lüftergeschwindigkeit" (fan-blade RPM) to
  "Saugkraft" (suction) in four places to match vacuum terminology.
- **German/Dutch furnished-map labels.** An uploaded graphic was labelled
  "Kunst"/"kunst" (artwork) across nine strings; changed to "Grafik" (de) and
  "Afbeelding" (nl) to fit an uploaded floor-plan image.
- **Spanish/Portuguese accents.** Theme-editor labels were missing their diacritics
  after a first pass dropped them; re-translated with proper native spelling
  (Spanish restored across 95 labels, Portuguese across 212). Portuguese
  relative-time "mes" corrected to "mês".
- **Setup headings and floor-type chips.** Wizard step headings and floor-type
  chips (Hardwood, Tile, Carpet, …) were baked-in English data values that fell
  back to English even when a translation was active; they now translate in all
  seven languages (e.g. German Setup headings now render in German).
- **English-leaking maintenance sections.** Filled four guide sections that
  rendered in English inside otherwise-localized cards (mopping cloth, swivel wheel,
  rolling-brush guard note, dust-collector tank note) across all seven languages,
  and cleaned up Italian/Portuguese/Dutch notes that had leaked manual-section
  references.
- **Latent encoding/empty-value bugs.** Fixed double-encoding that would have shown
  literal HTML entities (e.g. a French "l'eau", a group name like "Status,
  Confidence & Alerts") in room-estimate rows, the mapping-review outlier badge, and
  theme group-filter chips; a Metrics cell that rendered blank because an empty
  translation was mistaken for "no value"; and a status slug so the backend's
  British "cancelled" is recognized and translated rather than leaking raw.
- **Restored the card shell styling.** A stray backtick in a stylesheet comment
  truncated the bundled CSS, leaving the header unstyled and tab scrolling broken
  with no error. The styling is back, and a build guard now fails loudly on this
  class of breakage rather than shipping it silently.
- **Smaller card download.** Non-English locales no longer ship inside the card
  bundle — they are served as JSON and loaded at runtime, shrinking the card from
  ~1.93 MB to ~1.15 MB (about 40% / 772 KB smaller).
- **No stray English on the profile cards.** The "save candidate" badge and a few
  setting values ("Vacuum and mop", "Standard", "Turbo") rendered English on the
  Metrics → Profiles cards and filters because the stored values were un-normalized
  display strings; they now localize.
- **The room editor only offers settings your robot has.** Each picker (suction /
  mode / water / intensity) listed values aggregated from *every* saved profile, so
  a value from one brand's template (e.g. a Eufy "Standard" suction) appeared as a
  selectable option on another robot — including a Roborock, whose suction set is
  only gentle/quiet/balanced/turbo/max. Pickers now show the adapter's declared
  options plus the room's own current value, nothing else.

### Eufy scalar/Tuya devices
- **Support for reduced-transport ("scalar/Tuya") Eufy robots.** Vacuum Agent now
  drives Eufy robots on eufy-clean's legacy path, where the robot exposes its room
  list as a vacuum attribute but never creates an active-map sensor. These devices
  can now import rooms and run per-room cleans — anchoring to a single implicit map
  when there is no active-map sensor but the room list is populated, instead of
  failing with a red "No active map detected" warning. The X10 Pro Omni is verified;
  the other mapper families (X / S / L / LR / Omni) are expected to work and are
  test-and-report. Live map still needs the smcneece eufy-clean fork.
- **Model detected from the device registry.** A scalar-provisioned X10 (model
  T2351) now detects as the "x10" family instead of falling back to "generic",
  restoring its mop, mop-wash/dry, dust-empty, and path-control capability hints.
  Existing installs self-heal on the next restart, and a capability refresh no
  longer reverts a correctly detected model back to "generic" (which had silently
  disabled rooms on scalar devices).
- **Diagnostics now open with a plain-English `self_check`.** The diagnostics
  download leads with a summary answering "why can't I import my rooms?" — the
  transport mode (full MQTT vs. reduced scalar/Tuya), whether room control/import
  are available, whether the map picture can render, and the detected model — without
  reading the raw internals.
- **Docs: which Eufy models Vacuum Agent can drive.** The README "Tested hardware"
  section and the user-guide overview gained a "Will my Eufy vacuum work?" guide:
  per-room cleaning, the live map, room rollover, and learning/ETA all require an
  Eufy that builds a room map with per-room segments. The basic-navigation RoboVac
  C-series and G-series build no room map and are documented as unsupported (owners
  are pointed to eufy-clean directly).

### Roborock (external contribution by [@Nebr88](https://github.com/Nebr88), [#19](https://github.com/kingchddg901/Vacuum_Agent/pull/19))
- **Cleaning durations are recorded correctly.** Roborock reports cleaning time as a
  duration sensor (minutes, sometimes hours or milliseconds) rather than raw
  seconds; Vacuum Agent now converts using the sensor's unit before storing, so runs
  and the learning/ETA system are no longer off by a factor of 60 (a 6.15-minute
  clean records as 369 s, not 6).
- **Live room tracking no longer completes rooms prematurely.** Roborock's
  current-room signal is a live pointer that can revisit rooms while it optimizes its
  route; pointer changes are now treated as position updates only, deferring room
  completion to the final job snapshot. Per-room fan speed is still pushed live as
  the robot moves through its optimized order.
- **No spurious anomaly warnings on optimized routes.** Stall, running-long, and
  skipped-room checks assumed queue-order cleaning; for path-optimizing devices that
  legitimately jump ahead, those checks are now suppressed so a normal optimized
  route is not misreported as a problem.

### Internal
- **i18n contract + reachability gates.** A framework-free `npm run check:i18n`
  suite (grew from 11 to 26 assertions) asserts the fallback chain, interpolation,
  plural selection, escape-by-default, the draft-gate, locale validation, and
  prototype-pollution defenses, plus an orphan/dead-key check (orphan = fatal) that
  proves key reachability from source rather than a hand-maintained allowlist. A
  central `validateLocale()` drops bad entries while keeping the rest, blocks
  `__proto__`/`constructor`/`prototype` keys, enforces placeholder parity, and keeps
  the clean catalog a strict subset so English fallback is never removable.
- **Locale-intake sanitiser.** `src/i18n/sanitize-locale.js` parses via a real
  `<template>` walk (matching the actual sink) with an escape-visible scrub, a tag/
  link-host allowlist, URL-parser-based scheme checks, FNV-1a content-hash
  quarantine, and DOMPurify as a final hardening pass; covered by a real-Chromium
  adversarial suite (mutation-XSS, namespace payloads, host-confusion) and vetted by
  three blind security reviewers.
- **Harness hardening.** Added a pseudo-long/Cyrillic locale generator, a property-
  based layout-overflow gate at desktop @500px and mobile @390px, a real-locale
  `shoot-locales` render path (7 languages × 10 tabs, zero real overflow), and an
  `i18n-locale` spec that proves the UI actually switches language — the regression
  the English-only harness had missed. A build-time `check-styles.mjs` guard
  verifies brace balance to prevent silent CSS truncation. English output stayed
  byte-identical across every migration wave.
- **Misc.** De-bundled locale loading shares one catalog load with no double-fetch;
  context-free primitives (Save/Edit/On/Off/…) hoisted to `common.*`; removed the
  dead `_slugify_profile_name` slugifier; `deploy-live.ps1` gained an optional
  `-LiveRoot` to target a clone instance. Roborock tests realigned to live-pointer
  behavior; lifecycle/dock-drift test flakes stabilized (2,771 passed, 1 skipped).
  Developer reference (`docs/dev/33-i18n-system.md`) added; `mkdocs --strict` clean.
- **Settings normalized to canonical codes.** Observed clean-mode / clean-intensity
  / fan-speed / water-level values are normalized through adapter-owned alias maps
  (mirroring the existing water-level aliases) before they reach the card, so it
  always receives a code its vocabulary is keyed on — no future un-keyed display
  string can leak from that path. Each brand declares its own maps in its adapter.
  Backed by a code-first reason-code path: the learning manager emits stable codes
  (status, sanity flags, learning blockers, exclude/cancel reasons) and the card
  localizes them, keeping the English text only as the fallback.

## [1.2.5] - 2026-06-23

### Fixed
- **Empty-rooms hint points to the right place.** When a managed vacuum has no
  rooms yet, its empty-state hint now directs you to **Setup → Import Active
  Map** (the path that actually populates rooms) instead of a stale instruction.

## [1.2.4] - 2026-06-23

### Fixed
- **Stable room identity for non-Latin names.** Room slugs are now NFC-normalized
  before becoming identifiers, so Cyrillic/accented room names that differ only by
  Unicode composition resolve to one stable identity across reconciliation.
- **Unnamed Roborock map imports.** A Roborock map with no name no longer fails to
  import (external contribution by [@Nebr88](https://github.com/Nebr88),
  [#18](https://github.com/kingchddg901/Vacuum_Agent/pull/18)).
- **DOM-XSS hardening.** Map-tooltip room labels are HTML-escaped before they reach
  the DOM, so a crafted room name can't inject markup into the map overlay.

### Changed
- **Live-map / zone messaging retargeted to the jeppesens fork.** The Eufy
  live-map and zone-clean docs now point at the maintained `jeppesens` eufy-clean
  fork (v1.11.1+) instead of the older smcneece fork.

### Internal
- Closed `map_source_coordinator` + `_common` coverage gaps and reconciled the
  testing docs; refreshed the README Screenshots + Documentation sections for the
  GitHub Pages hub.

## [1.2.3] - 2026-06-22

### Added
- **Download Diagnostics.** The integration now answers Home Assistant's
  *Download diagnostics* button (Settings → Devices & Services → Vacuum Agent →
  ⋮). Per managed vacuum it reports how each adapter role resolves to a real
  entity — the fastest way to spot a missing/blank `active_map` sensor, the most
  common onboarding snag — plus the active map, every stored map and its per-room
  config, capabilities, the raw provider vacuum state, and the maintenance
  snapshot. Read-only, brand-agnostic (Eufy + Roborock), with credentials and the
  free-text notes field redacted.
- **Issue templates.** A bug-report form that asks for a diagnostics download up
  front (so reports arrive with the data needed to triage them), plus a
  feature-request form.

## [1.2.2] - 2026-06-22

### Added
- **Lifetime device stats on the Maintenance tab.** Total cleaned area (m²), total
  cleaning time, and lifetime clean count — plus the **dock firmware version** — now
  surface in the Maintenance overview, sourced from the robovac_mqtt v1.11.0+ Eufy
  sensors. Each value is shown only on devices that report it (hidden otherwise), so
  brands/models without these sensors are unaffected.

### Fixed
- Battery health (`_battery_health` sensor) is now capped at **100%** — a battery is
  never "healthier than new". A raw reading above 100 (the cell charging faster than
  its install baseline, common while the baseline is young) looked odd; the uncapped
  value stays on the `_cv_charge_speed` diagnostic sensor and the health sensor's
  `uncapped_pct` attribute.

## [1.2.1] - 2026-06-22

### Fixed
- `services.yaml`: the furnished-render services (`set_furnished_art_placement`,
  `set_room_viewport`) declared a number-selector `step` of `0.0001`, below Home
  Assistant's `1e-3` floor, which failed `hassfest` validation. Switched those
  resolution-independent pct-float fields to `step: any`. No behavior change — these
  services are driven by the card, not entered by hand.
- CI: refreshed the map-configuration visual-regression baseline (the tab grew when
  the furnished-render + align panels landed in v1.2.0).

## [1.2.0] - 2026-06-22

**The map comes alive.** The Map view goes from a static backdrop to a live, interactive
surface: the robot is tracked across it in real time, you can lay a render of your actual
furnished home over the live map (the robot and overlays ride on top), draw a box to
zone-clean, and more. The biggest map release since the integration began.

### Added
- **Mittens joins the map.** A new **Rainbow Bridge** animal group — companions for
  remembered pets — debuts with **Mittens**. Unlike the themeable animals, she's painted
  true to life: her real markings stay fixed whatever theme you run, and only her eyes
  shift with battery state. *In loving memory.*
- **Live robot tracking & map overlays.** A new VA-owned read of the device's own map
  (`map_state_source`) puts the live robot position, heading, dock, current room, cleaning
  path, and hazards (no-go / no-mop / walls) on the map in real time — plus native
  current-room rollover and a faster live room/fan refresh on Roborock. A **Mascot follows
  robot** toggle lets your companion ride the robot's live position.
- **Furnished render.** Lay a to-scale render of your real home over the live map so the
  robot drives across your actual furniture. **Save map image** to trace over, upload your
  art, pick a view mode (Live / Blend / Art), and align by eye — drag, scale, rotate
  (coarse ±90°, fine ±1°/±0.1°, ±15° trim slider). No calibration step — aligning by eye
  once is all it needs, so the live overlays ride on top for free. Brand-agnostic
  (Eufy fork + Roborock).
- **Zone cleaning (draw a box).** Zone-clean an area you draw on the live map, at any map
  rotation, with suction/mop settings — on **Eufy** (via the fork) **and Roborock** (stock
  integration, no fork/PR). Per-clean caps: Eufy up to 10 zones; Roborock up to 5, each
  1–32.8 ft² (enforced in the card + at dispatch).
- **More map interactions.** Tap rooms on the map to build a clean selection (unpicked
  rooms dim), **Hide area** to mask map noise, and draggable room-area (m²) labels. On a
  **bare Roborock live map** (no drawn rooms), the room names, the mascot, and tap-to-select
  now work from the device's own rooms (selected rooms light up).
- **Smarter external-run learning.** App-started runs now use the robot's recorded path to
  work out which rooms were actually cleaned, feeding the external-run review wizard.

### Changed
- New user guides for furnished render, zone cleaning, hide-area, and the live map, plus
  reconciled services/data-model references and consistent "NN — Title" nav titles across
  the docs site.
- Eufy-measured planning defaults moved into the Eufy adapter (cleaner brand boundary).
- Internal: the core manager was re-bundled into focused subsystems — `PhaseRunner`
  (strict-order phases), `ActiveJobTracker` run-anomaly detection, a `live_refresh`
  subsystem (Roborock live room/fan), and `MapSourceCoordinator` (the `map_state_source`
  backend). No behavior change.

### Fixed
- Strict-order finalization records every phase's timing, not just the last.
- Learning guards: recharge-drain bias, attribution-confidence marker, and rescuing the
  first cleaned room when `cleaning_area` is stale.
- Roborock live-room refresh targets `roborock.*` (not `vacuum.*`) and sticky-disables on a
  missing service.
- CI flakes: serialized the dock-drift append + isolated its test; closed re-run
  config-dir/executor leaks.

## [1.1.1] - 2026-06-16

**Optional CV stack, handled cleanly.** The CV libraries (numpy, Pillow, scipy) that
power Auto (CV) map segmentation are optional — the integration loads and works fully
without them. This release makes that explicit instead of a silent dead-end.

### Changed
- **Auto (CV) is gated on runtime library availability.** The dashboard snapshot now
  surfaces `cv_available` / `cv_missing`; when numpy/Pillow/scipy are absent (e.g. on HA
  Container/Core), the card hides the "Auto (CV)" chip and shows a note pointing to Live
  map / custom layouts / manual bounds, rather than a silent "No segments analysed".
- **README install matrix.** Required = Home Assistant + one supported provider vacuum
  entity; optional = a provider map/camera entity, the CV science stack, and brand
  companion entities. Manual map setup is the source of truth and is never required to
  install or load — Vacuum Agent is a supervisory layer over whatever the provider exposes.

### Fixed
- Corrected a stale code comment pointing at a non-existent `mapping/image_segments.py`
  (the CV pipeline lives in `adapters/eufy/segmentor.py`).

## [1.1.0] - 2026-06-16

**Eufy live maps (via the eufy-clean fork).** Eufy vacuums can now use a live map as
the Map-view backdrop and compose tap-selectable rooms over it — the same flow the
Roborock S6 has — for installs running the community
[eufy-clean fork by smcneece](https://github.com/smcneece/eufy-clean) that renders the
robot's map and exposes it as a `camera.<device>_map` entity. Plain (non-fork) Eufy
installs are unaffected.

### Added
- **Eufy live-map backdrop + selectable "Live map" source.** A Setup-tab "Live map
  camera" picker points the Map view at a live `camera.`/`image.` entity
  (override-first over an auto-resolved `camera.{object_id}_map` pattern, existence-
  gated). A "Live map" segmentation source lets you draw and link tap-selectable rooms
  straight over the live map, reusing the custom-layout composer — richer than the
  Roborock integration, which draws no polygons. A per-vacuum room-label toggle hides
  the card's own labels so they don't stack on a map that already carries them, and a
  `camera.` backdrop refreshes at frame cadence via a cache-bust on its stable token.

### Changed
- Acknowledged Home Assistant's built-in Roborock integration and its maintainers in
  the README.
- Doc reconciliation for the live-map feature (user guide, services reference, dev
  references).

## [1.0.0] - 2026-06-16

**Second brand: Roborock.** Vacuum Agent began as an Eufy integration; 1.0 makes
it a *multi-brand* one. Everything brand-specific now lives in a declarative
adapter, and the **Roborock S6** ships as the second supported brand — per-room
cleaning, native live room tracking, live maps, and strict ordering, all
Eufy-safe (the Eufy path is byte-identical where it should be). 1.0 marks the
architecture settling: the adapter seam, the dispatch-engine job model, and the
live-map pipeline are now the stable foundation other brands plug into. The
**Eufy X10 Pro Omni** and the **Roborock S6** are each brand's tested reference
model.

### Added
- **Roborock adapter (Roborock S6).** A capability-detecting adapter brings a
  second brand online with no core forks: room discovery from the `roborock.get_maps`
  service response (with name-slug identity reconciliation), live name→segment-id
  resolution at dispatch, completion keyed on the cleaning binary, per-room **live**
  fan speed, and native `current_room` live room rollover. The S6's real
  constraints are modeled honestly — mop/water is observe-only, passes are global,
  and room profiles are dropped — rather than faked.
- **Live maps in the card.** On live-map brands the Map view uses the vacuum's
  **live map image** as the backdrop (no screenshot upload): draw and save room
  segments straight over it, rotate it in 90° steps (stored server-side, so it
  follows you across devices) with the whole layer — image, polygons, labels,
  mascot — turning together, and watch a dwell-debounced mascot follow the robot's
  current room (draggable even when rotated).
- **Strict cleaning order.** A per-run opt-in for path-optimizing brands (e.g. the
  S6, which treats queue order as advisory): the integration sequences the run one
  room at a time in your exact order, with a per-phase watchdog that settles,
  dispatches, verifies the device actually started the room, and retries — fixing
  the "second room never fired" failure where a robot ignores a clean sent the
  instant it docks.
- **Per-vacuum panel rename.** Each vacuum's sidebar entry can be renamed live from
  the Setup tab (default "Vacuum Agent") — useful once you run more than one.
- **Room-identity reconciliation.** When a re-segment renumbers rooms, an
  apply/dismiss review carries each room's durable settings, access-graph grants,
  and floor-type confirmations onto the new IDs by name.
- **Add-another-vacuum** control in the Setup tab, and capability-gated navigation
  (Base Station and Map Bounds tabs appear only on models that have them).

### Changed
- **Adapter discipline.** Brand specifics are declarative config, not core code:
  the dispatch payload **shape** and **job model**, the live-map image entity-id
  pattern, and the strict-order phase-timing all moved out of core into the adapter.
- **Docs reconciled to multi-brand.** The README and the entire `docs/` tree
  (62 audited doc↔code findings across 32 files) now cover Eufy and Roborock with
  brand-aware inline callouts; a new Roborock adapter developer reference was added.

### Fixed
- Recharge-resume finalize guard (a mid-job dock-to-recharge no longer ends the job).
- Honor an explicit `supports_water_control` capability hint (S6 water is unsettable).
- Reconciliation no longer leaks stale rule-status onto a re-used room ID.
- Live-backed custom segments rendered off-screen; mascot drag drifted on a rotated map.
- Learning snapshot reads moved off the hot path.

## [0.11.0] - 2026-06-14

**Theme System 2.0.** Themes were already fully customizable; this release makes
them *discoverable, shareable, and per-device*. A tag system runs across the card
and the public gallery, a submission bot turns a pasted export into a reviewed
pull request, colorblind-safety is now verified rather than claimed, and each
browser can pin its own theme.

### Added
- **Theme tags + search, in the card and the gallery.** Every theme is auto-tagged
  from its palette — mode (dark/light), accent, temperature, surface, contrast,
  accessibility, and source — with free-text "vibe" tags on top. Filter and search
  the gallery *and* the card's own theme picker with the same vocabulary (OR within
  a facet, AND across facets), and edit a theme's vibe tags inline in the picker.
- **Theme submission pipeline.** Submit a theme to the gallery from a GitHub issue
  form: a bot validates the export, auto-tags it, verifies colorblind-safety,
  renders a real-card preview, and opens a pull request for a maintainer. Nothing
  publishes automatically. See
  [Sharing themes](https://kingchddg901.github.io/Vacuum_Agent/docs/user-guide/15-sharing-themes/).
- **Verified colorblind-safe badge + "Best for" filter.** colorblind-safe is now a
  badge *any* theme can earn — verified by simulating the three dichromacy types,
  not eyeballed — and a **Best for** filter surfaces themes tuned for red-green or
  blue-yellow vision.
- **Per-device theme selection.** Pin a theme to just this browser or kiosk
  ("This device only"), or follow the shared active theme. Your library and edits
  stay shared across devices; only the *selection* is local.
- **Theme picking on mobile.** The Theme tab is now reachable on phones for
  browsing, switching, importing, and exporting whole themes (the Palette and
  Token editors stay desktop-only).
- **One-click gallery download** and **theme source provenance** (core / community
  / generated / manual), shown as a filter facet.
- **New documentation.** A
  [Theme system](https://kingchddg901.github.io/Vacuum_Agent/docs/user-guide/17-theme-system/)
  user guide and an
  [Authoring a theme](https://kingchddg901.github.io/Vacuum_Agent/docs/contributing/theme-authoring/)
  contributing guide, plus full docs for the tag system, submission flow,
  per-device themes, and colorblind buckets.

### Changed
- **Theme Export/Import is now a modal.** Export opens a window showing the JSON
  with a **Copy** button (and a **Send to HA** option that posts it to a persistent
  notification); Import is a paste box — replacing the old console dump and browser
  prompt. Copy works on plain-HTTP LANs via a fallback.
- **Theme picker layout.** A collapsible filter band and a scrollable grid keep a
  large library usable.

### Security
- **Pre-release hardening (adversarial review).** Closed a stored-XSS through a
  submitted author URL, restricted author-URL credits to direct http(s) links (no
  shorteners or dangerous schemes), fixed a per-device pin that could wipe itself
  on load, and stopped theme metadata (tags/author) being dropped when a theme is
  overwritten.

## [0.10.3] - 2026-06-13

Map-editor visibility fixes (custom-layout composer + CV vertex editing).

### Fixed
- **The composer's selection outline stays visible on light / photo map backdrops.**
  A selected shape's bright outline could wash out over a light custom-photo backdrop;
  it now carries a thin black halo on each side, so it reads on any backdrop.
- **Map-editor lines and vertex handles no longer balloon when you zoom in.** The
  CV-segment polygon stroke and the vertex grab dots were sized in map units, so they
  grew as you zoomed to align a room and hid the floor plan underneath. They are now a
  fixed thin size at any zoom level.

## [0.10.2] - 2026-06-13

Light-theme readability fixes — the card now renders light themes cleanly,
surfaced by adding the gallery's first light theme.

### Fixed
- **Room order numbers (#1–#5) are readable on light themes.** The room-card order
  label inherited a fixed near-white colour and disappeared on light surfaces; it
  now tracks the theme's secondary text colour (unchanged on dark themes).
- **The room-rules "Disabled" tag keeps its pill on light themes.** Its background
  and border were hard-coded white; they now use the surface/border tokens.

## [0.10.1] - 2026-06-13

A small theming fix.

### Fixed
- **Modals now follow the active theme.** A custom theme that set only the core
  colors — surfaces, text, and accent, as hand- and AI-authored themes typically
  do — left every modal (the room editor, the app-started-run review wizard, and
  the rest) on the default dark palette, because the modal/overlay token family
  didn't derive from those core colors. Modals now derive their surfaces, text,
  and accent from the active theme, so any theme themes its modals too. A
  light-mode default is preserved, and the built-in themes are unchanged.

## [0.10.0] - 2026-06-12

A UI-heavy release: hand-drawn custom map layouts, a real documentation site, and
a reworked profile filter — plus a batch of fixes.

### Added
- **Named custom map layouts.** Keep several hand-drawn layouts per vacuum
  alongside Auto/CV detection. Each layout can have its own backdrop, rooms, room
  links, and mascot dock spot. Build rooms from primitive shapes — rectangles and
  circles — then move, scale, resize, rotate, merge, or subtract cutouts. Link
  each custom room to a real vacuum room, then save and re-edit later. See
  [Making your own maps](https://kingchddg901.github.io/Vacuum_Agent/docs/user-guide/16-making-your-own-maps/).
- **Documentation site.** The docs now render as a searchable
  [MkDocs site on GitHub Pages](https://kingchddg901.github.io/Vacuum_Agent/docs/),
  cross-linked with the theme gallery.
- **Profile filters reworked.** The Metrics and Learning Review profile filters
  now have a search box, a height-capped scroll area, and settings-disambiguated
  chips. Duplicate-named profiles, such as several "Kitchen Vacuum Quick"
  variants, show their settings so you can tell them apart on both the chips and
  the result cards.
- **Independent floor-texture toggles.** Map polygons and room cards can now
  control floor textures separately.
- **Custom-map polish.** Added mascot dock spots and composer shape rotation.

### Fixed
- Large map backdrops no longer exceed Home Assistant's 4 MiB websocket limit and
  drop the connection. Uploads are resized/recompressed client-side while
  preserving transparency.
- Non-first custom layouts now render their room-control map correctly.
- Dashboard snapshots no longer block the event loop on a `room_stats` read.

### Internal
- Large test-coverage and documentation-reconciliation pass.

## [0.9.17] - 2026-06-08

> The external-run capture + review capability in this release was driven entirely by
> [@chubban-lgtm](https://github.com/chubban-lgtm)'s question in
> [#4](https://github.com/kingchddg901/Vacuum_Agent/issues/4) — *"does it not use the
> runs from the eufy app for learning review?"* I didn't think it was possible at first;
> a little digging proved otherwise. Thank you.

### Added
- **External-run review wizard: server-side re-segmentation.** The "review an
  external (app-driven) run" flow no longer only lets you merge rooms client-side
  — it now re-segments on the backend from the raw counter trace. Step 1 is a
  **room-count stepper** plus a per-boundary **Split here** / **Merge up** control
  (action-first labels — the button says what it *does*); step 2 is a **per-room
  settings editor** for `fan_speed` / `clean_intensity` / `water_level` drawn from
  the adapter vocabulary (it mirrors the live room editor). The card calls the new
  `eufy_vacuum.resegment_external_run` service (`src/actions/external-jobs.js`),
  which takes either an `expected_rooms` count *or* an explicit `active_boundaries`
  list (mutually exclusive) and returns the re-segmented record.
- **Pending external-run schema v2.** Finalizing an external run now persists the
  raw `counter_samples` + `settings_samples` and the full candidate-boundary pool
  alongside the segments (`learning/external_ingest.py`,
  `PENDING_SCHEMA_VERSION = 2`), so a run can be re-segmented after the fact
  without re-driving the robot. Records are flagged `resegmentable` when samples
  are present; v1 records (no samples) gracefully degrade to the legacy
  merge-only view. Samples are stripped from every served/returned record
  (`strip_samples`) so the API stays light.
- **Transit-aware boundary detection.** `counter_segmentation.py` is decomposed
  into `find_candidates` → `select_active` → `build_segments`. `find_candidates`
  now surfaces a **`transit`** boundary kind (a 60–90 s flat-area inter-room move)
  in addition to `wash_plateau` / `area_jump` — the real-transit case the old
  single-pass filter silently dropped. The legacy `segment_counters()` is kept as
  a **byte-identical back-compat wrapper** (transit disabled), so the
  finalize/history path is unchanged.
- **Live queue: running-long & skipped indicators.** `get_job_progress_snapshot`
  now reports a soft **`running_long`** anomaly (the current room is past
  `running_long_ratio` × its estimate but below the existing 2× stall) and a
  conservative **`skipped`** signal (a queued room strictly before the current one
  that never completed). The queue chips render these as a warning ring
  (running-long) and a dashed, struck-through chip (skipped); a new
  `eufy_vacuum_room_skipped` event (`EVENT_ROOM_SKIPPED`) fires once per skipped
  room.
- **Brand-agnostic JOB-segmenter engine seam.** The counter/run segmenter — the
  per-room boundary detector that reads the `cleaning_time` / `cleaning_area`
  counters — is now pluggable, mirroring the dispatch-engine pattern
  (`learning/job_segmenter_engines.py`, modelled on `queue/dispatch_engines.py`).
  An adapter selects an engine via a new `job_segmenter.engine` config key; the
  framework resolves it from `_JOB_SEGMENTER_ENGINES`. This is the COUNTER
  segmenter — distinct from the MAP segmenter (`mapping/segmenter_engines.py`,
  `eufy_cv_v1`), which is unchanged. The engine owns the brand-specific stages
  (`find_candidates`, `build_segments`) and the legacy one-shot composition
  (`segment_legacy`); `select_active` stays a brand-agnostic *framework* function
  (`counter_segmentation.select_active`) so the external-review wizard's
  count/toggle logic is uniform across brands. Canonical cross-engine
  `JobBoundaryCandidate` / `JobSegment` TypedDicts document the contract.
  `EufyCounterSegmenter` (`eufy_counter_v1`) delegates verbatim to the
  `counter_segmentation` primitives and defines its `DEFAULT_TUNING` *by
  reference* to that module's constants, so the Eufy path is byte-for-byte
  identical by construction. Unlike the map seam, an absent/unknown engine falls
  back to the **Eufy** engine (not a noop), so live rollover, external-run ingest,
  and learned history keep working with no adapter registered. All three counter
  consumers now route through the engine — learned history
  (`learning/history_store.py`), external-run ingest
  (`learning/external_ingest.py`), and live rollover (`jobs/active_job.py`).

### Changed
- **Live current-room tracking is now transit-aware.** The 5 s job-progress tick
  (`jobs/active_job.py`) advances the current room on a real 60–90 s inter-room
  transit, not only on a wash/area-jump boundary, via a new transit-aware
  boundary count — fixing rooms that the live queue under-counted mid-run. The
  finalize/history segmentation is untouched.
- **Brand-agnostic adapter hooks (Eufy is the default, byte-identical).** The
  Eufy adapter config gains a `live_transition` block (boundary gaps, cadence,
  `rollover_kinds`, `native_transition_source`) and an `anomaly` block
  (`running_long_ratio` 1.5, `stall_ratio` 2.0). The previously-hardcoded
  constants in `planning/run_plan.py` (per-level water rate, wash-interval bounds,
  low-water margin) are now read as *adapter-overridable hooks* —
  `_water_rate_ml_per_minute` takes a `rate_override` from
  `water_model_configs[model]["water_rates"]`, and the wash-interval bounds /
  low-water margin read `wash_frequency_bounds` (top-level adapter config) and
  `water_model_configs[model]["low_clean_water_margin_ml"]` respectively — each
  falling back to the prior Eufy value when the key is absent. (The Eufy adapter
  does not yet declare those override keys, so Eufy keeps the built-in defaults and
  behavior is unchanged; the seam is in place for a second brand.) The room-profile
  capability gate (`profiles/room_profiles.py`) now *derives* the mop→vacuum
  downgrade target from the vacuum-only built-in profile (`get_room_profile`)
  instead of hardcoding it.
- **Boundary thresholds de-duplicated to a single source.** The five gap/area/
  cadence thresholds (`gap_delayed_s`, `gap_transit_s`, `gap_plateau_s`,
  `area_jump_m2`, `cadence_s`) now live **only** in the adapter's
  `job_segmenter.tuning` block — live rollover, external-run ingest, *and* learned
  history all read them from the resolved engine tuning. The `live_transition`
  block was trimmed to just its orchestration knobs (`enabled`, `rollover_kinds`,
  `native_transition_source`); the five threshold keys were removed from it (and
  from `_LIVE_TRANSITION_DEFAULTS` in `jobs/active_job.py`). The persisted
  external-run record field `gap_transit_s` (60.0) is unchanged — only its
  provenance moved (module constant → resolved engine tuning). Values and behavior
  are unchanged for Eufy. *(This supersedes the 0.9.16-era note that
  `live_transition` carried the boundary gaps and cadence.)*
- **Adapter-sourced room-profile vocabulary.** Room profiles are now resolved from
  the adapter rather than read straight off the in-code constants. A new adapter
  `room_profiles` block + `resolve_profile_catalog()` (`profiles/room_profiles.py`)
  merges the block over the in-code defaults **per key** (`builtins`,
  `custom_template`, `legacy_aliases`, `default_profile`, the floor-type fan/water
  defaults, `normalize_defaults`); a None/empty block returns the in-code defaults
  verbatim. Every resolver gained an optional `catalog` param. The in-code
  `BUILT_IN_ROOM_PROFILES` stays the framework default and the
  `_PROTECTED_ROOM_PROFILE_NAMES` source (that module-load binding is untouched);
  the Eufy adapter declares the block *by reference* to those constants, so Eufy is
  byte-identical. Wired into the **dispatch** path (`queue/queue_engine.py`
  `build_room_clean_payload`), which resolves the catalog from the adapter and
  threads it into per-room resolution and the capability gate. The global/singleton
  profile editor and the pure room-builder defaults still use the framework default
  catalog (no per-vacuum context); a second brand's editor UI would show framework
  defaults until threaded — a documented follow-up.

### Fixed
- **Graduated external runs no longer falsely flagged "failed sanity checks."**
  The jobs index stored `sanity_passed` as `None`, so the history snapshot's
  `not item.get('sanity_passed', True)` test never hit its default and tagged
  *every* graduated external run as failing the backend sanity checks. The checks
  now use `item.get('sanity_passed') is False` (`learning/manager.py`), and
  graduation sets `sanity_passed=True` / `sanity_flags=[]` explicitly (external
  runs only graduate after passing the tier-1 identity gate, so they're sane by
  construction).
- **External-run room dropdown readability.** The "assign to room" `<select>`
  options now pin a dark background / light text, fixing washed-out unreadable
  options in Windows Chrome.

## [0.9.16] - 2026-06-06

### Fixed
- **Run Profiles panel no longer overlaps the room cards.** On narrow card
  widths the panel positioned itself with a viewport media query that ignored
  the card living in a container narrower than the window, so it overlapped the
  rooms. It now wraps below them via container-relative flex — the two never
  collide at any width.

### Added
- **Theme gallery + submission system.** A public
  [theme gallery](https://kingchddg901.github.io/Vacuum_Agent/) where you can
  browse community themes (each previewed as the real card), download one to load
  via **Upload**, and **submit your own** with a "+ Submit a theme" button. A
  submission flows through an issue form, a bot that validates the export and
  renders an inline preview, and a pull request a maintainer reviews and merges —
  nothing auto-publishes, and the validator reuses the card's own import safety.
  The gallery and bot are repo-hosted, so this doesn't change what HACS installs.

### Docs
- **Theme-sharing documentation pass.** New end-user guide
  (`user-guide/15-sharing-themes`), the full gallery + submission architecture in
  `dev/27-render-harness`, and cross-links from the theme-system, README, and
  testing docs.

## [0.9.15] - 2026-06-06

### Added
- **Colorblind Safe theme.** A new built-in theme with a CVD-validated palette —
  every status-color pair stays distinguishable under protanopia, deuteranopia,
  and tritanopia (CIEDE2000 ΔE ≥ 15). See the new Accessibility guide.
- **Always-on status shape marks.** Mapping-review badges now carry a distinct
  non-color shape per state in addition to color, so status is never conveyed by
  color alone — this applies to *every* theme, not just the colorblind one.

### Fixed
- **Mapping-review badges are now themeable.** They were colored by undefined CSS
  variables, so the hardcoded fallback always won and no theme could recolor
  them. Migrated to the registry `--evcc-sem-*` tokens (with a new
  `--evcc-sem-info`), so themes — including the colorblind palette — now drive the
  badge colors.

## [0.9.14] - 2026-06-05

### Added
- **Two-tier marble veins.** Marble now renders separate **major** and **minor**
  vein layers. A master opacity/blur rides both tiers at once; per-tier offsets
  nudge each tier while preserving the gap between them. The minor tier *recedes*
  — its color is a clamped lighten / desaturate / hue offset from the master
  (OKLCH relative color), so it reads as atmospheric depth rather than a flat
  second color. Per-tier blur is opt-in.
- **Per-floor-type theme export/import.** Move a single floor type's look in
  isolation: **Download Floor** exports just that type's tokens
  (`evcc-floor-{type}-…json`), and uploading a floor-scoped file **replaces only
  that floor's namespace** on your active theme (clear-then-apply, values
  clamped, unknown namespaces skipped) instead of swapping the whole theme.
- **Marble presets.** Carrara, Portoro, and Calacatta starter bundles for the
  two-tier vein system. They apply as a scoped replace on the marble namespace —
  they tune marble in place, they are not separate themes to switch to.

### Changed
- **Single-source token ranges.** Editor sliders and the import clamp now share
  one min/max/step definition per token, so a slider can never show a value its
  own importer would reject.
- **Floor masks regenerated at 2048×2048** (were 512) to match the tiling/shift
  the renderer uses — sharper textures without visible seams.

### Fixed
- **Floor-texture legibility.** Status chips, room controls, and the active-clean
  progress fill stay readable over a filled floor texture across a wide range of
  theme colors (opaque chip backing, halo text-shadow, and explicit z-layer
  pinning so the texture can no longer occlude the progress fill).

### Docs
- **Full documentation accuracy pass** across the developer and advanced guides:
  corrected the adapter-config schema (17 top-level keys; `mapping` is validated
  but is not a schema field), the config-flow and storage shapes, and the
  events/services references — removed three never-implemented "runtime
  management" services and corrected `map_id` to optional (auto-resolves to the
  active map). Testing-doc counts and coverage tables regenerated.

## [0.9.13] - 2026-06-03

### Fixed
- **Integration brand logo.** `logo.png` / `logo@2x.png` were ~2× over Home
  Assistant's brand-image size limit (1024×256 / 2048×512), so the new HA brands
  proxy (which serves the integration's local `brand/` folder by domain) rejected
  them and the logo failed to load. Downscaled to spec (512×128 / 1024×256); the
  icon was already correct.

## [0.9.12] - 2026-06-03

### Fixed
- **Completed the "Vacuum Agent" rename.** The sidebar **panel title** and the
  card's panel text still read "Eufy Vacuum" — a separate string from the product
  name renamed in 0.9.11 (`sidebar_title`, not "Eufy Vacuum Manager"). Both now
  read "Vacuum Agent".

## [0.9.11] - 2026-06-03

### Changed
- **Renamed the product display name to "Vacuum Agent"** (was "Eufy Vacuum
  Manager"); the GitHub repo moved to `Vacuum_Agent`. The Home Assistant
  **domain stays `eufy_vacuum`** — all `eufy_vacuum.*` services, `eufy_vacuum_*`
  events, and `/eufy_vacuum/` paths are unchanged, so existing installs and
  automations keep working. Eufy remains the only supported brand.

## [0.9.10] - 2026-06-03

Mostly a bug-fix release, with significant under-the-hood groundwork for
multi-brand support.

### Fixed
- **Learning stats no longer corrupt on disk.** Learning JSON is written
  atomically (temp file + atomic replace), and a malformed file (e.g. a
  half-written `accuracy_stats.json`) is tolerated and self-heals instead of
  erroring on every startup.
- **No more event-loop stalls.** Synchronous file I/O during setup, dashboard
  refresh, and the job-start snapshot now runs in the executor — resolves the
  "Detected blocking call … inside the event loop" warnings.
- **Mid-job restart recovery fixed.** A crash in the periodic trace-sample flush
  meant a job spanning a Home Assistant restart silently lost its trace (no
  boundary learning); the flush now works.
- **No spurious maintenance warnings at startup.** Maintenance sensors no longer
  log "source entity unavailable" during the normal cross-integration load race;
  they start unavailable and only warn on a genuine availability drop.
- **Dock/maintenance reset buttons resolve correctly** when firmware entity names
  drift (the token-fallback resolution path was unreachable and always returned
  nothing).

### Added
- **Pluggable dispatch engine** with payload shapes for Eufy, Roborock/Ecovacs
  (flat id-list), and Dreame (parallel-array), plus a sequenced job-model
  mechanism wired into start/finalize — groundwork for second-brand adapters.
- **Brand-agnostic adapter conformance test harness.**
- **Developer docs:** Eufy adapter worked-example + CV-segmentor references, and
  a rewritten porting guide for the adapter architecture.
- **`scripts/update_test_docs.py`** — regenerates the testing-doc counts and
  per-module/coverage tables so they don't drift.

### Changed
- **Brand-agnostic core:** charging reads and the last residual Eufy assumptions
  moved out of core into adapter config; duplicate button data de-duplicated.
- **Test coverage to 94.1%** statement (CV segmentor 22% → 70%); CI gate aligned
  with the local behavior gate; checkout@v5 + setup-python@v6.

### Removed
- Dead code: defunct map entry-gating ("System-A"), the vestigial
  `boundary_pixel` field, and an unreachable current-room induction branch in the
  job-progress snapshot.

[0.9.13]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.12...v0.9.13
[0.9.12]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.11...v0.9.12
[0.9.11]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.10...v0.9.11
[0.9.10]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.9.1...v0.9.10
