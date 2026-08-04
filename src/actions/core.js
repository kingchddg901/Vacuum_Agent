// Base HA service call helpers shared by all action domain modules.

// Q9 operational reason codes (job_control's start_selected_rooms /
// start_zone_clean blocked paths) that carry their own translated phrase in
// the `service_reasons.*` i18n namespace — reason -> full i18n key, a DATA
// VALUE the check-i18n key-cross-check finds via the "quoted string anywhere
// in src" reachability path (case 2 in scripts/check-i18n.mjs), same pattern
// as this codebase's other code->key registries (e.g. map.js's variant
// labels). A code NOT in this map falls back to service_reasons.unknown,
// which still names the raw code (never blank, never fake success) —
// forward-compat with reasons the backend adds later without a matching
// frontend release (RP-031/CARD-1, SYNTH-11-packets-wave7-card.md).
const SERVICE_REASON_KEYS = {
  job_in_progress: "service_reasons.job_in_progress",
  job_paused: "service_reasons.job_paused",
  onboarding_required: "service_reasons.onboarding_required",
  all_selected_rooms_blocked: "service_reasons.all_selected_rooms_blocked",
  vacuum_missing: "service_reasons.vacuum_missing",
  map_mismatch: "service_reasons.map_mismatch",
  // A4-CUSTOM-2 — set_segment_room_link / set_companion_anchor refuse when custom
  // mode has no resolvable layout, instead of silently discarding the write.
  no_active_custom_layout: "service_reasons.no_active_custom_layout",
  // A3-IMAGE--8 — upload refuses rather than persisting a variant with null
  // width/height when neither the PNG header nor Pillow could measure it.
  unreadable_image_dimensions: "service_reasons.unreadable_image_dimensions",
  // Theme library/draft/import refusal codes (CARD-9(2)/(3), RP-034's
  // themes/manager.py — {ok:false, reason} shape, distinct from this file's
  // {success:false, reason} shape but resolved through the same lookup).
  // Reached via actions/theme.js's _callThemeService, which now inspects
  // {ok:false} centrally instead of at each of the ~11 theme action methods.
  theme_not_found: "service_reasons.theme_not_found",
  empty_draft: "service_reasons.empty_draft",
  invalid_payload: "service_reasons.invalid_payload",
  missing_theme: "service_reasons.missing_theme",
  missing_name: "service_reasons.missing_name",
  invalid_tokens: "service_reasons.invalid_tokens",
  invalid_colors: "service_reasons.invalid_colors",
  invalid_alpha: "service_reasons.invalid_alpha",
  missing_vacuum: "service_reasons.missing_vacuum",
  empty_scope: "service_reasons.empty_scope",
  no_active_theme: "service_reasons.no_active_theme",
};

export function applyCoreActions(proto) {

  /**
   * Single entry point for all HA service calls.
   * PURPOSE: centralise error handling so failures never propagate into the render cycle.
   * @param {string} domain
   * @param {string} service
   * @param {object} [data={}]
   * @param {boolean} [returnResponse=false] - set true for response-capable services
   * @returns {Promise<*>} service response or null on failure
   */
  proto.callService = async function (domain, service, data = {}, returnResponse = false) {
    if (!this.hass?.callService) {
      console.warn(
        `[eufy-vacuum-command-center] callService called before hass was ready.`,
        { domain, service, data }
      );
      return null;
    }

    try {
      const result = await this.hass.callService(
        domain,
        service,
        data,
        undefined,   // target
        false,       // notifyOnError
        returnResponse
      );
      // A NON-throwing response can still be an operational refusal, and the
      // backend has TWO such shapes: {success:false, reason} (RP-031, most
      // services) and {started:false, reason} (job_control's start_*). Without
      // this check either is handed back identically to a genuine success — no
      // toast, nothing. showServiceRefusalToast never swallows `result`;
      // callers still get the full payload back below.
      //
      // MZ-2: {started:false} used to be handled per call site, and only ONE of
      // the three ever did. startCleaning toasted it; cleanZone and
      // startRunProfile did not — so a refused ad-hoc zone clean was completely
      // silent and the user believed the robot was going. Asking the question
      // once here is what stops the next start-shaped service repeating it.
      //
      // confirmation_required is EXEMPT: it is a prompt, not a refusal, and
      // startCleaning answers it with a dedicated dialog. Toasting it would put
      // an error next to a question the user is being asked.
      if (returnResponse && result && typeof result === "object") {
        const refused =
          result.success === false ||
          (result.started === false && result.reason !== "confirmation_required");
        if (refused) {
          this.showServiceRefusalToast(result.reason);
        }
      }
      return returnResponse ? result : undefined;
    } catch (err) {
      console.error(
        `[eufy-vacuum-command-center] ${domain}.${service} failed`,
        { data, err }
      );
      // Surface it. `notifyOnError: false` above suppresses Home Assistant's own error
      // toast, which means THIS helper owns telling the user — and until now it did not.
      // Every service call in the card funnels through here, so a failed start, a refused
      // zone clean, or a fetch that could not run all resolved to `null` and were rendered
      // as ordinary empty/idle states. A console line is not user-visible.
      //
      // The toast is best-effort and deliberately never rethrows: a card that explodes
      // while reporting an error is worse than the error. Callers still receive `null`,
      // so every existing null-check keeps working — this only adds the missing signal.
      try {
        const label = `${domain}.${service}`;
        this.showToast?.(
          this.t?.("common.service_failed", { service: label }) ||
            `Could not complete ${label}`,
          { kind: "error", ttl: 6000 }
        );
      } catch (toastErr) {
        console.error("[eufy-vacuum-command-center] toast failed", toastErr);
      }
      return null;
    }
  };

  /**
   * Translate a Q9 operational refusal reason CODE (e.g. "job_in_progress")
   * into a user-facing phrase and show it as an error toast, wrapped in the
   * shared "Could not complete this" template (common.service_refused).
   * Known codes (SERVICE_REASON_KEYS) get their own translated sentence via
   * service_reasons.*; anything else falls back to service_reasons.unknown,
   * which still names the raw code in parens — forward-compat with reasons
   * added on the backend later (RP-031/CARD-1 contract).
   *
   * Shared by callService's own {success:false} inspection above AND by call
   * sites that consume the OTHER established backend refusal shape,
   * {started:false, reason} (job_control's start_selected_rooms /
   * start_run_profile — see rooms.js's startCleaning, FE-ERR-1), so both
   * shapes render through one translation path instead of two hand-copied
   * ones.
   *
   * Best-effort: wrapped in its own try/catch so a broken toast host can
   * never break the call it's reporting on — same defensive pattern as the
   * catch block above.
   * @param {string} reason - the raw backend reason code.
   */
  proto.showServiceRefusalToast = function (reason) {
    const code = String(reason ?? "");
    const reasonKey = SERVICE_REASON_KEYS[code];
    const reasonText = reasonKey
      ? (this.t?.(reasonKey) ?? code)
      : (this.t?.("service_reasons.unknown", { reason: code }) ?? `(${code})`);
    try {
      this.showToast?.(
        this.t?.("common.service_refused", { reason: reasonText }) ||
          `Refused: ${reasonText}`,
        { kind: "error", ttl: 6000 }
      );
    } catch (toastErr) {
      console.error("[eufy-vacuum-command-center] toast failed", toastErr);
    }
  };

  /**
   * Convenience wrapper for homeassistant domain calls (turn_on, turn_off, toggle).
   * @param {string} service
   * @param {string} entityId
   */
  proto.callHA = async function (service, entityId) {
    return this.callService("homeassistant", service, {
      entity_id: entityId,
    });
  };

  /**
   * Invoke a fully-qualified service string such as "button.press".
   * @param {string} fullService - "domain.service" format
   * @param {object} [data={}]
   * @param {boolean} [returnResponse=false]
   */
  proto.callNamedService = async function (fullService, data = {}, returnResponse = false) {
    const raw = String(fullService ?? "").trim();
    if (!raw || !raw.includes(".")) {
      console.warn(
        "[eufy-vacuum-command-center] Invalid full service name",
        { fullService, data }
      );
      return null;
    }

    const [domain, ...serviceParts] = raw.split(".");
    const service = serviceParts.join(".");
    if (!domain || !service) {
      console.warn(
        "[eufy-vacuum-command-center] Invalid split service name",
        { fullService, data }
      );
      return null;
    }

    return this.callService(domain, service, data, returnResponse);
  };
}
