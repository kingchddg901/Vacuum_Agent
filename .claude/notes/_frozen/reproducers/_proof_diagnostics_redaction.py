"""Proof RP-039 (RF-33) -- DIAG-2 + DIAG-4: diagnostics leaks secrets in cleartext.

Two cases, out of 29 finding_ids across two rollback groups (teardown
ledger-joining, RF-16, and diagnostics/debug honesty, RF-33) spanning 11
files. Both cases drive the REAL async_get_config_entry_diagnostics
(diagnostics.py:533-574) end to end -- no manager lifecycle beyond one
raising method is needed since the packet's own named example hits an
early-return branch. The rest of RF-16 (panel ledger, setup unwind,
services-table derivation, water/debug auto-stop ledger joins,
per-vacuum teardown) and RF-33 (debug switch ledger, area validation,
status() field clearing, dump filename suffix, the other repr(err) sinks,
dead _SENTINELS, live_refresh PERMANENT classification) are NOT driven
here -- left for follow-up, each independent.

DELEGATION CHECKED: the packet says DIAG-2 shares "the same masking seam as
RP-004" (already-landed flight-recorder redaction). Read debug_capture.py:
_DEFAULT_REDACTORS (line 71-79) is a real regex matching token/password/
api_key/secret/bearer patterns case-insensitively and replacing the
captured VALUE with the literal string "\xabredacted\xbb"; _redact() (line
89-92) applies it. This IS a real, working, reusable seam -- confirmed
directly, not assumed from the packet's claim.

  DIAG-2: diag["vacuums_error"] = repr(err) (line 565) sinks a raised
  exception's repr() completely unredacted into the diagnostics dump users
  are told to attach to GitHub issues. An upstream call whose exception
  message happens to embed a credential (a common shape for HTTP client
  errors: "401: api_key=... invalid") leaks it in cleartext.
  DIAG-4: diag["entry"]["title"] = entry.title (line 539) is never passed
  through async_redact_data (unlike entry.data/entry.options on the very
  next two lines) -- a user-set config-entry title containing anything
  sensitive ships unredacted.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_diagnostics_redaction.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.const import DOMAIN, DATA_RUNTIME   # noqa: E402
from custom_components.eufy_vacuum.diagnostics import async_get_config_entry_diagnostics   # noqa: E402
from custom_components.eufy_vacuum import debug_capture as _debug_capture   # noqa: E402

SECRET = "sk_live_should_not_leak_abc123"


class _FakeEntry:
    title = f"Alfred (api_key={SECRET})"
    version = 1
    data: dict = {}
    options: dict = {}
    runtime_data = None


def main() -> int:
    proof = H.Proof("RP-039", "DIAG-2 + DIAG-4: config-entry diagnostics leak secrets unredacted")
    import asyncio

    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)

    def _raise_with_secret():
        raise RuntimeError(f"upstream auth failed: api_key={SECRET} status=401")
    mgr.get_known_vacuum_ids = _raise_with_secret
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr

    diag = asyncio.run(async_get_config_entry_diagnostics(hass, _FakeEntry()))
    vacuums_error = str(diag.get("vacuums_error", ""))
    entry_title = str(diag.get("entry", {}).get("title", ""))

    # Independent confirmation that a redacted rendering IS achievable via the
    # real, already-landed redactor -- not a hypothetical "some future fix".
    redacted_would_be = _debug_capture._redact(vacuums_error)

    proof.case(
        "DIAG-2: get_known_vacuum_ids raises an exception whose message embeds an api_key",
        before=(SECRET in vacuums_error),
        before_msg="diag['vacuums_error'] = repr(err) sinks the raw "
                   "exception text verbatim -- the secret ships in the "
                   "diagnostics dump exactly as raised",
        after=(SECRET not in vacuums_error),
        after_msg="the repr(err) sink is routed through debug_capture's "
                  "existing redactor before landing in the diagnostics "
                  "dict -- confirmed the redactor itself already handles "
                  "this exact string: "
                  f"_redact(...) -> {redacted_would_be!r}",
        detail=f"diag['vacuums_error']={vacuums_error!r}",
    )

    proof.case(
        "DIAG-4: the config entry's own title happens to contain an api_key",
        before=(SECRET in entry_title),
        before_msg="diag['entry']['title'] = entry.title is emitted "
                   "verbatim -- unlike entry.data/entry.options on the very "
                   "next two lines, title never passes through "
                   "async_redact_data at all",
        after=(SECRET not in entry_title),
        after_msg="entry.title is redacted the same way entry.data/options "
                  "already are, closing the one field on this dict that "
                  "was skipped",
        detail=f"diag['entry']['title']={entry_title!r}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
