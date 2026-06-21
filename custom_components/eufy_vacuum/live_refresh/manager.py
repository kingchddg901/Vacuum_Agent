"""Lever B — live current-room refresh during a CONTIGUOUS run.

A brand whose live current-room signal lags its status poll (Roborock: the room is MAP-derived,
refreshed only on the ~30s IMAGE_CACHE_INTERVAL gate, while status moves at ~15s) can declare
``dispatch.live_room_refresh`` so the framework pulses an adapter-named service that refreshes that
signal off-cadence during a contiguous run. Core stays brand-agnostic: the service AND the
local-connection gate (which avoids a cloud rate-limit) are entirely adapter-declared data; a brand
that omits the block is disabled = a no-op. Excluded for strict-order (phased) runs by the caller —
those dock per room, so each room-start is a state flip that already forces a free refresh.

Extracted from core/manager.py (the orchestrator delegates via maybe_pulse_live_room_refresh) to
keep this self-contained subsystem — config resolution, the per-vacuum rate-limit + sticky-disable
state, the local-connection probe, and the fire-and-forget pulse — out of the orchestrator.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..adapters.registry import get_adapter_config as _get_adapter_config

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


class LiveRoomRefreshManager:
    """Owns the Lever B live current-room refresh. Constructed with the core manager (the
    bundled-subsystem pattern); reads adapter config + drives a fire-and-forget service pulse."""

    def __init__(self, *, manager: "EufyVacuumManager") -> None:
        self._manager = manager
        # Per-vacuum monotonic timestamp of the last pulse (the rate limit; the refresh is
        # per-vacuum upstream, so it's keyed by vacuum, not map); the vacuums whose service proved
        # unavailable this session (sticky-off); and the vacuums we've logged a first-pulse
        # breadcrumb for. In-memory only — a restart drops them.
        self._pulse_at: dict[str, float] = {}
        self._disabled: set[str] = set()
        self._seen: set[str] = set()

    @property
    def hass(self):  # noqa: D401 - thin accessor onto the core manager's hass
        return self._manager.hass

    def _resolve_config(self, vacuum_entity_id: str) -> dict[str, Any]:
        """Resolve the adapter's ``dispatch.live_room_refresh`` block over inert defaults
        (disabled). Brands that omit it are a no-op, byte-identical."""
        cfg: dict[str, Any] = {
            "enabled": False, "interval_s": 15, "service": None, "local_gate": None,
        }
        declared = (
            (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {}) or {}
        ).get("live_room_refresh", {}) or {}
        cfg["enabled"] = bool(declared.get("enabled"))
        if "interval_s" in declared:
            try:
                cfg["interval_s"] = max(1, int(declared["interval_s"]))
            except (TypeError, ValueError):
                pass
        svc = declared.get("service")
        cfg["service"] = svc if isinstance(svc, dict) else None
        gate = declared.get("local_gate")
        cfg["local_gate"] = gate if isinstance(gate, dict) else None
        return cfg

    def _connection_is_local(
        self, vacuum_entity_id: str, gate: dict[str, Any] | None
    ) -> bool:
        """Generic, fail-safe local-connection probe from an adapter-declared ``local_gate``
        spec. ALL brand-specific strings (the device-identifier domain, the upstream repair
        issue domain + id template) come from ``gate`` — core stays brand-agnostic. Returns
        True ONLY when local is positively confirmed; any uncertainty (no spec, unknown
        device/identifier) returns False so the caller SKIPS the pulse and falls back to the
        device's native cadence rather than risk a cloud-rate-limited refresh.

        Signal: the upstream integration raises a "using cloud API" repair issue while a
        device has never connected locally and clears it once local. Issue ABSENT/inactive =>
        local. Re-evaluated every pulse (never cached) so a mid-run local->cloud flip disables
        the pulse within one interval."""
        if not gate:
            return False
        from homeassistant.helpers import (
            device_registry as dr,
            entity_registry as er,
            issue_registry as ir,
        )
        from homeassistant.util import slugify

        ent = er.async_get(self.hass).async_get(vacuum_entity_id)
        if ent is None or not ent.device_id:
            return False
        dev = dr.async_get(self.hass).async_get(ent.device_id)
        if dev is None:
            return False
        id_domain = gate.get("device_identifier_domain")
        duid = next((i[1] for i in dev.identifiers if i[0] == id_domain), None)
        if not duid:
            return False
        template = str(gate.get("issue_id_template") or "")
        issue_domain = gate.get("issue_domain")
        if not template or not issue_domain:
            return False
        try:
            issue_id = template.format(duid_slug=slugify(duid))
        except (KeyError, IndexError, ValueError):
            return False
        issue = ir.async_get(self.hass).async_get_issue(issue_domain, issue_id)
        return issue is None or not getattr(issue, "active", True)

    def maybe_pulse(self, vacuum_entity_id: str) -> None:
        """During a CONTIGUOUS run, keep the brand's live current-room/map data fresh so the
        native per-room rollover + live fan track the adapter's interval instead of the device's
        slower native map cadence. No-op for brands that don't declare ``dispatch.live_room_refresh``
        (e.g. Eufy). Local-gated (never pulse a cloud connection — the device's map throttle is a
        cloud rate-limit guard), availability-gated, and rate-limited per vacuum. Fire-and-forget;
        any failure degrades to the native cadence. The caller (the job-progress ticker) must
        exclude strict-order (phased) runs — those advance one room per dispatched phase."""
        cfg = self._resolve_config(vacuum_entity_id)
        if not cfg["enabled"] or not cfg["service"]:
            return
        if vacuum_entity_id in self._disabled:
            return
        now = self.hass.loop.time()
        if now - self._pulse_at.get(vacuum_entity_id, 0.0) < cfg["interval_s"]:
            return
        st = self.hass.states.get(vacuum_entity_id)
        if st is None or st.state in ("unavailable", "unknown"):
            return
        if not self._connection_is_local(vacuum_entity_id, cfg["local_gate"]):
            return
        self._pulse_at[vacuum_entity_id] = now
        self.hass.async_create_task(
            self._do_pulse(vacuum_entity_id, cfg["service"])
        )

    async def _do_pulse(self, vacuum_entity_id: str, service: dict[str, Any]) -> None:
        """Fire the adapter-named refresh service (blocking so we can observe the outcome, but on
        a background task so the ticker never waits). A service that is missing on this install
        (ServiceNotFound) or unsupported by the model (ServiceNotSupported) sticky-disables the
        pulse for the session — neither will ever work. A transient error (e.g. the no-dock S6
        reporting no position mid-transit) IS swallowed and retried — its useful side effect, the
        off-gate map refresh, already ran before the raise. The refresh service may be
        SupportsResponse.ONLY (Roborock's is), so honor the adapter's ``returns_response`` flag; we
        discard the returned value and only want the refresh side effect."""
        from homeassistant.exceptions import (
            HomeAssistantError,
            ServiceNotFound,
            ServiceNotSupported,
        )

        domain = service.get("domain")
        name = service.get("service")
        if not domain or not name:
            return
        try:
            await self.hass.services.async_call(
                domain, name, {"entity_id": vacuum_entity_id},
                blocking=True, return_response=bool(service.get("returns_response")),
            )
        except (ServiceNotFound, ServiceNotSupported) as err:
            self._disabled.add(vacuum_entity_id)
            _LOGGER.info(
                "eufy_vacuum: live-room refresh %s.%s unavailable for %s (%s); disabling "
                "the pulse for this session",
                domain, name, vacuum_entity_id, err,
            )
            return
        except HomeAssistantError as err:
            # Transient (e.g. position_not_found / map_failure). The off-gate map refresh already
            # applied; the discarded return value raising is harmless — don't count it toward the
            # sticky-disable.
            _LOGGER.debug(
                "eufy_vacuum: live-room refresh for %s returned %s (refresh still applied)",
                vacuum_entity_id, err,
            )
            return
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception(
                "eufy_vacuum: live-room refresh pulse error for %s", vacuum_entity_id
            )
            return
        # First successful pulse per vacuum per session: a breadcrumb so a live run confirms the
        # feature is active without a debugger.
        if vacuum_entity_id not in self._seen:
            self._seen.add(vacuum_entity_id)
            _LOGGER.info(
                "eufy_vacuum: live-room refresh active for %s via %s.%s — live current-room "
                "+ per-room fan now track the ~%ss refresh instead of the native map cadence",
                vacuum_entity_id, domain, name,
                self._resolve_config(vacuum_entity_id)["interval_s"],
            )
