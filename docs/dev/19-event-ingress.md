# 19 — The Event Ingress Layer

**Scope.** The ten listeners in `listeners/` — everything that turns a Home Assistant state
change or a timer tick into a write. What each one subscribes to, why the three subscription
models differ, and where deduplication actually lives, which is nowhere near here.

Every listener is registered once per config-entry setup, keeps its unsubscribe handles in
`hass.data`, and re-reads the manager from `hass.data` on every event. All of it runs on the
event loop; the only executor hop in the entire reach is the post-job water-amendment file
rewrite.

---

## 1. Three subscription models, and the differences are the design

| listener | subscription | vacuum match |
|---|---|---|
| `lifecycle` | resolved **once** at register, over the union of every vacuum's watch entities | re-resolved **live**, per event |
| `dock_events` | resolved once, gated on `dock_events.enabled` | frozen `{dock_entity: vacuum_id}` captured in the closure |
| `job_metrics` | resolved once, from declared `entities` plus a capability-gated station-water entity | frozen `watch_map` |
| `pause_timeout` | a one-minute `async_track_time_interval` — no entity subscription at all | slots re-enumerated **per tick** |
| `pose_sampler` | a ticker, at each vacuum's own declared interval | per tick |

**`lifecycle` resolves its subscription list once and its vacuum match live, and that asymmetry
is a defect surface rather than a design.** An adapter entity that appears *after* registration —
a re-resolved id, a translation-key rescue, a newly added vacuum — is matched by the handler but
was never subscribed, so the handler never runs for it. The sibling in the same directory freezes
both halves consistently.

> ⚠ **`_common.py` is not the layer's shared substrate, whatever its name suggests.** It exports
> nine functions in three unrelated families — adapter-registry lookups, HA-state predicates, and
> event-payload builders. `pose_sampler.py` and `discovery.py` import **nothing** from it and call
> `adapters/registry.py::get_adapter_config` directly. The payload-builder half is genuinely
> shared; the lookup half is bypassed by half the layer. Its docstring's "every listener can import
> from it" describes availability, not the dependency graph.

---

## 2. Nothing is serialized at ingress

`lifecycle`'s handler is a `@callback` that does one thing: match, then
`hass.async_create_task(_process())`. **One unbounded task per event, with no single-flight
guard.** The task set exists only so teardown can cancel in-flight work.

That is a decision, not an omission, and the alternative is not hypothetical — it exists twice in
sibling files in the same directory. `path_blockers` wraps its `_process` in a single-flight
guard; `pause_timeout` guards overlap with a shared mutable `_tick_state` box.

**Concurrent entrants are expected, and the code says so out loud.** The finalize branch tests
`finalize_result_succeeded` rather than not-`None` precisely because a second entrant will arrive
and must be told apart from a refusal. Safety is pushed all the way down to the exactly-once claim
at the finalize chokepoint — see [06 — How a Run Ends](06-run-end.md).

**The gating pair hold opposite stances.** `path_blockers` is the only listener with both a
single-flight guard and a pre-action re-check before an irreversible cancel. `discovery` has
neither: every trigger spawns an independent task incrementing the same drift counters, and its
only coalescing comes from a module-level `_INFLIGHT` global in a different package
(`rooms/source_refresh.py`).

---

## 3. Where deduplication actually lives

Not at ingress. Three separate downstream layers, each with its own clock:

| what | where the dedup lives | keyed on |
|---|---|---|
| a path block | `active_jobs[…].last_path_block_signature`, written by `planning/run_plan.py` | sha1 of trigger entity + state + affected rooms + rules |
| a stall notification | `active_jobs[…]._stall_notified_room_ids`, written by `jobs/active_job.py` | room id, capped |
| a dock cycle | `dock_events[…].last_*_last_counted_at` — a **persisted** debounce clock | per trigger kind |

**`stall_capture` has no dedup of its own at all.** The only thing protecting it is
`_stall_notified_room_ids`, written by the *detector* on the emit path. A consumer subscribing to
`EVENT_STALL_DETECTED` inherits that protection without owning it.

**There are two mop-wash debounce clocks, and that is correct.** The dedicated listener uses the
persisted `dock_events[…].last_mop_wash_last_counted_at`; `lifecycle`'s inline detector keeps its
own `active_jobs[…].observed_mop_wash_last_at`. The same physical `dock_status` edge drives both —
through the same `is_dock_trigger_edge` helper and the same declared `debounce_seconds.last_mop_wash`
window — so it reads like one event being debounced twice against two reference points.

They count **different populations**, which is what makes two clocks right rather than redundant:

| counter | scope | feeds |
|---|---|---|
| `dock_events[…].mop_wash_count` | every wash, for the life of the install — **not** job-gated | maintenance |
| `active_jobs[…].observed_mop_wash_count` | washes observed while a job is `started`/`paused` | `actual_mop_wash_count`, water consumption, `unexpected_wash_cycles` |

Sharing one clock would be a defect, not a fix: the per-job counter has to start fresh each run, so
consulting the persisted marker would let the *previous* job's wash suppress the new job's first one.

Measured on the reference install 2026-08-23: `dock_events.mop_wash_count` is **207** while every
`observed_mop_wash_count` is **0**. That is the two scopes behaving correctly — washes overwhelmingly
happen at the dock after a run ends, and that vacuum has one mop run in its whole history — not
evidence that either clock is broken.

---

## 4. The completion gate

Four clauses, and each defends against a different observed failure:

1. the brand's declared `task_status` completion value matches, **and**
2. the secondary signal is satisfied, **and**
3. `has_observed_active_lifecycle` is armed, **and**
4. none of `is_job_active` / `_phase_dispatch_pending` / `_cancel_in_flight` suppresses it

**Arming requires the job-active binary only for brands declaring
`completion.require_job_active_clear`.** Requiring it universally would never arm on Eufy, which
declares no `entities.job_active`. Without the extra proof on the brands that do, a Roborock batch
job created while the device still showed the previous run's stale charging state armed at t=0 and
the gate finalized it in about a second.

**`vacuum_docked` is deliberately not a clause.** The vacuum may still be returning when these
signals fire, and requiring docked was stranding `active_job` records.

**`is_job_active` makes the caller declare what an unreadable signal means** rather than
collapsing it in the helper. The recharge guard passes `unavailable_is_active=True`, so a
transient cloud blip during a mid-recharge dock cannot let the gate finalize early and write a
truncated learning sample.

> ✅ **CORRECTED 2026-08-23.** in all FOUR copies — `listeners/lifecycle.py`, two in `core/manager.py`, and
> `planning/run_plan.py` — each of which claimed "every adapter today" is atomic.
> **The sequenced-phase branch is live, and the comments beside it said otherwise.** It reads
> "Atomic jobs — every adapter today — return False here and finalize as before."
> `adapters/roborock/adapter.py` declares `"template": "roborock_segment_clean"` →
> `queue/dispatch_engines.py::RoborockSegmentEngine`, whose `build_phases` emits one phase **per
> room** under `strict_order` — a shipped, user-facing option, present in all 17 locale packs and
> worded "rooms will be cleaned one at a time". Read as written, `jobs/phase_runner.py` and the
> `_phase_dispatch_pending` guard look like unreachable scaffolding.

---

## 5. Edge detection is adapter-vocabulary only

Both dock detectors resolve wash / empty / dry vocabulary from the adapter and carry **no Eufy
literal fallback**. The prior state is recoverable from source and was exactly that. Roborock omits
the whole `dock_events` block, so it resolves an empty trigger set and its detector is inert by
construction — rather than mislabelling Roborock dock states with Eufy words.

**The edge test refuses an unknown prior and refuses `old == new`**, instead of treating any
arrival at a trigger value as a new cycle. The unknown-prior refusal covers restart and reconnect,
where `old_state` is `None` or unavailable; arrival-based detection is named in the source as the
failure that produced the rule.

`dock_events.enabled` used to gate the dedicated listener and not the vocabulary — a partial
guard. `listeners/dock_events.py` reads it with `fallback=False` before subscribing;
`listeners/lifecycle.py`'s inline mop-wash detector read the same
`dock_events.triggers.last_mop_wash` with **no `enabled` check at all**, so a config carrying
`triggers` with `enabled` absent or false still wrote wash observations through the inline path.
The comment already claimed the closed shape, which is what made it hard to see — a guard that
EXISTS reads as complete, and the shorter copy of the predicate is the bug.

Both detectors now resolve `enabled` the same way, with the same `fallback=False`. The fallback
matters as much as the check: the schema default is False, so a brand declaring `triggers` and
never mentioning `enabled` must resolve to OFF — reading it with `fallback=True` would silently
enable every such brand, which is the shape the guard exists to refuse. The reference Eufy adapter
declares `enabled: True` explicitly, so live wash counting is unchanged; Roborock omits the whole
block and is now inert on both paths rather than one.

---

## 6. What a restart clears, and what survives

Three persisted suppression flags, and only two are cleared at load.

`finalize_claimed_at` and `_phase_dispatch_pending` **cannot legitimately survive a restart** — no
finalize is in flight when the process is starting, and a reload leaves no live strict-order
watchdog. Both are cleared unconditionally; an age heuristic was considered and rejected as
neither necessary nor sufficient.

**`_cancel_in_flight` is not cleared**, and nothing in the load path resets it.

`get_active_job()` returns a **normalized copy**, not a live reference. Every mutation therefore
needs an explicit write-back, and the lifecycle listener double-writes the arming flag onto its own
local copy to compensate. No source states why the copy was chosen — both consumers document
working around it.

---

## 7. What one event costs

**`job_metrics` spawns an immediate full-store save per accepted event**, and a
`cleaning_time`/`cleaning_area` change costs two writes, not one — `record_active_job_sensor_value`
and `record_counter_sample` each schedule one. It is a pure `@callback` with no awaits, no
debounce and no dedup.

`pause_timeout` runs three things per slot in a load-bearing order: reconcile the paused flag
against the robot's actual state on **both** edges, then the paused-timeout reap that reads that
flag, then the stranded-`started` reap — reachable only when the previous step did not fire,
because a cancel leaves status ≠ `started`. Its cancel path blocks on `return_to_base` then polls
for up to 30 s.

---

## 8. Common wrong assumptions

| assumption | actually |
|---|---|
| the sequenced-phase branch is dormant seam-work | it ships on Roborock under `strict_order`, a user-facing option in every locale |
| `_common.py` is what the listeners share | two of them import nothing from it |
| a burst of state changes is serialized somewhere in ingress | nothing serializes it; the exactly-once claim at finalize is the guard |
| `dock_events.enabled` turns dock-event counting off | it gates the dedicated listener; the inline detector ignores it |
| one mop-wash event is debounced once | two independent clocks count it, in different stores |
| the pose sampler over-samples a slow brand (per its own comment) | the per-vacuum interval fix was adopted 14 lines below the note that defers it |
| only Eufy declares `room_attribution` (per the same comment) | Roborock declares it too, at `interval_s 5.0` against Eufy's `2.0` |
| `get_active_job()` hands back the stored dict | it is a normalized copy; mutations need explicit write-back |
| all three suppression flags are reset on restart | `_cancel_in_flight` is not |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
