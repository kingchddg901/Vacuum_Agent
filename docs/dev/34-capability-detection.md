# 34 — Capability Detection

**Scope.** How the framework decides what a vacuum can do: the two kinds of adapter hint and why
they are not the same rule, and the diagnostic vocabulary that records not only which entity won a
role but how and why the alternatives lost. What a brand declares is
[22 — The Adapter Contract](22-adapter-contract.md); the two shipped answers are
[23](23-eufy-adapter.md) and [24](24-roborock-adapter.md).

`core/capabilities.py::detect_capabilities` holds no brand knowledge. Everything vacuum-specific —
the entity candidates, the model family, the hints, the maintenance catalog — arrives as arguments
from the adapter's registration.

The module spends a substantial share of its length on **explaining its own answers**, and that is
the part worth reading. A capability map that says only *yes* or *no* cannot be debugged by the
person whose install it is wrong on.

---

## 1. Two hint rules, and confusing them was a real defect

A hint is a model-based flag from the adapter. There are two ways one is combined with what the
probe found, and they are deliberately different:

**Permissive — hint OR entity presence.** A `True` hint means supported even when the entity is
absent; `False` or absent falls back to what the probe saw. This is right for features whose
evidence is an entity that may simply not be exposed yet.

**Authoritative — the hint wins outright.** For capabilities a brand can categorically *not* do, a
declared `False` must beat the derived value. Water control, edge mopping, passes, custom room
config, room clean and zone clean use this rule.

The failure that produced the split is named in place: **a hardcoded default is unreachable by any
adapter**, which is how edge-mopping support stayed `True` for a brand that declared it `False`.
Under the permissive rule a declared `False` is indistinguishable from silence, so a brand saying
"I cannot do this" and a brand saying nothing produce the same answer — and the one that spoke is
the one that gets a control it cannot honour.

Zone clean is the case caught mid-flight. Both shipped adapters hardcoded it `True` in their config
dicts, which is exactly the unreachable-default shape: a model that categorically cannot zone-clean
had nothing to declare *against*. `True` remains the default because both brands do support it — but
it is now a hint a model catalog can override. ([24 §8](24-roborock-adapter.md) records that the
brand end of that seam is still unwired.)

---

## 2. A typo in a hint is silent, so the key set is validated

`core/capabilities.py::KNOWN_CAPABILITY_HINTS` is the complete set of flags this module reads, and
the reason it exists is sharper than documentation:

A hint whose key is not in the set is a **silent no-op** — the lookup simply misses and the derived
value stands. So a brand declaring `supports_zone_cleen: False` is ignored exactly as thoroughly as
one declaring nothing. That is the same silent-wrong-answer shape the authoritative rule exists to
prevent, arriving by a different route.

`adapters/registry.py::_validate_adapter` checks every declared hint against the set, so the typo
fails at registration rather than surfacing months later as "why is this control showing?". The set
is pinned by a contract test against the reads themselves, so the two cannot drift.

---

## 3. Absent and disabled are different answers

Both used to produce a bare `None`, and they need **opposite fixes**: an absent entity is our
problem, a disabled one is a toggle in the user's own interface. A support round-trip was spent on
exactly that ambiguity, with both position sensors present-but-disabled on the device.

The resolution outcome is now first-class, and the four states are distinguishable:

| outcome | means |
|---|---|
| `core/capabilities.py::REASON_ABSENT` | no such entity exists |
| `core/capabilities.py::REASON_DISABLED` | it exists and the user has disabled it |
| `core/capabilities.py::REASON_REGISTERED_NO_STATE` | registered but reporting nothing yet |
| `core/capabilities.py::REASON_OVERRIDE_UNRESOLVED` | §4 |

The general rule this earns: **a diagnostic that collapses two causes into one symptom costs more
than it saves**, because the person reading it cannot tell which of the two fixes applies, and
neither can whoever they ask.

---

## 4. A user override that stopped working must be visible

When a user pins an entity to a role and that entity is later renamed or deleted, resolution
**falls through to the normal candidates** rather than pinning a dead id — the role still resolves
and the install keeps working.

That is the right behaviour and it is also dangerous, because the user's stated intent has been
silently replaced by the framework's guess. `core/capabilities.py::REASON_OVERRIDE_UNRESOLVED`
exists so the substitution is reported rather than hidden. The comment states the principle
directly:

> silently substituting our guess for their stated intent is the failure mode this whole effort
> exists to remove

Falling back and saying so is a different thing from falling back quietly, and only the second is a
bug.

---

## 5. The answer records how it was reached

Two more vocabularies ride along with every resolved role.

**Which rung decided a contested role** — object id, translation key, state class, or magnitude.
These are first-class values rather than prose because, in the comment's own framing, six months
later *"chosen by: magnitude"* sends you somewhere completely different from *"chosen by: manual
override"*. Magnitude is the last rung and requires a competing candidate to be substantially
larger before size alone decides, so it cannot casually overturn a name match.

**Where the winner came from** — derived, an override, or the device-sibling rescue — is recorded
for **every** role, not only contested ones. The reason is precise: without it, the diagnostic table
labels an entity a name match when the sibling search actually rescued it, which asserts something
visibly false. The comment calls that *manufactured confidence*, and the surface exists to catch it.

That is the whole design in one line: **a detection report that cannot be wrong about its own
provenance is worth more than one that is merely usually right about its conclusions.**

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| a hint is a hint | there are two rules, and a declared `False` is only authoritative under one of them — §1 |
| declaring a capability `False` disables it | under the permissive rule it is indistinguishable from silence — §1 |
| a misspelled hint fails loudly | it is a silent no-op at runtime; the registry validator is what makes it loud — §2 |
| a missing entity means the feature is unsupported | it may be disabled by the user, which is a different fix — §3 |
| an unresolved override is an error state | resolution falls through and the install works; the point is that it is reported — §4 |
| provenance is recorded for contested roles | it is recorded for every role, precisely so the uncontested ones cannot lie — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
