"""Listener registration modules.

Each submodule owns one functional group of HA state-change / time-interval
listeners. Public surface per submodule is just:

    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None

The main __init__.py imports and dispatches; this package owns the actual
event wiring. See _common.py for shared adapter-registry lookups and the
job-finished event payload builder used across multiple listener groups.
"""
