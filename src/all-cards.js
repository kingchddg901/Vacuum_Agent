// Registers all custom card elements for the Eufy Vacuum Command Center.
import "./main.js";
import "./room-card.js";
import "./cards/dashboard-card.js";
import "./cards/profile-card.js";
import { ensureFontFacesInDocument } from "./styles/fonts.js";
import { ensureUserMaterialsLoaded } from "./textures/ensure-user-materials.js";

// live:FONT-1 -- the faces must be registered on the DOCUMENT (Chromium ignores
// @font-face inside shadow trees). Idempotent; every entry calls it so the faces
// exist no matter which bundle loads first.
ensureFontFacesInDocument();

// live:UMAT-1 -- the THREE bundles each hold their own FLOOR_TEXTURE_REGISTRY, so a
// drop-in merged in one is invisible to the others. Idempotent; every entry calls
// it, exactly as ensureFontFacesInDocument does above and for the same reason.
ensureUserMaterialsLoaded("eufy-vacuum-command-center");

