# Tranche-2 Packets — Wave 7: card/frontend consumers (CARD-1..CARD-9)

**Frontend conventions (replace the backend conventions where they differ):**
- Files: `src/` only (+ `src/i18n/en.js` and ALL 17 locale packs in
  `custom_components/eufy_vacuum/frontend/locales/*.json` for every new string —
  feedback_no_string_without_i18n; nested-JSON insertion is ORDER-PRESERVING).
- Bundle is a BUILD ARTIFACT: edit src/, `npm run build:deploy`; never the minified
  bundle. Gates per packet: `npm run test:units` + `npm run check:i18n` +
  `build:deploy` (theme-lint rides it). Visual baselines: repin with `VISUAL=1` in
  the Playwright image ONLY where a packet notes it.
- "Reproducer" = a unit test on the pure-logic engine where one exists, else a
  scripted before/after check in the render harness; flip convention kept.
- Styling: ALL CSS in src/styles/ (no inline <style>), tokens only.
- Hardware tier: everything here is §M2 tier 1 — deploy-live + hard refresh
  (Ctrl+Shift+R), panel inspection; NO cleaning runs.
- Sequencing: each packet blocked_by its backend (listed); CARD-3/4/8 are
  unblocked TODAY and can run in any cheap window.

---

## CARD-1 — Refusals render as refusals (CF-5) — blocked_by RP-031

```yaml
packet_id: CARD-1
finding_ids: [carried CF-5 (FE-ERR-1 / MZ-2, the two failure-renders-as-success
  paths), plus the audit-#6 root: src/actions/core.js hides every service failure]
files: [src/actions/core.js, src/actions/ (call sites), src/i18n/en.js,
  custom_components/eufy_vacuum/frontend/locales/*.json, tests/frontend]
problem: core.js's action wrapper swallows service failures — the card renders
  success for refused/failed mutations (the proven card-side twin of RF-14).
required_behavior: >
  the action wrapper inspects RP-031's structured responses: on
  {success:false, reason} → error toast with the TRANSLATED reason code (new
  i18n namespace `service_reasons.*` — one key per Q9 operational reason, en +
  17 locales) and NO optimistic state update; raised errors (SVE/HAE surfaced by
  HA) render the same path. The two named failure-renders-as-success flows
  (FE-ERR-1/MZ-2) get explicit unit tests. Reason codes UNKNOWN to the map fall
  back to `service_reasons.unknown` + the raw code in parentheses (forward-compat
  with later backend reasons — never blank, never fake success).
rollback_plan: single commit (wrapper + keys); call-site sweep in a second commit.
proof: unit tests on the wrapper (mock refusal shapes) — before: state updated,
  no toast; after: toast keyed, state held. Visual: none (toast is existing UI).
superseded_tests: any frontend test pinning silent-swallow behaviour.
stop_conditions: [a call site DEPENDS on optimistic update for perceived latency —
  list them; optimistic-with-revert is a follow-up, not this packet]
```

---

## CARD-2 — Qualification: stale, held, allocated, provenance (CF-6) — blocked_by RP-027 + RP-013b

```yaml
packet_id: CARD-2
finding_ids: [carried CF-6 (CC-5 qualification gap)]
files: [src/state/map.js, src/renderers/ (map + metrics + learning),
  src/styles/, i18n en + 17, tests/frontend]
problem: the card renders held/stale map data and allocated/default-guess numbers
  as confident live values — the display half of RF-10/RF-11.
required_behavior: >
  (1) map: consume the hold contract (held_static/stale/stale_since) — dim the
  map layer + a "last seen <relative time>" badge; robot/room overlays absent
  (backend nulls them per RP-027) render as absent, not as stale positions.
  (2) timings/ETA: entries with allocated=True render with an "≈ shared across
  N rooms" qualifier; source="default" estimates render as "estimate (no data
  yet)" not as measured (GUESS-1's display half).
  (3) provenance keys in the learning panes: sample counts already exposed —
  surface them where confidence is shown. All strings via new i18n keys (en+17).
rollback_plan: 2 commits (map badge; metrics qualifiers).
proof: render-harness before/after screenshots + unit tests on the state
  selectors (held payload → badge flag). VISUAL=1 repin: YES (map badge).
stop_conditions: [the hold contract fields are absent in a live payload —
  backend/packet mismatch, stop]
```

---

## CARD-3 — Surface captured run errors (CF-7) — UNBLOCKED

```yaml
packet_id: CARD-3
finding_ids: [carried CF-7 (run_errors)]
files: [src/renderers/ (job/history panes), src/state/, i18n en + 17,
  src/styles/, tests/frontend]
problem: the backend carries app-started-run error evidence end to end; nothing
  displays it.
required_behavior: completed-run views (history entry + incomplete-run banner
  context) render the run's captured error list (time, translated fault label
  where the error-mining vocabulary provides one, raw code otherwise) behind a
  collapsed "N errors during this run" row. No new polling — the data is already
  in the payloads.
rollback_plan: single commit. proof: unit test with a run payload carrying
  run_errors; render harness check. VISUAL=1: no (collapsed row, existing
  patterns).
```

---

## CARD-4 — The three untranslated strings (CF-4) — UNBLOCKED, trivial

```yaml
packet_id: CARD-4
finding_ids: [carried CF-4]
files: [src/i18n/en.js is ALREADY keyed — the three strings
  (common.service_failed, learning.room_skipped, learning.run_incomplete_toast)
  need entries in ALL 17 non-EN locale packs]
required_behavior: translate per the established AI-draft tier (locale packs
  follow feedback_guide_source_ai_default; value-scan for loanwords per the
  i18n rollout rules). check:i18n goes green on the parity assertion.
rollback_plan: single commit. proof: check:i18n. VISUAL=1: no.
```

---

## CARD-5 — Missed-rooms retry is map-scoped (STATE-4 card half) — blocked_by RP-020

```yaml
packet_id: CARD-5
finding_ids: [#16:A4-STATE-4 card half (backend half closed by RP-020)]
files: [src/actions/rooms.js, src/bindings/rooms.js, src/state/learning.js,
  i18n en + 17, tests/frontend]
problem: retryMissedRooms applies missed_room_ids to whatever map is ACTIVE
  (force:true past the composer lock) — wrong-map selection wipe.
required_behavior: >
  the binding compares log.map_id to activeMapId() BEFORE acting: mismatch →
  the banner renders "recorded on <map>" with a disabled retry + a "switch map
  to retry" hint (no cross-map application, no force); match → existing flow.
  The backend refusal (RP-020's) is also consumed via CARD-1's wrapper as
  defense in depth. Banner dismissal calls RP-020's new clear service
  (STATE-9's durable dismissal — the client-only clear goes away).
rollback_plan: single commit. proof: unit test on the binding with mismatched
  map_id — before: selection rewritten; after: disabled + hint. VISUAL=1: no.
superseded_tests: bindings tests pinning force:true cross-map behaviour.
```

---

## CARD-6 — Plan honesty: leading breaks, zone repeats, zone bounds (Q12/Q17) — blocked_by RP-021a + RP-022

```yaml
packet_id: CARD-6
finding_ids: [Q17 card half (A5-PP-RP-5 display), Q12 card half (zone repeat
  control)]
files: [src/state/run-profiles.js, src/state/steps-order.js, src/renderers/
  (steps editor + zone UI), src/cards/zone-geometry.js,
  src/cards/dashboard-card.js, i18n en + 17, src/styles/, tests/frontend]

  >>> CLAUSE (3) DROPPED 2026-08-02 (Chris, OWNERSHIP-ADJUDICATION.md #5): NOT
  >>> IN SCOPE. Building the zone_bounds live readout is a feature, not a
  >>> repair, and does not belong in a defect campaign. Dropped, not deferred —
  >>> #7:DQ-ZONE-5 removed from finding_ids above. zone_bounds remains a
  >>> snapshot field with no frontend consumer BY DECISION, so a future reader
  >>> files it as intent rather than an oversight, not as a gap to close later.
  >>>
  >>> CLAUSE (2) FILE-LIST CORRECTED 2026-08-01 (main agent), after the executing
  >>> window correctly refused to guess between "file-list miss" and "build new".
  >>> It is a FILE-LIST MISS. The control EXISTS; the packet pointed at the wrong
  >>> tree. It lives in src/cards/dashboard-card.js, NOT src/renderers/:
  >>>     line 151      this._cleanTimes = 1;  // start_zone_clean repeat count
  >>>     lines 557-8   the 1x / 2x chips that set it
  >>>     line 952      clean_times: this._cleanTimes  -> the service call
  >>>
  >>> IT IS THE RIGHT CONTROL, and that needed checking rather than assuming,
  >>> because Q12 warns in its own words: "Do not infer a Eufy zone-repeat ceiling
  >>> from room passes." The ROOM passes control is a DIFFERENT control in the SAME
  >>> file (lines 502-509, clean_passes / max_clean_passes) and must NOT be gated
  >>> by this clause. Gate _cleanTimes ONLY.
  >>>
  >>> Q12 decided "unsupported and UNSURFACED until verified... the backend/card
  >>> must not expose a repeat control" — that is suppression of something that
  >>> exists, which is what this is. Nothing new is being built.
  >>>
  >>> THE TESTABILITY BLOCKER IS REAL AND HAS AN IDIOMATIC ANSWER. dashboard-card.js
  >>> extends HTMLElement and is not importable under plain `node --test` (no
  >>> customElements/window; this repo has no DOM shim). DO NOT add one. Follow the
  >>> pattern already used throughout src/state/ — affordance-and-warning,
  >>> hidden-regions, zone-draft and a dozen more are each a pure module with a
  >>> sibling .test.mjs: EXTRACT the decision ("given the snapshot's declared caps,
  >>> should the zone repeat control render?") into a pure helper, unit-test that,
  >>> and have the component call it. The component keeps the DOM; the decision
  >>> becomes testable. Capability-DECLARED only — no brand string checks, per the
  >>> clause's own wording.
required_behavior: >
  (1) Q17: the steps editor REFUSES adding a leading/trailing charge_wait/wait
  (disabled drop position + tooltip with the validation message, same i18n key
  family as RP-021a's backend reason); a legacy profile carrying one renders
  the step struck-through with "will be skipped (unsupported position)" —
  matching the backend's explicit normalization note, never a silently-shown
  step that won't run.
  (2) Q12: the zone repeat control renders ONLY when the brand's capability
  declaration supports zone repeats (driven by the snapshot's declared caps —
  no brand string checks); on Eufy it disappears.
rollback_plan: 2 commits (steps editor; repeat control).
proof: unit tests on steps-order sanitize + capability-driven visibility;
  render-harness draw check. VISUAL=1: YES (draw overlay + struck step).
superseded_tests: steps-editor tests permitting leading breaks.
```

---

## CARD-7 — Reconciliation review/confirm UI — blocked_by RP-019 + CHRIS DESIGN SESSION

```yaml
packet_id: CARD-7
finding_ids: [#10:A2-REC-1 card half (the unreachable-review product gap)]
files: [src/renderers/setup.js (EXTEND -- see below), i18n en + 17, src/styles/,
  tests/frontend]

  >>> NOT A NEW PANE (Chris, 2026-08-01). Rooms are already discovered and
  >>> surfaced in setup; a parallel review pane is redundant, and two surfaces for
  >>> the same objects is how they drift apart. The GAP is real --
  >>> rooms/reconciliation.py:141 returns {"reviews": [...], "has_changes": bool}
  >>> and there are ZERO card consumers -- but the fix is to surface the four
  >>> review kinds in the EXISTING setup surface. This closes the first and
  >>> largest of the design questions; entry point, per-kind rendering and the
  >>> stale-plan_token recovery remain for the session.
required_behavior: >
  SKELETON ONLY — the surface is a PRODUCT decision (REVIEW/catalogue pin:
  "card wiring is product work with Chris"). The packet fixes the CONTRACT:
  a review pane listing discover_rooms' reviews (renamed / id_changed /
  removed / new) with per-review accept, a confirm action carrying RP-019's
  plan_token, and the plan_changed refusal rendered as "the map changed —
  re-discover". Layout/entry-point/notification design happens WITH Chris
  before implementation (stop condition).
design_signed_off: >
  2026-08-02 — see CARD-7-DESIGN.md. The design session happened; this packet's
  stop condition is CLEARED. Read that file BEFORE this yaml: it corrects three
  things the packet gets wrong about the shipped backend.
    - TWO review kinds exist (id_changed, renamed), not four. "removed" is
      plan_migration's `dropped`; "new" is drift's. The set this packet names
      does not exist.
    - There is NO per-review accept and there must not be. reconcile_room
      rebuilds the whole map atomically and services.yaml says why: "a re-segment
      renumbers many rooms at once, so this is one per-map decision." Rendering
      checkboxes would imply a granularity the backend does not have.
    - review_discovered_rooms has ZERO consumers anywhere, not just no card
      wiring. It is dead until RP-019 lands.
  Chris's calls: setup banner ONLY (no repair issue, no notification); NO
  dropped-rooms dry-run (RP-019's scope unchanged) — but the card reports
  `dropped` from reconcile_room's own response after the fact, which costs
  nothing; stale plan_token AUTO-REFRESHES and re-renders rather than dead-ending.
stop_conditions: [design signed 2026-08-02 — the remaining gate is RP-019, which
  must ship plan_token + embedded reviews before any of this is wireable]
proof: unit tests on the token round-trip binding; the rest follows design.
```

---

## CARD-8 — Edge-mopping visibility is capability-driven (CF-9, Q11) — UNBLOCKED

```yaml
packet_id: CARD-8
finding_ids: [carried CF-9]
files: [src/renderers/external-jobs.js, src/renderers/metrics.js,
  src/state/, tests/frontend]
problem: the card renders edge-mopping controls on Roborock whose adapter
  declares supports_edge_mopping false (verified sites: external-jobs.js:287-289,
  metrics.js:537/551 — from the reconstructed-and-Q11-confirmed note).
required_behavior: Q11 VERBATIM — visibility driven by the per-brand capability
  declaration (supports_edge_mopping from the snapshot), NOT a product-wide
  removal and NOT brand-name checks; Eufy keeps the control. AUDIT the sweep for
  accidental global scope (Q11's explicit caution) — the packet's test asserts
  the control renders for a capability-true fixture and not for false.
rollback_plan: single commit. proof: unit tests both fixtures. VISUAL=1: no.
```

---

## CARD-9 — Theme flows: confirm dialogs + refusal toasts — blocked_by RP-034

```yaml
packet_id: CARD-9
finding_ids: [#17:A2-DRAFT-2 card half; RP-034's confirm:true contract consumer]
files: [src/bindings/theme.js, src/renderers/theme.js, src/state/theme.js,
  i18n en + 17, src/styles/, tests/frontend]
required_behavior: >
  (1) selecting a different theme with a dirty draft prompts "discard unsaved
  edits?" and sends confirm:true only on accept (consumes RP-034's refusal);
  re-selecting the ACTIVE theme is a no-op (matches the backend short-circuit).
  (2) theme service refusals ({success:false}) render via CARD-1's wrapper;
  overwrite's draft-over-target semantics get a one-line description in the
  overwrite dialog so the user knows the target is the base (Q7 surfaced).
  (3) import rejections (RP-034's invalid-key list) render the rejected keys.
rollback_plan: 2 commits (confirm flow; refusal surfaces).
proof: unit tests on the binding (dirty→prompt→confirm:true; active→no-op).
VISUAL=1: no (native confirm pattern already in use).
superseded_tests: bindings tests pinning the unconditional setActiveTheme call.
```

---

## Wave-7 sequencing & register

| Packet | Blocked by | Can run now? |
|---|---|---|
| CARD-3, CARD-4, CARD-8 | nothing | YES — any cheap window |
| CARD-1 | RP-031 | after Wave 6 |
| CARD-5 | RP-020 | after Wave 3 |
| CARD-6 | RP-021a + RP-022 | after Wave 4 |
| CARD-2 | RP-027 + RP-013b | after Waves 2+5 |
| CARD-9 | RP-034 | after Wave 6 |
| CARD-7 | RP-019 + Chris design session | design first |

i18n total: 5 packets add locale keys (CARD-1/2/5/6/9 + CARD-4's three) — batch
translation passes per the parameterized workflow in project_i18n_rollout when
several land together; langs stay LOCKED at 18. OpenDyslexic (CF-8) remains its
own planned feature outside this campaign.
