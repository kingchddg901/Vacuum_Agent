## Maintenance

The Maintenance tab gives you a single place to see the health of all consumable parts on your vacuum. It separates items into two categories — maintenance items managed by the integration and replacement items reported directly by the device — and flags anything that needs your attention.

### Overview panels

At the top of the tab, two summary panels give you a quick read on overall health.

**Maintenance Overview** shows:

- **Attention** — how many items are currently flagged for service
- **Priority** — the highest-priority status across all items
- **Items** — the total number of integration-managed maintenance items
- **Water** — the current station water reservoir level

If your vacuum model is known to the integration, the model name and the time the snapshot was last updated appear beneath the panel title.

!!! note "Roborock (S6): Water stat"

    The **Water** stat is only meaningful on vacuums that have a base-station water reservoir. On no-station models (such as the Roborock S6) there is nothing to report, so it reads Unknown or Empty.

**Replacement Overview** shows:

- **Items** — the total number of replacement items reported by the device
- **Attention** — how many replacement items need attention
- **Healthy** — how many replacement items are not flagged
- **Status** — "Tracked" if at least one replacement item exists, otherwise "Empty"

### Needs Attention

The **Needs Attention** section lists every item from either category that is currently flagged. An item appears here if any of the following is true:

- its status is `warning`, `replace_soon`, or `replace_now`
- it is marked overdue or due
- its remaining life is 20% or less

Clicking any item in this list opens the item detail modal (see below).

### Maintenance Items and Replacements tabs

Below the attention list, a tab row lets you switch between **Maintenance Items** (integration-managed intervals, such as filter cleaning or brush cleaning cycles) and **Replacements** (parts the device itself tracks, such as brushes, filters, and sensors).

Each item is shown as a card displaying:

- The item name
- Its current status (for example, "Good", "Warning", "Replace Soon", "Replace Now")
- A primary value — either a summary from the backend, a percentage remaining, or an hours-remaining figure
- A secondary value — either a usage summary, "N hours used of M hours" for replacements, or "N hours left of M hours" for maintenance items
- A "Due in ~N days / weeks / months" projection pill (maintenance items only) — appears once enough history has built up since the last reset (at least three days at non-trivial daily usage). Calculated from your actual usage rate, not the manufacturer's interval. Hidden on freshly-reset items.
- A guide frequency note if the integration has model-specific guidance for this item

The card background fill reflects how much life remains, so you can see at a glance which items are running low.

#### Station Water card

At the end of the Maintenance Items list, the **Station Water** card shows the current water level in the base station reservoir. The level can be a numeric percentage or a text label (such as "Low" or "Full"). The card maps these values to four status levels:

| Condition | Status |
|---|---|
| 70% or above | High |
| 35–69% | Medium |
| 1–34% | Low |
| 0% or empty | Empty |

If the integration has calculated an available clean tank volume, the card also shows that figure in millilitres.

!!! note "Roborock (S6): Station Water card"

    This card only reflects a real level on vacuums with a base-station water reservoir. On no-station models (such as the Roborock S6) there is no reservoir to read, so the card stays at Unknown or Empty.

### Item detail modal

Clicking any maintenance or replacement card opens a modal with full detail for that item.

The top section (the "hero" area) repeats the item's type, status, primary value, and secondary value in a larger format.

Below that:

- **Steps** — model-aware service instructions, shown as a numbered list. If the integration does not have steps for your model, the modal says so.
- **Notes** — any supplementary notes from the integration's guidance data.
- **Interval** — appears only on integration-managed maintenance items (not device-reported replacements). Lets you override how often the integration flags this component for service.
- **Reset** — appears only on items that support a reset action (`can_reset: true`).

#### Adjusting the Interval

The **Interval** section shows the current maintenance interval (in hours) for the item along with the manufacturer-recommended default and the maximum allowed override. Enter a new value and click **Save** to persist it; click **Default** to put the manufacturer's recommended interval back into the input (you still need to click **Save** to commit).

Intervals are stored per vacuum per component and persist across restarts. The value is shared with the matching maintenance-interval number entity for that component (e.g. `number.<vacuum>_<component>_maintenance_interval`, with the exact id derived by Home Assistant from the device and component names), so changes made on the card show up on the entity (and the reverse). Editing the interval does not reset the counter — the new value takes effect immediately and the "remaining" figure recalculates from current usage.

Use this when the default cleaning frequency does not suit your environment — for example, lowering the filter interval in a pet household, or raising the brush interval if your floors stay clean enough that the default warning fires too soon.

#### Using the Reset action

When a Reset section is present, you will see a **Reset** button. Click it to enter a confirmation step. The modal shows a short description of what the reset will do:

- For **integration-managed items**: "This will reset the tracked maintenance interval for [item name]."
- For **replacement items**: "This will send the reset command to the device for [item name]."

Click **Confirm Reset** to proceed or **Cancel** to go back. While the reset is in progress the buttons are disabled and the Confirm button label changes to "Resetting...".

On success, the modal shows "Maintenance reset saved" (for integration items) or "Replacement reset sent" (for device items), and the card data refreshes automatically. On failure, an error message appears in red.
