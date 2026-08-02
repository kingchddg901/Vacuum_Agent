/**
 * Fault-label resolution (CARD-3 / RF-DOCK).
 *
 * Mixed onto VacuumCardState via applyFaultState(proto).
 *
 * The backend hands the card a fault's i18n KEY, never its text. The vendor's numeric
 * codes are the adapter's business (adapters/eufy/vocabulary.py EUFY_ERROR_LABEL_KEYS)
 * and the strings are the locale packs'; core sits between them knowing neither.
 *
 * WHY A SEAM RATHER THAN t() AT EACH CALL SITE. The key arrives as runtime data, so every
 * consumer would otherwise repeat the same template form and the same fallback. One place
 * means one fallback to get right — and it gives check:i18n a single template proving all
 * `fault.<brand>.<slug>` keys reachable, instead of 189 apparently-dead entries. A gate
 * that always warns is a gate people stop reading.
 *
 * THE FALLBACK IS THE RAW CODE, DELIBERATELY. No label means the adapter has none for that
 * fault: a brand that declares nothing, or a code the vendor shipped after the table was
 * written. "Error 6013" is honest and searchable; an invented label is not, and a blank
 * row tells the user their robot failed for no reason.
 */

export function applyFaultState(proto) {
  /**
   * Resolve one fault to display text.
   *
   * @param {string|null|undefined} key   e.g. "fault.eufy.roller_brush_stuck"
   * @param {number|string|null|undefined} code  raw vendor code, used when there is no label
   * @returns {string}
   */
  proto.faultLabel = function (key, code) {
    if (typeof key === "string") {
      const parts = key.split(".");
      // Shape is fault.<brand>.<slug>. Anything else is not ours to translate.
      if (parts.length >= 3 && parts[0] === "fault") {
        const brand = parts[1];
        const slug = parts.slice(2).join("_");
        const label = this.t(`fault.${brand}.${slug}`);
        // A translator that echoes the key back has no entry for it — fall through
        // rather than printing a dotted key at the user.
        if (label && label !== key) return label;
      }
    }
    const raw =
      typeof code === "number" || (typeof code === "string" && code.trim())
        ? String(code).trim()
        : null;
    return raw ? this.t("faults.unknown_code", { code: raw }) : this.t("faults.unknown");
  };

  /**
   * Resolve a run's captured error list to display rows.
   * Order is preserved — the latch is already chronological.
   *
   * @param {Array<{code?: number, label_key?: string, captured_at?: string}>} errors
   */
  proto.faultRows = function (errors) {
    if (!Array.isArray(errors)) return [];
    return errors
      .filter((e) => e && typeof e === "object")
      .map((e, index) => ({
        index,
        code: e.code ?? null,
        capturedAt: typeof e.captured_at === "string" ? e.captured_at : null,
        label: this.faultLabel(e.label_key, e.code),
      }));
  };
}
