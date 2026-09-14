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
  // anchor: RNGP3ZBE  the RESPONSE-CAPABLE service-call convention -- the replica set.
  // The standalone card restates it in cards/_shared.js, argument for argument: target
  // undefined, notifyOnError false, returnResponse true, unwrap `response`, null on any
  // failure and never throw into the render cycle. Panel and card must refuse alike.
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
      //
      // UNWRAP FIRST, THEN INSPECT. `hass.callService(..., returnResponse)` resolves to an
      // ENVELOPE -- `{context, response}` -- and the service's own return value is the
      // `response` half. Every line below this used to read the ENVELOPE, so `result.success`
      // was ALWAYS undefined and this entire branch could never fire. Measured on the live
      // panel 2026-09-13: Object.keys(result) === ["context","response"]. Every refusal toast
      // the card has ever declared has therefore been silent, including the ones whose call
      // sites DELETED their own toast in favour of this one (see actions/rooms.js#L143's
      // comment, MZ-2, which describes a behaviour that never shipped).
      //
      // `?? result`, NOT `?? null`. A handler returning None gives `response: null`; falling
      // back to the envelope keeps the value TRUTHY, which is what bindings/maintenance.js and
      // bindings/base-station.js test for (`result === null` / `result !== null`) to decide
      // whether a save or a dock action took. `?? null` would report a successful save as a
      // failure. The `?? result` arm also makes this backward-compatible with the ~40 callers
      // that already spell the unwrap themselves -- their `result?.response ?? result` simply
      // becomes a no-op on an already-unwrapped payload.
      //
      // REPLICA RNGP3ZBE: this is the clause that had diverged. src/cards/_shared.js's
      // callResponse -- the declared twin -- has always returned the unwrapped payload.
      // Unwrapping here also revives the SECOND dead funnel, actions/theme.js's
      // `_callThemeService`, which reads `result.ok === false` at this same level.
      const payload = returnResponse ? (result?.response ?? result) : undefined;

      // A NON-throwing response can still be an operational refusal, and the
      // backend has TWO such shapes: {success:false, reason} (RP-031, most
      // services) and {started:false, reason} (job_control's start_*). Without
      // this check either is handed back identically to a genuine success — no
      // toast, nothing. showServiceRefusalToast never swallows the payload;
      // callers still get it back below.
      //
      // DELIBERATELY NOT WIDENED to the other discriminators the backend emits
      // ({ok:false}, {updated:false}, {saved:false}, {status:"error"}, {error}).
      // Those are already inspected by their own funnels -- theme.js for `ok`,
      // bindings/room-editor.js::_roomEditorSaveWasRejected for updated/error --
      // and adding them here would DOUBLE-toast every one. Fixing the shape is
      // not licence to change the contract; widening the set is a separate call.
      //
      // confirmation_required is EXEMPT: it is a prompt, not a refusal, and
      // startCleaning answers it with a dedicated dialog. Toasting it would put
      // an error next to a question the user is being asked.
      if (returnResponse && payload && typeof payload === "object") {
        const refused =
          payload.success === false ||
          (payload.started === false && payload.reason !== "confirmation_required");
        if (refused) {
          this.showServiceRefusalToast(payload.reason);
        }
      }
      return payload;
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
        // A refusal does not always come back as a VALUE. The theme services raise
        // ServiceValidationError("<operation> failed: <reason>") rather than returning
        // {ok:false, reason}, so all nine of them land in this catch — and the reason
        // the backend went to the trouble of computing was rendered as the generic
        // "could not complete", one layer from the user. THEME-1: a scoped import
        // refused with `missing_vacuum` read as "the vacuum may not have received it",
        // which points at the transport when the payload never left the client.
        // Prefer the specific toast whenever the message carries a reason code; the
        // generic one stays the fallback for genuine transport failures, which have no
        // code. Best-effort by design — a malformed message must not lose the toast.
        const reason = /\bfailed:\s*([a-z][a-z0-9_]*)\b[\s.]*$/i.exec(
          String(err?.message ?? "")
        )?.[1];
        // Direct calls, not `?.` — `t`/`showToast` are real methods on
        // VacuumCardActions now. Optional-chaining them is what let this whole path
        // no-op silently for as long as it did; if the delegation is ever removed
        // again, this should be loud rather than quiet.
        if (reason) {
          this.showServiceRefusalToast(reason);
        } else {
          this.showToast(
            this.t("common.service_failed", { service: label }),
            { kind: "error", ttl: 6000 }
          );
        }
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
    // A known code resolves to an escaped catalog string. An UNKNOWN one interpolates
    // the raw backend value, and t() inserts interpolated values raw (trust model B) —
    // so esc() it here, at the point it enters the chain, exactly as the bindings do
    // for backend `reason`/`message` text. The toast sink does not escape.
    const reasonText = reasonKey
      ? this.t(reasonKey)
      : this.t("service_reasons.unknown", { reason: this.esc(code) });
    try {
      // `reasonText` is already escaped (either a t() catalog string or an esc()'d raw
      // code), and t() inserts interpolated values raw — so this is single-escaped, not
      // double. Direct calls for the same reason as the failure path above.
      this.showToast(
        this.t("common.service_refused", { reason: reasonText }),
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
