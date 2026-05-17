"""Identity constants for the Eufy adapter.

These values are specific to the Eufy brand integration and are the only
things that need to change when porting the framework to another vacuum
ecosystem.  All other constants in the parent const.py are framework-
canonical and must not be modified per-adapter.
"""

from __future__ import annotations

DOMAIN = "eufy_vacuum"
NAME = "Eufy Vacuum Manager"
VERSION = "0.9.0"

DEFAULT_TITLE = NAME

SUPPORTED_TESTED_MODEL = "Eufy X10 Pro Omni"

# Stable identifier for the Eufy X10 Pro Omni code adapter.
# Written into every registered adapter config so the framework can
# distinguish Eufy-registered configs from future brand adapters.
# The value must never change — it is persisted in registered configs.
ADAPTER_ID = "eufy_x10_pro_omni"

# Storage key for the HA Store helper. Declared explicitly rather than
# derived from DOMAIN so that framework namespace changes never silently
# migrate or lose existing install data.
# The value must never change for existing Eufy installs.
STORAGE_KEY = "eufy_vacuum.storage"
