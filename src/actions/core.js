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
