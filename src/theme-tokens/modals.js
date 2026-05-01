/**
 * ============================================================
 * THEME TOKENS: MODALS & OVERLAYS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines modal, overlay, and modal-chip tokens used by EVCC's
 * modal host and overlay surfaces.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Modal authoring stays in a dedicated group so overlay-specific
 * tokens remain easy to extend while backend persistence remains
 * a flat token dictionary.
 *
 * ============================================================
 */

import { modalToken } from "./helpers.js";

export const MODAL_TOKENS = [
  modalToken.color("--evcc-modal-accent", "Modal Accent"),
  modalToken.color("--evcc-modal-accent-bg", "Modal Accent BG"),
  modalToken.color("--evcc-modal-accent-border", "Modal Accent Border"),
  modalToken.color("--evcc-modal-accent-text", "Modal Accent Text"),
  modalToken.color("--evcc-modal-backdrop-bg", "Modal Backdrop BG"),
  modalToken.number("--evcc-modal-backdrop-blur", "Modal Backdrop Blur"),
  modalToken.color("--evcc-modal-bg", "Modal BG"),
  modalToken.color("--evcc-modal-border", "Modal Border"),
  modalToken.color("--evcc-modal-border-default", "Modal Border Default"),
  modalToken.color("--evcc-modal-border-strong", "Modal Border Strong"),
  modalToken.color("--evcc-modal-border-subtle", "Modal Border Subtle"),
  modalToken.color("--evcc-modal-chip-active-bg", "Modal Chip Active BG"),
  modalToken.color("--evcc-modal-chip-active-border", "Modal Chip Active Border"),
  modalToken.color("--evcc-modal-chip-active-text", "Modal Chip Active Text"),
  modalToken.color("--evcc-modal-chip-bg", "Modal Chip BG"),
  modalToken.color("--evcc-modal-chip-border", "Modal Chip Border"),
  modalToken.color("--evcc-modal-chip-hover-bg", "Modal Chip Hover BG"),
  modalToken.color("--evcc-modal-chip-hover-border", "Modal Chip Hover Border"),
  modalToken.color("--evcc-modal-chip-hover-text", "Modal Chip Hover Text"),
  modalToken.color("--evcc-modal-chip-text", "Modal Chip Text"),
  modalToken.color("--evcc-modal-footer-bg", "Modal Footer BG"),
  modalToken.color("--evcc-modal-header-bg", "Modal Header BG"),
  modalToken.color("--evcc-modal-input-bg", "Modal Input BG"),
  modalToken.size("--evcc-modal-padding", "Modal Padding"),
  modalToken.size("--evcc-modal-radius", "Modal Radius"),
  modalToken.size("--evcc-modal-section-gap", "Modal Section Gap"),
  modalToken.shadow("--evcc-modal-shadow", "Modal Shadow"),
  modalToken.color("--evcc-modal-surface-input", "Modal Surface Input"),
  modalToken.color("--evcc-modal-surface-panel", "Modal Surface Panel"),
  modalToken.color("--evcc-modal-surface-section", "Modal Surface Section"),
  modalToken.color("--evcc-modal-text-muted", "Modal Text Muted"),
  modalToken.color("--evcc-modal-text-primary", "Modal Text Primary"),
  modalToken.color("--evcc-modal-text-secondary", "Modal Text Secondary"),
  modalToken.color("--evcc-modal-warning-bg", "Modal Warning BG"),
  modalToken.color("--evcc-modal-warning-border", "Modal Warning Border"),
  modalToken.color("--evcc-modal-warning-text", "Modal Warning Text"),
];
