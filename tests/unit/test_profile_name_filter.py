"""R2-BUG-2 — the saved-profile filter axis.

The PROFILE chip row used to be keyed on ``profile_key``, which ``_room_profile_key``
builds as a per-room SETTINGS SIGNATURE — ``slug::profile::mode::intensity::fan::water::
passes::carpet::edge``. That is the right key for pooling learned timings and the wrong
one for a user-facing filter:

  * it embeds the room slug, so the chip label read "Dining Room Vacuum Quick · Quick ·
    Quiet" and the separate ROOM row above it became redundant;
  * the option list grew as rooms x profiles x settings;
  * and ``_job_matches`` could not honour it at all — a job spans several rooms — so the
    Jobs count and Runs list silently stayed unfiltered while the chip rendered active.

``profile_name`` is room-independent, so all three lists mean the same thing under it.
These pin the seam end to end; ``_room_profile_key`` is deliberately untouched.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.learning.utils import _room_profile_key


def _room(slug, selected, resolved=None, **over):
    base = {
        "slug": slug,
        "selected_profile_name": selected,
        "resolved_profile_name": resolved if resolved is not None else selected,
        "clean_mode": "vacuum",
        "clean_intensity": "quick",
        "fan_speed": "quiet",
        "water_level": "",
        "clean_passes": 1,
        "edge_mopping": False,
    }
    base.update(over)
    return base


def test_profile_key_is_room_scoped_which_is_why_it_cannot_filter_jobs():
    """[PN-1] The premise. The same profile in two rooms yields two DIFFERENT keys, so no
    single profile_key can describe a multi-room job."""
    kitchen = _room_profile_key(_room("kitchen", "vacuum_quick"))
    dining = _room_profile_key(_room("dining_room", "vacuum_quick"))

    assert kitchen != dining, "signature is not room-scoped — the premise of R2-BUG-2 is stale"
    assert kitchen.startswith("kitchen::")
    assert "vacuum_quick" in kitchen
    # ...while the saved-profile NAME is shared, which is what makes it filterable.
    assert _room("kitchen", "vacuum_quick")["selected_profile_name"] == \
           _room("dining_room", "vacuum_quick")["selected_profile_name"]


def test_settings_change_forks_the_signature_but_not_the_profile_name():
    """[PN-2] Why the option list exploded: one room on one profile still forks a new
    signature per settings variation, and each fork became its own chip."""
    quiet = _room_profile_key(_room("kitchen", "vacuum_quick", fan_speed="quiet"))
    turbo = _room_profile_key(_room("kitchen", "vacuum_quick", fan_speed="turbo"))
    assert quiet != turbo
    # The name is stable across both — one chip, not two.
    assert _room("kitchen", "vacuum_quick", fan_speed="quiet")["selected_profile_name"] == \
           _room("kitchen", "vacuum_quick", fan_speed="turbo")["selected_profile_name"]
