"""Proof: remap_confirmed_floor_types loses confirmations on a renumbering SHIFT."""
from custom_components.eufy_vacuum.onboarding.manager import OnboardingManager

VAC, MAP = "vacuum.test", "1"


def run(id_remap, confirmed_before):
    data = {"onboarding": {VAC: {MAP: {"floor_types_confirmed": dict(confirmed_before)}}}}
    OnboardingManager(data, None).remap_confirmed_floor_types(
        vacuum_entity_id=VAC, map_id=MAP, id_remap=id_remap)
    return data["onboarding"][VAC][MAP]["floor_types_confirmed"]


cases = [
    ("no overlap  {1:10, 2:20}", {1: 10, 2: 20}, {"1": True, "2": True}, {"10": True, "20": True}),
    ("shift by 1  {1:2, 2:3, 3:4}", {1: 2, 2: 3, 3: 4},
     {"1": True, "2": True, "3": True}, {"2": True, "3": True, "4": True}),
    ("swap        {1:2, 2:1}", {1: 2, 2: 1}, {"1": True}, {"2": True}),
]
for label, remap, before, expected in cases:
    got = run(remap, before)
    ok = got == expected
    print(f"{'OK  ' if ok else 'FAIL'}  {label}")
    print(f"        before={before}")
    print(f"        expect={expected}")
    print(f"        got   ={got}")
    if not ok:
        lost = sorted(set(expected) - set(got))
        print(f"        -> rooms that LOST a confirmation and now block start: {lost}")
