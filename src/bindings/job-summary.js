/**
 * ============================================================
 * BINDINGS: JOB SUMMARY MODAL
 * ============================================================
 *
 * Opening comes from the Learning Review job card (row body and the error badge —
 * BOTH open this same modal, deliberately, so there is one surface rather than a
 * separate error dialog). Closing is bound in the modal host.
 *
 * ============================================================
 */

/**
 * Controls that live INSIDE the clickable job card and must not also open it.
 *
 * The exclude/restore buttons and the reason chips do NOT stop propagation —
 * checked, not assumed, and an earlier draft of this file claimed they did. Making
 * the card clickable therefore made every one of them open the modal as a side
 * effect. Guarding here rather than editing their handlers keeps the change inside
 * the feature that introduced the problem.
 */
const INTERACTIVE_INSIDE_CARD =
  "[data-review-action],[data-review-reason-chip],button,a,input,select,textarea,label";

/** True when the event came from a control that owns its own behaviour. */
function fromInnerControl(event) {
  const target = event.target;
  if (!target || typeof target.closest !== "function") return false;
  const hit = target.closest(INTERACTIVE_INSIDE_CARD);
  // `hit` inside the card means a real control; the card itself is an <article>
  // and never matches the selector, so this cannot swallow its own clicks.
  return !!hit && hit !== event.currentTarget;
}

export function applyJobSummaryBindings(proto) {
  /** Row + badge launch, bound in the review view. */
  proto._bindJobSummary = function () {
    this.card._onAll("[data-job-summary-open]", "click", (e) => {
      if (fromInnerControl(e)) return;
      const jobId = e.currentTarget?.dataset?.jobSummaryOpen;
      if (!jobId) return;
      this.card._state.openJobSummary?.(jobId);
      this.card._scheduleRender();
    });

    // Keyboard parity: the row is focusable, so Enter/Space must open it too.
    // A mouse-only affordance is not reachable for anyone navigating by keyboard.
    // Same guard — Enter on a focused Exclude button must exclude, not open this.
    this.card._onAll("[data-job-summary-open]", "keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
      if (fromInnerControl(e)) return;
      const jobId = e.currentTarget?.dataset?.jobSummaryOpen;
      if (!jobId) return;
      e.preventDefault();
      this.card._state.openJobSummary?.(jobId);
      this.card._scheduleRender();
    });
  };

  proto._bindJobSummaryHost = function (host) {
    if (!host) return;

    host.querySelectorAll("[data-action='close-job-summary']").forEach((el) => {
      this.card._on(el, "click", () => {
        this.card._state.closeJobSummary?.();
        this.card._scheduleRender();
      });
    });

    // Escape closes, like every other modal in the card. Bound on the modal itself
    // rather than the document so it dies with the node.
    host.querySelectorAll(".evcc-job-summary-modal").forEach((el) => {
      this.card._on(el, "keydown", (e) => {
        if (e.key !== "Escape") return;
        e.stopPropagation();
        this.card._state.closeJobSummary?.();
        this.card._scheduleRender();
      });
    });
  };
}
