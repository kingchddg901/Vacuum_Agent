r"""Mechanical doc-vs-code drift check for docs/advanced/ — the CONTRACT surface.

WHY THIS TREE, AND WHY A SCRIPT. The campaign reads `docs/dev/` (how it works)
and, as of charter delta 9, `docs/user-guide/` (how it is MEANT to be used).
`docs/advanced/` is neither: it is the contract users write code against —
service parameters, event names, and 700+ lines of automation YAML that people
copy verbatim. Drift here does not confuse a reader, it silently breaks their
automations.

It is also the one doc tree that does not need a reading pass. `03-services.md`
is a 1:1 mirror (111 of its 130 headings are literal service names, each followed
by a `| \`param\` | Required |` table), `02-events.md` heads each section with the
literal event name, and the automation examples are executable YAML. All three
are DIFFABLE. An agent re-reading 4,495 lines would mostly re-confirm what this
proves in a second.

WHAT IT CHECKS
  1. services   -- registered (services.yaml) vs documented (03-services.md headings)
  2. parameters -- per service, schema fields vs the doc's parameter table
  3. events     -- const.py EVENT_* values vs 02-events.md headings
  4. examples   -- every `service: eufy_vacuum.x` in 04-automation-examples.md
                   resolves, and every key under its `data:` is a real field

DIRECTION MATTERS. A doc naming something that does not exist is a BREAK: a user
copies it and gets an error. Something real but undocumented is a GAP: less
urgent, and sometimes correct (maintainer-only tooling, or a surface that is
mid-rebuild and should not be advertised yet). They are reported separately and
only breaks set the exit code.

    python .claude/notes/_check_advanced_doc_drift.py

Exit 1 on any BREAK, so it can gate the doc-vs-source sweep.
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVICES_YAML = ROOT / "custom_components/eufy_vacuum/services.yaml"
CONST_PY = ROOT / "custom_components/eufy_vacuum/const.py"
DOC_SERVICES = ROOT / "docs/advanced/03-services.md"
DOC_EVENTS = ROOT / "docs/advanced/02-events.md"
DOC_EXAMPLES = ROOT / "docs/advanced/04-automation-examples.md"

#: Undocumented on purpose. Maintainer-only tooling has no place in a user-facing
#: reference, and a surface that is mid-rebuild must not be advertised as stable.
#: Anything here is exempt from the GAP report but NOT from the break checks --
#: if a doc references one, that is still drift.
DELIBERATELY_UNDOCUMENTED = {
    # flight recorder: maintainer tooling, deliberately not user-facing
    "debug_capture_start", "debug_capture_stop", "debug_capture_status",
    "debug_capture_dump", "debug_log_live_room",
    # queue-break plumbing: the Phased Jobs surface, mid-rebuild 2026-08
    "add_queue_break", "remove_queue_break", "set_queue_breaks",
    "clear_queue_breaks", "get_queue_steps",
}

breaks: list[str] = []
gaps: list[str] = []


def _service_schema() -> dict[str, set[str]]:
    """{service: {field, ...}}. services.yaml is the UI description file, NOT the
    registry -- there are 172 async_register calls against 124 yaml entries, so a
    service can be perfectly real with no yaml block (analyze_map_image is).
    Treating yaml as the registry produced 19 false "not registered" breaks on the
    first run. Fields are only known for yaml-described services; the rest are
    registered with fields=None, meaning "cannot check params", not "no params"."""
    raw = yaml.safe_load(SERVICES_YAML.read_text(encoding="utf-8")) or {}
    out: dict[str, set[str] | None] = {
        name: set((body or {}).get("fields") or {}) for name, body in raw.items()
    }
    const = (ROOT / "custom_components/eufy_vacuum/const.py").read_text(encoding="utf-8")
    names = dict(re.findall(r'^(SERVICE_[A-Z0-9_]+)\s*=\s*"([a-z0-9_]+)"', const, re.M))
    for py in (ROOT / "custom_components/eufy_vacuum").rglob("*.py"):
        src = py.read_text(encoding="utf-8", errors="replace")
        for sym in re.findall(r"async_register\(\s*DOMAIN,\s*(SERVICE_[A-Z0-9_]+)", src):
            real = names.get(sym)
            if real and real not in out:
                out[real] = None            # registered, no yaml -> params unknown
    return out


def _documented_services() -> tuple[dict[str, set[str]], dict[str, str]]:
    """({service: {tabulated param}}, {service: full section text}).

    The body is returned too because not every service tabulates its parameters —
    `resegment_external_run` explains `expected_rooms` / `active_boundaries` in
    prose. Reporting those as undocumented because they are not in a TABLE is a
    formatting complaint dressed as a drift finding."""
    text = DOC_SERVICES.read_text(encoding="utf-8")
    # split on service-name headings; keep the body until the next heading
    parts = re.split(r"^#{2,4}\s+`?([a-z0-9_]+)`?\s*$", text, flags=re.M)
    out: dict[str, set[str]] = {}
    bodies: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        name, body = parts[i], parts[i + 1]
        # ONLY tables headed "| Parameter |". The doc also uses | Field | for
        # RESPONSE shapes, | Source |, and | Event | -- reading every table made
        # response fields and enum values look like undeclared parameters (21 of
        # the first run's 40 false breaks).
        params: set[str] = set()
        in_param_table = False
        for line in body.splitlines():
            if not line.startswith("|"):
                in_param_table = False
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells:
                continue
            if cells[0].lower() == "parameter":
                in_param_table = True
                continue
            if set(cells[0]) <= {"-", ":", " "}:      # separator row
                continue
            if not in_param_table:
                continue
            m = re.fullmatch(r"`([a-z0-9_]+)`", cells[0])
            if m:
                params.add(m.group(1))
        # UNION, never assign. A service can head more than one section -- the
        # canonical `### name` with its parameter table, plus a `#### name`
        # cross-reference elsewhere that has none. Assigning let the second,
        # tableless occurrence overwrite the first and reported every one of that
        # service's parameters as undocumented (9 services, 30+ phantom gaps).
        out.setdefault(name, set()).update(params)
        bodies[name] = bodies.get(name, "") + body
    return out, bodies


def _registered_events() -> set[str]:
    """Every event constant, ANYWHERE, in either spelling. const.py uses
    f"{DOMAIN}_x", but EVENT_ROOM_COMPLETED is a plain literal declared locally in
    mapping/tracker.py:40 -- scanning const.py alone reported a real, fired,
    correctly-documented event as fictional."""
    out: set[str] = set()
    for py in (ROOT / "custom_components/eufy_vacuum").rglob("*.py"):
        src = py.read_text(encoding="utf-8", errors="replace")
        out |= {f"eufy_vacuum_{m}" for m in
                re.findall(r'EVENT_[A-Z0-9_]+\s*=\s*f"\{DOMAIN\}_([a-z0-9_]+)"', src)}
        out |= set(re.findall(r'EVENT_[A-Z0-9_]+\s*=\s*"(eufy_vacuum_[a-z0-9_]+)"', src))
    return out


def _documented_events() -> set[str]:
    text = DOC_EVENTS.read_text(encoding="utf-8")
    return set(re.findall(r"^#{2,4}\s+`?(eufy_vacuum_[a-z0-9_]+)`?\s*$", text, re.M))


def _example_calls() -> list[tuple[int, str, set[str]]]:
    """(line_no, service, data_keys) for each eufy_vacuum service call in the
    examples. Deliberately regex-based, not a YAML load: these blocks are
    documentation snippets with elisions and templates that a strict loader
    rejects, and a checker that cannot read the file it checks is useless."""
    text = DOC_EXAMPLES.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[tuple[int, str, set[str]]] = []
    for idx, line in enumerate(lines):
        m = re.search(r"^\s*(?:-\s*)?(?:service|action):\s*eufy_vacuum\.([a-z0-9_]+)", line)
        if not m:
            continue
        indent = len(line) - len(line.lstrip())
        keys: set[str] = set()
        in_data = False
        data_indent = None
        for nxt in lines[idx + 1:]:
            if not nxt.strip():
                continue
            n_indent = len(nxt) - len(nxt.lstrip())
            if n_indent <= indent and not nxt.lstrip().startswith("data"):
                break                                  # next block
            if re.match(r"^\s*data:\s*$", nxt):
                in_data, data_indent = True, n_indent
                continue
            if in_data:
                if data_indent is not None and n_indent <= data_indent:
                    break
                km = re.match(r"^\s*([a-z0-9_]+):", nxt)
                if km:
                    keys.add(km.group(1))
        out.append((idx + 1, m.group(1), keys))
    return out


def main() -> int:
    schema = _service_schema()
    documented, bodies = _documented_services()

    print(f"services.yaml: {len(schema)} registered")
    print(f"03-services.md: {len(documented)} documented\n")

    # 1 + 2 -- services and their parameters
    for name in sorted(set(documented) - set(schema)):
        breaks.append(f"03-services.md documents `{name}`, which is NOT registered "
                      f"-- a user copying it gets 'service not found'")
    for name in sorted(set(schema) - set(documented) - DELIBERATELY_UNDOCUMENTED):
        gaps.append(f"`{name}` is registered but has no section in 03-services.md")

    for name in sorted(set(schema) & set(documented)):
        if schema[name] is None:
            continue                        # registered without a yaml block
        ghost = documented[name] - schema[name]
        missing = schema[name] - documented[name]
        for p in sorted(ghost):
            breaks.append(f"`{name}` documents parameter `{p}`, which the schema "
                          f"does not accept -- a user passing it gets a validation error")
        for p in sorted(missing):
            # prose counts. Only flag a parameter the section never names at all.
            if re.search(rf"`{re.escape(p)}`", bodies.get(name, "")):
                continue
            gaps.append(f"`{name}` accepts `{p}` and the section never mentions it")

    # 3 -- events
    reg_ev, doc_ev = _registered_events(), _documented_events()
    print(f"const.py: {len(reg_ev)} events   02-events.md: {len(doc_ev)} documented\n")
    for e in sorted(doc_ev - reg_ev):
        breaks.append(f"02-events.md documents event `{e}`, which is never fired "
                      f"-- an automation triggering on it never runs")
    for e in sorted(reg_ev - doc_ev):
        gaps.append(f"event `{e}` is fired but undocumented")

    # 4 -- the automation examples users copy
    calls = _example_calls()
    print(f"04-automation-examples.md: {len(calls)} service calls\n")
    for line_no, name, keys in calls:
        if name not in schema:
            breaks.append(f"04-automation-examples.md:{line_no} calls "
                          f"`eufy_vacuum.{name}`, which is NOT registered")
            continue
        if schema[name] is None:
            continue
        for k in sorted(keys - schema[name] - {"entity_id", "target", "response_variable"}):
            breaks.append(f"04-automation-examples.md:{line_no} passes `{k}` to "
                          f"`{name}`, which does not accept it")

    print("=" * 78)
    if breaks:
        print(f"BREAKS ({len(breaks)}) -- a user following the docs hits an error:")
        for b in breaks:
            print(f"   {b}")
    else:
        print("BREAKS: none -- nothing documented is missing or misnamed in code")
    print()
    if gaps:
        print(f"GAPS ({len(gaps)}) -- real but undocumented; triage, do not gate:")
        for g in gaps:
            print(f"   {g}")
    else:
        print("GAPS: none")
    print()
    print(f"exempt from GAPS by design: {len(DELIBERATELY_UNDOCUMENTED)} "
          f"(maintainer tooling + mid-rebuild queue-break surface)")
    return 1 if breaks else 0


if __name__ == "__main__":
    sys.exit(main())
