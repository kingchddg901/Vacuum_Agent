/**
 * ============================================================
 * THEME TOKENS: LEARNING & METRICS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines learning-panel, estimate, confidence, and metrics-
 * specific tokens used by EVCC's predictive and analytical UI.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Learning-specific visuals are authored together so the helper-
 * driven registry stays maintainable without changing the flat
 * backend token dictionary.
 *
 * ============================================================
 */

import { learningToken } from "./helpers.js";

export const LEARNING_TOKENS = [
  learningToken.color("--evcc-estimate-default-bg", "Estimate Default BG"),
  learningToken.color("--evcc-estimate-default-border", "Estimate Default Border"),
  learningToken.color("--evcc-estimate-default-text", "Estimate Default Text"),
  learningToken.color("--evcc-estimate-learned-bg", "Estimate Learned BG"),
  learningToken.color("--evcc-estimate-learned-border", "Estimate Learned Border"),
  learningToken.color("--evcc-estimate-learned-text", "Estimate Learned Text"),
  learningToken.duration("--evcc-learning-anim-duration-fast", "Learning Anim Duration Fast"),
  learningToken.duration("--evcc-learning-anim-duration-normal", "Learning Anim Duration Normal"),
  learningToken.duration("--evcc-learning-anim-duration-slow", "Learning Anim Duration Slow"),
  learningToken.text("--evcc-learning-anim-ease", "Learning Anim Ease"),
  learningToken.size("--evcc-learning-chip-font-size", "Learning Chip Font Size"),
  learningToken.typography("--evcc-learning-chip-font-weight", "Learning Chip Font Weight"),
  learningToken.size("--evcc-learning-chip-radius", "Learning Chip Radius"),
  learningToken.color("--evcc-learning-confidence-high-bg", "Learning Confidence High BG"),
  learningToken.color("--evcc-learning-confidence-high-border", "Learning Confidence High Border"),
  learningToken.text("--evcc-learning-confidence-high-gradient", "Learning Confidence High Gradient"),
  learningToken.color("--evcc-learning-confidence-high-text", "Learning Confidence High Text"),
  learningToken.color("--evcc-learning-confidence-low-border", "Learning Confidence Low Border"),
  learningToken.text("--evcc-learning-confidence-low-gradient", "Learning Confidence Low Gradient"),
  learningToken.color("--evcc-learning-confidence-low-text", "Learning Confidence Low Text"),
  learningToken.color("--evcc-learning-confidence-medium-bg", "Learning Confidence Medium BG"),
  learningToken.color("--evcc-learning-confidence-medium-border", "Learning Confidence Medium Border"),
  learningToken.text("--evcc-learning-confidence-medium-gradient", "Learning Confidence Medium Gradient"),
  learningToken.color("--evcc-learning-confidence-medium-text", "Learning Confidence Medium Text"),
  learningToken.color("--evcc-learning-confidence-neutral-border", "Learning Confidence Neutral Border"),
  learningToken.text("--evcc-learning-confidence-neutral-gradient", "Learning Confidence Neutral Gradient"),
  learningToken.color("--evcc-learning-confidence-neutral-text", "Learning Confidence Neutral Text"),
  learningToken.color("--evcc-learning-note-text", "Learning Note Text"),
  learningToken.color("--evcc-learning-panel-bg", "Learning Panel BG"),
  learningToken.color("--evcc-learning-panel-border", "Learning Panel Border"),
  learningToken.shadow("--evcc-learning-panel-shadow", "Learning Panel Shadow"),
  learningToken.color("--evcc-learning-reanchor-border", "Learning Reanchor Border"),
  learningToken.color("--evcc-learning-reanchor-highlight", "Learning Reanchor Highlight"),
  learningToken.color("--evcc-learning-text-muted", "Learning Text Muted"),
  learningToken.color("--evcc-learning-text-primary", "Learning Text Primary"),
  learningToken.color("--evcc-learning-text-secondary", "Learning Text Secondary"),
  learningToken.color("--evcc-learning-warning-text", "Learning Warning Text"),
];
