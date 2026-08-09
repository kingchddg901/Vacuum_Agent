// Pure "Runs As" step-manifest renderer, shared by the command-center run-profiles
// panel (renderers/run-profiles.js) and the standalone profile card (cards/
// profile-card.js) so the two surfaces cannot drift on how a routine reads.
//
// It takes the profile's steps, a room-id→name lookup, the CALLER's i18n (t), a
// vocab resolver (tVocab — localizes a setting VALUE like clean_mode and returns
// escape-safe HTML), and HTML escaper (escapeHtml) — no DOM, no `this`, and no
// imports beyond the dependency-free clean-mode fold below
// — and returns the manifest HTML string ("" when there are no steps).
//
// Class names match src/styles/run-profiles.js (.evcc-run-profiles-seq-*). The main
// bundle styles them for the panel; the standalone card carries the same rules in
// its own shadow root (aliased to HA tokens so it styles on a cold dashboard).

import { canonicalCleanMode } from "../clean-mode.js";

export function renderStepsManifest({ steps, nameById = {}, zoneNameById = {}, t, escapeHtml, tVocab }) {
  const list = Array.isArray(steps) ? steps : [];
  if (!list.length) return "";

  const items = list
    .map((step) => {
      if (step.type === "charge_wait") {
        const target = Number(step.target_battery_percent ?? 95);
        return `
          <li class="evcc-run-profiles-seq-step evcc-run-profiles-seq-step--charge">
            <span class="evcc-run-profiles-seq-icon" aria-hidden="true">⚡</span>${t("run_profiles.step_charge_to")} ${escapeHtml(String(target))}%
          </li>`;
      }
      if (step.type === "wait") {
        const mins = Number(step.wait_minutes ?? 30);
        return `
          <li class="evcc-run-profiles-seq-step evcc-run-profiles-seq-step--wait">
            <span class="evcc-run-profiles-seq-icon" aria-hidden="true">⏱</span>${t("run_profiles.step_wait")} ${escapeHtml(String(mins))} ${t("run_profiles.minutes_unit")}
          </li>`;
      }
      if (step.type === "zone") {
        // A zone is a CLEAN step, not a room group — without this it fell through below to
        // "Clean (no rooms)" (a zone carries zone_ids, never rooms). Names via zoneNameById.
        const ids = Array.isArray(step.zone_ids) ? step.zone_ids : [];
        const znames = ids
          .map((id) => escapeHtml(zoneNameById[String(id)] ?? t("rooms.zone_fallback")))
          .join(", ");
        return `
          <li class="evcc-run-profiles-seq-step evcc-run-profiles-seq-step--zone">
            <span class="evcc-run-profiles-seq-icon" aria-hidden="true">🎯</span><span class="evcc-run-profiles-seq-kind">${t("run_profiles.step_clean")}</span> ${znames || t("rooms.zone_fallback")}
          </li>`;
      }
      const groupRooms = Array.isArray(step.rooms) ? step.rooms : [];
      const names = groupRooms
        .map((r) =>
          escapeHtml(
            nameById[String(r.room_id)] ??
              t("run_profiles.room_fallback", { id: escapeHtml(String(r.room_id)) })
          )
        )
        .join(", ");
      // ISSUE #48: fold before the Set. Two rooms genuinely in the same mode but
      // stored with different spellings — one card-edited ("Vacuum and mop"), one
      // profile-resolved ("vacuum_mop") — gave size 2, so the chip was dropped and
      // an all-same-mode group rendered identically to a genuinely mixed one.
      const modes = new Set(groupRooms.map((r) => canonicalCleanMode(r.clean_mode)).filter(Boolean));
      // Show the room's own spelling, not the token — the chip is localized through
      // the caller's vocab resolver, which is keyed on what the room actually holds.
      const modeHint = modes.size === 1
        ? (groupRooms.find((r) => r.clean_mode)?.clean_mode ?? null)
        : null;
      // Localize the clean-mode chip (vacuum/mop/…) through the caller's vocab
      // resolver — without this it rendered the raw English enum (e.g. "VACUUM",
      // CSS-uppercased) on an otherwise fully-translated card. tVocab returns
      // escape-safe HTML; fall back to escapeHtml if a caller doesn't supply it.
      const modeLabel = modeHint
        ? (tVocab ? tVocab("clean_mode", modeHint, modeHint) : escapeHtml(modeHint))
        : null;
      return `
        <li class="evcc-run-profiles-seq-step">
          <span class="evcc-run-profiles-seq-kind">${t("run_profiles.step_clean")}</span> ${names || t("run_profiles.step_group_empty")}${modeLabel ? ` <span class="evcc-run-profiles-seq-mode">${modeLabel}</span>` : ""}
        </li>`;
    })
    .join("");

  return `
    <div class="evcc-run-profiles-sequence">
      <span class="evcc-run-profiles-label">${t("run_profiles.runs_as")}</span>
      <ol class="evcc-run-profiles-seq-list">${items}</ol>
    </div>
  `;
}
