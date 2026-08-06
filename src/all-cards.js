// Registers all custom card elements for the Eufy Vacuum Command Center.
import "./main.js";
import "./room-card.js";
import "./cards/dashboard-card.js";
import "./cards/profile-card.js";
import { ensureFontFacesInDocument } from "./styles/fonts.js";

// live:FONT-1 -- the faces must be registered on the DOCUMENT (Chromium ignores
// @font-face inside shadow trees). Idempotent; every entry calls it so the faces
// exist no matter which bundle loads first.
ensureFontFacesInDocument();

