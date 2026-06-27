# Translation review notes (AI drafts → native review)

`ru` + T1 (`de`/`fr`/`es`/`nl`/`it`/`pt`) are AI-generated drafts. Structure is
machine-verified (full key parity, placeholder parity, plural shapes, markup —
all pass `npm run check:i18n`) and a semantic QA pass found **no English-leakage**
in any locale. The items below are the QA's flagged judgment-calls for a **native
speaker** to confirm/apply. Two objective fixes were already applied in-tree
(de "fan speed"→`Saugkraft` ×4; pt `relative.months_ago` non-word `mes`→`mês`).

Verdicts: de = usable_with_fixes (now good after the fan-speed fix); all others = good_draft.

> **New keys pending translation:** the `card_editor.*` namespace (5 keys — the Lovelace
> visual config editor's labels) was added to en.js AFTER these drafts were produced, so the
> locales don't carry them yet and fall back to English in the card editor. Translate them when
> reviewing each locale (low priority — config-time surface; the language *option* labels are
> already native, e.g. "Deutsch (Entwurf)").

## ru (Russian — pilot, live native review)
- `learning.queue_missed_rooms` — lost the imperative verb, reads as a fragment. → e.g. "Добавить пропущенные комнаты в очередь".
- `maintenance.stat_total_cleaned` — blurs the "area in m²" sense vs `stat_cleans`. → e.g. "Убранная площадь".
- `learning.minutes_left`, `rooms.remaining_left` — pill word order; "осталось ~{x}" reads more naturally than "~{x} осталось". (verify pill width)
- `map.zone_clean_n` — plain string, `{count}` 1–5; "Очистить 1 зон" is wrong agreement. Confirm the count range; if 1–4 reachable, convert to a plural object.
- Plural agreement to verify: `learning.incomplete_title` (few form), `rooms.n_blocked`/`n_included`, `mapping_review.badge_n_excluded` (elided-noun gender — pick исключён/исключена by referent).

## de (German)
- `mapping_review.baseline` — "Grundlinie" reads as a chart baseline; sense is the protected anchor/oldest run. → "Referenzlauf" / "Basislauf".
- `maintenance.due_in_months`, `due_in_weeks` — only an `{other}` form; if count=1 is reachable add a `{one}` ("~1 Monat" / "~1 Woche").

## fr (French)
- `external_jobs.blocked` — "re-choisissez" non-idiomatic. → "choisissez à nouveau".
- `map.compose_cutout_on` — "(en cours)" reads as a busy/loading state; intended is the active carving MODE. → "(active)".

## es (Spanish)
- `room_editor.mopstate_mopping` — "Mopeando" is an anglicism. → "Fregando".
- `learning.done_by`, `room_estimate.subtitle_done_by` — "listo para las {time}" leans "ready for"; sense is projected finish-by. → "terminará para las {time}".
- `learning.note_runs_to_reliable` — loses the "more/additional runs" nuance. → "{count} limpiezas más para que sea fiable".

## nl (Dutch)
- `maintenance.due_today`, `due_tomorrow` — "verschuldigd" = owed (money); wrong for a due task. → "Vervalt vandaag/morgen" or "Vandaag/Morgen te doen".
- `metrics.battery_drain_subtitle` — doubled word ("per-categorie-categorieën").
- `rooms.reduced_run_detected` — "Verkleinde run" = shrunk in size; sense is fewer rooms than queued. → "Beperkte run gedetecteerd".

## it (Italian)
- `learning.done_at` — "Finito alle" reads past; sense is projected per-room finish. → "Fine prevista alle {time}".
- `learning.cleaning_room` — "Pulizia di {room}" is a noun phrase; sense is the live status. → "Pulizia di {room} in corso".
- `map.compose_split` — "Separa" loses the "split into its own room" sense. → "Dividi" / "Scorpora".
- Add `{one}` forms for count=1 agreement (only `{other}` shipped): `maintenance.due_in_weeks`/`due_in_months`, `external_jobs.segments_merged`, `base_station.recorded_count`, `rooms.n_blocked`/`n_included`, `mapping_review.badge_n_excluded` (also verify masc/fem referent).

## pt (Portuguese)
- (`relative.months_ago` non-word already fixed.) Minor register: `setup.*` "defina por favor" word order; `external_jobs.detected_rooms` one-form slightly long.
