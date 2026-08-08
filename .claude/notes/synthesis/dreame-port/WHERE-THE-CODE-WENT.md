# The Dreame adapter configs live OUTSIDE the repo

Chris, 2026-08-07: **"we dont ship dreame at all now it moves out of anywhere it
cant get swept up in a commit"**.

Both blind-built configs were moved to:

    C:\Users\CKing\Documents\durable\dreame-port-fixture\
        builder-1-adapter.py
        builder-2-adapter.py

Why out of the repo rather than just git-ignored: this directory already contains
two force-added tracked files (PREDICTION.md, REFERENCE-READ.md), so a later
`git add -f` on the directory would sweep the adapter code in with them. Outside
the working tree there is no accident available.

**Nothing about Dreame ships.** No `BRAND_REGISTRARS` row, no
`ADAPTER_BUILDERS` entry, no fixture under `tests/`. The framework change the
port motivated — `discovery.room_list_shape`, a declared per-map mapping shape —
DOES ship, because it is a brand-neutral axis that was missing, not a Dreame
special case. That was the condition: "adding is ok but needs to be a new shape
not an if Dreame fix."

The analysis stays here: PREDICTION.md, REFERENCE-READ.md, and both builders'
reports — the findings are the product, the config was only the instrument.

When hardware arrives, the promotion checklist is in REFERENCE-READ.md §7 and in
the builders' reports; the completion/lifecycle gap is the blocker to settle
first (Dreame reproduces Roborock's dock-revert hazard while shipping no
cleaning binary sensor, so the documented remedy does not exist for it).
