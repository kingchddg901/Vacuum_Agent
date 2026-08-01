"""Proof for the debug_capture doc-vs-code check. Throwaway; .claude/ is git-ignored."""
import logging
from custom_components.eufy_vacuum import debug_capture as dc

dc.configure("proofpkg")
cap = dc.get_capture()
cap.start()
log = logging.getLogger("proofpkg.thing")

# 1. the SAME secret, once in the message and once in an exception message
try:
    raise ValueError("auth failed for token=SUPERSECRET123 retrying")
except ValueError:
    log.debug("handshake failed with token=SUPERSECRET123", exc_info=True)

# 2. an oversized payload in an exception, to test truncation
try:
    raise RuntimeError("payload=" + "A" * 50000)
except RuntimeError:
    log.debug("dumping payload", exc_info=True)

cap.stop()
text = dc.render_text(cap.records())

print("=== CLAIM 1: 'Secrets are masked before a record is stored' ===")
print("  secret in the MESSAGE field :", "SUPERSECRET123" in dc.render_text(
    [{**r, "exc": ""} for r in cap.records()]))
print("  secret in the DUMPED FILE   :", "SUPERSECRET123" in text)
print("  occurrences in dump         :", text.count("SUPERSECRET123"))

print("=== CLAIM 2: 'Capping each message (~2 kB, eliding the rest)' ===")
print("  MAX_MESSAGE_CHARS           :", dc.MAX_MESSAGE_CHARS)
print("  longest line in the dump    :", max(len(l) for l in text.splitlines()))
print("  total dump size             :", len(text), "chars")
print("  'elided' marker present     :", "elided" in text)
