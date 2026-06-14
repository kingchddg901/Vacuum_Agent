#!/usr/bin/env python3
"""Export the integration's BUNDLED (preloaded) themes into the gallery.

The Pages gallery is the public "store"; the themes shipped inside the
integration are the ``core`` ones. This regenerates their export envelopes from
``themes/preloaded.py`` so the gallery carries them with ``source: "core"`` and
the Core facet is real — re-run it whenever you add or change a preloaded theme.

It loads preloaded.py DIRECTLY (the module is pure data — "no HA imports") so it
runs without a Home Assistant environment. The envelope shape matches
ThemeManager.export_theme() exactly (ok/version/exported_at/theme).

    python scripts/export-core-themes.py
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PRELOADED = REPO / "custom_components" / "eufy_vacuum" / "themes" / "preloaded.py"
OUT_DIR = REPO / "gallery" / "themes"

# "Follow HA Theme" carries no palette (it defers to the active HA theme), so it
# has nothing to show in a gallery — skip it.
SKIP_IDS = {"theme_follow_ha"}


def _load_preloaded():
    spec = importlib.util.spec_from_file_location("evcc_preloaded", PRELOADED)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    mod = _load_preloaded()
    written = []
    for spec in mod.PRELOADED_THEME_SPECS:
        theme_id = spec["id"]
        if theme_id in SKIP_IDS:
            continue
        # Same library entry the seeder builds (colors duplicated into tokens).
        entry = mod._build_preloaded_theme_entry(
            theme_id,
            spec["name"],
            colors=spec.get("colors"),
            tokens=spec.get("tokens"),
            alpha=spec.get("alpha"),
        )
        envelope = {
            "ok": True,
            "version": 1,
            "exported_at": None,
            "theme": {
                "id": theme_id,
                "name": entry.get("name", ""),
                "source": "core",
                "tokens": dict(entry.get("tokens", {})),
                "colors": dict(entry.get("colors", {})),
                "alpha": dict(entry.get("alpha", {})),
            },
        }
        slug = theme_id.removeprefix("theme_").replace("_", "-")
        path = OUT_DIR / f"{slug}.json"
        path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(slug)

    print(f"exported {len(written)} core themes -> gallery/themes/")
    for slug in written:
        print(f"  + {slug}.json")


if __name__ == "__main__":
    main()
