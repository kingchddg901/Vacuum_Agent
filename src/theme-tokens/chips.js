/**
 * ============================================================
 * THEME TOKENS: CHIPS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines the shared chip system used for tabs, filters, actions,
 * status badges, and lightweight control affordances across the
 * card.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Chips are authored as one grouped system so global chip changes
 * stay coherent while backend persistence remains a flat token
 * dictionary.
 *
 * ============================================================
 */

import { chipToken } from "./helpers.js";

export const CHIP_TOKENS = [
  chipToken.color("--evcc-chip-active-bg", "Chip Active BG"),
  chipToken.color("--evcc-chip-active-border", "Chip Active Border"),
  chipToken.color("--evcc-chip-active-text", "Chip Active Text"),
  chipToken.color("--evcc-chip-bg", "Chip BG"),
  chipToken.color("--evcc-chip-border", "Chip Border"),
  chipToken.color("--evcc-chip-excluded-bg", "Chip Excluded BG"),
  chipToken.color("--evcc-chip-excluded-border", "Chip Excluded Border"),
  chipToken.color("--evcc-chip-excluded-text", "Chip Excluded Text"),
  chipToken.size("--evcc-chip-font-size", "Chip Font Size"),
  chipToken.typography("--evcc-chip-font-weight", "Chip Font Weight"),
  chipToken.size("--evcc-chip-gap", "Chip Gap"),
  chipToken.size("--evcc-chip-height", "Chip Height"),
  chipToken.color("--evcc-chip-hover-bg", "Chip Hover BG"),
  chipToken.color("--evcc-chip-hover-border", "Chip Hover Border"),
  chipToken.color("--evcc-chip-hover-text", "Chip Hover Text"),
  chipToken.size("--evcc-chip-icon-height", "Chip Icon Height"),
  chipToken.size("--evcc-chip-icon-padding", "Chip Icon Padding"),
  chipToken.size("--evcc-chip-icon-size", "Chip Icon Size"),
  chipToken.color("--evcc-chip-included-bg", "Chip Included BG"),
  chipToken.color("--evcc-chip-included-border", "Chip Included Border"),
  chipToken.color("--evcc-chip-included-text", "Chip Included Text"),
  chipToken.color("--evcc-chip-neutral-bg", "Chip Neutral BG"),
  chipToken.size("--evcc-chip-padding", "Chip Padding"),
  chipToken.size("--evcc-chip-radius", "Chip Radius"),
  chipToken.color("--evcc-chip-success-bg", "Chip Success BG"),
  chipToken.color("--evcc-chip-success-border", "Chip Success Border"),
  chipToken.color("--evcc-chip-success-text", "Chip Success Text"),
  chipToken.color("--evcc-chip-text", "Chip Text"),
  chipToken.color("--evcc-chip-warning-bg", "Chip Warning BG"),
  chipToken.color("--evcc-chip-warning-border", "Chip Warning Border"),
  chipToken.color("--evcc-chip-warning-text", "Chip Warning Text"),
];
