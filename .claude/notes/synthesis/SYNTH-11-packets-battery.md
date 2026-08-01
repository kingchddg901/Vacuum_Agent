# Tranche-3 Packets — RF-36: battery / charge estimation (RP-042..RP-045)

**Provenance is different from every other family in this campaign, and that is
the point.** RF-01..RF-35 came from 17 hostile audits. These four came from
watching one charge cycle on 2026-08-01 while Ivy sat on a `charge_wait` phase —
because **`battery/` has ZERO findings across all twelve audit runs.** It was
never audited. 2,100 lines, no coverage, and four defects surfaced in twenty
minutes of looking.

That is the headline finding. The packets below are worth landing, but the
coverage gap they expose is worth more: see the closing note.

Evidence throughout is the LIVE production store
(`.storage/eufy_vacuum.storage`, both vacuums), not reasoning about the code.

---

## RP-042 — An unreadable battery must not be reported as 0 % (RF-36 part 1)

```yaml
packet_id: RP-042
family_id: RF-36
finding_ids: ["live:BAT-1"]
severity: HIGH
files: [custom_components/eufy_vacuum/core/charging.py,
  custom_components/eufy_vacuum/battery/manager.py, tests/]
symbols: [get_battery_level, _update_cycles drain accumulator]
problem: >
  get_battery_level returns a hard 0 when the battery is UNREADABLE. The
  adapter's battery sensor going unavailable/unknown makes _safe_int(state, -1)
  return -1, which falls through to the vacuum entity, whose missing
  battery_level attribute then defaults to 0 (charging.py:56-64). A dropout is
  therefore indistinguishable from a flat pack — and 0 is the most damaging
  value in the domain, because every consumer treats it as "empty".

  This is RP-006's defect class exactly (read_json's lying default, repaired to
  a tri-state) in a different file. The signature `-> int` cannot express
  "unknown", so it invents a reading.
evidence_live: >
  Both vacuums' session_history_recent contain physically impossible rows:
  Ivy 98 -> 0 in 2.57 min, Alfred 100 -> 0 in 17.58 / 24.84 / 112.57 / 573.93
  min. A pack cannot shed 98 points in 150 seconds.

  The damage is NOT confined to the history ring. battery/manager.py's cycle
  accounting runs on every negative delta:
      if raw_delta < 0: cumulative_drain_pct += -raw_delta
                        cycles = cumulative_drain_pct / 100.0
  so each dropout books ~1.0 phantom cycle. LIVE VALUES:
      Alfred  cycles = 5.41, of which >= 4.0 are phantom (4 visible dropouts)
      Ivy     cycles = 2.53, of which >= 1.98 are phantom (2 visible dropouts)
  Alfred's true figure is ~1.4. The counter is inflated ~285 %.

  ">=" is load-bearing: the ring holds only the recent 50 sessions, but
  cumulative_drain_pct is MONOTONIC and has no rebuild path. Dropouts that have
  rotated out of the ring are still baked into the total and are no longer
  visible. The numbers above are LOWER BOUNDS. This is the Audit-#2 lesson
  repeating — an accumulator outside the rebuild path takes permanent damage.
required_behavior: >
  (1) get_battery_level gains an explicit UNKNOWN result (None, or a tri-state
  mirroring RP-006 — pick one and use it at every call site). It must never
  return a number it did not read.
  (2) Every consumer decides explicitly. The drain accumulator and the session
  recorder SKIP an unknown sample rather than treating it as a reading; a
  skipped sample is a gap, not a delta.
  (3) A one-shot repair pass for the existing corruption: recompute
  cumulative_drain_pct from the session ring, discarding rows whose end_battery
  is 0 with a start_battery above a plausible-drain threshold, and record that
  the pre-repair value is a floor (older damage is unrecoverable). Do NOT
  silently zero it — the user has a number on a card today and it must change
  visibly, with a reason.
prohibited_changes: >
  No substring/heuristic fallback for the battery reading (the sibling
  is_charging deliberately refuses one — charging.py:67-75 — and the same
  reasoning applies).
rollback_plan: 3 commits (tri-state + call sites; consumer decisions; repair pass).
reproducer_script: NEW _proof_battery_unknown.py — battery sensor unavailable +
  vacuum attribute absent: reading (before 0 / after unknown); a dropout sample
  through the drain accumulator (before +98 pts / after skipped).
expected_before: ["level=0 on an unreadable sensor", "phantom drain +98"]
expected_after: ["level=unknown", "sample skipped, drain unchanged"]
tests_to_add_or_modify: dropout matrix (sensor unavailable / unknown / absent,
  attribute present / absent); accumulator skip; repair-pass idempotence.
superseded_tests: any test asserting get_battery_level returns 0 for a missing
  entity — that IS the defect; update with the decision in the docstring.
broader_gates: full suite.
hardware_gate: none (SOURCE_DECIDABLE) — the live store is already the evidence.
escalation_target: main agent -> Chris
```

---

## RP-043 — The charge ETA must not divide by a frozen rate (RF-36 part 2)

```yaml
packet_id: RP-043
family_id: RF-36
finding_ids: ["live:BAT-2"]
severity: MEDIUM
files: [custom_components/eufy_vacuum/battery/manager.py, tests/]
symbols: [compute_time_to_target_pct precedence, _update_health anchoring]
problem: >
  compute_time_to_target_pct PREFERS the learned baseline (cc/cv_min_per_pct)
  and treats the live zone rate as the degraded fallback. But _update_health
  anchors the baseline only when it is None and NEVER re-anchors, so the
  baseline is frozen at whatever the first qualifying session measured — for
  Alfred, a single session on 2026-06-08. Every Alfred charge ETA since has
  divided by a two-month-old rate, and will keep doing so as the cell ages.

  The fixed baseline is CORRECT for its other job: it is the "when new"
  reference that cc/cv_charge_speed_pct are measured against. One field is
  serving two masters with opposite requirements, and the ETA loses.
evidence_live: >
  Observed 2026-08-01. Ivy has NO baseline (cc/cv null, session_count 0 after 50
  sessions — it never runs below 50 %, so nothing qualifies), so its ETA took the
  zone_rate fallback. First paint quoted a rate carried over from a PREVIOUS
  session and was well off. The first live sample of the current charge
  overwrote rate_high_zone_per_min (manager.py:542-546) and the estimate became
  "very very close" and tracked the taper from there.

  So the fallback converged in ONE sample while the preferred path cannot
  converge at all. The precedence is empirically backwards for this consumer.
required_behavior: >
  Split the two roles. The baseline stays FIXED and keeps feeding
  cc/cv_charge_speed_pct — that is what battery health means and re-anchoring
  would destroy it. compute_time_to_target_pct instead prefers a FRESH zone rate
  and falls back to the baseline when the rate is stale or absent.

  "Fresh" needs a definition in-packet, not left to the implementer: a rate
  observed within this charging session. Sampling is single-interval and can be
  jumpy at a zone boundary or after an HA restart (MAX_RATE_INTERVAL_SEC already
  guards the restart case), so smooth across this session's samples rather than
  trusting the last one alone.
prohibited_changes: >
  Do NOT make the baseline re-anchor. That would fix the ETA by breaking battery
  health, which is the more expensive of the two and cannot be recovered once
  the "when new" reference is lost.
rollback_plan: 1 commit.
reproducer_script: NEW _proof_charge_eta.py — a job on charge_wait with a stale
  baseline and a live zone rate that disagree; assert which one the ETA divides
  by, and that the answer tracks a changing rate.
expected_before: ["eta from frozen baseline", "eta unchanged as live rate moves"]
expected_after: ["eta from fresh session rate", "eta tracks the rate"]
tests_to_add_or_modify: precedence matrix (fresh rate / stale rate / no rate x
  baseline present / absent); smoothing; baseline untouched by ETA changes.
broader_gates: full suite.
hardware_gate: tier 2 ride-along — any charge_wait run; compare the quoted ETA
  against wall-clock. Alfred is the interesting one (it has the frozen baseline).
escalation_target: main agent -> Chris
```

---

## RP-044 — The first ETA of a charge is the least trustworthy one (RF-36 part 3)

```yaml
packet_id: RP-044
family_id: RF-36
finding_ids: ["live:BAT-3"]
severity: LOW
files: [custom_components/eufy_vacuum/battery/manager.py, tests/]
symbols: [compute_time_to_target_pct zone_rate branch]
problem: >
  On the zone_rate path the first ETA of a charge divides by
  rate_high_zone_per_min left over from a PREVIOUS, unrelated charge — which may
  be a 1-minute 99->100 blip (Ivy's stored value was 1.0004 %/min from exactly
  that). The user's first number is systematically the worst one on screen, and
  nothing distinguishes it from the accurate ones that follow.
required_behavior: >
  Treat a carried-over rate as cold-start until THIS session has produced its own
  sample: return minutes=None, source=None. The card already handles that — it
  shows a live wall-clock instead of a fabricated number (the documented
  cold-start behaviour). Reuse that path; do not invent a "provisional" state.
  Depends on RP-043 (same function, same branch) — sequence after it.
rollback_plan: 1 commit, rebases on RP-043.
reproducer_script: extend _proof_charge_eta.py — first call of a new session
  with a stale carried rate.
expected_before: ["first eta from the previous session's rate"]
expected_after: ["first eta None -> wall-clock, then live once sampled"]
tests_to_add_or_modify: first-sample-of-session behaviour; the transition to a
  real number on sample 2.
broader_gates: full suite. hardware_gate: none.
escalation_target: main agent -> Chris
```

---

## RP-045 — Battery health is unreportable on every shipped device (RF-36 part 4)

```yaml
packet_id: RP-045
family_id: RF-36
finding_ids: ["live:BAT-4"]
severity: MEDIUM
files: [custom_components/eufy_vacuum/battery/manager.py,
  custom_components/eufy_vacuum/battery/sensors.py, tests/]
symbols: [_update_health qualifying filter, HEALTH_QUALIFY_START_MAX/END_MIN]
problem: >
  cc_charge_speed_pct, cv_charge_speed_pct and health_pct are computed from
  sessions in the recent-50 ring that start <= 50 % and end >= 90 %. On BOTH
  live vacuums all three read None. Alfred has an anchored baseline from
  2026-06-08 but its anchor session has since rotated out of the ring, so the
  reference survived and the comparison set did not. Ivy never qualifies at all —
  it lives on the dock and its sessions are 100->100, 99->100, 98->98.

  The qualification window describes a discharge pattern these robots do not
  have. A dock-dwelling vacuum can run for months and never once satisfy it, so
  the battery-health sensors ship reading nothing, indefinitely, with no
  indication of why.
evidence_live: >
  vacuum.alfred: baseline anchored (cc 2.6214 / cv 2.6262, 2026-06-08),
    50 sessions, health_pct None, cc_charge_speed_pct None, cv_charge_speed_pct None.
  vacuum.ivy:    baseline empty, 50 sessions, all three None.
required_behavior: >
  Decide and state which of these it is, then implement that:
    (a) the window is too strict -> widen it, and/or accumulate PARTIAL-span
        samples per regime instead of demanding one session spanning both;
    (b) the window is right but the ring is too short -> retain qualifying
        sessions separately from the rolling-50 display ring, so the comparison
        set cannot rotate away from its own anchor;
    (c) the metric is genuinely unavailable for a dock-dwelling device -> the
        sensor must SAY so (an explicit "insufficient data" state plus what
        would satisfy it), not read None forever.
  (b) is at minimum required regardless of the others: a reference outliving its
  comparison set is a bug on any reading.
  Any user-facing string is i18n at creation, all 18 locales.
prohibited_changes: >
  Do not lower the bar so far that health is computed from noise — a 96->100
  session says nothing about pack capacity. Widening must preserve the signal.
rollback_plan: 2 commits (retention/qualification; sensor state + i18n).
reproducer_script: NEW _proof_battery_health.py — a record whose anchor session
  has rotated out of the ring: health None (before) / computed-or-explicit
  (after); plus a dock-dweller history that never qualifies.
expected_before: ["health_pct None with an anchored baseline"]
expected_after: ["health_pct computed, or an explicit insufficient-data state"]
tests_to_add_or_modify: rotation case; dock-dweller case; partial-regime
  accumulation if (a) is chosen.
broader_gates: full suite + npm run check:i18n if a string is added.
hardware_gate: none.
escalation_target: main agent -> Chris
```

---

## The finding behind the findings — `battery/` was never audited

`_open_findings.json` carries 421 open findings across twelve audit runs. The
count from `battery/` is **zero**. Not "low" — zero. The runs were scoped
dispatch+queue, profiles+planning, jobs execution, rooms identity, map-source
lifecycle, listeners, services, core/manager, integration script, learning
consumers, themes, mapping services. `battery/` is in none of them.

Counting findings by top-level directory puts it in company:

| subsystem | lines | open findings |
|---|---:|---:|
| `battery/` | 2,100 | **0** |
| `sensor/` | 1,595 | **0** |
| `dock/` | 475 | 2 |
| `adapters/` | 14,391 | 1 |

`adapters/` is the explainable one — Audit #4 covered the adapter seam but filed
its findings against the CONSUMING call sites, which is consistent with its own
verdict ("the seam is real but ~80 % applied"). `battery/` and `sensor/` have no
such explanation: 3,700 lines between them and nobody has looked.

**Checked 2026-08-01, and the record was wrong in BOTH directions.** `mapping/`
is the subsystem the campaign listed as uncovered, and it is in fact the
best-covered in the repo — audits #11 and #18 between them filed 90 findings
across 6,936 of its 7,419 lines. The only untouched files are
`segmenter_engines.py` (442, the deliberately-excluded empirical-CV segmentor)
and `boundary.py` (40, dead by decision). So the campaign was carrying a
false NEGATIVE on `mapping/` and a false POSITIVE on everything else — which is
the coverage-from-findings trap running in both directions at once, and a second
reason to compute coverage from scopes.

Four defects fell out of twenty minutes of incidental observation, one of them
a permanent-corruption accumulator bug that has already inflated a
user-visible metric by ~285 %. That is not a good yield for careful auditing;
it is the yield of looking at all. The right inference is that the density in
`battery/` is unknown and probably comparable to the audited subsystems,
and these four are the ones that happened to be visible from the outside.

**Recommendation: a proper hostile audit of `battery/` + `sensor/` (+ `dock/`,
which is small and adjacent) before RF-36 is executed**, so the packets are
written against a complete picture rather than being spot-fixes that make the
subsystem look covered — the worst outcome here is a green tick over an
unexamined 3,700 lines. The measured cost of a heavyweight audit is
1.5-2.0M tokens / 30-41 min / 8 agents; these three total ~4,200 lines, so one
run of that size covers all of them.

Executing RP-042 first is still defensible — the accumulator is taking fresh
damage on every dropout, and the audit does not have to finish before the
bleeding stops.

### Coverage claim to correct in the campaign record

`project_hostile_audit_calibration` records coverage as "closed except
`mapping/` (~4,251 lines) + segmentor (excluded, empirical CV)". That is
**wrong**: `battery/` and `sensor/` are equally uncovered and were not on the
exclusion list. The gap was invisible because the ledger counts findings, and a
subsystem nobody audited produces no findings — it reads identically to a clean
one. Any future coverage claim should be computed from the audit SCOPES, not
inferred from where findings landed.

