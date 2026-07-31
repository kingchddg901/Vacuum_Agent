// Base HA service call helpers shared by all action domain modules.

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
