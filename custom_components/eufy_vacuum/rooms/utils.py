"""
Shared string utilities for the rooms subsystem.

Contains pure functions with no HA or brand dependencies that are used
by both the framework room modules and the brand adapters.
"""


def slugify_room_name(name: str) -> str:
    """Return a stable, URL-safe slug derived from a room name."""
    return (
        str(name)
        .strip()
        .lower()
        .replace("'", "")
        .replace('"', "")
        .replace("&", "and")
        .replace(" ", "_")
    )