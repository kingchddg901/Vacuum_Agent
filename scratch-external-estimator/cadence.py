"""cleaning_time advances in ~30s steps WHILE cleaning. Compare each increment to
wall-clock: ~30s/+30 = in-room cleaning; a long gap per +30 = non-cleaning
(transit / mop wash). Those gaps are the room-segment boundaries on multi-room
runs. Verify on the single-room runs (expect: one big gap = dock->room transit,
then steady ~30s)."""
import csv, datetime as dt

RUNS = [("Run1", r"C:\Users\CKing\Downloads\history.csv"),
        ("Run2", r"C:\Users\CKing\Downloads\same room 2nd run.csv")]

def parse_ts(s):
    s = s.strip()
    if s.endswith("Z"): s = s[:-1]
    return dt.datetime.fromisoformat(s)

for label, path in RUNS:
    ct = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["entity_id"] == "sensor.alfred_cleaning_time":
                ct.append((parse_ts(r["last_changed"]), float(r["state"])))
    ct.sort()
    print(f"\n=== {label} cleaning_time cadence ===")
    print(f"{'time':<10}{'value':>6}{'dval':>6}{'dwall(s)':>9}{'s per +30':>11}  note")
    prev = None
    for t, v in ct:
        if prev:
            pt, pv = prev
            dval = v - pv
            dwall = (t - pt).total_seconds()
            if dval == 0:
                prev = (t, v); continue
            if dval < 0:
                note = "RESET (job start)"
                rate = float("nan")
            else:
                rate = dwall / (dval / 30.0)   # wall-clock seconds per 30 of cleaning_time
                note = "cleaning" if rate < 45 else "GAP (transit / wash / pause)"
            print(f"{t.strftime('%H:%M:%S'):<10}{v:>6.0f}{dval:>6.0f}{dwall:>9.0f}{rate:>11.0f}  {note}")
        prev = (t, v)
