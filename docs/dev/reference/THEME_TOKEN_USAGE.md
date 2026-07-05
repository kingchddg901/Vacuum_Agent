<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Source of truth: src/theme-tokens/ (the editor registry) + the card CSS.
     Regenerate after any token add/remove/rename:  node scripts/gen-theme-token-docs.mjs -->

# Theme Token CSS-Usage Trace

> Generated reference — part of the [Theme System](../20-theme-system.md) docs. Companion: [Theme Token Map](THEME_TOKEN_MAP.md).

For each catalog token (`--evcc-*`): its **default** declaration, every real **consumer** `var()` (CSS property + file:line), and JS `setProperty` apply sites. Multiline-aware (handles `var(` wrapped across lines); scans `src/`, the `animal-svg/` module, and the Python preloaded themes. The self-referential seed (`--evcc-x: var(--evcc-x, fallback)`) is the default, not a use.

- Catalog **405** · consumer `var()` uses **2123** · with a consumer **271**, with none **134**
- `var()` → non-catalog tokens **11** · dynamic `var(--evcc-…${…})` sites **3**

---

## App Shell & Typography  ·  7/7 consumed

**`--evcc-accent`** — Accent · default src/styles/foundation.js:158, src/styles/index.js:306
- src/cards/dashboard-card.js:980 (--accent)
- src/cards/_shared.js:201 (color)
- src/room-card.js:370 (--accent)
- src/styles/external-jobs.js:32
- src/styles/external-jobs.js:33
- src/styles/external-jobs.js:34 (color)
- src/styles/external-jobs.js:57
- src/styles/external-jobs.js:58
- src/styles/external-jobs.js:59 (color)
- src/styles/external-jobs.js:113 (color)
- src/styles/external-jobs.js:114
- src/styles/external-jobs.js:124 (color)
- src/styles/external-jobs.js:125
- src/styles/external-jobs.js:134 (color)
- src/styles/external-jobs.js:135
- src/styles/external-jobs.js:145 (color)
- src/styles/foundation.js:88
- src/styles/foundation.js:89
- src/styles/foundation.js:91
- src/styles/foundation.js:193 (--evcc-color-docked)
- src/styles/foundation.js:320
- src/styles/foundation.js:321 (color)
- src/styles/index.js:192 (--evcc-modal-accent)
- src/styles/index.js:193 (--evcc-modal-accent-text)
- src/styles/index.js:194
- src/styles/index.js:195
- src/styles/index.js:308
- src/styles/index.js:492 (border-color)
- src/styles/index.js:524
- src/styles/index.js:529
- src/styles/index.js:534
- src/styles/index.js:866
- src/styles/index.js:867
- src/styles/index.js:873 (background)
- src/styles/index.js:937
- src/styles/learning.js:154
- src/styles/learning.js:157
- src/styles/learning.js:178
- src/styles/learning.js:183
- src/styles/learning.js:188
- src/styles/learning.js:195
- src/styles/learning.js:198
- src/styles/learning.js:201
- src/styles/learning.js:207
- src/styles/learning.js:323
- src/styles/learning.js:324
- src/styles/learning.js:325 (color)
- src/styles/learning.js:451
- src/styles/learning.js:457
- src/styles/maintenance.js:276
- src/styles/map.js:257 (background)
- src/styles/map.js:258 (border-color)
- src/styles/map.js:282
- src/styles/map.js:292
- src/styles/map.js:328
- src/styles/map.js:342 (background)
- src/styles/map.js:354
- src/styles/map.js:377 (background)
- src/styles/map.js:379 (border-color)
- src/styles/map.js:419 (background)
- src/styles/map.js:420 (border-color)
- src/styles/map.js:525 (background)
- src/styles/map.js:679 (background)
- src/styles/map.js:863 (background)
- src/styles/map.js:1017 (background)
- src/styles/map.js:1205 (color)
- src/styles/map.js:1234 (border-color)
- src/styles/map.js:1239 (border-color)
- src/styles/map.js:1267
- src/styles/map.js:1391
- src/styles/map.js:1393 (color)
- src/styles/map.js:1395
- src/styles/map.js:1401
- src/styles/map.js:1402 (color)
- src/styles/map.js:1578
- src/styles/map.js:1579 (color)
- src/styles/map.js:1581
- src/styles/map.js:1695 (accent-color)
- src/styles/mapping-review.js:267
- src/styles/mapping-review.js:268 (color)
- src/styles/mapping-review.js:269
- src/styles/mapping-review.js:273
- src/styles/metrics.js:164 (border-color)
- src/styles/mobile.js:170 (color)
- src/styles/mobile.js:270 (color)
- src/styles/mobile.js:272
- src/styles/modals.js:196
- src/styles/modals.js:201
- src/styles/modals.js:206
- src/styles/modals.js:214
- src/styles/modals.js:219
- src/styles/modals.js:223
- src/styles/modals.js:338
- src/styles/modals.js:339
- src/styles/order.js:138
- src/styles/order.js:149
- src/styles/order.js:155
- src/styles/order.js:161
- src/styles/order.js:174
- src/styles/room-rules.js:73
- src/styles/room-rules.js:74 (color)
- src/styles/room-rules.js:155
- src/styles/room-rules.js:156 (color)
- src/styles/room-rules.js:157
- src/styles/room-rules.js:201 (color)
- src/styles/room-rules.js:305
- src/styles/room-rules.js:306
- src/styles/room-rules.js:345 (border-color)
- src/styles/rooms.js:332
- src/styles/rooms.js:336
- src/styles/rooms.js:340
- src/styles/rooms.js:350
- src/styles/rooms.js:355
- src/styles/rooms.js:395
- src/styles/rooms.js:592
- src/styles/rooms.js:593 (--evcc-chip-text)
- src/styles/rooms.js:594
- src/styles/rooms.js:643
- src/styles/rooms.js:742
- src/styles/rooms.js:744
- src/styles/rooms.js:869
- src/styles/rooms.js:870
- src/styles/rooms.js:943
- src/styles/rooms.js:965
- src/styles/rooms.js:984
- src/styles/rooms.js:985
- src/styles/rooms.js:1073
- src/styles/rooms.js:1108
- src/styles/rooms.js:1109
- src/styles/saved-zones.js:26
- src/styles/saved-zones.js:59 (background)
- src/styles/saved-zones.js:132 (border-color)
- src/styles/saved-zones.js:133
- src/styles/saved-zones.js:154 (accent-color)
- src/styles/saved-zones.js:213
- src/styles/saved-zones.js:214
- src/styles/setup.js:56 (background)
- src/styles/setup.js:103 (background)
- src/styles/setup.js:153
- src/styles/setup.js:154
- src/styles/setup.js:155 (color)
- src/styles/setup.js:411
- src/styles/setup.js:412 (border-color)
- src/styles/setup.js:413 (color)
- src/styles/setup.js:648 (border-color)
- src/styles/shell.js:117
- src/styles/shell.js:120
- src/styles/shell.js:258
- src/styles/shell.js:263 (color)
- src/styles/shell.js:271 (color)
- src/styles/shell.js:331
- src/styles/shell.js:332 (color)
- src/styles/shell.js:428
- src/styles/theme-preview.js:105
- src/styles/theme-preview.js:154 (color)
- src/styles/theme-preview.js:164
- src/styles/theme-preview.js:165
- src/styles/theme-preview.js:272
- src/styles/theme-preview.js:282
- src/styles/theme-preview.js:482
- src/styles/theme-preview.js:530
- src/styles/theme-preview.js:531
- src/styles/theme-preview.js:532
- src/styles/theme.js:54 (border-color)
- src/styles/theme.js:136
- src/styles/theme.js:137
- src/styles/theme.js:238 (color)
- src/styles/theme.js:248 (border-color)
- src/styles/theme.js:249
- src/styles/theme.js:313 (border-color)
- src/styles/theme.js:316
- src/styles/theme.js:349 (background)
- src/styles/theme.js:399 (color)
- src/styles/theme.js:400
- src/styles/theme.js:401
- src/styles/theme.js:421 (color)
- src/styles/theme.js:426 (border-color)
- src/styles/theme.js:492 (border-color)
- src/styles/theme.js:502 (color)
- src/styles/theme.js:510
- src/styles/theme.js:625 (border-color)
- src/styles/theme.js:658 (border-color)
- src/styles/theme.js:661
- src/styles/theme.js:769
- src/styles/theme.js:956
- src/styles/theme.js:979
- src/styles/theme.js:1041
- src/styles/theme.js:1064
- src/styles/theme.js:1087 (border-color)
- custom_components/eufy_vacuum/themes/preloaded.py:81
- custom_components/eufy_vacuum/themes/preloaded.py:82
- custom_components/eufy_vacuum/themes/preloaded.py:83
- custom_components/eufy_vacuum/themes/preloaded.py:105
- custom_components/eufy_vacuum/themes/preloaded.py:106
- custom_components/eufy_vacuum/themes/preloaded.py:107
- custom_components/eufy_vacuum/themes/preloaded.py:112
- custom_components/eufy_vacuum/themes/preloaded.py:113
- custom_components/eufy_vacuum/themes/preloaded.py:114
- custom_components/eufy_vacuum/themes/preloaded.py:115
- custom_components/eufy_vacuum/themes/preloaded.py:116
- custom_components/eufy_vacuum/themes/preloaded.py:117
- custom_components/eufy_vacuum/themes/preloaded.py:124
- custom_components/eufy_vacuum/themes/preloaded.py:125
- custom_components/eufy_vacuum/themes/preloaded.py:126
- custom_components/eufy_vacuum/themes/preloaded.py:143
- custom_components/eufy_vacuum/themes/preloaded.py:162
- custom_components/eufy_vacuum/themes/preloaded.py:164
- custom_components/eufy_vacuum/themes/preloaded.py:174
- custom_components/eufy_vacuum/themes/preloaded.py:175
- custom_components/eufy_vacuum/themes/preloaded.py:176
- custom_components/eufy_vacuum/themes/preloaded.py:190
- custom_components/eufy_vacuum/themes/preloaded.py:191
- custom_components/eufy_vacuum/themes/preloaded.py:196
- custom_components/eufy_vacuum/themes/preloaded.py:197
- custom_components/eufy_vacuum/themes/preloaded.py:198
- custom_components/eufy_vacuum/themes/preloaded.py:199
- custom_components/eufy_vacuum/themes/preloaded.py:504

**`--evcc-accent-soft`** — Accent Soft · default src/styles/foundation.js:159
- src/styles/map.js:1238 (background)
- src/styles/map.js:1266 (fill)
- src/styles/map.js:1274 (fill)

**`--evcc-text-muted`** — Text Muted · default src/styles/foundation.js:147, src/styles/index.js:302, src/styles/index.js:735
- src/cards/dashboard-card.js:984 (--text-muted)
- src/cards/vacuum-map-host.js:37 (color)
- src/cards/_shared.js:194 (color)
- src/cards/_shared.js:198 (color)
- src/room-card.js:374 (--text-muted)
- src/styles/base-station.js:88 (color)
- src/styles/index.js:189 (--evcc-modal-text-muted)
- src/styles/index.js:512
- src/styles/index.js:542
- src/styles/index.js:608
- src/styles/index.js:679 (--evcc-modal-text-muted)
- src/styles/index.js:862 (color)
- src/styles/index.js:945 (color)
- src/styles/learning.js:54 (--evcc-learning-text-muted)
- src/styles/learning.js:120
- src/styles/learning.js:121
- src/styles/learning.js:652 (color)
- src/styles/learning.js:695 (color)
- src/styles/maintenance.js:217 (color)
- src/styles/maintenance.js:366 (color)
- src/styles/maintenance.js:420 (color)
- src/styles/map.js:29 (color)
- src/styles/map.js:962 (color)
- src/styles/map.js:1043 (color)
- src/styles/map.js:1163 (color)
- src/styles/map.js:1174 (color)
- src/styles/map.js:1334 (color)
- src/styles/map.js:1351 (color)
- src/styles/map.js:1364 (color)
- src/styles/map.js:1497 (color)
- src/styles/map.js:1504 (color)
- src/styles/map.js:1525 (color)
- src/styles/map.js:1564 (color)
- src/styles/mapping-review.js:104
- src/styles/mapping-review.js:105 (color)
- src/styles/mapping-review.js:212 (color)
- src/styles/mapping-review.js:240 (color)
- src/styles/metrics.js:196 (color)
- src/styles/metrics.js:212 (color)
- src/styles/metrics.js:232 (color)
- src/styles/metrics.js:243 (color)
- src/styles/modals.js:241
- src/styles/modals.js:310
- src/styles/modals.js:320
- src/styles/modals.js:321
- src/styles/modals.js:322 (color)
- src/styles/modals.js:344
- src/styles/modals.js:345
- src/styles/modals.js:346 (color)
- src/styles/modals.js:352 (color)
- src/styles/modals.js:360
- src/styles/review.js:225 (color)
- src/styles/room-access.js:83 (color)
- src/styles/room-rules.js:100 (color)
- src/styles/room-rules.js:179 (color)
- src/styles/room-rules.js:193 (color)
- src/styles/room-rules.js:213 (color)
- src/styles/room-rules.js:269 (color)
- src/styles/room-rules.js:318 (color)
- src/styles/room-rules.js:328 (color)
- src/styles/room-rules.js:361 (color)
- src/styles/room-rules.js:389 (color)
- src/styles/rooms.js:75 (color)
- src/styles/rooms.js:163
- src/styles/rooms.js:164
- src/styles/rooms.js:165 (color)
- src/styles/rooms.js:220 (color)
- src/styles/rooms.js:249 (color)
- src/styles/rooms.js:435 (color)
- src/styles/rooms.js:586
- src/styles/rooms.js:731 (color)
- src/styles/rooms.js:749
- src/styles/rooms.js:756 (--evcc-learning-note-text)
- src/styles/rooms.js:785 (color)
- src/styles/rooms.js:1114
- src/styles/rooms.js:1115
- src/styles/rooms.js:1153
- src/styles/rooms.js:1154
- src/styles/rooms.js:1161 (color)
- src/styles/rooms.js:1175 (color)
- src/styles/rooms.js:1176
- src/styles/run-profiles.js:75 (color)
- src/styles/saved-zones.js:64 (color)
- src/styles/saved-zones.js:86 (color)
- src/styles/saved-zones.js:116 (color)
- src/styles/saved-zones.js:168 (color)
- src/styles/setup.js:90 (color)
- src/styles/setup.js:186 (color)
- src/styles/setup.js:204 (color)
- src/styles/setup.js:315 (color)
- src/styles/setup.js:372 (color)
- src/styles/setup.js:566
- src/styles/setup.js:578 (color)
- src/styles/shell.js:99 (color)
- src/styles/shell.js:112
- src/styles/shell.js:122
- src/styles/shell.js:123
- src/styles/shell.js:127 (color)
- src/styles/shell.js:236 (color)
- src/styles/shell.js:291 (color)
- src/styles/shell.js:367 (color)
- src/styles/shell.js:439 (color)
- src/styles/theme-preview.js:51 (color)
- src/styles/theme-preview.js:117 (color)
- src/styles/theme-preview.js:149 (color)
- src/styles/theme-preview.js:196 (color)
- src/styles/theme-preview.js:609 (color)
- src/styles/theme-preview.js:632 (color)
- src/styles/theme.js:60 (color)
- src/styles/theme.js:77 (color)
- src/styles/theme.js:126 (color)
- src/styles/theme.js:149 (color)
- src/styles/theme.js:273 (color)
- src/styles/theme.js:327 (color)
- src/styles/theme.js:412 (color)
- src/styles/theme.js:461 (color)
- src/styles/theme.js:601 (color)
- src/styles/theme.js:707 (color)
- src/styles/theme.js:1120 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:167
- custom_components/eufy_vacuum/themes/preloaded.py:170
- custom_components/eufy_vacuum/themes/preloaded.py:192
- custom_components/eufy_vacuum/themes/preloaded.py:221

**`--evcc-text-on-accent`** — Text On Accent · default src/styles/foundation.js:149
- src/styles/index.js:874 (color)
- src/styles/map.js:1429 (color)

**`--evcc-text-primary`** — Text Primary · default src/styles/foundation.js:145, src/styles/index.js:294, src/styles/index.js:727
- src/cards/dashboard-card.js:983 (--text-primary)
- src/cards/_shared.js:195 (color)
- src/cards/_shared.js:199 (color)
- src/room-card.js:373 (--text-primary)
- src/styles/base-station.js:40 (color)
- src/styles/base-station.js:75 (color)
- src/styles/external-jobs.js:23 (color)
- src/styles/external-jobs.js:71 (color)
- src/styles/external-jobs.js:87 (color)
- src/styles/external-jobs.js:144 (color)
- src/styles/external-jobs.js:150 (color)
- src/styles/external-jobs.js:160 (color)
- src/styles/foundation.js:82
- src/styles/foundation.js:114 (color)
- src/styles/foundation.js:210 (--evcc-chip-hover-text)
- src/styles/foundation.js:253 (color)
- src/styles/foundation.js:316 (color)
- src/styles/index.js:187 (--evcc-modal-text-primary)
- src/styles/index.js:203 (--evcc-modal-chip-hover-text)
- src/styles/index.js:235
- src/styles/index.js:263
- src/styles/index.js:407
- src/styles/index.js:443
- src/styles/index.js:481 (color)
- src/styles/index.js:677 (--evcc-modal-text-primary)
- src/styles/index.js:686 (--evcc-modal-chip-hover-text)
- src/styles/index.js:868 (color)
- src/styles/index.js:927 (color)
- src/styles/index.js:952 (color)
- src/styles/learning.js:48 (--evcc-learning-text-primary)
- src/styles/learning.js:594 (color)
- src/styles/learning.js:630 (color)
- src/styles/learning.js:665 (color)
- src/styles/maintenance.js:58 (color)
- src/styles/maintenance.js:104 (color)
- src/styles/maintenance.js:110 (color)
- src/styles/maintenance.js:183 (color)
- src/styles/maintenance.js:209 (color)
- src/styles/maintenance.js:320 (color)
- src/styles/maintenance.js:333 (color)
- src/styles/maintenance.js:393 (color)
- src/styles/map.js:50 (color)
- src/styles/map.js:1035 (color)
- src/styles/map.js:1107 (color)
- src/styles/map.js:1113 (color)
- src/styles/map.js:1216 (color)
- src/styles/map.js:1240 (color)
- src/styles/map.js:1329 (color)
- src/styles/map.js:1386 (color)
- src/styles/map.js:1625 (color)
- src/styles/map.js:1678 (color)
- src/styles/map.js:1683 (color)
- src/styles/mapping-review.js:43 (color)
- src/styles/mapping-review.js:152 (color)
- src/styles/mapping-review.js:206 (color)
- src/styles/metrics.js:40 (color)
- src/styles/metrics.js:75 (color)
- src/styles/metrics.js:81 (color)
- src/styles/metrics.js:156 (color)
- src/styles/metrics.js:257 (color)
- src/styles/mobile.js:90 (color)
- src/styles/mobile.js:112 (color)
- src/styles/mobile.js:258 (color)
- src/styles/modals.js:118
- src/styles/modals.js:145
- src/styles/modals.js:340 (color)
- src/styles/order.js:100
- src/styles/review.js:40 (color)
- src/styles/review.js:133 (color)
- src/styles/review.js:206 (color)
- src/styles/room-estimate.js:45
- src/styles/room-rules.js:53 (color)
- src/styles/room-rules.js:58 (color)
- src/styles/room-rules.js:171 (color)
- src/styles/room-rules.js:250 (color)
- src/styles/room-rules.js:312 (color)
- src/styles/room-rules.js:337 (color)
- src/styles/rooms.js:70 (color)
- src/styles/rooms.js:85
- src/styles/rooms.js:139 (color)
- src/styles/rooms.js:152 (color)
- src/styles/rooms.js:198 (color)
- src/styles/rooms.js:239 (color)
- src/styles/rooms.js:406 (color)
- src/styles/rooms.js:462
- src/styles/rooms.js:679
- src/styles/rooms.js:686
- src/styles/rooms.js:746 (--evcc-estimate-learned-text)
- src/styles/rooms.js:871 (color)
- src/styles/rooms.js:1110 (--evcc-chip-text)
- src/styles/run-profiles.js:37 (color)
- src/styles/run-profiles.js:61 (color)
- src/styles/run-profiles.js:85 (color)
- src/styles/saved-zones.js:42 (color)
- src/styles/saved-zones.js:161 (color)
- src/styles/saved-zones.js:185 (color)
- src/styles/setup.js:23 (color)
- src/styles/setup.js:74 (color)
- src/styles/setup.js:181 (color)
- src/styles/setup.js:222 (color)
- src/styles/setup.js:276 (color)
- src/styles/setup.js:383 (color)
- src/styles/setup.js:485 (color)
- src/styles/setup.js:505 (color)
- src/styles/setup.js:516 (color)
- src/styles/setup.js:573 (color)
- src/styles/setup.js:601 (color)
- src/styles/setup.js:626 (color)
- src/styles/setup.js:642 (color)
- src/styles/setup.js:674 (color)
- src/styles/setup.js:704 (color)
- src/styles/shell.js:80 (color)
- src/styles/shell.js:185 (color)
- src/styles/shell.js:190 (color)
- src/styles/shell.js:259 (color)
- src/styles/shell.js:327 (color)
- src/styles/shell.js:411 (color)
- src/styles/shell.js:447 (color)
- src/styles/theme-preview.js:57 (color)
- src/styles/theme-preview.js:124 (color)
- src/styles/theme-preview.js:131 (color)
- src/styles/theme-preview.js:207 (color)
- src/styles/theme-preview.js:299 (color)
- src/styles/theme-preview.js:305
- src/styles/theme-preview.js:335
- src/styles/theme-preview.js:352
- src/styles/theme-preview.js:600 (color)
- src/styles/theme.js:69 (color)
- src/styles/theme.js:145 (color)
- src/styles/theme.js:364 (color)
- src/styles/theme.js:487 (color)
- src/styles/theme.js:589 (color)
- src/styles/theme.js:618 (color)
- src/styles/theme.js:676 (color)
- src/styles/theme.js:857 (color)
- src/styles/theme.js:1079 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:91
- custom_components/eufy_vacuum/themes/preloaded.py:129
- custom_components/eufy_vacuum/themes/preloaded.py:193
- custom_components/eufy_vacuum/themes/preloaded.py:213
- custom_components/eufy_vacuum/themes/preloaded.py:222

**`--evcc-text-secondary`** — Text Secondary · default src/styles/foundation.js:146, src/styles/index.js:298, src/styles/index.js:731
- src/styles/base-station.js:46 (color)
- src/styles/base-station.js:82 (color)
- src/styles/external-jobs.js:50 (color)
- src/styles/external-jobs.js:62 (color)
- src/styles/external-jobs.js:72 (color)
- src/styles/external-jobs.js:104 (color)
- src/styles/external-jobs.js:105 (color)
- src/styles/external-jobs.js:109 (color)
- src/styles/external-jobs.js:120 (color)
- src/styles/external-jobs.js:130 (color)
- src/styles/external-jobs.js:146 (color)
- src/styles/external-jobs.js:147 (color)
- src/styles/foundation.js:47
- src/styles/foundation.js:195 (--evcc-color-idle)
- src/styles/foundation.js:207 (--evcc-chip-text)
- src/styles/foundation.js:282 (color)
- src/styles/foundation.js:298 (color)
- src/styles/foundation.js:310 (color)
- src/styles/index.js:188 (--evcc-modal-text-secondary)
- src/styles/index.js:200 (--evcc-modal-chip-text)
- src/styles/index.js:393
- src/styles/index.js:472 (color)
- src/styles/index.js:547
- src/styles/index.js:595
- src/styles/index.js:678 (--evcc-modal-text-secondary)
- src/styles/index.js:683 (--evcc-modal-chip-text)
- src/styles/index.js:848 (color)
- src/styles/learning.js:51 (--evcc-learning-text-secondary)
- src/styles/learning.js:115 (--evcc-learning-confidence-neutral-text)
- src/styles/learning.js:614 (color)
- src/styles/maintenance.js:52 (color)
- src/styles/maintenance.js:63 (color)
- src/styles/maintenance.js:90 (color)
- src/styles/maintenance.js:169
- src/styles/maintenance.js:177 (color)
- src/styles/maintenance.js:189 (color)
- src/styles/maintenance.js:327 (color)
- src/styles/maintenance.js:339 (color)
- src/styles/maintenance.js:351 (color)
- src/styles/maintenance.js:359 (color)
- src/styles/maintenance.js:398 (color)
- src/styles/maintenance.js:406 (color)
- src/styles/maintenance.js:412 (color)
- src/styles/map.js:42 (color)
- src/styles/map.js:955 (color)
- src/styles/map.js:1097 (color)
- src/styles/map.js:1180 (color)
- src/styles/map.js:1200 (color)
- src/styles/map.js:1226 (color)
- src/styles/map.js:1374 (color)
- src/styles/map.js:1478 (color)
- src/styles/map.js:1532 (color)
- src/styles/map.js:1573 (color)
- src/styles/map.js:1615 (color)
- src/styles/map.js:1666 (color)
- src/styles/mapping-review.js:13 (color)
- src/styles/mapping-review.js:55 (color)
- src/styles/mapping-review.js:111 (color)
- src/styles/mapping-review.js:145 (color)
- src/styles/mapping-review.js:157 (color)
- src/styles/mapping-review.js:172 (color)
- src/styles/mapping-review.js:217 (color)
- src/styles/metrics.js:47 (color)
- src/styles/metrics.js:115 (color)
- src/styles/mobile.js:102 (color)
- src/styles/mobile.js:158 (color)
- src/styles/modals.js:364
- src/styles/order.js:56
- src/styles/review.js:46 (color)
- src/styles/review.js:141 (color)
- src/styles/review.js:188 (color)
- src/styles/room-access.js:22 (color)
- src/styles/room-estimate.js:17
- src/styles/room-estimate.js:41
- src/styles/room-estimate.js:61
- src/styles/room-rules.js:42 (color)
- src/styles/room-rules.js:187 (color)
- src/styles/room-rules.js:379 (color)
- src/styles/rooms.js:206 (color)
- src/styles/rooms.js:243 (color)
- src/styles/rooms.js:456
- src/styles/rooms.js:544 (color)
- src/styles/rooms.js:587
- src/styles/rooms.js:622
- src/styles/rooms.js:644
- src/styles/rooms.js:672
- src/styles/rooms.js:693
- src/styles/rooms.js:700
- src/styles/rooms.js:753 (--evcc-estimate-default-text)
- src/styles/rooms.js:852 (color)
- src/styles/rooms.js:1116 (--evcc-chip-text)
- src/styles/run-profiles.js:43 (color)
- src/styles/run-profiles.js:94 (color)
- src/styles/run-profiles.js:110 (color)
- src/styles/saved-zones.js:49 (color)
- src/styles/saved-zones.js:96 (color)
- src/styles/saved-zones.js:219 (color)
- src/styles/setup.js:28 (color)
- src/styles/setup.js:79 (color)
- src/styles/setup.js:124 (color)
- src/styles/setup.js:405 (color)
- src/styles/setup.js:500 (color)
- src/styles/shell.js:91 (color)
- src/styles/shell.js:175 (color)
- src/styles/shell.js:249 (color)
- src/styles/shell.js:318 (color)
- src/styles/theme-preview.js:63 (color)
- src/styles/theme-preview.js:144 (color)
- src/styles/theme-preview.js:317
- src/styles/theme-preview.js:359
- src/styles/theme-preview.js:392 (color)
- src/styles/theme-preview.js:616 (color)
- src/styles/theme.js:85 (color)
- src/styles/theme.js:165 (color)
- src/styles/theme.js:385 (color)
- src/styles/theme.js:453 (color)
- src/styles/theme.js:640 (color)
- src/styles/theme.js:911 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:99
- custom_components/eufy_vacuum/themes/preloaded.py:108
- custom_components/eufy_vacuum/themes/preloaded.py:111
- custom_components/eufy_vacuum/themes/preloaded.py:120
- custom_components/eufy_vacuum/themes/preloaded.py:135
- custom_components/eufy_vacuum/themes/preloaded.py:138
- custom_components/eufy_vacuum/themes/preloaded.py:145
- custom_components/eufy_vacuum/themes/preloaded.py:166
- custom_components/eufy_vacuum/themes/preloaded.py:173
- custom_components/eufy_vacuum/themes/preloaded.py:186
- custom_components/eufy_vacuum/themes/preloaded.py:187
- custom_components/eufy_vacuum/themes/preloaded.py:194
- custom_components/eufy_vacuum/themes/preloaded.py:214
- custom_components/eufy_vacuum/themes/preloaded.py:223

**`--evcc-text-strong`** — Text Strong · default src/styles/foundation.js:148
- src/styles/learning.js:687 (color)
- src/styles/metrics.js:206 (color)

## Cards & Surfaces  ·  18/18 consumed

**`--evcc-bg-input`** — BG Input · default src/styles/foundation.js:189
- src/styles/theme-preview.js:194

**`--evcc-card-bg`** — Card BG · default src/styles/foundation.js:187
- src/styles/theme-preview.js:34
- src/styles/theme-preview.js:173
- src/styles/theme-preview.js:206
- src/styles/theme-preview.js:275

**`--evcc-card-gap`** — Card Gap · default —
- src/styles/rooms.js:316 (gap)

**`--evcc-card-min-height`** — Card Min Height · default —
- src/styles/rooms.js:317 (min-height)
- src/styles/theme-preview.js:94 (min-height)

**`--evcc-card-padding`** — Card Padding · default —
- src/styles/rooms.js:318 (padding)
- src/styles/theme-preview.js:93 (padding)
- src/styles/theme-preview.js:172 (padding)

**`--evcc-panel-bg`** — Panel BG · default src/styles/foundation.js:188
- src/styles/run-profiles.js:24
- src/styles/saved-zones.js:14
- src/styles/theme-preview.js:95
- src/styles/theme-preview.js:108
- src/styles/theme-preview.js:183
- src/styles/theme-preview.js:561

**`--evcc-surface-action`** — Surface Action · default src/styles/foundation.js:139
- src/styles/learning.js:629 (background)
- src/styles/map.js:226 (background)
- src/styles/map.js:412 (background)
- src/styles/map.js:495 (background)

**`--evcc-surface-action-hover`** — Surface Action Hover · default src/styles/foundation.js:140
- src/styles/learning.js:639 (background)
- src/styles/map.js:236 (background)
- src/styles/map.js:416 (background)
- src/styles/map.js:540 (background)

**`--evcc-surface-base`** — Surface Base · default src/styles/foundation.js:131
- src/styles/foundation.js:132 (--evcc-surface-card)
- src/styles/foundation.js:133
- src/styles/foundation.js:134
- src/styles/index.js:168 (--evcc-modal-bg)
- src/styles/index.js:662 (--evcc-modal-bg)
- src/styles/theme.js:335 (background)
- src/styles/theme.js:954 (background)
- src/styles/theme.js:957
- src/styles/theme.js:977 (background)
- src/styles/theme.js:980
- src/styles/theme.js:1039 (background)
- src/styles/theme.js:1042
- src/styles/theme.js:1062 (background)
- src/styles/theme.js:1065
- custom_components/eufy_vacuum/themes/preloaded.py:73
- custom_components/eufy_vacuum/themes/preloaded.py:201

**`--evcc-surface-card`** — Surface Card · default src/styles/foundation.js:132
- src/cards/dashboard-card.js:981 (--surface)
- src/cards/_shared.js:197 (background)
- src/room-card.js:371 (--surface)
- src/styles/foundation.js:187 (--evcc-card-bg)
- src/styles/foundation.js:251 (background)
- src/styles/rooms.js:321
- src/styles/rooms.js:337
- src/styles/rooms.js:505
- src/styles/rooms.js:512 (background-color)
- src/styles/rooms.js:525
- src/styles/rooms.js:534
- src/styles/rooms.js:535
- src/styles/rooms.js:536
- src/styles/rooms.js:554 (background-color)
- src/styles/setup.js:640 (background)
- src/styles/shell.js:47 (background)
- src/styles/theme-preview.js:34 (background)
- src/styles/theme-preview.js:173 (background)
- src/styles/theme-preview.js:206 (background)
- src/styles/theme-preview.js:275
- src/styles/theme.js:295 (background)
- src/styles/theme.js:317
- src/styles/theme.js:856 (background)
- custom_components/eufy_vacuum/themes/preloaded.py:70

**`--evcc-surface-chip`** — Surface Chip · default src/styles/foundation.js:138
- src/styles/learning.js:610 (background)
- src/styles/learning.js:664 (background)

**`--evcc-surface-input`** — Surface Input · default src/styles/foundation.js:135, src/styles/index.js:273, src/styles/index.js:710
- src/styles/external-jobs.js:22 (background)
- src/styles/external-jobs.js:100 (background)
- src/styles/external-jobs.js:149 (background)
- src/styles/foundation.js:46
- src/styles/foundation.js:189 (--evcc-bg-input)
- src/styles/foundation.js:205 (--evcc-chip-bg)
- src/styles/index.js:177 (--evcc-modal-surface-input)
- src/styles/index.js:179 (--evcc-modal-input-bg)
- src/styles/index.js:198 (--evcc-modal-chip-bg)
- src/styles/index.js:389
- src/styles/index.js:482 (background)
- src/styles/index.js:670 (--evcc-modal-surface-input)
- src/styles/index.js:672 (--evcc-modal-input-bg)
- src/styles/index.js:681 (--evcc-modal-chip-bg)
- src/styles/maintenance.js:168
- src/styles/map.js:39 (background)
- src/styles/map.js:48 (background)
- src/styles/map.js:989 (background)
- src/styles/map.js:1105 (background)
- src/styles/map.js:1215 (background)
- src/styles/map.js:1384 (background)
- src/styles/map.js:1486 (background)
- src/styles/map.js:1492 (background)
- src/styles/map.js:1572 (background)
- src/styles/map.js:1623 (background)
- src/styles/metrics.js:157 (background)
- src/styles/order.js:50
- src/styles/review.js:187 (background)
- src/styles/room-rules.js:52 (background)
- src/styles/room-rules.js:57 (background)
- src/styles/room-rules.js:119 (background)
- src/styles/room-rules.js:212 (background)
- src/styles/room-rules.js:237 (background)
- src/styles/room-rules.js:300 (background)
- src/styles/room-rules.js:336 (background)
- src/styles/room-rules.js:388 (background)
- src/styles/rooms.js:502
- src/styles/rooms.js:503
- src/styles/rooms.js:522
- src/styles/rooms.js:523
- src/styles/rooms.js:620
- src/styles/rooms.js:641
- src/styles/rooms.js:670
- src/styles/rooms.js:677
- src/styles/rooms.js:684
- src/styles/rooms.js:691
- src/styles/rooms.js:698
- src/styles/rooms.js:733
- src/styles/rooms.js:826
- src/styles/rooms.js:833
- src/styles/rooms.js:840
- src/styles/run-profiles.js:54
- src/styles/run-profiles.js:84 (background)
- src/styles/saved-zones.js:78
- src/styles/saved-zones.js:128
- src/styles/saved-zones.js:133
- src/styles/saved-zones.js:184 (background)
- src/styles/setup.js:42 (background)
- src/styles/setup.js:123 (background)
- src/styles/setup.js:174 (background)
- src/styles/setup.js:270 (background)
- src/styles/setup.js:335 (background)
- src/styles/setup.js:371 (background)
- src/styles/setup.js:404 (background)
- src/styles/setup.js:515 (background)
- src/styles/setup.js:619 (background)
- src/styles/setup.js:667 (background)
- src/styles/theme-preview.js:194 (background)
- src/styles/theme.js:45 (background)
- src/styles/theme.js:386 (background)
- src/styles/theme.js:454 (background)
- src/styles/theme.js:486 (background)
- src/styles/theme.js:615 (background)
- src/styles/theme.js:758 (background)
- src/styles/theme.js:1075 (background)
- custom_components/eufy_vacuum/themes/preloaded.py:69
- custom_components/eufy_vacuum/themes/preloaded.py:84
- custom_components/eufy_vacuum/themes/preloaded.py:103
- custom_components/eufy_vacuum/themes/preloaded.py:118
- custom_components/eufy_vacuum/themes/preloaded.py:136
- custom_components/eufy_vacuum/themes/preloaded.py:171
- custom_components/eufy_vacuum/themes/preloaded.py:209
- custom_components/eufy_vacuum/themes/preloaded.py:217
- custom_components/eufy_vacuum/themes/preloaded.py:218

**`--evcc-surface-overlay`** — Surface Overlay · default src/styles/foundation.js:136
- src/styles/index.js:169 (--evcc-modal-backdrop-bg)
- src/styles/index.js:663 (--evcc-modal-backdrop-bg)
- custom_components/eufy_vacuum/themes/preloaded.py:200

**`--evcc-surface-panel`** — Surface Panel · default src/styles/foundation.js:133, src/styles/index.js:278, src/styles/index.js:706
- src/styles/base-station.js:23 (background)
- src/styles/external-jobs.js:29 (background)
- src/styles/external-jobs.js:159 (background)
- src/styles/foundation.js:81
- src/styles/foundation.js:113 (background)
- src/styles/foundation.js:188 (--evcc-panel-bg)
- src/styles/foundation.js:209 (--evcc-chip-hover-bg)
- src/styles/index.js:176 (--evcc-modal-surface-panel)
- src/styles/index.js:183
- src/styles/index.js:184
- src/styles/index.js:201 (--evcc-modal-chip-hover-bg)
- src/styles/index.js:403
- src/styles/index.js:669 (--evcc-modal-surface-panel)
- src/styles/index.js:674
- src/styles/index.js:675
- src/styles/index.js:684 (--evcc-modal-chip-hover-bg)
- src/styles/learning.js:39 (--evcc-learning-panel-bg)
- src/styles/maintenance.js:141 (background)
- src/styles/map.js:74 (background)
- src/styles/map.js:321 (background)
- src/styles/map.js:394 (background)
- src/styles/map.js:448 (background)
- src/styles/map.js:880 (background)
- src/styles/map.js:975 (background)
- src/styles/map.js:1004 (background)
- src/styles/map.js:1682 (background)
- src/styles/mapping-review.js:31 (background)
- src/styles/metrics.js:23 (background)
- src/styles/mobile.js:72 (background)
- src/styles/mobile.js:127 (background)
- src/styles/mobile.js:234 (background)
- src/styles/order.js:99
- src/styles/review.js:23 (background)
- src/styles/review.js:105
- src/styles/review.js:214
- src/styles/room-access.js:16
- src/styles/room-estimate.js:40
- src/styles/room-estimate.js:62
- src/styles/room-rules.js:282 (background)
- src/styles/run-profiles.js:24 (background)
- src/styles/saved-zones.js:14 (background)
- src/styles/shell.js:309 (background)
- src/styles/theme-preview.js:95 (background)
- src/styles/theme-preview.js:108
- src/styles/theme-preview.js:183 (background)
- src/styles/theme-preview.js:485
- src/styles/theme-preview.js:561 (background)
- src/styles/theme.js:55 (background)
- src/styles/theme.js:355 (background)
- src/styles/theme.js:549
- src/styles/theme.js:569
- src/styles/theme.js:652 (background)
- src/styles/theme.js:662
- custom_components/eufy_vacuum/themes/preloaded.py:71
- custom_components/eufy_vacuum/themes/preloaded.py:89
- custom_components/eufy_vacuum/themes/preloaded.py:109
- custom_components/eufy_vacuum/themes/preloaded.py:127
- custom_components/eufy_vacuum/themes/preloaded.py:188
- custom_components/eufy_vacuum/themes/preloaded.py:211
- custom_components/eufy_vacuum/themes/preloaded.py:215
- custom_components/eufy_vacuum/themes/preloaded.py:216
- custom_components/eufy_vacuum/themes/preloaded.py:219
- custom_components/eufy_vacuum/themes/preloaded.py:427

**`--evcc-surface-raised`** — Surface Raised · default src/styles/foundation.js:134
- src/styles/base-station.js:67 (background)
- src/styles/base-station.js:107
- src/styles/external-jobs.js:67 (background)
- src/styles/foundation.js:297 (background)
- src/styles/foundation.js:315 (background)
- src/styles/index.js:178 (--evcc-modal-surface-section)
- src/styles/index.js:671 (--evcc-modal-surface-section)
- src/styles/index.js:926 (background)
- src/styles/maintenance.js:25
- src/styles/maintenance.js:29
- src/styles/maintenance.js:34
- src/styles/maintenance.js:38
- src/styles/maintenance.js:98 (background)
- src/styles/maintenance.js:103
- src/styles/maintenance.js:109
- src/styles/maintenance.js:203 (background)
- src/styles/maintenance.js:265
- src/styles/maintenance.js:377 (background)
- src/styles/map.js:372 (background)
- src/styles/map.js:1199 (background)
- src/styles/map.js:1225 (background)
- src/styles/mapping-review.js:116
- src/styles/metrics.js:68 (background)
- src/styles/mobile.js:166 (background)
- src/styles/mobile.js:266 (background)
- src/styles/review.js:90 (background)
- src/styles/review.js:126 (background)
- src/styles/shell.js:184 (background)
- src/styles/shell.js:189 (background)
- src/styles/shell.js:224 (background)
- src/styles/shell.js:326 (background)
- src/styles/shell.js:410 (background)
- custom_components/eufy_vacuum/themes/preloaded.py:95
- custom_components/eufy_vacuum/themes/preloaded.py:133
- custom_components/eufy_vacuum/themes/preloaded.py:220
- custom_components/eufy_vacuum/themes/preloaded.py:331
- custom_components/eufy_vacuum/themes/preloaded.py:381
- custom_components/eufy_vacuum/themes/preloaded.py:404

**`--evcc-surface-subtle`** — Surface Subtle · default src/styles/foundation.js:137
- src/styles/index.js:846 (background)
- src/styles/index.js:861 (background)
- src/styles/maintenance.js:352 (background)
- src/styles/rooms.js:786 (background)
- src/styles/setup.js:548 (background)
- src/styles/setup.js:595 (background)
- src/styles/theme-preview.js:624 (background)
- src/styles/theme-preview.js:637 (background)

**`--evcc-surface-sunken`** — Surface Sunken · default src/styles/foundation.js:141
- src/styles/metrics.js:251 (background)
- src/styles/setup.js:310 (background)

**`--evcc-surface-warning`** — Surface Warning · default src/styles/foundation.js:142
- src/styles/learning.js:582 (background)

## Borders & Shadows  ·  6/6 consumed

**`--evcc-border-default`** — Border Default · default src/styles/foundation.js:153, src/styles/index.js:282, src/styles/index.js:715
- src/cards/dashboard-card.js:982 (--border)
- src/cards/_shared.js:194
- src/cards/_shared.js:197
- src/room-card.js:372 (--border)
- src/styles/base-station.js:22
- src/styles/external-jobs.js:21
- src/styles/external-jobs.js:48
- src/styles/external-jobs.js:68
- src/styles/external-jobs.js:108
- src/styles/external-jobs.js:119
- src/styles/external-jobs.js:129
- src/styles/external-jobs.js:141
- src/styles/external-jobs.js:151
- src/styles/foundation.js:44
- src/styles/foundation.js:206 (--evcc-chip-border)
- src/styles/foundation.js:299
- src/styles/index.js:170 (--evcc-modal-border)
- src/styles/index.js:171 (--evcc-modal-border-default)
- src/styles/index.js:199 (--evcc-modal-chip-border)
- src/styles/index.js:385
- src/styles/index.js:483
- src/styles/index.js:664 (--evcc-modal-border)
- src/styles/index.js:665 (--evcc-modal-border-default)
- src/styles/index.js:682 (--evcc-modal-chip-border)
- src/styles/index.js:809
- src/styles/index.js:929
- src/styles/learning.js:42 (--evcc-learning-panel-border)
- src/styles/learning.js:112 (--evcc-learning-confidence-neutral-border)
- src/styles/learning.js:611
- src/styles/learning.js:628
- src/styles/learning.js:650
- src/styles/maintenance.js:24
- src/styles/maintenance.js:140
- src/styles/maintenance.js:167
- src/styles/maintenance.js:264
- src/styles/maintenance.js:419
- src/styles/map.js:25
- src/styles/map.js:992
- src/styles/map.js:1094
- src/styles/map.js:1198
- src/styles/map.js:1214
- src/styles/map.js:1224
- src/styles/map.js:1371
- src/styles/map.js:1475
- src/styles/map.js:1561
- src/styles/map.js:1612
- src/styles/map.js:1664
- src/styles/mapping-review.js:30
- src/styles/mapping-review.js:180
- src/styles/metrics.js:22
- src/styles/metrics.js:158
- src/styles/metrics.js:195
- src/styles/metrics.js:227
- src/styles/metrics.js:252
- src/styles/modals.js:132
- src/styles/modals.js:181
- src/styles/modals.js:284
- src/styles/order.js:53
- src/styles/review.js:22
- src/styles/review.js:186 (border-color)
- src/styles/review.js:224
- src/styles/room-access.js:15
- src/styles/room-rules.js:59 (border-color)
- src/styles/room-rules.js:118
- src/styles/room-rules.js:236
- src/styles/room-rules.js:301 (border-color)
- src/styles/room-rules.js:335
- src/styles/room-rules.js:390 (border-color)
- src/styles/rooms.js:49
- src/styles/rooms.js:320
- src/styles/rooms.js:588
- src/styles/rooms.js:621
- src/styles/rooms.js:671
- src/styles/rooms.js:678
- src/styles/rooms.js:685
- src/styles/rooms.js:692
- src/styles/rooms.js:699
- src/styles/rooms.js:732
- src/styles/rooms.js:751 (--evcc-estimate-default-border)
- src/styles/rooms.js:827
- src/styles/rooms.js:834
- src/styles/rooms.js:841
- src/styles/run-profiles.js:23
- src/styles/run-profiles.js:53
- src/styles/run-profiles.js:83
- src/styles/saved-zones.js:13
- src/styles/saved-zones.js:77
- src/styles/saved-zones.js:127
- src/styles/saved-zones.js:183
- src/styles/setup.js:43
- src/styles/setup.js:125
- src/styles/setup.js:260
- src/styles/setup.js:309
- src/styles/setup.js:403
- src/styles/setup.js:620
- src/styles/setup.js:641
- src/styles/setup.js:668
- src/styles/theme-preview.js:96
- src/styles/theme-preview.js:185
- src/styles/theme-preview.js:195
- src/styles/theme-preview.js:216
- src/styles/theme-preview.js:344
- src/styles/theme-preview.js:486
- src/styles/theme-preview.js:562
- src/styles/theme-preview.js:590
- src/styles/theme.js:616
- src/styles/theme.js:759
- src/styles/theme.js:858
- src/styles/theme.js:898
- src/styles/theme.js:930
- src/styles/theme.js:942
- src/styles/theme.js:967
- src/styles/theme.js:989
- src/styles/theme.js:1015
- src/styles/theme.js:1027
- src/styles/theme.js:1052
- src/styles/theme.js:1076
- custom_components/eufy_vacuum/themes/preloaded.py:85
- custom_components/eufy_vacuum/themes/preloaded.py:104
- custom_components/eufy_vacuum/themes/preloaded.py:110
- custom_components/eufy_vacuum/themes/preloaded.py:119
- custom_components/eufy_vacuum/themes/preloaded.py:134
- custom_components/eufy_vacuum/themes/preloaded.py:172
- custom_components/eufy_vacuum/themes/preloaded.py:185
- custom_components/eufy_vacuum/themes/preloaded.py:189
- custom_components/eufy_vacuum/themes/preloaded.py:202
- custom_components/eufy_vacuum/themes/preloaded.py:203
- custom_components/eufy_vacuum/themes/preloaded.py:210

**`--evcc-border-strong`** — Border Strong · default src/styles/foundation.js:154, src/styles/index.js:290, src/styles/index.js:723
- src/styles/base-station.js:102 (border-color)
- src/styles/foundation.js:83
- src/styles/foundation.js:211 (--evcc-chip-hover-border)
- src/styles/index.js:172 (--evcc-modal-border-strong)
- src/styles/index.js:202 (--evcc-modal-chip-hover-border)
- src/styles/index.js:411
- src/styles/index.js:552
- src/styles/index.js:666 (--evcc-modal-border-strong)
- src/styles/index.js:685 (--evcc-modal-chip-hover-border)
- src/styles/maintenance.js:307 (border-color)
- src/styles/map.js:52 (border-color)
- src/styles/map.js:1006 (border-color)
- src/styles/map.js:1627 (border-color)
- src/styles/map.js:1677 (border-color)
- src/styles/metrics.js:164
- src/styles/modals.js:368
- src/styles/order.js:101
- src/styles/rooms.js:346 (border-color)
- src/styles/theme-preview.js:220
- src/styles/theme.js:308 (border-color)
- custom_components/eufy_vacuum/themes/preloaded.py:90
- custom_components/eufy_vacuum/themes/preloaded.py:128
- custom_components/eufy_vacuum/themes/preloaded.py:204
- custom_components/eufy_vacuum/themes/preloaded.py:212
- custom_components/eufy_vacuum/themes/preloaded.py:450

**`--evcc-border-subtle`** — Border Subtle · default src/styles/foundation.js:152, src/styles/index.js:286, src/styles/index.js:719
- src/styles/base-station.js:66
- src/styles/index.js:173 (--evcc-modal-border-subtle)
- src/styles/index.js:430
- src/styles/index.js:572
- src/styles/index.js:587
- src/styles/index.js:667 (--evcc-modal-border-subtle)
- src/styles/index.js:847
- src/styles/learning.js:339
- src/styles/learning.js:390
- src/styles/maintenance.js:97
- src/styles/maintenance.js:202
- src/styles/maintenance.js:353
- src/styles/maintenance.js:376
- src/styles/map.js:977
- src/styles/map.js:1072
- src/styles/map.js:1083
- src/styles/map.js:1148
- src/styles/map.js:1158
- src/styles/mapping-review.js:193 (border-color)
- src/styles/metrics.js:67
- src/styles/mobile.js:71
- src/styles/mobile.js:128
- src/styles/mobile.js:235
- src/styles/mobile.js:247 (background)
- src/styles/mobile.js:543
- src/styles/mobile.js:636
- src/styles/review.js:89
- src/styles/review.js:104
- src/styles/review.js:125
- src/styles/review.js:213
- src/styles/room-estimate.js:38
- src/styles/room-estimate.js:60
- src/styles/room-rules.js:27
- src/styles/room-rules.js:214
- src/styles/room-rules.js:243
- src/styles/room-rules.js:281
- src/styles/room-rules.js:293
- src/styles/room-rules.js:414
- src/styles/rooms.js:787 (border-color)
- src/styles/setup.js:175
- src/styles/setup.js:336
- src/styles/setup.js:547
- src/styles/setup.js:691
- src/styles/shell.js:66
- src/styles/shell.js:225
- src/styles/shell.js:308
- src/styles/shell.js:413
- src/styles/theme-preview.js:35
- src/styles/theme-preview.js:212
- src/styles/theme-preview.js:499
- src/styles/theme.js:46
- src/styles/theme.js:111
- src/styles/theme.js:242
- src/styles/theme.js:296
- src/styles/theme.js:387
- src/styles/theme.js:435
- src/styles/theme.js:455
- src/styles/theme.js:485
- src/styles/theme.js:500
- src/styles/theme.js:552
- src/styles/theme.js:572
- src/styles/theme.js:631 (border-color)
- src/styles/theme.js:653
- custom_components/eufy_vacuum/themes/preloaded.py:137
- custom_components/eufy_vacuum/themes/preloaded.py:205

**`--evcc-border-warning`** — Border Warning · default src/styles/foundation.js:155
- src/styles/learning.js:583

**`--evcc-shadow-card`** — Shadow Card · default —
- src/styles/learning.js:45 (--evcc-learning-panel-shadow)
- src/styles/order.js:150
- src/styles/order.js:162
- src/styles/rooms.js:322 (box-shadow)
- src/styles/run-profiles.js:25 (box-shadow)
- src/styles/saved-zones.js:15 (box-shadow)
- src/styles/shell.js:49 (box-shadow)
- src/styles/theme-preview.js:37 (box-shadow)
- src/styles/theme-preview.js:98 (box-shadow)
- src/styles/theme-preview.js:175 (box-shadow)
- src/styles/theme-preview.js:224 (box-shadow)

**`--evcc-shadow-hover`** — Shadow Hover · default —
- src/styles/order.js:122 (box-shadow)
- src/styles/order.js:156
- src/styles/rooms.js:341
- src/styles/rooms.js:645 (box-shadow)
- src/styles/theme-preview.js:228 (box-shadow)
- src/styles/theme-preview.js:380

## Chips  ·  31/31 consumed

**`--evcc-chip-active-bg`** — Chip Active BG · default —
- src/styles/foundation.js:87 (background)

**`--evcc-chip-active-border`** — Chip Active Border · default —
- src/styles/foundation.js:90 (border-color)

**`--evcc-chip-active-text`** — Chip Active Text · default —
- src/styles/foundation.js:89 (color)

**`--evcc-chip-bg`** — Chip BG · default src/styles/foundation.js:205, src/styles/index.js:387, src/styles/order.js:48, src/styles/rooms.js:454, src/styles/rooms.js:460, src/styles/rooms.js:467, src/styles/rooms.js:475, src/styles/rooms.js:577, src/styles/rooms.js:585, src/styles/rooms.js:592, src/styles/rooms.js:1108, src/styles/rooms.js:1114
- src/styles/foundation.js:46 (background)
- src/styles/maintenance.js:168 (background)
- src/styles/rooms.js:502
- src/styles/rooms.js:503
- src/styles/rooms.js:522
- src/styles/rooms.js:523
- src/styles/theme-preview.js:237

**`--evcc-chip-border`** — Chip Border · default src/styles/foundation.js:206, src/styles/index.js:383, src/styles/order.js:52, src/styles/rooms.js:455, src/styles/rooms.js:461, src/styles/rooms.js:469, src/styles/rooms.js:476, src/styles/rooms.js:580, src/styles/rooms.js:588, src/styles/rooms.js:594, src/styles/rooms.js:1109, src/styles/rooms.js:1115
- src/styles/foundation.js:44
- src/styles/maintenance.js:167
- src/styles/theme-preview.js:238

**`--evcc-chip-excluded-bg`** — Chip Excluded BG · default —
- src/styles/rooms.js:585 (--evcc-chip-bg)
- src/styles/theme-preview.js:249 (background)

**`--evcc-chip-excluded-border`** — Chip Excluded Border · default —
- src/styles/rooms.js:588 (--evcc-chip-border)
- src/styles/theme-preview.js:250 (border-color)

**`--evcc-chip-excluded-text`** — Chip Excluded Text · default —
- src/styles/rooms.js:587 (--evcc-chip-text)
- src/styles/theme-preview.js:251 (color)

**`--evcc-chip-font-size`** — Chip Font Size · default src/styles/index.js:395, src/styles/order.js:45, src/styles/order.js:72, src/styles/order.js:83, src/styles/rooms.js:452, src/styles/rooms.js:571, src/styles/rooms.js:928, src/styles/rooms.js:1106
- src/styles/foundation.js:49 (font-size)

**`--evcc-chip-font-weight`** — Chip Font Weight · default src/styles/index.js:398, src/styles/order.js:46, src/styles/order.js:73, src/styles/order.js:84, src/styles/rooms.js:453, src/styles/rooms.js:572, src/styles/rooms.js:1107
- src/styles/foundation.js:50 (font-weight)

**`--evcc-chip-gap`** — Chip Gap · default —
- src/styles/foundation.js:30 (gap)
- src/styles/order.js:34 (gap)
- src/styles/rooms.js:446 (gap)

**`--evcc-chip-height`** — Chip Height · default src/styles/foundation.js:201, src/styles/index.js:313, src/styles/order.js:43, src/styles/order.js:70, src/styles/order.js:81, src/styles/rooms.js:450, src/styles/rooms.js:569, src/styles/rooms.js:926, src/styles/rooms.js:1104
- src/styles/foundation.js:40 (min-height)
- src/styles/maintenance.js:164 (min-height)

**`--evcc-chip-hover-bg`** — Chip Hover BG · default src/styles/foundation.js:209, src/styles/index.js:401
- src/styles/foundation.js:81 (background)
- src/styles/order.js:99 (background)
- src/styles/theme-preview.js:237 (background)

**`--evcc-chip-hover-border`** — Chip Hover Border · default src/styles/foundation.js:211, src/styles/index.js:409
- src/styles/foundation.js:83 (border-color)
- src/styles/order.js:101 (border-color)
- src/styles/theme-preview.js:238 (border-color)

**`--evcc-chip-hover-text`** — Chip Hover Text · default src/styles/foundation.js:210, src/styles/index.js:405
- src/styles/foundation.js:82 (color)
- src/styles/order.js:100 (color)
- src/styles/theme-preview.js:239 (color)

**`--evcc-chip-icon-height`** — Chip Icon Height · default src/styles/foundation.js:213, src/styles/index.js:413
- src/styles/foundation.js:101 (min-height)

**`--evcc-chip-icon-padding`** — Chip Icon Padding · default src/styles/foundation.js:214, src/styles/index.js:416
- src/styles/foundation.js:102 (padding)

**`--evcc-chip-icon-size`** — Chip Icon Size · default src/styles/foundation.js:215, src/styles/index.js:419
- src/styles/foundation.js:103 (font-size)

**`--evcc-chip-included-bg`** — Chip Included BG · default —
- src/styles/index.js:618 (background)
- src/styles/rooms.js:577 (--evcc-chip-bg)
- src/styles/theme-preview.js:243 (background)

**`--evcc-chip-included-border`** — Chip Included Border · default —
- src/styles/index.js:626 (border-color)
- src/styles/rooms.js:580 (--evcc-chip-border)
- src/styles/theme-preview.js:244 (border-color)

**`--evcc-chip-included-text`** — Chip Included Text · default —
- src/styles/index.js:622 (color)
- src/styles/rooms.js:579 (--evcc-chip-text)
- src/styles/theme-preview.js:245 (color)

**`--evcc-chip-neutral-bg`** — Chip Neutral BG · default —
- src/styles/order.js:49

**`--evcc-chip-padding`** — Chip Padding · default src/styles/foundation.js:202, src/styles/index.js:316, src/styles/order.js:44, src/styles/order.js:71, src/styles/order.js:82, src/styles/rooms.js:451, src/styles/rooms.js:570, src/styles/rooms.js:927, src/styles/rooms.js:1105
- src/styles/foundation.js:41 (padding)
- src/styles/maintenance.js:165 (padding)

**`--evcc-chip-radius`** — Chip Radius · default src/styles/foundation.js:203, src/styles/index.js:319
- src/styles/foundation.js:43 (border-radius)
- src/styles/maintenance.js:166 (border-radius)

**`--evcc-chip-success-bg`** — Chip Success BG · default —
- src/styles/rooms.js:83 (background)
- src/styles/theme-preview.js:255 (background)

**`--evcc-chip-success-border`** — Chip Success Border · default —
- src/styles/rooms.js:86 (border-color)
- src/styles/theme-preview.js:256 (border-color)

**`--evcc-chip-success-text`** — Chip Success Text · default —
- src/styles/rooms.js:85 (color)
- src/styles/theme-preview.js:257 (color)

**`--evcc-chip-text`** — Chip Text · default src/styles/foundation.js:207, src/styles/index.js:391, src/styles/order.js:55, src/styles/rooms.js:456, src/styles/rooms.js:462, src/styles/rooms.js:471, src/styles/rooms.js:579, src/styles/rooms.js:587, src/styles/rooms.js:593, src/styles/rooms.js:1110, src/styles/rooms.js:1116
- src/styles/foundation.js:47 (color)
- src/styles/maintenance.js:169 (color)
- src/styles/theme-preview.js:239

**`--evcc-chip-warning-bg`** — Chip Warning BG · default —
- src/styles/rooms.js:97 (background)
- src/styles/rooms.js:654 (background)
- src/styles/theme-preview.js:261 (background)

**`--evcc-chip-warning-border`** — Chip Warning Border · default —
- src/styles/rooms.js:100 (border-color)
- src/styles/rooms.js:656 (border-color)
- src/styles/theme-preview.js:262 (border-color)

**`--evcc-chip-warning-text`** — Chip Warning Text · default —
- src/styles/rooms.js:99 (color)
- src/styles/rooms.js:658 (color)
- src/styles/theme-preview.js:263 (color)

## Room Cards  ·  13/13 consumed

**`--evcc-profile-chip-bg`** — Profile Chip BG · default —
- src/styles/rooms.js:460 (--evcc-chip-bg)
- src/styles/theme-preview.js:303 (background)

**`--evcc-profile-chip-border`** — Profile Chip Border · default —
- src/styles/rooms.js:461 (--evcc-chip-border)
- src/styles/theme-preview.js:304 (border-color)

**`--evcc-profile-chip-custom-bg`** — Profile Chip Custom BG · default —
- src/styles/rooms.js:467 (--evcc-chip-bg)
- src/styles/theme-preview.js:309 (background)

**`--evcc-profile-chip-custom-border`** — Profile Chip Custom Border · default —
- src/styles/rooms.js:469 (--evcc-chip-border)
- src/styles/theme-preview.js:310 (border-color)

**`--evcc-profile-chip-custom-text`** — Profile Chip Custom Text · default —
- src/styles/rooms.js:471 (--evcc-chip-text)
- src/styles/theme-preview.js:311 (color)

**`--evcc-profile-chip-text`** — Profile Chip Text · default —
- src/styles/rooms.js:462 (--evcc-chip-text)
- src/styles/theme-preview.js:305 (color)

**`--evcc-room-chip-bg`** — Room Chip BG · default —
- src/styles/rooms.js:454 (--evcc-chip-bg)
- src/styles/rooms.js:475 (--evcc-chip-bg)
- src/styles/theme-preview.js:315 (background)

**`--evcc-room-chip-border`** — Room Chip Border · default —
- src/styles/rooms.js:455 (--evcc-chip-border)
- src/styles/rooms.js:476 (--evcc-chip-border)
- src/styles/theme-preview.js:316 (border-color)

**`--evcc-room-chip-text`** — Room Chip Text · default —
- src/styles/rooms.js:456 (--evcc-chip-text)
- src/styles/theme-preview.js:317 (color)

**`--evcc-room-fill-opacity`** — Room Card Opacity · default src/styles/rooms.js:1081, src/styles/rooms.js:1085, src/styles/rooms.js:1089
- src/styles/rooms.js:969 (opacity)
- src/styles/theme-preview.js:272
- src/styles/theme-preview.js:282

**`--evcc-room-grid-columns`** — Room Grid Columns · default —
- src/styles/layout.js:79 (grid-template-columns)

**`--evcc-room-grid-gap`** — Room Grid Gap · default src/styles/layout.js:64
- src/styles/layout.js:78 (gap)

**`--evcc-room-grid-min`** — Room Grid Min · default src/styles/layout.js:65
- src/styles/layout.js:81

## Map  ·  22/34 consumed

**`--evcc-map-label-bg`** — Map Label Background · default src/styles/index.js:324
- src/styles/map.js:659 (background)
- src/styles/map.js:788 (background)
- src/styles/map.js:825 (background)

**`--evcc-map-label-text`** — Map Label Text · default src/styles/index.js:327
- src/styles/map.js:652 (color)

**`--evcc-map-label-text-selected`** — Map Label Text (Selected) · default src/styles/index.js:330
- src/styles/map.js:669 (color)

**`--evcc-map-label-order-text`** — Map Order Badge Text · default src/styles/index.js:333
- src/styles/map.js:680 (color)
- src/styles/map.js:1018 (color)

**`--evcc-map-tooltip-bg`** — Map Tooltip Background · default src/styles/index.js:336
- src/styles/map.js:210 (background)
- src/styles/map.js:917 (background)

**`--evcc-map-tooltip-border`** — Map Tooltip Border · default src/styles/index.js:339
- src/styles/map.js:211
- src/styles/map.js:227
- src/styles/map.js:395
- src/styles/map.js:413
- src/styles/map.js:449
- src/styles/map.js:496
- src/styles/map.js:881
- src/styles/map.js:919

**`--evcc-map-tooltip-text`** — Map Tooltip Text · default src/styles/index.js:342
- src/styles/map.js:225 (color)
- src/styles/map.js:411 (color)
- src/styles/map.js:454 (color)
- src/styles/map.js:486 (color)
- src/styles/map.js:494 (color)
- src/styles/map.js:514 (color)
- src/styles/map.js:886 (color)
- src/styles/map.js:902 (color)
- src/styles/map.js:933 (color)

**`--evcc-map-tooltip-hint`** — Map Tooltip Hint Text · default src/styles/index.js:345
- src/styles/map.js:246 (color)
- src/styles/map.js:402 (color)
- src/styles/map.js:466 (color)
- src/styles/map.js:476 (color)
- src/styles/map.js:532 (color)
- src/styles/map.js:890 (color)
- src/styles/map.js:939 (color)

**`--evcc-map-compose-selected-stroke`** — Composer Selected Outline · default src/styles/index.js:348
- src/styles/map.js:1275 (stroke)

**`--evcc-map-compose-cut-fill`** — Composer Cutout Fill · default src/styles/index.js:351
- src/styles/map.js:1295 (fill)

**`--evcc-map-compose-cut-selected-fill`** — Composer Cutout Fill (Selected) · default src/styles/index.js:354
- src/styles/map.js:1299 (fill)

**`--evcc-map-vertex-selected-glow`** — Composer Selected Vertex Glow · default src/styles/index.js:357
- src/styles/map.js:1135

**`--evcc-map-ov-current`** — Overlay: Current Room · default src/styles/index.js:362
- src/styles/map.js:693 (fill)
- src/styles/map.js:695 (stroke)

**`--evcc-map-ov-nogo`** — Overlay: No-Go Zone · default src/styles/index.js:364
- src/styles/map.js:707 (fill)
- src/styles/map.js:708 (stroke)

**`--evcc-map-ov-nomop`** — Overlay: No-Mop Zone · default src/styles/index.js:366
- src/styles/map.js:711 (fill)
- src/styles/map.js:712 (stroke)

**`--evcc-map-ov-wall`** — Overlay: Virtual Wall · default src/styles/index.js:368
- src/styles/map.js:720 (stroke)

**`--evcc-map-ov-zone`** — Overlay: Saved Zone · default src/styles/index.js:370
- src/styles/map.js:715 (fill)
- src/styles/map.js:716 (stroke)

**`--evcc-map-ov-path`** — Overlay: Cleaning Path · default src/styles/index.js:372
- src/styles/map.js:728 (stroke)

**`--evcc-map-ov-robot`** — Overlay: Robot Marker · default src/styles/index.js:374
- src/styles/map.js:755 (background)
- src/styles/map.js:766

**`--evcc-map-ov-dock`** — Overlay: Dock Marker · default src/styles/index.js:376
- src/styles/map.js:748 (background)

**`--evcc-map-ov-obstacle`** — Overlay: Obstacle Marker · default src/styles/index.js:378
- src/styles/map.js:774 (background)
- src/styles/map.js:778

**`--evcc-map-ov-area-text`** — Overlay: Area Label Text · default src/styles/index.js:380
- src/styles/map.js:787 (color)

**`--evcc-room-fill-1`** — Map Room Color 1 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-2`** — Map Room Color 2 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-3`** — Map Room Color 3 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-4`** — Map Room Color 4 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-5`** — Map Room Color 5 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-6`** — Map Room Color 6 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-7`** — Map Room Color 7 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-8`** — Map Room Color 8 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-9`** — Map Room Color 9 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-10`** — Map Room Color 10 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-11`** — Map Room Color 11 · default —
- _no consumer — only seeded_

**`--evcc-room-fill-12`** — Map Room Color 12 · default —
- _no consumer — only seeded_

## Floor Textures  ·  4/4 consumed

**`--evcc-floor-textures-card-enabled`** — Card Textures Enabled (0/1) · default —
- src/styles/floor-texture-styles.js:80

**`--evcc-floor-textures-map-enabled`** — Map Textures Enabled (0/1) · default —
- src/styles/floor-texture-styles.js:104

**`--evcc-floor-texture-opacity-card`** — Card Texture Opacity (all) · default —
- src/renderers/floor-texture-surface.js:99

**`--evcc-floor-texture-opacity-map`** — Map Texture Opacity (all) · default —
- src/styles/floor-texture-styles.js:103

## Floor Textures — Tile  ·  0/7 consumed

**`--evcc-floor-tile-base`** — Tile Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-tile-grout`** — Tile Grout Color · default —
- _no consumer — only seeded_

**`--evcc-floor-tile-accent`** — Tile Grout Line Color · default —
- _no consumer — only seeded_

**`--evcc-floor-tile-opacity-card`** — Tile Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-tile-face-opacity`** — Tile Base Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-tile-grout-opacity`** — Tile Grout Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-tile-line-opacity`** — Tile Grout Line Layer Opacity · default —
- _no consumer — only seeded_

## Floor Textures — Wood  ·  0/6 consumed

**`--evcc-floor-wood-base`** — Wood Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-wood-accent`** — Wood Seam Color · default —
- _no consumer — only seeded_

**`--evcc-floor-wood-opacity-card`** — Wood Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-wood-depth-opacity`** — Wood Depth Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-wood-grain-opacity`** — Wood Grain Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-wood-seam-opacity`** — Wood Seam Layer Opacity · default —
- _no consumer — only seeded_

## Floor Textures — Marble  ·  10/15 consumed

**`--evcc-floor-marble-base`** — Marble Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-marble-micro`** — Marble Micro Color · default —
- _no consumer — only seeded_

**`--evcc-floor-marble-accent`** — Marble Vein Color · default —
- src/textures/floor-texture-registry.js:152

**`--evcc-floor-marble-opacity-card`** — Marble Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-marble-base-opacity`** — Marble Base Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-marble-micro-opacity`** — Marble Micro Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-marble-vein-opacity`** — Marble Vein Opacity (master) · default —
- src/textures/floor-texture-registry.js:143
- src/textures/floor-texture-registry.js:154

**`--evcc-floor-marble-vein-blur`** — Marble Vein Blur (master, px) · default —
- src/textures/floor-texture-registry.js:145
- src/textures/floor-texture-registry.js:156

**`--evcc-floor-marble-vein-major-opacity`** — Marble Major Vein Opacity +/- · default —
- src/textures/floor-texture-registry.js:143

**`--evcc-floor-marble-vein-minor-opacity`** — Marble Minor Vein Opacity +/- · default —
- src/textures/floor-texture-registry.js:154

**`--evcc-floor-marble-vein-major-blur`** — Marble Major Vein Blur +/- (px) · default —
- src/textures/floor-texture-registry.js:145

**`--evcc-floor-marble-vein-minor-blur`** — Marble Minor Vein Blur +/- (px) · default —
- src/textures/floor-texture-registry.js:156

**`--evcc-floor-marble-vein-minor-light`** — Marble Minor Vein Lighten (L+) · default —
- src/textures/floor-texture-registry.js:152

**`--evcc-floor-marble-vein-minor-chroma`** — Marble Minor Vein Saturation (xC) · default —
- src/textures/floor-texture-registry.js:152

**`--evcc-floor-marble-vein-minor-hue`** — Marble Minor Vein Hue Shift (deg) · default —
- src/textures/floor-texture-registry.js:152

## Floor Textures — Concrete  ·  0/5 consumed

**`--evcc-floor-concrete-base`** — Concrete Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-concrete-accent`** — Concrete Micro Color · default —
- _no consumer — only seeded_

**`--evcc-floor-concrete-opacity-card`** — Concrete Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-concrete-broad-opacity`** — Concrete Base Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-concrete-micro-opacity`** — Concrete Micro Layer Opacity · default —
- _no consumer — only seeded_

## Floor Textures — Carpet Low  ·  0/5 consumed

**`--evcc-floor-carpet-low-base`** — Carpet Low Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-low-weave`** — Carpet Low Weave Color · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-low-opacity-card`** — Carpet Low Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-low-base-opacity`** — Carpet Low Base Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-low-weave-opacity`** — Carpet Low Weave Layer Opacity · default —
- _no consumer — only seeded_

## Floor Textures — Carpet High  ·  0/5 consumed

**`--evcc-floor-carpet-high-base`** — Carpet High Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-high-weave`** — Carpet High Weave Color · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-high-opacity-card`** — Carpet High Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-high-base-opacity`** — Carpet High Base Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-high-weave-opacity`** — Carpet High Weave Layer Opacity · default —
- _no consumer — only seeded_

## Floor Textures — Granite  ·  0/5 consumed

**`--evcc-floor-granite-light-base`** — Granite Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-granite-light-aggregate`** — Granite Aggregate Color · default —
- _no consumer — only seeded_

**`--evcc-floor-granite-light-opacity-card`** — Granite Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-granite-light-base-opacity`** — Granite Base Layer Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-granite-light-aggregate-opacity`** — Granite Aggregate Layer Opacity · default —
- _no consumer — only seeded_

## Queue & Ordering  ·  41/41 consumed

**`--evcc-drag-opacity`** — Drag Opacity · default —
- src/styles/order.js:130 (opacity)
- src/styles/theme-preview.js:378 (opacity)

**`--evcc-drag-scale`** — Drag Scale · default —
- src/styles/order.js:131
- src/styles/theme-preview.js:379

**`--evcc-drag-shadow`** — Drag Shadow · default —
- src/styles/order.js:132 (box-shadow)
- src/styles/theme-preview.js:380 (box-shadow)

**`--evcc-order-chip-bg`** — Order Chip BG · default —
- src/styles/order.js:48 (--evcc-chip-bg)
- src/styles/theme-preview.js:333 (background)

**`--evcc-order-chip-border`** — Order Chip Border · default —
- src/styles/order.js:52 (--evcc-chip-border)
- src/styles/theme-preview.js:334 (border-color)

**`--evcc-order-chip-text`** — Order Chip Text · default —
- src/styles/order.js:55 (--evcc-chip-text)
- src/styles/theme-preview.js:335 (color)

**`--evcc-order-feedback-border`** — Order Feedback Border · default —
- src/styles/order.js:173 (border-color)
- src/styles/theme-preview.js:384

**`--evcc-order-target-outline`** — Order Target Outline · default —
- src/styles/order.js:137
- src/styles/theme-preview.js:384

**`--evcc-progress-complete`** — Progress Complete · default —
- src/styles/rooms.js:1030 (background)
- src/styles/rooms.js:1038 (background)

**`--evcc-progress-fill`** — Progress Fill · default —
- src/styles/rooms.js:941 (background)
- src/styles/rooms.js:963 (background)

**`--evcc-queue-chip-bg`** — Queue Chip BG · default —
- src/styles/rooms.js:620 (background)
- src/styles/rooms.js:641
- src/styles/rooms.js:670
- src/styles/rooms.js:677
- src/styles/rooms.js:684
- src/styles/rooms.js:691
- src/styles/rooms.js:698

**`--evcc-queue-chip-border`** — Queue Chip Border · default —
- src/styles/rooms.js:621
- src/styles/rooms.js:671
- src/styles/rooms.js:678
- src/styles/rooms.js:685
- src/styles/rooms.js:692
- src/styles/rooms.js:699

**`--evcc-queue-chip-gap`** — Queue Chip Gap · default —
- src/styles/rooms.js:605 (gap)
- src/styles/theme-preview.js:341 (gap)

**`--evcc-queue-chip-text`** — Queue Chip Text · default —
- src/styles/rooms.js:622 (color)
- src/styles/rooms.js:644
- src/styles/rooms.js:672
- src/styles/rooms.js:679
- src/styles/rooms.js:686
- src/styles/rooms.js:693
- src/styles/rooms.js:700

**`--evcc-queue-completed-bg`** — Queue Completed BG · default —
- src/styles/rooms.js:691 (background)
- src/styles/theme-preview.js:364 (background)

**`--evcc-queue-completed-border`** — Queue Completed Border · default —
- src/styles/rooms.js:692 (border-color)
- src/styles/theme-preview.js:365 (border-color)

**`--evcc-queue-completed-opacity`** — Queue Completed Opacity · default —
- src/styles/rooms.js:694 (opacity)
- src/styles/theme-preview.js:367 (opacity)

**`--evcc-queue-completed-text`** — Queue Completed Text · default —
- src/styles/rooms.js:693 (color)
- src/styles/theme-preview.js:366 (color)

**`--evcc-queue-current-bg`** — Queue Current BG · default —
- src/styles/rooms.js:662 (background)
- src/styles/rooms.js:677 (background)
- src/styles/theme-preview.js:350 (background)

**`--evcc-queue-current-border`** — Queue Current Border · default —
- src/styles/rooms.js:664 (border-color)
- src/styles/rooms.js:678 (border-color)
- src/styles/theme-preview.js:351 (border-color)

**`--evcc-queue-current-glow`** — Queue Current Glow · default —
- src/styles/rooms.js:680 (box-shadow)
- src/styles/theme-preview.js:353 (box-shadow)

**`--evcc-queue-current-text`** — Queue Current Text · default —
- src/styles/rooms.js:666 (color)
- src/styles/rooms.js:679 (color)
- src/styles/theme-preview.js:352 (color)

**`--evcc-queue-hover-bg`** — Queue Hover BG · default —
- src/styles/rooms.js:641 (background)

**`--evcc-queue-hover-border`** — Queue Hover Border · default —
- src/styles/rooms.js:642 (border-color)

**`--evcc-queue-hover-text`** — Queue Hover Text · default —
- src/styles/rooms.js:644 (color)

**`--evcc-queue-inferred-bg`** — Queue Inferred BG · default —
- src/styles/rooms.js:684 (background)
- src/styles/theme-preview.js:371 (background)

**`--evcc-queue-inferred-border`** — Queue Inferred Border · default —
- src/styles/rooms.js:685 (border-color)
- src/styles/theme-preview.js:372 (border-color)

**`--evcc-queue-inferred-glow`** — Queue Inferred Glow · default —
- src/styles/rooms.js:687 (box-shadow)
- src/styles/theme-preview.js:374 (box-shadow)

**`--evcc-queue-inferred-text`** — Queue Inferred Text · default —
- src/styles/rooms.js:686 (color)
- src/styles/theme-preview.js:373 (color)

**`--evcc-queue-order-bg`** — Queue Order BG · default —
- src/styles/rooms.js:711 (background)
- src/styles/theme-preview.js:333

**`--evcc-queue-order-border`** — Queue Order Border · default —
- src/styles/rooms.js:712
- src/styles/theme-preview.js:334

**`--evcc-queue-order-text`** — Queue Order Text · default —
- src/styles/rooms.js:715 (color)
- src/styles/theme-preview.js:335

**`--evcc-queue-pending-bg`** — Queue Pending BG · default —
- src/styles/rooms.js:670 (background)
- src/styles/theme-preview.js:357 (background)

**`--evcc-queue-pending-border`** — Queue Pending Border · default —
- src/styles/rooms.js:671 (border-color)
- src/styles/theme-preview.js:358 (border-color)

**`--evcc-queue-pending-opacity`** — Queue Pending Opacity · default —
- src/styles/rooms.js:673 (opacity)
- src/styles/theme-preview.js:360 (opacity)

**`--evcc-queue-pending-text`** — Queue Pending Text · default —
- src/styles/rooms.js:672 (color)
- src/styles/theme-preview.js:359 (color)

**`--evcc-queue-skipped-bg`** — Queue Skipped BG · default —
- src/styles/rooms.js:698 (background)

**`--evcc-queue-skipped-border`** — Queue Skipped Border · default —
- src/styles/rooms.js:699 (border-color)

**`--evcc-queue-skipped-text`** — Queue Skipped Text · default —
- src/styles/rooms.js:700 (color)

**`--evcc-reorder-feedback-duration`** — Reorder Feedback Duration · default —
- src/styles/order.js:169

**`--evcc-reorder-flip-easing`** — Reorder Flip Easing · default —
- src/styles/order.js:170

## Status, Confidence & Alerts  ·  31/31 consumed

**`--evcc-color-cleaning`** — Color Cleaning · default src/styles/foundation.js:192
- src/styles/theme-preview.js:410

**`--evcc-color-docked`** — Color Docked · default src/styles/foundation.js:193
- src/styles/theme-preview.js:414

**`--evcc-color-error`** — Color Error · default src/styles/foundation.js:194
- src/styles/theme-preview.js:418

**`--evcc-color-idle`** — Color Idle · default src/styles/foundation.js:195
- src/styles/theme-preview.js:406

**`--evcc-confidence-high-bg`** — Confidence High BG · default src/styles/learning.js:125
- src/styles/rooms.js:826
- src/styles/rooms.js:828
- src/styles/theme-preview.js:423 (background)

**`--evcc-confidence-high-border`** — Confidence High Border · default src/styles/learning.js:127
- src/styles/rooms.js:827
- src/styles/theme-preview.js:424 (border-color)

**`--evcc-confidence-high-text`** — Confidence High Text · default src/styles/learning.js:129
- src/styles/theme-preview.js:425 (color)

**`--evcc-confidence-low-bg`** — Confidence Low BG · default src/styles/learning.js:139
- src/styles/rooms.js:840
- src/styles/rooms.js:842
- src/styles/theme-preview.js:436 (background)

**`--evcc-confidence-low-border`** — Confidence Low Border · default src/styles/learning.js:141
- src/styles/rooms.js:841
- src/styles/theme-preview.js:437 (border-color)

**`--evcc-confidence-low-text`** — Confidence Low Text · default src/styles/learning.js:143
- src/styles/theme-preview.js:438 (color)

**`--evcc-confidence-medium-bg`** — Confidence Medium BG · default src/styles/learning.js:132
- src/styles/rooms.js:833
- src/styles/rooms.js:835
- src/styles/theme-preview.js:430 (background)

**`--evcc-confidence-medium-border`** — Confidence Medium Border · default src/styles/learning.js:134
- src/styles/rooms.js:834
- src/styles/theme-preview.js:431 (border-color)

**`--evcc-confidence-medium-text`** — Confidence Medium Text · default src/styles/learning.js:136
- src/styles/theme-preview.js:432 (color)

**`--evcc-sem-error`** — Sem Error · default src/styles/foundation.js:164
- src/styles/external-jobs.js:80
- src/styles/external-jobs.js:81
- src/styles/external-jobs.js:82 (color)
- src/styles/foundation.js:194 (--evcc-color-error)
- src/styles/index.js:498 (color)
- src/styles/index.js:936
- src/styles/learning.js:98
- src/styles/learning.js:101 (--evcc-learning-confidence-low-text)
- src/styles/learning.js:106
- src/styles/learning.js:107
- src/styles/learning.js:140
- src/styles/learning.js:142
- src/styles/learning.js:144 (--evcc-confidence-low-text)
- src/styles/learning.js:329
- src/styles/learning.js:330
- src/styles/learning.js:331 (color)
- src/styles/maintenance.js:38
- src/styles/maintenance.js:108
- src/styles/maintenance.js:109
- src/styles/maintenance.js:298
- src/styles/map.js:1414
- src/styles/map.js:1415 (color)
- src/styles/map.js:1416
- src/styles/map.js:1420
- src/styles/map.js:1421
- src/styles/map.js:1428 (background)
- src/styles/map.js:1430 (border-color)
- src/styles/map.js:1436
- src/styles/map.js:1437
- src/styles/map.js:1447 (color)
- src/styles/mapping-review.js:94
- src/styles/mapping-review.js:95 (color)
- src/styles/mapping-review.js:187
- src/styles/mapping-review.js:188
- src/styles/review.js:151
- src/styles/review.js:173
- src/styles/review.js:174
- src/styles/review.js:175 (color)
- src/styles/room-rules.js:149
- src/styles/room-rules.js:150 (color)
- src/styles/room-rules.js:151
- src/styles/room-rules.js:218 (color)
- src/styles/room-rules.js:219
- src/styles/room-rules.js:223
- src/styles/room-rules.js:224
- src/styles/room-rules.js:349 (border-color)
- src/styles/room-rules.js:403
- src/styles/room-rules.js:404
- src/styles/room-rules.js:405 (color)
- src/styles/rooms.js:111
- src/styles/rooms.js:112 (color)
- src/styles/rooms.js:113
- src/styles/rooms.js:118
- src/styles/rooms.js:119
- src/styles/rooms.js:137
- src/styles/rooms.js:138
- src/styles/setup.js:147
- src/styles/setup.js:148
- src/styles/setup.js:149 (color)
- src/styles/setup.js:431 (background)
- src/styles/setup.js:442 (color)
- src/styles/setup.js:443
- src/styles/setup.js:449
- src/styles/setup.js:461
- src/styles/setup.js:462
- src/styles/setup.js:489 (color)
- src/styles/setup.js:514
- src/styles/setup.js:522 (border-color)
- src/styles/shell.js:119
- src/styles/shell.js:136 (color)
- src/styles/shell.js:424
- src/styles/theme-preview.js:461
- src/styles/theme-preview.js:462
- src/styles/theme-preview.js:463 (color)
- src/styles/theme.js:469 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:86
- custom_components/eufy_vacuum/themes/preloaded.py:87
- custom_components/eufy_vacuum/themes/preloaded.py:88
- custom_components/eufy_vacuum/themes/preloaded.py:144
- custom_components/eufy_vacuum/themes/preloaded.py:149
- custom_components/eufy_vacuum/themes/preloaded.py:150
- custom_components/eufy_vacuum/themes/preloaded.py:151
- custom_components/eufy_vacuum/themes/preloaded.py:165
- custom_components/eufy_vacuum/themes/preloaded.py:180
- custom_components/eufy_vacuum/themes/preloaded.py:181
- custom_components/eufy_vacuum/themes/preloaded.py:330
- custom_components/eufy_vacuum/themes/preloaded.py:404
- custom_components/eufy_vacuum/themes/preloaded.py:427
- custom_components/eufy_vacuum/themes/preloaded.py:450

**`--evcc-sem-info`** — Sem Info · default src/styles/foundation.js:168
- src/styles/mapping-review.js:99
- src/styles/mapping-review.js:100 (color)
- src/styles/setup.js:560
- src/styles/theme-preview.js:449
- src/styles/theme-preview.js:450
- src/styles/theme-preview.js:451 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:130
- custom_components/eufy_vacuum/themes/preloaded.py:131
- custom_components/eufy_vacuum/themes/preloaded.py:132

**`--evcc-sem-success`** — Sem Success · default src/styles/foundation.js:162
- src/styles/base-station.js:107
- src/styles/foundation.js:192 (--evcc-color-cleaning)
- src/styles/index.js:619
- src/styles/index.js:623
- src/styles/index.js:627
- src/styles/index.js:935
- src/styles/learning.js:64
- src/styles/learning.js:67
- src/styles/learning.js:70 (--evcc-learning-confidence-high-text)
- src/styles/learning.js:75
- src/styles/learning.js:76
- src/styles/learning.js:126
- src/styles/learning.js:128
- src/styles/learning.js:130 (--evcc-confidence-high-text)
- src/styles/maintenance.js:29
- src/styles/maintenance.js:102
- src/styles/maintenance.js:103
- src/styles/maintenance.js:289
- src/styles/map.js:1347 (color)
- src/styles/map.js:1587
- src/styles/map.js:1592
- src/styles/map.js:1593 (color)
- src/styles/map.js:1595
- src/styles/map.js:1633
- src/styles/map.js:1634 (color)
- src/styles/map.js:1636
- src/styles/mapping-review.js:78
- src/styles/mapping-review.js:79 (color)
- src/styles/rooms.js:84
- src/styles/rooms.js:87
- src/styles/rooms.js:92
- src/styles/rooms.js:93
- src/styles/rooms.js:264
- src/styles/rooms.js:266
- src/styles/rooms.js:278
- src/styles/rooms.js:285
- src/styles/rooms.js:286
- src/styles/rooms.js:291
- src/styles/rooms.js:578
- src/styles/rooms.js:579
- src/styles/rooms.js:581
- src/styles/rooms.js:663
- src/styles/rooms.js:665
- src/styles/rooms.js:666
- src/styles/rooms.js:1032
- src/styles/rooms.js:1040
- src/styles/setup.js:68 (background)
- src/styles/setup.js:141
- src/styles/setup.js:142
- src/styles/setup.js:143 (color)
- src/styles/setup.js:215
- src/styles/setup.js:216
- src/styles/setup.js:230 (color)
- src/styles/setup.js:292 (color)
- src/styles/setup.js:366 (background)
- src/styles/shell.js:116
- src/styles/shell.js:121
- src/styles/shell.js:420
- src/styles/theme.js:393 (color)
- src/styles/theme.js:394
- src/styles/theme.js:395
- custom_components/eufy_vacuum/themes/preloaded.py:92
- custom_components/eufy_vacuum/themes/preloaded.py:93
- custom_components/eufy_vacuum/themes/preloaded.py:94
- custom_components/eufy_vacuum/themes/preloaded.py:96
- custom_components/eufy_vacuum/themes/preloaded.py:97
- custom_components/eufy_vacuum/themes/preloaded.py:98
- custom_components/eufy_vacuum/themes/preloaded.py:121
- custom_components/eufy_vacuum/themes/preloaded.py:122
- custom_components/eufy_vacuum/themes/preloaded.py:123
- custom_components/eufy_vacuum/themes/preloaded.py:142
- custom_components/eufy_vacuum/themes/preloaded.py:146
- custom_components/eufy_vacuum/themes/preloaded.py:147
- custom_components/eufy_vacuum/themes/preloaded.py:148
- custom_components/eufy_vacuum/themes/preloaded.py:159
- custom_components/eufy_vacuum/themes/preloaded.py:160
- custom_components/eufy_vacuum/themes/preloaded.py:161
- custom_components/eufy_vacuum/themes/preloaded.py:163
- custom_components/eufy_vacuum/themes/preloaded.py:177
- custom_components/eufy_vacuum/themes/preloaded.py:178
- custom_components/eufy_vacuum/themes/preloaded.py:179
- custom_components/eufy_vacuum/themes/preloaded.py:328
- custom_components/eufy_vacuum/themes/preloaded.py:381
- custom_components/eufy_vacuum/themes/preloaded.py:404
- custom_components/eufy_vacuum/themes/preloaded.py:427
- custom_components/eufy_vacuum/themes/preloaded.py:450

**`--evcc-sem-warning`** — Sem Warning · default src/styles/foundation.js:163
- src/styles/external-jobs.js:38
- src/styles/external-jobs.js:39
- src/styles/external-jobs.js:40 (color)
- src/styles/external-jobs.js:162 (color)
- src/styles/index.js:209
- src/styles/index.js:210
- src/styles/index.js:211
- src/styles/index.js:636
- src/styles/index.js:640
- src/styles/index.js:644
- src/styles/learning.js:81
- src/styles/learning.js:84
- src/styles/learning.js:87 (--evcc-learning-confidence-medium-text)
- src/styles/learning.js:92
- src/styles/learning.js:93
- src/styles/learning.js:133
- src/styles/learning.js:135
- src/styles/learning.js:137 (--evcc-confidence-medium-text)
- src/styles/learning.js:317
- src/styles/learning.js:318
- src/styles/learning.js:319 (color)
- src/styles/maintenance.js:34
- src/styles/maintenance.js:294
- src/styles/mapping-review.js:83
- src/styles/mapping-review.js:84 (color)
- src/styles/mapping-review.js:89
- src/styles/mapping-review.js:90 (color)
- src/styles/metrics.js:94
- src/styles/metrics.js:95
- src/styles/metrics.js:96 (color)
- src/styles/modals.js:259
- src/styles/modals.js:263
- src/styles/modals.js:267
- src/styles/review.js:155
- src/styles/review.js:180
- src/styles/review.js:181
- src/styles/review.js:182 (color)
- src/styles/room-access.js:47
- src/styles/room-access.js:48 (color)
- src/styles/room-access.js:72 (color)
- src/styles/room-access.js:78
- src/styles/room-access.js:79
- src/styles/rooms.js:98
- src/styles/rooms.js:99
- src/styles/rooms.js:101
- src/styles/rooms.js:106
- src/styles/rooms.js:107
- src/styles/rooms.js:128 (color)
- src/styles/rooms.js:150
- src/styles/rooms.js:151
- src/styles/rooms.js:191
- src/styles/rooms.js:192
- src/styles/rooms.js:298
- src/styles/rooms.js:302
- src/styles/rooms.js:468
- src/styles/rooms.js:470
- src/styles/rooms.js:471
- src/styles/rooms.js:655
- src/styles/rooms.js:657
- src/styles/rooms.js:658
- src/styles/rooms.js:758 (--evcc-learning-warning-text)
- src/styles/rooms.js:882
- src/styles/rooms.js:890
- src/styles/rooms.js:891
- src/styles/setup.js:476
- src/styles/setup.js:477
- src/styles/setup.js:478
- src/styles/setup.js:563
- src/styles/shell.js:118
- src/styles/shell.js:132 (color)
- src/styles/theme-preview.js:455
- src/styles/theme-preview.js:456
- src/styles/theme-preview.js:457
- custom_components/eufy_vacuum/themes/preloaded.py:100
- custom_components/eufy_vacuum/themes/preloaded.py:101
- custom_components/eufy_vacuum/themes/preloaded.py:102
- custom_components/eufy_vacuum/themes/preloaded.py:139
- custom_components/eufy_vacuum/themes/preloaded.py:140
- custom_components/eufy_vacuum/themes/preloaded.py:141
- custom_components/eufy_vacuum/themes/preloaded.py:152
- custom_components/eufy_vacuum/themes/preloaded.py:153
- custom_components/eufy_vacuum/themes/preloaded.py:154
- custom_components/eufy_vacuum/themes/preloaded.py:168
- custom_components/eufy_vacuum/themes/preloaded.py:169
- custom_components/eufy_vacuum/themes/preloaded.py:182
- custom_components/eufy_vacuum/themes/preloaded.py:183
- custom_components/eufy_vacuum/themes/preloaded.py:184
- custom_components/eufy_vacuum/themes/preloaded.py:195
- custom_components/eufy_vacuum/themes/preloaded.py:224
- custom_components/eufy_vacuum/themes/preloaded.py:225
- custom_components/eufy_vacuum/themes/preloaded.py:226
- custom_components/eufy_vacuum/themes/preloaded.py:329
- custom_components/eufy_vacuum/themes/preloaded.py:404
- custom_components/eufy_vacuum/themes/preloaded.py:427
- custom_components/eufy_vacuum/themes/preloaded.py:450

**`--evcc-status-cleaning-bg`** — Status Cleaning BG · default —
- src/styles/rooms.js:265 (background)

**`--evcc-status-cleaning-border`** — Status Cleaning Border · default —
- src/styles/rooms.js:263

**`--evcc-status-cleaning-text`** — Status Cleaning Text · default —
- src/styles/rooms.js:278 (color)

**`--evcc-status-dot-charging`** — Status Dot Charging · default —
- src/styles/shell.js:121 (background)

**`--evcc-status-dot-cleaning`** — Status Dot Cleaning · default —
- src/styles/rooms.js:285 (background)
- src/styles/rooms.js:286
- src/styles/rooms.js:291
- src/styles/shell.js:116 (background)
- src/styles/theme-preview.js:410 (background)

**`--evcc-status-dot-docked`** — Status Dot Docked · default —
- src/styles/shell.js:117 (background)
- src/styles/theme-preview.js:414 (background)

**`--evcc-status-dot-error`** — Status Dot Error · default —
- src/styles/shell.js:119 (background)
- src/styles/theme-preview.js:418 (background)

**`--evcc-status-dot-idle`** — Status Dot Idle · default —
- src/styles/shell.js:112 (background)
- src/styles/theme-preview.js:406 (background)

**`--evcc-status-dot-offline`** — Status Dot Offline · default —
- src/styles/shell.js:122 (background)

**`--evcc-status-dot-paused`** — Status Dot Paused · default —
- src/styles/shell.js:120 (background)

**`--evcc-status-dot-returning`** — Status Dot Returning · default —
- src/styles/shell.js:118 (background)

**`--evcc-status-dot-shadow`** — Status Dot Shadow · default —
- src/styles/shell.js:113 (box-shadow)
- src/styles/theme-preview.js:401 (box-shadow)

**`--evcc-status-dot-unavailable`** — Status Dot Unavailable · default —
- src/styles/shell.js:123 (background)

**`--evcc-status-pulse-duration`** — Status Pulse Duration · default —
- src/styles/rooms.js:287
- src/styles/theme-preview.js:402

## Learning & Metrics  ·  37/37 consumed

**`--evcc-estimate-default-bg`** — Estimate Default BG · default src/styles/rooms.js:748
- src/styles/rooms.js:776 (background)
- src/styles/theme-preview.js:467 (background)

**`--evcc-estimate-default-border`** — Estimate Default Border · default src/styles/rooms.js:750
- src/styles/rooms.js:777 (border-color)
- src/styles/theme-preview.js:468 (border-color)

**`--evcc-estimate-default-text`** — Estimate Default Text · default src/styles/rooms.js:752
- src/styles/rooms.js:778 (color)
- src/styles/theme-preview.js:469 (color)

**`--evcc-estimate-learned-bg`** — Estimate Learned BG · default src/styles/rooms.js:741
- src/styles/rooms.js:770 (background)
- src/styles/theme-preview.js:473 (background)

**`--evcc-estimate-learned-border`** — Estimate Learned Border · default src/styles/rooms.js:743
- src/styles/rooms.js:771 (border-color)
- src/styles/theme-preview.js:474 (border-color)

**`--evcc-estimate-learned-text`** — Estimate Learned Text · default src/styles/rooms.js:745
- src/styles/rooms.js:772 (color)
- src/styles/theme-preview.js:475 (color)

**`--evcc-learning-anim-duration-fast`** — Learning Anim Duration Fast · default src/styles/learning.js:147
- src/styles/learning.js:296
- src/styles/learning.js:393
- src/styles/learning.js:394
- src/styles/learning.js:395
- src/styles/learning.js:396
- src/styles/learning.js:486
- src/styles/learning.js:487
- src/styles/learning.js:488
- src/styles/learning.js:489

**`--evcc-learning-anim-duration-normal`** — Learning Anim Duration Normal · default src/styles/learning.js:148
- src/styles/learning.js:239
- src/styles/learning.js:240
- src/styles/learning.js:241
- src/styles/learning.js:242
- src/styles/learning.js:288

**`--evcc-learning-anim-duration-slow`** — Learning Anim Duration Slow · default src/styles/learning.js:149
- src/styles/learning.js:289
- src/styles/learning.js:297

**`--evcc-learning-anim-ease`** — Learning Anim Ease · default src/styles/learning.js:150
- src/styles/learning.js:239
- src/styles/learning.js:240
- src/styles/learning.js:241
- src/styles/learning.js:242
- src/styles/learning.js:288
- src/styles/learning.js:289
- src/styles/learning.js:296
- src/styles/learning.js:297
- src/styles/learning.js:393
- src/styles/learning.js:394
- src/styles/learning.js:395
- src/styles/learning.js:396
- src/styles/learning.js:486
- src/styles/learning.js:487
- src/styles/learning.js:488
- src/styles/learning.js:489

**`--evcc-learning-chip-font-size`** — Learning Chip Font Size · default src/styles/learning.js:59
- src/styles/learning.js:480 (font-size)

**`--evcc-learning-chip-font-weight`** — Learning Chip Font Weight · default src/styles/learning.js:60
- src/styles/learning.js:481 (font-weight)

**`--evcc-learning-chip-radius`** — Learning Chip Radius · default src/styles/learning.js:56
- src/styles/learning.js:474 (border-radius)

**`--evcc-learning-confidence-high-bg`** — Learning Confidence High BG · default src/styles/learning.js:63
- src/styles/theme-preview.js:423

**`--evcc-learning-confidence-high-border`** — Learning Confidence High Border · default src/styles/learning.js:66
- src/styles/learning.js:499 (border-color)
- src/styles/theme-preview.js:424

**`--evcc-learning-confidence-high-gradient`** — Learning Confidence High Gradient · default src/styles/learning.js:72
- src/styles/learning.js:500 (background)

**`--evcc-learning-confidence-high-text`** — Learning Confidence High Text · default src/styles/learning.js:69
- src/styles/learning.js:501 (color)
- src/styles/theme-preview.js:425

**`--evcc-learning-confidence-low-border`** — Learning Confidence Low Border · default src/styles/learning.js:97
- src/styles/learning.js:511 (border-color)

**`--evcc-learning-confidence-low-gradient`** — Learning Confidence Low Gradient · default src/styles/learning.js:103
- src/styles/learning.js:512 (background)

**`--evcc-learning-confidence-low-text`** — Learning Confidence Low Text · default src/styles/learning.js:100
- src/styles/learning.js:513 (color)

**`--evcc-learning-confidence-medium-bg`** — Learning Confidence Medium BG · default src/styles/learning.js:80
- src/styles/theme-preview.js:430

**`--evcc-learning-confidence-medium-border`** — Learning Confidence Medium Border · default src/styles/learning.js:83
- src/styles/learning.js:505 (border-color)
- src/styles/theme-preview.js:431

**`--evcc-learning-confidence-medium-gradient`** — Learning Confidence Medium Gradient · default src/styles/learning.js:89
- src/styles/learning.js:506 (background)

**`--evcc-learning-confidence-medium-text`** — Learning Confidence Medium Text · default src/styles/learning.js:86
- src/styles/learning.js:507 (color)
- src/styles/theme-preview.js:432

**`--evcc-learning-confidence-neutral-border`** — Learning Confidence Neutral Border · default src/styles/learning.js:111
- src/styles/learning.js:475
- src/styles/learning.js:517 (border-color)

**`--evcc-learning-confidence-neutral-gradient`** — Learning Confidence Neutral Gradient · default src/styles/learning.js:117
- src/styles/learning.js:477 (background)
- src/styles/learning.js:518 (background)

**`--evcc-learning-confidence-neutral-text`** — Learning Confidence Neutral Text · default src/styles/learning.js:114
- src/styles/learning.js:478 (color)
- src/styles/learning.js:519 (color)

**`--evcc-learning-note-text`** — Learning Note Text · default src/styles/rooms.js:755
- src/styles/rooms.js:808 (color)
- src/styles/theme-preview.js:491 (color)

**`--evcc-learning-panel-bg`** — Learning Panel BG · default src/styles/learning.js:38
- src/styles/learning.js:233 (background)
- src/styles/theme-preview.js:485

**`--evcc-learning-panel-border`** — Learning Panel Border · default src/styles/learning.js:41
- src/styles/learning.js:232
- src/styles/theme-preview.js:486 (border-color)

**`--evcc-learning-panel-shadow`** — Learning Panel Shadow · default src/styles/learning.js:44
- src/styles/learning.js:179
- src/styles/learning.js:184
- src/styles/learning.js:189
- src/styles/learning.js:234 (box-shadow)
- src/styles/theme-preview.js:487 (box-shadow)

**`--evcc-learning-reanchor-border`** — Learning Reanchor Border · default src/styles/learning.js:156
- src/styles/learning.js:290 (border-color)

**`--evcc-learning-reanchor-highlight`** — Learning Reanchor Highlight · default src/styles/learning.js:153
- src/styles/theme-preview.js:482

**`--evcc-learning-text-muted`** — Learning Text Muted · default src/styles/learning.js:53
- src/styles/learning.js:436 (color)

**`--evcc-learning-text-primary`** — Learning Text Primary · default src/styles/learning.js:47
- src/styles/learning.js:236 (color)
- src/styles/learning.js:270 (color)
- src/styles/learning.js:412 (color)

**`--evcc-learning-text-secondary`** — Learning Text Secondary · default src/styles/learning.js:50
- src/styles/learning.js:279 (color)
- src/styles/learning.js:347 (color)
- src/styles/learning.js:373 (color)
- src/styles/learning.js:424 (color)
- src/styles/theme-preview.js:491

**`--evcc-learning-warning-text`** — Learning Warning Text · default src/styles/rooms.js:757
- src/styles/rooms.js:812 (color)

## Modals & Overlays  ·  36/36 consumed

**`--evcc-modal-accent`** — Modal Accent · default src/styles/index.js:192
- src/styles/dialog.js:44 (border-color)
- src/styles/index.js:307 (--evcc-accent)
- src/styles/index.js:524
- src/styles/index.js:529
- src/styles/index.js:534
- src/styles/modals.js:196
- src/styles/modals.js:201
- src/styles/modals.js:206
- src/styles/modals.js:214
- src/styles/modals.js:219
- src/styles/modals.js:223
- src/styles/theme-preview.js:530
- src/styles/theme-preview.js:531
- src/styles/theme-preview.js:532

**`--evcc-modal-accent-bg`** — Modal Accent BG · default src/styles/index.js:194
- src/styles/index.js:204 (--evcc-modal-chip-active-bg)
- src/styles/index.js:523
- src/styles/modals.js:195
- src/styles/theme-preview.js:530 (background)
- custom_components/eufy_vacuum/themes/preloaded.py:206

**`--evcc-modal-accent-border`** — Modal Accent Border · default src/styles/index.js:195
- src/styles/index.js:205 (--evcc-modal-chip-active-border)
- src/styles/index.js:533
- src/styles/modals.js:205
- src/styles/theme-preview.js:531 (border-color)
- custom_components/eufy_vacuum/themes/preloaded.py:207

**`--evcc-modal-accent-text`** — Modal Accent Text · default src/styles/index.js:193
- src/styles/index.js:206 (--evcc-modal-chip-active-text)
- src/styles/index.js:528
- src/styles/modals.js:200
- src/styles/modals.js:218
- src/styles/theme-preview.js:532 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:208

**`--evcc-modal-backdrop-bg`** — Modal Backdrop BG · default src/styles/index.js:169, src/styles/index.js:663
- src/styles/index.js:219 (background)
- src/styles/index.js:742 (background)
- src/styles/modals.js:77 (background)
- src/styles/modals.js:400 (background)
- src/styles/theme-preview.js:505 (background)

**`--evcc-modal-backdrop-blur`** — Modal Backdrop Blur · default —
- src/styles/index.js:223
- src/styles/modals.js:81
- src/styles/theme-preview.js:506

**`--evcc-modal-bg`** — Modal BG · default src/styles/index.js:168, src/styles/index.js:662
- src/styles/index.js:247 (background)
- src/styles/index.js:691 (background)
- src/styles/index.js:797 (background)
- src/styles/index.js:806 (background)
- src/styles/modals.js:96 (background)
- src/styles/modals.js:386 (background)
- src/styles/theme-preview.js:518 (background)

**`--evcc-modal-border`** — Modal Border · default src/styles/index.js:170, src/styles/index.js:664
- src/styles/index.js:251
- src/styles/index.js:695
- src/styles/modals.js:100
- src/styles/modals.js:284
- src/styles/modals.js:390
- src/styles/theme-preview.js:519

**`--evcc-modal-border-default`** — Modal Border Default · default src/styles/index.js:171, src/styles/index.js:665
- src/styles/index.js:283 (--evcc-border-default)
- src/styles/index.js:716 (--evcc-border-default)

**`--evcc-modal-border-strong`** — Modal Border Strong · default src/styles/index.js:172, src/styles/index.js:666
- src/styles/dialog.js:37
- src/styles/index.js:291 (--evcc-border-strong)
- src/styles/index.js:724 (--evcc-border-strong)
- src/styles/modals.js:368

**`--evcc-modal-border-subtle`** — Modal Border Subtle · default src/styles/index.js:173, src/styles/index.js:667
- src/styles/index.js:287 (--evcc-border-subtle)
- src/styles/index.js:429
- src/styles/index.js:571
- src/styles/index.js:586
- src/styles/index.js:720 (--evcc-border-subtle)
- src/styles/index.js:808
- src/styles/modals.js:131
- src/styles/modals.js:180
- src/styles/room-estimate.js:38
- src/styles/room-estimate.js:60

**`--evcc-modal-chip-active-bg`** — Modal Chip Active BG · default src/styles/index.js:204
- src/styles/index.js:522 (background)
- src/styles/modals.js:194 (background)

**`--evcc-modal-chip-active-border`** — Modal Chip Active Border · default src/styles/index.js:205
- src/styles/index.js:532 (border-color)
- src/styles/modals.js:204 (border-color)

**`--evcc-modal-chip-active-text`** — Modal Chip Active Text · default src/styles/index.js:206
- src/styles/index.js:527 (color)
- src/styles/modals.js:199 (color)

**`--evcc-modal-chip-bg`** — Modal Chip BG · default src/styles/index.js:198, src/styles/index.js:681
- src/styles/index.js:388 (--evcc-chip-bg)
- src/styles/index.js:541 (background)
- src/styles/modals.js:359 (background)

**`--evcc-modal-chip-border`** — Modal Chip Border · default src/styles/index.js:199, src/styles/index.js:682
- src/styles/index.js:384 (--evcc-chip-border)
- src/styles/index.js:550 (border-color)
- src/styles/modals.js:367 (border-color)

**`--evcc-modal-chip-hover-bg`** — Modal Chip Hover BG · default src/styles/index.js:201, src/styles/index.js:684
- src/styles/index.js:402 (--evcc-chip-hover-bg)
- src/styles/modals.js:213 (background)

**`--evcc-modal-chip-hover-border`** — Modal Chip Hover Border · default src/styles/index.js:202, src/styles/index.js:685
- src/styles/index.js:410 (--evcc-chip-hover-border)
- src/styles/modals.js:222 (border-color)

**`--evcc-modal-chip-hover-text`** — Modal Chip Hover Text · default src/styles/index.js:203, src/styles/index.js:686
- src/styles/index.js:406 (--evcc-chip-hover-text)
- src/styles/modals.js:217 (color)

**`--evcc-modal-chip-text`** — Modal Chip Text · default src/styles/index.js:200, src/styles/index.js:683
- src/styles/index.js:392 (--evcc-chip-text)
- src/styles/index.js:545 (color)
- src/styles/modals.js:363 (color)

**`--evcc-modal-footer-bg`** — Modal Footer BG · default src/styles/index.js:184, src/styles/index.js:675
- src/styles/index.js:575 (background)
- src/styles/modals.js:184 (background)

**`--evcc-modal-header-bg`** — Modal Header BG · default src/styles/index.js:183, src/styles/index.js:674
- src/styles/index.js:434 (background)
- src/styles/modals.js:136 (background)

**`--evcc-modal-input-bg`** — Modal Input BG · default src/styles/index.js:179, src/styles/index.js:672
- src/styles/dialog.js:36 (background)
- src/styles/index.js:274 (--evcc-surface-input)
- src/styles/index.js:711 (--evcc-surface-input)

**`--evcc-modal-padding`** — Modal Padding · default —
- src/styles/index.js:427 (padding)
- src/styles/index.js:457 (padding)
- src/styles/index.js:569 (padding)
- src/styles/modals.js:129 (padding)
- src/styles/modals.js:160 (padding)
- src/styles/modals.js:178 (padding)
- src/styles/theme-preview.js:517 (padding)

**`--evcc-modal-radius`** — Modal Radius · default —
- src/styles/index.js:255 (border-radius)
- src/styles/modals.js:103 (border-radius)
- src/styles/modals.js:412 (border-radius)
- src/styles/theme-preview.js:520 (border-radius)

**`--evcc-modal-section-gap`** — Modal Section Gap · default —
- src/styles/index.js:460 (gap)
- src/styles/modals.js:163 (gap)

**`--evcc-modal-shadow`** — Modal Shadow · default —
- src/styles/index.js:258 (box-shadow)
- src/styles/index.js:699 (box-shadow)
- src/styles/modals.js:106 (box-shadow)
- src/styles/modals.js:394 (box-shadow)
- src/styles/theme-preview.js:521 (box-shadow)

**`--evcc-modal-surface-input`** — Modal Surface Input · default src/styles/index.js:177, src/styles/index.js:670
- src/styles/index.js:275
- src/styles/index.js:712

**`--evcc-modal-surface-panel`** — Modal Surface Panel · default src/styles/index.js:176, src/styles/index.js:669
- src/styles/index.js:279 (--evcc-surface-panel)
- src/styles/index.js:707 (--evcc-surface-panel)
- src/styles/room-estimate.js:40
- src/styles/room-estimate.js:62

**`--evcc-modal-surface-section`** — Modal Surface Section · default src/styles/index.js:178, src/styles/index.js:671
- src/styles/modals.js:165 (background)

**`--evcc-modal-text-muted`** — Modal Text Muted · default src/styles/index.js:189, src/styles/index.js:679
- src/styles/index.js:303 (--evcc-text-muted)
- src/styles/index.js:511 (color)
- src/styles/index.js:542
- src/styles/index.js:607 (color)
- src/styles/index.js:736 (--evcc-text-muted)
- src/styles/modals.js:240 (color)
- src/styles/modals.js:309 (color)
- src/styles/modals.js:360

**`--evcc-modal-text-primary`** — Modal Text Primary · default src/styles/index.js:187, src/styles/index.js:677
- src/styles/dialog.js:24 (color)
- src/styles/dialog.js:38 (color)
- src/styles/index.js:234 (color)
- src/styles/index.js:262 (color)
- src/styles/index.js:295 (--evcc-text-primary)
- src/styles/index.js:442 (color)
- src/styles/index.js:703 (color)
- src/styles/index.js:728 (--evcc-text-primary)
- src/styles/modals.js:117 (color)
- src/styles/modals.js:144 (color)
- src/styles/room-estimate.js:45 (color)

**`--evcc-modal-text-secondary`** — Modal Text Secondary · default src/styles/index.js:188, src/styles/index.js:678
- src/styles/index.js:299 (--evcc-text-secondary)
- src/styles/index.js:594 (color)
- src/styles/index.js:732 (--evcc-text-secondary)
- src/styles/modals.js:364
- src/styles/room-estimate.js:17 (color)
- src/styles/room-estimate.js:41 (color)
- src/styles/room-estimate.js:61 (color)

**`--evcc-modal-warning-bg`** — Modal Warning BG · default src/styles/index.js:209
- src/styles/index.js:635 (background)
- src/styles/modals.js:258 (background)
- src/styles/theme-preview.js:455 (background)

**`--evcc-modal-warning-border`** — Modal Warning Border · default src/styles/index.js:210
- src/styles/index.js:551
- src/styles/index.js:639
- src/styles/modals.js:262
- src/styles/theme-preview.js:456 (border-color)

**`--evcc-modal-warning-text`** — Modal Warning Text · default src/styles/index.js:211
- src/styles/index.js:546
- src/styles/index.js:636
- src/styles/index.js:640
- src/styles/index.js:643 (color)
- src/styles/modals.js:259
- src/styles/modals.js:263
- src/styles/modals.js:266 (color)
- src/styles/theme-preview.js:457 (color)

## Animal Companion  ·  0/14 consumed

**`--evcc-animal-eye-good`** — Eye — Good (>50% battery) · default —
- _no consumer — only seeded_

**`--evcc-animal-eye-mid`** — Eye — Mid (25–50%) · default —
- _no consumer — only seeded_

**`--evcc-animal-eye-warn`** — Eye — Warn (15–25%) · default —
- _no consumer — only seeded_

**`--evcc-animal-eye-low`** — Eye — Low (≤15%) · default —
- _no consumer — only seeded_

**`--evcc-animal-eye-charging`** — Eye — Charging (pulses) · default —
- _no consumer — only seeded_

**`--evcc-animal-fur`** — Fur (all animals) · default —
- _no consumer — only seeded_

**`--evcc-animal-fur-shadow`** — Fur Shadow (all) · default —
- _no consumer — only seeded_

**`--evcc-animal-fur-highlight`** — Fur Highlight (all) · default —
- _no consumer — only seeded_

**`--evcc-animal-eye`** — Eye Base (all) · default —
- _no consumer — only seeded_

**`--evcc-animal-pupil`** — Pupil (all) · default —
- _no consumer — only seeded_

**`--evcc-animal-nose`** — Nose (all) · default —
- _no consumer — only seeded_

**`--evcc-animal-whisker`** — Whisker (all) · default —
- _no consumer — only seeded_

**`--evcc-animal-ear-inner`** — Ear Inner (all) · default —
- _no consumer — only seeded_

**`--evcc-animal-white-tip`** — White Tip / Accent (all) · default —
- _no consumer — only seeded_

## Animal Companion — Cat  ·  0/14 consumed

*(template — Dog/Raccoon/Parrot/Snake mirror it; consumed dynamically in animal-svg/)*

**`--evcc-animal-cat-eye-good`** — Eye — Good · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-eye-mid`** — Eye — Mid · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-eye-warn`** — Eye — Warn · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-eye-low`** — Eye — Low · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-eye-charging`** — Eye — Charging · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-fur`** — Fur · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-fur-shadow`** — Fur Shadow · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-fur-highlight`** — Fur Highlight · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-eye`** — Eye Base · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-pupil`** — Pupil · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-nose`** — Nose · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-whisker`** — Whisker · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-ear-inner`** — Ear Inner · default —
- _no consumer — only seeded_

**`--evcc-animal-cat-white-tip`** — White Tip / Accent · default —
- _no consumer — only seeded_

## Shared Foundations  ·  15/15 consumed

**`--evcc-font-family`** — Font Family · default —
- src/styles/index.js:231 (font-family)
- src/styles/index.js:914 (font-family)
- src/styles/theme-preview.js:121 (font-family)

**`--evcc-gap`** — Gap · default src/styles/foundation.js:180
- src/styles/foundation.js:269 (gap)
- src/styles/shell.js:67 (gap)
- src/styles/theme-preview.js:79 (gap)
- src/styles/theme-preview.js:92 (gap)
- src/styles/theme-preview.js:327 (gap)

**`--evcc-grid-gap`** — Grid Gap · default src/styles/layout.js:63
- src/styles/base-station.js:7 (gap)
- src/styles/base-station.js:12 (gap)
- src/styles/layout.js:64 (--evcc-room-grid-gap)
- src/styles/layout.js:78
- src/styles/maintenance.js:125 (gap)
- src/styles/maintenance.js:130 (gap)
- src/styles/mapping-review.js:7 (gap)
- src/styles/mapping-review.js:20 (gap)
- src/styles/metrics.js:7 (gap)
- src/styles/metrics.js:12 (gap)
- src/styles/review.js:7 (gap)
- src/styles/review.js:12 (gap)

**`--evcc-hover-lift`** — Hover Lift · default —
- src/styles/order.js:121
- src/styles/rooms.js:345
- src/styles/rooms.js:640
- src/styles/theme-preview.js:229

**`--evcc-pad`** — Pad · default src/styles/foundation.js:181
- src/styles/foundation.js:270 (padding)
- src/styles/foundation.js:270
- src/styles/foundation.js:326 (padding)
- src/styles/theme-preview.js:182 (padding)

**`--evcc-press-scale`** — Press Scale · default —
- src/styles/rooms.js:650

**`--evcc-radius-card`** — Radius Card · default src/styles/foundation.js:171
- src/cards/dashboard-card.js:985 (--radius)
- src/room-card.js:375 (--radius)
- src/styles/external-jobs.js:69 (border-radius)
- src/styles/external-jobs.js:142 (border-radius)
- src/styles/foundation.js:252 (border-radius)
- src/styles/learning.js:581 (border-radius)
- src/styles/map.js:73 (border-radius)
- src/styles/map.js:447 (border-radius)
- src/styles/map.js:879 (border-radius)
- src/styles/rooms.js:319 (border-radius)
- src/styles/shell.js:48 (border-radius)
- src/styles/shell.js:226 (border-radius)
- src/styles/theme-preview.js:36 (border-radius)
- src/styles/theme-preview.js:97 (border-radius)
- src/styles/theme-preview.js:174 (border-radius)
- src/styles/theme-preview.js:498 (border-radius)
- src/styles/theme-preview.js:563 (border-radius)
- src/styles/theme.js:297 (border-radius)
- src/styles/theme.js:553 (border-radius)
- src/styles/theme.js:573 (border-radius)
- src/styles/theme.js:632 (border-radius)

**`--evcc-radius-chip`** — Radius Chip · default src/styles/foundation.js:173
- src/styles/external-jobs.js:51 (border-radius)
- src/styles/foundation.js:308 (border-radius)
- src/styles/learning.js:57 (--evcc-learning-chip-radius)
- src/styles/order.js:59 (border-radius)
- src/styles/rooms.js:553 (border-radius)
- src/styles/shell.js:173 (border-radius)
- src/styles/shell.js:247 (border-radius)
- src/styles/shell.js:315 (border-radius)
- src/styles/theme-preview.js:163 (border-radius)
- src/styles/theme-preview.js:343 (border-radius)

**`--evcc-radius-inner`** — Radius Inner · default src/styles/foundation.js:172
- src/styles/base-station.js:21 (border-radius)
- src/styles/base-station.js:65 (border-radius)
- src/styles/external-jobs.js:24 (border-radius)
- src/styles/external-jobs.js:83 (border-radius)
- src/styles/external-jobs.js:99 (border-radius)
- src/styles/external-jobs.js:110 (border-radius)
- src/styles/external-jobs.js:121 (border-radius)
- src/styles/external-jobs.js:131 (border-radius)
- src/styles/external-jobs.js:152 (border-radius)
- src/styles/index.js:484 (border-radius)
- src/styles/maintenance.js:23 (border-radius)
- src/styles/maintenance.js:96 (border-radius)
- src/styles/maintenance.js:139 (border-radius)
- src/styles/maintenance.js:201 (border-radius)
- src/styles/maintenance.js:263 (border-radius)
- src/styles/maintenance.js:375 (border-radius)
- src/styles/maintenance.js:418 (border-radius)
- src/styles/mapping-review.js:29 (border-radius)
- src/styles/mapping-review.js:117 (border-radius)
- src/styles/metrics.js:21 (border-radius)
- src/styles/metrics.js:66 (border-radius)
- src/styles/metrics.js:159 (border-radius)
- src/styles/metrics.js:194 (border-radius)
- src/styles/metrics.js:253 (border-radius)
- src/styles/review.js:21 (border-radius)
- src/styles/review.js:88 (border-radius)
- src/styles/review.js:103 (border-radius)
- src/styles/review.js:124 (border-radius)
- src/styles/review.js:212 (border-radius)
- src/styles/review.js:223 (border-radius)
- src/styles/rooms.js:136 (border-radius)
- src/styles/rooms.js:149 (border-radius)
- src/styles/rooms.js:162 (border-radius)
- src/styles/rooms.js:1152 (border-radius)
- src/styles/run-profiles.js:52 (border-radius)
- src/styles/run-profiles.js:82 (border-radius)
- src/styles/saved-zones.js:76 (border-radius)
- src/styles/saved-zones.js:126 (border-radius)
- src/styles/saved-zones.js:212 (border-radius)
- src/styles/theme-preview.js:193 (border-radius)
- src/styles/theme-preview.js:205 (border-radius)
- src/styles/theme-preview.js:443 (border-radius)
- src/styles/theme.js:47 (border-radius)
- src/styles/theme.js:135 (border-radius)
- src/styles/theme.js:241 (border-radius)
- src/styles/theme.js:334 (border-radius)
- src/styles/theme.js:484 (border-radius)
- src/styles/theme.js:503 (border-radius)
- src/styles/theme.js:654 (border-radius)
- src/styles/theme.js:988 (border-radius)

**`--evcc-radius-panel`** — Radius Panel · default —
- src/styles/learning.js:231 (border-radius)
- src/styles/room-access.js:14 (border-radius)
- src/styles/rooms.js:190 (border-radius)
- src/styles/rooms.js:262 (border-radius)
- src/styles/rooms.js:729 (border-radius)
- src/styles/run-profiles.js:22 (border-radius)
- src/styles/saved-zones.js:12 (border-radius)
- src/styles/theme-preview.js:184 (border-radius)

**`--evcc-section-gap`** — Section Gap · default —
- src/styles/rooms.js:47 (gap)
- src/styles/theme-preview.js:536 (gap)

**`--evcc-space-lg`** — Space Lg · default src/styles/foundation.js:178
- src/styles/foundation.js:181 (--evcc-pad)
- src/styles/shell.js:345 (padding)

**`--evcc-space-md`** — Space Md · default src/styles/foundation.js:177
- src/styles/foundation.js:180 (--evcc-gap)
- src/styles/rooms.js:48 (padding-bottom)
- src/styles/rooms.js:50 (margin-bottom)
- src/styles/rooms.js:57 (gap)
- src/styles/rooms.js:261 (margin-bottom)
- src/styles/rooms.js:1155 (margin-bottom)
- src/styles/theme.js:13 (gap)
- src/styles/theme.js:21 (gap)

**`--evcc-space-sm`** — Space Sm · default src/styles/foundation.js:176
- src/styles/rooms.js:799 (margin-top)
- src/styles/rooms.js:1150 (gap)

**`--evcc-transition-normal`** — Transition Normal · default src/styles/foundation.js:218, src/styles/index.js:310
- src/styles/base-station.js:97
- src/styles/base-station.js:98
- src/styles/foundation.js:57
- src/styles/foundation.js:58
- src/styles/foundation.js:59
- src/styles/foundation.js:60
- src/styles/maintenance.js:279
- src/styles/maintenance.js:280
- src/styles/order.js:93
- src/styles/order.js:94
- src/styles/order.js:95
- src/styles/order.js:114
- src/styles/order.js:115
- src/styles/order.js:116
- src/styles/order.js:117
- src/styles/room-access.js:31
- src/styles/room-access.js:32
- src/styles/room-access.js:33
- src/styles/room-access.js:34
- src/styles/rooms.js:324
- src/styles/rooms.js:325
- src/styles/rooms.js:326
- src/styles/rooms.js:327
- src/styles/rooms.js:631
- src/styles/rooms.js:632
- src/styles/rooms.js:633
- src/styles/rooms.js:634
- src/styles/rooms.js:635
- src/styles/rooms.js:636
- src/styles/shell.js:179
- src/styles/shell.js:180
- src/styles/shell.js:253
- src/styles/shell.js:254
- src/styles/shell.js:321
- src/styles/shell.js:322
- src/styles/theme.js:50 (transition)
- src/styles/theme.js:243 (transition)

---

## Tokens with no consumer  ·  134

Three kinds — only the last is a concern:

### Consumed dynamically — floor-texture presets  ·  38

Built at runtime as `var(--evcc-floor-${floorType}-…)` in `src/renderers/floor-texture-surface.js`. Working as intended.

`--evcc-floor-tile-base`, `--evcc-floor-tile-grout`, `--evcc-floor-tile-accent`, `--evcc-floor-tile-opacity-card`, `--evcc-floor-tile-face-opacity`, `--evcc-floor-tile-grout-opacity`, `--evcc-floor-tile-line-opacity`, `--evcc-floor-wood-base`, `--evcc-floor-wood-accent`, `--evcc-floor-wood-opacity-card`, `--evcc-floor-wood-depth-opacity`, `--evcc-floor-wood-grain-opacity`, `--evcc-floor-wood-seam-opacity`, `--evcc-floor-marble-base`, `--evcc-floor-marble-micro`, `--evcc-floor-marble-opacity-card`, `--evcc-floor-marble-base-opacity`, `--evcc-floor-marble-micro-opacity`, `--evcc-floor-concrete-base`, `--evcc-floor-concrete-accent`, `--evcc-floor-concrete-opacity-card`, `--evcc-floor-concrete-broad-opacity`, `--evcc-floor-concrete-micro-opacity`, `--evcc-floor-carpet-low-base`, `--evcc-floor-carpet-low-weave`, `--evcc-floor-carpet-low-opacity-card`, `--evcc-floor-carpet-low-base-opacity`, `--evcc-floor-carpet-low-weave-opacity`, `--evcc-floor-carpet-high-base`, `--evcc-floor-carpet-high-weave`, `--evcc-floor-carpet-high-opacity-card`, `--evcc-floor-carpet-high-base-opacity`, `--evcc-floor-carpet-high-weave-opacity`, `--evcc-floor-granite-light-base`, `--evcc-floor-granite-light-aggregate`, `--evcc-floor-granite-light-opacity-card`, `--evcc-floor-granite-light-base-opacity`, `--evcc-floor-granite-light-aggregate-opacity`

### Per-animal palette (consumed dynamically in animal-svg/)  ·  84

The `--evcc-animal-*` tokens are referenced via dynamic `var()` in the shipped animal-svg module; per-animal `--evcc-animal-<name>-*` feed the active companion. Expected.

`--evcc-animal-eye-good`, `--evcc-animal-eye-mid`, `--evcc-animal-eye-warn`, `--evcc-animal-eye-low`, `--evcc-animal-eye-charging`, `--evcc-animal-fur`, `--evcc-animal-fur-shadow`, `--evcc-animal-fur-highlight`, `--evcc-animal-eye`, `--evcc-animal-pupil`, `--evcc-animal-nose`, `--evcc-animal-whisker`, `--evcc-animal-ear-inner`, `--evcc-animal-white-tip`, `--evcc-animal-cat-eye-good`, `--evcc-animal-cat-eye-mid`, `--evcc-animal-cat-eye-warn`, `--evcc-animal-cat-eye-low`, `--evcc-animal-cat-eye-charging`, `--evcc-animal-cat-fur`, `--evcc-animal-cat-fur-shadow`, `--evcc-animal-cat-fur-highlight`, `--evcc-animal-cat-eye`, `--evcc-animal-cat-pupil`, `--evcc-animal-cat-nose`, `--evcc-animal-cat-whisker`, `--evcc-animal-cat-ear-inner`, `--evcc-animal-cat-white-tip`, `--evcc-animal-dog-eye-good`, `--evcc-animal-dog-eye-mid`, `--evcc-animal-dog-eye-warn`, `--evcc-animal-dog-eye-low`, `--evcc-animal-dog-eye-charging`, `--evcc-animal-dog-fur`, `--evcc-animal-dog-fur-shadow`, `--evcc-animal-dog-fur-highlight`, `--evcc-animal-dog-eye`, `--evcc-animal-dog-pupil`, `--evcc-animal-dog-nose`, `--evcc-animal-dog-whisker`, `--evcc-animal-dog-ear-inner`, `--evcc-animal-dog-white-tip`, `--evcc-animal-raccoon-eye-good`, `--evcc-animal-raccoon-eye-mid`, `--evcc-animal-raccoon-eye-warn`, `--evcc-animal-raccoon-eye-low`, `--evcc-animal-raccoon-eye-charging`, `--evcc-animal-raccoon-fur`, `--evcc-animal-raccoon-fur-shadow`, `--evcc-animal-raccoon-fur-highlight`, `--evcc-animal-raccoon-eye`, `--evcc-animal-raccoon-pupil`, `--evcc-animal-raccoon-nose`, `--evcc-animal-raccoon-whisker`, `--evcc-animal-raccoon-ear-inner`, `--evcc-animal-raccoon-white-tip`, `--evcc-animal-parrot-eye-good`, `--evcc-animal-parrot-eye-mid`, `--evcc-animal-parrot-eye-warn`, `--evcc-animal-parrot-eye-low`, `--evcc-animal-parrot-eye-charging`, `--evcc-animal-parrot-fur`, `--evcc-animal-parrot-fur-shadow`, `--evcc-animal-parrot-fur-highlight`, `--evcc-animal-parrot-eye`, `--evcc-animal-parrot-pupil`, `--evcc-animal-parrot-nose`, `--evcc-animal-parrot-whisker`, `--evcc-animal-parrot-ear-inner`, `--evcc-animal-parrot-white-tip`, `--evcc-animal-snake-eye-good`, `--evcc-animal-snake-eye-mid`, `--evcc-animal-snake-eye-warn`, `--evcc-animal-snake-eye-low`, `--evcc-animal-snake-eye-charging`, `--evcc-animal-snake-fur`, `--evcc-animal-snake-fur-shadow`, `--evcc-animal-snake-fur-highlight`, `--evcc-animal-snake-eye`, `--evcc-animal-snake-pupil`, `--evcc-animal-snake-nose`, `--evcc-animal-snake-whisker`, `--evcc-animal-snake-ear-inner`, `--evcc-animal-snake-white-tip`

### Truly dead — no `var()` anywhere  ·  12

Seeded + exposed in the editor but nothing reads them — no-op editor knobs (wire them up or drop them).

- **Map** (12): `--evcc-room-fill-1`, `--evcc-room-fill-2`, `--evcc-room-fill-3`, `--evcc-room-fill-4`, `--evcc-room-fill-5`, `--evcc-room-fill-6`, `--evcc-room-fill-7`, `--evcc-room-fill-8`, `--evcc-room-fill-9`, `--evcc-room-fill-10`, `--evcc-room-fill-11`, `--evcc-room-fill-12`

---

## var() → non-catalog tokens  ·  11

Used in CSS but not in the editor registry (dynamic fragments or intentional internals like `--evcc-grp`).

- `--evcc-border` — src/styles/map.js:370
- `--evcc-text` — src/styles/map.js:373
- `--evcc-map-rotation` — src/styles/map.js:562, src/styles/map.js:627, src/styles/map.js:784, src/styles/map.js:821, src/styles/map.js:853
- `--evcc-map-ov-savedzone` — src/styles/map.js:803, src/styles/map.js:805, src/styles/map.js:834
- `--evcc-map-ov-savedzone-text` — src/styles/map.js:824
- `--evcc-grp` — src/styles/map.js:1267
- `--evcc-on-accent` — src/styles/saved-zones.js:58
- `--evcc-danger` — src/styles/saved-zones.js:199
- `--evcc-surface-default` — src/styles/setup.js:690
- `--evcc-shadow-overlay` — src/styles/shell.js:227
- `--evcc-animal-X` — custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js:289

---

## dynamic var(--evcc-…${…}) sites  ·  3

- src/renderers/floor-texture-surface.js:99
- custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js:316
- custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js:317

