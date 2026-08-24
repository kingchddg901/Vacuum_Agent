# 13 — How Rooms Are Found

**Scope.** The pluggable segmenter contract, the shape every engine must return, the geometry
toolkit both the CV and hand-authored paths share, and what survives of the deleted
boundary-derivation subsystem.

**None of these three files owns storage.** They compute; `mapping_services.py` persists. That
is why the CV-versus-custom split lives in a mode switch there and not in a branch here — see
[11 — A Map's Stored State](11-map-stored-state.md).

---

## 1. A failing engine returns a result

`segment_map_image` wraps the CV stack in a bare `except Exception`, logs the traceback, and
returns a **fully-shaped** `SegmentationResult` with `available: False`.

Neither alternative works. Letting the exception propagate puts a CV stack traceback in front of
a user who uploaded a picture. Returning a bare `{available: False}` breaks every consumer that
reads `result["summary"]["segment_count"]` or the diagnostics block without `.get()` — the
failure path is exactly where those consumers are least defensive.

**A shaped failure is the contract.** An engine may fail; it may not fail *differently*.

> ✅ **CORRECTED 2026-08-23.** — as a WARNING at the declaration, not as a reconciliation. The Literals now carry a
> table of declared-vs-emitted and state that off-contract is not a subset. Reconciling them
> properly is a contract change with a card-facing surface, not a widening of a type alias.
> **The `SegmentationState` and `EditReadiness` Literals do not describe what ships.** They
> declare `clean · needs_review · ambiguous` and `ready · needs_edit · blocked`. Of those six,
> only `clean` and `ready` are ever emitted. `adapters/eufy/segmentor.py::_segmentation_state`
> returns `merged_candidate`, `fragmented_candidate` or `review`; the hand-authored path writes
> a further `custom`. None of those four appears in either Literal, and they pass through
> `mapping/segmenter_engines.py::EufyCVSegmenter._reshape` unmodified.
>
> The values are **off-contract, not a subset of it** — so an exhaustive match written against
> the Literals falls through on most real data rather than on an edge case. Treat the Literals
> as the intended vocabulary and the emitted set as the live one until they are reconciled.

### Two rejection layers, deliberately unalike

A bad `mapping.segmenter_engine` is caught twice and handled differently each time:

| layer | behaviour |
|---|---|
| **registration** | requires the key when a `mapping` block exists, and reports a typo as an issue |
| **lookup** | falls back to `noop_fallback` rather than raising |

Collapse them into one and you pick a poison. Raise at lookup and a stale stored config takes
down map analysis with a `KeyError` instead of degrading to "no polygonal overlays". Validate
only at registration and a config that predates the check runs forever with an engine name
nothing resolves.

> ⚠ **Registration reports the typo; it only REFUSES a user-sourced config.**
> `adapters/registry.py::AdapterCoordinator.register_adapter_config` logs every issue and then
> raises only when `config["source"] == "config"`. Both shipped brand adapters declare
> `"source": "code"`, as would any new brand package registering at startup — so for a brand
> author the validation is **warn-only**. A typo'd `segmenter_engine` in a
> brand adapter registers intact, and the lookup layer then degrades it to `noop_fallback`
> silently. A config carrying no `source` key at all behaves the same way.

### Engines are instances, and stateless by declaration

The registry holds objects constructed at import, not classes or factories, so **every vacuum on
the install shares one engine object.** The Protocol docstring declares engines stateless from
the framework's perspective, and that declaration is what makes the sharing safe. Any per-vacuum
state an engine author adds as `self.*` leaks across vacuums silently.

> ⚠ **The brand-agnostic registry imports the Eufy CV pipeline at module level**, and the source
> marks it as the only deliberate deviation of its kind. Importing the registry therefore
> attempts the whole optional CV stack. The rejected alternative — a lazy adapter-side
> registration hook — is cleaner and was refused for a stated reason; read the block before
> "fixing" it.

---

## 2. The shared toolkit is adapter-facing, conditionally

`segment_primitives.py` is adjudicated as SDK a brand package may import freely, rather than as
scheduled architectural debt.

**That adjudication holds only while the module stays brand-neutral.** The moment an Eufy
threshold or an Eufy colour assumption lands in it, the isolation test goes on passing while the
premise is gone — the test checks the import graph, not the contents.

**`compactness` is not normalised, and must not be.** Its attainable maximum is π/4 ≈ 0.785 for
an axis-aligned square. The old docstring implied a 0–1 range where 1 means a circle, and
rescaling to match would be a reasonable-looking change that silently invalidates every
empirically tuned threshold keyed to this exact function.

**Colour features are bare chromaticity with no luminance weighting**, and the docstring says
re-adding one cannot change anything. It is not an opinion: the weights cancel exactly, so the
original luminance division could never influence output and neither clamp on that path could
bind.

---

## 3. The hand-authored path does not use the contract

There is no `custom` engine. `mapping_services.py` imports the rasteriser directly and
hand-builds a result envelope; `get_segmenter_engine("custom")` returns the noop.

**`custom` is a provenance string in stored data, not a selectable engine.**

Authored shapes are rasterised and then re-extracted through the *same* polygon extractor the CV
path uses, rather than converted directly — a rectangle is already four points, so the
round-trip is lossy and slower. What it buys is one extraction path to fix and boolean
composition for free. What it costs is that authored geometry inherits every property of the
raster transit, and **re-editing is lossy by construction**.

> ⚠ **A subtract that carves an interior hole does not leave a hole.** The extractor traces
> every closed loop and then keeps exactly one — the largest by absolute area. Multi-shape
> authoring survives only as its dominant loop.

**The mode switch never re-runs a segmenter, in either direction.** Setting the mode writes a
flag; the resolver then reads whichever store that names. A cv → custom → cv round trip
preserves both segment sets with zero re-analysis, which is precisely why both stores have to
stay independently valid.

---

## 4. What is left of boundary derivation

`boundary.py` is 40 lines: `point_in_polygon` and nothing else. The trace-to-room-polygon
subsystem — corner detection, transition scoring, line simplification — was deleted.

**There is no path from a driven trace to a room polygon.** Rooms come from CV segmentation,
hand-authored primitives, or the vendor's own segmentation.

The inclusion test is written with a strict-inequality XOR rather than the more readable
inclusive span test, and that is a guard rather than a style: the XOR can only be true when the
two vertex y-values differ, so the divisor is never zero. Swap in the span test and a horizontal
edge at exactly the test point divides by zero.

---

## 5. Common wrong assumptions

| assumption | actually |
|---|---|
| the state and readiness Literals describe what engines emit | only `clean` and `ready` of the six are ever emitted; the shipped values are off-contract, not a subset — see §1 |
| a typo'd `segmenter_engine` in a brand adapter is refused at registration | it is refused only for a user-sourced config; a code-sourced one warns and registers intact |
| `polygon_pct` is engine-produced and bbox-relative | no segmenter emits it — it is computed at read time, and it is image-relative |
| the custom path works without the science stack because the card only hides the CV button | the dependency floors differ; rasterising needs more than the card's check implies |
| "tuning is ignored" from the noop means a leftover tuning block is harmless | `validate_tuning` has no severity channel — every string it returns is an issue |
| switching to `noop_fallback` stops the card rendering room overlays | it stops **new** analysis; stored segments are still served from cache |
| the framework call sites are `manager.py` and `mapping_services.py`, per the docstring | `mapping/manager.py` does not exist — it went with the mapping split |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
