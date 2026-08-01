"""Proof: session avg_rate_per_min divides a rate SUM by the count of ALL samples.

Simulates one charge session at a realistic polling cadence, where the integer
battery percentage does not tick on every sample.
"""
from datetime import datetime, timedelta, timezone
from custom_components.eufy_vacuum.battery.manager import BatteryHealthManager


class _Hass:                      # only async_add_executor_job is reached
    def async_add_executor_job(self, *a, **k): return None


mgr = BatteryHealthManager.__new__(BatteryHealthManager)
mgr._hass = _Hass()
mgr._config_dir = "/tmp"
mgr._save_cb = lambda: None
mgr._listeners = []
mgr._pending_post_job = {}
mgr._data = {"battery": {"vacuums": {}}}
mgr._notify = lambda v: None
mgr._schedule_save = lambda: None
mgr._lookup_vacuum_for_record = lambda r: "vacuum.test"

rec = {"stats": {}, "baseline": {}, "session_history_recent": [], "current_session": None,
       "last_charging": False}
t0 = datetime(2026, 7, 31, 9, 0, tzinfo=timezone.utc)

# Charge 60 -> 70 over 20 min, sampled every 60s. The percentage ticks once every
# other sample, so half the charging samples carry no rate.
def step(level, charging, ts, rate):
    """Mirror _process_sample: _update_session, THEN commit last_charging."""
    mgr._update_session(rec, level, charging, ts, rate)
    rec["last_charging"] = charging


step(60, True, t0, None)                               # open
rate_values, level = [], 60
for i in range(1, 21):
    ts = t0 + timedelta(minutes=i)
    if i % 2 == 0:                                     # percentage ticks
        level += 1
        rate = 1.0                                     # 1% over 1 min
        rate_values.append(rate)
    else:
        rate = None                                    # no tick -> no rate
    step(level, True, ts, rate)
sess = dict(rec["current_session"])
step(level, False, t0 + timedelta(minutes=21), None)   # close

summary = rec["session_history_recent"][-1]
true_mean = sum(rate_values) / len(rate_values)
print(f"charging samples counted (session.samples) : {sess['samples']}")
print(f"samples that produced a rate               : {len(rate_values)}")
print(f"rate_sum                                   : {sess['rate_sum']:.3f}")
print()
print(f"TRUE mean of observed rates                : {true_mean:.3f} %/min")
print(f"reported avg_rate_per_min                  : {summary['avg_rate_per_min']:.3f} %/min")
print(f"understated by                             : "
      f"{(1 - summary['avg_rate_per_min']/true_mean)*100:.0f}%")
print()
print(f"sanity - actual charge was {level-60} pct over 21 min = "
      f"{(level-60)/21:.3f} %/min")
