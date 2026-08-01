# Gate 4 — Chris Decisions (Q1–Q17)

Drop-in decision set for the Fable synthesis and hostile-review amendments.

## Q1 — Finalize with no stored job

**Decision:** Refuse.

When `_stored_job is None`, return:

```python
{"finalized": False, "reason": "no_active_job_record"}
```

Log a warning with safe job/map context. Do not emit completion events, mark the slot finalized, fabricate a summary, or create a claim-less fallback. A job record that does not exist cannot be finalized.

---

## Q2 — Water-level precedence

**Decision:** Uniform precedence with explicit safety clamps.

Resolve fields in this order:

1. explicit room value;
2. selected profile value;
3. brand/floor default only when absent.

Apply floor safety behavior afterward as an explicit clamp. Carpet may force water off and any required fan behavior, but ordinary hard-floor defaults must not override an explicit profile value.

---

## Q3 — Granite/concrete water default

**Decision:** Use the brand’s normal hard-floor default.

Granite and concrete should use the same brand-specific water default as tile/marble. Do not send `""` or `None`, and do not force water off merely because the floor type is granite or concrete.

---

## Q4 — Slug collision suffix

**Decision:** Approve `_r{room_id}` for collisions only.

Preserve the unsuffixed slug for the lowest stable room ID and suffix only colliding siblings. Do not rename non-colliding rooms.

Historical duplicate-slug migration must use the same rule and record an explicit before/after manifest:

```yaml
map_id:
room_id:
old_slug:
new_slug:
reason: duplicate_slug_migration
```

Rollback must restore `old_slug` from the manifest; it must not infer rollback by stripping the suffix.

---

## Q5 — Newly discovered room enablement

**Decision:** Confirm intended behavior.

- First map import: enable all discovered rooms.
- Incremental discovery/reconciliation: add genuinely new rooms disabled and unconfirmed.

Do not silently insert newly discovered rooms into an existing cleaning queue. The user must review and explicitly enable them.

---

## Q6 — Stale `trouble_rooms` markers

**Decision:** Add a rebuilder for stale markers.

Add rebuild support for stale `trouble_rooms` markers from archived job evidence, with correct map scoping. Keep the existing live path for current markers unchanged.

The rebuilder exists to recalculate or clear historical markers that cannot self-heal after a room is no longer queued.

---

## Q7 — `overwrite_theme` semantics

**Decision:** Draft-over-target.

`overwrite_theme` must apply the current draft over the selected target theme. The target is the base and the draft supplies the user’s edits.

Refuse when no valid draft or target can be resolved. Never substitute the active theme as the source and never overwrite the target with an empty payload. Preserve provenance rules and recompute draft state after the write.

---

## Q8 — `repairs.py`

**Decision:** Delete the unreachable repair flow.

Remove the dead repair infrastructure. Reintroduce `repairs.py` only when a concrete repair issue exists with a complete create, update, dismiss, and test lifecycle.

---

## Q9 — Service failure convention

**Decision:** Use class-based failure behavior.

For automation-common operational services, return structured failure responses so scripts can inspect and branch:

```yaml
success: false
reason: ...
```

Use `ServiceValidationError` for invalid caller input and `HomeAssistantError` for internal failures on administrative or destructive configuration mutations.

No service may silently drop a refusal or return a success-shaped response after failure. Callers must branch on explicit result flags, not reason-string matching.

---

## Q10 — `setup_reject_rooms`

**Decision:** Map-scope it and add reversal.

`setup_reject_rooms` must require explicit map scoping and use the same protection and confirmation standards as other destructive setup actions.

Add a corresponding un-reject service. Rejection must not apply across maps or require direct storage editing to reverse.

---

## Q11 — Edge-mopping control removal

**Decision:** Roborock-only removal.

The removal applies only to Roborock. Other brands retain the control when their adapter declares support.

Audit CF-9 for accidental global scope expansion. Frontend visibility must be driven by the per-brand capability declaration, not a product-wide hardcoded exclusion.

---

## Q12 — Eufy zone repeat ceiling

**Decision:** Unsupported and unsurfaced until verified.

Do not infer a Eufy zone-repeat ceiling from room passes. The Eufy adapter should declare zone repeats unsupported or omit `zone_passes_max`, and the backend/card must not expose a repeat control.

Reject or normalize unsolicited Eufy zone `clean_times > 1`. If zone repetition is implemented and verified later, add an independently validated declaration and enforce it consistently.

---

## Q13 — Two-Eufy hardware run

**Decision:** Cannot be performed with current hardware.

Chris does not own an Omni E28. Correct the hardware inventory and remove any claim that this device is available.

RF-09’s multi-Eufy closure remains hardware-unsatisfied. Use source verification plus single-device regression testing, and leave the multi-device proof open for future hardware or another authorized tester. Do not fabricate closure.

---

## Q14 — Mid-job recharge capture

**Decision:** Simulation plus source verification.

Do not require a staged low-battery hardware run. The condition is rare with the current systems, batteries are healthy, and deliberately forcing it would add battery wear for little value.

Validate charging→not-charging transitions and tracker resume behavior with deterministic tests, then verify that production listeners supply equivalent state transitions. Hardware remains optional only if parity cannot be established.

---

## Q15 — Historical orphan registry entries

**Decision:** Report only; never auto-delete.

Historical orphan candidates may be identified and reported, but they must not be deleted automatically.

Exact cleanup is allowed only when ownership can be reconstructed from current structured data. Unknown or old-looking entries remain untouched for manual review or a future explicit cleanup workflow.

---

## Q16 — Sleeping/unreachable Roborock dispatch

**Decision:** Refuse until awake and freshly resolved.

When live room resolution cannot be obtained because the Roborock is asleep or unreachable, refuse dispatch. Do not send stored segment IDs as a wake attempt.

Return a user-visible reason directing the user to physically wake the robot or wait for the upstream integration to reconnect, then retry. Once live refresh succeeds, resolve against the current map and dispatch normally.

---

## Q17 — Leading `charge_wait`

**Decision:** Unsupported; do not add non-clean phase-0 engine behavior.

A leading `charge_wait` is pointless in the normal model because the robot begins docked and charging. Do not implement a substantial new state-machine path for it.

Reject or explicitly normalize the step during plan validation. The card must not display it as though it will execute; show a clear validation message or omit it after explicit normalization.

Zone-first support remains valid and proceeds independently.

---

# Authorization Summary

- Q1 and Q16 unblock Waves 0–1.
- Q2–Q15 and Q17 govern later packet authoring and hardware gates.
- These decisions supersede recommendations or ambiguous alternatives in the original synthesis and hostile-review documents.
- Product semantics stop here: implementation agents must not reinterpret these decisions.
