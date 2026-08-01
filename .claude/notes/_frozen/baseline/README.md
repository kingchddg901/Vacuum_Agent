# Hardware baseline capture — drop files here

**Why:** after fixes land, "it behaves like X" proves only what the repaired build does. Without a
before-picture, every oddity is ambiguous between *we broke it* and *it always did that*. This is
the only Gate 1 item that degrades by waiting.

**Total hands-on time: ~15 minutes.** Two cleaning runs happen in the background.

---

## Phase A — static capture (5 min, no cleaning)

Both files come from one click each. They already contain device, model, firmware/model_family,
adapter config, entity resolution, capabilities, maps, rooms and upkeep — everything the generic
"record your configuration" instruction was asking for.

1. **Settings → Devices & Services → Vacuum Agent → ⋮ → Download diagnostics**
   Save as `alfred-diagnostics-BEFORE.json` here.
2. Repeat for the Roborock/Ivy entry if it is a separate config entry, else the same file covers
   both vacuums. Save as `ivy-diagnostics-BEFORE.json`.

That's Phase A. Nothing to type.

---

## Phase B — one instrumented run per device (~1 hr each, mostly unattended)

The flight recorder turns the run into a small diffable artifact instead of a memory.

For **each** vacuum:

1. Set the **Debug target** select to `Everything (unfiltered)`
   *(entity: `select.<vacuum>_debug_target`)*
2. Turn **Debug capture** switch ON *(`switch.<vacuum>_debug_capture`)*
3. Start a **normal room clean from the card** — two or three rooms is plenty. Let it finish and
   return to the dock.
4. Turn the switch **OFF** — it auto-writes the dump and puts the path in the `last_dump`
   attribute.
5. Copy that file here as `alfred-run-BEFORE.log` / `ivy-run-BEFORE.log`.

One run exercises dispatch → job lifecycle → finalize → room attribution → learning → battery
session → dock events. **270 of the 482 open findings sit on those paths, 86 of them HIGH or
CRITICAL.**

> If a full clean is inconvenient, a single small room still covers dispatch, lifecycle, finalize
> and attribution. Battery-session and dock-event coverage need the return-to-dock.

---

## Phase C — three cheap checks that settle findings without a run (5 min)

These are worth more per minute than anything else here, because each one can **downgrade or kill
an open finding** rather than just observe it.

**C1 — do two of your vacuum entity_ids collide?**
In Developer Tools → States, filter `vacuum.`. Write down every entity_id.
*What it settles:* `DR-SETUP-1` / `EP-2` / `SN-3` (HIGH, entity-registry destruction) need one
vacuum's entity_id to be a prefix of another's plus a map id — e.g. `vacuum.alfred` and
`vacuum.alfred_2`. **If nothing collides, the cross-vacuum half is not reachable on your hardware**
and its priority drops sharply. Record the answer either way.

**C2 — what does Ivy's selected-map entity actually report?**
Developer Tools → States → `select.<ivy>_selected_map`. Note the exact state string.
*What it settles:* `A1-SERVIC-1` (HIGH) and the Roborock half of the prefix collision both depend
on `map_id` being a human-editable NAME. If it reports a name like `Main floor`, both are live —
and a map name containing a space or underscore makes the intra-vacuum collision reachable.

**C3 — does Ivy's diagnostics carry a `roborock_geometry_drift` block?**
Open `ivy-diagnostics-BEFORE.json` and search for `roborock_geometry_drift`.
*What it settles:* `A7-ROBORO-4` (MEDIUM) hangs entirely on the upstream parser's ImageConfig trim
being nonzero — the meta-verifier flagged that the shipped drift diagnostic answers it outright.
Note `present`, and `centre_delta` if it appears.

---

## What you do NOT need to do

- **Don't** hand-record firmware, config or entity lists — Phase A has them.
- **Don't** take screenshots. Almost nothing in scope is a visual finding.
- **Don't** set up the 24 precondition-dependent findings (rename a profile, rebuild a map, delete
  a custom layout). Those need deliberate destructive setup and belong with the packet that
  repairs them, not with a baseline.
- **Don't** try to force an error for the error-latch findings. Errors are captured opportunistically;
  if one happens during Phase B the recorder already has it.

---

## When you're done

Drop the files here and say so. I will:

- record `HARDWARE_BASELINE_GATE` as satisfied in the corpus,
- fold C1–C3's answers into the affected findings (they may re-grade several),
- re-freeze, and present `FABLE INPUT READY`.

> **Note for the flight-recorder dumps:** `DR-DBG-1` is open — dumps carry unredacted, untruncated
> tracebacks. These files stay local and go in `_frozen/baseline/`, which is committed. Skim them
> before you hand them over if anything sensitive appears; the redaction gap is real and unfixed.
