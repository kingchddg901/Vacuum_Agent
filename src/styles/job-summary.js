/**
 * ============================================================
 * STYLES: JOB SUMMARY MODAL
 * ============================================================
 *
 * Chrome comes from the shared .evcc-modal* classes; only the layout inside the
 * body lives here. No raw colours -- everything resolves through a theme token,
 * which check-styles enforces.
 *
 * NO BACKTICKS ANYWHERE IN THIS FILE, including comments: one would close the
 * enclosing template literal and silently truncate every rule after it. That is
 * the exact bug check-styles exists to catch, and it caught it once already
 * during this feature.
 *
 * Logical properties throughout (inline-start/end, not left/right) so the whole
 * modal mirrors under ar/he -- also lint-enforced.
 * ============================================================
 */

export const jobSummaryStyles = `

  .evcc-job-summary-modal {
    /* Literal, matching the sibling room-estimate modal. There is no width
       token in this card and inventing one that nothing defines would look
       themeable while always falling back. */
    max-width: 560px;
  }

  .evcc-job-summary-subtitle {
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
    /* The run id is a machine token; keep it exactly as it is so a user can
       paste it into a search or an issue and have it match. */
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    overflow-wrap: anywhere;
  }

  .evcc-job-summary-note {
    padding: 8px 12px;
    margin-block-end: 12px;
    border-radius: var(--evcc-radius-inner);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-info, var(--evcc-accent)) 30%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-info, var(--evcc-accent)) 10%, transparent);
    color: var(--evcc-text-secondary);
    font-size: 0.82rem;
    line-height: 1.4;
  }

  .evcc-job-summary-section {
    padding-block: 12px;
    border-block-start: 1px solid var(--evcc-border-subtle, var(--evcc-border-default));
  }

  .evcc-job-summary-section:first-child {
    border-block-start: none;
    padding-block-start: 0;
  }

  .evcc-job-summary-section-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-secondary);
    margin-block-end: 8px;
  }

  .evcc-job-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
  }

  .evcc-job-summary-recharge {
    margin-block-start: 10px;
    font-size: 0.82rem;
    color: var(--evcc-sem-warning);
  }

  .evcc-job-summary-room {
    padding-block: 8px;
    border-block-start: 1px solid var(--evcc-border-subtle, var(--evcc-border-default));
  }

  .evcc-job-summary-room:first-of-type {
    border-block-start: none;
  }

  .evcc-job-summary-room-name {
    font-weight: 600;
    font-size: 0.9rem;
  }

  .evcc-job-summary-room-chips {
    margin-block: 6px;
  }

  .evcc-job-summary-room-result,
  .evcc-job-summary-fault-meta {
    font-size: 0.8rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-job-summary-muted {
    opacity: 0.7;
    font-style: italic;
  }

  .evcc-job-summary-fault {
    padding-block: 6px;
  }

  .evcc-job-summary-fault-name {
    font-weight: 600;
    font-size: 0.88rem;
    color: var(--evcc-sem-warning);
  }

  /* The job card in the review list is now a button in behaviour, so it must look
     and focus like one. The focus ring is not decorative: this is the only way to
     reach the modal without a mouse. */
  .evcc-review-job-card[data-job-summary-open] {
    cursor: pointer;
  }

  .evcc-review-job-card[data-job-summary-open]:hover {
    border-color: color-mix(in srgb, var(--evcc-accent) 45%, transparent);
  }

  .evcc-review-job-card[data-job-summary-open]:focus-visible {
    outline: 2px solid var(--evcc-accent);
    outline-offset: 2px;
  }
`;
