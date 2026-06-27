/**
 * ============================================================
 * BINDINGS: COMBINER
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines VacuumCardBindings and mixes all binding modules
 * onto its prototype.
 *
 * This file owns:
 * - the VacuumCardBindings class
 * - the bindEvents() entry point called after every render
 * - prototype composition order
 *
 * WHAT THIS FILE SHOULD NOT CONTAIN
 * ----------------------------------
 * - binding logic (lives in binding modules)
 * - rendering
 * - state logic
 * - service calls
 *
 * IMPORTANT DESIGN RULE
 * ---------------------
 * bindEvents() is called after every shadowRoot replacement.
 * Because the DOM is fully replaced on each render, all
 * previously attached listeners are gone. This method
 * reconnects everything cleanly from scratch each time.
 *
 * HOW THIS FILE FITS INTO THE SYSTEM
 * -----------------------------------
 * Instantiated once in main.js.
 * main.js calls this._bindings.bindEvents() after each render.
 *
 * ============================================================
 */

import { applyNavBindings        } from "./nav.js";
import { applyLanguageBindings   } from "./language.js";
import { applyBaseStationBindings } from "./base-station.js";
import { applyMaintenanceBindings } from "./maintenance.js";
import { applyMetricsBindings    } from "./metrics.js";
import { applyOrderBindings      } from "./order.js";
import { applyRunProfilesBindings } from "./run-profiles.js";
import { applyReviewBindings     } from "./review.js";
import { applyRoomsBindings      } from "./rooms.js";
import { applyRoomAccessBindings } from "./room-access.js";
import { applyRoomEstimateBindings } from "./room-estimate.js";
import { applyRoomEditorBindings } from "./room-editor.js";
import { applyRoomRulesBindings  } from "./room-rules.js";
import { applyThemeBindings         } from "./theme.js";
import { applyMapBindings           } from "./map.js";
import { applySetupBindings         } from "./setup.js";
import { applyMappingReviewBindings } from "./mapping-review.js";
import { applyMobileShellBindings   } from "./mobile-shell.js";
import { applyExternalJobsBindings   } from "./external-jobs.js";

/* =========================================================
   CLASS
   ========================================================= */

export class VacuumCardBindings {

  /**
   * @param {object} card - The host `VacuumCard` custom element instance.
   */
  constructor(card) {
    this.card = card;
  }

  /**
   * Update the card reference without recreating the object.
   *
   * @param {object} card - New card instance.
   * @returns {VacuumCardBindings} `this` for chaining.
   */
  sync(card) {
    this.card = card;
    return this;
  }

  /**
   * Translate a UI string for a binding (toast / confirm / error message). The
   * binding prototype has no `t` of its own, so it delegates to the renderers'
   * i18n (`card._renderers.t`, defined in renderers/shared.js); if the renderers
   * aren't constructed yet it falls back to the key — a visible miss, never a
   * throw. Interpolation values are raw, escaped by the caller at the sink as
   * before (trust model B escapes only the catalog string).
   *
   * @param {string} key - dot-namespaced string key (e.g. "bind_rooms.saved").
   * @param {Record<string, unknown>} [vars] - interpolation values (raw).
   * @returns {string}
   */
  t(key, vars) {
    return this.card?._renderers?.t?.(key, vars) ?? key;
  }

  /** Markup-preserving translate (see `t`); delegates to `card._renderers.tRaw`. */
  tRaw(key, vars) {
    return this.card?._renderers?.tRaw?.(key, vars) ?? key;
  }

  /** Re-attach all shadow-root event handlers after each render. */
  bindEvents() {
    this._bindNav();
    this._bindLanguage();
    this._bindBaseStation();
    this._bindMaintenance();
    this._bindMetrics();
    this._bindOrder();
    this._bindRunProfiles();
    this._bindReview();
    this._bindExternalJobs();
    this._bindRooms();
    this._bindRoomAccess();
    this._bindRoomEstimate();
    this._bindRoomEditor();
    this._bindRoomRules();
    this._bindThemeEditor();
    this._bindMap();
    this._bindSetup();
    this._bindMappingReview();
    this._bindMobileShell();
    this._bindToasts();
  }

  /**
   * Wire dismiss buttons on active toast pills. Each click drops the
   * matching toast from the queue and schedules a re-render. Idempotent
   * via card._onAll so re-binding across renders is safe.
   */
  _bindToasts() {
    this.card._onAll("[data-action='dismiss-toast']", "click", (e) => {
      const id = e.currentTarget?.dataset?.toastId;
      if (!id) return;
      this.card._state.dismissToast?.(id);
      this.card._scheduleRender();
    });
  }

  _bindOrder() {
    this.bindOrderEvents(this.card.shadowRoot);
  }

  /**
   * Wire event handlers on the external modal host node.
   *
   * @param {Element|null} host - The modal host element, or null.
   */
  bindModalHostEvents(host) {
    if (!host) return;

    // Stop propagation inside modal so backdrop click doesn't fire.
    const modal = host.querySelector("[data-stop-propagation]");
    if (modal) {
      modal.addEventListener("click", (e) => e.stopPropagation());
    }

    // Include/exclude toggle inside modal.
    host.querySelectorAll("[data-action='toggle-room']").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();

        const roomId = Number(btn.dataset.roomId);
        const mapId = String(btn.dataset.mapId);
        const enabled = btn.dataset.enabled === "true";
        if (!roomId || !mapId) return;

        await this.card._actions.toggleRoomEnabled(mapId, roomId, enabled);
        await this.card.refreshDashboardSnapshot?.();
        this.card._scheduleRender();
      });
    });

    // Shared order selector actions inside modal host.
    host.querySelectorAll("[data-action='close-order-selector']").forEach((el) => {
      el.addEventListener("click", () => {
        this.card._state.closeOrderSelector();
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='set-order-position']").forEach((btn) => {
      btn.addEventListener("click", () => {
        const position = Number(btn.dataset.position);
        if (!position) return;

        this.card._state.setOrderSelectorTargetPosition(position);
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='confirm-order-selector']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await this.confirmOrderSelectorWithFlip();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Failed to save ordered position:", err);
        }
      });
    });

    host.querySelectorAll("[data-action='open-order-selector']").forEach((btn) => {
      btn.addEventListener("click", () => {
        const scope = btn.dataset.scope;
        const itemId = btn.dataset.itemId;
        if (!scope || itemId == null) return;

        this.card._state.openOrderSelector(scope, itemId);
        this.card._scheduleRender();
      });
    });

    this._bindMaintenanceModalHost?.(host);
    this._bindRoomAccessHost?.(host);
    this._bindRoomEstimateHost?.(host);
    this._bindExternalWizardHost?.(host);
    this._bindThemeJsonModalHost?.(host);

    // Close room editor actions.
    host.querySelectorAll("[data-action='close-room-editor']").forEach((el) => {
      el.addEventListener("click", () => {
        this.card._state.closeRoomEditor();
        this.card._scheduleRender();
      });
    });

    // Field chip clicks.
    host.querySelectorAll("[data-field]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const field = btn.dataset.field;
        let value = btn.dataset.value;
        if (!field || value === undefined) return;

        if (btn.dataset.action === "apply-profile") {
          this.card._state.applyEditorProfile(value);
          this.card._scheduleRender();
          return;
        }

        if (field === "clean_passes") value = Number(value);
        if (field === "edge_mopping") value = value === "true";

        this.card._state.updateEditorField(field, value);
        this.card._scheduleRender();
      });
    });

    // Save room editor.
    const saveBtn = host.querySelector("[data-action='save-room-editor']");
    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        const room = this.card._state.activeEditorRoom();
        const fields = this.card._state.editorFields();
        if (!room || !fields) return;

        try {
          await this.card._actions.saveRoomEditor(
            room.mapId,
            room.id,
            fields
          );

          await this._refreshRoomEditorEstimates?.();
          this.card._state.closeRoomEditor();
          this.card._scheduleRender();
        } catch (err) {
          console.error("[eufy-vacuum-command-center] Failed to save room editor:", err);
        }
      });
    }

    host.querySelectorAll("[data-action='save-room-profile-as-new']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await this._handleSaveRoomProfileAsNew?.();
      });
    });

    host.querySelectorAll("[data-action='overwrite-room-profile']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (btn.disabled) return;
        await this._handleOverwriteRoomProfile?.();
      });
    });

    host.querySelectorAll("[data-action='rename-room-profile']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (btn.disabled) return;
        await this._handleRenameRoomProfile?.();
      });
    });

    host.querySelectorAll("[data-action='delete-room-profile']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (btn.disabled) return;
        await this._handleDeleteRoomProfile?.();
      });
    });
  }
}

/* =========================================================
   PROTOTYPE COMPOSITION
   ========================================================= */

applyNavBindings(VacuumCardBindings.prototype);
applyLanguageBindings(VacuumCardBindings.prototype);
applyBaseStationBindings(VacuumCardBindings.prototype);
applyMaintenanceBindings(VacuumCardBindings.prototype);
applyMetricsBindings(VacuumCardBindings.prototype);
applyOrderBindings(VacuumCardBindings.prototype);
applyRunProfilesBindings(VacuumCardBindings.prototype);
applyReviewBindings(VacuumCardBindings.prototype);
applyRoomsBindings(VacuumCardBindings.prototype);
applyRoomAccessBindings(VacuumCardBindings.prototype);
applyRoomEstimateBindings(VacuumCardBindings.prototype);
applyRoomEditorBindings(VacuumCardBindings.prototype);
applyRoomRulesBindings(VacuumCardBindings.prototype);
applyThemeBindings(VacuumCardBindings.prototype);
applyMapBindings(VacuumCardBindings.prototype);
applySetupBindings(VacuumCardBindings.prototype);
applyMappingReviewBindings(VacuumCardBindings.prototype);
applyMobileShellBindings(VacuumCardBindings.prototype);
applyExternalJobsBindings(VacuumCardBindings.prototype);
