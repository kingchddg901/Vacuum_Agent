# Recorder-derived run corpus

**LOCAL ONLY. Never commit anything under this directory.** These are one
household's real device telemetry — room names, cleaning times, when the house
was occupied. The repo is public and in the HACS default store. `.claude/` is
git-ignored; keep it that way. Only the TOOLS are committed
(`tests/replay/harvest.py`, `refocus.py`).

Lives here, one level ABOVE `harvest/`, because re-running the harvester
`rm -rf`s that directory — an earlier copy of this file was lost that way.

```
harvest/     55 runs, truth-vs-recorded + flags   (python -m tests.replay.harvest ...)
focus-*/     per-lens cuts of the above           (python -m tests.replay.refocus --lens X ...)
eject/       arbitrary windows, no job record     (--window START END --match ivy)
```

## Calibration — check this before trusting anything

`job_2026-08-04T19-37-52` had its true numbers established BY HAND, off the
recorder, before the harvester existed:

```
parent 510 s / 8 m²    phase0 120 s / 2 m²    phase2 390 s / 6 m²
```

Re-run this check after ANY harvester change. It caught three of my own bugs,
including the harvester reproducing the very quantum loss it was built to detect.

## READ THE FLAGS BEFORE THE DELTAS

A raw `truth - recorded` gap is not automatically a defect.

| flag | meaning |
|---|---|
| `area_likely_learned_fallback` | `phase_runner` substitutes the room's LEARNED area when the within-phase delta is ~0. BY DESIGN. |
| `run_never_advanced_counters` | The run did not clean; both figures are trivially 0. |
| `zero_second_observed_room` | **live:PHASE-ATTR-1** — a fabricated zero admitted to learning as an observation. |

`job_2026-07-26T13-03-41` is the worked example of the first: a 2m40s run whose
area counter never moved, truth correctly 0.0, recorded 7.0 — the learned value
doing its job. Reading that as "over-credited by 7 m²" files a feature as a bug.
My first pass did exactly that.

## THIS IS A TESTING CORPUS, NOT A USAGE CORPUS (Chris, 2026-08-04)

Valid for: **"did the code compute the right number from these inputs?"** Every
run is measured against the recorder independently of anyone's intent, which is
how live:PHASE-ATTR-1 was proven.

NOT valid for: **"what do runs typically look like?"** These are a maintainer
stress-testing phased dispatch — *"I am using phased jobs a lot right now
because of testing; my house is in general a bad corpus for learning."* Aborted
partials are in here (kitchen wall ranges 30 s to 460 s), grouped runs are
over-represented, and the learning store was CLEARED 2026-08-03. Do not draw
distributional conclusions, and do not read a room's sample spread as natural
variance.

**THE INVERSION WORTH REMEMBERING:** a learning-convention defect matters MORE
for a normal user than for this corpus, and is LESS detectable here. Someone who
runs the same rooms the same way every week converges onto a stable number
carrying whatever bias exists, with a High confidence chip on it and no way to
notice. This corpus is too noisy to converge on anything, so bias hides in the
spread. Same builder-is-not-the-user pattern as always, showing up in the data
layer instead of the UI.

**CONSEQUENCE FOR METHOD:** a CONTROLLED pair — same room, same settings, one
variable (e.g. solo vs grouped dispatch) — is worth more than statistics over
this corpus. n=1 controlled can discriminate hypotheses that n=40 observational
cannot.

## Open leads (candidates, NOT findings)

- **`job_2026-08-01T23-23-35`, +360 s** with zero area delta — biggest single
  gap, does not look like the one-quantum signature. Uninvestigated.
- **Ivy under-credits on 6 of 6** vs Alfred's 12 of 41. Roborock's counters are
  shaped differently (0.1 m² steps, no 1 m² quantisation, continuous minutes,
  resets between rooms mid-run) and `_RESET_EPS` was reasoned from Eufy's
  quantum. Uninvestigated.

## THE TRUTH COLUMN HAS A KNOWN HOLE

Reset detection is decrease-based, so a per-job counter reset that lands BETWEEN
two samples is invisible when the counter climbs back above the old floor before
publishing again. `job_2026-08-04T23-01-25`: swept 2 m², area published ONCE at
2.0 against a stale floor of 1.0, no decrease seen, truth reported 1.0 — one
quantum low. **The integration's 2.0 was right and this tool was wrong.**

Biases `truth - recorded` DOWNWARD on sparse-area runs. It cannot invent an
under-credit finding (those need truth high), but it CAN inflate
`area_likely_learned_fallback`. Treat that flag as a candidate, not a verdict.

Found because two independent implementations disagreed — which is the entire
argument for `_progress_total` not importing the production helper.

## Limits

- States + attributes only. No logs, no MQTT frames, no map payloads — for what
  our CODE thought, that is `debug_capture.py`, a different tape.
- Retention is `purge_keep_days`, a USER SETTING (10 is the default, not a
  promise). `recorder:` filters can drop entities silently. This install has NO
  `recorder:` block, so nothing is excluded here.
- Units are detected PER STATE ROW from `state_attributes`, because HA's unit
  preference can change between runs or inside one. This corpus contains no such
  change, so that path is proved by `tests/replay/test_harvest_units.py`, not by
  this data.
