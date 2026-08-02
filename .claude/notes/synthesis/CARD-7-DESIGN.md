# CARD-7 design — reconciliation review in the setup surface

**Signed off by Chris, 2026-08-02.** This closes CARD-7's `stop_conditions`
("DO NOT IMPLEMENT until Chris signs the pane design"). CARD-7 remains
`blocked_by RP-019` — the backend must ship `plan_token` and embed the reviews first.

## Three corrections to the packet — the design is built on these, not on the packet text

1. **Two review kinds, not four.** `rooms/reconciliation.py` emits exactly `id_changed`
   and `renamed`. A brand-new room is drift's ("drift owns it, no review here", :139) and
   a removed room is `plan_migration`'s `dropped`. The packet's "renamed / id_changed /
   removed / new" describes a set that does not exist.

2. **There is no per-review accept, and there must not be.** The only apply path is
   `reconcile_room(action=migrate)`, which calls `plan_migration` and rebuilds the whole
   room map atomically. `services.yaml` states the rationale: *"A re-segment renumbers
   many rooms at once, so this is one per-map decision."* The packet's "per-review accept"
   contradicts the shipped contract. The surface is a PREVIEW plus ONE decision.

3. **`review_discovered_rooms` has zero consumers anywhere** — not merely no card wiring.
   It is dead code today. RP-019 makes it reachable; CARD-7 consumes it. Same reachability
   class as the card-cancel bypass [[feedback_audit_callsite_reachability]].

## What it is

A banner inside the EXISTING setup room list. No new pane — rooms are already discovered
and surfaced there, and two surfaces for the same objects is how they drift apart
(Chris, 2026-08-01).

**Chris's calls, 2026-08-02:**

| decision | choice |
|---|---|
| Announcement | **Setup banner only.** No repair issue, no persistent notification. |
| Dropped-rooms preview | **Ship without it.** No dry-run; RP-019's scope stays as authored. |
| Stale `plan_token` | **Auto-refresh and re-render**, with a note that the map changed. |

## The surface

### State A — no changes
`has_changes: false` → render nothing. No empty state, no "all good" badge.

### State B — changes pending
A banner above the room list. Two groups, because the kinds are NOT symmetric:

**Renumbered** (`id_changed`) — informational, not a question. The slug matched, so
identity held; this is bookkeeping the system is confident about.
> *3 rooms were renumbered by the robot. Their settings will follow them.*
> Kitchen 5 → 7 · Hallway 2 → 4 · Den 9 → 3

**Renamed** (`renamed`) — the actual ambiguity. Same id, different name: either the user
renamed it in the Eufy app, or the robot re-segmented and that id is now different space.
**The card cannot know, and neither can the backend.**
> *Room 5 is now called "Dining". It was "Kitchen".*

**One decision, two buttons.** Because the backend is map-wide, the renamed entries are
EVIDENCE FOR the decision, not individual toggles. Do not render checkboxes — they would
imply a granularity `reconcile_room` does not have.

> **[ Update saved rooms ]**  → `reconcile_room(action=migrate, plan_token)`
> **[ Dismiss ]**             → `reconcile_room(action=ignore, plan_token)`

Dismiss is not "never ask again": RP-019 clause 3 suppresses identical reviews only until
the discovery snapshot changes. Copy must not promise permanence — "Dismiss", never
"Ignore forever".

### State C — after Update
Render the response. `reconcile_room` already returns `id_remap` and **`dropped`**, so
report what actually happened:
> *Updated 3 rooms. **The Den was removed from this map and its settings were discarded.***

This is not the preview Chris declined — it costs no backend change and is strictly better
than the user discovering it weeks later. If `dropped` is empty, omit the sentence.

## Stale `plan_token`

The card catches `plan_changed`, silently re-runs `discover_rooms`, and re-renders State B
from the fresh reviews with a one-line note: *"The map changed while you were reviewing —
this is the current state."*

Safe because the operation is atomic: a refused migrate applied NOTHING, so there is no
partial state to reconcile. Never auto-confirm the refreshed plan — swapping what the user
is agreeing to is the exact thing `plan_token` exists to prevent.

If the refresh itself fails, fall back to the packet's literal behaviour: render
"the map changed — re-discover" with the button.

## Constraints

- **Every string is i18n at creation, all 18 locales** [[feedback_no_string_without_i18n]].
  Room names and ids interpolate; do not concatenate translated fragments.
- CSS in `src/styles/` only — no inline `<style>`; `check-styles` fails the build on an
  un-tokenized colour [[feedback_styles_in_styles_only]].
- The banner is a READ of `discover_rooms`' response. It must not trigger a discovery on
  render — that would make opening setup mutate state.
- `plan_token` is opaque to the card: hold it, send it back, never parse it.

## Proof

Per the packet: unit tests on the token round-trip binding. Plus, from this design:
the two groups render from the real two kinds; the stale-token path re-renders rather
than dead-ends; `dropped` is reported in State C when non-empty and omitted when empty.
