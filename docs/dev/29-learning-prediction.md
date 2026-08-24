# 29 — Prediction and Accuracy

**Scope.** How the learned stores are read back into an estimate: the five-pass lookup and why it
relaxes in the order it does, what a relaxed match costs, the four terms of the confidence score,
and the loop that feeds a prediction's own error back into its next confidence. What is stored is
[28](28-learning-statistics.md).

`learning/estimator.py` is pure computation. It takes normalized inputs and returns structured
payloads, with no Home Assistant dependency beyond reading the history store — all orchestration
lives outside it. That is what makes its behaviour testable without a running vacuum.

**Numbers are not reproduced here.** The scoring weights, the overhead constants and the staleness
window are all module constants; copying them into prose creates a second copy that drifts. What
follows is the shape and the reason for each term.

---

## 1. Five passes, relaxed cheapest-first

`learning/estimator.py::_find_room_match` looks for the learned entry matching a room's exact
settings, then progressively drops dimensions until something matches:

| pass | drops | why it is dropped at this point |
|---|---|---|
| 1 | nothing — exact match | |
| 2 | clean intensity | smallest effect on cleaning time |
| 3 | is-carpet | approximately constant for a given room |
| 4 | edge mopping | materially changes time — held back this long deliberately |
| 5 | pass count | moves time the most — dropped only as a last resort |

**The order is an effect-size ranking, not an arbitrary sequence.** The dimensions that move the
clock most are held longest, so the first thing sacrificed is the thing whose loss distorts the
answer least. Reordering this would silently make relaxed estimates worse without changing any
threshold.

Two supporting rules keep a relaxed pass honest:

- **Ties break on sample count**, not iteration order. A relaxed pass can match several stored
  entries, and the one with the most observations wins — so the result is deterministic and
  prefers the better-evidenced entry.
- **The intensity comparison routes through the shared canonical helper**
  (`learning/utils.py::_canonical_clean_intensity`), the same one the query-side projection and the
  accuracy recorder use. Three places must agree on what "the same intensity" means, and they agree
  by construction rather than by three matching implementations.

---

## 2. A relaxed match is corrected, not just accepted

Finding a room's timing at the wrong pass count and using it unchanged would report a two-pass
clean as taking one pass worth of time. Instead
`learning/estimator.py::_measured_setting_ratio` reads the per-setting baselines from
[28 §4](28-learning-statistics.md) and derives the **measured** ratio between the bucket that was
wanted and the bucket that was found, then scales the estimate by it.

The ratio is defended three ways, and each guards a different failure:

- a **minimum sample count**, so one freak run cannot define the relationship
- **clamping**, so a ratio derived from thin or noisy data cannot produce an absurd estimate
- **abstention** — with no usable ratio, the scale is simply left alone rather than guessed

This is the difference between "we have no data for this exact setting" and "we have no idea". The
system usually knows how much slower two passes are *for this room*, and using that is better than
either refusing to answer or pretending the settings match.

A relaxed match **also** returns a mismatch flag, which costs confidence in §3. The estimate is
corrected and the reader is told it is less trustworthy — both, not one or the other.

---

## 3. Confidence is a base plus one bonus and three penalties

`learning/estimator.py::_score_room_confidence` produces a 0–1 score:

| term | direction | what it is defending against |
|---|---|---|
| base | learned entries start well above unlearned defaults | a guess should never look like an observation |
| sample bonus | rises with sample count, saturating | one lucky sample is not evidence |
| variance penalty | rises with coefficient of variation | a room that takes 4–12 minutes averages 8 and predicts nothing |
| mismatch penalty | flat, applied on a relaxed match | §2's correction is an inference, not a measurement |
| accuracy penalty | rises with historical drift | §4 |

The **UI breakpoints are derived from these constants, not written beside them** — the sample counts
at which a room reaches medium and high confidence are computed from the bonus curve. Retuning the
curve moves the labels automatically, so the badge a user sees cannot fall out of step with the
score behind it.

Job confidence is the **minimum** across the job's rooms rather than the mean. A queue is only as
predictable as its least-known room, and averaging lets nine well-learned rooms hide one that has
never been cleaned.

`learning/estimator.py::_learning_velocity` reports how fast a room is accumulating evidence, which
is the answer to "will this get better if I keep using it" — a different question from how good the
estimate is now.

---

## 4. The loop: a prediction's error feeds its next confidence

`learning/estimator.py::record_estimate_accuracy` writes what was predicted against what actually
happened, filed under the **same key** the stats use — which is why
[28 §1](28-learning-statistics.md) insists the two key builders are shared.

`learning/estimator.py::_drift_ratio_for_room` reads that history back and converts it into the
accuracy penalty above. A room whose estimates have been consistently wrong reports lower
confidence **even when it has plenty of samples and low variance**, because those two measure
self-consistency and neither can detect being consistently wrong.

That is the only term in the score derived from outcomes rather than from the shape of the stored
data, and it is the one that closes the loop.

`learning/estimator.py::_is_stats_stale` handles the other direction: statistics that have not been
refreshed within the staleness window are flagged, because a room's timing can change for physical
reasons — furniture, a new rug — that no amount of old evidence will reveal.

---

## 5. During the run, the timeline reanchors

An estimate made at dispatch is a prediction about the whole queue.
`learning/estimator.py::reanchor_timeline` rebuilds the remaining timeline from the **actual**
durations of rooms already finished, so a run that started slow does not keep reporting the
original finish time.

`learning/estimator.py::next_room` and the transit lookup fill the gaps between rooms from the
access graph rather than from a flat per-room constant, so the projection accounts for a queue's
travel order and not only its room set.

`learning/estimator.py::_compute_overhead` models what a run costs beyond cleaning — startup, room
boundaries, recharge time proportional to battery used, mop-wash cycles, and the return trip. These
are what make an estimate a finish time rather than a sum of room minutes.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| the fallback ladder relaxes in schema order | it relaxes by effect size, cheapest first — §1 |
| a relaxed match reuses the found entry's minutes | it is scaled by a measured between-bucket ratio — §2 |
| more samples always means higher confidence | variance and historical drift both pull the other way — §3 |
| job confidence averages its rooms | it is the minimum — §3 |
| confidence measures whether the estimate is right | three of its four terms measure self-consistency; only the drift term sees outcomes — §4 |
| the estimate is fixed at dispatch | the timeline reanchors from completed rooms — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
