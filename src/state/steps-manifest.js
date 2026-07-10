// Pure "Runs As" step-manifest renderer, shared by the command-center run-profiles
// panel (renderers/run-profiles.js) and the standalone profile card (cards/
// profile-card.js) so the two surfaces cannot drift on how a routine reads.
//
// It takes the profile's steps, a room-id→name lookup, and the CALLER's i18n (t)
// and HTML escaper (escapeHtml) — no DOM, no `this`, no imports — and returns the
// manifest HTML string ("" when there are no steps).
//
// Class names match src/styles/run-profiles.js (.evcc-run-profiles-seq-*). The main
// bundle styles them for the panel; the standalone card carries the same rules in
// its own shadow root (aliased to HA tokens so it styles on a cold dashboard).

export function renderStepsManifest({ steps, nameById = {}, t, escapeHtml }) {
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
      const groupRooms = Array.isArray(step.rooms) ? step.rooms : [];
      const names = groupRooms
        .map((r) =>
          escapeHtml(
            nameById[String(r.room_id)] ??
              t("run_profiles.room_fallback", { id: escapeHtml(String(r.room_id)) })
          )
        )
        .join(", ");
      const modes = new Set(groupRooms.map((r) => r.clean_mode).filter(Boolean));
      const modeHint = modes.size === 1 ? [...modes][0] : null;
      return `
        <li class="evcc-run-profiles-seq-step">
          <span class="evcc-run-profiles-seq-kind">${t("run_profiles.step_clean")}</span> ${names || t("run_profiles.step_group_empty")}${modeHint ? ` <span class="evcc-run-profiles-seq-mode">${escapeHtml(modeHint)}</span>` : ""}
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
