/**
 * ============================================================
 * THEME TOKENS: QUEUE & ORDERING
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines queue-strip, ordering, drag feedback, and queue-progress
 * tokens for the room ordering and active-queue surfaces.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Queue and ordering metadata stays in its own group so queue-
 * specific authoring remains maintainable while backend
 * persistence remains flat.
 *
 * ============================================================
 */

import { queueToken } from "./helpers.js";

export const QUEUE_ORDERING_TOKENS = [
  queueToken.number("--evcc-drag-opacity", "Drag Opacity"),
  queueToken.number("--evcc-drag-scale", "Drag Scale"),
  queueToken.shadow("--evcc-drag-shadow", "Drag Shadow"),
  queueToken.color("--evcc-order-chip-bg", "Order Chip BG"),
  queueToken.color("--evcc-order-chip-border", "Order Chip Border"),
  queueToken.color("--evcc-order-chip-text", "Order Chip Text"),
  queueToken.color("--evcc-order-feedback-border", "Order Feedback Border"),
  queueToken.color("--evcc-order-target-outline", "Order Target Outline"),
  queueToken.text("--evcc-progress-complete", "Progress Complete"),
  queueToken.color("--evcc-progress-fill", "Progress Fill"),
  queueToken.color("--evcc-queue-chip-bg", "Queue Chip BG"),
  queueToken.color("--evcc-queue-chip-border", "Queue Chip Border"),
  queueToken.size("--evcc-queue-chip-gap", "Queue Chip Gap"),
  queueToken.color("--evcc-queue-chip-text", "Queue Chip Text"),
  queueToken.color("--evcc-queue-completed-bg", "Queue Completed BG"),
  queueToken.color("--evcc-queue-completed-border", "Queue Completed Border"),
  queueToken.number("--evcc-queue-completed-opacity", "Queue Completed Opacity"),
  queueToken.color("--evcc-queue-completed-text", "Queue Completed Text"),
  queueToken.color("--evcc-queue-current-bg", "Queue Current BG"),
  queueToken.color("--evcc-queue-current-border", "Queue Current Border"),
  queueToken.shadow("--evcc-queue-current-glow", "Queue Current Glow"),
  queueToken.color("--evcc-queue-current-text", "Queue Current Text"),
  queueToken.color("--evcc-queue-hover-bg", "Queue Hover BG"),
  queueToken.color("--evcc-queue-hover-border", "Queue Hover Border"),
  queueToken.color("--evcc-queue-hover-text", "Queue Hover Text"),
  queueToken.color("--evcc-queue-inferred-bg", "Queue Inferred BG"),
  queueToken.color("--evcc-queue-inferred-border", "Queue Inferred Border"),
  queueToken.shadow("--evcc-queue-inferred-glow", "Queue Inferred Glow"),
  queueToken.color("--evcc-queue-inferred-text", "Queue Inferred Text"),
  queueToken.color("--evcc-queue-order-bg", "Queue Order BG"),
  queueToken.color("--evcc-queue-order-border", "Queue Order Border"),
  queueToken.color("--evcc-queue-order-text", "Queue Order Text"),
  queueToken.color("--evcc-queue-pending-bg", "Queue Pending BG"),
  queueToken.color("--evcc-queue-pending-border", "Queue Pending Border"),
  queueToken.number("--evcc-queue-pending-opacity", "Queue Pending Opacity"),
  queueToken.color("--evcc-queue-pending-text", "Queue Pending Text"),
  queueToken.color("--evcc-queue-skipped-bg", "Queue Skipped BG"),
  queueToken.color("--evcc-queue-skipped-border", "Queue Skipped Border"),
  queueToken.color("--evcc-queue-skipped-text", "Queue Skipped Text"),
  queueToken.duration("--evcc-reorder-feedback-duration", "Reorder Feedback Duration"),
  queueToken.easing("--evcc-reorder-flip-easing", "Reorder Flip Easing"),
];
