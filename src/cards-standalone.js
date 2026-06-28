// Global cards bundle — registers ONLY the standalone Lovelace cards (the
// single-room room-card and the multi-room dashboard card), with NO panel.
//
// The integration loads this on every HA page via frontend.add_extra_module_url,
// so the cards are defined even on a cold dashboard that never opens the sidebar
// panel (a wall tablet, a hard refresh). The full panel bundle (all-cards.js)
// also defines these cards when it loads; the defineCard guard in _shared.js
// makes the double-registration a no-op.
import "./room-card.js";
import "./cards/dashboard-card.js";
