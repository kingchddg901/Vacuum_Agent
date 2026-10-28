"""Two card-side keys whose validity depends on a backend fact staying true.

Most of the i18n census was the card failing to look a code up. These two are the opposite
shape: the card is now RIGHT, and stays right only while something in Python holds. Neither
fact is visible from the card, so neither can be gated there.

[SSK-*] THE SETUP WIZARD'S STEP HEADINGS. `renderers/setup.js` resolves
``setup.step_<id>`` and falls back to the backend's ``step.label`` on a miss — an English
label, in every language. Three of the five ``SETUP_STEP_IDS`` were keyed and two were not;
no adapter ships those two, so nothing was English on screen, which is exactly why nobody
would notice the day one started. The keys are forward-compat and this is what makes that
claim checkable instead of aspirational.

[OA-*] THE ORDER ADVISORY. ``_order_advisory`` returns ONE fixed sentence or None, so the
card keys on its PRESENCE and renders its own wording. That is only sound while there is
one sentence: a second would render as the first. There is no code to key on and inventing
one is a backend change, so the contract is pinned here rather than widened there.

Coverage targets
----------------
[SSK-1] every SETUP_STEP_IDS member has a `setup.step_<id>` key in en.js.
[SSK-2] the mutation control: an id with no key is reported.
[SSK-3] every id an adapter actually DECLARES is keyed — the subset that renders today.
[OA-1] `_order_advisory` has exactly one sentence, and returns None when order is honoured.
"""

from __future__ import annotations

import inspect
import pathlib
import re

import pytest

from custom_components.eufy_vacuum.planning import run_plan
from custom_components.eufy_vacuum.setup.drift import SETUP_STEP_IDS

REPO = pathlib.Path(__file__).resolve().parents[2]
EN_JS = REPO / "src" / "i18n" / "en.js"
ADAPTERS = REPO / "custom_components" / "eufy_vacuum" / "adapters"


def en_keys() -> set[str]:
    """The flat quoted keys defined in en.js (a JS module, so read as text)."""
    pattern = re.compile(r'^\s*"([a-z0-9_.]+)"\s*:')
    return {
        m.group(1)
        for m in (pattern.match(line) for line in EN_JS.read_text(encoding="utf-8").splitlines())
        if m
    }


def unkeyed(ids, keys: set[str]) -> list[str]:
    return sorted({i for i in ids if f"setup.step_{i}" not in keys})


def test_ssk_1_every_declared_step_id_has_a_heading_key() -> None:
    """[SSK-1]"""
    keys = en_keys()
    assert len(keys) > 2000, f"en.js scan found only {len(keys)} keys — the scanner is broken"
    assert len(SETUP_STEP_IDS) >= 5, "the id set shrank; this gate would pass vacuously"

    missing = unkeyed(SETUP_STEP_IDS, keys)
    assert not missing, (
        "these setup steps have no heading key, so an adapter declaring one would put the "
        "backend's English label on the wizard in all 17 languages:\n  "
        + "\n  ".join(f"setup.step_{i}" for i in missing)
    )


def test_ssk_2_an_unkeyed_step_is_reported() -> None:
    """[SSK-2] the mutation control."""
    keys = en_keys()
    assert unkeyed(set(SETUP_STEP_IDS) | {"polish_floor"}, keys) == ["polish_floor"]
    assert not unkeyed(SETUP_STEP_IDS, keys)


def test_ssk_3_the_steps_adapters_actually_declare_are_keyed() -> None:
    """[SSK-3] the subset that renders today, read from the adapters themselves.

    [SSK-1] covers the whole ID set including ids nothing ships. This narrows to what a
    user can currently see, so a failure here is live rather than forward-looking — and it
    reads the declarations rather than restating them, because a list here would be a third
    copy of a set that already exists twice.
    """
    keys = en_keys()
    declared: set[str] = set()
    for adapter in sorted(ADAPTERS.glob("*/adapter.py")):
        source = adapter.read_text(encoding="utf-8")
        for block in re.findall(r'"steps":\s*\[([^\]]*)\]', source):
            declared |= set(re.findall(r'"([a-z_]+)"', block))

    assert declared, "no adapter declares setup steps — the scan or the glob is wrong"
    assert declared <= set(SETUP_STEP_IDS), (
        f"an adapter declares a step the framework does not know: {declared - set(SETUP_STEP_IDS)}"
    )
    missing = unkeyed(declared, keys)
    assert not missing, f"steps that render today with no key: {missing}"


def test_oa_1_the_order_advisory_is_one_sentence() -> None:
    """[OA-1]"""
    source = inspect.getsource(run_plan.RunPlanManager._order_advisory)

    # Every string literal in the function body, minus the docstring.
    body = source.split('"""')[-1] if source.count('"""') >= 2 else source
    sentences = [
        s for s in re.findall(r'"((?:[^"\\]|\\.){12,})"', body)
        if not s.startswith(("capabilities.", "honors_"))
    ]
    # The sentence is written as adjacent literals across lines, so join-and-count rather
    # than count-the-literals: what matters is how many DISTINCT messages can be returned.
    assert sentences, "no advisory sentence found — did the function move or get renamed?"
    assert "advisory" in " ".join(sentences).lower(), (
        "the advisory text no longer mentions being advisory; the card's own wording may "
        "have drifted from what this returns"
    )

    # Exactly one `return` of a message, plus the early `return None`.
    returns = re.findall(r"^\s*return\b(.*)$", body, flags=re.MULTILINE)
    assert len(returns) == 2, (
        "`_order_advisory` has more than one message return, so its PRESENCE is no longer a "
        "sufficient signal and the card can no longer key on it alone: "
        f"{[r.strip()[:40] for r in returns]}"
    )
    assert any(r.strip() == "None" for r in returns), "the honours-order early return is gone"


@pytest.mark.parametrize("honours,rooms,expect_none", [
    (True, [1, 2, 3], True),    # the brand honours order — nothing to advise
    (False, [1], True),         # a single room — order is moot
    (False, [1, 2], False),     # the one case that advises
])
def test_oa_2_the_advisory_fires_only_where_order_is_both_ignored_and_plural(
    honours: bool, rooms: list[int], expect_none: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[OA-2] a gate over a function that always answers the same thing proves nothing."""
    monkeypatch.setattr(run_plan, "adapter_honors_clean_order", lambda _vid: honours)
    manager = object.__new__(run_plan.RunPlanManager)
    result = run_plan.RunPlanManager._order_advisory(
        manager, vacuum_entity_id="vacuum.test", included_room_ids=rooms
    )
    if expect_none:
        assert result is None
    else:
        assert result and "advisory" in result.lower()
