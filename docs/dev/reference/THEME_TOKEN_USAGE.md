<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Source of truth: src/theme-tokens/ (the editor registry) + the card CSS.
     Regenerate after any token add/remove/rename:  node scripts/gen-theme-token-docs.mjs -->

# Theme Token CSS-Usage Trace

> Generated reference — part of the [Theme System](../20-theme-system.md) docs. Companion: [Theme Token Map](THEME_TOKEN_MAP.md).

For each catalog token (`--evcc-*`): its **default** declaration, every real **consumer** `var()` (CSS property + file:line), and JS `setProperty` apply sites. Multiline-aware (handles `var(` wrapped across lines); scans `src/`, the `animal-svg/` module, and the Python preloaded themes. The self-referential seed (`--evcc-x: var(--evcc-x, fallback)`) is the default, not a use.

- Catalog **377** · consumer `var()` uses **1850** · with a consumer **261**, with none **116**
- `var()` → non-catalog tokens **2** · dynamic `var(--evcc-…${…})` sites **3**

---

## App Shell & Typography  ·  7/7 consumed

**`--evcc-accent`** — Accent · default src/styles/foundation.js:134, src/styles/index.js:218
- src/room-card.js:336 (--accent)
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
- src/styles/foundation.js:75
- src/styles/foundation.js:76
- src/styles/foundation.js:78
- src/styles/foundation.js:169 (--evcc-color-docked)
- src/styles/foundation.js:296
- src/styles/foundation.js:297 (color)
- src/styles/index.js:220
- src/styles/index.js:375
- src/styles/index.js:380
- src/styles/index.js:385
- src/styles/index.js:679
- src/styles/index.js:680
- src/styles/index.js:686 (background)
- src/styles/index.js:750
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
- src/styles/map.js:266 (background)
- src/styles/map.js:384 (background)
- src/styles/map.js:585 (border-color)
- src/styles/map.js:590 (border-color)
- src/styles/map.js:604
- src/styles/map.js:715
- src/styles/map.js:717 (color)
- src/styles/map.js:719
- src/styles/map.js:725
- src/styles/map.js:726 (color)
- src/styles/map.js:902
- src/styles/map.js:903 (color)
- src/styles/map.js:905
- src/styles/map.js:1019 (accent-color)
- src/styles/mapping-review.js:267
- src/styles/mapping-review.js:268 (color)
- src/styles/mapping-review.js:269
- src/styles/mapping-review.js:273
- src/styles/metrics.js:164 (border-color)
- src/styles/mobile.js:158 (color)
- src/styles/mobile.js:258 (color)
- src/styles/mobile.js:260
- src/styles/modals.js:196
- src/styles/modals.js:201
- src/styles/modals.js:206
- src/styles/modals.js:214
- src/styles/modals.js:219
- src/styles/modals.js:223
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
- src/styles/rooms.js:297
- src/styles/rooms.js:301
- src/styles/rooms.js:305
- src/styles/rooms.js:315
- src/styles/rooms.js:320
- src/styles/rooms.js:360
- src/styles/rooms.js:548
- src/styles/rooms.js:549 (--evcc-chip-text)
- src/styles/rooms.js:550
- src/styles/rooms.js:599
- src/styles/rooms.js:698
- src/styles/rooms.js:700
- src/styles/rooms.js:825
- src/styles/rooms.js:826
- src/styles/rooms.js:899
- src/styles/rooms.js:921
- src/styles/rooms.js:940
- src/styles/rooms.js:941
- src/styles/rooms.js:1029
- src/styles/rooms.js:1064
- src/styles/rooms.js:1065
- src/styles/setup.js:56 (background)
- src/styles/setup.js:103 (background)
- src/styles/setup.js:153
- src/styles/setup.js:154
- src/styles/setup.js:155 (color)
- src/styles/setup.js:411
- src/styles/setup.js:412 (border-color)
- src/styles/setup.js:413 (color)
- src/styles/shell.js:117
- src/styles/shell.js:120
- src/styles/shell.js:170
- src/styles/shell.js:171 (color)
- src/styles/shell.js:267
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
- src/styles/theme.js:131 (border-color)
- src/styles/theme.js:134
- src/styles/theme.js:167 (background)
- src/styles/theme.js:302 (border-color)
- src/styles/theme.js:335 (border-color)
- src/styles/theme.js:338
- src/styles/theme.js:446
- src/styles/theme.js:633
- src/styles/theme.js:656
- src/styles/theme.js:718
- src/styles/theme.js:741
- src/styles/theme.js:764 (border-color)
- custom_components/eufy_vacuum/themes/preloaded.py:78
- custom_components/eufy_vacuum/themes/preloaded.py:79
- custom_components/eufy_vacuum/themes/preloaded.py:80
- custom_components/eufy_vacuum/themes/preloaded.py:102
- custom_components/eufy_vacuum/themes/preloaded.py:103
- custom_components/eufy_vacuum/themes/preloaded.py:104
- custom_components/eufy_vacuum/themes/preloaded.py:109
- custom_components/eufy_vacuum/themes/preloaded.py:110
- custom_components/eufy_vacuum/themes/preloaded.py:111
- custom_components/eufy_vacuum/themes/preloaded.py:112
- custom_components/eufy_vacuum/themes/preloaded.py:113
- custom_components/eufy_vacuum/themes/preloaded.py:114
- custom_components/eufy_vacuum/themes/preloaded.py:121
- custom_components/eufy_vacuum/themes/preloaded.py:122
- custom_components/eufy_vacuum/themes/preloaded.py:123
- custom_components/eufy_vacuum/themes/preloaded.py:140
- custom_components/eufy_vacuum/themes/preloaded.py:159
- custom_components/eufy_vacuum/themes/preloaded.py:161
- custom_components/eufy_vacuum/themes/preloaded.py:171
- custom_components/eufy_vacuum/themes/preloaded.py:172
- custom_components/eufy_vacuum/themes/preloaded.py:173
- custom_components/eufy_vacuum/themes/preloaded.py:187
- custom_components/eufy_vacuum/themes/preloaded.py:188
- custom_components/eufy_vacuum/themes/preloaded.py:193
- custom_components/eufy_vacuum/themes/preloaded.py:194
- custom_components/eufy_vacuum/themes/preloaded.py:195
- custom_components/eufy_vacuum/themes/preloaded.py:196
- custom_components/eufy_vacuum/themes/preloaded.py:501

**`--evcc-accent-soft`** — Accent Soft · default src/styles/foundation.js:135
- src/styles/map.js:589 (background)
- src/styles/map.js:603 (fill)
- src/styles/map.js:611 (fill)

**`--evcc-text-muted`** — Text Muted · default src/styles/foundation.js:123, src/styles/index.js:214, src/styles/index.js:548
- src/room-card.js:340 (--text-muted)
- src/styles/base-station.js:88 (color)
- src/styles/index.js:363
- src/styles/index.js:393
- src/styles/index.js:458
- src/styles/index.js:675 (color)
- src/styles/index.js:758 (color)
- src/styles/learning.js:54 (--evcc-learning-text-muted)
- src/styles/learning.js:120
- src/styles/learning.js:121
- src/styles/learning.js:652 (color)
- src/styles/learning.js:695 (color)
- src/styles/maintenance.js:217 (color)
- src/styles/maintenance.js:366 (color)
- src/styles/maintenance.js:420 (color)
- src/styles/map.js:29 (color)
- src/styles/map.js:329 (color)
- src/styles/map.js:410 (color)
- src/styles/map.js:530 (color)
- src/styles/map.js:541 (color)
- src/styles/map.js:658 (color)
- src/styles/map.js:675 (color)
- src/styles/map.js:688 (color)
- src/styles/map.js:821 (color)
- src/styles/map.js:828 (color)
- src/styles/map.js:849 (color)
- src/styles/map.js:888 (color)
- src/styles/mapping-review.js:104
- src/styles/mapping-review.js:105 (color)
- src/styles/mapping-review.js:212 (color)
- src/styles/mapping-review.js:240 (color)
- src/styles/metrics.js:196 (color)
- src/styles/metrics.js:212 (color)
- src/styles/metrics.js:232 (color)
- src/styles/metrics.js:243 (color)
- src/styles/modals.js:241
- src/styles/modals.js:276
- src/styles/modals.js:277
- src/styles/modals.js:278 (color)
- src/styles/modals.js:287
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
- src/styles/rooms.js:185 (color)
- src/styles/rooms.js:214 (color)
- src/styles/rooms.js:400 (color)
- src/styles/rooms.js:542
- src/styles/rooms.js:687 (color)
- src/styles/rooms.js:705
- src/styles/rooms.js:712 (--evcc-learning-note-text)
- src/styles/rooms.js:741 (color)
- src/styles/rooms.js:1070
- src/styles/rooms.js:1071
- src/styles/rooms.js:1109
- src/styles/rooms.js:1110
- src/styles/rooms.js:1117 (color)
- src/styles/rooms.js:1131 (color)
- src/styles/rooms.js:1132
- src/styles/run-profiles.js:75 (color)
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
- src/styles/shell.js:206 (color)
- src/styles/shell.js:278 (color)
- src/styles/theme-preview.js:51 (color)
- src/styles/theme-preview.js:117 (color)
- src/styles/theme-preview.js:149 (color)
- src/styles/theme-preview.js:196 (color)
- src/styles/theme-preview.js:609 (color)
- src/styles/theme-preview.js:632 (color)
- src/styles/theme.js:60 (color)
- src/styles/theme.js:77 (color)
- src/styles/theme.js:145 (color)
- src/styles/theme.js:278 (color)
- src/styles/theme.js:384 (color)
- src/styles/theme.js:797 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:164
- custom_components/eufy_vacuum/themes/preloaded.py:167
- custom_components/eufy_vacuum/themes/preloaded.py:189
- custom_components/eufy_vacuum/themes/preloaded.py:218

**`--evcc-text-on-accent`** — Text On Accent · default src/styles/foundation.js:125
- src/styles/index.js:687 (color)
- src/styles/map.js:753 (color)

**`--evcc-text-primary`** — Text Primary · default src/styles/foundation.js:121, src/styles/index.js:206, src/styles/index.js:540
- src/room-card.js:339 (--text-primary)
- src/styles/base-station.js:40 (color)
- src/styles/base-station.js:75 (color)
- src/styles/external-jobs.js:23 (color)
- src/styles/external-jobs.js:71 (color)
- src/styles/external-jobs.js:87 (color)
- src/styles/external-jobs.js:144 (color)
- src/styles/external-jobs.js:150 (color)
- src/styles/external-jobs.js:160 (color)
- src/styles/foundation.js:69
- src/styles/foundation.js:186 (--evcc-chip-hover-text)
- src/styles/foundation.js:229 (color)
- src/styles/foundation.js:292 (color)
- src/styles/index.js:147
- src/styles/index.js:175
- src/styles/index.js:296
- src/styles/index.js:332
- src/styles/index.js:681 (color)
- src/styles/index.js:740 (color)
- src/styles/index.js:765 (color)
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
- src/styles/map.js:402 (color)
- src/styles/map.js:474 (color)
- src/styles/map.js:480 (color)
- src/styles/map.js:567 (color)
- src/styles/map.js:591 (color)
- src/styles/map.js:653 (color)
- src/styles/map.js:710 (color)
- src/styles/map.js:949 (color)
- src/styles/map.js:1002 (color)
- src/styles/map.js:1007 (color)
- src/styles/mapping-review.js:43 (color)
- src/styles/mapping-review.js:152 (color)
- src/styles/mapping-review.js:206 (color)
- src/styles/metrics.js:40 (color)
- src/styles/metrics.js:75 (color)
- src/styles/metrics.js:81 (color)
- src/styles/metrics.js:156 (color)
- src/styles/metrics.js:257 (color)
- src/styles/mobile.js:78 (color)
- src/styles/mobile.js:100 (color)
- src/styles/mobile.js:246 (color)
- src/styles/modals.js:118
- src/styles/modals.js:145
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
- src/styles/rooms.js:163 (color)
- src/styles/rooms.js:204 (color)
- src/styles/rooms.js:371 (color)
- src/styles/rooms.js:427
- src/styles/rooms.js:635
- src/styles/rooms.js:642
- src/styles/rooms.js:702 (--evcc-estimate-learned-text)
- src/styles/rooms.js:827 (color)
- src/styles/rooms.js:1066 (--evcc-chip-text)
- src/styles/run-profiles.js:37 (color)
- src/styles/run-profiles.js:61 (color)
- src/styles/run-profiles.js:85 (color)
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
- src/styles/shell.js:80 (color)
- src/styles/shell.js:166 (color)
- src/styles/shell.js:250 (color)
- src/styles/shell.js:286 (color)
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
- src/styles/theme.js:182 (color)
- src/styles/theme.js:266 (color)
- src/styles/theme.js:295 (color)
- src/styles/theme.js:353 (color)
- src/styles/theme.js:534 (color)
- src/styles/theme.js:756 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:88
- custom_components/eufy_vacuum/themes/preloaded.py:126
- custom_components/eufy_vacuum/themes/preloaded.py:190
- custom_components/eufy_vacuum/themes/preloaded.py:210
- custom_components/eufy_vacuum/themes/preloaded.py:219

**`--evcc-text-secondary`** — Text Secondary · default src/styles/foundation.js:122, src/styles/index.js:210, src/styles/index.js:544
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
- src/styles/foundation.js:171 (--evcc-color-idle)
- src/styles/foundation.js:183 (--evcc-chip-text)
- src/styles/foundation.js:258 (color)
- src/styles/foundation.js:274 (color)
- src/styles/foundation.js:286 (color)
- src/styles/index.js:282
- src/styles/index.js:398
- src/styles/index.js:445
- src/styles/index.js:661 (color)
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
- src/styles/map.js:322 (color)
- src/styles/map.js:464 (color)
- src/styles/map.js:547 (color)
- src/styles/map.js:577 (color)
- src/styles/map.js:698 (color)
- src/styles/map.js:802 (color)
- src/styles/map.js:856 (color)
- src/styles/map.js:897 (color)
- src/styles/map.js:939 (color)
- src/styles/map.js:990 (color)
- src/styles/mapping-review.js:13 (color)
- src/styles/mapping-review.js:55 (color)
- src/styles/mapping-review.js:111 (color)
- src/styles/mapping-review.js:145 (color)
- src/styles/mapping-review.js:157 (color)
- src/styles/mapping-review.js:172 (color)
- src/styles/mapping-review.js:217 (color)
- src/styles/metrics.js:47 (color)
- src/styles/metrics.js:115 (color)
- src/styles/mobile.js:90 (color)
- src/styles/mobile.js:146 (color)
- src/styles/modals.js:291
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
- src/styles/rooms.js:171 (color)
- src/styles/rooms.js:208 (color)
- src/styles/rooms.js:421
- src/styles/rooms.js:543
- src/styles/rooms.js:578
- src/styles/rooms.js:600
- src/styles/rooms.js:628
- src/styles/rooms.js:649
- src/styles/rooms.js:656
- src/styles/rooms.js:709 (--evcc-estimate-default-text)
- src/styles/rooms.js:808 (color)
- src/styles/rooms.js:1072 (--evcc-chip-text)
- src/styles/run-profiles.js:43 (color)
- src/styles/run-profiles.js:94 (color)
- src/styles/run-profiles.js:110 (color)
- src/styles/setup.js:28 (color)
- src/styles/setup.js:79 (color)
- src/styles/setup.js:124 (color)
- src/styles/setup.js:405 (color)
- src/styles/setup.js:500 (color)
- src/styles/shell.js:91 (color)
- src/styles/shell.js:157 (color)
- src/styles/theme-preview.js:63 (color)
- src/styles/theme-preview.js:144 (color)
- src/styles/theme-preview.js:317
- src/styles/theme-preview.js:359
- src/styles/theme-preview.js:392 (color)
- src/styles/theme-preview.js:616 (color)
- src/styles/theme.js:85 (color)
- src/styles/theme.js:317 (color)
- src/styles/theme.js:588 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:96
- custom_components/eufy_vacuum/themes/preloaded.py:105
- custom_components/eufy_vacuum/themes/preloaded.py:108
- custom_components/eufy_vacuum/themes/preloaded.py:117
- custom_components/eufy_vacuum/themes/preloaded.py:132
- custom_components/eufy_vacuum/themes/preloaded.py:135
- custom_components/eufy_vacuum/themes/preloaded.py:142
- custom_components/eufy_vacuum/themes/preloaded.py:163
- custom_components/eufy_vacuum/themes/preloaded.py:170
- custom_components/eufy_vacuum/themes/preloaded.py:183
- custom_components/eufy_vacuum/themes/preloaded.py:184
- custom_components/eufy_vacuum/themes/preloaded.py:191
- custom_components/eufy_vacuum/themes/preloaded.py:211
- custom_components/eufy_vacuum/themes/preloaded.py:220

**`--evcc-text-strong`** — Text Strong · default src/styles/foundation.js:124
- src/styles/learning.js:687 (color)
- src/styles/metrics.js:206 (color)

## Cards & Surfaces  ·  18/18 consumed

**`--evcc-bg-input`** — BG Input · default src/styles/foundation.js:165
- src/styles/theme-preview.js:194

**`--evcc-card-bg`** — Card BG · default src/styles/foundation.js:163
- src/styles/theme-preview.js:34
- src/styles/theme-preview.js:173
- src/styles/theme-preview.js:206
- src/styles/theme-preview.js:275

**`--evcc-card-gap`** — Card Gap · default —
- src/styles/rooms.js:281 (gap)

**`--evcc-card-min-height`** — Card Min Height · default —
- src/styles/rooms.js:282 (min-height)
- src/styles/theme-preview.js:94 (min-height)

**`--evcc-card-padding`** — Card Padding · default —
- src/styles/rooms.js:283 (padding)
- src/styles/theme-preview.js:93 (padding)
- src/styles/theme-preview.js:172 (padding)

**`--evcc-panel-bg`** — Panel BG · default src/styles/foundation.js:164
- src/styles/run-profiles.js:24
- src/styles/theme-preview.js:95
- src/styles/theme-preview.js:108
- src/styles/theme-preview.js:183
- src/styles/theme-preview.js:561

**`--evcc-surface-action`** — Surface Action · default src/styles/foundation.js:115
- src/styles/learning.js:629 (background)
- src/styles/map.js:136 (background)

**`--evcc-surface-action-hover`** — Surface Action Hover · default src/styles/foundation.js:116
- src/styles/learning.js:639 (background)
- src/styles/map.js:146 (background)

**`--evcc-surface-base`** — Surface Base · default src/styles/foundation.js:107
- src/styles/foundation.js:108 (--evcc-surface-card)
- src/styles/foundation.js:109
- src/styles/foundation.js:110
- src/styles/theme.js:153 (background)
- src/styles/theme.js:631 (background)
- src/styles/theme.js:634
- src/styles/theme.js:654 (background)
- src/styles/theme.js:657
- src/styles/theme.js:716 (background)
- src/styles/theme.js:719
- src/styles/theme.js:739 (background)
- src/styles/theme.js:742
- custom_components/eufy_vacuum/themes/preloaded.py:70
- custom_components/eufy_vacuum/themes/preloaded.py:198

**`--evcc-surface-card`** — Surface Card · default src/styles/foundation.js:108
- src/room-card.js:337 (--surface)
- src/styles/foundation.js:163 (--evcc-card-bg)
- src/styles/foundation.js:227 (background)
- src/styles/rooms.js:286
- src/styles/rooms.js:302
- src/styles/rooms.js:470
- src/styles/rooms.js:477 (background-color)
- src/styles/rooms.js:490
- src/styles/rooms.js:498
- src/styles/rooms.js:499
- src/styles/rooms.js:500
- src/styles/rooms.js:510 (background-color)
- src/styles/shell.js:47 (background)
- src/styles/theme-preview.js:34 (background)
- src/styles/theme-preview.js:173 (background)
- src/styles/theme-preview.js:206 (background)
- src/styles/theme-preview.js:275
- src/styles/theme.js:113 (background)
- src/styles/theme.js:135
- src/styles/theme.js:533 (background)
- custom_components/eufy_vacuum/themes/preloaded.py:67

**`--evcc-surface-chip`** — Surface Chip · default src/styles/foundation.js:114
- src/styles/learning.js:610 (background)
- src/styles/learning.js:664 (background)

**`--evcc-surface-input`** — Surface Input · default src/styles/foundation.js:111, src/styles/index.js:185, src/styles/index.js:523
- src/styles/external-jobs.js:22 (background)
- src/styles/external-jobs.js:100 (background)
- src/styles/external-jobs.js:149 (background)
- src/styles/foundation.js:46
- src/styles/foundation.js:165 (--evcc-bg-input)
- src/styles/foundation.js:181 (--evcc-chip-bg)
- src/styles/index.js:278
- src/styles/maintenance.js:168
- src/styles/map.js:39 (background)
- src/styles/map.js:48 (background)
- src/styles/map.js:356 (background)
- src/styles/map.js:472 (background)
- src/styles/map.js:566 (background)
- src/styles/map.js:708 (background)
- src/styles/map.js:810 (background)
- src/styles/map.js:816 (background)
- src/styles/map.js:896 (background)
- src/styles/map.js:947 (background)
- src/styles/metrics.js:157 (background)
- src/styles/order.js:50
- src/styles/review.js:187 (background)
- src/styles/room-rules.js:52 (background)
- src/styles/room-rules.js:57 (background)
- src/styles/room-rules.js:119 (background)
- src/styles/room-rules.js:237 (background)
- src/styles/room-rules.js:300 (background)
- src/styles/room-rules.js:336 (background)
- src/styles/room-rules.js:388 (background)
- src/styles/rooms.js:467
- src/styles/rooms.js:468
- src/styles/rooms.js:487
- src/styles/rooms.js:488
- src/styles/rooms.js:576
- src/styles/rooms.js:597
- src/styles/rooms.js:626
- src/styles/rooms.js:633
- src/styles/rooms.js:640
- src/styles/rooms.js:647
- src/styles/rooms.js:654
- src/styles/rooms.js:689
- src/styles/rooms.js:782
- src/styles/rooms.js:789
- src/styles/rooms.js:796
- src/styles/run-profiles.js:54
- src/styles/run-profiles.js:84 (background)
- src/styles/setup.js:42 (background)
- src/styles/setup.js:123 (background)
- src/styles/setup.js:174 (background)
- src/styles/setup.js:270 (background)
- src/styles/setup.js:335 (background)
- src/styles/setup.js:371 (background)
- src/styles/setup.js:404 (background)
- src/styles/setup.js:515 (background)
- src/styles/theme-preview.js:194 (background)
- src/styles/theme.js:45 (background)
- src/styles/theme.js:292 (background)
- src/styles/theme.js:435 (background)
- src/styles/theme.js:752 (background)
- custom_components/eufy_vacuum/themes/preloaded.py:66
- custom_components/eufy_vacuum/themes/preloaded.py:81
- custom_components/eufy_vacuum/themes/preloaded.py:100
- custom_components/eufy_vacuum/themes/preloaded.py:115
- custom_components/eufy_vacuum/themes/preloaded.py:133
- custom_components/eufy_vacuum/themes/preloaded.py:168
- custom_components/eufy_vacuum/themes/preloaded.py:206
- custom_components/eufy_vacuum/themes/preloaded.py:214
- custom_components/eufy_vacuum/themes/preloaded.py:215

**`--evcc-surface-overlay`** — Surface Overlay · default src/styles/foundation.js:112
- custom_components/eufy_vacuum/themes/preloaded.py:197

**`--evcc-surface-panel`** — Surface Panel · default src/styles/foundation.js:109, src/styles/index.js:190, src/styles/index.js:519
- src/styles/base-station.js:23 (background)
- src/styles/external-jobs.js:29 (background)
- src/styles/external-jobs.js:159 (background)
- src/styles/foundation.js:68
- src/styles/foundation.js:164 (--evcc-panel-bg)
- src/styles/foundation.js:185 (--evcc-chip-hover-bg)
- src/styles/index.js:292
- src/styles/learning.js:39 (--evcc-learning-panel-bg)
- src/styles/maintenance.js:141 (background)
- src/styles/map.js:74 (background)
- src/styles/map.js:342 (background)
- src/styles/map.js:371 (background)
- src/styles/map.js:1006 (background)
- src/styles/mapping-review.js:31 (background)
- src/styles/metrics.js:23 (background)
- src/styles/mobile.js:69 (background)
- src/styles/mobile.js:115 (background)
- src/styles/mobile.js:222 (background)
- src/styles/order.js:99
- src/styles/review.js:23 (background)
- src/styles/review.js:105
- src/styles/review.js:214
- src/styles/room-access.js:16
- src/styles/room-estimate.js:40
- src/styles/room-estimate.js:62
- src/styles/room-rules.js:282 (background)
- src/styles/run-profiles.js:24 (background)
- src/styles/shell.js:148 (background)
- src/styles/theme-preview.js:95 (background)
- src/styles/theme-preview.js:108
- src/styles/theme-preview.js:183 (background)
- src/styles/theme-preview.js:485
- src/styles/theme-preview.js:561 (background)
- src/styles/theme.js:55 (background)
- src/styles/theme.js:173 (background)
- src/styles/theme.js:226
- src/styles/theme.js:246
- src/styles/theme.js:329 (background)
- src/styles/theme.js:339
- custom_components/eufy_vacuum/themes/preloaded.py:68
- custom_components/eufy_vacuum/themes/preloaded.py:86
- custom_components/eufy_vacuum/themes/preloaded.py:106
- custom_components/eufy_vacuum/themes/preloaded.py:124
- custom_components/eufy_vacuum/themes/preloaded.py:185
- custom_components/eufy_vacuum/themes/preloaded.py:208
- custom_components/eufy_vacuum/themes/preloaded.py:212
- custom_components/eufy_vacuum/themes/preloaded.py:213
- custom_components/eufy_vacuum/themes/preloaded.py:216
- custom_components/eufy_vacuum/themes/preloaded.py:424

**`--evcc-surface-raised`** — Surface Raised · default src/styles/foundation.js:110
- src/styles/base-station.js:67 (background)
- src/styles/base-station.js:107
- src/styles/external-jobs.js:67 (background)
- src/styles/foundation.js:273 (background)
- src/styles/foundation.js:291 (background)
- src/styles/index.js:739 (background)
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
- src/styles/map.js:576 (background)
- src/styles/mapping-review.js:116
- src/styles/metrics.js:68 (background)
- src/styles/mobile.js:154 (background)
- src/styles/mobile.js:254 (background)
- src/styles/review.js:90 (background)
- src/styles/review.js:126 (background)
- src/styles/shell.js:165 (background)
- src/styles/shell.js:249 (background)
- custom_components/eufy_vacuum/themes/preloaded.py:92
- custom_components/eufy_vacuum/themes/preloaded.py:130
- custom_components/eufy_vacuum/themes/preloaded.py:217
- custom_components/eufy_vacuum/themes/preloaded.py:328
- custom_components/eufy_vacuum/themes/preloaded.py:378
- custom_components/eufy_vacuum/themes/preloaded.py:401

**`--evcc-surface-subtle`** — Surface Subtle · default src/styles/foundation.js:113
- src/styles/index.js:659 (background)
- src/styles/index.js:674 (background)
- src/styles/maintenance.js:352 (background)
- src/styles/rooms.js:742 (background)
- src/styles/setup.js:548 (background)
- src/styles/setup.js:595 (background)
- src/styles/theme-preview.js:624 (background)
- src/styles/theme-preview.js:637 (background)

**`--evcc-surface-sunken`** — Surface Sunken · default src/styles/foundation.js:117
- src/styles/metrics.js:251 (background)
- src/styles/setup.js:310 (background)

**`--evcc-surface-warning`** — Surface Warning · default src/styles/foundation.js:118
- src/styles/learning.js:582 (background)

## Borders & Shadows  ·  6/6 consumed

**`--evcc-border-default`** — Border Default · default src/styles/foundation.js:129, src/styles/index.js:194, src/styles/index.js:528
- src/room-card.js:338 (--border)
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
- src/styles/foundation.js:182 (--evcc-chip-border)
- src/styles/foundation.js:275
- src/styles/index.js:274
- src/styles/index.js:622
- src/styles/index.js:742
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
- src/styles/map.js:359
- src/styles/map.js:461
- src/styles/map.js:565
- src/styles/map.js:575
- src/styles/map.js:695
- src/styles/map.js:799
- src/styles/map.js:885
- src/styles/map.js:936
- src/styles/map.js:988
- src/styles/mapping-review.js:30
- src/styles/mapping-review.js:180
- src/styles/metrics.js:22
- src/styles/metrics.js:158
- src/styles/metrics.js:195
- src/styles/metrics.js:227
- src/styles/metrics.js:252
- src/styles/modals.js:132
- src/styles/modals.js:181
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
- src/styles/rooms.js:285
- src/styles/rooms.js:544
- src/styles/rooms.js:577
- src/styles/rooms.js:627
- src/styles/rooms.js:634
- src/styles/rooms.js:641
- src/styles/rooms.js:648
- src/styles/rooms.js:655
- src/styles/rooms.js:688
- src/styles/rooms.js:707 (--evcc-estimate-default-border)
- src/styles/rooms.js:783
- src/styles/rooms.js:790
- src/styles/rooms.js:797
- src/styles/run-profiles.js:23
- src/styles/run-profiles.js:53
- src/styles/run-profiles.js:83
- src/styles/setup.js:43
- src/styles/setup.js:125
- src/styles/setup.js:260
- src/styles/setup.js:309
- src/styles/setup.js:403
- src/styles/theme-preview.js:96
- src/styles/theme-preview.js:185
- src/styles/theme-preview.js:195
- src/styles/theme-preview.js:216
- src/styles/theme-preview.js:344
- src/styles/theme-preview.js:486
- src/styles/theme-preview.js:562
- src/styles/theme-preview.js:590
- src/styles/theme.js:293
- src/styles/theme.js:436
- src/styles/theme.js:535
- src/styles/theme.js:575
- src/styles/theme.js:607
- src/styles/theme.js:619
- src/styles/theme.js:644
- src/styles/theme.js:666
- src/styles/theme.js:692
- src/styles/theme.js:704
- src/styles/theme.js:729
- src/styles/theme.js:753
- custom_components/eufy_vacuum/themes/preloaded.py:82
- custom_components/eufy_vacuum/themes/preloaded.py:101
- custom_components/eufy_vacuum/themes/preloaded.py:107
- custom_components/eufy_vacuum/themes/preloaded.py:116
- custom_components/eufy_vacuum/themes/preloaded.py:131
- custom_components/eufy_vacuum/themes/preloaded.py:169
- custom_components/eufy_vacuum/themes/preloaded.py:182
- custom_components/eufy_vacuum/themes/preloaded.py:186
- custom_components/eufy_vacuum/themes/preloaded.py:199
- custom_components/eufy_vacuum/themes/preloaded.py:200
- custom_components/eufy_vacuum/themes/preloaded.py:207

**`--evcc-border-strong`** — Border Strong · default src/styles/foundation.js:130, src/styles/index.js:202, src/styles/index.js:536
- src/styles/base-station.js:102 (border-color)
- src/styles/foundation.js:70
- src/styles/foundation.js:187 (--evcc-chip-hover-border)
- src/styles/index.js:300
- src/styles/index.js:403
- src/styles/maintenance.js:307 (border-color)
- src/styles/map.js:52 (border-color)
- src/styles/map.js:373 (border-color)
- src/styles/map.js:951 (border-color)
- src/styles/map.js:1001 (border-color)
- src/styles/metrics.js:164
- src/styles/modals.js:295
- src/styles/order.js:101
- src/styles/rooms.js:311 (border-color)
- src/styles/theme-preview.js:220
- src/styles/theme.js:126 (border-color)
- custom_components/eufy_vacuum/themes/preloaded.py:87
- custom_components/eufy_vacuum/themes/preloaded.py:125
- custom_components/eufy_vacuum/themes/preloaded.py:201
- custom_components/eufy_vacuum/themes/preloaded.py:209
- custom_components/eufy_vacuum/themes/preloaded.py:447

**`--evcc-border-subtle`** — Border Subtle · default src/styles/foundation.js:128, src/styles/index.js:198, src/styles/index.js:532
- src/styles/base-station.js:66
- src/styles/index.js:319
- src/styles/index.js:422
- src/styles/index.js:437
- src/styles/index.js:660
- src/styles/learning.js:339
- src/styles/learning.js:390
- src/styles/maintenance.js:97
- src/styles/maintenance.js:202
- src/styles/maintenance.js:353
- src/styles/maintenance.js:376
- src/styles/map.js:344
- src/styles/map.js:439
- src/styles/map.js:450
- src/styles/map.js:515
- src/styles/map.js:525
- src/styles/mapping-review.js:193 (border-color)
- src/styles/metrics.js:67
- src/styles/mobile.js:68
- src/styles/mobile.js:116
- src/styles/mobile.js:223
- src/styles/mobile.js:235 (background)
- src/styles/mobile.js:531
- src/styles/mobile.js:624
- src/styles/review.js:89
- src/styles/review.js:104
- src/styles/review.js:125
- src/styles/review.js:213
- src/styles/room-estimate.js:38
- src/styles/room-estimate.js:60
- src/styles/room-rules.js:27
- src/styles/room-rules.js:243
- src/styles/room-rules.js:281
- src/styles/room-rules.js:293
- src/styles/room-rules.js:414
- src/styles/rooms.js:743 (border-color)
- src/styles/setup.js:175
- src/styles/setup.js:336
- src/styles/setup.js:547
- src/styles/shell.js:66
- src/styles/shell.js:147
- src/styles/shell.js:252
- src/styles/theme-preview.js:35
- src/styles/theme-preview.js:212
- src/styles/theme-preview.js:499
- src/styles/theme.js:46
- src/styles/theme.js:114
- src/styles/theme.js:229
- src/styles/theme.js:249
- src/styles/theme.js:308 (border-color)
- src/styles/theme.js:330
- custom_components/eufy_vacuum/themes/preloaded.py:134
- custom_components/eufy_vacuum/themes/preloaded.py:202

**`--evcc-border-warning`** — Border Warning · default src/styles/foundation.js:131
- src/styles/learning.js:583

**`--evcc-shadow-card`** — Shadow Card · default —
- src/styles/learning.js:45 (--evcc-learning-panel-shadow)
- src/styles/order.js:150
- src/styles/order.js:162
- src/styles/rooms.js:287 (box-shadow)
- src/styles/run-profiles.js:25 (box-shadow)
- src/styles/shell.js:49 (box-shadow)
- src/styles/theme-preview.js:37 (box-shadow)
- src/styles/theme-preview.js:98 (box-shadow)
- src/styles/theme-preview.js:175 (box-shadow)
- src/styles/theme-preview.js:224 (box-shadow)

**`--evcc-shadow-hover`** — Shadow Hover · default —
- src/styles/order.js:122 (box-shadow)
- src/styles/order.js:156
- src/styles/rooms.js:306
- src/styles/rooms.js:601 (box-shadow)
- src/styles/theme-preview.js:228 (box-shadow)
- src/styles/theme-preview.js:380

## Chips  ·  31/31 consumed

**`--evcc-chip-active-bg`** — Chip Active BG · default —
- src/styles/foundation.js:74 (background)

**`--evcc-chip-active-border`** — Chip Active Border · default —
- src/styles/foundation.js:77 (border-color)

**`--evcc-chip-active-text`** — Chip Active Text · default —
- src/styles/foundation.js:76 (color)

**`--evcc-chip-bg`** — Chip BG · default src/styles/foundation.js:181, src/styles/index.js:276, src/styles/order.js:48, src/styles/rooms.js:419, src/styles/rooms.js:425, src/styles/rooms.js:432, src/styles/rooms.js:440, src/styles/rooms.js:533, src/styles/rooms.js:541, src/styles/rooms.js:548, src/styles/rooms.js:1064, src/styles/rooms.js:1070
- src/styles/foundation.js:46 (background)
- src/styles/maintenance.js:168 (background)
- src/styles/rooms.js:467
- src/styles/rooms.js:468
- src/styles/rooms.js:487
- src/styles/rooms.js:488
- src/styles/theme-preview.js:237

**`--evcc-chip-border`** — Chip Border · default src/styles/foundation.js:182, src/styles/index.js:272, src/styles/order.js:52, src/styles/rooms.js:420, src/styles/rooms.js:426, src/styles/rooms.js:434, src/styles/rooms.js:441, src/styles/rooms.js:536, src/styles/rooms.js:544, src/styles/rooms.js:550, src/styles/rooms.js:1065, src/styles/rooms.js:1071
- src/styles/foundation.js:44
- src/styles/maintenance.js:167
- src/styles/theme-preview.js:238

**`--evcc-chip-excluded-bg`** — Chip Excluded BG · default —
- src/styles/rooms.js:541 (--evcc-chip-bg)
- src/styles/theme-preview.js:249 (background)

**`--evcc-chip-excluded-border`** — Chip Excluded Border · default —
- src/styles/rooms.js:544 (--evcc-chip-border)
- src/styles/theme-preview.js:250 (border-color)

**`--evcc-chip-excluded-text`** — Chip Excluded Text · default —
- src/styles/rooms.js:543 (--evcc-chip-text)
- src/styles/theme-preview.js:251 (color)

**`--evcc-chip-font-size`** — Chip Font Size · default src/styles/index.js:284, src/styles/order.js:45, src/styles/order.js:72, src/styles/order.js:83, src/styles/rooms.js:417, src/styles/rooms.js:527, src/styles/rooms.js:884, src/styles/rooms.js:1062
- src/styles/foundation.js:49 (font-size)

**`--evcc-chip-font-weight`** — Chip Font Weight · default src/styles/index.js:287, src/styles/order.js:46, src/styles/order.js:73, src/styles/order.js:84, src/styles/rooms.js:418, src/styles/rooms.js:528, src/styles/rooms.js:1063
- src/styles/foundation.js:50 (font-weight)

**`--evcc-chip-gap`** — Chip Gap · default —
- src/styles/foundation.js:30 (gap)
- src/styles/order.js:34 (gap)
- src/styles/rooms.js:411 (gap)

**`--evcc-chip-height`** — Chip Height · default src/styles/foundation.js:177, src/styles/index.js:225, src/styles/order.js:43, src/styles/order.js:70, src/styles/order.js:81, src/styles/rooms.js:415, src/styles/rooms.js:525, src/styles/rooms.js:882, src/styles/rooms.js:1060
- src/styles/foundation.js:40 (min-height)
- src/styles/maintenance.js:164 (min-height)

**`--evcc-chip-hover-bg`** — Chip Hover BG · default src/styles/foundation.js:185, src/styles/index.js:290
- src/styles/foundation.js:68 (background)
- src/styles/order.js:99 (background)
- src/styles/theme-preview.js:237 (background)

**`--evcc-chip-hover-border`** — Chip Hover Border · default src/styles/foundation.js:187, src/styles/index.js:298
- src/styles/foundation.js:70 (border-color)
- src/styles/order.js:101 (border-color)
- src/styles/theme-preview.js:238 (border-color)

**`--evcc-chip-hover-text`** — Chip Hover Text · default src/styles/foundation.js:186, src/styles/index.js:294
- src/styles/foundation.js:69 (color)
- src/styles/order.js:100 (color)
- src/styles/theme-preview.js:239 (color)

**`--evcc-chip-icon-height`** — Chip Icon Height · default src/styles/foundation.js:189, src/styles/index.js:302
- src/styles/foundation.js:88 (min-height)

**`--evcc-chip-icon-padding`** — Chip Icon Padding · default src/styles/foundation.js:190, src/styles/index.js:305
- src/styles/foundation.js:89 (padding)

**`--evcc-chip-icon-size`** — Chip Icon Size · default src/styles/foundation.js:191, src/styles/index.js:308
- src/styles/foundation.js:90 (font-size)

**`--evcc-chip-included-bg`** — Chip Included BG · default —
- src/styles/index.js:468 (background)
- src/styles/rooms.js:533 (--evcc-chip-bg)
- src/styles/theme-preview.js:243 (background)

**`--evcc-chip-included-border`** — Chip Included Border · default —
- src/styles/index.js:476 (border-color)
- src/styles/rooms.js:536 (--evcc-chip-border)
- src/styles/theme-preview.js:244 (border-color)

**`--evcc-chip-included-text`** — Chip Included Text · default —
- src/styles/index.js:472 (color)
- src/styles/rooms.js:535 (--evcc-chip-text)
- src/styles/theme-preview.js:245 (color)

**`--evcc-chip-neutral-bg`** — Chip Neutral BG · default —
- src/styles/order.js:49

**`--evcc-chip-padding`** — Chip Padding · default src/styles/foundation.js:178, src/styles/index.js:228, src/styles/order.js:44, src/styles/order.js:71, src/styles/order.js:82, src/styles/rooms.js:416, src/styles/rooms.js:526, src/styles/rooms.js:883, src/styles/rooms.js:1061
- src/styles/foundation.js:41 (padding)
- src/styles/maintenance.js:165 (padding)

**`--evcc-chip-radius`** — Chip Radius · default src/styles/foundation.js:179, src/styles/index.js:231
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

**`--evcc-chip-text`** — Chip Text · default src/styles/foundation.js:183, src/styles/index.js:280, src/styles/order.js:55, src/styles/rooms.js:421, src/styles/rooms.js:427, src/styles/rooms.js:436, src/styles/rooms.js:535, src/styles/rooms.js:543, src/styles/rooms.js:549, src/styles/rooms.js:1066, src/styles/rooms.js:1072
- src/styles/foundation.js:47 (color)
- src/styles/maintenance.js:169 (color)
- src/styles/theme-preview.js:239

**`--evcc-chip-warning-bg`** — Chip Warning BG · default —
- src/styles/rooms.js:97 (background)
- src/styles/rooms.js:610 (background)
- src/styles/theme-preview.js:261 (background)

**`--evcc-chip-warning-border`** — Chip Warning Border · default —
- src/styles/rooms.js:100 (border-color)
- src/styles/rooms.js:612 (border-color)
- src/styles/theme-preview.js:262 (border-color)

**`--evcc-chip-warning-text`** — Chip Warning Text · default —
- src/styles/rooms.js:99 (color)
- src/styles/rooms.js:614 (color)
- src/styles/theme-preview.js:263 (color)

## Room Cards  ·  13/13 consumed

**`--evcc-profile-chip-bg`** — Profile Chip BG · default —
- src/styles/rooms.js:425 (--evcc-chip-bg)
- src/styles/theme-preview.js:303 (background)

**`--evcc-profile-chip-border`** — Profile Chip Border · default —
- src/styles/rooms.js:426 (--evcc-chip-border)
- src/styles/theme-preview.js:304 (border-color)

**`--evcc-profile-chip-custom-bg`** — Profile Chip Custom BG · default —
- src/styles/rooms.js:432 (--evcc-chip-bg)
- src/styles/theme-preview.js:309 (background)

**`--evcc-profile-chip-custom-border`** — Profile Chip Custom Border · default —
- src/styles/rooms.js:434 (--evcc-chip-border)
- src/styles/theme-preview.js:310 (border-color)

**`--evcc-profile-chip-custom-text`** — Profile Chip Custom Text · default —
- src/styles/rooms.js:436 (--evcc-chip-text)
- src/styles/theme-preview.js:311 (color)

**`--evcc-profile-chip-text`** — Profile Chip Text · default —
- src/styles/rooms.js:427 (--evcc-chip-text)
- src/styles/theme-preview.js:305 (color)

**`--evcc-room-chip-bg`** — Room Chip BG · default —
- src/styles/rooms.js:419 (--evcc-chip-bg)
- src/styles/rooms.js:440 (--evcc-chip-bg)
- src/styles/theme-preview.js:315 (background)

**`--evcc-room-chip-border`** — Room Chip Border · default —
- src/styles/rooms.js:420 (--evcc-chip-border)
- src/styles/rooms.js:441 (--evcc-chip-border)
- src/styles/theme-preview.js:316 (border-color)

**`--evcc-room-chip-text`** — Room Chip Text · default —
- src/styles/rooms.js:421 (--evcc-chip-text)
- src/styles/theme-preview.js:317 (color)

**`--evcc-room-fill-opacity`** — Room Fill Opacity · default src/styles/rooms.js:1037, src/styles/rooms.js:1041, src/styles/rooms.js:1045
- src/styles/rooms.js:925 (opacity)
- src/styles/theme-preview.js:272
- src/styles/theme-preview.js:282

**`--evcc-room-grid-columns`** — Room Grid Columns · default —
- src/styles/layout.js:79 (grid-template-columns)

**`--evcc-room-grid-gap`** — Room Grid Gap · default src/styles/layout.js:64
- src/styles/layout.js:78 (gap)

**`--evcc-room-grid-min`** — Room Grid Min · default src/styles/layout.js:65
- src/styles/layout.js:81

## Map  ·  12/12 consumed

**`--evcc-map-label-bg`** — Map Label Background · default src/styles/index.js:236
- src/styles/map.js:246 (background)

**`--evcc-map-label-text`** — Map Label Text · default src/styles/index.js:239
- src/styles/map.js:239 (color)

**`--evcc-map-label-text-selected`** — Map Label Text (Selected) · default src/styles/index.js:242
- src/styles/map.js:256 (color)

**`--evcc-map-label-order-text`** — Map Order Badge Text · default src/styles/index.js:245
- src/styles/map.js:267 (color)
- src/styles/map.js:385 (color)

**`--evcc-map-tooltip-bg`** — Map Tooltip Background · default src/styles/index.js:248
- src/styles/map.js:120 (background)
- src/styles/map.js:284 (background)

**`--evcc-map-tooltip-border`** — Map Tooltip Border · default src/styles/index.js:251
- src/styles/map.js:121
- src/styles/map.js:137
- src/styles/map.js:286

**`--evcc-map-tooltip-text`** — Map Tooltip Text · default src/styles/index.js:254
- src/styles/map.js:135 (color)
- src/styles/map.js:300 (color)

**`--evcc-map-tooltip-hint`** — Map Tooltip Hint Text · default src/styles/index.js:257
- src/styles/map.js:156 (color)
- src/styles/map.js:306 (color)

**`--evcc-map-compose-selected-stroke`** — Composer Selected Outline · default src/styles/index.js:260
- src/styles/map.js:612 (stroke)

**`--evcc-map-compose-cut-fill`** — Composer Cutout Fill · default src/styles/index.js:263
- src/styles/map.js:619 (fill)

**`--evcc-map-compose-cut-selected-fill`** — Composer Cutout Fill (Selected) · default src/styles/index.js:266
- src/styles/map.js:623 (fill)

**`--evcc-map-vertex-selected-glow`** — Composer Selected Vertex Glow · default src/styles/index.js:269
- src/styles/map.js:502

## Floor Textures  ·  4/4 consumed

**`--evcc-floor-textures-card-enabled`** — Card Textures Enabled (0/1) · default —
- src/styles/floor-texture-styles.js:80

**`--evcc-floor-textures-map-enabled`** — Map Textures Enabled (0/1) · default —
- src/styles/floor-texture-styles.js:104

**`--evcc-floor-texture-opacity-card`** — Card Texture Opacity (all) · default —
- src/renderers/floor-texture-surface.js:97

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

## Floor Textures — Carpet Low  ·  0/3 consumed

**`--evcc-floor-carpet-low-base`** — Carpet Low Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-low-opacity-card`** — Carpet Low Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-low-texture-opacity`** — Carpet Low Texture Layer Opacity · default —
- _no consumer — only seeded_

## Floor Textures — Carpet High  ·  0/3 consumed

**`--evcc-floor-carpet-high-base`** — Carpet High Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-high-opacity-card`** — Carpet High Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-carpet-high-texture-opacity`** — Carpet High Texture Layer Opacity · default —
- _no consumer — only seeded_

## Floor Textures — Granite  ·  0/3 consumed

**`--evcc-floor-granite-light-base`** — Granite Base Color · default —
- _no consumer — only seeded_

**`--evcc-floor-granite-light-opacity-card`** — Granite Card Opacity · default —
- _no consumer — only seeded_

**`--evcc-floor-granite-light-texture-opacity`** — Granite Texture Layer Opacity · default —
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
- src/styles/rooms.js:986 (background)
- src/styles/rooms.js:994 (background)

**`--evcc-progress-fill`** — Progress Fill · default —
- src/styles/rooms.js:897 (background)
- src/styles/rooms.js:919 (background)

**`--evcc-queue-chip-bg`** — Queue Chip BG · default —
- src/styles/rooms.js:576 (background)
- src/styles/rooms.js:597
- src/styles/rooms.js:626
- src/styles/rooms.js:633
- src/styles/rooms.js:640
- src/styles/rooms.js:647
- src/styles/rooms.js:654

**`--evcc-queue-chip-border`** — Queue Chip Border · default —
- src/styles/rooms.js:577
- src/styles/rooms.js:627
- src/styles/rooms.js:634
- src/styles/rooms.js:641
- src/styles/rooms.js:648
- src/styles/rooms.js:655

**`--evcc-queue-chip-gap`** — Queue Chip Gap · default —
- src/styles/rooms.js:561 (gap)
- src/styles/theme-preview.js:341 (gap)

**`--evcc-queue-chip-text`** — Queue Chip Text · default —
- src/styles/rooms.js:578 (color)
- src/styles/rooms.js:600
- src/styles/rooms.js:628
- src/styles/rooms.js:635
- src/styles/rooms.js:642
- src/styles/rooms.js:649
- src/styles/rooms.js:656

**`--evcc-queue-completed-bg`** — Queue Completed BG · default —
- src/styles/rooms.js:647 (background)
- src/styles/theme-preview.js:364 (background)

**`--evcc-queue-completed-border`** — Queue Completed Border · default —
- src/styles/rooms.js:648 (border-color)
- src/styles/theme-preview.js:365 (border-color)

**`--evcc-queue-completed-opacity`** — Queue Completed Opacity · default —
- src/styles/rooms.js:650 (opacity)
- src/styles/theme-preview.js:367 (opacity)

**`--evcc-queue-completed-text`** — Queue Completed Text · default —
- src/styles/rooms.js:649 (color)
- src/styles/theme-preview.js:366 (color)

**`--evcc-queue-current-bg`** — Queue Current BG · default —
- src/styles/rooms.js:618 (background)
- src/styles/rooms.js:633 (background)
- src/styles/theme-preview.js:350 (background)

**`--evcc-queue-current-border`** — Queue Current Border · default —
- src/styles/rooms.js:620 (border-color)
- src/styles/rooms.js:634 (border-color)
- src/styles/theme-preview.js:351 (border-color)

**`--evcc-queue-current-glow`** — Queue Current Glow · default —
- src/styles/rooms.js:636 (box-shadow)
- src/styles/theme-preview.js:353 (box-shadow)

**`--evcc-queue-current-text`** — Queue Current Text · default —
- src/styles/rooms.js:622 (color)
- src/styles/rooms.js:635 (color)
- src/styles/theme-preview.js:352 (color)

**`--evcc-queue-hover-bg`** — Queue Hover BG · default —
- src/styles/rooms.js:597 (background)

**`--evcc-queue-hover-border`** — Queue Hover Border · default —
- src/styles/rooms.js:598 (border-color)

**`--evcc-queue-hover-text`** — Queue Hover Text · default —
- src/styles/rooms.js:600 (color)

**`--evcc-queue-inferred-bg`** — Queue Inferred BG · default —
- src/styles/rooms.js:640 (background)
- src/styles/theme-preview.js:371 (background)

**`--evcc-queue-inferred-border`** — Queue Inferred Border · default —
- src/styles/rooms.js:641 (border-color)
- src/styles/theme-preview.js:372 (border-color)

**`--evcc-queue-inferred-glow`** — Queue Inferred Glow · default —
- src/styles/rooms.js:643 (box-shadow)
- src/styles/theme-preview.js:374 (box-shadow)

**`--evcc-queue-inferred-text`** — Queue Inferred Text · default —
- src/styles/rooms.js:642 (color)
- src/styles/theme-preview.js:373 (color)

**`--evcc-queue-order-bg`** — Queue Order BG · default —
- src/styles/rooms.js:667 (background)
- src/styles/theme-preview.js:333

**`--evcc-queue-order-border`** — Queue Order Border · default —
- src/styles/rooms.js:668
- src/styles/theme-preview.js:334

**`--evcc-queue-order-text`** — Queue Order Text · default —
- src/styles/rooms.js:671 (color)
- src/styles/theme-preview.js:335

**`--evcc-queue-pending-bg`** — Queue Pending BG · default —
- src/styles/rooms.js:626 (background)
- src/styles/theme-preview.js:357 (background)

**`--evcc-queue-pending-border`** — Queue Pending Border · default —
- src/styles/rooms.js:627 (border-color)
- src/styles/theme-preview.js:358 (border-color)

**`--evcc-queue-pending-opacity`** — Queue Pending Opacity · default —
- src/styles/rooms.js:629 (opacity)
- src/styles/theme-preview.js:360 (opacity)

**`--evcc-queue-pending-text`** — Queue Pending Text · default —
- src/styles/rooms.js:628 (color)
- src/styles/theme-preview.js:359 (color)

**`--evcc-queue-skipped-bg`** — Queue Skipped BG · default —
- src/styles/rooms.js:654 (background)

**`--evcc-queue-skipped-border`** — Queue Skipped Border · default —
- src/styles/rooms.js:655 (border-color)

**`--evcc-queue-skipped-text`** — Queue Skipped Text · default —
- src/styles/rooms.js:656 (color)

**`--evcc-reorder-feedback-duration`** — Reorder Feedback Duration · default —
- src/styles/order.js:169

**`--evcc-reorder-flip-easing`** — Reorder Flip Easing · default —
- src/styles/order.js:170

## Status, Confidence & Alerts  ·  31/31 consumed

**`--evcc-color-cleaning`** — Color Cleaning · default src/styles/foundation.js:168
- src/styles/theme-preview.js:410

**`--evcc-color-docked`** — Color Docked · default src/styles/foundation.js:169
- src/styles/theme-preview.js:414

**`--evcc-color-error`** — Color Error · default src/styles/foundation.js:170
- src/styles/theme-preview.js:418

**`--evcc-color-idle`** — Color Idle · default src/styles/foundation.js:171
- src/styles/theme-preview.js:406

**`--evcc-confidence-high-bg`** — Confidence High BG · default src/styles/learning.js:125
- src/styles/rooms.js:782
- src/styles/rooms.js:784
- src/styles/theme-preview.js:423 (background)

**`--evcc-confidence-high-border`** — Confidence High Border · default src/styles/learning.js:127
- src/styles/rooms.js:783
- src/styles/theme-preview.js:424 (border-color)

**`--evcc-confidence-high-text`** — Confidence High Text · default src/styles/learning.js:129
- src/styles/theme-preview.js:425 (color)

**`--evcc-confidence-low-bg`** — Confidence Low BG · default src/styles/learning.js:139
- src/styles/rooms.js:796
- src/styles/rooms.js:798
- src/styles/theme-preview.js:436 (background)

**`--evcc-confidence-low-border`** — Confidence Low Border · default src/styles/learning.js:141
- src/styles/rooms.js:797
- src/styles/theme-preview.js:437 (border-color)

**`--evcc-confidence-low-text`** — Confidence Low Text · default src/styles/learning.js:143
- src/styles/theme-preview.js:438 (color)

**`--evcc-confidence-medium-bg`** — Confidence Medium BG · default src/styles/learning.js:132
- src/styles/rooms.js:789
- src/styles/rooms.js:791
- src/styles/theme-preview.js:430 (background)

**`--evcc-confidence-medium-border`** — Confidence Medium Border · default src/styles/learning.js:134
- src/styles/rooms.js:790
- src/styles/theme-preview.js:431 (border-color)

**`--evcc-confidence-medium-text`** — Confidence Medium Text · default src/styles/learning.js:136
- src/styles/theme-preview.js:432 (color)

**`--evcc-sem-error`** — Sem Error · default src/styles/foundation.js:140
- src/styles/external-jobs.js:80
- src/styles/external-jobs.js:81
- src/styles/external-jobs.js:82 (color)
- src/styles/foundation.js:170 (--evcc-color-error)
- src/styles/index.js:749
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
- src/styles/map.js:738
- src/styles/map.js:739 (color)
- src/styles/map.js:740
- src/styles/map.js:744
- src/styles/map.js:745
- src/styles/map.js:752 (background)
- src/styles/map.js:754 (border-color)
- src/styles/map.js:760
- src/styles/map.js:761
- src/styles/map.js:771 (color)
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
- src/styles/shell.js:263
- src/styles/theme-preview.js:461
- src/styles/theme-preview.js:462
- src/styles/theme-preview.js:463 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:83
- custom_components/eufy_vacuum/themes/preloaded.py:84
- custom_components/eufy_vacuum/themes/preloaded.py:85
- custom_components/eufy_vacuum/themes/preloaded.py:141
- custom_components/eufy_vacuum/themes/preloaded.py:146
- custom_components/eufy_vacuum/themes/preloaded.py:147
- custom_components/eufy_vacuum/themes/preloaded.py:148
- custom_components/eufy_vacuum/themes/preloaded.py:162
- custom_components/eufy_vacuum/themes/preloaded.py:177
- custom_components/eufy_vacuum/themes/preloaded.py:178
- custom_components/eufy_vacuum/themes/preloaded.py:327
- custom_components/eufy_vacuum/themes/preloaded.py:401
- custom_components/eufy_vacuum/themes/preloaded.py:424
- custom_components/eufy_vacuum/themes/preloaded.py:447

**`--evcc-sem-info`** — Sem Info · default src/styles/foundation.js:144
- src/styles/mapping-review.js:99
- src/styles/mapping-review.js:100 (color)
- src/styles/setup.js:560
- src/styles/theme-preview.js:449
- src/styles/theme-preview.js:450
- src/styles/theme-preview.js:451 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:127
- custom_components/eufy_vacuum/themes/preloaded.py:128
- custom_components/eufy_vacuum/themes/preloaded.py:129

**`--evcc-sem-success`** — Sem Success · default src/styles/foundation.js:138
- src/styles/base-station.js:107
- src/styles/foundation.js:168 (--evcc-color-cleaning)
- src/styles/index.js:469
- src/styles/index.js:473
- src/styles/index.js:477
- src/styles/index.js:748
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
- src/styles/map.js:671 (color)
- src/styles/map.js:911
- src/styles/map.js:916
- src/styles/map.js:917 (color)
- src/styles/map.js:919
- src/styles/map.js:957
- src/styles/map.js:958 (color)
- src/styles/map.js:960
- src/styles/mapping-review.js:78
- src/styles/mapping-review.js:79 (color)
- src/styles/rooms.js:84
- src/styles/rooms.js:87
- src/styles/rooms.js:92
- src/styles/rooms.js:93
- src/styles/rooms.js:229
- src/styles/rooms.js:231
- src/styles/rooms.js:243
- src/styles/rooms.js:250
- src/styles/rooms.js:251
- src/styles/rooms.js:256
- src/styles/rooms.js:534
- src/styles/rooms.js:535
- src/styles/rooms.js:537
- src/styles/rooms.js:619
- src/styles/rooms.js:621
- src/styles/rooms.js:622
- src/styles/rooms.js:988
- src/styles/rooms.js:996
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
- src/styles/shell.js:259
- custom_components/eufy_vacuum/themes/preloaded.py:89
- custom_components/eufy_vacuum/themes/preloaded.py:90
- custom_components/eufy_vacuum/themes/preloaded.py:91
- custom_components/eufy_vacuum/themes/preloaded.py:93
- custom_components/eufy_vacuum/themes/preloaded.py:94
- custom_components/eufy_vacuum/themes/preloaded.py:95
- custom_components/eufy_vacuum/themes/preloaded.py:118
- custom_components/eufy_vacuum/themes/preloaded.py:119
- custom_components/eufy_vacuum/themes/preloaded.py:120
- custom_components/eufy_vacuum/themes/preloaded.py:139
- custom_components/eufy_vacuum/themes/preloaded.py:143
- custom_components/eufy_vacuum/themes/preloaded.py:144
- custom_components/eufy_vacuum/themes/preloaded.py:145
- custom_components/eufy_vacuum/themes/preloaded.py:156
- custom_components/eufy_vacuum/themes/preloaded.py:157
- custom_components/eufy_vacuum/themes/preloaded.py:158
- custom_components/eufy_vacuum/themes/preloaded.py:160
- custom_components/eufy_vacuum/themes/preloaded.py:174
- custom_components/eufy_vacuum/themes/preloaded.py:175
- custom_components/eufy_vacuum/themes/preloaded.py:176
- custom_components/eufy_vacuum/themes/preloaded.py:325
- custom_components/eufy_vacuum/themes/preloaded.py:378
- custom_components/eufy_vacuum/themes/preloaded.py:401
- custom_components/eufy_vacuum/themes/preloaded.py:424
- custom_components/eufy_vacuum/themes/preloaded.py:447

**`--evcc-sem-warning`** — Sem Warning · default src/styles/foundation.js:139
- src/styles/external-jobs.js:38
- src/styles/external-jobs.js:39
- src/styles/external-jobs.js:40 (color)
- src/styles/external-jobs.js:162 (color)
- src/styles/index.js:486
- src/styles/index.js:490
- src/styles/index.js:494
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
- src/styles/rooms.js:156
- src/styles/rooms.js:157
- src/styles/rooms.js:263
- src/styles/rooms.js:267
- src/styles/rooms.js:433
- src/styles/rooms.js:435
- src/styles/rooms.js:436
- src/styles/rooms.js:611
- src/styles/rooms.js:613
- src/styles/rooms.js:614
- src/styles/rooms.js:714 (--evcc-learning-warning-text)
- src/styles/rooms.js:838
- src/styles/rooms.js:846
- src/styles/rooms.js:847
- src/styles/setup.js:476
- src/styles/setup.js:477
- src/styles/setup.js:478
- src/styles/setup.js:563
- src/styles/shell.js:118
- src/styles/shell.js:132 (color)
- src/styles/theme-preview.js:455
- src/styles/theme-preview.js:456
- src/styles/theme-preview.js:457
- custom_components/eufy_vacuum/themes/preloaded.py:97
- custom_components/eufy_vacuum/themes/preloaded.py:98
- custom_components/eufy_vacuum/themes/preloaded.py:99
- custom_components/eufy_vacuum/themes/preloaded.py:136
- custom_components/eufy_vacuum/themes/preloaded.py:137
- custom_components/eufy_vacuum/themes/preloaded.py:138
- custom_components/eufy_vacuum/themes/preloaded.py:149
- custom_components/eufy_vacuum/themes/preloaded.py:150
- custom_components/eufy_vacuum/themes/preloaded.py:151
- custom_components/eufy_vacuum/themes/preloaded.py:165
- custom_components/eufy_vacuum/themes/preloaded.py:166
- custom_components/eufy_vacuum/themes/preloaded.py:179
- custom_components/eufy_vacuum/themes/preloaded.py:180
- custom_components/eufy_vacuum/themes/preloaded.py:181
- custom_components/eufy_vacuum/themes/preloaded.py:192
- custom_components/eufy_vacuum/themes/preloaded.py:221
- custom_components/eufy_vacuum/themes/preloaded.py:222
- custom_components/eufy_vacuum/themes/preloaded.py:223
- custom_components/eufy_vacuum/themes/preloaded.py:326
- custom_components/eufy_vacuum/themes/preloaded.py:401
- custom_components/eufy_vacuum/themes/preloaded.py:424
- custom_components/eufy_vacuum/themes/preloaded.py:447

**`--evcc-status-cleaning-bg`** — Status Cleaning BG · default —
- src/styles/rooms.js:230 (background)

**`--evcc-status-cleaning-border`** — Status Cleaning Border · default —
- src/styles/rooms.js:228

**`--evcc-status-cleaning-text`** — Status Cleaning Text · default —
- src/styles/rooms.js:243 (color)

**`--evcc-status-dot-charging`** — Status Dot Charging · default —
- src/styles/shell.js:121 (background)

**`--evcc-status-dot-cleaning`** — Status Dot Cleaning · default —
- src/styles/rooms.js:250 (background)
- src/styles/rooms.js:251
- src/styles/rooms.js:256
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
- src/styles/rooms.js:252
- src/styles/theme-preview.js:402

## Learning & Metrics  ·  37/37 consumed

**`--evcc-estimate-default-bg`** — Estimate Default BG · default src/styles/rooms.js:704
- src/styles/rooms.js:732 (background)
- src/styles/theme-preview.js:467 (background)

**`--evcc-estimate-default-border`** — Estimate Default Border · default src/styles/rooms.js:706
- src/styles/rooms.js:733 (border-color)
- src/styles/theme-preview.js:468 (border-color)

**`--evcc-estimate-default-text`** — Estimate Default Text · default src/styles/rooms.js:708
- src/styles/rooms.js:734 (color)
- src/styles/theme-preview.js:469 (color)

**`--evcc-estimate-learned-bg`** — Estimate Learned BG · default src/styles/rooms.js:697
- src/styles/rooms.js:726 (background)
- src/styles/theme-preview.js:473 (background)

**`--evcc-estimate-learned-border`** — Estimate Learned Border · default src/styles/rooms.js:699
- src/styles/rooms.js:727 (border-color)
- src/styles/theme-preview.js:474 (border-color)

**`--evcc-estimate-learned-text`** — Estimate Learned Text · default src/styles/rooms.js:701
- src/styles/rooms.js:728 (color)
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

**`--evcc-learning-note-text`** — Learning Note Text · default src/styles/rooms.js:711
- src/styles/rooms.js:764 (color)
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

**`--evcc-learning-warning-text`** — Learning Warning Text · default src/styles/rooms.js:713
- src/styles/rooms.js:768 (color)

## Modals & Overlays  ·  36/36 consumed

**`--evcc-modal-accent`** — Modal Accent · default —
- src/styles/index.js:219 (--evcc-accent)
- src/styles/index.js:375
- src/styles/index.js:380
- src/styles/index.js:385
- src/styles/modals.js:196
- src/styles/modals.js:201
- src/styles/modals.js:206
- src/styles/modals.js:214
- src/styles/modals.js:219
- src/styles/modals.js:223
- src/styles/theme-preview.js:530
- src/styles/theme-preview.js:531
- src/styles/theme-preview.js:532

**`--evcc-modal-accent-bg`** — Modal Accent BG · default —
- src/styles/index.js:374
- src/styles/modals.js:195
- src/styles/theme-preview.js:530 (background)
- custom_components/eufy_vacuum/themes/preloaded.py:203

**`--evcc-modal-accent-border`** — Modal Accent Border · default —
- src/styles/index.js:384
- src/styles/modals.js:205
- src/styles/theme-preview.js:531 (border-color)
- custom_components/eufy_vacuum/themes/preloaded.py:204

**`--evcc-modal-accent-text`** — Modal Accent Text · default —
- src/styles/index.js:379
- src/styles/modals.js:200
- src/styles/modals.js:218
- src/styles/theme-preview.js:532 (color)
- custom_components/eufy_vacuum/themes/preloaded.py:205

**`--evcc-modal-backdrop-bg`** — Modal Backdrop BG · default —
- src/styles/index.js:131 (background)
- src/styles/index.js:555 (background)
- src/styles/modals.js:77 (background)
- src/styles/modals.js:327 (background)
- src/styles/theme-preview.js:505 (background)

**`--evcc-modal-backdrop-blur`** — Modal Backdrop Blur · default —
- src/styles/index.js:135
- src/styles/modals.js:81
- src/styles/theme-preview.js:506

**`--evcc-modal-bg`** — Modal BG · default —
- src/styles/index.js:159 (background)
- src/styles/index.js:504 (background)
- src/styles/index.js:610 (background)
- src/styles/index.js:619 (background)
- src/styles/modals.js:96 (background)
- src/styles/modals.js:313 (background)
- src/styles/theme-preview.js:518 (background)

**`--evcc-modal-border`** — Modal Border · default —
- src/styles/index.js:163
- src/styles/index.js:508
- src/styles/modals.js:100
- src/styles/modals.js:317
- src/styles/theme-preview.js:519

**`--evcc-modal-border-default`** — Modal Border Default · default —
- src/styles/index.js:195 (--evcc-border-default)
- src/styles/index.js:529 (--evcc-border-default)

**`--evcc-modal-border-strong`** — Modal Border Strong · default —
- src/styles/index.js:203 (--evcc-border-strong)
- src/styles/index.js:537 (--evcc-border-strong)
- src/styles/modals.js:295

**`--evcc-modal-border-subtle`** — Modal Border Subtle · default —
- src/styles/index.js:199 (--evcc-border-subtle)
- src/styles/index.js:318
- src/styles/index.js:421
- src/styles/index.js:436
- src/styles/index.js:533 (--evcc-border-subtle)
- src/styles/index.js:621
- src/styles/modals.js:131
- src/styles/modals.js:180
- src/styles/room-estimate.js:38
- src/styles/room-estimate.js:60

**`--evcc-modal-chip-active-bg`** — Modal Chip Active BG · default —
- src/styles/index.js:373 (background)
- src/styles/modals.js:194 (background)

**`--evcc-modal-chip-active-border`** — Modal Chip Active Border · default —
- src/styles/index.js:383 (border-color)
- src/styles/modals.js:204 (border-color)

**`--evcc-modal-chip-active-text`** — Modal Chip Active Text · default —
- src/styles/index.js:378 (color)
- src/styles/modals.js:199 (color)

**`--evcc-modal-chip-bg`** — Modal Chip BG · default —
- src/styles/index.js:277 (--evcc-chip-bg)
- src/styles/index.js:392 (background)
- src/styles/modals.js:286 (background)

**`--evcc-modal-chip-border`** — Modal Chip Border · default —
- src/styles/index.js:273 (--evcc-chip-border)
- src/styles/index.js:401 (border-color)
- src/styles/modals.js:294 (border-color)

**`--evcc-modal-chip-hover-bg`** — Modal Chip Hover BG · default —
- src/styles/index.js:291 (--evcc-chip-hover-bg)
- src/styles/modals.js:213 (background)

**`--evcc-modal-chip-hover-border`** — Modal Chip Hover Border · default —
- src/styles/index.js:299 (--evcc-chip-hover-border)
- src/styles/modals.js:222 (border-color)

**`--evcc-modal-chip-hover-text`** — Modal Chip Hover Text · default —
- src/styles/index.js:295 (--evcc-chip-hover-text)
- src/styles/modals.js:217 (color)

**`--evcc-modal-chip-text`** — Modal Chip Text · default —
- src/styles/index.js:281 (--evcc-chip-text)
- src/styles/index.js:396 (color)
- src/styles/modals.js:290 (color)

**`--evcc-modal-footer-bg`** — Modal Footer BG · default —
- src/styles/index.js:425 (background)
- src/styles/modals.js:184 (background)

**`--evcc-modal-header-bg`** — Modal Header BG · default —
- src/styles/index.js:323 (background)
- src/styles/modals.js:136 (background)

**`--evcc-modal-input-bg`** — Modal Input BG · default —
- src/styles/index.js:186 (--evcc-surface-input)
- src/styles/index.js:524 (--evcc-surface-input)

**`--evcc-modal-padding`** — Modal Padding · default —
- src/styles/index.js:316 (padding)
- src/styles/index.js:346 (padding)
- src/styles/index.js:419 (padding)
- src/styles/modals.js:129 (padding)
- src/styles/modals.js:160 (padding)
- src/styles/modals.js:178 (padding)
- src/styles/theme-preview.js:517 (padding)

**`--evcc-modal-radius`** — Modal Radius · default —
- src/styles/index.js:167 (border-radius)
- src/styles/modals.js:103 (border-radius)
- src/styles/modals.js:339 (border-radius)
- src/styles/theme-preview.js:520 (border-radius)

**`--evcc-modal-section-gap`** — Modal Section Gap · default —
- src/styles/index.js:349 (gap)
- src/styles/modals.js:163 (gap)

**`--evcc-modal-shadow`** — Modal Shadow · default —
- src/styles/index.js:170 (box-shadow)
- src/styles/index.js:512 (box-shadow)
- src/styles/modals.js:106 (box-shadow)
- src/styles/modals.js:321 (box-shadow)
- src/styles/theme-preview.js:521 (box-shadow)

**`--evcc-modal-surface-input`** — Modal Surface Input · default —
- src/styles/index.js:187
- src/styles/index.js:525

**`--evcc-modal-surface-panel`** — Modal Surface Panel · default —
- src/styles/index.js:191 (--evcc-surface-panel)
- src/styles/index.js:520 (--evcc-surface-panel)
- src/styles/room-estimate.js:40
- src/styles/room-estimate.js:62

**`--evcc-modal-surface-section`** — Modal Surface Section · default —
- src/styles/modals.js:165 (background)

**`--evcc-modal-text-muted`** — Modal Text Muted · default —
- src/styles/index.js:215 (--evcc-text-muted)
- src/styles/index.js:362 (color)
- src/styles/index.js:393
- src/styles/index.js:457 (color)
- src/styles/index.js:549 (--evcc-text-muted)
- src/styles/modals.js:240 (color)
- src/styles/modals.js:287

**`--evcc-modal-text-primary`** — Modal Text Primary · default —
- src/styles/index.js:146 (color)
- src/styles/index.js:174 (color)
- src/styles/index.js:207 (--evcc-text-primary)
- src/styles/index.js:331 (color)
- src/styles/index.js:516 (color)
- src/styles/index.js:541 (--evcc-text-primary)
- src/styles/modals.js:117 (color)
- src/styles/modals.js:144 (color)
- src/styles/room-estimate.js:45 (color)

**`--evcc-modal-text-secondary`** — Modal Text Secondary · default —
- src/styles/index.js:211 (--evcc-text-secondary)
- src/styles/index.js:444 (color)
- src/styles/index.js:545 (--evcc-text-secondary)
- src/styles/modals.js:291
- src/styles/room-estimate.js:17 (color)
- src/styles/room-estimate.js:41 (color)
- src/styles/room-estimate.js:61 (color)

**`--evcc-modal-warning-bg`** — Modal Warning BG · default —
- src/styles/index.js:485 (background)
- src/styles/modals.js:258 (background)
- src/styles/theme-preview.js:455 (background)

**`--evcc-modal-warning-border`** — Modal Warning Border · default —
- src/styles/index.js:402
- src/styles/index.js:489
- src/styles/modals.js:262
- src/styles/theme-preview.js:456 (border-color)

**`--evcc-modal-warning-text`** — Modal Warning Text · default —
- src/styles/index.js:397
- src/styles/index.js:486
- src/styles/index.js:490
- src/styles/index.js:493 (color)
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
- src/styles/index.js:143 (font-family)
- src/styles/index.js:727 (font-family)
- src/styles/theme-preview.js:121 (font-family)

**`--evcc-gap`** — Gap · default src/styles/foundation.js:156
- src/styles/foundation.js:245 (gap)
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
- src/styles/rooms.js:310
- src/styles/rooms.js:596
- src/styles/theme-preview.js:229

**`--evcc-pad`** — Pad · default src/styles/foundation.js:157
- src/styles/foundation.js:246 (padding)
- src/styles/foundation.js:246
- src/styles/foundation.js:302 (padding)
- src/styles/theme-preview.js:182 (padding)

**`--evcc-press-scale`** — Press Scale · default —
- src/styles/rooms.js:606

**`--evcc-radius-card`** — Radius Card · default src/styles/foundation.js:147
- src/room-card.js:341 (--radius)
- src/styles/external-jobs.js:69 (border-radius)
- src/styles/external-jobs.js:142 (border-radius)
- src/styles/foundation.js:228 (border-radius)
- src/styles/learning.js:581 (border-radius)
- src/styles/map.js:73 (border-radius)
- src/styles/rooms.js:284 (border-radius)
- src/styles/shell.js:48 (border-radius)
- src/styles/theme-preview.js:36 (border-radius)
- src/styles/theme-preview.js:97 (border-radius)
- src/styles/theme-preview.js:174 (border-radius)
- src/styles/theme-preview.js:498 (border-radius)
- src/styles/theme-preview.js:563 (border-radius)
- src/styles/theme.js:115 (border-radius)
- src/styles/theme.js:230 (border-radius)
- src/styles/theme.js:250 (border-radius)
- src/styles/theme.js:309 (border-radius)

**`--evcc-radius-chip`** — Radius Chip · default src/styles/foundation.js:149
- src/styles/external-jobs.js:51 (border-radius)
- src/styles/foundation.js:284 (border-radius)
- src/styles/learning.js:57 (--evcc-learning-chip-radius)
- src/styles/order.js:59 (border-radius)
- src/styles/rooms.js:509 (border-radius)
- src/styles/shell.js:154 (border-radius)
- src/styles/theme-preview.js:163 (border-radius)
- src/styles/theme-preview.js:343 (border-radius)

**`--evcc-radius-inner`** — Radius Inner · default src/styles/foundation.js:148
- src/styles/base-station.js:21 (border-radius)
- src/styles/base-station.js:65 (border-radius)
- src/styles/external-jobs.js:24 (border-radius)
- src/styles/external-jobs.js:83 (border-radius)
- src/styles/external-jobs.js:99 (border-radius)
- src/styles/external-jobs.js:110 (border-radius)
- src/styles/external-jobs.js:121 (border-radius)
- src/styles/external-jobs.js:131 (border-radius)
- src/styles/external-jobs.js:152 (border-radius)
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
- src/styles/rooms.js:1108 (border-radius)
- src/styles/run-profiles.js:52 (border-radius)
- src/styles/run-profiles.js:82 (border-radius)
- src/styles/theme-preview.js:193 (border-radius)
- src/styles/theme-preview.js:205 (border-radius)
- src/styles/theme-preview.js:443 (border-radius)
- src/styles/theme.js:47 (border-radius)
- src/styles/theme.js:152 (border-radius)
- src/styles/theme.js:331 (border-radius)
- src/styles/theme.js:665 (border-radius)

**`--evcc-radius-panel`** — Radius Panel · default —
- src/styles/learning.js:231 (border-radius)
- src/styles/room-access.js:14 (border-radius)
- src/styles/rooms.js:155 (border-radius)
- src/styles/rooms.js:227 (border-radius)
- src/styles/rooms.js:685 (border-radius)
- src/styles/run-profiles.js:22 (border-radius)
- src/styles/theme-preview.js:184 (border-radius)

**`--evcc-section-gap`** — Section Gap · default —
- src/styles/rooms.js:47 (gap)
- src/styles/theme-preview.js:536 (gap)

**`--evcc-space-lg`** — Space Lg · default src/styles/foundation.js:154
- src/styles/foundation.js:157 (--evcc-pad)
- src/styles/shell.js:184 (padding)

**`--evcc-space-md`** — Space Md · default src/styles/foundation.js:153
- src/styles/foundation.js:156 (--evcc-gap)
- src/styles/rooms.js:48 (padding-bottom)
- src/styles/rooms.js:50 (margin-bottom)
- src/styles/rooms.js:57 (gap)
- src/styles/rooms.js:226 (margin-bottom)
- src/styles/rooms.js:1111 (margin-bottom)
- src/styles/theme.js:13 (gap)
- src/styles/theme.js:21 (gap)

**`--evcc-space-sm`** — Space Sm · default src/styles/foundation.js:152
- src/styles/rooms.js:755 (margin-top)
- src/styles/rooms.js:1106 (gap)

**`--evcc-transition-normal`** — Transition Normal · default src/styles/foundation.js:194, src/styles/index.js:222
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
- src/styles/rooms.js:289
- src/styles/rooms.js:290
- src/styles/rooms.js:291
- src/styles/rooms.js:292
- src/styles/rooms.js:587
- src/styles/rooms.js:588
- src/styles/rooms.js:589
- src/styles/rooms.js:590
- src/styles/rooms.js:591
- src/styles/rooms.js:592
- src/styles/shell.js:160
- src/styles/shell.js:161
- src/styles/theme.js:50 (transition)

---

## Tokens with no consumer  ·  116

Three kinds — only the last is a concern:

### Consumed dynamically — floor-texture presets  ·  32

Built at runtime as `var(--evcc-floor-${floorType}-…)` in `src/renderers/floor-texture-surface.js`. Working as intended.

`--evcc-floor-tile-base`, `--evcc-floor-tile-grout`, `--evcc-floor-tile-accent`, `--evcc-floor-tile-opacity-card`, `--evcc-floor-tile-face-opacity`, `--evcc-floor-tile-grout-opacity`, `--evcc-floor-tile-line-opacity`, `--evcc-floor-wood-base`, `--evcc-floor-wood-accent`, `--evcc-floor-wood-opacity-card`, `--evcc-floor-wood-depth-opacity`, `--evcc-floor-wood-grain-opacity`, `--evcc-floor-wood-seam-opacity`, `--evcc-floor-marble-base`, `--evcc-floor-marble-micro`, `--evcc-floor-marble-opacity-card`, `--evcc-floor-marble-base-opacity`, `--evcc-floor-marble-micro-opacity`, `--evcc-floor-concrete-base`, `--evcc-floor-concrete-accent`, `--evcc-floor-concrete-opacity-card`, `--evcc-floor-concrete-broad-opacity`, `--evcc-floor-concrete-micro-opacity`, `--evcc-floor-carpet-low-base`, `--evcc-floor-carpet-low-opacity-card`, `--evcc-floor-carpet-low-texture-opacity`, `--evcc-floor-carpet-high-base`, `--evcc-floor-carpet-high-opacity-card`, `--evcc-floor-carpet-high-texture-opacity`, `--evcc-floor-granite-light-base`, `--evcc-floor-granite-light-opacity-card`, `--evcc-floor-granite-light-texture-opacity`

### Per-animal palette (consumed dynamically in animal-svg/)  ·  84

The `--evcc-animal-*` tokens are referenced via dynamic `var()` in the shipped animal-svg module; per-animal `--evcc-animal-<name>-*` feed the active companion. Expected.

`--evcc-animal-eye-good`, `--evcc-animal-eye-mid`, `--evcc-animal-eye-warn`, `--evcc-animal-eye-low`, `--evcc-animal-eye-charging`, `--evcc-animal-fur`, `--evcc-animal-fur-shadow`, `--evcc-animal-fur-highlight`, `--evcc-animal-eye`, `--evcc-animal-pupil`, `--evcc-animal-nose`, `--evcc-animal-whisker`, `--evcc-animal-ear-inner`, `--evcc-animal-white-tip`, `--evcc-animal-cat-eye-good`, `--evcc-animal-cat-eye-mid`, `--evcc-animal-cat-eye-warn`, `--evcc-animal-cat-eye-low`, `--evcc-animal-cat-eye-charging`, `--evcc-animal-cat-fur`, `--evcc-animal-cat-fur-shadow`, `--evcc-animal-cat-fur-highlight`, `--evcc-animal-cat-eye`, `--evcc-animal-cat-pupil`, `--evcc-animal-cat-nose`, `--evcc-animal-cat-whisker`, `--evcc-animal-cat-ear-inner`, `--evcc-animal-cat-white-tip`, `--evcc-animal-dog-eye-good`, `--evcc-animal-dog-eye-mid`, `--evcc-animal-dog-eye-warn`, `--evcc-animal-dog-eye-low`, `--evcc-animal-dog-eye-charging`, `--evcc-animal-dog-fur`, `--evcc-animal-dog-fur-shadow`, `--evcc-animal-dog-fur-highlight`, `--evcc-animal-dog-eye`, `--evcc-animal-dog-pupil`, `--evcc-animal-dog-nose`, `--evcc-animal-dog-whisker`, `--evcc-animal-dog-ear-inner`, `--evcc-animal-dog-white-tip`, `--evcc-animal-raccoon-eye-good`, `--evcc-animal-raccoon-eye-mid`, `--evcc-animal-raccoon-eye-warn`, `--evcc-animal-raccoon-eye-low`, `--evcc-animal-raccoon-eye-charging`, `--evcc-animal-raccoon-fur`, `--evcc-animal-raccoon-fur-shadow`, `--evcc-animal-raccoon-fur-highlight`, `--evcc-animal-raccoon-eye`, `--evcc-animal-raccoon-pupil`, `--evcc-animal-raccoon-nose`, `--evcc-animal-raccoon-whisker`, `--evcc-animal-raccoon-ear-inner`, `--evcc-animal-raccoon-white-tip`, `--evcc-animal-parrot-eye-good`, `--evcc-animal-parrot-eye-mid`, `--evcc-animal-parrot-eye-warn`, `--evcc-animal-parrot-eye-low`, `--evcc-animal-parrot-eye-charging`, `--evcc-animal-parrot-fur`, `--evcc-animal-parrot-fur-shadow`, `--evcc-animal-parrot-fur-highlight`, `--evcc-animal-parrot-eye`, `--evcc-animal-parrot-pupil`, `--evcc-animal-parrot-nose`, `--evcc-animal-parrot-whisker`, `--evcc-animal-parrot-ear-inner`, `--evcc-animal-parrot-white-tip`, `--evcc-animal-snake-eye-good`, `--evcc-animal-snake-eye-mid`, `--evcc-animal-snake-eye-warn`, `--evcc-animal-snake-eye-low`, `--evcc-animal-snake-eye-charging`, `--evcc-animal-snake-fur`, `--evcc-animal-snake-fur-shadow`, `--evcc-animal-snake-fur-highlight`, `--evcc-animal-snake-eye`, `--evcc-animal-snake-pupil`, `--evcc-animal-snake-nose`, `--evcc-animal-snake-whisker`, `--evcc-animal-snake-ear-inner`, `--evcc-animal-snake-white-tip`

### Truly dead — no `var()` anywhere  ·  0

Seeded + exposed in the editor but nothing reads them — no-op editor knobs (wire them up or drop them).

None — every non-dynamic catalog token has a consumer.

---

## var() → non-catalog tokens  ·  2

Used in CSS but not in the editor registry (dynamic fragments or intentional internals like `--evcc-grp`).

- `--evcc-grp` — src/styles/map.js:604
- `--evcc-animal-X` — custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js:283

---

## dynamic var(--evcc-…${…}) sites  ·  3

- src/renderers/floor-texture-surface.js:97
- custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js:310
- custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js:311

