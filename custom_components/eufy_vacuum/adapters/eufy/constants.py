"""
Empirically tuned constants for the Eufy X10 Pro Omni adapter.

These values were derived from real hardware observation on a single
installed unit. They are not generic defaults. A port to a different
vacuum model must re-measure and replace these values — do not assume
they transfer.

See porting-guide.md for what each constant controls and what a new
brand author needs to measure to provide their own.
"""

# ----------------------
# Mop wash debounce
# ----------------------

# The Eufy X10 Pro Omni dock wash cycle is not a single state flip.
# The full sequence is:
#   Washing → Recycling dirty water → Adding clean water → Washing
# This produces 2-3 "Washing" state appearances per single physical
# wash cycle. The debounce window must span the entire sequence.
#
# Observed average cycle duration: ~46 seconds wall-clock.
# 60 seconds provides a 14-second buffer against cycle variance and
# firmware timing jitter.
MOP_WASH_DEBOUNCE_SECONDS = 60

# Same window applied to the dock event counter in record_dock_event().
# Kept as a separate constant because the two debounce sites serve
# different purposes — one guards the active-job wash count, one guards
# the dock events storage counter.
DOCK_EVENT_MOP_WASH_DEBOUNCE_SECONDS = 60

# Minimum interval between wash count increments in the post-job water
# amendment watcher. Same 60s reasoning as above — the watcher fires on
# dock_status transitions and must not double-count the recycle/refill
# intermediate states.
POST_JOB_AMENDMENT_MIN_WASH_INTERVAL_SECONDS = 60.0

# ----------------------
# Post-job water amendment timeout
# ----------------------

# The X10 Pro Omni washes the mop pad after docking from a mop job.
# This starts approximately 2 seconds after job finalization.
# The amendment watcher must stay open long enough to capture the full
# post-job wash cycle and commit the corrected water actuals to the
# completed job file.
#
# 180 seconds observed as sufficient for the full post-job wash sequence
# including the drying transition that triggers the commit.
POST_JOB_AMENDMENT_TIMEOUT_SECONDS = 180

# ----------------------
# Battery
# ----------------------

# Low battery return threshold. The vacuum returns to dock for recharge
# when battery drops to or below this level during a job.
# Observed on X10 Pro Omni — other models may use a different threshold.
# Used alongside task_status == "returning to charge" as a two-signal
# confirmation of mid-job recharge rather than user-initiated return.
LOW_BATTERY_THRESHOLD_PERCENT = 20

# ----------------------
# Water flow rates
# ----------------------

# Floor application water rates by water level setting.
# Measured on X10 Pro Omni against the dock clean water tank.
# Method: delta percent × tank capacity / elapsed mop minutes across
# multiple single-room mop-only runs at each water level setting.
# These are first-pass floor application rates only — dock wash overhead
# is accounted for separately via DOCK_WASH_OVERHEAD_ML_PER_CYCLE.
WATER_RATE_OFF_ML_PER_MIN = 0.0
WATER_RATE_LOW_ML_PER_MIN = 3.2
WATER_RATE_MEDIUM_ML_PER_MIN = 4.0
WATER_RATE_HIGH_ML_PER_MIN = 5.3

# ----------------------
# Physical tank measurements
# ----------------------

# Physical hardware constants for the X10 Pro Omni dock.
# These do not vary with firmware version or configuration.
# A different model will have different values — check the manufacturer
# spec sheet or measure directly.

# Internal robot water reservoir capacity.
ROBOT_INTERNAL_TANK_ML = 80.0

# Dock clean water tank total capacity.
DOCK_CLEAN_TANK_CAPACITY_ML = 3080.0

# Water consumed by the dock per mop wash cycle.
# Measured as delta percent × tank capacity across observed wash cycles.
# Includes water used for both the wash and the rinse stages within
# a single cycle.
DOCK_WASH_OVERHEAD_ML_PER_CYCLE = 120.0

# ----------------------
# Wash frequency interval bounds
# ----------------------

# The wash frequency interval is user-configurable via
# select.*_wash_frequency_mode and number.*_wash_frequency_value_time.
# These bounds clamp the raw entity value to a safe range for ETA math.
# Observed valid range on X10 Pro Omni firmware: 15–25 minutes.
# Default fallback used when the entity is unavailable.
WASH_INTERVAL_MIN_MINUTES = 15.0
WASH_INTERVAL_MAX_MINUTES = 25.0
WASH_INTERVAL_DEFAULT_MINUTES = 20.0
