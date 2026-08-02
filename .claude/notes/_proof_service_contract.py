"""Proof RP-031 (RF-14 + RF-05; Q9) — mutation handlers whose refusal cannot reach the caller.

RP-031 is the largest packet in the campaign: 39 finding_ids over ~60 handlers in 8 service
modules. `_proof_service_refusal_ordering.py` drives ONE fully-specified example (RF-05a,
apply_run_profile). This is the packet's OWN named shape for the rest — "table-driven over
the handler matrix" — built the way its tests_to_add_or_modify describes: a GENERATED
conformance table, not sixty hand-written cases.

THE CONTRACT (Q9). A service that can refuse must let the caller find out. In HA there are
exactly two ways: return a response (which requires `supports_response` at registration) or
raise (ServiceValidationError / HomeAssistantError). A handler that does NEITHER and returns
a refusal dict has that dict silently discarded by the service layer — the caller sees a
successful call that did nothing. That is the "refusal dropped (None returned)" and
"success-shaped no-op" in the packet's expected_before.

WHAT THIS DRIVES. Every `hass.services.async_register(DOMAIN, SERVICE_X, handler, ...)` in
the integration is parsed from source, classified read-vs-mutation by its verb, and checked
for a refusal channel. A mutation handler with no `supports_response` and no raise anywhere
in its body cannot report a refusal, by construction — no fixture required, no behaviour
simulated. The AST is the evidence.

Deliberately NOT driven: the per-handler ORDERING findings (05a/05b — refuse before the
mutation rather than after). Ordering is a property of a specific handler's body and needs
its own case each; `_proof_service_refusal_ordering.py` is the template, and the packet
sequences those per-module anyway ("no two modules in one commit").

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_service_contract.py
"""

from __future__ import annotations

import ast
import pathlib
import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

ROOT = pathlib.Path("custom_components/eufy_vacuum")

# Verbs that MUTATE. A handler named for one of these can refuse, so it owes the caller a
# way to hear about it. `get_*` reads are exempt: a read has nothing to refuse.
MUTATION_VERBS = (
    "save_", "set_", "delete_", "remove_", "add_", "clear_", "start_", "stop_", "pause_",
    "resume_", "cancel_", "apply_", "overwrite_", "rename_", "import_", "export_",
    "create_", "update_", "build_", "retry_", "reset_", "rebuild_", "finalize_",
    "acknowledge_", "adjust_", "upload_", "wash_", "dry_", "empty_", "discard_",
    "confirm_", "reanchor_", "resegment_", "exclude_", "restore_", "revert_", "run_",
    "observe_", "discover_", "process_", "record_", "reconcile_", "analyze_",
)


def _service_names() -> dict[str, str]:
    """SERVICE_CONST -> literal service name, from every const assignment in the tree."""
    out: dict[str, str] = {}
    for path in ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:      # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id.startswith("SERVICE_"):
                        if isinstance(node.value.value, str):
                            out[tgt.id] = node.value.value
    return out


def _registrations() -> list[dict]:
    """Every async_register call: the service, its handler name, and whether it declares
    supports_response. Parsed from source — no import side effects, no HA required."""
    names = _service_names()
    found: list[dict] = []
    for path in sorted(ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError:      # pragma: no cover
            continue
        # Per function: its source (to spot delegation) and whether it contains a real
        # `raise`. Counted as AST nodes, not a substring — "raise" appears in docstrings
        # and comments throughout this codebase, and a table built on text matching would
        # quietly mark voiceless handlers as fine.
        funcs = {
            n.name: {
                "src": ast.get_source_segment(text, n) or "",
                "raises": any(isinstance(x, ast.Raise) for x in ast.walk(n)),
            }
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "async_register"):
                continue
            if len(node.args) < 3:
                continue
            svc_arg, handler_arg = node.args[1], node.args[2]
            service = (
                names.get(svc_arg.id) if isinstance(svc_arg, ast.Name)
                else svc_arg.value if isinstance(svc_arg, ast.Constant) else None
            )
            handler = handler_arg.id if isinstance(handler_arg, ast.Name) else None
            if not service:
                continue
            declares = any(
                kw.arg == "supports_response" for kw in node.keywords
            )
            # Follow ONE level of delegation. Most handlers here are two-line wrappers
            # around a module-level `_handle_*`, so scanning only the wrapper would call
            # a handler voiceless when its delegate raises — a false positive, and a
            # generated table nobody can trust is worse than no table.
            entry = funcs.get(handler or "", {"src": "", "raises": False})
            raises = entry["raises"]
            for callee, callee_entry in funcs.items():
                if callee != handler and f"{callee}(" in entry["src"]:
                    raises = raises or callee_entry["raises"]
            found.append({
                "service": service, "handler": handler, "file": str(path),
                "supports_response": declares,
                "raises": raises,
                "mutates": service.startswith(MUTATION_VERBS),
            })
    return found


def case_mutation_handlers_cannot_refuse(proof: H.Proof) -> None:
    regs = _registrations()
    mutations = [r for r in regs if r["mutates"]]
    # No response channel AND no raise -> a refusal dict is discarded by the service layer.
    voiceless = sorted(
        r["service"] for r in mutations
        if not r["supports_response"] and not r["raises"]
    )
    reads = [r for r in regs if not r["mutates"]]

    proof.case(
        f"every registered mutation service ({len(mutations)} of {len(regs)}) — can it "
        f"tell the caller it refused?",
        before=bool(voiceless),
        before_msg=f"refusal dropped — {len(voiceless)} mutation handler(s) declare no "
                   "supports_response and raise nothing, so a refusal they return is "
                   "discarded by the service layer and the caller sees a successful call "
                   "that did nothing",
        after=not voiceless,
        after_msg="every mutation handler either declares supports_response or raises, so "
                  "a refusal always reaches the caller",
        detail=f"registrations parsed={len(regs)} (mutation {len(mutations)} / read "
               f"{len(reads)}) · WITHOUT a refusal channel ({len(voiceless)}): "
               + (", ".join(voiceless) if voiceless else "none"),
    )


def main() -> None:
    proof = H.Proof("RP-031", "mutation handlers whose refusal cannot reach the caller")
    case_mutation_handlers_cannot_refuse(proof)
    proof.finish()


H.run(main)
