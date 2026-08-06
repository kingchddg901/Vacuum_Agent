# FINDING — live:RB-ERR-2: the Roborock error enum never enters the `code` field

**Found 2026-08-06 during the DR-doc reconciliation (doc 23 pass), by §5.2 discipline: the
reconstruction disagreed with the shipped claim, so it was investigated before patching.**
Status: OPEN, unfixed, report-only (error tracker is shared territory; a doc pass does not
land code fixes).

## Chain (all verified at source, current tree)

1. Roborock's fault code IS the enum string state of `sensor.{id}_vacuum_error`
   (`bumper_stuck`, `wheels_suspended`) — the adapter's own comment says so
   (adapters/roborock/adapter.py:301-306: "code lives in the enum string, not a numeric
   attr, so error_code_attribute_names usually misses -> code None, message = the code
   string").
2. The ONLY writers of record `code` fields are the two `_record_rising_edge` call sites
   (core/error_tracker.py:794, :816), both fed by `_read_error_code_attr` (int-only:
   `_safe_int`, first non-zero int) or literal None. **No path ever writes an enum string
   into `code`.** The enum lands in `message`.
3. Every consumer reads `e.get("code")`: the finalizer's evidence/source splits
   (learning/job_finalizer.py:954, :972) and the read-time fault-naming rows
   (learning/manager.py:95-104).
4. Therefore `_code_key(None)` → None → `classify_error_code` = "unclassified",
   `error_source_for_code` = "unknown", `error_label_key` = None — **for every Roborock
   fault, always.** The five declared Roborock tables (`error_label_keys`,
   `dock/robot_sourced_error_codes`, `evidence_invalidating/safe_error_codes`,
   adapters/roborock/vocabulary.py) can never match at runtime.

## Why this survived shipping

live:RB-ERR-1's fix (`_code_key`) made core ABLE to carry enum codes and its docstring
correctly notes the old adapter warning "points at the wrong fix" — but only the
COMPARISON half was built; the CAPTURE half (getting the enum into `code`) was not.
Device evidence: the learning archive holds real int codes for Alfred (5× 6013, 6010,
6025, 12× 7002) and **zero error-carrying Ivy records ever** — no Roborock fault has
ever been archived, so nothing live could expose the dead tables. (Delta-11 note: one
archive grep settled what static reading could only suspect.)

## Fix shape (for whoever lands it — NOT applied)

At the message-channel rising edge (core/error_tracker.py:816), when the attribute route
yields None and the incoming error VALUE is itself a code-like enum (the brand's error
entity state), carry it: e.g. `code = self._read_error_code_attr(vid)` falling back to
`_code_key(str(new_state))` **gated on adapter declaration** (only for brands whose
error_message entity carries the code enum — a Eufy prose message like "Robot is stuck"
must NOT become a pseudo-code `robot is stuck`). An adapter flag
(`error_tracking.message_is_code` or similar) keeps core brand-agnostic. Degrade
unchanged for legacy records (code stays None; read-time resolution then names them the
moment a fixed capture writes codes — no migration, per the existing read-time design).

## Doc handling (this pass)

Doc 23 documents record `code` fields as `int | None` (what capture writes TODAY), the
classification seams as accepting int AND enum-string keys (what `_code_key` does), and
references this finding for the open capture gap — stating intent as fact is exactly
what §5.1 forbids.
