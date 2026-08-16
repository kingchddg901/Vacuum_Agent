"""Identity constants for the Eufy adapter.

These values are specific to the Eufy brand integration and are the only
things that need to change when porting the framework to another vacuum
ecosystem.  All other constants in the parent const.py are framework-
canonical and must not be modified per-adapter.
"""

from __future__ import annotations

DOMAIN = "eufy_vacuum"
NAME = "Vacuum Agent"
VERSION = "0.9.0"

DEFAULT_TITLE = NAME

SUPPORTED_TESTED_MODEL = "Eufy X10 Pro Omni"

# Stable identifier for the Eufy X10 Pro Omni code adapter.
# Written into every registered adapter config so the framework can
# distinguish Eufy-registered configs from future brand adapters.
# The value must never change — it is persisted in registered configs.
ADAPTER_ID = "eufy_x10_pro_omni"

# The HA integration domain(s) that PROVIDE this brand's vacuum entity — read from
# the ENTITY registry (`entry.platform`). This is the adapter's own identity claim;
# brand selection matches a vacuum's platform against this tuple.
#
# ⚠ THIS IS THE FIRST HONEST POSITIVE TEST FOR EUFY. brands.py long carried the note
# that Eufy had no `detect` because "the Eufy adapter never reads the device registry
# for manufacturer/model, so there is no honest positive test to write". That was true
# of the DEVICE registry — manufacturer and model are free text and routinely blank on
# real installs. The ENTITY registry's platform is neither: HA sets it from the
# providing integration's domain, always, and it cannot be blank. Verified on
# `vacuum.alfred` (platform `robovac_mqtt`) and in ptruman's issue #49 diagnostics,
# whose 65 device entities all report the same platform.
#
# A TUPLE by design. Eufy's upstream is a FORK, and `robovac_mqtt` is that fork's
# chosen domain — a rename or a second fork lands here as data, not as a code change.
# Exactly one entry is planned; the tuple only keeps that door from being painted shut.
UPSTREAM_PLATFORMS: tuple[str, ...] = ("robovac_mqtt",)

# Storage key for the HA Store helper. Declared explicitly rather than
# derived from DOMAIN so that framework namespace changes never silently
# migrate or lose existing install data.
# The value must never change for existing Eufy installs.
STORAGE_KEY = "eufy_vacuum.storage"
