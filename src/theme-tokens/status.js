/**
 * ============================================================
 * THEME TOKENS: STATUS, CONFIDENCE & ALERTS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines semantic status, confidence, and alert-state tokens
 * reused across the EVCC control surfaces.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * This group keeps semantic and confidence metadata centralized
 * for editor organization while backend persistence remains a
 * flat token dictionary.
 *
 * ============================================================
 */

import { statusToken } from "./helpers.js";

export const STATUS_TOKENS = [
  statusToken.color("--evcc-color-cleaning", "Color Cleaning"),
  statusToken.color("--evcc-color-docked", "Color Docked"),
  statusToken.color("--evcc-color-error", "Color Error"),
  statusToken.color("--evcc-color-idle", "Color Idle"),
  statusToken.color("--evcc-color-paused", "Color Paused"),
  statusToken.color("--evcc-color-returning", "Color Returning"),
  statusToken.color("--evcc-conf-high", "Conf High"),
  statusToken.color("--evcc-conf-low", "Conf Low"),
  statusToken.color("--evcc-conf-mid", "Conf Mid"),
  statusToken.color("--evcc-conf-none", "Conf None"),
  statusToken.color("--evcc-confidence-high-bg", "Confidence High BG"),
  statusToken.color("--evcc-confidence-high-border", "Confidence High Border"),
  statusToken.color("--evcc-confidence-high-text", "Confidence High Text"),
  statusToken.color("--evcc-confidence-low-bg", "Confidence Low BG"),
  statusToken.color("--evcc-confidence-low-border", "Confidence Low Border"),
  statusToken.color("--evcc-confidence-low-text", "Confidence Low Text"),
  statusToken.color("--evcc-confidence-medium-bg", "Confidence Medium BG"),
  statusToken.color("--evcc-confidence-medium-border", "Confidence Medium Border"),
  statusToken.color("--evcc-confidence-medium-text", "Confidence Medium Text"),
  statusToken.color("--evcc-sem-error", "Sem Error"),
  statusToken.color("--evcc-sem-info", "Sem Info"),
  statusToken.color("--evcc-sem-success", "Sem Success"),
  statusToken.color("--evcc-sem-warning", "Sem Warning"),
  statusToken.color("--evcc-status-cleaning-bg", "Status Cleaning BG"),
  statusToken.color("--evcc-status-cleaning-border", "Status Cleaning Border"),
  statusToken.color("--evcc-status-cleaning-text", "Status Cleaning Text"),
  statusToken.color("--evcc-status-dot-charging", "Status Dot Charging"),
  statusToken.color("--evcc-status-dot-cleaning", "Status Dot Cleaning"),
  statusToken.color("--evcc-status-dot-docked", "Status Dot Docked"),
  statusToken.color("--evcc-status-dot-error", "Status Dot Error"),
  statusToken.color("--evcc-status-dot-idle", "Status Dot Idle"),
  statusToken.color("--evcc-status-dot-offline", "Status Dot Offline"),
  statusToken.color("--evcc-status-dot-paused", "Status Dot Paused"),
  statusToken.color("--evcc-status-dot-returning", "Status Dot Returning"),
  statusToken.shadow("--evcc-status-dot-shadow", "Status Dot Shadow"),
  statusToken.color("--evcc-status-dot-unavailable", "Status Dot Unavailable"),
  statusToken.duration("--evcc-status-pulse-duration", "Status Pulse Duration"),
];
