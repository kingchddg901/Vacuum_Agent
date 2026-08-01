# REVIEW-02 — Family verdicts (Passes 2, 3, 7)

Mandatory high-risk targets reviewed first, at depth; remaining families swept for the
Pass-2 attack classes. Source re-checks performed where noted (fresh Grep/Read against
`c61b3eb`, not corpus quotes).

---

## RF-01 — verdict: **amend** (confidence: high)

Re-derived invariant from source (manager.py:690-741 re-read this session): the claim
covers entry; `finalized` is written by jobs/active_job.py:2034-2035 (re-read this
session) — a different module, after `listeners/lifecycle.py` L334's executor hop.
Invariant holds; hardware evidence is dispositive.

**Errors found:**
- **D1 (HIGH, RP-002 step 4):** on an `already_finalized` refusal the stranded reaper
  must MARK the slot (existing tool verified at source:
  `mark_active_job_finalized(finalize_result=None)` sets status=completed,
  finalized=True, and — isinstance-guarded — writes NO fabricated summary). My packet
  said "leave the slot for the next tick" for ALL refusals → a slot whose learning
  record exists but whose status stayed `started` would be re-reaped and re-refused
  **every minute forever**. Amended: branch by reason (`finalize_in_flight` → leave;
  `already_finalized` → mark with finalize_result=None).
- **D8 (LOW, residual, recorded not fixed):** `finalized=True` written by RP-001 is
  in-memory until the next async_save; an HA crash in that window re-runs the body on
  restart (completed_job file already on disk → double ingest). Pre-existing window,
  NOT widened by RP-001 (it previously existed with a larger aperture). Packet gains a
  note: the caller's existing save path persists it; verify save scheduling at
  execution. No design change.
- Positive interaction verified: after D1's amendment, a crash between the
  chokepoint's gate write and the caller's mark is SELF-HEALING (reaper refuses with
  already_finalized → marks slot). This strengthens RP-001+RP-002 as a pair.
- `BaseException` release-on-cancel re-checked: correct (CancelledError must release —
  retryable).
members_added: [] · members_removed: [] · severity_changes: none

## RF-02 — verdict: **uphold** (high)
Attack: "explicit empty selection is legitimate" — re-rejected (disable ≠ delete;
rejection path exists). First-import path preserved in packet. Killed A5-AG-3
confirms rebuild_map unreachable in-repo (FACADE-3 rides free). No changes.

## RF-03 — verdict: **amend** (high)
- **D4 (MEDIUM, RP-006):** "do not cache UNREADABLE" creates a hot-loop hazard: on a
  down SMB mount, estimate() (event-loop path) would re-attempt the blocking read on
  EVERY call. Amended: cache UNREADABLE with a short retry-after (60s monotonic
  backoff) — recovers without hot-looping. Absent-vs-corrupt distinction re-verified
  as detectable (json.JSONDecodeError vs OSError vs FileNotFoundError — three
  separable classes; FileNotFoundError = ABSENT).
- Attack "tolerant readers become crashes": packet's compat wrapper keeps read paths
  None-tolerant — verified against members list; no reader converts to raise. Upheld.
- Under-unification probe: A6-TRK-6 (dock-drift failed write forfeits event) asks a
  related-but-different question (write-side commit ordering) — correctly NOT a
  member (stays RF-29/RP-030 side). No merge.

## RF-04 — verdict: **amend** (high)
- **D2 (MEDIUM, RP-009):** ownership attributes verified AT SOURCE this session:
  `EufyVacuumRoomEntity.__init__` sets `_vacuum_entity_id` and `_map_id`
  (room_entities.py:35-36); switch's room entity inherits (kwargs → base). They are
  PRIVATE attrs — packet amended: add two read-only properties (`vacuum_entity_id`,
  `map_id`) on the base entity rather than reaching for privates from entity_helpers.
- **D3 (MEDIUM, RP-009 step 4):** the closed-set registry sweep cannot remove
  ORPHANS predating the fix (registry entries whose room_id is no longer in stored
  rooms — the very population the prefix sweep caught by accident). Amended: the
  sweep removes the closed set AND enumerates-but-does-not-delete residual entries
  matching the map's singleton ids, reporting them in the service result; orphan
  cleanup is a separate Chris decision (added to the questions list as Q15). This is
  the honest trade — the prefix sweep's "bonus" cleanup was the mechanism of the
  proven cross-vacuum deletion.
- Anti-migration decision re-attacked (mandatory target: "legacy/singleton IDs,
  offline entities, hidden prefix consumers"): grepped for further startswith
  consumers beyond the five named — packet's grep-assertable "no startswith in
  touched sweeps" stands, and a repo-wide `startswith(prefix)` audit is added to
  RP-009's regression block. Offline entities: the registry sweep path (step 4)
  covers not-loaded entities; live-object path covers loaded ones. Upheld with
  amendments; NO migration remains the right call.

## RF-05 — verdict: **uphold** (high). The a/b split re-examined against Pass-2
"one repair covers every member" — it already splits at packet level; DQ-ACT-6's
device-state member correctly carries its own wontfix-or-restore escalation.

## RF-06/RF-07 — verdict: **uphold** (high)
Pass-3 attack on RP-010's future design recorded: the dispatch re-check must be
INSIDE _dispatch_active_phase after the LAST await (not at entry — the four awaits
are the window); cancel single-flight latch must be cleared on cancel failure
(turn-transient-permanent hazard) — both pinned as packet requirements for tranche 2.

## RF-08 — verdict: **uphold** (high)
Pass-3: "refusal strands mid-sequence runs" — already split (refuse-start vs
skip-room-and-advance). New attack found and pinned: step 7's freshness TTL must not
block the FIRST dispatch after HA restart (cache empty, refresh ok=False because
Roborock asleep) — packet gains: when the device is asleep and no refresh has ever
succeeded this boot, fall back to STORED ids WITH a loud warning only when
resolve_live_ids_by_slug's failure is `device_unreachable`, else refuse. This
preserves the ability to wake-by-dispatch. **Flag to Chris (Q16): is wake-by-dispatch
with stored ids acceptable, or refuse until awake?**

## RF-09 — verdict: **amend** (medium-high)
Mandatory target. The Eufy fix depends on fork-coordinator↔HA-device linkage that
remains UNVERIFIED at source (fork code not re-read this review). Amended: RP-026
gains a mandatory pre-step — main agent verifies `EufyCleanCoordinator.device_id`
mapping to the vacuum entity's device registry entry on the LIVE fork version before
Sonnet assignment; if no deterministic linkage exists, the family's Eufy half returns
to synthesis with a fork-PR option (jeppesens mainline). Roborock half stands.
Content-hash rule (EXT-2/ROBORO-3) upheld.

## RF-10 — verdict: **uphold** (high). Display-vs-actuation split is the family's own
core distinction; re-checked POSE-1 repoint direction against corpus guards — stands.

## RF-11 — verdict: **amend — packet split** (high)
- **D14 (MEDIUM):** RP-013 as one packet spans 5 sub-repairs × 4 files — not
  executable as a single bounded Sonnet packet. Split into RP-013a (phase-type
  validity + INF-8), RP-013b (allocated group timing), RP-013c (cumulative completed
  set + finalizer consumption), RP-013d (frozen queue block), RP-013e (recorder
  predicates + bucket scoping). Ordering: a→c→b/d/e.
- Historical-record compatibility re-attacked: rebuilder tolerance of absent keys
  asserted from corpus, NOT re-verified at source → added to RP-013's preconditions
  (main-agent source check of stats_rebuilder's `.get` discipline).
- Interrupted-final-room honesty re-checked: upheld (no synthesis of completion
  without timing evidence).

## RF-12 — verdict: **uphold** (high). A6-VAC-1 severity re-checked under Pass 7:
actuating (dock wash/dry fires mid-run) → HIGH stands.

## RF-13 — verdict: **uphold** (high). GUARD-1 hold-previous semantics re-attacked
(both alternative behaviours produce worse outcomes — recorded in packet). PRE-1's
behaviour change (error-state robot now blocks start) stays Chris-visible.

## RF-14 — verdict: **uphold with note** (high)
Raise-vs-response: raising aborts automations mid-script — the convention table
(Chris Q9) must default automation-common services (start_*, retry) to
response-carrying rather than raise. Noted for RP-031 authoring; not a family defect.

## RF-15 — verdict: **uphold** (high). Killed FURNIS-2 boundary (display-preference
fallbacks allowed) re-confirmed in packet scope.

## RF-16 — verdict: **uphold** (high). RP-003's closed-flag save suppression
re-attacked for "hide errors": suppression logs at WARNING and only after shutdown —
correct by construction.

## RF-17 — verdict: **uphold** (high). Overwrite semantics decision remains Chris Q7;
minimal-fix default confirmed as non-redesigning.

## RF-18 — verdict: **uphold** (high)
Mandatory target. Re-checked each member against the four killed lookalikes' RoomConfig
rule — all members fire on catalog/profile paths, none on stored-room-absent-key
premises. "Legacy stored literals" (Roborock rooms already carrying "Quick") correctly
NOT closed here (CF-3 named). Deliberate framework canonicals ("wide"/1/False/"vacuum")
correctly excluded from the purge.

## RF-19 — verdict: **uphold** (high). Precedence remains a Chris fork (Q2) with both
variants authored — the review confirms neither variant silently decides product
semantics.

## RF-20 — verdict: **uphold** (high).

## RF-21..RF-23, RF-26..RF-34 — verdict: **uphold** (high) after sweep; no Pass-2/3
failures beyond notes already in the catalogue. RF-23's ZONE-4 refusal behaviour
change stays flagged. RF-26's AG-2 regrade (MEDIUM→HIGH) re-confirmed by the
broad-inability consequence.

## RF-24 — verdict: **amend** (high)
- **D5 (HIGH, missing migration):** stored rooms MAY ALREADY contain duplicate slugs
  (created before the uniqueness fix; REC-2 proves the collision path exists today).
  RP-015 as written fixes only the ADMISSION boundary; RF-25's slug-led carry
  (RP-018) over a store with duplicate slugs would collapse identities — the exact
  REC-2 defect reintroduced at the new layer. Amended: RP-015 gains a stored-slug
  dedupe migration (scan every map's rooms; apply the same `_r{room_id}` suffix to
  duplicates; MIGRATION_INSPECTION_GATE: before/after dumps + reversibility note),
  and RP-018 gains `blocked_by: RP-015-migration`. This is the review's most
  important structural catch.

## RF-25 — verdict: **amend** (high) — inherits D5's dependency. "Real Ivy remap
evidence" (mandatory target): RP-018's closure evidence upgraded from "fixtures
possible" to REQUIRING one real Ivy re-map capture before (b) slug-led carry is
declared closed (fixtures for the rest). Rollback for (b): the previous id-led carry
is restorable by revert; storage is not transformed by the carry itself — verified
reasoning recorded.

## RF-35 — verdict: **amend** (high)
- **D6 (MEDIUM):** "trim removal" for leading charge_wait requires
  start_selected_rooms to support a NON-CLEAN phase 0 (arm dock poller instead of
  dispatching a clean) — materially larger than the packet's "phase-type branch"
  phrasing. Amended: RP-021 splits the trim question out; leading-zone support ships
  (dispatch branch exists in phase_runner to model); leading charge_wait becomes a
  Chris option (Q17): (a) implement non-clean phase-0 start, or (b) keep the trim for
  charge_wait only and fix the CARD to show the trim (honest display). Zone-first
  validation fix is independent of that choice and proceeds.

## Batches/deferrals — DOC-ONLY/DEAD-CODE upheld; DEF-2 dissolved (see REVIEW-01 D7).
