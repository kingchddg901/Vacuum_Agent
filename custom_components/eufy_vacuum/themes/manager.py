"""ThemeManager — owns theme library CRUD, per-vacuum draft state, and
update callbacks.

Constructed inside EufyVacuumManager after storage is loaded.  Receives a
direct reference to the integration's root data dict and reads/writes
data["theme"] in place — no separate storage handle needed.

Callback contract
-----------------
Callers register via ``register_update_callback(cb)`` where ``cb`` is a
callable that accepts ``vacuum_entity_id: str | None``.  Pass ``None`` for
library-wide mutations (rename, delete, import); pass the vacuum entity ID
for per-vacuum mutations (save_as_new, set_active, update_draft, revert).
The sensor platform uses this to push state writes without polling.
"""

from __future__ import annotations

import logging
from datetime import datetime as _dt
from typing import Any

_LOGGER = logging.getLogger(__name__)


class ThemeManager:
    """Manages the theme library and per-vacuum draft state."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialise with a reference to the integration's root data dict.

        Seeds the theme sub-tree and runs the preloaded-library check so
        subsequent read paths never need to iterate PRELOADED_THEME_SPECS.
        """
        from .preloaded import ensure_preloaded_theme_library

        self._data = data
        self._data.setdefault("theme", {})
        self._data["theme"].setdefault("library", {})
        self._data["theme"].setdefault("default_theme_id", None)
        self._data["theme"].setdefault("vacuums", {})
        ensure_preloaded_theme_library(self._data["theme"])
        self._update_callbacks: list = []

    # ------------------------------------------------------------------
    # Callback management
    # ------------------------------------------------------------------

    def register_update_callback(self, callback) -> None:
        """Register a callback to fire when theme state changes."""
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def unregister_update_callback(self, callback) -> None:
        """Unregister a theme update callback."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    def _notify_updated(self, *, vacuum_entity_id: str | None = None) -> None:
        """Fire all registered theme update callbacks."""
        for cb in list(self._update_callbacks):
            try:
                cb(vacuum_entity_id=vacuum_entity_id)
            except Exception:
                _LOGGER.exception(
                    "Theme update callback failed for %s",
                    vacuum_entity_id,
                )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_theme_data(self) -> dict:
        """Return the root theme dict, ensuring all required keys are present."""
        self._data.setdefault("theme", {})
        self._data["theme"].setdefault("library", {})
        self._data["theme"].setdefault("default_theme_id", None)
        self._data["theme"].setdefault("vacuums", {})
        return self._data["theme"]

    def _get_vacuum_theme(self, vacuum_entity_id: str) -> dict:
        """Return per-vacuum theme state, creating defaults if absent."""
        theme = self._get_theme_data()
        theme["vacuums"].setdefault(
            vacuum_entity_id,
            {
                "active_theme_id": None,
                "working_draft": {"tokens": {}, "colors": {}, "alpha": {}},
                "draft_dirty": False,
                "editor_mode": "live",
            },
        )
        vac = theme["vacuums"][vacuum_entity_id]
        vac.setdefault("active_theme_id", None)
        vac["working_draft"] = self._normalize_theme_draft(vac.get("working_draft"))
        vac["draft_dirty"] = bool(vac.get("draft_dirty", False))
        vac["editor_mode"] = str(vac.get("editor_mode") or "live")
        return vac

    def _generate_theme_id(self) -> str:
        """Generate a stable, sortable unique theme ID."""
        return f"theme_{_dt.now().strftime('%Y%m%dT%H%M%S%f')}"

    def _empty_theme_draft(self) -> dict[str, dict[str, Any]]:
        """Return an empty draft payload."""
        return {"tokens": {}, "colors": {}, "alpha": {}}

    def _normalize_theme_entry(self, payload: Any) -> dict[str, Any]:
        """Return one normalized stored theme entry."""
        source = dict(payload) if isinstance(payload, dict) else {}
        entry = {
            "id": str(source.get("id") or "").strip() or None,
            "name": str(source.get("name") or "").strip() or "Untitled",
            "tokens": dict(source.get("tokens", {})) if isinstance(source.get("tokens"), dict) else {},
            "colors": dict(source.get("colors", {})) if isinstance(source.get("colors"), dict) else {},
            "alpha": dict(source.get("alpha", {})) if isinstance(source.get("alpha"), dict) else {},
        }
        # Provenance for the Source facet — carried through every read; only the
        # four known values survive (unknown/garbage is dropped, not stored).
        provenance = str(source.get("source", "")).strip().lower()
        if provenance in {"core", "community", "generated", "manual"}:
            entry["source"] = provenance
        return entry

    def _normalize_theme_draft(self, payload: Any) -> dict[str, dict[str, Any]]:
        """Return one normalized working draft."""
        source = dict(payload) if isinstance(payload, dict) else {}
        return {
            "tokens": dict(source.get("tokens", {})) if isinstance(source.get("tokens"), dict) else {},
            "colors": dict(source.get("colors", {})) if isinstance(source.get("colors"), dict) else {},
            "alpha": dict(source.get("alpha", {})) if isinstance(source.get("alpha"), dict) else {},
        }

    def _get_theme_library_entries(self) -> dict[str, dict[str, Any]]:
        """Return a normalized view of the theme library keyed by theme id.

        Returns a copy — does not mutate theme["library"]. Write-time
        normalization keeps stored entries clean without touching storage on
        every read.
        """
        theme = self._get_theme_data()
        library = theme.get("library", {})
        normalized: dict[str, dict[str, Any]] = {}
        for raw_theme_id, raw_entry in library.items():
            theme_id = str(raw_theme_id or "").strip()
            if not theme_id:
                continue
            entry = self._normalize_theme_entry(raw_entry)
            entry["id"] = theme_id
            normalized[theme_id] = entry
        return normalized

    def _resolved_theme_payload(
        self,
        *,
        active_entry: dict[str, Any] | None,
        draft: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        """Return active theme values with working-draft overrides applied."""
        base_entry = self._normalize_theme_entry(active_entry)
        overlay = self._normalize_theme_draft(draft)
        return {
            "tokens": {
                **dict(base_entry.get("tokens", {})),
                **dict(overlay.get("tokens", {})),
            },
            "colors": {
                **dict(base_entry.get("colors", {})),
                **dict(overlay.get("colors", {})),
            },
            "alpha": {
                **dict(base_entry.get("alpha", {})),
                **dict(overlay.get("alpha", {})),
            },
        }

    def _minimal_theme_mutation_response(
        self,
        *,
        ok: bool,
        theme_id: str | None = None,
        active_theme_id: str | None = None,
        draft_dirty: bool | None = None,
    ) -> dict[str, Any]:
        """Return a small card-friendly mutation response."""
        payload: dict[str, Any] = {"ok": bool(ok)}
        if theme_id is not None:
            payload["theme_id"] = theme_id
        if active_theme_id is not None:
            payload["active_theme_id"] = active_theme_id
        if draft_dirty is not None:
            payload["draft_dirty"] = bool(draft_dirty)
        return payload

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_theme_library(self) -> dict[str, Any]:
        """Return the full theme library with a summary list."""
        theme = self._get_theme_data()
        library = self._get_theme_library_entries()
        return {
            "default_theme_id": theme["default_theme_id"],
            "themes": [
                {"id": tid, "theme_id": tid, "name": t.get("name", ""), "source": t.get("source")}
                for tid, t in library.items()
            ],
            "library": library,
        }

    def save_theme_as_new(
        self,
        *,
        vacuum_entity_id: str,
        name: str,
        set_as_default: bool = False,
    ) -> dict[str, Any]:
        """Save vacuum's working draft as a new named theme in the library."""
        theme = self._get_theme_data()
        library = self._get_theme_library_entries()
        vac = self._get_vacuum_theme(vacuum_entity_id)
        active_id = str(vac.get("active_theme_id") or "").strip()
        active_entry = library.get(active_id) if active_id else None
        resolved = self._resolved_theme_payload(
            active_entry=active_entry,
            draft=vac.get("working_draft"),
        )
        theme_id = self._generate_theme_id()

        theme["library"][theme_id] = {
            "id": theme_id,
            "name": str(name).strip() or "Untitled",
            # User-crafted from the working draft -> manual provenance.
            "source": "manual",
            "tokens": dict(resolved.get("tokens", {})),
            "colors": dict(resolved.get("colors", {})),
            "alpha": dict(resolved.get("alpha", {})),
        }

        vac["active_theme_id"] = theme_id
        vac["working_draft"] = self._empty_theme_draft()
        vac["draft_dirty"] = False

        if set_as_default:
            theme["default_theme_id"] = theme_id

        self._notify_updated(vacuum_entity_id=vacuum_entity_id)
        return self._minimal_theme_mutation_response(
            ok=True,
            theme_id=theme_id,
            active_theme_id=theme_id,
            draft_dirty=False,
        )

    def overwrite_theme(
        self,
        *,
        vacuum_entity_id: str,
        theme_id: str,
    ) -> dict[str, Any]:
        """Overwrite an existing library entry with the vacuum's working draft."""
        theme = self._get_theme_data()
        library = self._get_theme_library_entries()
        if theme_id not in library:
            return {"ok": False, "reason": "theme_not_found", "theme_id": theme_id}
        vac = self._get_vacuum_theme(vacuum_entity_id)
        active_id = str(vac.get("active_theme_id") or "").strip()
        active_entry = library.get(active_id) if active_id else None
        resolved = self._resolved_theme_payload(
            active_entry=active_entry,
            draft=vac.get("working_draft"),
        )
        existing_name = library[theme_id].get("name", "")
        existing_source = library[theme_id].get("source")

        entry = {
            "id": theme_id,
            "name": existing_name,
            "tokens": dict(resolved.get("tokens", {})),
            "colors": dict(resolved.get("colors", {})),
            "alpha": dict(resolved.get("alpha", {})),
        }
        # Overwriting edits content in place — keep the entry's provenance.
        if existing_source:
            entry["source"] = existing_source
        theme["library"][theme_id] = entry

        vac["active_theme_id"] = theme_id
        vac["working_draft"] = self._empty_theme_draft()
        vac["draft_dirty"] = False

        self._notify_updated(vacuum_entity_id=vacuum_entity_id)
        return self._minimal_theme_mutation_response(
            ok=True,
            theme_id=theme_id,
            active_theme_id=theme_id,
            draft_dirty=False,
        )

    def rename_theme(
        self,
        *,
        theme_id: str,
        name: str,
    ) -> dict[str, Any]:
        """Rename a theme in the library."""
        theme = self._get_theme_data()
        library = self._get_theme_library_entries()
        if theme_id not in library:
            return {"ok": False, "reason": "theme_not_found", "theme_id": theme_id}

        clean_name = str(name).strip() or "Untitled"
        theme["library"][theme_id]["name"] = clean_name

        self._notify_updated(vacuum_entity_id=None)
        return self._minimal_theme_mutation_response(ok=True, theme_id=theme_id)

    def delete_theme(self, *, theme_id: str) -> dict[str, Any]:
        """Remove a theme from the library. Clears it from any vacuum that uses it."""
        theme = self._get_theme_data()
        library = self._get_theme_library_entries()
        if theme_id not in library:
            return {"ok": False, "reason": "theme_not_found", "theme_id": theme_id}

        del theme["library"][theme_id]

        if theme["default_theme_id"] == theme_id:
            theme["default_theme_id"] = None

        for vac_data in theme["vacuums"].values():
            if vac_data.get("active_theme_id") == theme_id:
                vac_data["active_theme_id"] = None
            vac_data["working_draft"] = self._normalize_theme_draft(vac_data.get("working_draft"))

        self._notify_updated(vacuum_entity_id=None)
        return self._minimal_theme_mutation_response(ok=True, theme_id=theme_id)

    def set_active_theme(
        self,
        *,
        vacuum_entity_id: str | None,
        theme_id: str,
    ) -> dict[str, Any]:
        """Point a vacuum (or global default) at a library theme."""
        theme = self._get_theme_data()
        library = self._get_theme_library_entries()
        if theme_id not in library:
            return {"ok": False, "reason": "theme_not_found", "theme_id": theme_id}

        if vacuum_entity_id is None:
            theme["default_theme_id"] = theme_id
            return self._minimal_theme_mutation_response(ok=True, theme_id=theme_id)

        vac = self._get_vacuum_theme(vacuum_entity_id)
        vac["active_theme_id"] = theme_id
        vac["working_draft"] = self._empty_theme_draft()
        vac["draft_dirty"] = False

        self._notify_updated(vacuum_entity_id=vacuum_entity_id)
        return self._minimal_theme_mutation_response(
            ok=True,
            theme_id=theme_id,
            active_theme_id=theme_id,
            draft_dirty=False,
        )

    def update_working_draft(
        self,
        *,
        vacuum_entity_id: str,
        tokens: dict[str, Any] | None = None,
        colors: dict[str, Any] | None = None,
        alpha: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Patch-merge theme draft updates into the working draft."""
        vac = self._get_vacuum_theme(vacuum_entity_id)
        draft = vac.setdefault("working_draft", self._empty_theme_draft())

        for bucket_name, updates in (
            ("tokens", tokens),
            ("colors", colors),
            ("alpha", alpha),
        ):
            if not isinstance(updates, dict):
                continue
            bucket = draft.setdefault(bucket_name, {})
            for key, value in updates.items():
                if value is None or value == "":
                    bucket.pop(str(key), None)
                    continue
                bucket[str(key)] = value

        vac["draft_dirty"] = any(
            isinstance(draft.get(bucket_name), dict) and bool(draft.get(bucket_name))
            for bucket_name in ("tokens", "colors", "alpha")
        )

        self._notify_updated(vacuum_entity_id=vacuum_entity_id)
        return self._minimal_theme_mutation_response(
            ok=True,
            active_theme_id=vac.get("active_theme_id"),
            draft_dirty=vac.get("draft_dirty"),
        )

    def revert_draft(self, *, vacuum_entity_id: str) -> dict[str, Any]:
        """Reset working draft back to the active theme. Clears dirty flag."""
        vac = self._get_vacuum_theme(vacuum_entity_id)
        active_id = str(vac.get("active_theme_id") or "").strip() or None
        vac["working_draft"] = self._empty_theme_draft()
        vac["draft_dirty"] = False

        self._notify_updated(vacuum_entity_id=vacuum_entity_id)
        return self._minimal_theme_mutation_response(
            ok=True,
            active_theme_id=active_id,
            draft_dirty=False,
        )

    def export_theme(self, *, theme_id: str) -> dict[str, Any]:
        """Return a theme as a portable JSON-safe dict for card-side download."""
        from ..timestamp_utils import utc_now_iso

        library = self._get_theme_library_entries()
        if theme_id not in library:
            return {"ok": False, "reason": "theme_not_found", "theme_id": theme_id}

        entry = library[theme_id]
        theme_out = {
            "id": theme_id,
            "name": entry.get("name", ""),
            "tokens": dict(entry.get("tokens", {})),
            "colors": dict(entry.get("colors", {})),
            "alpha": dict(entry.get("alpha", {})),
        }
        # Carry provenance so a downloaded export keeps its `source` (the gallery
        # and card Source facet read it); omitted when the entry has none.
        if entry.get("source"):
            theme_out["source"] = entry["source"]
        return {
            "ok": True,
            "version": 1,
            "exported_at": utc_now_iso(),
            "theme": theme_out,
        }

    def import_theme(
        self,
        *,
        payload: dict[str, Any],
        vacuum_entity_id: str | None = None,
    ) -> dict[str, Any]:
        """Import a theme.

        Full import (scope absent or "full"): validate and add a NEW theme to
        the library. Scoped import (scope is a non-empty list of floor-type
        names): REPLACE those namespaces on the vacuum's active theme via
        clear-then-apply — see _import_scoped.
        """
        if not isinstance(payload, dict):
            return {"ok": False, "reason": "invalid_payload"}

        source_theme = payload.get("theme") if isinstance(payload.get("theme"), dict) else payload
        if not isinstance(source_theme, dict):
            return {"ok": False, "reason": "missing_theme"}

        scope = payload.get("scope")
        if isinstance(scope, list) and scope:
            return self._import_scoped(
                scope=scope,
                source=source_theme,
                vacuum_entity_id=vacuum_entity_id,
            )

        name = str(source_theme.get("name", "")).strip()
        tokens = source_theme.get("tokens")
        colors = source_theme.get("colors")
        alpha = source_theme.get("alpha")

        if not name:
            return {"ok": False, "reason": "missing_name"}
        if tokens is not None and not isinstance(tokens, dict):
            return {"ok": False, "reason": "invalid_tokens"}
        if colors is not None and not isinstance(colors, dict):
            return {"ok": False, "reason": "invalid_colors"}
        if alpha is not None and not isinstance(alpha, dict):
            return {"ok": False, "reason": "invalid_alpha"}

        library = self._get_theme_library_entries()
        existing_names = {t.get("name", "") for t in library.values()}
        final_name = name
        if final_name in existing_names:
            final_name = f"{name} (imported)"

        # Preserve the envelope's provenance, but never honor `core` on import:
        # only the seeded preloaded themes are truly bundled, so an imported copy
        # of one becomes a user theme.
        imported_source = str(source_theme.get("source", "")).strip().lower()
        entry_source = imported_source if imported_source in {"community", "generated", "manual"} else "manual"

        theme_id = self._generate_theme_id()
        theme = self._get_theme_data()
        theme["library"][theme_id] = {
            "id": theme_id,
            "name": final_name,
            "source": entry_source,
            "tokens": dict(tokens) if isinstance(tokens, dict) else {},
            "colors": dict(colors) if isinstance(colors, dict) else {},
            "alpha": dict(alpha) if isinstance(alpha, dict) else {},
        }

        self._notify_updated(vacuum_entity_id=None)
        return self._minimal_theme_mutation_response(ok=True, theme_id=theme_id)

    def _import_scoped(
        self,
        *,
        scope: list,
        source: dict[str, Any],
        vacuum_entity_id: str | None,
    ) -> dict[str, Any]:
        """REPLACE each scoped floor-type namespace on the vacuum's ACTIVE theme.

        For every type name in `scope`, clear every --evcc-floor-{name}-* key
        across tokens/colors/alpha on the active library entry, then apply the
        import's keys for that namespace. Clear-then-apply (not patch) makes the
        result deterministic regardless of the target's prior state — no stale
        override can survive (the same leftover-token bleed that hit the floor
        registry). Values arrive already range-clamped by the card. Matching
        working-draft overrides are cleared too, so the entry's new namespace is
        what renders.

        Type names are used only as opaque key prefixes here (--evcc-floor-
        {name}-); the card validates them against the registry before sending,
        so unknown namespaces never reach this method.
        """
        if not vacuum_entity_id:
            return {"ok": False, "reason": "missing_vacuum"}

        names = [str(n).strip() for n in scope if str(n).strip()]
        if not names:
            return {"ok": False, "reason": "empty_scope"}

        vac = self._get_vacuum_theme(vacuum_entity_id)
        active_id = str(vac.get("active_theme_id") or "").strip()
        theme = self._get_theme_data()
        library = theme.get("library", {})
        if not active_id or active_id not in library:
            return {"ok": False, "reason": "no_active_theme"}

        entry = library[active_id]
        sources = {
            bucket: (source.get(bucket) if isinstance(source.get(bucket), dict) else {})
            for bucket in ("tokens", "colors", "alpha")
        }
        draft = vac.get("working_draft") if isinstance(vac.get("working_draft"), dict) else {}

        applied = 0
        cleared = 0
        for name in names:
            prefix = f"--evcc-floor-{name}-"
            for bucket in ("tokens", "colors", "alpha"):
                target = entry.get(bucket)
                if not isinstance(target, dict):
                    target = {}
                    entry[bucket] = target

                # clear every existing key in the namespace
                for key in [k for k in target if isinstance(k, str) and k.startswith(prefix)]:
                    del target[key]
                    cleared += 1

                # apply the import's keys for the namespace
                for key, value in sources[bucket].items():
                    if isinstance(key, str) and key.startswith(prefix):
                        target[key] = value
                        applied += 1

                # drop matching working-draft overrides so the entry's value renders
                draft_bucket = draft.get(bucket) if isinstance(draft.get(bucket), dict) else None
                if draft_bucket:
                    for key in [k for k in draft_bucket if isinstance(k, str) and k.startswith(prefix)]:
                        del draft_bucket[key]

        self._notify_updated(vacuum_entity_id=vacuum_entity_id)
        response = self._minimal_theme_mutation_response(
            ok=True,
            theme_id=active_id,
            active_theme_id=active_id,
        )
        response["scope"] = list(names)
        response["applied"] = applied
        response["cleared"] = cleared
        return response
