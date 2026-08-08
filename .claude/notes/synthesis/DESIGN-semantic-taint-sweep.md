# DESIGN — semantic taint sweep (Eufy vocabulary outside the Eufy boundary)

**Status: DESIGNED. Chris, 2026-08-07 — initially "not now", revised within the
hour to "may need to be done soon", and the reason is a sequencing one worth
keeping.**

Doc hygiene never blocks a release. But this sweep does not produce doc hygiene —
it produces a possible ARCHITECTURAL finding: core interpreting a provider's
vocabulary is a contract defect, its repair is a canonicalization change, and
under lifecycle §13 the DR docs must absorb that in the same commit. An
architectural change CAN block a release, and the worst time to discover one is
the week after tagging.

There is also a concrete blast radius: vocabulary values are written onto stored
rooms (the same reason the `profiles.room_profiles` leak is a stored-data change,
not a refactor), and a wrong-dialect comparison outside the adapter would affect
NON-Eufy brands specifically — Roborock users — while looking fine on the
first-brand hardware everything was developed against.

**Therefore run it as DISCOVERY ONLY, before the next release, with repair
deferred.** Discovery does not block; it informs. A clean result buys a genuinely
strong claim to ship on. A finding lets Chris decide whether it rides the release
or waits, instead of that decision being made for him by timing. This matches the
standing preference: spend capability on discovery, defer repair.

Origin: Chris + a ChatGPT review round, immediately after `test_adapter_isolation`
(ISO-1..5) landed.

## The boundary this tests — a different one

`test_adapter_isolation.py` answers **"can the Eufy adapter reach back into VA
internals?"** Four instruments (imports incl. deferred, dynamic imports, runtime
private reaches, `hass.data`) say no, apart from the one ledgered
`profiles.room_profiles` leak.

This sweep answers a different question:

> **After Eufy data crosses the adapter boundary, does anything outside the
> adapter still UNDERSTAND Eufy vocabulary?**

An adapter can be perfectly import-clean and still architecturally dirty:

```
Eufy says:        "Turbo"
adapter returns:  "Turbo"          <- no translation
core says:        if fan_speed == "Turbo": ...
```

No forbidden import anywhere. Still a leak. The correct shape is a translation in
both directions:

```
Eufy "Turbo"  ->  [eufy adapter]  ->  canonical VA term   ->  core
canonical VA intent  ->  [eufy adapter]  ->  Eufy command/value/payload
```

## The invariant — carried vs interpreted

Stronger than "no Eufy words outside Eufy", because some raw provider data
legitimately must survive for diagnostics and provenance:

> **Outside the Eufy boundary, provider-specific values may be CARRIED OPAQUELY,
> but they may not be INTERPRETED AS BEHAVIOR.**

Fine — a receipt that preserves provenance:

```
provider = eufy
raw_error = 17
```

Not fine — the same value steering control flow outside the translation boundary:

```
if raw_error == 17:
    retry_room_clean()
```

Same distinction for provider room IDs: core may carry an opaque provider
identifier back to the adapter, but it must not know that `5` means Kitchen to
Eufy, and it must not construct Eufy's room-clean payload itself.

## Search surface

Provider-specific strings, enum values, command names, error codes, attribute
names, payload keys, service semantics, map-state vocabulary, maintenance
component names, mode names, and brand-specific conditionals — anywhere outside
`adapters/eufy/`. Include tests, fixtures, storage fields, and the frontend: a
fossil in a fixture or a card comparison is the same leak.

## Why the yield could be real

Eufy was the first provider, so anything that looked like a universal concept
when there was only one brand is a candidate fossil: a comparison, a fixture, a
storage field, an error branch, or a frontend assumption still speaking the old
dialect after the concept was canonicalized. Two already-known adjacent findings
point the same way — the `error[]`/fault-code work and the "Eufy-isms leak in the
interpretive layer" pattern (brand ports fix core but miss
diagnostics/presentation/onboarding).

## Method notes for whoever builds it

- **Negative controls are mandatory.** A clean result means nothing unless the
  sweep has been shown to find a planted fossil — plant a canonical-looking Eufy
  string in a core comparison and confirm it is caught. This is the ISO-5 lesson
  and the W0 v2 lesson: a detector never seen firing has not been tested.
- **Expect the prose false positive.** `scripts/mock_census.py` had to move off
  regex onto AST because a regex flagged a file for DOCUMENTING the rule; the
  PF-7 pin flagged a source COMMENT for the same reason. A vocabulary sweep will
  hit this constantly — docs, comments, and test names legitimately say "Turbo".
  Distinguish an interpreted value (compared, branched on, used as a dict key
  driving behavior) from a mentioned one.
- **Carried-vs-interpreted is an AST question, not a grep question:** the value
  appearing in a `Compare`, an `if` test, or a dispatch table is the signal;
  appearing in a string assigned to a diagnostics field is not.

## The claim it would earn

If it comes back clean after deliberate negative controls:

> **VA core neither reaches into a provider nor speaks a provider's language.**

That is a materially stronger statement than "the adapters are separated", and it
is the one that makes the substitutability claim in doc 32 real rather than
structural.
