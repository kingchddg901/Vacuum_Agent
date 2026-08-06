# DOC-PASS TRIAGE — findings + intent questions surfaced by the 2026-08-06 reconciliation

**Per Chris's rule: serious questions about how something is SUPPOSED to work get surfaced,
not guessed. This is the standing queue — bug signals become fix tickets, intent questions
get his answer, nothing rots silently. Updated as workflow clusters land.**

## OPEN — needs a fix ticket (code, not docs)

1. **live:FONT-1 remainder — fix landed, NOT confirmed effective.** `41a9735` registers the
   @font-face on the document (the shadow-tree gap was real and is closed; all three bundles
   verified carrying it on the live box). Chris's phone STILL does not render OpenDyslexic
   after force-close + earlier full cache nuke. Status: PARKED by Chris 2026-08-06 ("docs are
   more important"). The shadow-registration gap was necessary-but-not-sufficient, or a
   client layer (WebView font handling? remote-path fetch? something unfound) still
   interposes. Do NOT claim fixed. Next debugging lead when resumed: phone-browser direct
   fetch of /eufy_vacuum/fonts/OpenDyslexic-Regular.woff2 via his EXTERNAL access path, and
   whether the picker's own sample (class .evcc-font-sample-opendyslexic, setting-independent)
   renders the face. A last screenshot is attached in-session (unexamined at park time).
2. **live:RB-ERR-2** — Roborock error enum never enters the `code` field; all five declared
   Roborock tables unreachable at runtime. FINDING-roborock-error-code-carrier.md has the
   chain + fix shape. (Pre-existing, restated here so the queue is complete.)
3. **Config flow shows the Eufy tested model on Roborock installs** — `SUPPORTED_TESTED_MODEL`
   duplicated per-brand; `const.py` imports only Eufy's (orphan 01/02 report, bug signal 3).
4. **`_background_tasks` is a dead ledger** — never appended to anywhere; live phase watchdog
   tasks ride bare `async_create_task` with no shutdown coverage (orphan 30 report, signal 2).
5. **Collapse-path settings loss (UNVERIFIED reachable)** — `_build_steps_phases` collapsing
   adjacent room_group steps rebuilds from `effective_rooms`, discarding per-group settings
   overlays. Needs a reachability check before it becomes a ticket (orphan 30 report, signal 1).
6. **Dead SERVICE_* constants + local redefinition drift** — 4 dead constants in const.py;
   learning/services.py declares 17 service names locally, diverging from the stated
   convention (orphan 01/02 report, signal 2). Cheap hygiene fix.
7. **Stale in-source module docstrings** (queue.py "five services" for 11, etc.) — likely the
   root cause the dev docs drifted; fix the in-file docstrings with the doc pass or they
   re-poison the next transcription (orphan 01/02 report, signal 4).

## QUESTIONS FOR CHRIS — intent, not defects

1. **`discovery.py` trigger semantics:** the doc said auto-discovery fires on "first non-idle
   state"; code fires on entering DOCKED (run-end), plus map-change/reload/timer. Which is the
   intended design? (If docked-on-purpose — rooms are freshest right after a run — say so and
   the doc gets the rationale; if the doc described the real intent, this is a regression.)
2. **Phased-Jobs doc depth:** both dev-jobs auditors and orphan reports left hedged pointers
   instead of documenting the parent/child finalize schema (your rebuild boundary honored).
   Stand pat until the rebuild is declared complete, or want a thin "current shape, subject
   to change" section sooner?
3. *(placeholder — user-guide cluster intent questions land here when the workflow returns;
   any patch section depending on an answer is HELD, not applied.)*

## RESOLVED THIS PASS (for the record)

- RP-047(b): shipped, then REVERTED on live evidence — surviving design now documented in 06.
- The 06/07/30 orphan patches + 5 orphan reports: quarantined in scratchpad/docpass as
  apply-time cross-checks; tree never accepted unverified edits after the reset.
