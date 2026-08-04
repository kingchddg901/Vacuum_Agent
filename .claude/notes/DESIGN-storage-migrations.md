# Storage migrations — the rule, and the escape hatch

**Status: DESIGN, not scheduled.** Chris: "not a build-now item — we build it between
releases, when I'm not doing anything else." Written up 2026-08-04 from a
conversation that started with ChatGPT's maintenance-mode proposal and got
substantially narrowed. Nothing here is implemented except the worked example at
the bottom, which shipped as part of an unrelated fix.

---

## 1. The rule

> **A storage migration must not change the WIRE shape.**
> Change where data lives; keep emitting the identical contract, with the backend
> merging old and new storage before it reaches the card.

Not a style preference — it is the only version that survives both of the
version-skew asymmetries below. Everything else in this document is either
evidence for that rule or the handling of cases where it is not enough.

The corollary is that the card needs no dual-read, no feature detection and no
coordinated release. It never learns the migration happened.

---

## 2. Why: two asymmetries that skew in OPPOSITE directions

### 2a. Python: the backend does not update until a restart

HA imports `custom_components` at startup and Python caches modules in
`sys.modules`. HACS rewriting the files changes nothing in the running process —
the old code keeps executing until HA restarts.

**Exception, and it is real here: function-scoped imports.** A module that has not
been imported yet is not in `sys.modules`, so a lazy import resolving for the
first time AFTER an update loads the NEW file into the OLD process. Measured
2026-08-04:

```
166  function-scoped imports across the integration
 26  in core/manager.py alone (several on the dashboard-snapshot path,
     which fires on ordinary card interaction)
 18  learning/external_run.py
 15  mapping/map_source_coordinator.py
```

So "nothing takes effect until restart" is *mostly* true, and where it is false it
fails in the worst way: **partially**. Old `core/manager.py` calling into new
`mapping/map_source.py` is a state neither version was tested in.

### 2b. Frontend: the card CAN update without a restart

The card is a JS bundle served over HTTP, not a Python module. A browser refresh
picks up a new bundle with no restart at all. So the skew reachable without
restarting is:

> **new card → old backend**

which is the reverse of the direction people instinctively guard. A new card
asking an old backend for keys it does not emit yet.

### What the pair implies

| skew | reachable how | guarded by |
|---|---|---|
| old card → new backend | user never hard-refreshes after a restart | wire shape unchanged |
| new card → old backend | user refreshes the browser, no restart | wire shape unchanged |
| partially-updated backend | lazy import resolves post-update, pre-restart | nothing — avoid by not updating mid-run |

Both card skews vanish under one rule. The third is not a migration problem and
cannot be fixed by one; it is a release-note problem (§6).

---

## 3. Invisible vs maintenance mode — the dividing line

ChatGPT's framing was size ("global, lengthy"). Size is the wrong axis. The test
is whether the migration can be expressed as:

> **per-record, order-independent, and idempotent**

A million records that each transform independently can stay invisible. Forty
records whose **relationships** change cannot, because there is no consistent
intermediate state to serve while half of them are rewritten.

| shape | approach |
|---|---|
| per-record, order-independent, idempotent | invisible, no ceremony |
| changes relationships / ownership between records | maintenance mode |

`area_label_anchors` (§7) is firmly the first kind. "Rebuild every persisted
map/profile/queue relationship because the ownership model changed" is the second.

### Lazy vs first-run, for the invisible kind

| | first-run migration | lazy (migrate on write) |
|---|---|---|
| cost | touches every bucket at boot | zero for users who never use the feature |
| risk | a bug there breaks startup | cannot break startup |
| tolerant reader | temporary — droppable a release later | **permanent** — storage stays mixed forever |

Lazy is safer to ship and permanently keeps a legacy branch nobody can retire.
First-run is riskier once, then clean. **Neither is wrong; the choice is whether
you ever want to delete the compatibility code**, and that decision needs
`schema_version` (§5) to be answerable at all.

---

## 4. Maintenance mode — restart-scoped

ChatGPT proposed a maintenance state with a progress screen, a backend that
enforces it, refusals for dispatch and config writes, checkpoint/resume, and the
schema version bumped last. The parts worth keeping:

- **The screen cannot be cosmetic.** A modal saying "please wait" while the
  backend still accepts writes is exactly the silent-failure class this repo has
  been fixing all week — card says one thing, backend does another.
- **Version bumps LAST**, after the migrated data is durable. That is what makes a
  crashed migration replayable rather than ambiguous.
- **Freeze the integration, not the instance.**

### Chris's refinement, which is the important one

> It only happens at a Home Assistant restart. When someone first opens the card
> after installing, instead of a non-functional screen we temporarily show a
> different one.

**Run the migration BEFORE registering anything.** "Close the writers" becomes
"don't open them yet", and most of the mechanism disappears:

| ChatGPT's concern | dissolved by restart-scoping |
|---|---|
| telemetry keeps writing (listeners drive `has_observed_active_lifecycle`, counter samples, dock events, finalization into `learning/`) | listeners are not registered yet — there is no writer |
| a run in flight cannot be refused (already dispatched) | at setup there is no live job, only an `active_job` RECORD, which is just data being migrated |
| gate ~172 registered services without 172 copies of the predicate | do not register them yet — one decision point, structurally enforced |

That is a materially smaller mechanism: the enforcement is **ordering**, not policy.

### What survives the reframe

1. **HA's setup timeout and the event loop.** A minutes-long migration inside
   `async_setup_entry` trips "Setup of eufy_vacuum is taking over 10 seconds", and
   if synchronous it stalls the whole HA startup — the thing we were avoiding. It
   must run in an executor or as a background task, with setup returning promptly.
2. **The screen needs something alive to read.** So it is not "nothing is
   registered" — it is "panel plus one status read are up, everything else is
   closed". That single surface is a deliberate exception: it is the thing that
   must work when nothing else does.
3. **Not registering ≠ refusing.** An automation firing at `homeassistant_started`
   against an unregistered service gets `Service eufy_vacuum.start_selected_rooms
   not found` — an HA-level error with no toast and no explanation. Registering
   the services and refusing with `migration_in_progress` routes through the
   existing `SERVICE_REASON_KEYS` / `showServiceRefusalToast` path and yields a
   sentence. Same enforcement, better failure. This is the one place the
   registration-seam wrapper is still needed — one wrapper, not 172 edits, and the
   service-parity gate should be extended to prove nothing bypasses it.
4. **A static screen hides a hung migration.** Chris: "doesn't even have to have an
   update." Agreed on progress bars — but with no signal at all, wedged and slow
   are indistinguishable forever. A start timestamp or one incrementing counter is
   enough, and is the difference between "working" and a permanent mystery.
5. **Rerunnability is a requirement on the author, not a property.** The
   enforceable version: a unit must be a pure `old shape -> new shape` transform
   that does NOT destroy its input until the version bump. A unit that deletes as
   it goes is not rerunnable. Checkable at review; not checkable at runtime.

---

## 5. Prerequisite: `schema_version`

There is no `schema_version` in the store today. "Schema 12 -> 13" has nothing to
count from, so none of §4 is expressible and §3's "droppable a release later"
cannot be decided.

It is small, and worth landing on its own the next time storage is touched —
independently of whether maintenance mode is ever built.

---

## 6. Release note wording

The blunt disclaimer is correct and buys a genuine simplification: it removes the
requirement for new code to correctly interpret an **in-flight job record written
by an older schema**. That is the expensive compatibility case — otherwise every
migration must be reversible-in-meaning for live records, not just stored ones.

Two corrections to the obvious phrasing:

- **Name the restart, not the update.** A HACS update writes files and is inert
  until HA restarts. The dangerous moment is the restart — which also happens for
  reasons unrelated to Vacuum Agent (HA core updates, add-on installs, reloads,
  power blips), so the note protects users more broadly this way.
- **Name the outcome, not the uncertainty.** We know exactly what happens: the run
  cannot arm, the reaper stamps it at `NEVER_STARTED_SECONDS` and force-closes it
  as `interrupted` a grace period later. Bounded, non-destructive, and excluded
  from learning.

> **Don't restart Home Assistant while a clean is running.** The run will be
> recorded as interrupted and excluded from learning — the robot finishes, but
> Vacuum Agent won't have timings for it.

That is a stronger claim than "we cannot guarantee completion" *and* it is already
true today, requiring nothing to be built.

---

## 7. Worked example — A5-FURNIS-4 (shipped, `ed08643`)

The rule in §1 is not hypothetical; it shipped:

- **Storage moved.** `area_label_anchors` was a map-level side-table keyed by
  device room id. It now lives on the room record (`rooms[id]["label_anchor"]`),
  where `rooms/reconciliation.py`'s slug matching carries it through a renumber
  for free (`carried = dict(source)`).
- **Wire unchanged.** `resolve_area_label_anchors()` merges room-record and legacy
  storage and emits the same `{room_id: {pct_x, pct_y}}` under the same key. The
  card was not touched.
- **Migration is lazy**, on the write path only — a read that mutates storage is
  the defect RP-029/POLYGO-3 exists to prevent.
- **Non-destructive.** An entry whose room id does not resolve is LEFT, not
  dropped: the migration cannot distinguish "room deleted" from "room never
  managed", and the card can drag a label on an unmanaged room.

Also the demonstration that the mixed-state question has a sharp answer: that
migration is a synchronous dict rewrite with no `await`, so it is **atomic with
respect to every reader** — HA's loop is single-threaded and nothing else runs
until it returns. There is no window to read across.

**But the reader tolerates both shapes anyway**, deliberately. Atomicity there is
a property of the current implementation, not of the design; someone adds an
`await` inside that helper in six months and the guarantee evaporates with no test
failing.

| migration size | shape | mixed-state window | reader must tolerate both? |
|---|---|---|---|
| single key, one bucket | sync, in the write path | none — atomic in the loop | no, but do it anyway |
| store-wide, many records | must chunk + await | real, seconds to minutes | **mandatory** |

The second row is not a choice: a synchronous store-wide rewrite would block the
event loop for its whole duration, so it must be chunked, and chunking is exactly
what creates the window. **"Big" and "atomic" are mutually exclusive.**

---

## 8. Open questions

1. Lazy or first-run as the default for invisible migrations (§3) — depends on
   whether compatibility code should ever be deletable.
2. Does maintenance mode register-and-refuse, or not register? (§4.3 argues
   register-and-refuse; it costs one wrapper.)
3. What is the single status surface that stays up? (§4.2)
4. Where does `schema_version` live — per config entry, or per vacuum? Per-vacuum
   allows partial migration; per-entry is simpler and probably right.

## 9. Rejected

- **Card dual-reads old and new keys during a transition window.** The window is
  not bounded — it is "until every user hard-refreshes", which is unobservable.
  Keeping the wire shape removes the card from the problem entirely.
- **Sizing maintenance mode by record count.** The axis is relational vs
  per-record (§3), not big vs small.
- **A cosmetic "please wait" screen.** If the backend does not enforce it, a
  second dashboard or an automation writes straight through it.
