# 06 — Review Panel

The **Learning Review** panel lets you inspect every cleaning run the integration has recorded, understand why a run was or was not used for learning, and manually exclude or restore individual jobs. This matters because the integration's time estimates are built from historical run data — if a bad run is included, it skews future estimates.

The panel has two subtabs:

- **Learning History** — the full list of recorded runs, plus the stats, filters, and Profile Matcher (covered first, below).
- **External Jobs** — runs started from your robot's own app rather than from this card. These need a quick review to confirm which rooms they cleaned before the integration can learn from them. When any are waiting, the subtab shows a count, e.g. **External Jobs (2)**. See [Reviewing app-started runs](#reviewing-app-started-runs).

---

## Opening the review panel

The Learning Review panel is a dedicated view inside the card. Navigate to it through the card's view selector, then pick the **Learning History** or **External Jobs** subtab at the top.

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
| **Origin** | All Origins / External / Dispatched. **External** runs were started from your robot's own app; **Dispatched** runs were started by this integration. |
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
| **Cleaning Passes** | Fixed at 1 Pass or 2 Passes. (Unlike the room editor, the matcher does not expand to a vacuum's higher pass counts.) |
| **Edge Mopping** | On or Off. Only shown when the selected Cleaning Mode involves mopping. |

The pass and mode choices follow your vacuum's own vocabulary, so the exact options vary by model.

!!! note "Roborock (S6): no per-room cleaning mode"

    The S6 doesn't expose a per-room cleaning mode, so the **Cleaning Mode** field (and the mopping-only **Water Level** and **Edge Mopping** fields) may not appear for it.

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
| **External** | The run was started from your robot's own app rather than from this card. This is its own neutral flag — it is not a sanity or learning verdict. |
| **Suggested Exclude** | The integration has flagged this job as a candidate for exclusion. |
| Non-"completed" status | The job did not finish normally (e.g. Canceled, Failed, Interrupted). |
| **Sanity Failed** | The job failed an internal data-quality check. External runs never show this badge — being externally captured is not a data-quality failure. |
| **Recharge** | A mid-job battery recharge was observed during this run. |
| **Single Room** | The job covered only one room. |
| **Multi Room** | The job covered more than one room. |
| **Room Mismatch** | On a dispatched run, the robot's live room signal disagreed with the room the run was assigned for part of the clean. The run is flagged for review — the assignment is kept, never silently overridden. Open the run to check which room was actually cleaned. |

### Key-value grid

Each card shows the following fields:

| Field | Meaning |
|-------|---------|
| **Rooms** | The room slugs covered in this job. |
| **Zones** | The saved [zone(s)](04a-zones.md) cleaned during this run, shown when the job included a [zone step](04a-zones.md#add-a-zone-to-a-run-a-zone-step). Lists the zone name(s); a multi-zone step also shows the count. |
| **Area Cleaned** | The floor area cleaned this run, in m². Shown when the run recorded a cleaned area — external (app-started) runs now carry this for both single- and multi-room cleans. |
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
| **Custom…** | Reveals a free-text field so you can record your own reason instead of a preset. |

The default reason is "Manual Test Run". Selecting **Custom…** opens a text box — type your reason there before excluding. Click **Exclude** to confirm. The button shows "Working..." while the action is in progress and is disabled to prevent double-clicks.

### Restoring a job

If a job card has a **Restore** button, the job was previously excluded. Click **Restore** to include it in learning again. The button shows "Working..." while the action is in progress.

After excluding or restoring a job, the history snapshot is automatically re-fetched and the job list updates to reflect the change.

---

## Reviewing app-started runs

When you start a clean from your robot's own app instead of from this card, the integration records the run but cannot be sure which rooms it covered or what settings each room used. These runs land on the **External Jobs** subtab and wait for a quick review. Once you confirm them, they feed the learning model just like card-started runs.

### The pending list

Each waiting run appears as a card showing roughly when it ran, its total cleaned area, and how many segments were detected. Two buttons sit on the card:

- **Review** — opens the two-step review wizard for that run.
- **Discard** — drops the run entirely. Use this for a run you don't want to keep (a quick test, a mis-detection). Discarding cannot be undone.

If nothing is waiting, the subtab shows a short message telling you to start a clean from the app and check back.

### Step 1 — How many rooms?

The robot reports its path as a series of segments. The integration's best guess at the room boundaries is shown, but it isn't always right — a single room can look like two, or two rooms can blur into one. Step 1 lets you correct the room count before naming anything.

You have two ways to fix the split, and you can mix them freely:

- **Room count stepper** — at the top, a **Rooms** counter with **−** and **+** buttons. Press **+** to ask for one more room or **−** for one fewer; the integration re-segments the run on the spot and redraws the list. You can't go below one room, and you can't go past the number of boundaries the run actually contains.
- **Split here / Merge up** — each detected room is listed in order with a one-line summary (area, time, mode, passes). The buttons say what they *do*:
  - **↥ Merge up** — folds this room into the one above it (you decided the boundary was spurious).
  - **↳ Split here** — appears inside a room when the integration spotted a possible boundary it didn't act on. Click it to break the room in two at that point. A boundary the integration is unsure about is labelled **· uncertain** so you know it's a softer guess.

Every change is applied by re-segmenting on the server, so the room summaries always reflect the current split. While a re-segment is in flight the controls are briefly disabled. If the run can't be split any finer, a short note explains that the count was capped.

When the rooms look right, click **Next: name rooms →**.

> **Older runs:** runs recorded before this feature was added don't carry the detail needed to re-split them. For those, Step 1 falls back to a simpler merge-only view — you can still merge over-split segments together, just not re-split or set an exact count.

### Step 2 — Name each room

Step 2 shows one panel per room (in cleaning order) so you can identify it and correct its settings.

| Field | What it does |
|-------|--------------|
| **Which room?** | Pick the room this segment belongs to. The integration's top suggestions appear as chips (with their learned area, when known). If the right room isn't shown, use the **… pick another room** dropdown to choose from every room on that map. |
| **Mode** | Vacuum, Vac & Mop, or Mop — when your vacuum exposes a per-room mode. Some vacuums (e.g. Roborock S6) don't, so this field may be absent. |
| **Passes** | Choose 1× or 2×. This field is always 1×/2×; it does not vary by vacuum. |
| **Suction** | Suction level, using your vacuum's available options. |
| **Cleaning Path** | Cleaning path / intensity, using your vacuum's available options. |
| **Water** | Water level. Only shown when the mode involves mopping. |
| **Edge mop?** | On or Off. This isn't detected from an app-started run, so set it yourself. |

The mode, passes, and per-setting options come straight from your vacuum's own vocabulary — the same choices you'd see in the room editor — and whatever the integration captured from the run is pre-selected, so most rooms only need a confirmation. The dropdown of all rooms is pinned to a dark, readable style so the list stays legible.

If a picked room's area looks very different from what was actually cleaned, the wizard warns you at the bottom: *"N rooms don't match the picked area — re-pick, or keep anyway."* Either re-pick the room or, if you're confident, click **Keep anyway** to confirm regardless.

Click **Confirm** to save. The button shows "Saving…" while it works. You must pick a room for every panel first. Use **← Back** to return to Step 1, or **Cancel** to close without saving. Once confirmed, the run leaves the pending list and the count on the subtab drops.
