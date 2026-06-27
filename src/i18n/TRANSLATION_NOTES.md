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

## Second-model cross-review (2026-06-26)
A second model reviewed all 7 — nothing broken. **Applied in-tree** from its list:
- **de**: `Kunst`→`Grafik` across all 9 furnished keys ("Kunst" = artwork, wrong for an uploaded map graphic); `external_jobs.mode_vacuum_mop` "Saug. & Wisch."→"Saugen & Wischen"; `learning.chip_vacuum_mop`→"{count} Saug- und Wischraum / -räume"; `maintenance.dock_fw` "Fw"→"FW"; `map.furnished_art_alt`→"Eingerichteter Grundriss"; `map.backdrop_image_hint` "bemalt"→"überzeichnet"; `bind_map.could_not_save_map_image` "auf der Karte"→"auf dem Kartenbild".
- **nl**: `Kunst`/`kunst`→`Afbeelding`/`afbeelding` across all 9 furnished keys (same artwork issue).

**Deferred** (dialect / native-judgment — the second model itself hedged; for the native reviewers):
- **es**: verb+noun clash in the vacuum+mop mode/chip labels ("Aspirar y mopa", "… aspirar + mopa") — pick a consistent dialect form (e.g. "Aspirar y fregar" / "Aspirado + mopa" / "Aspirar + pasar mopa"). Also the earlier `room_editor.mopstate_mopping` "Mopeando"→"Fregando".
- **fr**: over-abbreviated mode/chip ("Asp. & serp.") — spell out unless the chip is truly tiny ("Aspi. + serpillière" / "Asp. + lavage").
- **it**: English "mop" leaks ("Asciuga mop", "Lava mop", "aspira + mop") — more native = "panno" / "panno lavapavimenti" / "lavaggio" (acceptable for tech users).
- **ru**: literal "швабру" (mop) in dock actions — a native may prefer "салфетку" / "моп" / "моющую насадку" per common robovac phrasing.
- **pt**: reads European Portuguese (divisão, guardar, aplicação, mopa), NOT truly region-neutral. Fine as `pt`; add a `pt-BR` later if Brazilian users care (keep this as pt-PT-ish).
- **all locales**: the "save image on the map" family reads slightly odd everywhere — better phrased as "right-click the map image and choose Save image" (rephrase per language).

## Post-pattern-fix: new keys (setup.floor_* / setup.step_*), translated
The render review found data-literal UI strings that bypassed t() (floor types + setup-step headings); they now route through t() and were AI-translated into all 7 locales. Native-review nuance:
- **setup.step_add_vacuum** rendered with the plain vacuum term per locale. **de** aligned to "Saugroboter hinzufügen" (de uses "Saugroboter" 30:1 — never the plain "Staubsauger"). **fr/es/it/pt** also use a "robot"-qualified device term in fuller text (~24×); a native may prefer it in the step heading too, though the plain term matches English's "Add vacuum". **nl** ("Stofzuiger") + **ru** ("пылесос") match their locale's dominant plain term — fine.
- **setup.floor_*** are standard native flooring terms (e.g. de Holz/Fliesen/Beton, fr Parquet/Carrelage/Béton, ru Паркетная доска/Плитка/Бетон) — verify against regional convention if a native cares (e.g. pt-PT "alcatifa" vs pt-BR "carpete").
