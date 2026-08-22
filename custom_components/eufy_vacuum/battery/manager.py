"""BatteryHealthManager — accumulates battery samples, charge sessions, and
cumulative cycle wear for each managed vacuum.

DESIGN
======

Cycle counting (industry standard)
----------------------------------
A "cycle" is **cumulative drain ÷ 100**. We add the size of every
percent-point drop in battery to a running ``cumulative_drain_pct``;
``cycles = cumulative_drain_pct / 100``. Charging samples never decrement
the counter — only drain wears the cell.

A safety threshold (``MAX_DELTA_PCT``) ignores implausibly fast per-sample
changes that typically indicate a sensor reset, HA restart gap, firmware
flip (X → 0 / 0 → X), or self-discharge across a long idle. Without this
the counter would inflate every time HA missed events while the integration
was unloaded.

Charge rate tracking — three values
-----------------------------------
1. **Overall** — instantaneous %/min between the most recent two samples
   *while charging*.
2. **Low zone** — same instantaneous %/min, but only updated when the battery
   level at the END of the interval is **≤ 29%**.
3. **High zone** — same, but only updated when end battery is **≥ 80%**.

These zones are the meaningful diagnostics: Li-ion charge curves taper at the
top (CV phase, ≥80%) and start slow at the bottom. Health degrades visibly
in those bands first.

Charge sessions
---------------
A session opens on the first sample where ``charging=True`` after a non-charging
sample, and closes when one of:
- ``charging`` transitions to False
- battery reaches 100%
- a sanity timeout (``SESSION_MAX_HOURS``) elapses without a closing event

Closed sessions are summarized (start/end battery, duration, avg/min/max rate)
and:
- written to ``sessions.csv``
- appended to a recent-history ring buffer in storage (size ``HISTORY_LIMIT``)
- contribute to the baseline + current health windows

Battery health proxy
--------------------
We compute "minutes per 1% gained" for each completed deep-enough session
(start ≤ 50%, end ≥ 90%). The FIRST such session this install observes
anchors the baseline. Average of the LAST 14-day window of similar sessions
is "current". ``health_pct = round(baseline / current * 100, 1)``.

While the baseline is being seeded (no qualifying sessions yet), health_pct
is None.

The baseline is per-install ("your battery as it was when you started
measuring"), not an estimate of factory-fresh performance — the integration
has no way to know factory performance for a given unit. After a battery
swap, call the eufy_vacuum.battery_rebaseline service to clear the anchor
so the next qualifying recharge re-anchors on the new cell.

The qualify window is intentionally wide (50→90, not 30→95): a vacuum that
mostly runs single-room jobs rarely drains far enough for the strict window,
which would leave the baseline unseeded for months. The window still spans
the 80→90 CV-taper region so the rate isn't gamed by skipping the slow part.

Persistence
-----------
The manager owns a slice of ``eufy_vacuum.storage`` under the top-level key
``battery`` (see ``ensure_record``). It reads/writes via the main
``EufyVacuumManager``'s storage helpers so it benefits from the existing
debounced save loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any, Callable

from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event

from . import store as raw_store
from ..adapters.registry import get_adapter_config

_LOGGER = logging.getLogger(__name__)

# === TUNABLES ================================================================

#: Ignore drain/charge deltas above this many percentage points in a single
#: sample interval. Real per-sample motion tops out around ±2-3 pp even
#: under heavy mid-job recharge or peak cleaning drain (per ~30 s sample).
#: Anything above this is almost certainly a sensor reset, HA restart gap,
#: firmware X-to-0 / 0-to-X flip, or multi-hour self-discharge. The trade
#: is that legitimate gap-filling deltas during real HA restarts also get
#: dropped — but those samples are averaged over an unknown gap and were
#: never reliable for rate computation anyway, so the cycles counter
#: stays cleaner with them excluded.
MAX_DELTA_PCT = 3.0

#: Plausible band for a regime-speed percentage (``baseline / current * 100``).
#:
#: live:BATT-CV-1. That expression is a RATIO and nothing bounded it: a regime span
#: measured across a very small window drives ``current`` toward zero and the
#: quotient explodes. Observed on Alfred 2026-08-05 — the first time these fields
#: ever held a value at all, after two deep overnight charges finally re-qualified
#: the session set — as cv 868.7 against cc 118.4.
#:
#: THE PHYSICS RULES IT OUT BEFORE ANY THRESHOLD IS ARGUED. CV is the TAPER phase,
#: where current falls and charging SLOWS. A CV figure seven times the CC one is
#: backwards, whatever band you pick.
#:
#: 100 is a pack matching its own anchor. The floor is deliberately generous — a
#: genuinely tired pack reading 30 is grim but real, and rejecting it would hide
#: exactly the degradation this proxy exists to show. The ceiling is the load-
#: bearing one: charging measurably FASTER than when the baseline was taken is
#: something a cell cannot do, so anything above it is a measurement artefact.
#:
#: WHY NONE IS SAFE HERE. These three fields read None on both vacuums for months
#: before RP-045, so every consumer — sensors, card, diagnostics — already handles
#: it, and health_unavailable_reason already exists to explain it. Rejecting into a
#: state the system has always had cannot break an install; publishing 868.7 could.
REGIME_PCT_MIN = 25.0
REGIME_PCT_MAX = 150.0

#: Ignore *rate* computation when more than this many seconds elapsed since
#: the previous sample — the value would be a meaningless average over the
#: gap (e.g. an HA restart, integration unloaded for a while). Drain still
#: counts toward cumulative cycles since drain is independent of time.
MAX_RATE_INTERVAL_SEC = 600.0

#: Physical ceiling on a charge rate, in percentage points per minute.
#:
#: live:BATT-ZONE-1. THE BATTERY IS QUANTISED TO WHOLE PERCENT, so
#: `delta_pct / (elapsed/60)` inflates without limit as `elapsed` shrinks: one 1%
#: tick landing 18 s after the previous sample reads as 3.33 %/min whatever the pack
#: is really doing. That is the shape of the observed rate_high_zone 3.3079 on a dock
#: measured at ~0.45 %/min at its fastest — an eightfold overstatement produced by a
#: short interval, not by charging. MAX_RATE_INTERVAL_SEC bounded the LONG end and
#: nothing bounded the short one, which reads as complete until you ask what the
#: other end does.
#:
#: 2.5 %/min is a 40-minute 0-100 charge, far beyond any dock these adapters serve
#: (Alfred's measured deep recharge was 9% -> 49% in 88 minutes, about 0.45 %/min).
#: Above it the number is arithmetic, not electricity.
#:
#: A MINIMUM-INTERVAL FLOOR WAS TRIED FIRST AND THE REAL DATA REJECTED IT. Bounding
#: the error at source is the better-looking fix, but at 120 s it discarded genuine
#: samples from the captured charge-curve fixture and moved cc_charge_speed 118.9 ->
#: 114.7. The device's own sample cadence is shorter than the interval a 1% quantum
#: needs, so no floor exists that is both safe and useful — the artefact has to be
#: caught by its VALUE instead. Do not re-add the floor without re-running
#: test_charge_rates.
#:
#: NOT applied as a taper invariant (high_zone <= low_zone) either. That holds of a
#: charge CURVE but not of any single sample pair, so asserting it per sample would
#: reject legitimate readings. This bound removes the artefact that violated it
#: without inventing a rule the data cannot honour.
MAX_PLAUSIBLE_RATE_PCT_PER_MIN = 2.5

#: Battery range that counts as "low zone" — slow CC start.
LOW_ZONE_MAX = 29

#: Battery range that counts as "high zone" — slow CV taper.
HIGH_ZONE_MIN = 80

#: Maximum age of an open session before it is force-closed and discarded.
SESSION_MAX_HOURS = 12.0

#: Sessions kept in the storage ring buffer for recent-trend computation.
HISTORY_LIMIT = 50

#: RP-045: sessions that qualify for the health/charge-speed computation are
#: ALSO retained here, separately from the HISTORY_LIMIT display ring above.
#: The ring rotates on every session close regardless of whether a session
#: qualified; a baseline anchored from a qualifying session can easily
#: outlive that session's place in a 50-item ring (it did, for real, after
#: ~50 ordinary top-ups). This store is not meant to rotate away within a
#: baseline's working life, so it gets a much higher ceiling -- still capped
#: so a very old, very active install doesn't grow this unboundedly.
HEALTH_QUALIFYING_RETENTION_LIMIT = 500

#: Qualifying sessions used to anchor the baseline. The baseline is
#: per-install ("your battery as it was when you set this up"), not an
#: estimate of factory-fresh performance, so the first valid session
#: anchors it. CURRENT_WINDOW_DAYS smooths comparison-side noise.
BASELINE_SAMPLE_COUNT = 1

#: Window for the "current" health average. Wider than 7 days because
#: single-room users rarely produce qualifying sessions — the rolling
#: average needs more time to fill.
CURRENT_WINDOW_DAYS = 14

#: Sessions used for health proxy must start at or below this and reach at
#: least this much. Keeps comparisons apples-to-apples while still being
#: loose enough to capture natural recharges (vacuums on single-room jobs
#: rarely hit the strict 30→95 window).
HEALTH_QUALIFY_START_MAX = 50
HEALTH_QUALIFY_END_MIN = 90

#: Regime accounting windows. CC = constant-current (capacity proxy),
#: CV = constant-voltage taper (resistance proxy). The two regimes age in
#: opposite directions — capacity loss raises %/min in CC, resistance rise
#: lowers %/min in CV — so they're tracked separately. CC_ZONE_MAX is the
#: boundary between them; CC_ZONE_MIN and CV_ZONE_MAX are the outer clip
#: bounds. Aligned with HEALTH_QUALIFY_* by design but decoupled — do not
#: collapse them. LOW_ZONE_MAX / HIGH_ZONE_MIN remain independent and feed
#: the rate_low_zone / rate_high_zone stat sensors.
CC_ZONE_MIN = 50
CC_ZONE_MAX = 80
CV_ZONE_MAX = 90

#: When a job finishes, the *next* charge session within this many hours is
#: attached as its post-job recharge. Anything beyond is treated as
#: independent (e.g. user manually placed the vacuum back on the dock days
#: later).
POST_JOB_CHARGE_LINK_HOURS = 4.0


# === SCHEMA HELPERS ==========================================================

def _new_record() -> dict[str, Any]:
    return {
        "cycles": 0.0,
        "cumulative_drain_pct": 0.0,
        "last_battery_level": None,
        "last_sample_ts": None,
        "last_charging": False,
        "current_session": None,
        "stats": {
            "rate_overall_per_min": None,
            "rate_low_zone_per_min": None,
            "rate_high_zone_per_min": None,
            "last_charge_duration_min": None,
            "last_charge_delta_pct": None,
            # health_pct is the headline; semantically it's an alias of
            # cv_charge_speed_pct (resistance proxy). Kept under this name for
            # entity_id continuity with the existing _battery_health sensor.
            "health_pct": None,
            "cc_charge_speed_pct": None,
            "cv_charge_speed_pct": None,
            # RP-045(iii): set only when health_pct is None AND we have
            # enough session history to say WHY -- not on a genuinely fresh
            # install with no charges yet, which is just "still building"
            # rather than stuck. Paired code + plain-English fallback text,
            # mirroring the learning manager's trust_reason/trust_reason_text
            # convention (src/renderers/metrics.js's tVocabRaw).
            "health_unavailable_reason": None,
            "health_unavailable_reason_text": None,
        },
        "baseline": {
            # Split into per-regime anchors. CC = capacity proxy (50→80),
            # CV = resistance proxy (80→90). The legacy session-wide
            # `min_per_pct` field is intentionally absent; ensure_record only
            # adds missing keys, so old records keep their legacy field unused
            # until a future cleanup prunes it.
            "cc_min_per_pct": None,
            "cv_min_per_pct": None,
            "session_count": 0,
            "anchored_at": None,
        },
        "session_history_recent": [],
        # RP-045: sessions that qualify for cc- and/or cv-side health
        # computation, retained apart from session_history_recent above so
        # the comparison set used by _update_health cannot rotate away from
        # its own baseline anchor. Populated (and capped at
        # HEALTH_QUALIFYING_RETENTION_LIMIT) by _update_health itself.
        "health_qualifying_sessions": [],
        # Job-level battery metrics — populated by record_job_metrics().
        "last_job": None,
        "job_aggregates": {
            "all_jobs": _new_aggregate_bucket(),
            "by_clean_mode": {},   # bucket per single-mode value
            "by_fan_speed": {},
            "by_water_level": {},
        },
        # Mid-job recharge rates — high-quality health signal (consistent
        # 15→75 charge zone, in CC region, hot from cleaning).
        "mid_job_recharge_stats": {
            "count": 0,
            "rate_sum": 0.0,
            "rate_mean_per_min": None,
            "last_rate_per_min": None,
            "last_recorded_at": None,
        },
    }


def _new_aggregate_bucket() -> dict[str, Any]:
    """Running mean container for a per-bucket aggregate.

    Stores ``count`` and the cumulative sums needed to recompute means on
    demand without keeping every sample around.
    """
    return {
        "count": 0,
        "duration_min_sum": 0.0,
        "area_m2_sum": 0.0,
        # Total drain over every job in the bucket. A real quantity, but NOT a ratio
        # numerator — the two partnered sums below are. See C17.
        "drain_pct_sum": 0.0,
        # PARTNERED NUMERATORS. A ratio whose top and bottom count different
        # populations is not a mean of anything, so each of these accumulates ONLY
        # when its partner denominator is present too.
        "drain_pct_sum_for_duration": 0.0,
        "drain_pct_sum_for_area": 0.0,
        # The honest denominators, so a consumer can publish the sample size a mean
        # was actually computed over rather than `count`, which counts every job.
        "samples_duration": 0,
        "samples_area": 0,
        # Pre-rounded means — written every record_job_metrics call.
        "drain_per_min_mean": None,
        "drain_per_hour_mean": None,
        "drain_per_m2_mean": None,
    }


# === MANAGER =================================================================


class BatteryHealthManager:
    """Tracks battery state per vacuum, persisted via the main manager."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        runtime_manager: Any,
        config_dir: str | None = None,
    ) -> None:
        self._hass = hass
        self._manager = runtime_manager
        self._config_dir = config_dir or hass.config.config_dir
        self._listeners: list[Callable[[], None]] = []
        # entity_id (battery sensor) -> vacuum_entity_id
        self._battery_to_vacuum: dict[str, str] = {}
        # vacuum_entity_id -> set of HA-side state-change unsub callables
        self._vacuum_unsubs: dict[str, list[Callable[[], None]]] = {}
        # Listeners notified whenever a vacuum's state changes (for sensors).
        self._update_listeners: list[Callable[[str], None]] = []
        # vacuum_entity_id -> {job_id, recorded_ts} pending post-job charge
        # link. Set in record_job_metrics(), consumed by _close_session().
        self._pending_post_job: dict[str, dict[str, Any]] = {}

    # -- listener registration -------------------------------------------------

    def add_update_listener(self, cb: Callable[[str], None]) -> Callable[[], None]:
        """Register a callback fired with vacuum_entity_id whenever its battery
        state record is updated. Returns an unregister callable."""
        self._update_listeners.append(cb)

        def _unsub() -> None:
            try:
                self._update_listeners.remove(cb)
            except ValueError:
                pass

        return _unsub

    def _notify(self, vacuum_entity_id: str) -> None:
        for cb in list(self._update_listeners):
            try:
                cb(vacuum_entity_id)
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("battery: update listener raised")

    # -- record access ---------------------------------------------------------

    def _root(self) -> dict[str, Any]:
        battery = self._manager.data.setdefault("battery", {})
        battery.setdefault("vacuums", {})
        return battery

    def ensure_record(self, vacuum_entity_id: str) -> dict[str, Any]:
        vacuums = self._root()["vacuums"]
        record = vacuums.get(vacuum_entity_id)
        if record is None:
            record = _new_record()
            vacuums[vacuum_entity_id] = record
        else:
            # Repair any missing keys from older records.
            template = _new_record()
            for key, default in template.items():
                record.setdefault(key, default)
            for key, default in template["stats"].items():
                record["stats"].setdefault(key, default)
            for key, default in template["baseline"].items():
                record["baseline"].setdefault(key, default)
        return record

    def get_record(self, vacuum_entity_id: str) -> dict[str, Any]:
        """Return the live record (creating if absent)."""
        return self.ensure_record(vacuum_entity_id)

    def compute_time_to_target_pct(
        self, *, vacuum_entity_id: str, current_pct: int, target_pct: int
    ) -> dict[str, Any]:
        """Estimate minutes to charge from ``current_pct`` to ``target_pct``.

        Splits the span at the CC/CV boundary (``HIGH_ZONE_MIN`` = 80): the sub-80
        constant-current phase pairs with the "low" zone rate, the >=80 CV taper
        (which dominates a 95% target) pairs with the "high" zone rate.

        RP-043/RP-044: per span, the precedence is:
          1. A rate observed by THIS charging session for the needed zone (freshest —
             see the low/high_zone_rate_* accumulators opened in _update_session and
             filled in _process_sample). Source ``"zone_rate"``.
          2. The cross-session ``stats.rate_*_zone_per_min`` — but ONLY when there
             ISN'T a currently open session that could have produced its own sample
             for this zone and simply hasn't yet. When a session IS open without its
             own sample, that stats value belongs to a previous, unrelated charge and
             must not be quietly reused (RP-044's cold-start contract) — this tier is
             skipped entirely rather than divide by a stale carry-over. Source
             ``"zone_rate"``.
          3. The learned per-install ``cc_min_per_pct``/``cv_min_per_pct`` baseline —
             a fixed, potentially weeks-old anchor, so it is the last resort rather
             than (as before) the first. Source ``"baseline"``.
          4. None of the above -> ``minutes=None`` — a cold-start install, where the
             caller shows a live wall-clock "charging..." instead of a fabricated ETA
             (the charge-rate baseline fills passively from every dock, so this
             self-heals within a sample or two of the session opening).

        Returns ``{minutes: float|None, source: 'baseline'|'zone_rate'|'already_charged'|None}``.
        ``source`` is ``"baseline"`` only when EVERY needed span used the baseline;
        any live-measured contribution (tier 1 or 2) marks the whole estimate
        ``"zone_rate"``, since that's the more informative half of the answer for
        the card (is this number still anchored to a frozen reading, or not).
        """
        cur = max(0, min(int(current_pct), 100))
        tgt = max(0, min(int(target_pct), 100))
        if cur >= tgt:
            return {"minutes": 0.0, "source": "already_charged"}

        record = self.get_record(vacuum_entity_id)
        baseline = record.get("baseline", {}) if isinstance(record, dict) else {}
        stats = record.get("stats", {}) if isinstance(record, dict) else {}
        session = record.get("current_session") if isinstance(record, dict) else None

        cc_span = max(0, min(tgt, HIGH_ZONE_MIN) - cur)   # % points below 80 (CC)
        cv_span = max(0, tgt - max(cur, HIGH_ZONE_MIN))    # % points at/above 80 (CV taper)

        cc_minutes, cc_tier = self._span_minutes(
            span=cc_span,
            session=session,
            session_sum_key="low_zone_rate_sum",
            session_samples_key="low_zone_rate_samples",
            stats=stats,
            stats_rate_key="rate_low_zone_per_min",
            baseline_mpp=baseline.get("cc_min_per_pct"),
        )
        cv_minutes, cv_tier = self._span_minutes(
            span=cv_span,
            session=session,
            session_sum_key="high_zone_rate_sum",
            session_samples_key="high_zone_rate_samples",
            stats=stats,
            stats_rate_key="rate_high_zone_per_min",
            baseline_mpp=baseline.get("cv_min_per_pct"),
        )

        if cc_minutes is None or cv_minutes is None:
            return {"minutes": None, "source": None}  # cold-start -> wall-clock display

        tiers = {t for t, span in ((cc_tier, cc_span), (cv_tier, cv_span)) if span > 0}
        source = "baseline" if tiers == {"baseline"} else "zone_rate"
        return {"minutes": round(cc_minutes + cv_minutes, 1), "source": source}

    def _span_minutes(
        self,
        *,
        span: float,
        session: dict[str, Any] | None,
        session_sum_key: str,
        session_samples_key: str,
        stats: dict[str, Any],
        stats_rate_key: str,
        baseline_mpp: float | None,
    ) -> tuple[float | None, str | None]:
        """Minutes contributed by one regime span, and the tier that supplied it.

        See ``compute_time_to_target_pct``'s docstring for the full precedence.
        A span of 0 (this regime isn't needed for the requested range) always
        returns ``(0.0, None)`` regardless of data availability — mirrors the
        original "cc_span == 0 or cc_mpp" short-circuit.
        """
        if span <= 0:
            return 0.0, None

        session_open_without_own_sample = False
        if session is not None:
            samples = int(session.get(session_samples_key) or 0)
            if samples > 0:
                rate_sum = float(session.get(session_sum_key) or 0.0)
                avg_rate = rate_sum / samples
                if avg_rate > 0:
                    return span / avg_rate, "zone_rate"
            # Session open but hasn't produced its own sample for this zone —
            # RP-044: don't fall through to the cross-session stats value below,
            # it would be a previous session's leftover.
            session_open_without_own_sample = True

        if not session_open_without_own_sample:
            rate = stats.get(stats_rate_key) or stats.get("rate_overall_per_min")
            if rate:
                return span / float(rate), "zone_rate"

        if baseline_mpp:
            return span * float(baseline_mpp), "baseline"

        return None, None

    # -- HA wiring -------------------------------------------------------------

    def start(self, vacuum_entity_ids: list[str]) -> None:
        """Begin listening for battery + charging state changes for each vacuum."""
        for vacuum_entity_id in vacuum_entity_ids:
            self._wire_vacuum(vacuum_entity_id)

    def stop(self) -> None:
        for unsubs in self._vacuum_unsubs.values():
            for unsub in unsubs:
                try:
                    unsub()
                except Exception:  # pragma: no cover
                    pass
        self._vacuum_unsubs.clear()
        self._battery_to_vacuum.clear()

    def unregister_vacuum(self, vacuum_entity_id: str) -> None:
        """Tear down ONE vacuum's live state — the per-vacuum analogue of stop().

        Used when a single managed vacuum is removed (its device deleted) while
        the others keep running. IN-MEMORY ONLY: the persisted battery record is
        dropped separately by ``EufyVacuumManager.remove_vacuum_record`` — this
        just unsubscribes the state listeners and forgets the lookup maps so a
        removed vacuum leaves no stale subscription behind.
        """
        for unsub in self._vacuum_unsubs.pop(vacuum_entity_id, []):
            try:
                unsub()
            except Exception:  # pragma: no cover
                pass
        # _battery_to_vacuum is keyed by BOTH the battery-sensor id and the
        # vacuum id, each mapping to the vacuum id — drop every entry pointing
        # at this vacuum (value match avoids recomputing the sensor id).
        for key in [k for k, v in self._battery_to_vacuum.items() if v == vacuum_entity_id]:
            self._battery_to_vacuum.pop(key, None)
        self._pending_post_job.pop(vacuum_entity_id, None)

    def _wire_vacuum(self, vacuum_entity_id: str) -> None:
        if vacuum_entity_id in self._vacuum_unsubs:
            return

        object_id = vacuum_entity_id.split(".", 1)[-1]
        # Prefer the adapter's declared battery entity; fall back to the Eufy
        # suffix convention only if the adapter isn't registered yet (setup
        # ordering) or doesn't declare one.
        battery_sensor_id = (
            (get_adapter_config(vacuum_entity_id) or {}).get("entities", {}).get("battery")
            or f"sensor.{object_id}_battery"
        )

        self._battery_to_vacuum[battery_sensor_id] = vacuum_entity_id
        self._battery_to_vacuum[vacuum_entity_id] = vacuum_entity_id

        self.ensure_record(vacuum_entity_id)

        unsubs: list[Callable[[], None]] = []
        unsubs.append(
            async_track_state_change_event(
                self._hass,
                [battery_sensor_id, vacuum_entity_id],
                self._on_state_event,
            )
        )
        self._vacuum_unsubs[vacuum_entity_id] = unsubs

        # Capture an initial sample if we have one already.
        try:
            self._sample_now(vacuum_entity_id)
        except Exception:  # pragma: no cover
            _LOGGER.exception("battery: initial sample failed for %s", vacuum_entity_id)

    @callback
    def _on_state_event(self, event) -> None:
        entity_id = event.data.get("entity_id")
        vacuum_entity_id = self._battery_to_vacuum.get(entity_id)
        if vacuum_entity_id is None:
            return
        self._sample_now(vacuum_entity_id)

    # -- sampling --------------------------------------------------------------

    def _sample_now(self, vacuum_entity_id: str) -> None:
        battery_level = self._manager._get_battery_level(vacuum_entity_id)
        charging = self._is_charging(vacuum_entity_id)
        ts = datetime.now(timezone.utc)
        self._process_sample(
            vacuum_entity_id=vacuum_entity_id,
            battery_level=battery_level,
            charging=charging,
            ts=ts,
        )

    def _has_active_job(self, vacuum_entity_id: str) -> bool:
        """True if the vacuum has any in-progress job across its maps.

        Used at session-open time to classify a charge session as mid-job
        (vacuum paused mid-clean to recharge) vs post-job vs idle.
        """
        from ..jobs.active_job import dispatched_job_is_in_flight

        active_jobs = self._manager.data.get("active_jobs", {})
        per_map = active_jobs.get(vacuum_entity_id, {})
        if not isinstance(per_map, dict):
            return False
        for map_state in per_map.values():
            # Was `started_at and not ended_at`; ended_at is never written to an
            # active-job record, so a finished job read as in-flight indefinitely.
            if dispatched_job_is_in_flight(map_state):
                return True
        return False

    def _is_charging(self, vacuum_entity_id: str) -> bool:
        """Decide whether the vacuum is actively charging right now.

        Delegates to ``EufyVacuumManager._is_charging`` (core/charging.py),
        which reads the dedicated ``entities.charging`` binary sensor and
        returns False when it's absent/unavailable — no substring fallback
        (substring matching on task_status/dock_status has known false
        negatives, e.g. post-job recharges where ``task_status`` lingers as
        ``"completed"``). The local ``except`` branch below only fires for a
        legacy runtime manager that doesn't expose ``_is_charging`` at all.
        """
        try:
            return self._manager._is_charging(vacuum_entity_id)
        except AttributeError:
            # Defensive — older runtime managers may not expose _is_charging
            # yet. Fall back to a minimal substring check on the vacuum
            # entity's own state + attributes (no auxiliary sensor lookups).
            vacuum_state = self._hass.states.get(vacuum_entity_id)
            vacuum_str = vacuum_state.state if vacuum_state else None
            attrs = vacuum_state.attributes if vacuum_state else {}
            task_status = attrs.get("task_status") if attrs else None
            dock_status = attrs.get("dock_status") if attrs else None
            for v in (vacuum_str, task_status, dock_status):
                if v and ("charg" in str(v).lower() or "recharg" in str(v).lower()):
                    return True
            return False

    # -- core compute ----------------------------------------------------------

    def _process_sample(
        self,
        *,
        vacuum_entity_id: str,
        battery_level: int | None,
        charging: bool,
        ts: datetime,
    ) -> None:
        # RP-042/RF-36: None is a GAP, not a delta -- skip entirely rather than
        # difference against it or carry the previous reading forward as if it
        # had been observed (either would be the same lie the fabricated 0 told,
        # just quieter). No anchor advance, no drain/rate update, no session
        # sample -- this sample simply didn't happen as far as the record goes.
        if battery_level is None or battery_level < 0 or battery_level > 100:
            return

        record = self.ensure_record(vacuum_entity_id)
        prev_level = record.get("last_battery_level")
        prev_ts_str = record.get("last_sample_ts")
        prev_ts = _parse_iso(prev_ts_str)

        delta_pct = None
        rate_per_min = None
        drain_added = 0.0
        # Non-null only when this sample's raw_delta was thrown out by the
        # MAX_DELTA_PCT guard. Surfaced in the JSONL so post-hoc analysis can
        # see which observations were rejected and how big the flip was.
        rejected_delta_pct: float | None = None
        zone = _zone_for(battery_level)

        advance_anchor = True
        if prev_level is not None and prev_ts is not None:
            elapsed_sec = (ts - prev_ts).total_seconds()
            advance_anchor = elapsed_sec > 0
            if elapsed_sec > 0:
                raw_delta = battery_level - prev_level  # +charging, -draining
                if abs(raw_delta) <= MAX_DELTA_PCT:
                    delta_pct = float(raw_delta)

                    # Cycle accounting — drain only, valid over any interval.
                    if raw_delta < 0:
                        drain_added = float(-raw_delta)
                        record["cumulative_drain_pct"] = (
                            float(record.get("cumulative_drain_pct") or 0.0) + drain_added
                        )
                        record["cycles"] = round(
                            record["cumulative_drain_pct"] / 100.0, 4
                        )

                    # Rate metrics — only meaningful for charging samples taken
                    # within a short window. Long gaps (HA restart) would produce
                    # a misleading averaged-over-the-gap value.
                    if raw_delta > 0 and elapsed_sec <= MAX_RATE_INTERVAL_SEC:
                        rate_per_min = delta_pct / (elapsed_sec / 60.0)
                        # live:BATT-ZONE-1 — a 1% quantum over a short interval reads
                        # as a huge rate. Caught by VALUE because the device's sample
                        # cadence rules out catching it by interval (see the constant).
                        if rate_per_min > MAX_PLAUSIBLE_RATE_PCT_PER_MIN:
                            _LOGGER.warning(
                                "battery: implausible charge rate %.4f %%/min "
                                "(%.2f%% over %.0fs, zone=%s) — above %.2f, discarding "
                                "the sample rather than publishing it",
                                rate_per_min, delta_pct, elapsed_sec, zone,
                                MAX_PLAUSIBLE_RATE_PCT_PER_MIN,
                            )
                            record["stats"]["rejected_rate_per_min"] = round(rate_per_min, 4)
                            rate_per_min = None
                    else:
                        rate_per_min = None

                    if rate_per_min is not None:
                        record["stats"]["rate_overall_per_min"] = round(rate_per_min, 4)
                        if zone == "low":
                            record["stats"]["rate_low_zone_per_min"] = round(rate_per_min, 4)
                        elif zone == "high":
                            record["stats"]["rate_high_zone_per_min"] = round(rate_per_min, 4)

                        # Regime attribution — split this charging interval
                        # into CC (50→80) and CV (80→90) portions, weighted
                        # linearly by percentage span. Same constant-rate-
                        # within-a-sample assumption that rate_per_min already
                        # makes; we just split the time across the boundary.
                        #
                        # Runs BEFORE _update_session so the closing sample
                        # (battery hits 100 / charging flips false) is still
                        # attributed to the open session before _update_session
                        # closes it. Skipping the transition sample (charging
                        # just started, current_session still None) is the
                        # correct trade — its delta crosses a non-charging gap
                        # of unknown duration, so attributing the full
                        # elapsed_sec to charging would be misleading.
                        if record.get("current_session") is not None:
                            sess = record["current_session"]

                            # RP-043/RP-044: session-scoped zone-rate accumulation
                            # (running sum + count) -- mirrors the record-level
                            # rate_low_zone_per_min/rate_high_zone_per_min stats
                            # just above, but scoped to THIS session so a fresh
                            # charge's ETA doesn't lean on a previous session's
                            # leftover value. Fires on every interval-valid
                            # charging sample the same as the record-level
                            # write, independent of the CC/CV window gates below.
                            if zone == "low":
                                sess["low_zone_rate_sum"] = (
                                    float(sess.get("low_zone_rate_sum") or 0.0) + rate_per_min
                                )
                                sess["low_zone_rate_samples"] = (
                                    int(sess.get("low_zone_rate_samples") or 0) + 1
                                )
                            elif zone == "high":
                                sess["high_zone_rate_sum"] = (
                                    float(sess.get("high_zone_rate_sum") or 0.0) + rate_per_min
                                )
                                sess["high_zone_rate_samples"] = (
                                    int(sess.get("high_zone_rate_samples") or 0) + 1
                                )

                            lo, hi = prev_level, battery_level
                            win_lo = max(lo, CC_ZONE_MIN)
                            win_hi = min(hi, CV_ZONE_MAX)
                            if win_hi > win_lo:
                                cc_lo = max(win_lo, CC_ZONE_MIN)
                                cc_hi = min(win_hi, CC_ZONE_MAX)
                                cv_lo = max(win_lo, CC_ZONE_MAX)
                                cv_hi = min(win_hi, CV_ZONE_MAX)
                                cc_span = max(cc_hi - cc_lo, 0.0)
                                cv_span = max(cv_hi - cv_lo, 0.0)
                                full_span = float(hi - lo)
                                if full_span > 0:
                                    elapsed_min = elapsed_sec / 60.0
                                    if cc_span > 0:
                                        sess["cc_duration_min"] = float(
                                            sess.get("cc_duration_min") or 0.0
                                        ) + (cc_span / full_span) * elapsed_min
                                        sess["cc_delta_pct"] = float(
                                            sess.get("cc_delta_pct") or 0.0
                                        ) + cc_span
                                    if cv_span > 0:
                                        sess["cv_duration_min"] = float(
                                            sess.get("cv_duration_min") or 0.0
                                        ) + (cv_span / full_span) * elapsed_min
                                        sess["cv_delta_pct"] = float(
                                            sess.get("cv_delta_pct") or 0.0
                                        ) + cv_span
                else:
                    # Guard rejected this observation. Capture the magnitude
                    # for the JSONL audit trail. delta_pct stays None so
                    # downstream rate/drain/regime accounting correctly
                    # ignores the rejected sample.
                    rejected_delta_pct = float(raw_delta)

        # Session lifecycle.
        self._update_session(record, battery_level, charging, ts, rate_per_min)

        # DR-BAT-2: an out-of-order sample (elapsed_sec <= 0) is correctly
        # excluded from the delta/rate/drain accounting above, and its level/ts
        # do not move the anchor -- else the NEXT (genuinely newer) sample
        # computes its own delta against a stale, wrong anchor.
        #
        # THIS GUARD IS NARROWER THAN IT READS, AND THIS COMMENT USED TO SAY
        # OTHERWISE. Only the two fields inside the block are held. The sample has
        # ALREADY reached _update_session above, and last_charging is written below
        # unconditionally -- so an out-of-order sample can still OPEN or CLOSE a
        # charge session, carrying its own stale ts and battery_level in. That can
        # write a session_history_recent entry, and a sessions.csv row, whose end_ts
        # precedes its own start_ts. Nothing repairs those; rebaseline() does not
        # clear session history.
        #
        # IF YOU CLOSE THIS, CLOSE BOTH. Moving _update_session inside without
        # last_charging makes every repeated stale sample re-open the session;
        # moving last_charging without _update_session makes the next genuine
        # sample see a false transition and restart a live one. Either half alone
        # is worse than neither. (Ledger C15; the drafted invariant "a rejected
        # datum is rejected for every purpose" would say close it.)
        #
        # LEFT OPEN ON EVIDENCE, NOT OVERSIGHT. elapsed_sec <= 0 needs the wall
        # clock to step BACKWARDS: ts is minted per-sample from datetime.now() and
        # never inherited from a state object, so two co-timed samples cannot
        # collide. 104 vacuum-days of samples.jsonl across two live machines hold
        # no such step, and 387 archived sessions hold no inverted row -- the
        # signature this would leave. Mechanism certain, occurrence unobserved.
        if advance_anchor:
            record["last_battery_level"] = int(battery_level)
            record["last_sample_ts"] = ts.isoformat()
        record["last_charging"] = bool(charging)

        # Persist + notify. The append is offloaded to a worker thread because
        # _process_sample runs on the event loop (initial sync sample at setup
        # and the @callback state-change path) — direct file I/O here trips
        # HA's blocking-call detector. async_add_executor_job returns a Future
        # that runs on the executor pool whether or not we hold the reference;
        # we don't need to wrap it in async_create_task (which expects a
        # coroutine and rejects Futures under Python 3.14).
        self._hass.async_add_executor_job(
            partial(
                raw_store.append_sample,
                config_dir=self._config_dir,
                vacuum_entity_id=vacuum_entity_id,
                sample={
                    "ts": ts.isoformat(),
                    "battery_level": battery_level,
                    "charging": charging,
                    "delta_pct": delta_pct,
                    "rate_per_min": (round(rate_per_min, 4) if rate_per_min is not None else None),
                    "zone": zone,
                    "drain_added": drain_added,
                    "cycles": record.get("cycles"),
                    "rejected_delta_pct": rejected_delta_pct,
                },
            )
        )
        self._schedule_save()
        self._notify(vacuum_entity_id)

    # -- sessions --------------------------------------------------------------

    def _update_session(
        self,
        record: dict[str, Any],
        battery_level: int,
        charging: bool,
        ts: datetime,
        rate_per_min: float | None,
    ) -> None:
        session = record.get("current_session")

        # Force-close stale sessions
        session_was_discarded = False
        if session is not None:
            start_ts = _parse_iso(session.get("start_ts"))
            if start_ts is not None and (ts - start_ts) > timedelta(hours=SESSION_MAX_HOURS):
                _LOGGER.debug(  # pragma: no cover
                    "battery: discarding stale session for vacuum (%s old)",
                    ts - start_ts,
                )
                record["current_session"] = None
                session = None
                session_was_discarded = True

        prev_charging = bool(record.get("last_charging"))

        # Open a new session when charging begins -- or when charging was
        # already under way but its session was just force-closed as stale
        # (DR-BAT-3): without the session_was_discarded check, prev_charging
        # is already True so this branch never fires, and tracking goes dark
        # until charging flips false and true again.
        if charging and (not prev_charging or session_was_discarded):
            vacuum_entity_id = self._lookup_vacuum_for_record(record)
            kind = self._classify_session_kind(vacuum_entity_id)
            record["current_session"] = {
                "start_ts": ts.isoformat(),
                "start_battery": int(battery_level),
                "samples": 1,
                "rate_sum": 0.0,
                "rate_min": None,
                "rate_max": None,
                "kind": kind,
                # Per-regime accumulators populated by the attribution block
                # in _process_sample as each charging interval crosses the
                # CC (50→80) and CV (80→90) windows.
                "cc_duration_min": 0.0,
                "cc_delta_pct": 0.0,
                "cv_duration_min": 0.0,
                "cv_delta_pct": 0.0,
                # RP-043/RP-044: session-scoped low/high-zone rate accumulators
                # (running sum + count, mirrors the record-level
                # rate_low_zone_per_min/rate_high_zone_per_min stats but
                # private to THIS charge) -- so the ETA can prefer a rate
                # this session has actually measured over a carried-over
                # value left by a previous, unrelated charge.
                "low_zone_rate_sum": 0.0,
                "low_zone_rate_samples": 0,
                "high_zone_rate_sum": 0.0,
                "high_zone_rate_samples": 0,
            }
            return

        if session is None:
            return

        # Accumulate while charging.
        if charging:
            session["samples"] = int(session.get("samples", 0)) + 1
            if rate_per_min is not None and rate_per_min > 0:
                session["rate_sum"] = float(session.get("rate_sum") or 0.0) + rate_per_min
                rmin = session.get("rate_min")
                rmax = session.get("rate_max")
                session["rate_min"] = rate_per_min if rmin is None else min(rmin, rate_per_min)
                session["rate_max"] = rate_per_min if rmax is None else max(rmax, rate_per_min)

        # Close when no longer charging or at full.
        if (not charging) or battery_level >= 100:
            self._close_session(record, session, end_battery=int(battery_level), ts=ts)

    def _close_session(
        self,
        record: dict[str, Any],
        session: dict[str, Any],
        *,
        end_battery: int,
        ts: datetime,
    ) -> None:
        start_ts = _parse_iso(session.get("start_ts")) or ts
        duration_min = max(0.0, (ts - start_ts).total_seconds() / 60.0)
        start_battery = int(session.get("start_battery") or end_battery)
        delta_pct = end_battery - start_battery
        samples = int(session.get("samples", 0))
        avg = (
            (session.get("rate_sum") or 0.0) / samples
            if samples > 0
            else None
        )
        kind = str(session.get("kind") or "idle")

        # Per-regime accumulators. Default to 0.0 so sessions opened before
        # the regime-split rebuild still close cleanly — they just won't
        # contribute to the new baseline (no anchor data) and read None for
        # cc_min_per_pct / cv_min_per_pct.
        cc_dur = float(session.get("cc_duration_min") or 0.0)
        cc_pct = float(session.get("cc_delta_pct") or 0.0)
        cv_dur = float(session.get("cv_duration_min") or 0.0)
        cv_pct = float(session.get("cv_delta_pct") or 0.0)

        summary = {
            "start_ts": start_ts.isoformat(),
            "end_ts": ts.isoformat(),
            "duration_min": round(duration_min, 2),
            "start_battery": start_battery,
            "end_battery": end_battery,
            "delta_pct": delta_pct,
            "avg_rate_per_min": round(avg, 4) if avg is not None else None,
            "min_rate_per_min": (
                round(session["rate_min"], 4) if session.get("rate_min") is not None else None
            ),
            "max_rate_per_min": (
                round(session["rate_max"], 4) if session.get("rate_max") is not None else None
            ),
            "samples": samples,
            "ended_reason": "full" if end_battery >= 100 else "stopped",
            "kind": kind,
            # Regime-split fields. Raw values for audit + future re-derivation;
            # min_per_pct values for direct use in _update_health. Both can be
            # None for sessions that never crossed a given regime window.
            "cc_duration_min": round(cc_dur, 4),
            "cc_delta_pct": round(cc_pct, 4),
            "cv_duration_min": round(cv_dur, 4),
            "cv_delta_pct": round(cv_pct, 4),
            "cc_min_per_pct": round(cc_dur / cc_pct, 4) if cc_pct > 0 else None,
            "cv_min_per_pct": round(cv_dur / cv_pct, 4) if cv_pct > 0 else None,
        }

        # Update last-charge stats.
        if delta_pct > 0 and duration_min > 0:
            record["stats"]["last_charge_duration_min"] = round(duration_min, 2)
            record["stats"]["last_charge_delta_pct"] = delta_pct

        # Append to history ring buffer.
        history = record.setdefault("session_history_recent", [])
        history.append(summary)
        if len(history) > HISTORY_LIMIT:
            del history[: len(history) - HISTORY_LIMIT]

        # Update health proxy (uses qualifying full charges).
        self._update_health(record)

        # Mid-job recharges are gold-standard data — tight, consistent
        # 15→75 windows in pure CC region. Track their rate as its own stat
        # for a high-quality second opinion on health.
        if kind == "mid_job" and avg is not None and avg > 0 and delta_pct > 0:
            self._update_mid_job_rate_stat(record, avg)

        record["current_session"] = None

        vacuum_entity_id = self._lookup_vacuum_for_record(record)
        # Offloaded to worker thread — _close_session is reachable from sync
        # state-change callbacks, so direct CSV I/O would block the event loop.
        # async_create_task wrapping was a Python 3.14 TypeError (Task expects
        # a coroutine, not a Future); the executor future runs regardless.
        self._hass.async_add_executor_job(
            partial(
                raw_store.append_session,
                config_dir=self._config_dir,
                vacuum_entity_id=vacuum_entity_id,
                session=summary,
            )
        )

        # Post-job recharge linkage — attach to last_job if pending and timely.
        if kind == "post_job":
            self._attach_post_job_charge_if_pending(vacuum_entity_id, summary)

    def _classify_session_kind(self, vacuum_entity_id: str) -> str:
        """Tag a newly opened charge session with its operational context.

        - ``mid_job`` — vacuum has an in-progress job (will resume after charge).
        - ``post_job`` — within POST_JOB_CHARGE_LINK_HOURS of a finalized job.
        - ``idle`` — none of the above (user docked it, opportunistic top-up).
        """
        try:
            if self._has_active_job(vacuum_entity_id):
                return "mid_job"
        except Exception:  # pragma: no cover
            _LOGGER.debug("battery: active-job check failed", exc_info=True)

        pending = self._pending_post_job.get(vacuum_entity_id)
        if pending:
            recorded_ts = pending.get("recorded_ts")
            if isinstance(recorded_ts, datetime):
                age = datetime.now(timezone.utc) - recorded_ts
                if age <= timedelta(hours=POST_JOB_CHARGE_LINK_HOURS):
                    return "post_job"

        return "idle"

    def _update_mid_job_rate_stat(
        self,
        record: dict[str, Any],
        avg_rate_per_min: float,
    ) -> None:
        """Maintain a rolling mean of mid-job recharge rates.

        These sessions are the cleanest health signal we get — same start/end
        zone, same thermal state — so a drop in the mean is an early sign of
        capacity loss before the 0→100 baseline shifts.
        """
        stats = record.setdefault("mid_job_recharge_stats", {
            "count": 0,
            "rate_sum": 0.0,
            "rate_mean_per_min": None,
            "last_rate_per_min": None,
            "last_recorded_at": None,
        })
        stats["count"] = int(stats.get("count", 0)) + 1
        stats["rate_sum"] = float(stats.get("rate_sum", 0.0)) + float(avg_rate_per_min)
        stats["rate_mean_per_min"] = round(stats["rate_sum"] / stats["count"], 4)
        stats["last_rate_per_min"] = round(float(avg_rate_per_min), 4)
        stats["last_recorded_at"] = datetime.now(timezone.utc).isoformat()

    def _lookup_vacuum_for_record(self, record: dict[str, Any]) -> str:
        # Reverse lookup — small map.
        for vid, rec in self._root()["vacuums"].items():
            if rec is record:
                return vid
        return "unknown"

    # -- health proxy ----------------------------------------------------------

    def _update_health(self, record: dict[str, Any]) -> None:
        """Update CC and CV regime indices plus the headline health_pct.

        - cc_charge_speed_pct: capacity proxy (50→80). Aged cells hold less
          energy per percent, so %/min rises with age and ratio falls below
          100. Higher = healthier.
        - cv_charge_speed_pct: resistance proxy (80→90). Aged cells force
          earlier/longer taper, so %/min falls with age and ratio falls
          below 100. Higher = healthier.
        - health_pct: alias of cv_charge_speed_pct. CV is the conventional
          "battery health" signal users expect; the headline keeps that
          framing while CC is exposed separately for the capacity story.
          Stored uncapped here (== cv_charge_speed_pct); the _battery_health
          SENSOR caps it at 100% for display (never "healthier than new").

        RP-045 (i): the comparison set used below is ``health_qualifying_sessions``,
        retained separately from the HISTORY_LIMIT-capped ``session_history_recent``
        display ring, so a baseline's own qualifying session can't rotate out from
        under it. Promoted here (idempotent, de-duped by start/end timestamp) rather
        than only at session close, so a record whose retained set hasn't caught up
        yet — an older on-disk record, or a test driving this method directly —
        still computes from whatever is currently in the ring.

        RP-045 (ii): cc- and cv-side qualification are decoupled — a session is
        eligible to contribute a cc-side sample if it starts at/below
        HEALTH_QUALIFY_START_MAX (regardless of where it ends), and a cv-side
        sample if it ends at/above HEALTH_QUALIFY_END_MIN (regardless of where it
        starts). The baseline ANCHOR keeps the original, stricter requirement (one
        session satisfying both, with both regimes populated) — it is a single
        coherent reference point, not a per-regime one, so decoupling it would
        change what it means, not just how it's found.
        """
        baseline = record.get("baseline", {})

        retained = record.setdefault("health_qualifying_sessions", [])
        retained_keys = {
            (s.get("start_ts"), s.get("end_ts")) for s in retained if isinstance(s, dict)
        }
        for s in record.get("session_history_recent", []) or []:
            if not isinstance(s, dict):
                continue
            key = (s.get("start_ts"), s.get("end_ts"))
            if key in retained_keys:
                continue
            if _session_cc_qualifies(s) or _session_cv_qualifies(s):
                retained.append(s)
                retained_keys.add(key)
        if len(retained) > HEALTH_QUALIFYING_RETENTION_LIMIT:
            del retained[: len(retained) - HEALTH_QUALIFYING_RETENTION_LIMIT]

        cc_qualifying = [s for s in retained if _session_cc_qualifies(s)]
        cv_qualifying = [s for s in retained if _session_cv_qualifies(s)]

        # Anchor on the first FULLY qualifying session (both the original
        # start<=50/end>=90 window AND both regimes populated) — unchanged
        # criteria and unchanged "never re-anchor" timing, just sourced from
        # the retained set instead of the rotating display ring.
        if baseline.get("cc_min_per_pct") is None or baseline.get("cv_min_per_pct") is None:
            for seed in retained:
                start = seed.get("start_battery")
                end = seed.get("end_battery")
                if (
                    start is not None and end is not None
                    and start <= HEALTH_QUALIFY_START_MAX
                    and end >= HEALTH_QUALIFY_END_MIN
                    and seed.get("cc_min_per_pct") is not None
                    and seed.get("cv_min_per_pct") is not None
                ):
                    baseline["cc_min_per_pct"] = seed["cc_min_per_pct"]
                    baseline["cv_min_per_pct"] = seed["cv_min_per_pct"]
                    baseline["session_count"] = 1
                    baseline["anchored_at"] = seed.get("end_ts")
                    break

        cc_pct, cc_rejected = self._compute_regime_pct(
            cc_qualifying, baseline.get("cc_min_per_pct"), "cc_min_per_pct"
        )
        cv_pct, cv_rejected = self._compute_regime_pct(
            cv_qualifying, baseline.get("cv_min_per_pct"), "cv_min_per_pct"
        )
        record["stats"]["cc_charge_speed_pct"] = cc_pct
        record["stats"]["cv_charge_speed_pct"] = cv_pct
        # live:BATT-CV-1 — what the plausibility guard threw away, kept so the failure
        # is diagnosable. A rejected value that leaves no trace is how "the field reads
        # unknown" becomes indistinguishable from "the field was never computed", which
        # is the confusion RP-045 spent a whole packet undoing.
        record["stats"]["cc_charge_speed_rejected_pct"] = cc_rejected
        record["stats"]["cv_charge_speed_rejected_pct"] = cv_rejected
        # Headline alias — the entity_id stays "_battery_health" for
        # continuity, but the value is now explicitly the CV (resistance)
        # signal, which is what "battery health" conventionally means.
        record["stats"]["health_pct"] = record["stats"]["cv_charge_speed_pct"]

        # RP-045 (iii): a device that (i)+(ii) still can't produce a value for
        # must say so rather than read None forever — but only once there's
        # enough session history to say WHY; a brand-new install with zero
        # charges yet is genuinely "still building", not stuck.
        if record["stats"]["health_pct"] is None and cv_rejected is not None:
            # live:BATT-CV-1 — REJECTED is not the same as NEVER COMPUTED. Saying
            # "no completed charge has started low enough" would be a lie here: one
            # did, and the number it produced was impossible. Naming that sends a
            # reader to the session data instead of to their charging habits.
            record["stats"]["health_unavailable_reason"] = "implausible_regime_ratio"
            record["stats"]["health_unavailable_reason_text"] = (
                f"A health figure was computed but rejected as implausible "
                f"({cv_rejected}%, outside {REGIME_PCT_MIN:.0f}-{REGIME_PCT_MAX:.0f}%). "
                "This is a ratio against the baseline charge, so a regime measured "
                "over a very short span can inflate it without limit. The next "
                "qualifying charge that spans the full window will replace it."
            )
        elif record["stats"]["health_pct"] is None and record.get("session_history_recent"):
            record["stats"]["health_unavailable_reason"] = "insufficient_discharge_data"
            record["stats"]["health_unavailable_reason_text"] = (
                f"No completed charge has started at {HEALTH_QUALIFY_START_MAX}% or "
                f"lower and reached {HEALTH_QUALIFY_END_MIN}% or higher, so there is "
                "no baseline to compare against yet. A vacuum that docks frequently "
                "and rarely runs low may never produce one on its own."
            )
        else:
            record["stats"]["health_unavailable_reason"] = None
            record["stats"]["health_unavailable_reason_text"] = None

    def _compute_regime_pct(
        self,
        qualifying: list[dict[str, Any]],
        baseline_value: float | None,
        field: str,
    ) -> tuple[float | None, float | None]:
        """Current regime % vs baseline, as ``(value, rejected)``.

        ``value`` is None when there is no usable data OR when the computed figure is
        implausible (live:BATT-CV-1); in the latter case ``rejected`` carries the raw
        number so it can be reported rather than vanish. Exactly one of the two is
        ever non-None.
        """
        if baseline_value is None:
            return None, None

        cutoff = datetime.now(timezone.utc) - timedelta(days=CURRENT_WINDOW_DAYS)
        recent: list[float] = []
        for s in qualifying:
            value = s.get(field)
            if value is None:
                continue
            end_ts = _parse_iso(s.get("end_ts"))
            if end_ts is not None and end_ts >= cutoff:
                recent.append(float(value))

        if not recent:
            # Fallback: most recent qualifying session that has this regime.
            for s in reversed(qualifying):
                value = s.get(field)
                if value is not None:
                    recent = [float(value)]
                    break
            if not recent:
                return None, None

        current = sum(recent) / len(recent)
        if current <= 0:
            return None, None
        value = round(baseline_value / current * 100.0, 1)
        # live:BATT-CV-1 — the ratio is unbounded by construction, so plausibility is
        # checked HERE rather than trusted. Out-of-band returns None (a state these
        # fields have always had and every consumer already handles) and hands the raw
        # figure back so it can be surfaced instead of silently swallowed — the same
        # shape as `rejected_delta_pct` on the drain accumulator, which is the guard
        # this one was missing.
        if not (REGIME_PCT_MIN <= value <= REGIME_PCT_MAX):
            _LOGGER.warning(
                "battery: implausible %s regime speed %.1f%% (baseline %.4f vs current "
                "%.4f min/pct over %d session(s)) — outside %.0f-%.0f%%, reporting "
                "unknown rather than publishing it",
                field, value, baseline_value, current, len(recent),
                REGIME_PCT_MIN, REGIME_PCT_MAX,
            )
            return None, value
        return value, None

    # -- baseline management ---------------------------------------------------

    def rebaseline(self, vacuum_entity_id: str) -> bool:
        """Clear the health baseline so the next qualifying session re-anchors it.

        Intended for use after a battery replacement. Does not touch cycles,
        aggregates, session history, mid-job stats, or job metrics — only the
        health proxy's anchor point (and, per RP-045, the separately-retained
        qualifying-session set it's compared against — see below). The next
        qualifying recharge (start <= HEALTH_QUALIFY_START_MAX, end >=
        HEALTH_QUALIFY_END_MIN) will seed a fresh baseline.

        Returns True if a record existed for the vacuum and was cleared,
        False if no record was found.
        """
        vacuums = self._root()["vacuums"]
        if vacuum_entity_id not in vacuums:
            return False
        record = self.ensure_record(vacuum_entity_id)
        baseline = record["baseline"]
        baseline["cc_min_per_pct"] = None
        baseline["cv_min_per_pct"] = None
        baseline["session_count"] = 0
        baseline["anchored_at"] = None
        # Legacy field — only present on records that pre-date the regime
        # split. Clear it too so a rebaselined record looks consistently
        # empty regardless of upgrade history.
        if "min_per_pct" in baseline:
            baseline["min_per_pct"] = None
        stats = record["stats"]
        stats["cc_charge_speed_pct"] = None
        stats["cv_charge_speed_pct"] = None
        stats["health_pct"] = None
        stats["health_unavailable_reason"] = None
        stats["health_unavailable_reason_text"] = None
        # RP-045: the retained qualifying-session set exists precisely so a
        # baseline's anchor session can't rotate out from under it — but
        # that means it must be cleared here too, or the very next
        # _update_health call would re-anchor off an OLD (pre-swap) session
        # still sitting in the retained store instead of a fresh one.
        record["health_qualifying_sessions"] = []
        self._schedule_save()
        self._notify(vacuum_entity_id)
        return True

    # -- job metrics ingestion -------------------------------------------------

    def _apply_metrics_to_aggregates(
        self,
        record: dict[str, Any],
        metrics: dict[str, Any],
    ) -> None:
        """Fold one job's metrics into the drain aggregates.

        THE single definition of "which buckets does this job feed". Shared by the live
        path (``record_job_metrics``) and the archive replay (``rebuild_job_aggregates``)
        so a rebuild reproduces exactly what the live folds produced — two copies of this
        bucket-selection logic would drift, and a rebuild that disagreed with the live path
        would be worse than no rebuild.
        """
        aggregates = record.setdefault("job_aggregates", {})
        aggregates.setdefault("all_jobs", _new_aggregate_bucket())
        aggregates.setdefault("by_clean_mode", {})
        aggregates.setdefault("by_fan_speed", {})
        aggregates.setdefault("by_water_level", {})

        self._update_aggregate_bucket(aggregates["all_jobs"], metrics)

        # A mid-job recharge nets out of the raw start−end drain, understating the true
        # discharge — so keep a flagged run OUT of the per-config drain means (the same
        # anti-bias spirit as the is_single_* gates). last_job / all_jobs still record it.
        single_ok = not bool(metrics.get("mid_job_recharge"))

        if single_ok and metrics.get("is_single_clean_mode") and metrics.get("single_clean_mode"):
            bucket = aggregates["by_clean_mode"].setdefault(
                metrics["single_clean_mode"], _new_aggregate_bucket()
            )
            self._update_aggregate_bucket(bucket, metrics)

        if single_ok and metrics.get("is_single_fan_speed") and metrics.get("single_fan_speed"):
            bucket = aggregates["by_fan_speed"].setdefault(
                metrics["single_fan_speed"], _new_aggregate_bucket()
            )
            self._update_aggregate_bucket(bucket, metrics)

        if single_ok and metrics.get("is_single_water_level") and metrics.get("single_water_level"):
            bucket = aggregates["by_water_level"].setdefault(
                metrics["single_water_level"], _new_aggregate_bucket()
            )
            self._update_aggregate_bucket(bucket, metrics)

    def rebuild_job_aggregates(
        self,
        *,
        vacuum_entity_id: str,
        metrics_list: list[dict[str, Any]],
    ) -> int:
        """Recompute the drain aggregates from scratch over an archive of job metrics.

        ``job_aggregates`` is an incremental read-modify-write store outside the learning
        rebuild, so a bad sample — a duplicate finalize, or a run that should have been
        excluded — used to sit in the drain means permanently. Per-config buckets are
        narrow, so a poisoned sample may never dilute.

        Rebuilds from EMPTY: folding onto the existing aggregates would preserve exactly
        the samples this exists to remove.

        Deliberately does NOT touch ``last_job`` or the pending-post-job-charge linkage.
        Those are point-in-time state about the MOST RECENT run, not derived history —
        replaying them would leave a stale ``post_job_charge`` slot for the next real
        charge session to link into. Only the aggregates are recomputed.

        Returns the number of metric sets applied. Caller supplies the archive because the
        battery subsystem does not own it.
        """
        record = self.ensure_record(vacuum_entity_id)
        record["job_aggregates"] = {
            "all_jobs": _new_aggregate_bucket(),
            "by_clean_mode": {},
            "by_fan_speed": {},
            "by_water_level": {},
        }
        applied = 0
        for metrics in metrics_list or []:
            if not isinstance(metrics, dict):
                continue
            self._apply_metrics_to_aggregates(record, metrics)
            applied += 1

        self._schedule_save()
        self._notify(vacuum_entity_id)
        return applied

    def record_job_metrics(
        self,
        *,
        vacuum_entity_id: str,
        metrics: dict[str, Any],
        job_id: str | None = None,
    ) -> None:
        """Record battery metrics from a finalized job.

        - Always: stores the metrics as ``last_job`` and updates the
          ``all_jobs`` aggregate.
        - Single-bucket runs additionally feed ``by_clean_mode``,
          ``by_fan_speed``, and ``by_water_level`` aggregates — only those
          jobs can be cleanly attributed to a single setting.
        - Sets a pending-post-job-charge flag so the next completed charge
          session links back to this job's record.
        """
        if not isinstance(metrics, dict):
            return

        record = self.ensure_record(vacuum_entity_id)
        now = datetime.now(timezone.utc)

        # Snapshot last-job — keep it small enough for sensor attributes.
        last_job = {
            "job_id": job_id,
            "recorded_at": now.isoformat(),
            "battery_used_pct": metrics.get("battery_used_pct"),
            "duration_min": metrics.get("duration_min"),
            "area_m2": metrics.get("area_m2"),
            "drain_per_min": metrics.get("drain_per_min"),
            "drain_per_hour": metrics.get("drain_per_hour"),
            "drain_per_m2": metrics.get("drain_per_m2"),
            "is_single_clean_mode": bool(metrics.get("is_single_clean_mode")),
            "is_single_fan_speed": bool(metrics.get("is_single_fan_speed")),
            "is_single_water_level": bool(metrics.get("is_single_water_level")),
            "mid_job_recharge": bool(metrics.get("mid_job_recharge")),
            "single_clean_mode": metrics.get("single_clean_mode"),
            "single_fan_speed": metrics.get("single_fan_speed"),
            "single_water_level": metrics.get("single_water_level"),
            "by_clean_mode": metrics.get("by_clean_mode"),
            "by_fan_speed": metrics.get("by_fan_speed"),
            "by_water_level": metrics.get("by_water_level"),
            "edge_mopping": metrics.get("edge_mopping"),
            "weighted_by": metrics.get("weighted_by"),
            "post_job_charge": None,  # filled later by _close_session
        }
        record["last_job"] = last_job

        self._apply_metrics_to_aggregates(record, metrics)

        # Mark the next charge session for post-job linkage. Cleared either
        # when consumed by _close_session() or when stale.
        self._pending_post_job[vacuum_entity_id] = {
            "job_id": job_id,
            "recorded_ts": now,
        }

        self._schedule_save()
        self._notify(vacuum_entity_id)

    @staticmethod
    def _update_aggregate_bucket(bucket: dict[str, Any], metrics: dict[str, Any]) -> None:
        """Fold one job into ``bucket`` and refresh the rolling means.

        ``count`` is every job folded in and increments unconditionally. It is NOT
        the sample size of any mean — ``samples_duration`` / ``samples_area`` are.

        EACH MEAN IS A RATIO WHOSE TOP AND BOTTOM COUNT THE SAME JOBS (C17). Until
        2026-08-21 one ``drain_pct_sum`` fed all three means while each denominator
        accumulated over a different subset, so a job with drain and duration but no
        measured area still added drain to the per-m2 numerator and nothing to its
        denominator.

        The zero-guard on the division HID it rather than preventing it: it fires
        only when NO job in the bucket had area, so a single measured job was enough
        for the ratio to proceed over mismatched populations. Measured: six jobs of
        10 m2 at 20% drain among ten recorded jobs published 200/60 = 3.333 %/m2
        where the honest figure over the six is 2.0 — 67% high, and worse the more
        area-less runs land.

        Area is the read that goes missing in practice: it loses the same
        finalize-time race ``job_finalizer.py`` documents for cleaning_time, and no
        learning-blocker stops such a job being recorded.
        """
        bucket["count"] = int(bucket.get("count", 0)) + 1

        drain = metrics.get("battery_used_pct")
        duration = metrics.get("duration_min")
        area = metrics.get("area_m2")

        # A raw total over every job that reported a drain. NOT a mean input: since the
        # numerators were split it has no reader anywhere in the tree. Kept because it is
        # a PERSISTED KEY in existing records and a true, separate fact; removing it is a
        # storage-shape decision, not a tidy-up.
        if drain is not None:
            bucket["drain_pct_sum"] = float(bucket.get("drain_pct_sum", 0.0)) + float(drain)
        # THE PAIRING, AND IT GATES BOTH SIDES. A ratio's numerator and denominator
        # must count the SAME jobs, so a job reaches a mean only when it carried BOTH
        # halves -- which means the DENOMINATOR is gated on the drain as well.
        #
        # Partnering only the numerators (the first pass at this, 1e2ba0d7) fixes one
        # direction and leaves the mirror: a job with a duration and no drain grew
        # duration_min_sum without growing drain_pct_sum_for_duration, DEFLATING the
        # mean exactly as the original defect INFLATED it. One numerator served three
        # denominators, so the substitution ran both ways and closing one way is not
        # closing it. [BM-5d] is the direction [BM-5b] and [BM-5c] cannot see, because
        # both of those supply a drain and vary the other field.
        #
        # duration_min_sum and area_m2_sum have no consumer outside these three means,
        # so narrowing them costs nothing else. They are denominators, not totals.
        if drain is not None and duration is not None:
            bucket["drain_pct_sum_for_duration"] = (
                float(bucket.get("drain_pct_sum_for_duration", 0.0)) + float(drain)
            )
            bucket["duration_min_sum"] = (
                float(bucket.get("duration_min_sum", 0.0)) + float(duration)
            )
            bucket["samples_duration"] = int(bucket.get("samples_duration", 0)) + 1
        if drain is not None and area is not None:
            bucket["drain_pct_sum_for_area"] = (
                float(bucket.get("drain_pct_sum_for_area", 0.0)) + float(drain)
            )
            bucket["area_m2_sum"] = float(bucket.get("area_m2_sum", 0.0)) + float(area)
            bucket["samples_area"] = int(bucket.get("samples_area", 0)) + 1

        dt_sum = float(bucket.get("drain_pct_sum_for_duration", 0.0))
        da_sum = float(bucket.get("drain_pct_sum_for_area", 0.0))
        t_sum = float(bucket.get("duration_min_sum", 0.0))
        a_sum = float(bucket.get("area_m2_sum", 0.0))

        bucket["drain_per_min_mean"] = round(dt_sum / t_sum, 4) if t_sum > 0 else None
        bucket["drain_per_hour_mean"] = (
            round((dt_sum / t_sum) * 60.0, 4) if t_sum > 0 else None
        )
        bucket["drain_per_m2_mean"] = round(da_sum / a_sum, 4) if a_sum > 0 else None

    def _attach_post_job_charge_if_pending(
        self,
        vacuum_entity_id: str,
        session_summary: dict[str, Any],
    ) -> None:
        """If a job recently finished for this vacuum, attach the just-closed
        charge session as that job's post-job recharge data.

        Time gate: the charge session's start must land within
        POST_JOB_CHARGE_LINK_HOURS of when the job metrics were recorded; an
        idle vacuum shouldn't randomly inherit a recharge from days later.
        """
        pending = self._pending_post_job.get(vacuum_entity_id)
        if not pending:
            return

        recorded_ts = pending.get("recorded_ts")
        if not isinstance(recorded_ts, datetime):
            self._pending_post_job.pop(vacuum_entity_id, None)
            return

        session_start = _parse_iso(session_summary.get("start_ts"))
        if session_start is None or session_start < recorded_ts:
            return  # session opened before the job ended — not its recharge

        if (session_start - recorded_ts) > timedelta(hours=POST_JOB_CHARGE_LINK_HOURS):
            self._pending_post_job.pop(vacuum_entity_id, None)
            return

        record = self.ensure_record(vacuum_entity_id)
        last_job = record.get("last_job")
        if isinstance(last_job, dict):
            last_job["post_job_charge"] = {
                "job_id": pending.get("job_id"),
                "start_ts": session_summary.get("start_ts"),
                "end_ts": session_summary.get("end_ts"),
                "duration_min": session_summary.get("duration_min"),
                "start_battery": session_summary.get("start_battery"),
                "end_battery": session_summary.get("end_battery"),
                "delta_pct": session_summary.get("delta_pct"),
                "avg_rate_per_min": session_summary.get("avg_rate_per_min"),
                "ended_reason": session_summary.get("ended_reason"),
            }

        self._pending_post_job.pop(vacuum_entity_id, None)
        self._notify(vacuum_entity_id)

    # -- save plumbing ---------------------------------------------------------

    def _schedule_save(self) -> None:
        """Fire-and-forget save of the integration's storage.

        Callable from any thread:
        - State-change samples arrive on the event loop (safe path).
        - ``record_job_metrics`` runs from the JobFinalizer's executor pool
          (worker thread), and ``async_create_task`` is event-loop-only.

        ``run_coroutine_threadsafe`` posts the coroutine to the loop from
        whichever thread we're on; if we're already on the loop, fall back
        to ``async_create_task`` directly. Saves are idempotent, so even
        rapid-fire calls just coalesce in the storage layer.
        """
        try:
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None

            coro = self._manager.async_save()
            if running is self._hass.loop:
                self._hass.async_create_task(coro)
            else:
                asyncio.run_coroutine_threadsafe(coro, self._hass.loop)
        except Exception:  # pragma: no cover
            _LOGGER.debug("battery: async_save scheduling failed", exc_info=True)


# === HELPERS =================================================================

def _session_cc_qualifies(session: dict[str, Any]) -> bool:
    """RP-045(ii): is this session usable as a CC-side (50→80) sample on its
    own, independent of whether it also reached the CV window?

    Requires both the threshold (a genuinely low start — a session that
    starts higher skips the slowest part of the CC curve and would bias the
    rate) AND real attributed data (``cc_min_per_pct``): a session whose
    start is <= the threshold but never actually crosses into the 50-80
    window (e.g. 45→48) produces no CC attribution at all and must not be
    treated as a sample just because the start looks low enough.
    """
    start = session.get("start_battery")
    return (
        start is not None
        and start <= HEALTH_QUALIFY_START_MAX
        and session.get("cc_min_per_pct") is not None
    )


def _session_cv_qualifies(session: dict[str, Any]) -> bool:
    """RP-045(ii): CV-side (80→90) counterpart of ``_session_cc_qualifies``.

    A session that starts above CV_ZONE_MAX (e.g. 96→100) can satisfy
    ``end >= HEALTH_QUALIFY_END_MIN`` by threshold alone without ever
    traversing the 80-90 window — the regime-attribution pass in
    ``_process_sample`` correctly leaves ``cv_min_per_pct`` unset for such a
    session, so the ``is not None`` check here is what actually excludes it
    (a 96→100 charge "says nothing about pack capacity" per RP-045's
    prohibited_changes and must not silently feed this regime).
    """
    end = session.get("end_battery")
    return (
        end is not None
        and end >= HEALTH_QUALIFY_END_MIN
        and session.get("cv_min_per_pct") is not None
    )


def _zone_for(level: int) -> str:
    if level <= LOW_ZONE_MAX:
        return "low"
    if level >= HIGH_ZONE_MIN:
        return "high"
    return "mid"


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
