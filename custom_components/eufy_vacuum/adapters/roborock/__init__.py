"""Roborock adapter package for the multi-brand vacuum framework.

See README.md for the Wave 1 scope and the locked design decisions.

Two public surfaces, and the split is deliberate:

- ``adapter.register_roborock_adapter_for_vacuum`` — the entry point core CALLS.
- ``const.UPSTREAM_PLATFORMS`` — the identity core READS. This package states which
  integration provides its vacuum entity; core compares and never asks the brand to
  judge itself. There is no ``is_roborock_vacuum`` any more, on purpose.
"""
