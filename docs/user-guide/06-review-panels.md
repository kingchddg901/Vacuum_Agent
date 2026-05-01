# 06 — Review Panel

The **Learning Review** panel lets you inspect every cleaning run the integration has recorded, understand why a run was or was not used for learning, and manually exclude or restore individual jobs. This matters because the integration's time estimates are built from historical run data — if a bad run is included, it skews future estimates.

---

## Opening the review panel

The Learning Review panel is a dedicated view inside the card. Navigate to it through the card's view selector.

---

## Overview stats

At the top of the panel, four counters give you a snapshot of what is currently loaded:

| Stat | Meaning |
|------|---------|
| **Jobs** | Number of jobs shown after applying the current filters. |
| **Rooms** | Number of distinct room-run pairs in the filtered set. |
| **Profiles** | Number of distinct cleaning profiles in the filtered set. |
| **Updated** | When the history snapshot was last fetched from the integration. |

---

## Filters

Below the stats, a row of chip-button filters lets you narrow the job list to exactly what you need. Selecting a filter chip immediately re-fetches the history from the integration with the new parameters applied — results update automatically.

| Filter | Options |
|--------|---------|
| **Room** | One chip per room present in the history, plus "All Rooms". |
| **Profile** | One chip per cleaning profile present in the history, plus "All Profiles". Profile chips show a tooltip with the profile subtitle when one is available. |
| **Status** | All Statuses / Completed / Canceled / Failed / Interrupted. |
| **Learning Use** | All Learning Use / Used For Learning / Not Used For Learning. |
| **Sort** | Newest / Highest Outlier / Suggested Exclude / Excluded Only. |

Sorting is applied locally on the card — it does not trigger a new fetch.

### Sort modes explained

- **Newest** — most recent jobs at the top (default).
- **Highest Outlier** — jobs sorted by outlier score, highest first. Useful for finding runs that deviated most from the average.
- **Suggested Exclude** — shows only jobs the integration has flagged as candidates for exclusion, sorted by outlier score.
- **Excluded Only** — shows only jobs you have already manually excluded, sorted by date.

---

## Profile Matcher

The Profile Matcher lets you simulate a room configuration without editing any live room settings. You pick cleaning parameters using chip buttons, and the card tells you which saved learning profiles match exactly.

### Fields

| Field | Options |
|-------|---------|
| **Cleaning Mode** | Matches the available cleaning mode options for your vacuum. |
| **Suction Level** | Matches the available suction level options. |
| **Water Level** | Only shown when the selected Cleaning Mode involves mopping. |
| **Cleaning Path** | Matches the available cleaning intensity/path options. |
| **Cleaning Passes** | 1 Pass or 2 Passes. |
| **Edge Mopping** | On or Off. Only shown when the selected Cleaning Mode involves mopping. |

### How to use it

1. Set the fields to the combination you want to look up.
2. The **Matched Profiles** section updates immediately to show any profiles that are an exact match for those settings.
3. Click a matched profile chip to apply it as a filter — the job list below updates to show only runs that used that profile.
4. Click **Reset Matcher** to return all fields to their defaults.

If no profiles match, the panel says "No exact profile matches for the current settings." Adjust one or more fields until you find a match.

---

## Runs list

The Runs section lists individual cleaning jobs as cards. Each card contains:

### Header

- **Job ID** — the unique identifier for the run.
- **Detail line** — start date and time, duration in minutes, outlier score (if available), battery used (if available), and water used in ml (if available and non-zero).

### Badges

One or more coloured badges can appear on a job card:

| Badge | Meaning |
|-------|---------|
| **Excluded** | This job has been manually excluded from learning. |
| **Suggested Exclude** | The integration has flagged this job as a candidate for exclusion. |
| Non-"completed" status | The job did not finish normally (e.g. Canceled, Failed, Interrupted). |
| **Sanity Failed** | The job failed an internal data-quality check. |
| **Recharge** | A mid-job battery recharge was observed during this run. |
| **Single Room** | The job covered only one room. |
| **Multi Room** | The job covered more than one room. |

### Key-value grid

Each card shows five fields:

| Field | Meaning |
|-------|---------|
| **Rooms** | The room slugs covered in this job. |
| **Scope** | Whether the job was single-room or multi-room (formatted label). |
| **Profile** | The cleaning profile used. A subtitle line appears when the profile has extra detail. |
| **Used For Learning** | Yes or No — whether this job was included in the learning model. |
| **Primary Room** | The primary room associated with this job. |

### Notes

If the integration provides a reason text for the job (an exclude suggestion reason, a learning blocker explanation, a sanity flag, or a cancellation reason), it appears as a plain-text note below the key-value grid.

---

## Excluding and restoring jobs

### Excluding a job

If a job card has an **Exclude** button, you can remove that run from learning. Before clicking Exclude, pick a reason using the **Exclude Reason** chips that appear on the card:

| Reason | When to use it |
|--------|---------------|
| **Short Test Cancel** | You cancelled the run quickly as a test, not a real clean. |
| **Manual Test Run** | You ran the vacuum manually to test something, not as a normal clean. |
| **False Completion** | The vacuum reported completion but did not actually finish. |
| **Bad Room Attribution** | The run was attributed to the wrong room. |
| **Interrupted Run** | The run was cut short by an interruption outside your control. |

The default reason is "Manual Test Run". Click **Exclude** to confirm. The button shows "Working..." while the action is in progress and is disabled to prevent double-clicks.

### Restoring a job

If a job card has a **Restore** button, the job was previously excluded. Click **Restore** to include it in learning again. The button shows "Working..." while the action is in progress.

After excluding or restoring a job, the history snapshot is automatically re-fetched and the job list updates to reflect the change.
