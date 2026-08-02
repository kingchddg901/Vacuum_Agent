# CARD-3 — plain-language rewrites for the 96 jargon fault strings

**DRAFT. Owner-reviewed 2026-08-02; nothing has landed in the vocabulary.**

Source: robovac_mqtt `const.EUFY_CLEAN_ERROR_CODES` — 199 codes, of which **103 are
already plain language** ("Wheel Stuck", "Mop Cloth Dislodged", "Station No Dust Bag
Installed") and translate as-is. These 96 carry engineer-speak and are rewritten first,
because translating "Overcurrent" literally just ships a cryptic string in 17 languages
instead of one.

CARD-3 renders the raw code alongside the label, so the precise electrical term stays
available to anyone who needs it.

## Rules

| Eufy | becomes | note |
|---|---|---|
| `X ABNORMAL` | *X fault* | 异常 → "abnormal" is a CN→EN artifact; it means fault |
| `X OPEN CIRCUIT` / station `X OPEN` | *X is not responding* | |
| `X SHORT CIRCUIT` / station `X SHORT` | *X electrical fault* | |
| `X RPM ABNORMAL` | *X not spinning correctly — check for a blockage* | |
| `HOST` / `MACHINE` / `ROBOVAC` | *Robot* | "Host" is a CN-ism for the main unit |
| `STATION` | *Base station* | matches the card's own `nav.tab_base_station` |

### Open vs short stay DISTINCT (owner ruling)

They are genuinely different faults. The user action is the same — contact support — but
the displayed diagnosis can still differ, and collapsing them would save translation
effort at the cost of diagnostic truth. Deliberately *"is not responding"* rather than
anything implying a broken external connection the homeowner could go and inspect.

### `X OVERCURRENT` is COMPONENT-AWARE, not a global substitution (owner ruling)

| component family | wording |
|---|---|
| mechanical motor (wheel, brush, cutter) | *X jammed — check for tangled hair or debris* |
| pump or fluid path | *X may be blocked* |
| any other electrical load (board, heater, fan) | *X is drawing too much current* |

**All 9 overcurrent codes in this catalog are wheels and brushes**, so today every one
takes the first row — verified, not assumed. The other two rows exist so a future code
cannot be blind-substituted into "hair tangle" when it is an internal hardware fault.

### The action frame belongs to the CARD, not to 96 labels

A hardware fault gets one general frame — *"Restart the base station. If the fault
returns, contact support."* — rendered once by CARD-3. An action is embedded in a label
ONLY where it is uniquely appropriate and the user can genuinely act: a jammed brush, a
blocked duct, a smeared sensor, a trapped robot. It is deliberately absent from every
"electrical fault" label, because there is no chore to do.

### `6013` stays technical (owner ruling)

*"Base station clean-water pump electrical fault"* — specific enough to name the failed
subsystem, invents no home repair, and distinguishes it from clean-water tank empty, tank
missing, pump blocked, and water-path obstruction, all of which are separate codes.

## The 96

| code | Eufy's string | proposed |
|---|---|---|
| 5 | Host Trapped Clear Obst | Robot is trapped — clear the obstacles around it |
| 26 | Power Appoint Start Fail | Scheduled clean could not start |
| 41 | Airdryer Heater Abnormal | Base station mop dryer heater fault |
| 76 | Camera Abnormal | Camera fault |
| 77 | 3D Tof Abnormal | Depth sensor fault |
| 78 | Ultrasonic Abnormal | Ultrasonic sensor fault |
| 101 | Battery Abnormal | Battery fault |
| 102 | Wheel Module Abnormal | Wheel module fault |
| 103 | Side Brush Abnormal | Side brush fault |
| 104 | Fan Abnormal | Suction fan fault |
| 105 | Roller Brush Motor Abnormal | Roller brush motor fault |
| 106 | Host Pump Abnormal | Robot water pump fault |
| 107 | Laser Sensor Abnormal | Laser distance sensor fault |
| 111 | Rotation Motor Abnormal | Mop rotation motor fault |
| 112 | Lift Motor Abnormal | Mop lift motor fault |
| 113 | Water Spray Abnormal | Water spray fault |
| 114 | Water Pump Abnormal | Water pump fault |
| 117 | Ultrasonic Abnormal | Ultrasonic sensor fault |
| 119 | Wifi Bluetooth Abnormal | Wi-Fi or Bluetooth fault |
| 1010 | Left Wheel Open Circuit | Left wheel motor not responding |
| 1011 | Left Wheel Short Circuit | Left wheel motor electrical fault |
| 1012 | Left Wheel Abnormal | Left wheel fault |
| 1013 | Left Wheel Overcurrent | Left wheel jammed — check for tangled hair or debris |
| 1020 | Right Wheel Open Circuit | Right wheel motor not responding |
| 1021 | Right Wheel Short Circuit | Right wheel motor electrical fault |
| 1022 | Right Wheel Abnormal | Right wheel fault |
| 1023 | Right Wheel Overcurrent | Right wheel jammed — check for tangled hair or debris |
| 1030 | Both Wheels Open Circuit | Both wheel motors not responding |
| 1031 | Both Wheels Short Circuit | Both wheel motors electrical fault |
| 1032 | Both Wheels Abnormal | Both wheels fault |
| 1033 | Both Wheels Overcurrent | Both wheels jammed — check for tangled hair or debris |
| 2010 | Fan Open Circuit | Suction fan not responding |
| 2011 | Fan Short Circuit | Suction fan electrical fault |
| 2012 | Fan Abnormal | Suction fan fault |
| 2013 | Fan Rpm Abnormal | Suction fan not spinning correctly — check for a blockage |
| 2020 | Left Fan Open Circuit | Left suction fan not responding |
| 2021 | Left Fan Short Circuit | Left suction fan electrical fault |
| 2022 | Left Fan Abnormal | Left suction fan fault |
| 2023 | Left Fan Rpm Abnormal | Left suction fan not spinning correctly — check for a blockage |
| 2024 | Right Fan Open Circuit | Right suction fan not responding |
| 2025 | Right Fan Short Circuit | Right suction fan electrical fault |
| 2026 | Right Fan Abnormal | Right suction fan fault |
| 2027 | Right Fan Rpm Abnormal | Right suction fan not spinning correctly — check for a blockage |
| 2110 | Roller Brush Open Circuit | Roller brush motor not responding |
| 2111 | Roller Brush Short Circuit | Roller brush motor electrical fault |
| 2112 | Roller Brush Overcurrent | Roller brush jammed — check for tangled hair |
| 2113 | Roller Brush Abnormal | Roller brush fault |
| 2120 | Front Roller Brush Open Circuit | Front roller brush motor not responding |
| 2121 | Front Roller Brush Short Circuit | Front roller brush motor electrical fault |
| 2122 | Front Roller Brush Overcurrent | Front roller brush jammed — check for tangled hair |
| 2123 | Rear Roller Brush Open Circuit | Rear roller brush motor not responding |
| 2124 | Rear Roller Brush Short Circuit | Rear roller brush motor electrical fault |
| 2125 | Rear Roller Brush Overcurrent | Rear roller brush jammed — check for tangled hair |
| 2210 | Side Brush Open Circuit | Side brush motor not responding |
| 2211 | Side Brush Short Circuit | Side brush motor electrical fault |
| 2212 | Side Brush Abnormal | Side brush fault |
| 2213 | Side Brush Overcurrent | Side brush jammed — check for tangled hair |
| 2220 | Left Side Brush Open Circuit | Left side brush motor not responding |
| 2221 | Left Side Brush Short Circuit | Left side brush motor electrical fault |
| 2222 | Left Side Brush Abnormal | Left side brush fault |
| 2223 | Left Side Brush Overcurrent | Left side brush jammed — check for tangled hair |
| 2224 | Right Side Brush Open Circuit | Right side brush motor not responding |
| 2225 | Right Side Brush Short Circuit | Right side brush motor electrical fault |
| 2226 | Right Side Brush Abnormal | Right side brush fault |
| 2227 | Right Side Brush Overcurrent | Right side brush jammed — check for tangled hair |
| 3010 | Water Pump Open Circuit | Water pump not responding |
| 3011 | Water Pump Short Circuit | Water pump electrical fault |
| 3012 | Water Pump Abnormal | Water pump fault |
| 3120 | Rotation Motor Open Circuit | Mop rotation motor not responding |
| 3121 | Rotation Motor Short Circuit | Mop rotation motor electrical fault |
| 3122 | Rotation Motor Abnormal | Mop rotation motor fault |
| 3130 | Lift Motor Open Circuit | Mop lift motor not responding |
| 3131 | Lift Motor Short Circuit | Mop lift motor electrical fault |
| 3132 | Lift Motor Abnormal | Mop lift motor fault |
| 4012 | Radar Rpm Abnormal | Lidar not spinning correctly — check for a blockage |
| 4020 | Gyroscope Abnormal | Gyroscope fault |
| 4030 | Tof Sensor Error | Depth sensor error |
| 4031 | Tof Sensor Blocked | Depth sensor blocked — wipe it clean |
| 5010 | Battery Open Circuit | Battery not responding |
| 5011 | Battery Short Circuit | Battery electrical fault |
| 5017 | Charging Voltage Abnormal | Charging voltage fault |
| 5018 | Battery Temp Abnormal | Battery temperature out of range |
| 5112 | Ir Communication Error | Infrared link to the base station failed |
| 6012 | Station Clean Water Pump Open | Base station clean-water pump not responding |
| 6013 | Station Clean Water Pump Short | Base station clean-water pump electrical fault |
| 6014 | Station Valve Short | Base station water valve electrical fault |
| 6022 | Station Dirty Pump Open | Base station dirty-water pump not responding |
| 6023 | Station Dirty Pump Short | Base station dirty-water pump electrical fault |
| 6040 | Station Dryer Open | Base station mop dryer not responding |
| 6041 | Station Dryer Short | Base station mop dryer electrical fault |
| 6042 | Station Heater Open | Base station heater not responding |
| 6043 | Station Ntc Open | Base station temperature sensor not responding |
| 6110 | Station Voltage Error | Base station power fault |
| 6112 | Station Dust Ap Duct Blocked | Base station dust duct blocked — clear it |
| 6115 | Station Barometer Error | Base station pressure sensor fault |
| 7037 | Docking Failed (Ir Reflection) | Could not dock — something reflective is confusing the dock sensor |
