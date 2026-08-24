# 21 — Run Profiles

**Scope.** The saved-run library: what a run profile captures, how applying one reconstructs a
queue, and the ladder that decides where each setting comes from. Room profiles are a different
store with a different scope — [20 — Room Profiles](20-room-profiles.md).

**This store is scoped where room profiles are not.** `data["run_profiles"][vac][map][pid]` has
both a vacuum and a map axis, which is why it appears in `PER_MAP_STORES` and
`VACUUM_KEYED_BUCKETS` — deleted with its map, swept with an orphaned vacuum.

---

## 1. What a save captures

`profiles/manager.py::ProfileManager.save_run_profile` writes identity, membership and — only when
the live queue reports breaks — a step list.

`_snapshot_room_for_run_profile` captures exactly ten keys per room: `room_id`, `name`,
`profile_name`, `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`,
`edge_mopping`, `order`.

`path_type` used to be missing from that list, and it is the only pass-density axis Roborock
declares — the snapshot was the Eufy axis set, so a Roborock user's path setting was neither
captured at save nor restored at apply. It never entered the ladder in §3, while `clean_intensity`,
which Roborock does *not* declare, was captured and restored.

It is captured now, **conditionally**: the key is written only when the room actually holds a
value. This dict is persisted verbatim and never passes through `_finalize_room_update`, so an
unconditional write would put `path_type: ""` into every saved profile on every brand, re-creating
the fossil the one-shot store repair cleared — `""` and `None` stringify to the literal `"None"`
downstream, on units whose adapter has no path axis at all. Empty must stay indistinguishable from
absent; that is what *this brand has no path axis* means (`models/models.py::RoomConfig.as_dict`).

The apply side writes it unconditionally, and the asymmetry is deliberate: that dict *does* go
through `_finalize_room_update`, whose existing guard pops `path_type` when it resolves empty. One
copy of "strip the undeclared axis", not two — the shorter copy is how this class of bug spreads.

Four fields are **persisted and then re-derived**: `room_count`, `room_ids`, `room_names` and
`room_names_label`. `_enrich_saved_run_profile` spreads the stored record and then overwrites all
four from the effective steps, so the persisted copies are never read — and go stale the moment
`set_run_profile_steps` runs, since that updates only `steps` and `updated_at`.

`profile_id` used to be `f"rp_{now:%Y%m%dT%H%M%S}"` — **local** time, one-second resolution, with
no collision check at all. Two saves inside the same second produced the same key and the second
silently **replaced** the first: the user sees one profile where they saved two, and the one they
lost is the one they still had open. A second sounds like enough resolution until you notice the
card can submit a save without a name, which is one click.

Both id spaces now go through `profiles/manager.py::ProfileManager._timestamp_id`, which draws from
**UTC** and suffixes only on collision. UTC for the DST fall-back, one hour a year: a local clock
repeats an entire hour, so two profiles saved sixty minutes apart could collide exactly as if they
were simultaneous. Nothing reads a date back out of these ids — `created_at` and `updated_at` carry
the real timestamps — so the clock is free to be the one that never goes backwards. The trailing
`Z` also means a newly minted id can never equal a pre-existing local-time one.

The room-profile generator had the identical defect and took the identical fix. It was a sibling
copy, and a rule repaired in one copy and not the other is how the unrepaired copy becomes the
bug.

---

## 2. Steps: one normalizer, two policies

Four step types: `room_group`, `charge_wait`, `wait`, `zone`.

`_normalize_steps_reporting` returns `(kept, dropped)` — one implementation serving two policies.
**Reads are tolerant** so a stored profile keeps loading; **writes are strict** and report what
they refused.

Collapse it to the tolerant path for both and a YAML author gets `saved: True` for a profile that
quietly lost its charge stop — after which the robot runs the whole sequence in one go and can
strand mid-run. Give writes their own normalizer and the two can disagree about the same stored
profile.

**A leading zone is refused on write and tolerated on read**, and the refusal deliberately sits
*outside* `_reject_unbracketed_break`. Put it inside and the read path inherits it, so a stored
leading-zone profile stops loading and a legacy profile stops starting.

**`overwrite_run_profile` re-snapshots steps from the current queue** rather than blanking them.
Blanking was the shipped code — itself a fix for a `{**existing}` spread that carried *stale*
steps forward. The failure it caused: a save whose whole intent was a rename or an
`expose_as_button` toggle flattened "Downstairs, wait 30 min, then Upstairs" into a single pass.

---

## 3. Applying one — the ladder

**step field → saved snapshot → live room → adapter `custom_template`.**

The live room is the *last* resort, not the first. Reading straight through to it — the shipped
behaviour — silently replaced every saved setting with the room's current state: the recorded case
is a profile that restored the right rooms in the right order with the wrong settings on all of
them.

**Resolution and authorisation happen before any mutation.** The enabled-flag wipe runs only after
at least one profile room is confirmed to resolve. Wiping first and layering updates afterwards
means a fully-failed apply — every referenced room deleted or renumbered by a re-segment — still
destroys the user's prior selection, with nothing to roll back to.

**A room with no saved snapshot keeps its current settings, and the fact is reported** — in
`unsnapshotted_room_ids` and an INFO log. Inventing values for the missing fields would make "the
right rooms ran with the wrong settings" indistinguishable from a clean apply. The stated
principle: the user gets today's settings, which is recoverable.

---

## 4. Applying writes the queue, not just the rooms

`apply_run_profile` derives `queue_breaks` from the profile's own steps and writes them through
`core/manager.py::EufyVacuumManager.set_queue_breaks` — the replace-all primitive, never assigned
directly here. It also stamps a `queue_source` provenance tag of `{profile_id, stepped, applied_at}`.

Enabling the right rooms in the right order and stopping there was the shipped behaviour, and it
breaks on any path that starts the queue without going back through the profile: a reloaded
dashboard, a second tab, a phone, or an automation that calls `apply_run_profile` and then
`start_cleaning`. All of them ran the profile as one flat pass.

`set_queue_breaks` clamps `after_index` into range and **clears the list entirely** when fewer
than two rooms are enabled.

**`start_run_profile` reads `strict_order` from the stored profile**, with an explicit argument
overriding in either direction. Plumbing it only from the direct service call — the shipped
state — silently discards the saved room order on a path-optimising brand, because the button
entity carries no service data. Roborock declares `honors_clean_order: False`.

The step sequence is stashed in an ephemeral `data["_pending_run_steps"][vac][map]`, popped by the
plan builder on real dispatch and peeked on preflight, with a leak sweep when the start reports
not-started.

> ⚠ `queue_source` is written here and read by **nothing in Python**. `clear_queue` pops it. It is
> a provenance tag for the card, not a control input.

---

## 5. Common wrong assumptions

| assumption | actually |
|---|---|
| a run profile captures the room's full settings | ten keys, and `path_type` — Roborock's only pass-density axis — is not one of them |
| `room_count` / `room_ids` on the stored record are authoritative | they are re-derived from the steps on every read; the stored copies go stale and are never read |
| applying a profile restores settings from the room | the live room is the *last* rung, below the saved snapshot |
| a room missing from the snapshot gets sensible defaults | it keeps its current settings, and says so in `unsnapshotted_room_ids` |
| a failed apply leaves the previous selection alone | it does now — because authorisation was moved ahead of the wipe |
| saving over a profile to rename it leaves its steps alone | only since `overwrite_run_profile` re-snapshotted; blanking flattened multi-phase profiles |
| applying a profile only touches which rooms are enabled | it also writes `queue_breaks`, or a plain Start runs the whole thing flat |
| `queue_source` drives behaviour | nothing in Python reads it |
| two profiles saved quickly get distinct ids | the id is local time to the second, with no collision check |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
