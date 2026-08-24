# 28 — From Records To Statistics

**Scope.** How surviving job records become the learned stores: the key that decides what counts as
"the same clean", what is gated out of an average and what is kept, and why the baselines bucket by
some settings and not others. Which records survive to get here is
[27](27-learning-eligibility.md); how the stores are read back is [29](29-learning-prediction.md).
Room-pair travel time is aggregated here but belongs to
[18 — The Access Graph](18-access-graph.md).

The rebuilder is a **pure re-derivation**. It reads completed-job JSON and writes the learned
stores; it never edits a job record. Every store below can be thrown away and rebuilt, which is
what makes a corrupt derived file recoverable for readers in
[26 §4](26-learning-record-store.md).

---

## 1. The key decides what "the same clean" means

`learning/utils.py::_room_key` builds the room learning key from seven components — the map, the
room's slug, the effective mode, the pass count, whether it is carpet, the clean intensity, and
whether edge mopping was on.

**Settings are in the key, not averaged over.** Two runs of the same room with different pass
counts are not two samples of one thing; they are one sample each of two things. Averaging them
produces a number that describes neither.

Edge mopping earns its place on the same test and the code says so directly: it materially changes
cleaning time, so edge-on and edge-off runs are learned separately. The test for adding a component
is whether it moves the clock, not whether it is a setting.

The key is **shared with the accuracy store** so the two always align. A prediction and the record
of how wrong that prediction was have to be filed under the same name, or the feedback loop in
[29](29-learning-prediction.md) compares unrelated things.

---

## 2. The key is slug-based, and a rename is detected but not applied

The room component of the key is the **slug**, not the room id — a survival from the era when the
slug was the primary identity, which [17 — Room Identity](17-room-identity.md) records as since
demoted to a convenience field.

`rooms/reconciliation.py` does detect renames. It matches a discovered room to an existing one by
id, notices the slug has changed, and emits a `renamed` review carrying both the old and new slug.
That review reaches the card and is rendered to the user.

⚠ **Nothing rekeys the learned stores.** No code path reads the old-slug value back into
`learning/`, and no function moves a room's stats from one key to another. A renamed room therefore
starts from zero samples while its history stays filed under a key nothing will ask for again.

The evidence needed to fix it is already computed and shown to a person; it simply is not consumed.
This is the same failure class as the vacuum-level orphan in
[26 §7](26-learning-record-store.md) — history keyed on a name a user is free to change — at a
finer granularity.

---

## 3. A partial clean loses its time and keeps everything else

`learning/stats_rebuilder.py::_gate_minutes_by_area` compares each sample's cleaned area against
the room's median area and drops the **minutes** of any sample that falls too far off it. A room
that was half-cleaned took half the time, and folding that into the average teaches the estimator
the room is faster than it is.

Three properties make the gate safe rather than merely strict:

- **It gates time only.** Area, battery and water keep every sample. A partial clean is a bad
  sample *of duration* and a perfectly good sample of how much battery the robot uses per square
  metre.
- **It cannot empty the set.** If the gate would exclude everything, it returns all samples
  instead. A gate that can starve its own average is worse than no gate.
- **It abstains when it cannot judge.** With too few area samples to define a median, and for any
  sample with no paired area, everything is kept. The band has to exist before it can exclude.

The count of excluded samples is stored beside the average, so a room whose timing looks thin can
be distinguished from one whose samples were mostly rejected.

---

## 4. Baselines bucket by setting — except area, deliberately

`learning/stats_rebuilder.py::_finalize_setting_buckets` breaks each room's averages out by pass
count and by edge mopping, and each bucket carries a sample count, an average, and a
minimum/maximum/standard-deviation band.

**The band is the point, not the average.** The stated reason is that a consumer should be able to
match within variance rather than against a brittle point mean — a room that always takes eight
minutes and a room that takes between four and twelve both average eight, and only one of them
supports a confident prediction.

Area is **not** bucketed, because area is settings-invariant: a room is the same size whether it
was mopped once or twice. Bucketing it would split one population into several smaller ones and
lose precision for nothing. The rule that decides is whether the setting changes the *quantity*,
not whether it changes the run.

Travel time gets the same band treatment through
`learning/stats_rebuilder.py::_seconds_band`, and is aggregated only from runs whose transit
capture was marked valid. It is stored as **time**, never as coordinates, because raw coordinates
drift between sessions while a travel duration does not.

---

## 5. Bad runs are excluded by the caller, not here

The rebuilder aggregates learning-jobs-only, and the filtering happens **before** aggregation
rather than inside it. Cancelled, failed, interrupted and test jobs stay fully visible in history
and in the CSV exports; they simply never reach the averaging.

That split is why the exports and the learned stores disagree on purpose. A user looking at the
history should see every run; a model should see only the ones that mean something. Reconciling
those two views would require one of them to lie.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| the learned stores are authoritative | they are derived, and `learning/stats_rebuilder.py::rebuild_all` can reproduce every one from the job records |
| renaming a room carries its history | the rename is detected and displayed; nothing rekeys the stores — §2 |
| a partial clean is discarded | only its duration is; area, battery and water are kept — §3 |
| the average is what gets matched | the band is, and a wide band is a real answer about confidence — §4 |
| the CSV and the learned stats should agree | they are deliberately different populations — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
