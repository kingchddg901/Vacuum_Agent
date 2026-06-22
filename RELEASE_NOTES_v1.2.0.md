**The Map view goes from a static backdrop to a live, interactive surface.** Your robot is now tracked across the map in real time — and you can lay a render of your *actual furnished home* over the live map — the robot and overlays ride on top — then draw a box to zone-clean, and more. The biggest map release since the integration began.

### Added
- **Mittens joins the map.** A new **Rainbow Bridge** animal group — companions for remembered pets — debuts with **Mittens**. Unlike the themeable animals, she's painted true to life: her real markings stay fixed whatever theme you run, and only her eyes shift with battery state. *In loving memory.*
- **Live robot tracking & map overlays.** A new VA-owned read of the device's own map puts the **live robot position, heading, dock, current room, cleaning path, and hazards** (no-go / no-mop / walls) on the map in real time — plus native current-room rollover and a faster live room/fan refresh on Roborock. A **Mascot follows robot** toggle lets your companion ride the robot's live position.
- **Furnished render.** Lay a to-scale render of your real home over the live map so the robot drives across your actual furniture. **Save map image** to trace over, upload your art, pick a view mode (**Live / Blend / Art**), and align by eye — drag, scale, rotate (coarse ±90°, fine ±1°/±0.1°, ±15° trim slider). No calibration step: aligning it by eye once is all it needs, and the live overlays ride on top for free. Brand-agnostic (Eufy fork + Roborock).
- **Zone cleaning (draw a box).** Zone-clean an area you draw on the live map, at **any map rotation**, with suction/mop settings — on **Eufy** (via the eufy-clean fork) **and Roborock** (stock integration, no fork/PR). Per-clean caps: Eufy up to **10** zones; Roborock up to **5**, each **1–32.8 ft²**.
- **More map interactions.** Tap rooms on the map to build a clean selection (unpicked rooms dim), **Hide area** to mask map noise, and **draggable room-area (m²) labels**. On a **bare Roborock live map** (no drawn rooms), the room names, the mascot, and tap-to-select now work from the vacuum's own rooms (selected rooms light up).
- **Smarter external-run learning.** App-started runs now use the robot's recorded path to work out which rooms were actually cleaned, feeding the external-run review wizard.

### Changed
- New user guides for furnished render, zone cleaning, hide-area, and the live map, plus reconciled services/data-model references.

### Fixed
- Strict-order runs now record **every** room's timing, not just the last — better ETAs for sequenced cleans.
- Learning accuracy: recharge-drain bias guard, attribution-confidence marker, and rescuing the first cleaned room when the device's cleaned-area is stale.
- Roborock live-room refresh now targets the right entity and self-disables cleanly when the service isn't available.

### How to update
- **HACS:** open Vacuum Agent in HACS, update to **v1.2.0**, then restart Home Assistant.
- **Manual:** replace `custom_components/eufy_vacuum/` with the v1.2.0 tree and restart.

> Furnished render, zone cleaning, and live robot tracking need a **live-map backdrop** — Eufy via the [eufy-clean fork](https://github.com/smcneece/eufy-clean) or Roborock. Plain (non-fork) Eufy still works fully; these live-map features simply stay hidden until a live-map entity is available.
