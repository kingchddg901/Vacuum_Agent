# Phased Jobs — full design

**Written 2026-08-02. DESIGN ONLY — no code until Chris signs this.**

Supersedes the wave sketch in `PLAN-phased-jobs-option-b.md` (that file becomes the
sequencing appendix once this is agreed). Rationale lives in
`ARCH-phased-jobs-concept-vs-execution.md` and is not re-argued here.

---

## 1. Vocabulary

Fixed by Chris, 2026-08-02. Used consistently in code, storage, UI and docs.

| term | means |
|---|---|
| **Phased Job** | the whole run the user started. The parent. |
| **Phase** | one step inside it. Ordered, typed, numbered from 0. |
| **Clean phase** | a phase that dispatches cleaning — `room_group` or `zone`. Produces a **job record**. |
| **Break phase** | `charge_wait` or `wait`. Produces a **phase record**, never a job record. |
| **Child** | a clean phase's job record. A job in the full sense. |

A non-phased run is a Phased Job with exactly one phase. **There is no second code path** —
that is the point of the model, and it is what stops phased and atomic behaviour drifting
apart again.

### 1.1 What makes a run phased (Chris, 2026-08-02)

> *"if a job has waits or zone it is a phased job by default"*

**This rule is already implemented and correct** — `planning/run_plan.py`
`_build_steps_phases` collapses to a single atomic clean phase ONLY when there is nothing
but `room_group` dispatch:

```python
# A zone is a real clean phase, so a rooms+zone run (no charge/wait) must STAY
# multi-phase — only collapse to one atomic clean when there is nothing but
# room_group dispatch phases (no breaks AND no zones).
if not any(p.get("phase_type") in _BREAKS or p.get("phase_type") == "zone"
           for p in collapsed):
```

So the CLASSIFICATION was never the broken part. A run with a wait, a charge, or a zone has
always been built as multi-phase; what was missing is that multi-phase never produced
multiple records. This design changes the recording, not the trigger.

Consequences worth stating:

- **Any wait or charge ⇒ Phased Job.** Even `[room] → wait → [room]`.
- **Any zone ⇒ Phased Job**, including a zone-only run — one phase, still a Phased Job,
  which §1's "exactly one phase" case already covers.
- **Leading and trailing breaks are trimmed** before this test (RP-021a / Q17), so
  `[room, wait]` collapses to `[room]` and is atomic. A break only makes a run phased when
  it BRACKETS cleaning.
- More than one `room_group` also forces phased, independent of this rule.

---

## 2. Object model

```
PhasedJob                      phased_job_id, shape, phases[], outcome, aggregate
├─ Phase 0  clean   [kitchen]        -> job record  (a normal completed_job)
├─ Phase 1  break   wait 2m          -> phase record
└─ Phase 2  clean   [entryway,hall]  -> job record  (a normal completed_job)
```

**Every phase gets a record.** Including ones that never ran — see §5. Absence must never
be the way we represent "did not happen", because absence is indistinguishable from "was
never planned", and that ambiguity is what produced the invisible wait.

---

## 3. Identity and learning keys

### 3.1 Instance identity (unique per run, never a learning key)

```
phased_job_id   "pj_2026-08-02T11-15-51"     one per user-initiated run
phase_index     0, 1, 2 …                    ordinal within the run
phase_count     3                            so a truncated run is detectable
```

Every child job record and every phase record carries all three.

### 3.2 Learning identity (repeats across runs — THIS is what teaches)

Chris's rule: *"the group composite key should be Phase Job ID and its internal Phases."*
Read as: **a phase's learning identity is its Phased Job's identity plus its own position
and content** — not the bare room set. `[8+4]` as phase 2 of a known shape is a different
subject from `[8+4]` run standalone, because what preceded it (battery, position, dock
state) differs.

A Phased Job's learning identity has two sources:

```
launched from a saved run profile   ->  profile:<vacuum>:<map>:<profile_name>
ad-hoc (steps set, never saved)     ->  shape:<hash of the phase structure>
```

Saved profiles are keyed by name in `run_profiles[vacuum][map_id]` today. **RESOLVED
(Chris, 2026-08-02): a profile gets a stable internal id; the name becomes a friendly
label.** The learning key uses the id, so renaming a profile keeps its history instead of
forking it.

```
profile:<vacuum>:<map>:<profile_id>      <- learning key, never the name
name                                     <- display only, freely editable
```

Migration: existing profiles are keyed by name only, so each is assigned an id on first
load. `rename_run_profile` becomes a pure label edit; nothing downstream re-keys.

The ad-hoc shape key encodes structure, not just rooms:

```
pj:map:12|p0:group(5)|p1:wait(120)|p2:group(4,8)
```

Room ids sorted within a group so member order does not fork the key. Break parameters
included, because a 2-minute wait and a 20-minute wait are not the same shape.

**This is what fixes the collision.** A flat `[5,8,4]` run keys as
`pj:map:12|p0:group(4,5,8)` and can never again share an identity with
`[5] → wait → [8,4]`.

### 3.3 What each subject learns

| subject | key | teaches |
|---|---|---|
| room | existing per-room key | duration, area, battery — **only from authoritative boundaries** |
| clean phase (group) | phased-job identity + ordinal | composite duration, battery, area, settings, dispatch success |
| zone phase | the zone's own identity | the ZONE only — never rooms (Chris, 2026-08-02) |
| Phased Job | phased-job identity | orchestration cost ONLY — boundary transit |

The Phased Job is an **aggregate for presentation** and a **learner for one narrow thing**.
It must never teach room duration, queue shape, or cleaning overhead — the children
already do, and teaching both double-counts the same work.

---

## 4. The phase record (break phases)

Break phases are not jobs and must not wear a `completed_job` schema.

```json
{
  "record_type": "phase_record",
  "phased_job_id": "pj_2026-08-02T11-15-51",
  "phase_index": 1,
  "phase_count": 3,
  "phase_type": "wait",
  "planned": { "wait_minutes": 2 },
  "actual":  { "started_at": "...", "ended_at": "...", "seconds": 120 },
  "outcome": "held",
  "reason": null
}
```

`planned` differs by type and this is deliberate:

```
wait         { "wait_minutes": 2 }               duration IS planned
charge_wait  { "target_battery_percent": 80 }    TARGET planned, duration is not
```

`outcome` ∈ `held` · `skipped` · `truncated` · `not_started`.

A `charge_wait` to 80 % on a robot already at 85 % is **`skipped`, actual 0** — never
"charging to 80 % took zero minutes". Recording it as a held zero would be the same lie as
the 50/50 allocation.

A break record contributes to the Phased Job's wall-clock and to **nothing else**. Never to
cleaning time, never to learned cleaning overhead.

---

## 5. Lifecycle and cancel propagation

### 5.1 Normal progression

```
dispatch phase N
  ↓ completion hook
finalize phase N  →  child job record (clean) or phase record (break)
  ↓
advance to N+1, dispatch
  ↓ … last phase finalizes …
close the Phased Job  →  parent record
```

Finalizing the outgoing phase happens **at the advance point**, where manager state is
already that phase's queue/payload/resolved_rooms.

### 5.2 Cancel propagates forward — Chris's rule 1

**A cancel at any phase cancels every later phase.** The Phased Job stops; it does not skip
ahead.

```
Phase 0  kitchen              completed        ← untouched, keeps teaching
Phase 1  wait                 held             ← untouched
Phase 2  entryway+hallway     cancelled        ← the phase in flight
Phase 3  bedroom              not_started      ← record written, cause recorded
```

Rules:

- **Earlier phases are immutable.** Already finalized, already learned. A later cancel
  cannot retroactively poison them — this is the single largest win of the model.
- **The in-flight phase** finalizes as `cancelled` with whatever evidence it has. Its
  learning eligibility follows the existing cancelled-job rules.
- **Later phases get records with `outcome: not_started`** and
  `reason: "cancelled_upstream"` plus the index that cancelled. They are written, not
  omitted, so the structure is complete and the parent can show what did not happen.
- **The Phased Job** closes immediately with a mixed outcome.

Failure and interruption propagate identically. Pause does not — a paused phase resumes.

### 5.3 Phased Job outcome — never collapsed

The parent carries an aggregate label **and** the full child list. The label is a summary;
the children are the truth.

```json
"outcome": {
  "status": "partial",
  "phases": [
    {"index": 0, "type": "room_group", "outcome": "completed"},
    {"index": 1, "type": "wait",       "outcome": "held"},
    {"index": 2, "type": "room_group", "outcome": "cancelled"},
    {"index": 3, "type": "room_group", "outcome": "not_started"}
  ]
}
```

Proposed vocabulary — **OPEN, §11.2**: `completed` (all clean phases completed) ·
`partial` (some completed, some not) · `cancelled` (cancelled before any clean phase
completed) · `failed`.

---

## 6. The Phased Job record

An aggregate. **It sums its children; it never re-derives from raw counters.** Re-deriving
is how double-counting gets in.

```json
{
  "record_type": "phased_job",
  "phased_job_id": "pj_2026-08-02T11-15-51",
  "learning_key": "profile:vacuum.alfred:12:Evening tidy",
  "started_at": "...", "ended_at": "...",
  "wall_clock_minutes": 21.0,
  "battery": {"start": 100, "end": 95, "used": 5},
  "children": ["job_2026-08-02T11-15-51", "job_2026-08-02T11-21-41"],
  "phase_records": ["phase_2026-08-02T11-18-16"],
  "aggregate": {
    "cleaning_time_seconds": 870,      // Σ children — never recomputed
    "cleaning_area_m2": 9.0,
    "rooms_cleaned": [5, 8, 4]
  },
  "boundaries": [
    {"after_phase": 0, "seconds": 205, "planned_hold_seconds": 120,
     "transit_seconds": 85}
  ],
  "outcome": { "...": "§5.3" }
}
```

### 6.1 Boundaries — the three gap kinds, finally separated

```
boundary_seconds = child[n].ended_at → child[n+1].started_at
planned_hold     = the break record's actual seconds (0 when no break)
transit          = boundary_seconds − planned_hold
```

Only **transit** is learnable. The planned hold is arithmetic the user chose. Entry and
return stay with the children, where they already are.

For `11-15-51`: boundary 205 s, hold 120 s, transit 85 s — against a kitchen that sits
~30 s from the dock, which is the sanity check that the split is right.

### 6.2 What it makes possible

```
estimate = Σ child estimates + Σ planned holds + Σ learned transit
```

That run estimated **3.61 minutes** and took **21**. No current bucket can produce the
left-hand side.

---

## 7. Learning contract

Stated as rules, because every violation in the current system is a rule that was never
written down.

1. **A room learns only from an authoritative boundary.** One room, one dispatch. Anything
   else is apportionment.
2. **`allocated: true` is binding.** A row so marked never reaches per-room learning as
   observed duration. It exists for presentation and for the phase's own sum.
3. **A group phase teaches the group**, keyed per §3.2 — composite duration, battery, area,
   settings, dispatch success. Never invented member boundaries.
4. **A break teaches nothing.**
5. **The Phased Job teaches transit only.**
6. **Children are independent.** A cancelled phase 2 does not touch phase 0's eligibility.

---

## 8. Storage

```
learning/<vacuum>/jobs/          job_<ts>.json         children (unchanged shape + identity fields)
learning/<vacuum>/phases/        phase_<ts>.json       break records          [NEW]
learning/<vacuum>/phased_jobs/   pj_<ts>.json          parents                [NEW]
```

Children keep their existing directory and shape. Every existing consumer of `jobs/` keeps
working on a per-child basis; what changes is that a phased run writes several. That is why
the parent must land with the children (§10).

---

## 9. Card contract

- **Review** groups by `phased_job_id`. One run = one entry, expandable to its phases. A
  single-phase run renders exactly as today.
- **Live progress** shows the current phase. For a group, all its rooms
  ("Entryway + Hallway") joined with `Intl.ListFormat` — locale grammar, not a `" + "`
  literal.
- **Stall detection is phase-scoped** when member attribution is unavailable: threshold
  from the group's combined estimate, one event per phase, not per pinned member.
- **The Phased Job's outcome** shows the summary label and the per-phase list. A partial run
  must be legible as "kitchen done, the rest cancelled".

---

## 10. Migration

Legacy records are marked `legacy_monolithic: true` and otherwise left alone.

- Kept for display and aggregate metrics.
- Trustworthy totals (battery, area, wall-clock) survive.
- Ambiguous allocated per-room timings are **excluded from room learning**.
- **No modern phased key is assigned**, so legacy runs cannot pollute the new buckets.
- **No child records are manufactured.** Inventing children from insufficient history would
  repeat the exact error being repaired — converting allocation into observation.

---

## 11. Resolved (Chris, 2026-08-02)

**1. Profile identity — friendly name vs id.** A stable internal id is the learning key;
the name is a label. Rename preserves history. Folded into §3.2.

**2. Status vocabulary — agreed.** `completed` · `partial` · `cancelled` · `failed`, per
§5.3.

**3. Ad-hoc Phased Jobs are RECORDED but NOT LEARNED by default.** They appear in the
Phased Job list like any other, but the parent carries `used_for_learning: false` and its
orchestration data teaches nothing until the user opts it in — **reusing the existing
exclude/restore mechanism**, not a new one (`exclude_learning_job` / `restore_learning_job`
already exist and behave exactly this way for ordinary jobs).

Rationale: an ad-hoc shape key is stable but arbitrary. A user who never repeats a
structure would otherwise accumulate one-sample orchestration buckets forever, and a
one-sample bucket presented as learned is the same overconfidence as the 50/50 allocation.

**This restriction is on the PARENT only.** A child of an ad-hoc run is an ordinary job
with an ordinary room key and teaches normally — the concern is orchestration shape, not
room duration. A profile-launched Phased Job's parent learns by default, because it
repeats by construction.

**4. Zone phases teach ZONES ONLY.** A zone has no room identity; it must never contribute
to a room's stats. Folded into §3.3.

## 11b. Still open

Nothing blocking. Two items to settle during implementation, not before:

- Whether a Phased Job whose children all completed but whose parent is ad-hoc should
  surface an "include this run" affordance on the card, or stay service-only.
- Whether `phase_count` alone is enough to detect truncation, or the parent needs an
  explicit `planned_phase_count` for the case where the plan itself was rebuilt mid-run.

---

## 12. Invariants this design must preserve

Binding, from the gpt review. Implementations may be replaced; these may not.

| # | invariant | where it lives here |
|---|---|---|
| 1 | a completed phase credits only its own rooms | structural — a child's queue block IS its phase |
| 2 | archived completed ids agree with the finalized child | structural — one child, one completion |
| 3 | one child cannot inherit another's counters | per-child battery/timestamps at finalize |
| 4 | allocation never consumed as observed per-room timing | §7 rule 2 |
| 5 | parent aggregation never double-counts | §6 — sums children, never re-derives |
| 6 | a completed child survives a later cancellation | §5.2 |
| 7 | a wait/charge cannot contaminate cleaning overhead | §4 — break records touch wall-clock only |
| 8 | flat 3-room ≠ `[room] → wait → [2 rooms]` | §3.2 — the shape key |

Six become structural. **That is the argument for the design and the reason to be
sceptical of it** — structural claims still need reproducers, and every existing reproducer
gets redirected here rather than retired.
