<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Source of truth: src/theme-tokens/ (the editor registry) + the card CSS.
     Regenerate after any token add/remove/rename:  node scripts/gen-theme-token-docs.mjs -->

# Theme Token CSS-Usage Trace

> Generated reference — part of the [Theme System](../frontend/theme-system.md) docs. Companion: [Theme Token Map](THEME_TOKEN_MAP.md).

For each catalog token (`--evcc-*`): its **default** declaration, every real **consumer** `var()` (CSS property + file:line), and JS `setProperty` apply sites. Multiline-aware (handles `var(` wrapped across lines); scans `src/`, the `animal-svg/` module, and the Python preloaded themes. The self-referential seed (`--evcc-x: var(--evcc-x, fallback)`) is the default, not a use.

- Catalog **408** · consumer `var()` uses **2324**
- **274** with a STATIC consumer · **134** consumed DYNAMICALLY (constructed names, below) · **0** with no consumer at all
- `var()` → non-catalog tokens **12** · dynamic `var(--evcc-…${…})` sites **3**

> **A token with no STATIC consumer is not dead.** This tracer is a regex scan and cannot follow a `var()` whose name is built at runtime, so 134 live tokens would otherwise read as rot — and deleting them would break theming for every animal, every floor material and the whole room palette. The families that construct their names:
> - **84** `animal` — `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`
> - **38** `floor-material` — `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key
> - **12** `room-fill` — `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)
- **Token CSS coverage 98.7%** — 1402/1420 color declarations resolve through a token (18 deliberate `theme-lint-ignore`, **0 stray**); **100.0%** of colors that should be themed. Scope: `src/styles/*` (minus token defs) + the standalone cards; guarded by `scripts/check-styles.mjs`.

---

## App Shell & Typography  ·  7 static / 7

**`--evcc-accent`** — Accent · default `var(--accent-color, #3b82f6)` src/styles/foundation.js:218, src/styles/modal-host.js:238
- custom_components/eufy_vacuum/themes/preloaded.py:82
- custom_components/eufy_vacuum/themes/preloaded.py:83
- custom_components/eufy_vacuum/themes/preloaded.py:84
- custom_components/eufy_vacuum/themes/preloaded.py:106
- custom_components/eufy_vacuum/themes/preloaded.py:107
- custom_components/eufy_vacuum/themes/preloaded.py:108
- custom_components/eufy_vacuum/themes/preloaded.py:113
- custom_components/eufy_vacuum/themes/preloaded.py:114
- custom_components/eufy_vacuum/themes/preloaded.py:115
- custom_components/eufy_vacuum/themes/preloaded.py:116
- custom_components/eufy_vacuum/themes/preloaded.py:117
- custom_components/eufy_vacuum/themes/preloaded.py:118
- custom_components/eufy_vacuum/themes/preloaded.py:125
- custom_components/eufy_vacuum/themes/preloaded.py:126
- custom_components/eufy_vacuum/themes/preloaded.py:127
- custom_components/eufy_vacuum/themes/preloaded.py:144
- custom_components/eufy_vacuum/themes/preloaded.py:163
- custom_components/eufy_vacuum/themes/preloaded.py:165
- custom_components/eufy_vacuum/themes/preloaded.py:175
- custom_components/eufy_vacuum/themes/preloaded.py:176
- custom_components/eufy_vacuum/themes/preloaded.py:177
- custom_components/eufy_vacuum/themes/preloaded.py:191
- custom_components/eufy_vacuum/themes/preloaded.py:192
- custom_components/eufy_vacuum/themes/preloaded.py:197
- custom_components/eufy_vacuum/themes/preloaded.py:198
- custom_components/eufy_vacuum/themes/preloaded.py:199
- custom_components/eufy_vacuum/themes/preloaded.py:200
- custom_components/eufy_vacuum/themes/preloaded.py:509
- src/cards/_shared.js:222 (color)
- src/cards/dashboard-card.js:1239 (--accent)
- src/cards/profile-card.js:35 (--accent)
- src/room-card.js:374 (--accent)
- src/styles/external-jobs.js:32
- src/styles/external-jobs.js:33
- src/styles/external-jobs.js:34 (color)
- src/styles/external-jobs.js:57
- src/styles/external-jobs.js:58
- src/styles/external-jobs.js:59 (color)
- src/styles/external-jobs.js:135 (color)
- src/styles/external-jobs.js:136
- src/styles/external-jobs.js:146 (color)
- src/styles/external-jobs.js:147
- src/styles/external-jobs.js:156 (color)
- src/styles/external-jobs.js:157
- src/styles/external-jobs.js:167 (color)
- src/styles/foundation.js:110
- src/styles/foundation.js:111
- src/styles/foundation.js:113
- src/styles/foundation.js:261 (--evcc-color-docked)
- src/styles/foundation.js:392
- src/styles/foundation.js:393 (color)
- src/styles/job-summary.js:42
- src/styles/job-summary.js:43
- src/styles/job-summary.js:127
- src/styles/job-summary.js:131
- src/styles/learning.js:154
- src/styles/learning.js:157
- src/styles/learning.js:178
- src/styles/learning.js:183
- src/styles/learning.js:188
- src/styles/learning.js:195
- src/styles/learning.js:198
- src/styles/learning.js:201
- src/styles/learning.js:207
- src/styles/learning.js:280
- src/styles/learning.js:281
- src/styles/learning.js:310 (color)
- src/styles/learning.js:371
- src/styles/learning.js:372
- src/styles/learning.js:373 (color)
- src/styles/learning.js:499
- src/styles/learning.js:505
- src/styles/maintenance.js:285
- src/styles/map.js:363 (background)
- src/styles/map.js:364 (border-color)
- src/styles/map.js:388
- src/styles/map.js:389
- src/styles/map.js:398
- src/styles/map.js:399
- src/styles/map.js:433
- src/styles/map.js:434
- src/styles/map.js:448 (background)
- src/styles/map.js:460
- src/styles/map.js:483 (background)
- src/styles/map.js:485 (border-color)
- src/styles/map.js:525 (background)
- src/styles/map.js:526 (border-color)
- src/styles/map.js:631 (background)
- src/styles/map.js:791 (background)
- src/styles/map.js:975 (background)
- src/styles/map.js:1129 (background)
- src/styles/map.js:1317 (color)
- src/styles/map.js:1346 (border-color)
- src/styles/map.js:1351 (border-color)
- src/styles/map.js:1379
- src/styles/map.js:1503
- src/styles/map.js:1505 (color)
- src/styles/map.js:1507
- src/styles/map.js:1513
- src/styles/map.js:1514 (color)
- src/styles/map.js:1690
- src/styles/map.js:1691 (color)
- src/styles/map.js:1693
- src/styles/map.js:1820 (accent-color)
- src/styles/metrics.js:192 (border-color)
- src/styles/mobile.js:181 (color)
- src/styles/mobile.js:281 (color)
- src/styles/mobile.js:283
- src/styles/modal-host.js:123 (--evcc-modal-accent)
- src/styles/modal-host.js:124 (--evcc-modal-accent-text)
- src/styles/modal-host.js:125
- src/styles/modal-host.js:126
- src/styles/modal-host.js:240
- src/styles/modal-host.js:432 (border-color)
- src/styles/modal-host.js:465
- src/styles/modal-host.js:470
- src/styles/modal-host.js:475
- src/styles/modal-host.js:811
- src/styles/modal-host.js:812
- src/styles/modal-host.js:818 (background)
- src/styles/modals.js:196
- src/styles/modals.js:201
- src/styles/modals.js:206
- src/styles/modals.js:214
- src/styles/modals.js:219
- src/styles/modals.js:223
- src/styles/modals.js:352
- src/styles/modals.js:353
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
- src/styles/rooms.js:409
- src/styles/rooms.js:413
- src/styles/rooms.js:417
- src/styles/rooms.js:427
- src/styles/rooms.js:432
- src/styles/rooms.js:472
- src/styles/rooms.js:669
- src/styles/rooms.js:670 (--evcc-chip-text)
- src/styles/rooms.js:671
- src/styles/rooms.js:720
- src/styles/rooms.js:819
- src/styles/rooms.js:821
- src/styles/rooms.js:948
- src/styles/rooms.js:949
- src/styles/rooms.js:1027
- src/styles/rooms.js:1028
- src/styles/rooms.js:1128
- src/styles/rooms.js:1129
- src/styles/rooms.js:1202
- src/styles/rooms.js:1224
- src/styles/rooms.js:1243
- src/styles/rooms.js:1244
- src/styles/rooms.js:1341
- src/styles/rooms.js:1376
- src/styles/rooms.js:1377
- src/styles/run-profiles.js:164
- src/styles/run-profiles.js:165
- src/styles/run-profiles.js:358
- src/styles/run-profiles.js:359
- src/styles/saved-zones.js:30
- src/styles/saved-zones.js:63 (background)
- src/styles/saved-zones.js:151 (border-color)
- src/styles/saved-zones.js:152
- src/styles/saved-zones.js:173 (accent-color)
- src/styles/saved-zones.js:232
- src/styles/saved-zones.js:233
- src/styles/setup.js:56 (background)
- src/styles/setup.js:103 (background)
- src/styles/setup.js:153
- src/styles/setup.js:154
- src/styles/setup.js:155 (color)
- src/styles/setup.js:411
- src/styles/setup.js:412 (border-color)
- src/styles/setup.js:413 (color)
- src/styles/setup.js:767 (border-color)
- src/styles/setup.js:838
- src/styles/setup.js:839
- src/styles/setup.js:840 (color)
- src/styles/shell.js:154
- src/styles/shell.js:157
- src/styles/shell.js:298
- src/styles/shell.js:303 (color)
- src/styles/shell.js:311 (color)
- src/styles/shell.js:371
- src/styles/shell.js:372 (color)
- src/styles/shell.js:482
- src/styles/theme-preview.js:105
- src/styles/theme-preview.js:154 (color)
- src/styles/theme-preview.js:164
- src/styles/theme-preview.js:165
- src/styles/theme-preview.js:272
- src/styles/theme-preview.js:282
- src/styles/theme-preview.js:589
- src/styles/theme-preview.js:637
- src/styles/theme-preview.js:638
- src/styles/theme-preview.js:639
- src/styles/theme.js:122
- src/styles/theme.js:123
- src/styles/theme.js:124 (color)
- src/styles/theme.js:143 (border-color)
- src/styles/theme.js:365
- src/styles/theme.js:366
- src/styles/theme.js:467 (color)
- src/styles/theme.js:477 (border-color)
- src/styles/theme.js:478
- src/styles/theme.js:542 (border-color)
- src/styles/theme.js:545
- src/styles/theme.js:578 (background)
- src/styles/theme.js:628 (color)
- src/styles/theme.js:629
- src/styles/theme.js:630
- src/styles/theme.js:650 (color)
- src/styles/theme.js:655 (border-color)
- src/styles/theme.js:721 (border-color)
- src/styles/theme.js:731 (color)
- src/styles/theme.js:739
- src/styles/theme.js:861 (border-color)
- src/styles/theme.js:894 (border-color)
- src/styles/theme.js:897
- src/styles/theme.js:1040
- src/styles/theme.js:1041 (color)
- src/styles/theme.js:1099
- src/styles/theme.js:1306
- src/styles/theme.js:1329
- src/styles/theme.js:1391
- src/styles/theme.js:1414
- src/styles/theme.js:1437 (border-color)
- src/styles/toast-host.js:82

**`--evcc-accent-soft`** — Accent Soft · default `rgba(0,229,255,0.16)` src/styles/foundation.js:219
- src/styles/map.js:1350 (background)
- src/styles/map.js:1378 (fill)
- src/styles/map.js:1386 (fill)

**`--evcc-text-muted`** — Text Muted · default `rgba(240,242,245,0.48)` src/styles/foundation.js:205, src/styles/modal-host.js:234, src/styles/modal-host.js:680
- custom_components/eufy_vacuum/themes/preloaded.py:168
- custom_components/eufy_vacuum/themes/preloaded.py:171
- custom_components/eufy_vacuum/themes/preloaded.py:193
- custom_components/eufy_vacuum/themes/preloaded.py:222
- src/cards/_shared.js:215 (color)
- src/cards/_shared.js:219 (color)
- src/cards/dashboard-card.js:1243 (--text-muted)
- src/cards/profile-card.js:40 (--text-muted)
- src/cards/vacuum-map-host.js:44 (color)
- src/room-card.js:378 (--text-muted)
- src/styles/base-station.js:88 (color)
- src/styles/learning.js:54 (--evcc-learning-text-muted)
- src/styles/learning.js:120
- src/styles/learning.js:121
- src/styles/learning.js:326 (color)
- src/styles/learning.js:716 (color)
- src/styles/learning.js:759 (color)
- src/styles/maintenance.js:226 (color)
- src/styles/maintenance.js:391 (color)
- src/styles/maintenance.js:445 (color)
- src/styles/map.js:41 (color)
- src/styles/map.js:1074 (color)
- src/styles/map.js:1155 (color)
- src/styles/map.js:1275 (color)
- src/styles/map.js:1286 (color)
- src/styles/map.js:1446 (color)
- src/styles/map.js:1463 (color)
- src/styles/map.js:1476 (color)
- src/styles/map.js:1609 (color)
- src/styles/map.js:1616 (color)
- src/styles/map.js:1637 (color)
- src/styles/map.js:1676 (color)
- src/styles/metrics.js:224 (color)
- src/styles/metrics.js:240 (color)
- src/styles/metrics.js:306 (color)
- src/styles/metrics.js:317 (color)
- src/styles/mobile.js:926 (color)
- src/styles/modal-host.js:120 (--evcc-modal-text-muted)
- src/styles/modal-host.js:452
- src/styles/modal-host.js:483
- src/styles/modal-host.js:551
- src/styles/modal-host.js:624 (--evcc-modal-text-muted)
- src/styles/modal-host.js:807 (color)
- src/styles/modals.js:241
- src/styles/modals.js:324
- src/styles/modals.js:334
- src/styles/modals.js:335
- src/styles/modals.js:336 (color)
- src/styles/modals.js:358
- src/styles/modals.js:359
- src/styles/modals.js:360 (color)
- src/styles/modals.js:366 (color)
- src/styles/modals.js:374
- src/styles/review.js:232 (color)
- src/styles/room-access.js:92 (color)
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
- src/styles/rooms.js:251
- src/styles/rooms.js:252
- src/styles/rooms.js:291 (color)
- src/styles/rooms.js:320 (color)
- src/styles/rooms.js:512 (color)
- src/styles/rooms.js:663
- src/styles/rooms.js:808 (color)
- src/styles/rooms.js:826
- src/styles/rooms.js:833 (--evcc-learning-note-text)
- src/styles/rooms.js:862 (color)
- src/styles/rooms.js:994 (color)
- src/styles/rooms.js:1382
- src/styles/rooms.js:1383
- src/styles/rooms.js:1421
- src/styles/rooms.js:1422
- src/styles/rooms.js:1429 (color)
- src/styles/rooms.js:1443 (color)
- src/styles/rooms.js:1444
- src/styles/run-profiles.js:82 (color)
- src/styles/run-profiles.js:141 (color)
- src/styles/run-profiles.js:235 (color)
- src/styles/run-profiles.js:324 (color)
- src/styles/run-profiles.js:346 (color)
- src/styles/run-profiles.js:381 (color)
- src/styles/run-profiles.js:386 (color)
- src/styles/run-profiles.js:405 (color)
- src/styles/saved-zones.js:68 (color)
- src/styles/saved-zones.js:103 (color)
- src/styles/saved-zones.js:133 (color)
- src/styles/saved-zones.js:187 (color)
- src/styles/setup.js:90 (color)
- src/styles/setup.js:186 (color)
- src/styles/setup.js:204 (color)
- src/styles/setup.js:315 (color)
- src/styles/setup.js:372 (color)
- src/styles/setup.js:566
- src/styles/setup.js:578 (color)
- src/styles/setup.js:645
- src/styles/setup.js:660 (color)
- src/styles/setup.js:691 (color)
- src/styles/setup.js:703 (color)
- src/styles/setup.js:708 (color)
- src/styles/setup.js:724 (color)
- src/styles/setup.js:913 (color)
- src/styles/shell.js:136 (color)
- src/styles/shell.js:149
- src/styles/shell.js:159
- src/styles/shell.js:160
- src/styles/shell.js:164 (color)
- src/styles/shell.js:276 (color)
- src/styles/shell.js:331 (color)
- src/styles/shell.js:421 (color)
- src/styles/shell.js:493 (color)
- src/styles/theme-preview.js:51 (color)
- src/styles/theme-preview.js:117 (color)
- src/styles/theme-preview.js:149 (color)
- src/styles/theme-preview.js:196 (color)
- src/styles/theme-preview.js:725 (color)
- src/styles/theme-preview.js:748 (color)
- src/styles/theme.js:149 (color)
- src/styles/theme.js:166 (color)
- src/styles/theme.js:355 (color)
- src/styles/theme.js:378 (color)
- src/styles/theme.js:502 (color)
- src/styles/theme.js:556 (color)
- src/styles/theme.js:641 (color)
- src/styles/theme.js:690 (color)
- src/styles/theme.js:837 (color)
- src/styles/theme.js:980 (color)
- src/styles/theme.js:998 (color)
- src/styles/theme.js:1502 (color)
- src/styles/toast-host.js:90 (color)

**`--evcc-text-on-accent`** — Text On Accent · default `#ffffff` src/styles/foundation.js:207
- src/cards/dashboard-card.js:1305 (color)
- src/cards/dashboard-card.js:1320 (color)
- src/cards/profile-card.js:42 (--text-on-accent)
- src/room-card.js:381 (--text-on-accent)
- src/styles/map.js:365 (color)
- src/styles/map.js:449 (color)
- src/styles/map.js:484 (color)
- src/styles/map.js:527 (color)
- src/styles/map.js:630 (color)
- src/styles/map.js:974 (color)
- src/styles/map.js:1541 (color)
- src/styles/modal-host.js:819 (color)
- src/styles/saved-zones.js:62 (color)
- src/styles/setup.js:57 (color)
- src/styles/setup.js:104 (color)
- src/styles/setup.js:367 (color)
- src/styles/setup.js:432 (color)

**`--evcc-text-primary`** — Text Primary · default `var(--primary-text-color, #f0f2f5)` src/styles/foundation.js:203, src/styles/modal-host.js:226, src/styles/modal-host.js:672
- custom_components/eufy_vacuum/themes/preloaded.py:92
- custom_components/eufy_vacuum/themes/preloaded.py:130
- custom_components/eufy_vacuum/themes/preloaded.py:194
- custom_components/eufy_vacuum/themes/preloaded.py:214
- custom_components/eufy_vacuum/themes/preloaded.py:223
- src/cards/_shared.js:216 (color)
- src/cards/_shared.js:220 (color)
- src/cards/dashboard-card.js:1242 (--text-primary)
- src/cards/profile-card.js:39 (--text-primary)
- src/room-card.js:377 (--text-primary)
- src/styles/base-station.js:40 (color)
- src/styles/base-station.js:75 (color)
- src/styles/external-jobs.js:23 (color)
- src/styles/external-jobs.js:71 (color)
- src/styles/external-jobs.js:109 (color)
- src/styles/external-jobs.js:166 (color)
- src/styles/external-jobs.js:172 (color)
- src/styles/external-jobs.js:182 (color)
- src/styles/foundation.js:104
- src/styles/foundation.js:136 (color)
- src/styles/foundation.js:278 (--evcc-chip-hover-text)
- src/styles/foundation.js:388 (color)
- src/styles/learning.js:48 (--evcc-learning-text-primary)
- src/styles/learning.js:658 (color)
- src/styles/learning.js:694 (color)
- src/styles/learning.js:729 (color)
- src/styles/learning.js:808 (color)
- src/styles/learning.js:822 (color)
- src/styles/maintenance.js:58 (color)
- src/styles/maintenance.js:113 (color)
- src/styles/maintenance.js:119 (color)
- src/styles/maintenance.js:192 (color)
- src/styles/maintenance.js:218 (color)
- src/styles/maintenance.js:341 (color)
- src/styles/maintenance.js:358 (color)
- src/styles/maintenance.js:418 (color)
- src/styles/map.js:62 (color)
- src/styles/map.js:479 (color)
- src/styles/map.js:645 (color)
- src/styles/map.js:1147 (color)
- src/styles/map.js:1219 (color)
- src/styles/map.js:1225 (color)
- src/styles/map.js:1328 (color)
- src/styles/map.js:1352 (color)
- src/styles/map.js:1441 (color)
- src/styles/map.js:1498 (color)
- src/styles/map.js:1737 (color)
- src/styles/map.js:1803 (color)
- src/styles/map.js:1808 (color)
- src/styles/metrics.js:46 (color)
- src/styles/metrics.js:103 (color)
- src/styles/metrics.js:109 (color)
- src/styles/metrics.js:184 (color)
- src/styles/metrics.js:331 (color)
- src/styles/mobile.js:95 (color)
- src/styles/mobile.js:117 (color)
- src/styles/mobile.js:269 (color)
- src/styles/modal-host.js:118 (--evcc-modal-text-primary)
- src/styles/modal-host.js:134 (--evcc-modal-chip-hover-text)
- src/styles/modal-host.js:167
- src/styles/modal-host.js:195
- src/styles/modal-host.js:347
- src/styles/modal-host.js:383
- src/styles/modal-host.js:421 (color)
- src/styles/modal-host.js:622 (--evcc-modal-text-primary)
- src/styles/modal-host.js:631 (--evcc-modal-chip-hover-text)
- src/styles/modal-host.js:813 (color)
- src/styles/modals.js:118
- src/styles/modals.js:145
- src/styles/modals.js:354 (color)
- src/styles/order.js:100
- src/styles/review.js:40 (color)
- src/styles/review.js:140 (color)
- src/styles/review.js:213 (color)
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
- src/styles/rooms.js:269 (color)
- src/styles/rooms.js:310 (color)
- src/styles/rooms.js:483 (color)
- src/styles/rooms.js:539
- src/styles/rooms.js:756
- src/styles/rooms.js:763
- src/styles/rooms.js:823 (--evcc-estimate-learned-text)
- src/styles/rooms.js:1053 (color)
- src/styles/rooms.js:1077 (color)
- src/styles/rooms.js:1130 (color)
- src/styles/rooms.js:1378 (--evcc-chip-text)
- src/styles/run-profiles.js:44 (color)
- src/styles/run-profiles.js:68 (color)
- src/styles/run-profiles.js:92 (color)
- src/styles/run-profiles.js:221 (color)
- src/styles/run-profiles.js:246 (color)
- src/styles/run-profiles.js:331 (color)
- src/styles/run-profiles.js:337 (color)
- src/styles/saved-zones.js:46 (color)
- src/styles/saved-zones.js:180 (color)
- src/styles/saved-zones.js:204 (color)
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
- src/styles/setup.js:655 (color)
- src/styles/setup.js:684 (color)
- src/styles/setup.js:745 (color)
- src/styles/setup.js:761 (color)
- src/styles/setup.js:793 (color)
- src/styles/setup.js:823 (color)
- src/styles/setup.js:908 (color)
- src/styles/setup.js:946 (color)
- src/styles/shell.js:87 (color)
- src/styles/shell.js:117 (color)
- src/styles/shell.js:223 (color)
- src/styles/shell.js:228 (color)
- src/styles/shell.js:299 (color)
- src/styles/shell.js:367 (color)
- src/styles/shell.js:465 (color)
- src/styles/shell.js:501 (color)
- src/styles/theme-preview.js:57 (color)
- src/styles/theme-preview.js:124 (color)
- src/styles/theme-preview.js:131 (color)
- src/styles/theme-preview.js:207 (color)
- src/styles/theme-preview.js:299 (color)
- src/styles/theme-preview.js:305
- src/styles/theme-preview.js:442
- src/styles/theme-preview.js:459
- src/styles/theme-preview.js:716 (color)
- src/styles/theme.js:96 (color)
- src/styles/theme.js:103 (color)
- src/styles/theme.js:158 (color)
- src/styles/theme.js:374 (color)
- src/styles/theme.js:593 (color)
- src/styles/theme.js:716 (color)
- src/styles/theme.js:825 (color)
- src/styles/theme.js:854 (color)
- src/styles/theme.js:912 (color)
- src/styles/theme.js:1187 (color)
- src/styles/theme.js:1429 (color)
- src/styles/toast-host.js:72 (color)
- src/styles/toast-host.js:97 (color)

**`--evcc-text-secondary`** — Text Secondary · default `var(--secondary-text-color, rgba(240,242,245,0.72))` src/styles/foundation.js:204, src/styles/modal-host.js:230, src/styles/modal-host.js:676
- custom_components/eufy_vacuum/themes/preloaded.py:100
- custom_components/eufy_vacuum/themes/preloaded.py:109
- custom_components/eufy_vacuum/themes/preloaded.py:112
- custom_components/eufy_vacuum/themes/preloaded.py:121
- custom_components/eufy_vacuum/themes/preloaded.py:136
- custom_components/eufy_vacuum/themes/preloaded.py:139
- custom_components/eufy_vacuum/themes/preloaded.py:146
- custom_components/eufy_vacuum/themes/preloaded.py:167
- custom_components/eufy_vacuum/themes/preloaded.py:174
- custom_components/eufy_vacuum/themes/preloaded.py:187
- custom_components/eufy_vacuum/themes/preloaded.py:188
- custom_components/eufy_vacuum/themes/preloaded.py:195
- custom_components/eufy_vacuum/themes/preloaded.py:215
- custom_components/eufy_vacuum/themes/preloaded.py:224
- src/styles/base-station.js:46 (color)
- src/styles/base-station.js:82 (color)
- src/styles/external-jobs.js:50 (color)
- src/styles/external-jobs.js:62 (color)
- src/styles/external-jobs.js:72 (color)
- src/styles/external-jobs.js:126 (color)
- src/styles/external-jobs.js:127 (color)
- src/styles/external-jobs.js:131 (color)
- src/styles/external-jobs.js:142 (color)
- src/styles/external-jobs.js:152 (color)
- src/styles/external-jobs.js:168 (color)
- src/styles/external-jobs.js:169 (color)
- src/styles/foundation.js:47
- src/styles/foundation.js:263 (--evcc-color-idle)
- src/styles/foundation.js:275 (--evcc-chip-text)
- src/styles/foundation.js:354 (color)
- src/styles/foundation.js:370 (color)
- src/styles/foundation.js:382 (color)
- src/styles/job-summary.js:31 (color)
- src/styles/job-summary.js:44 (color)
- src/styles/job-summary.js:64 (color)
- src/styles/job-summary.js:101 (color)
- src/styles/learning.js:51 (--evcc-learning-text-secondary)
- src/styles/learning.js:115 (--evcc-learning-confidence-neutral-text)
- src/styles/learning.js:678 (color)
- src/styles/learning.js:813 (color)
- src/styles/maintenance.js:52 (color)
- src/styles/maintenance.js:63 (color)
- src/styles/maintenance.js:90 (color)
- src/styles/maintenance.js:178
- src/styles/maintenance.js:186 (color)
- src/styles/maintenance.js:198 (color)
- src/styles/maintenance.js:352 (color)
- src/styles/maintenance.js:364 (color)
- src/styles/maintenance.js:376 (color)
- src/styles/maintenance.js:384 (color)
- src/styles/maintenance.js:423 (color)
- src/styles/maintenance.js:431 (color)
- src/styles/maintenance.js:437 (color)
- src/styles/map.js:54 (color)
- src/styles/map.js:1067 (color)
- src/styles/map.js:1209 (color)
- src/styles/map.js:1292 (color)
- src/styles/map.js:1312 (color)
- src/styles/map.js:1338 (color)
- src/styles/map.js:1486 (color)
- src/styles/map.js:1590 (color)
- src/styles/map.js:1644 (color)
- src/styles/map.js:1685 (color)
- src/styles/map.js:1727 (color)
- src/styles/map.js:1791 (color)
- src/styles/metrics.js:53 (color)
- src/styles/metrics.js:143 (color)
- src/styles/mobile.js:107 (color)
- src/styles/mobile.js:169 (color)
- src/styles/mobile.js:919 (color)
- src/styles/modal-host.js:119 (--evcc-modal-text-secondary)
- src/styles/modal-host.js:131 (--evcc-modal-chip-text)
- src/styles/modal-host.js:333
- src/styles/modal-host.js:412 (color)
- src/styles/modal-host.js:488
- src/styles/modal-host.js:538
- src/styles/modal-host.js:623 (--evcc-modal-text-secondary)
- src/styles/modal-host.js:628 (--evcc-modal-chip-text)
- src/styles/modal-host.js:793 (color)
- src/styles/modals.js:378
- src/styles/order.js:56
- src/styles/review.js:46 (color)
- src/styles/review.js:148 (color)
- src/styles/review.js:195 (color)
- src/styles/room-access.js:22 (color)
- src/styles/room-estimate.js:17
- src/styles/room-estimate.js:41
- src/styles/room-estimate.js:61
- src/styles/room-rules.js:42 (color)
- src/styles/room-rules.js:187 (color)
- src/styles/room-rules.js:379 (color)
- src/styles/rooms.js:253 (--evcc-chip-active-text)
- src/styles/rooms.js:277 (color)
- src/styles/rooms.js:314 (color)
- src/styles/rooms.js:533
- src/styles/rooms.js:621 (color)
- src/styles/rooms.js:664
- src/styles/rooms.js:699
- src/styles/rooms.js:721
- src/styles/rooms.js:749
- src/styles/rooms.js:770
- src/styles/rooms.js:777
- src/styles/rooms.js:830 (--evcc-estimate-default-text)
- src/styles/rooms.js:929 (color)
- src/styles/rooms.js:1009 (color)
- src/styles/rooms.js:1105 (color)
- src/styles/rooms.js:1384 (--evcc-chip-text)
- src/styles/run-profiles.js:50 (color)
- src/styles/run-profiles.js:101 (color)
- src/styles/run-profiles.js:111 (color)
- src/styles/run-profiles.js:127 (color)
- src/styles/run-profiles.js:204 (color)
- src/styles/run-profiles.js:216 (color)
- src/styles/run-profiles.js:266 (color)
- src/styles/run-profiles.js:309 (color)
- src/styles/saved-zones.js:53 (color)
- src/styles/saved-zones.js:113 (color)
- src/styles/saved-zones.js:238 (color)
- src/styles/setup.js:28 (color)
- src/styles/setup.js:79 (color)
- src/styles/setup.js:124 (color)
- src/styles/setup.js:405 (color)
- src/styles/setup.js:500 (color)
- src/styles/setup.js:830 (color)
- src/styles/setup.js:844 (color)
- src/styles/setup.js:927 (color)
- src/styles/shell.js:128 (color)
- src/styles/shell.js:213 (color)
- src/styles/shell.js:289 (color)
- src/styles/shell.js:358 (color)
- src/styles/theme-preview.js:63 (color)
- src/styles/theme-preview.js:144 (color)
- src/styles/theme-preview.js:317
- src/styles/theme-preview.js:466
- src/styles/theme-preview.js:499 (color)
- src/styles/theme-preview.js:732 (color)
- src/styles/theme.js:72 (color)
- src/styles/theme.js:174 (color)
- src/styles/theme.js:298 (color)
- src/styles/theme.js:325 (color)
- src/styles/theme.js:394 (color)
- src/styles/theme.js:614 (color)
- src/styles/theme.js:682 (color)
- src/styles/theme.js:876 (color)
- src/styles/theme.js:1261 (color)

**`--evcc-text-strong`** — Text Strong · default `var(--primary-text-color, #f0f2f5)` src/styles/foundation.js:206
- src/styles/learning.js:751 (color)
- src/styles/metrics.js:234 (color)

## Cards & Surfaces  ·  19 static / 19

**`--evcc-bg-input`** — BG Input · default `var(--evcc-surface-input)` src/styles/foundation.js:257
- src/styles/theme-preview.js:194

**`--evcc-card-bg`** — Card BG · default `var(--evcc-surface-card)` src/styles/foundation.js:255
- src/styles/theme-preview.js:34
- src/styles/theme-preview.js:173
- src/styles/theme-preview.js:206
- src/styles/theme-preview.js:275

**`--evcc-card-gap`** — Card Gap · default —
- src/styles/rooms.js:387 (gap)

**`--evcc-card-min-height`** — Card Min Height · default —
- src/styles/rooms.js:388 (min-height)
- src/styles/theme-preview.js:94 (min-height)

**`--evcc-card-padding`** — Card Padding · default —
- src/styles/rooms.js:389 (padding)
- src/styles/theme-preview.js:93 (padding)
- src/styles/theme-preview.js:172 (padding)

**`--evcc-panel-bg`** — Panel BG · default `var(--evcc-surface-panel)` src/styles/foundation.js:256
- src/styles/run-profiles.js:28
- src/styles/saved-zones.js:17
- src/styles/theme-preview.js:95
- src/styles/theme-preview.js:108
- src/styles/theme-preview.js:183
- src/styles/theme-preview.js:668

**`--evcc-surface-action`** — Surface Action · default `rgba(255,255,255,0.10)` src/styles/foundation.js:188
- src/styles/learning.js:693 (background)
- src/styles/learning.js:821 (background)
- src/styles/map.js:246 (background)
- src/styles/map.js:278 (background)
- src/styles/map.js:321 (background)
- src/styles/map.js:518 (background)
- src/styles/map.js:601 (background)

**`--evcc-surface-action-hover`** — Surface Action Hover · default `rgba(255,255,255,0.18)` src/styles/foundation.js:189
- src/cards/_shared.js:221 (background)
- src/cards/dashboard-card.js:1290 (background)
- src/room-card.js:489 (background)
- src/styles/learning.js:703 (background)
- src/styles/learning.js:831 (background)
- src/styles/map.js:256 (background)
- src/styles/map.js:285 (background)
- src/styles/map.js:326 (background)
- src/styles/map.js:522 (background)
- src/styles/map.js:646 (background)
- src/styles/setup.js:418 (background)

**`--evcc-surface-base`** — Surface Base · default `var(--card-background-color, #1c2127)` src/styles/foundation.js:179
- custom_components/eufy_vacuum/themes/preloaded.py:74
- custom_components/eufy_vacuum/themes/preloaded.py:202
- src/styles/foundation.js:180 (--evcc-surface-card)
- src/styles/foundation.js:181
- src/styles/foundation.js:182
- src/styles/modal-host.js:99 (--evcc-modal-bg)
- src/styles/modal-host.js:607 (--evcc-modal-bg)
- src/styles/theme.js:564 (background)
- src/styles/theme.js:1304 (background)
- src/styles/theme.js:1307
- src/styles/theme.js:1327 (background)
- src/styles/theme.js:1330
- src/styles/theme.js:1389 (background)
- src/styles/theme.js:1392
- src/styles/theme.js:1412 (background)
- src/styles/theme.js:1415

**`--evcc-surface-card`** — Surface Card · default `var(--evcc-surface-base)` src/styles/foundation.js:180
- custom_components/eufy_vacuum/themes/preloaded.py:71
- src/cards/_shared.js:218 (background)
- src/cards/dashboard-card.js:1240 (--surface)
- src/cards/profile-card.js:36 (--surface)
- src/room-card.js:375 (--surface)
- src/styles/foundation.js:255 (--evcc-card-bg)
- src/styles/rooms.js:392
- src/styles/rooms.js:414
- src/styles/rooms.js:582
- src/styles/rooms.js:589 (background-color)
- src/styles/rooms.js:602
- src/styles/rooms.js:611
- src/styles/rooms.js:612
- src/styles/rooms.js:613
- src/styles/rooms.js:631 (background-color)
- src/styles/setup.js:759 (background)
- src/styles/shell.js:47 (background)
- src/styles/theme-preview.js:34 (background)
- src/styles/theme-preview.js:173 (background)
- src/styles/theme-preview.js:206 (background)
- src/styles/theme-preview.js:275
- src/styles/theme.js:524 (background)
- src/styles/theme.js:546
- src/styles/theme.js:1186 (background)

**`--evcc-surface-chip`** — Surface Chip · default `rgba(255,255,255,0.09)` src/styles/foundation.js:187
- src/styles/learning.js:674 (background)
- src/styles/learning.js:728 (background)
- src/styles/learning.js:781 (background)

**`--evcc-surface-input`** — Surface Input · default `rgba(255,255,255,0.06)` src/styles/foundation.js:183, src/styles/modal-host.js:205, src/styles/modal-host.js:655
- custom_components/eufy_vacuum/themes/preloaded.py:70
- custom_components/eufy_vacuum/themes/preloaded.py:85
- custom_components/eufy_vacuum/themes/preloaded.py:104
- custom_components/eufy_vacuum/themes/preloaded.py:119
- custom_components/eufy_vacuum/themes/preloaded.py:137
- custom_components/eufy_vacuum/themes/preloaded.py:172
- custom_components/eufy_vacuum/themes/preloaded.py:210
- custom_components/eufy_vacuum/themes/preloaded.py:218
- custom_components/eufy_vacuum/themes/preloaded.py:219
- src/cards/profile-card.js:37 (--surface-input)
- src/styles/external-jobs.js:22 (background)
- src/styles/external-jobs.js:122 (background)
- src/styles/external-jobs.js:171 (background)
- src/styles/foundation.js:46
- src/styles/foundation.js:257 (--evcc-bg-input)
- src/styles/foundation.js:273 (--evcc-chip-bg)
- src/styles/maintenance.js:177
- src/styles/map.js:51 (background)
- src/styles/map.js:60 (background)
- src/styles/map.js:1101 (background)
- src/styles/map.js:1217 (background)
- src/styles/map.js:1327 (background)
- src/styles/map.js:1496 (background)
- src/styles/map.js:1598 (background)
- src/styles/map.js:1604 (background)
- src/styles/map.js:1684 (background)
- src/styles/map.js:1735 (background)
- src/styles/metrics.js:185 (background)
- src/styles/modal-host.js:108 (--evcc-modal-surface-input)
- src/styles/modal-host.js:110 (--evcc-modal-input-bg)
- src/styles/modal-host.js:129 (--evcc-modal-chip-bg)
- src/styles/modal-host.js:329
- src/styles/modal-host.js:422 (background)
- src/styles/modal-host.js:615 (--evcc-modal-surface-input)
- src/styles/modal-host.js:617 (--evcc-modal-input-bg)
- src/styles/modal-host.js:626 (--evcc-modal-chip-bg)
- src/styles/order.js:50
- src/styles/review.js:194 (background)
- src/styles/room-rules.js:52 (background)
- src/styles/room-rules.js:57 (background)
- src/styles/room-rules.js:119 (background)
- src/styles/room-rules.js:212 (background)
- src/styles/room-rules.js:237 (background)
- src/styles/room-rules.js:300 (background)
- src/styles/room-rules.js:336 (background)
- src/styles/room-rules.js:388 (background)
- src/styles/rooms.js:579
- src/styles/rooms.js:580
- src/styles/rooms.js:599
- src/styles/rooms.js:600
- src/styles/rooms.js:697
- src/styles/rooms.js:718
- src/styles/rooms.js:747
- src/styles/rooms.js:754
- src/styles/rooms.js:761
- src/styles/rooms.js:768
- src/styles/rooms.js:775
- src/styles/rooms.js:810
- src/styles/rooms.js:903
- src/styles/rooms.js:910
- src/styles/rooms.js:917
- src/styles/rooms.js:1076 (background)
- src/styles/run-profiles.js:61
- src/styles/run-profiles.js:91 (background)
- src/styles/run-profiles.js:160
- src/styles/run-profiles.js:205
- src/styles/run-profiles.js:236
- src/styles/run-profiles.js:245 (background)
- src/styles/run-profiles.js:265 (background)
- src/styles/run-profiles.js:325
- src/styles/run-profiles.js:347
- src/styles/saved-zones.js:95
- src/styles/saved-zones.js:146
- src/styles/saved-zones.js:152
- src/styles/saved-zones.js:203 (background)
- src/styles/setup.js:42 (background)
- src/styles/setup.js:123 (background)
- src/styles/setup.js:174 (background)
- src/styles/setup.js:270 (background)
- src/styles/setup.js:335 (background)
- src/styles/setup.js:371 (background)
- src/styles/setup.js:404 (background)
- src/styles/setup.js:515 (background)
- src/styles/setup.js:738 (background)
- src/styles/setup.js:786 (background)
- src/styles/setup.js:945 (background)
- src/styles/theme-preview.js:194 (background)
- src/styles/theme.js:134 (background)
- src/styles/theme.js:615 (background)
- src/styles/theme.js:683 (background)
- src/styles/theme.js:715 (background)
- src/styles/theme.js:851 (background)
- src/styles/theme.js:1088 (background)
- src/styles/theme.js:1425 (background)

**`--evcc-surface-overlay`** — Surface Overlay · default `rgba(0,0,0,0.4)` src/styles/foundation.js:184
- custom_components/eufy_vacuum/themes/preloaded.py:201
- src/styles/mobile.js:229 (background)
- src/styles/modal-host.js:100 (--evcc-modal-backdrop-bg)
- src/styles/modal-host.js:608 (--evcc-modal-backdrop-bg)

**`--evcc-surface-panel`** — Surface Panel · default `color-mix(in srgb, var(--evcc-surface-base) 85%, white 15%)` src/styles/foundation.js:181, src/styles/modal-host.js:210, src/styles/modal-host.js:651
- custom_components/eufy_vacuum/themes/preloaded.py:72
- custom_components/eufy_vacuum/themes/preloaded.py:90
- custom_components/eufy_vacuum/themes/preloaded.py:110
- custom_components/eufy_vacuum/themes/preloaded.py:128
- custom_components/eufy_vacuum/themes/preloaded.py:189
- custom_components/eufy_vacuum/themes/preloaded.py:212
- custom_components/eufy_vacuum/themes/preloaded.py:216
- custom_components/eufy_vacuum/themes/preloaded.py:217
- custom_components/eufy_vacuum/themes/preloaded.py:220
- custom_components/eufy_vacuum/themes/preloaded.py:429
- src/styles/base-station.js:23 (background)
- src/styles/external-jobs.js:29 (background)
- src/styles/external-jobs.js:181 (background)
- src/styles/foundation.js:103
- src/styles/foundation.js:135 (background)
- src/styles/foundation.js:256 (--evcc-panel-bg)
- src/styles/foundation.js:277 (--evcc-chip-hover-bg)
- src/styles/learning.js:39 (--evcc-learning-panel-bg)
- src/styles/maintenance.js:150 (background)
- src/styles/map.js:94 (background)
- src/styles/map.js:427 (background)
- src/styles/map.js:500 (background)
- src/styles/map.js:554 (background)
- src/styles/map.js:992 (background)
- src/styles/map.js:1087 (background)
- src/styles/map.js:1116 (background)
- src/styles/map.js:1807 (background)
- src/styles/metrics.js:29 (background)
- src/styles/mobile.js:72 (background)
- src/styles/mobile.js:138 (background)
- src/styles/mobile.js:245 (background)
- src/styles/modal-host.js:107 (--evcc-modal-surface-panel)
- src/styles/modal-host.js:114
- src/styles/modal-host.js:115
- src/styles/modal-host.js:132 (--evcc-modal-chip-hover-bg)
- src/styles/modal-host.js:343
- src/styles/modal-host.js:614 (--evcc-modal-surface-panel)
- src/styles/modal-host.js:619
- src/styles/modal-host.js:620
- src/styles/modal-host.js:629 (--evcc-modal-chip-hover-bg)
- src/styles/order.js:99
- src/styles/review.js:23 (background)
- src/styles/review.js:112
- src/styles/review.js:221
- src/styles/room-access.js:16
- src/styles/room-estimate.js:40
- src/styles/room-estimate.js:62
- src/styles/room-rules.js:282 (background)
- src/styles/run-profiles.js:28 (background)
- src/styles/saved-zones.js:17 (background)
- src/styles/setup.js:890 (background)
- src/styles/shell.js:88 (background)
- src/styles/shell.js:349 (background)
- src/styles/theme-preview.js:95 (background)
- src/styles/theme-preview.js:108
- src/styles/theme-preview.js:183 (background)
- src/styles/theme-preview.js:592
- src/styles/theme-preview.js:668 (background)
- src/styles/theme.js:144 (background)
- src/styles/theme.js:305
- src/styles/theme.js:306
- src/styles/theme.js:584 (background)
- src/styles/theme.js:785
- src/styles/theme.js:805
- src/styles/theme.js:888 (background)
- src/styles/theme.js:898
- src/styles/theme.js:971 (background)
- src/styles/theme.js:977

**`--evcc-surface-raised`** — Surface Raised · default `color-mix(in srgb, var(--evcc-surface-base) 92%, white 8%)` src/styles/foundation.js:182
- custom_components/eufy_vacuum/themes/preloaded.py:96
- custom_components/eufy_vacuum/themes/preloaded.py:134
- custom_components/eufy_vacuum/themes/preloaded.py:221
- custom_components/eufy_vacuum/themes/preloaded.py:333
- custom_components/eufy_vacuum/themes/preloaded.py:383
- custom_components/eufy_vacuum/themes/preloaded.py:406
- src/styles/base-station.js:67 (background)
- src/styles/base-station.js:107
- src/styles/external-jobs.js:67 (background)
- src/styles/foundation.js:369 (background)
- src/styles/foundation.js:387 (background)
- src/styles/maintenance.js:25
- src/styles/maintenance.js:29
- src/styles/maintenance.js:34
- src/styles/maintenance.js:38
- src/styles/maintenance.js:107 (background)
- src/styles/maintenance.js:112
- src/styles/maintenance.js:118
- src/styles/maintenance.js:212 (background)
- src/styles/maintenance.js:274
- src/styles/maintenance.js:402 (background)
- src/styles/map.js:478 (background)
- src/styles/map.js:1311 (background)
- src/styles/map.js:1337 (background)
- src/styles/metrics.js:96 (background)
- src/styles/mobile.js:177 (background)
- src/styles/mobile.js:277 (background)
- src/styles/modal-host.js:109 (--evcc-modal-surface-section)
- src/styles/modal-host.js:616 (--evcc-modal-surface-section)
- src/styles/review.js:97 (background)
- src/styles/review.js:133 (background)
- src/styles/shell.js:222 (background)
- src/styles/shell.js:227 (background)
- src/styles/shell.js:264 (background)
- src/styles/shell.js:366 (background)
- src/styles/shell.js:464 (background)
- src/styles/toast-host.js:71 (background)

**`--evcc-surface-subtle`** — Surface Subtle · default `rgba(255,255,255,0.04)` src/styles/foundation.js:185
- src/cards/dashboard-card.js:1285 (background)
- src/cards/dashboard-card.js:1289 (background)
- src/room-card.js:380 (--surface-subtle)
- src/styles/maintenance.js:377 (background)
- src/styles/modal-host.js:791 (background)
- src/styles/modal-host.js:806 (background)
- src/styles/rooms.js:863 (background)
- src/styles/setup.js:548 (background)
- src/styles/setup.js:595 (background)
- src/styles/setup.js:633 (background)
- src/styles/setup.js:678 (background)
- src/styles/setup.js:809 (background)
- src/styles/theme-preview.js:740 (background)
- src/styles/theme-preview.js:753 (background)

**`--evcc-surface-success`** — Surface Success · default `rgba(76,175,110,0.12)` src/styles/foundation.js:200
- src/cards/dashboard-card.js:1251 (--status-success-bg)
- src/styles/rooms.js:230 (background)

**`--evcc-surface-sunken`** — Surface Sunken · default `rgba(0,0,0,0.18)` src/styles/foundation.js:190
- src/cards/dashboard-card.js:1299 (background)
- src/styles/metrics.js:325 (background)
- src/styles/setup.js:310 (background)

**`--evcc-surface-warning`** — Surface Warning · default `rgba(255,180,0,0.12)` src/styles/foundation.js:191
- src/cards/dashboard-card.js:1249 (--status-warning-bg)
- src/styles/learning.js:630 (background)
- src/styles/rooms.js:238 (background)

## Borders & Shadows  ·  7 static / 7

**`--evcc-border-default`** — Border Default · default `rgba(255,255,255,0.10)` src/styles/foundation.js:211, src/styles/modal-host.js:214, src/styles/modal-host.js:660
- custom_components/eufy_vacuum/themes/preloaded.py:86
- custom_components/eufy_vacuum/themes/preloaded.py:105
- custom_components/eufy_vacuum/themes/preloaded.py:111
- custom_components/eufy_vacuum/themes/preloaded.py:120
- custom_components/eufy_vacuum/themes/preloaded.py:135
- custom_components/eufy_vacuum/themes/preloaded.py:173
- custom_components/eufy_vacuum/themes/preloaded.py:186
- custom_components/eufy_vacuum/themes/preloaded.py:190
- custom_components/eufy_vacuum/themes/preloaded.py:203
- custom_components/eufy_vacuum/themes/preloaded.py:204
- custom_components/eufy_vacuum/themes/preloaded.py:211
- src/cards/_shared.js:215
- src/cards/_shared.js:218
- src/cards/dashboard-card.js:1241 (--border)
- src/cards/profile-card.js:38 (--border)
- src/room-card.js:376 (--border)
- src/styles/base-station.js:22
- src/styles/external-jobs.js:21
- src/styles/external-jobs.js:48
- src/styles/external-jobs.js:68
- src/styles/external-jobs.js:130
- src/styles/external-jobs.js:141
- src/styles/external-jobs.js:151
- src/styles/external-jobs.js:163
- src/styles/external-jobs.js:173
- src/styles/foundation.js:44
- src/styles/foundation.js:274 (--evcc-chip-border)
- src/styles/foundation.js:371
- src/styles/job-summary.js:51
- src/styles/job-summary.js:82
- src/styles/learning.js:42 (--evcc-learning-panel-border)
- src/styles/learning.js:112 (--evcc-learning-confidence-neutral-border)
- src/styles/learning.js:675
- src/styles/learning.js:692
- src/styles/learning.js:714
- src/styles/learning.js:780
- src/styles/learning.js:785
- src/styles/learning.js:820
- src/styles/maintenance.js:24
- src/styles/maintenance.js:149
- src/styles/maintenance.js:176
- src/styles/maintenance.js:273
- src/styles/maintenance.js:444
- src/styles/map.js:37
- src/styles/map.js:476
- src/styles/map.js:1104
- src/styles/map.js:1206
- src/styles/map.js:1310
- src/styles/map.js:1326
- src/styles/map.js:1336
- src/styles/map.js:1483
- src/styles/map.js:1587
- src/styles/map.js:1673
- src/styles/map.js:1724
- src/styles/map.js:1789
- src/styles/metrics.js:28
- src/styles/metrics.js:186
- src/styles/metrics.js:223
- src/styles/metrics.js:255
- src/styles/metrics.js:326
- src/styles/mobile.js:903
- src/styles/modal-host.js:101 (--evcc-modal-border)
- src/styles/modal-host.js:102 (--evcc-modal-border-default)
- src/styles/modal-host.js:130 (--evcc-modal-chip-border)
- src/styles/modal-host.js:325
- src/styles/modal-host.js:423
- src/styles/modal-host.js:609 (--evcc-modal-border)
- src/styles/modal-host.js:610 (--evcc-modal-border-default)
- src/styles/modal-host.js:627 (--evcc-modal-chip-border)
- src/styles/modal-host.js:754
- src/styles/modals.js:132
- src/styles/modals.js:181
- src/styles/modals.js:298
- src/styles/order.js:53
- src/styles/review.js:22
- src/styles/review.js:193 (border-color)
- src/styles/review.js:231
- src/styles/room-access.js:15
- src/styles/room-rules.js:59 (border-color)
- src/styles/room-rules.js:118
- src/styles/room-rules.js:236
- src/styles/room-rules.js:301 (border-color)
- src/styles/room-rules.js:335
- src/styles/room-rules.js:390 (border-color)
- src/styles/rooms.js:49
- src/styles/rooms.js:391
- src/styles/rooms.js:665
- src/styles/rooms.js:698
- src/styles/rooms.js:748
- src/styles/rooms.js:755
- src/styles/rooms.js:762
- src/styles/rooms.js:769
- src/styles/rooms.js:776
- src/styles/rooms.js:809
- src/styles/rooms.js:828 (--evcc-estimate-default-border)
- src/styles/rooms.js:904
- src/styles/rooms.js:911
- src/styles/rooms.js:918
- src/styles/rooms.js:1050
- src/styles/rooms.js:1075
- src/styles/run-profiles.js:27
- src/styles/run-profiles.js:60
- src/styles/run-profiles.js:90
- src/styles/run-profiles.js:159
- src/styles/run-profiles.js:164
- src/styles/run-profiles.js:169
- src/styles/run-profiles.js:174
- src/styles/run-profiles.js:244
- src/styles/run-profiles.js:264
- src/styles/run-profiles.js:358
- src/styles/saved-zones.js:16
- src/styles/saved-zones.js:94
- src/styles/saved-zones.js:145
- src/styles/saved-zones.js:202
- src/styles/setup.js:43
- src/styles/setup.js:125
- src/styles/setup.js:260
- src/styles/setup.js:309
- src/styles/setup.js:403
- src/styles/setup.js:739
- src/styles/setup.js:760
- src/styles/setup.js:787
- src/styles/setup.js:831
- src/styles/setup.js:888
- src/styles/setup.js:947
- src/styles/shell.js:89
- src/styles/theme-preview.js:96
- src/styles/theme-preview.js:185
- src/styles/theme-preview.js:195
- src/styles/theme-preview.js:216
- src/styles/theme-preview.js:451
- src/styles/theme-preview.js:593
- src/styles/theme-preview.js:669
- src/styles/theme-preview.js:706
- src/styles/theme.js:852
- src/styles/theme.js:1089
- src/styles/theme.js:1188
- src/styles/theme.js:1248
- src/styles/theme.js:1280
- src/styles/theme.js:1292
- src/styles/theme.js:1317
- src/styles/theme.js:1339
- src/styles/theme.js:1365
- src/styles/theme.js:1377
- src/styles/theme.js:1402
- src/styles/theme.js:1426
- src/styles/toast-host.js:74

**`--evcc-border-strong`** — Border Strong · default `rgba(255,255,255,0.18)` src/styles/foundation.js:212, src/styles/modal-host.js:222, src/styles/modal-host.js:668
- custom_components/eufy_vacuum/themes/preloaded.py:91
- custom_components/eufy_vacuum/themes/preloaded.py:129
- custom_components/eufy_vacuum/themes/preloaded.py:205
- custom_components/eufy_vacuum/themes/preloaded.py:213
- custom_components/eufy_vacuum/themes/preloaded.py:452
- src/styles/base-station.js:102 (border-color)
- src/styles/foundation.js:105
- src/styles/foundation.js:279 (--evcc-chip-hover-border)
- src/styles/maintenance.js:316 (border-color)
- src/styles/map.js:64 (border-color)
- src/styles/map.js:1118 (border-color)
- src/styles/map.js:1739 (border-color)
- src/styles/map.js:1802 (border-color)
- src/styles/metrics.js:192
- src/styles/modal-host.js:103 (--evcc-modal-border-strong)
- src/styles/modal-host.js:133 (--evcc-modal-chip-hover-border)
- src/styles/modal-host.js:351
- src/styles/modal-host.js:493
- src/styles/modal-host.js:611 (--evcc-modal-border-strong)
- src/styles/modal-host.js:630 (--evcc-modal-chip-hover-border)
- src/styles/modals.js:382
- src/styles/order.js:101
- src/styles/rooms.js:423 (border-color)
- src/styles/theme-preview.js:220
- src/styles/theme.js:537 (border-color)

**`--evcc-border-subtle`** — Border Subtle · default `rgba(255,255,255,0.06)` src/styles/foundation.js:210, src/styles/modal-host.js:218, src/styles/modal-host.js:664
- custom_components/eufy_vacuum/themes/preloaded.py:138
- custom_components/eufy_vacuum/themes/preloaded.py:206
- src/styles/base-station.js:66
- src/styles/job-summary.js:51
- src/styles/job-summary.js:82
- src/styles/learning.js:387
- src/styles/learning.js:438
- src/styles/maintenance.js:106
- src/styles/maintenance.js:211
- src/styles/maintenance.js:378
- src/styles/maintenance.js:401
- src/styles/map.js:1089
- src/styles/map.js:1184
- src/styles/map.js:1195
- src/styles/map.js:1260
- src/styles/map.js:1270
- src/styles/metrics.js:95
- src/styles/mobile.js:71
- src/styles/mobile.js:139
- src/styles/mobile.js:246
- src/styles/mobile.js:258 (background)
- src/styles/mobile.js:618
- src/styles/mobile.js:711
- src/styles/modal-host.js:104 (--evcc-modal-border-subtle)
- src/styles/modal-host.js:370
- src/styles/modal-host.js:515
- src/styles/modal-host.js:530
- src/styles/modal-host.js:612 (--evcc-modal-border-subtle)
- src/styles/modal-host.js:792
- src/styles/review.js:96
- src/styles/review.js:111
- src/styles/review.js:132
- src/styles/review.js:220
- src/styles/room-estimate.js:38
- src/styles/room-estimate.js:60
- src/styles/room-rules.js:27
- src/styles/room-rules.js:214
- src/styles/room-rules.js:243
- src/styles/room-rules.js:281
- src/styles/room-rules.js:293
- src/styles/room-rules.js:414
- src/styles/rooms.js:864 (border-color)
- src/styles/setup.js:175
- src/styles/setup.js:336
- src/styles/setup.js:547
- src/styles/setup.js:632
- src/styles/setup.js:810
- src/styles/shell.js:103
- src/styles/shell.js:265
- src/styles/shell.js:348
- src/styles/shell.js:467
- src/styles/theme-preview.js:35
- src/styles/theme-preview.js:212
- src/styles/theme-preview.js:606
- src/styles/theme.js:135
- src/styles/theme.js:340
- src/styles/theme.js:471
- src/styles/theme.js:525
- src/styles/theme.js:616
- src/styles/theme.js:664
- src/styles/theme.js:684
- src/styles/theme.js:714
- src/styles/theme.js:729
- src/styles/theme.js:788
- src/styles/theme.js:808
- src/styles/theme.js:867 (border-color)
- src/styles/theme.js:889
- src/styles/theme.js:978

**`--evcc-border-success`** — Border Success · default `rgba(76,175,110,0.35)` src/styles/foundation.js:214
- src/styles/rooms.js:231 (border-color)
- src/styles/rooms.js:232 (--evcc-chip-active-bg)
- src/styles/rooms.js:233 (--evcc-chip-active-border)

**`--evcc-border-warning`** — Border Warning · default `rgba(255,180,0,0.35)` src/styles/foundation.js:213
- src/styles/learning.js:631
- src/styles/rooms.js:239 (border-color)
- src/styles/rooms.js:240 (--evcc-chip-active-bg)
- src/styles/rooms.js:241 (--evcc-chip-active-border)

**`--evcc-shadow-card`** — Shadow Card · default —
- src/styles/learning.js:45 (--evcc-learning-panel-shadow)
- src/styles/order.js:150
- src/styles/order.js:162
- src/styles/rooms.js:393 (box-shadow)
- src/styles/run-profiles.js:29 (box-shadow)
- src/styles/saved-zones.js:18 (box-shadow)
- src/styles/shell.js:49 (box-shadow)
- src/styles/theme-preview.js:37 (box-shadow)
- src/styles/theme-preview.js:98 (box-shadow)
- src/styles/theme-preview.js:175 (box-shadow)
- src/styles/theme-preview.js:224 (box-shadow)

**`--evcc-shadow-hover`** — Shadow Hover · default —
- src/styles/order.js:122 (box-shadow)
- src/styles/order.js:156
- src/styles/rooms.js:418
- src/styles/rooms.js:722 (box-shadow)
- src/styles/theme-preview.js:228 (box-shadow)
- src/styles/theme-preview.js:487

## Chips  ·  31 static / 31

**`--evcc-chip-active-bg`** — Chip Active BG · default src/styles/rooms.js:232, src/styles/rooms.js:240, src/styles/rooms.js:251
- src/styles/foundation.js:109 (background)

**`--evcc-chip-active-border`** — Chip Active Border · default src/styles/rooms.js:233, src/styles/rooms.js:241, src/styles/rooms.js:252
- src/styles/foundation.js:112 (border-color)

**`--evcc-chip-active-text`** — Chip Active Text · default src/styles/rooms.js:234, src/styles/rooms.js:242, src/styles/rooms.js:253
- src/styles/foundation.js:111 (color)

**`--evcc-chip-bg`** — Chip BG · default `var(--evcc-surface-input)` src/styles/foundation.js:273, src/styles/modal-host.js:327, src/styles/order.js:48, src/styles/rooms.js:531, src/styles/rooms.js:537, src/styles/rooms.js:544, src/styles/rooms.js:552, src/styles/rooms.js:654, src/styles/rooms.js:662, src/styles/rooms.js:669, src/styles/rooms.js:1376, src/styles/rooms.js:1382
- src/styles/foundation.js:46 (background)
- src/styles/maintenance.js:177 (background)
- src/styles/rooms.js:579
- src/styles/rooms.js:580
- src/styles/rooms.js:599
- src/styles/rooms.js:600
- src/styles/theme-preview.js:237

**`--evcc-chip-border`** — Chip Border · default `var(--evcc-border-default)` src/styles/foundation.js:274, src/styles/modal-host.js:323, src/styles/order.js:52, src/styles/rooms.js:532, src/styles/rooms.js:538, src/styles/rooms.js:546, src/styles/rooms.js:553, src/styles/rooms.js:657, src/styles/rooms.js:665, src/styles/rooms.js:671, src/styles/rooms.js:1377, src/styles/rooms.js:1383
- src/styles/foundation.js:44
- src/styles/maintenance.js:176
- src/styles/theme-preview.js:238

**`--evcc-chip-excluded-bg`** — Chip Excluded BG · default —
- src/styles/rooms.js:662 (--evcc-chip-bg)
- src/styles/theme-preview.js:249 (background)

**`--evcc-chip-excluded-border`** — Chip Excluded Border · default —
- src/styles/rooms.js:665 (--evcc-chip-border)
- src/styles/theme-preview.js:250 (border-color)

**`--evcc-chip-excluded-text`** — Chip Excluded Text · default —
- src/styles/rooms.js:664 (--evcc-chip-text)
- src/styles/theme-preview.js:251 (color)

**`--evcc-chip-font-size`** — Chip Font Size · default src/styles/modal-host.js:335, src/styles/order.js:45, src/styles/order.js:72, src/styles/order.js:83, src/styles/rooms.js:529, src/styles/rooms.js:648, src/styles/rooms.js:1187, src/styles/rooms.js:1374
- src/styles/foundation.js:49 (font-size)

**`--evcc-chip-font-weight`** — Chip Font Weight · default src/styles/modal-host.js:338, src/styles/order.js:46, src/styles/order.js:73, src/styles/order.js:84, src/styles/rooms.js:530, src/styles/rooms.js:649, src/styles/rooms.js:1375
- src/styles/foundation.js:50 (font-weight)

**`--evcc-chip-gap`** — Chip Gap · default —
- src/styles/foundation.js:30 (gap)
- src/styles/order.js:34 (gap)
- src/styles/rooms.js:523 (gap)

**`--evcc-chip-height`** — Chip Height · default `24px` src/styles/foundation.js:269, src/styles/modal-host.js:245, src/styles/order.js:43, src/styles/order.js:70, src/styles/order.js:81, src/styles/rooms.js:527, src/styles/rooms.js:646, src/styles/rooms.js:1185, src/styles/rooms.js:1372
- src/styles/foundation.js:40 (min-height)
- src/styles/maintenance.js:173 (min-height)

**`--evcc-chip-hover-bg`** — Chip Hover BG · default `var(--evcc-surface-panel)` src/styles/foundation.js:277, src/styles/modal-host.js:341
- src/styles/foundation.js:103 (background)
- src/styles/order.js:99 (background)
- src/styles/theme-preview.js:237 (background)

**`--evcc-chip-hover-border`** — Chip Hover Border · default `var(--evcc-border-strong)` src/styles/foundation.js:279, src/styles/modal-host.js:349
- src/styles/foundation.js:105 (border-color)
- src/styles/order.js:101 (border-color)
- src/styles/theme-preview.js:238 (border-color)

**`--evcc-chip-hover-text`** — Chip Hover Text · default `var(--evcc-text-primary)` src/styles/foundation.js:278, src/styles/modal-host.js:345
- src/styles/foundation.js:104 (color)
- src/styles/order.js:100 (color)
- src/styles/theme-preview.js:239 (color)

**`--evcc-chip-icon-height`** — Chip Icon Height · default `24px` src/styles/foundation.js:281, src/styles/modal-host.js:353
- src/styles/foundation.js:123 (min-height)

**`--evcc-chip-icon-padding`** — Chip Icon Padding · default `4px 8px` src/styles/foundation.js:282, src/styles/modal-host.js:356
- src/styles/foundation.js:124 (padding)

**`--evcc-chip-icon-size`** — Chip Icon Size · default `0.8rem` src/styles/foundation.js:283, src/styles/modal-host.js:359
- src/styles/foundation.js:125 (font-size)

**`--evcc-chip-included-bg`** — Chip Included BG · default —
- src/styles/modal-host.js:561 (background)
- src/styles/rooms.js:654 (--evcc-chip-bg)
- src/styles/theme-preview.js:243 (background)

**`--evcc-chip-included-border`** — Chip Included Border · default —
- src/styles/modal-host.js:569 (border-color)
- src/styles/rooms.js:657 (--evcc-chip-border)
- src/styles/theme-preview.js:244 (border-color)

**`--evcc-chip-included-text`** — Chip Included Text · default —
- src/styles/modal-host.js:565 (color)
- src/styles/rooms.js:656 (--evcc-chip-text)
- src/styles/theme-preview.js:245 (color)

**`--evcc-chip-neutral-bg`** — Chip Neutral BG · default —
- src/styles/order.js:49

**`--evcc-chip-padding`** — Chip Padding · default `5px 14px` src/styles/foundation.js:270, src/styles/modal-host.js:248, src/styles/order.js:44, src/styles/order.js:71, src/styles/order.js:82, src/styles/rooms.js:528, src/styles/rooms.js:647, src/styles/rooms.js:1186, src/styles/rooms.js:1373
- src/styles/foundation.js:41 (padding)
- src/styles/maintenance.js:174 (padding)

**`--evcc-chip-radius`** — Chip Radius · default `999px` src/styles/foundation.js:271, src/styles/modal-host.js:251
- src/styles/foundation.js:43 (border-radius)
- src/styles/maintenance.js:175 (border-radius)

**`--evcc-chip-success-bg`** — Chip Success BG · default —
- src/styles/rooms.js:83 (background)
- src/styles/theme-preview.js:255 (background)

**`--evcc-chip-success-border`** — Chip Success Border · default —
- src/styles/rooms.js:86 (border-color)
- src/styles/theme-preview.js:256 (border-color)

**`--evcc-chip-success-text`** — Chip Success Text · default —
- src/styles/rooms.js:85 (color)
- src/styles/theme-preview.js:257 (color)

**`--evcc-chip-text`** — Chip Text · default `var(--evcc-text-secondary)` src/styles/foundation.js:275, src/styles/modal-host.js:331, src/styles/order.js:55, src/styles/rooms.js:533, src/styles/rooms.js:539, src/styles/rooms.js:548, src/styles/rooms.js:656, src/styles/rooms.js:664, src/styles/rooms.js:670, src/styles/rooms.js:1378, src/styles/rooms.js:1384
- src/styles/foundation.js:47 (color)
- src/styles/maintenance.js:178 (color)
- src/styles/theme-preview.js:239

**`--evcc-chip-warning-bg`** — Chip Warning BG · default —
- src/styles/rooms.js:97 (background)
- src/styles/rooms.js:731 (background)
- src/styles/theme-preview.js:261 (background)

**`--evcc-chip-warning-border`** — Chip Warning Border · default —
- src/styles/rooms.js:100 (border-color)
- src/styles/rooms.js:733 (border-color)
- src/styles/theme-preview.js:262 (border-color)

**`--evcc-chip-warning-text`** — Chip Warning Text · default —
- src/styles/rooms.js:99 (color)
- src/styles/rooms.js:735 (color)
- src/styles/theme-preview.js:263 (color)

## Room Cards  ·  13 static / 13

**`--evcc-profile-chip-bg`** — Profile Chip BG · default —
- src/styles/rooms.js:537 (--evcc-chip-bg)
- src/styles/theme-preview.js:303 (background)

**`--evcc-profile-chip-border`** — Profile Chip Border · default —
- src/styles/rooms.js:538 (--evcc-chip-border)
- src/styles/theme-preview.js:304 (border-color)

**`--evcc-profile-chip-custom-bg`** — Profile Chip Custom BG · default —
- src/styles/rooms.js:544 (--evcc-chip-bg)
- src/styles/theme-preview.js:309 (background)

**`--evcc-profile-chip-custom-border`** — Profile Chip Custom Border · default —
- src/styles/rooms.js:546 (--evcc-chip-border)
- src/styles/theme-preview.js:310 (border-color)

**`--evcc-profile-chip-custom-text`** — Profile Chip Custom Text · default —
- src/styles/rooms.js:548 (--evcc-chip-text)
- src/styles/theme-preview.js:311 (color)

**`--evcc-profile-chip-text`** — Profile Chip Text · default —
- src/styles/rooms.js:539 (--evcc-chip-text)
- src/styles/theme-preview.js:305 (color)

**`--evcc-room-chip-bg`** — Room Chip BG · default —
- src/styles/rooms.js:531 (--evcc-chip-bg)
- src/styles/rooms.js:552 (--evcc-chip-bg)
- src/styles/theme-preview.js:315 (background)

**`--evcc-room-chip-border`** — Room Chip Border · default —
- src/styles/rooms.js:532 (--evcc-chip-border)
- src/styles/rooms.js:553 (--evcc-chip-border)
- src/styles/theme-preview.js:316 (border-color)

**`--evcc-room-chip-text`** — Room Chip Text · default —
- src/styles/rooms.js:533 (--evcc-chip-text)
- src/styles/theme-preview.js:317 (color)

**`--evcc-room-fill-opacity`** — Room Card Opacity · default src/styles/rooms.js:1349, src/styles/rooms.js:1353, src/styles/rooms.js:1357
- src/styles/rooms.js:1228 (opacity)
- src/styles/theme-preview.js:272
- src/styles/theme-preview.js:282

**`--evcc-room-grid-columns`** — Room Grid Columns · default —
- src/styles/layout.js:79 (grid-template-columns)

**`--evcc-room-grid-gap`** — Room Grid Gap · default `var(--evcc-grid-gap)` src/styles/layout.js:64
- src/styles/layout.js:78 (gap)

**`--evcc-room-grid-min`** — Room Grid Min · default `240px` src/styles/layout.js:65
- src/styles/layout.js:81

## Map  ·  22 static + 12 dynamic / 34

**`--evcc-map-label-bg`** — Map Label Background · default src/styles/modal-host.js:256
- src/styles/map.js:771 (background)
- src/styles/map.js:900 (background)
- src/styles/map.js:937 (background)

**`--evcc-map-label-text`** — Map Label Text · default src/styles/modal-host.js:259
- src/styles/map.js:764 (color)

**`--evcc-map-label-text-selected`** — Map Label Text (Selected) · default src/styles/modal-host.js:262
- src/styles/map.js:781 (color)

**`--evcc-map-label-order-text`** — Map Order Badge Text · default src/styles/modal-host.js:265
- src/styles/map.js:792 (color)
- src/styles/map.js:1130 (color)

**`--evcc-map-tooltip-bg`** — Map Tooltip Background · default src/styles/modal-host.js:268
- src/styles/map.js:230 (background)
- src/styles/map.js:305 (background)
- src/styles/map.js:351 (background)
- src/styles/map.js:1029 (background)

**`--evcc-map-tooltip-border`** — Map Tooltip Border · default src/styles/modal-host.js:271
- src/styles/map.js:231
- src/styles/map.js:247
- src/styles/map.js:279
- src/styles/map.js:322
- src/styles/map.js:352
- src/styles/map.js:501
- src/styles/map.js:519
- src/styles/map.js:555
- src/styles/map.js:602
- src/styles/map.js:993
- src/styles/map.js:1031

**`--evcc-map-tooltip-text`** — Map Tooltip Text · default src/styles/modal-host.js:274
- src/styles/map.js:245 (color)
- src/styles/map.js:277 (color)
- src/styles/map.js:304 (color)
- src/styles/map.js:320 (color)
- src/styles/map.js:350 (color)
- src/styles/map.js:517 (color)
- src/styles/map.js:560 (color)
- src/styles/map.js:592 (color)
- src/styles/map.js:600 (color)
- src/styles/map.js:620 (color)
- src/styles/map.js:998 (color)
- src/styles/map.js:1014 (color)
- src/styles/map.js:1045 (color)

**`--evcc-map-tooltip-hint`** — Map Tooltip Hint Text · default src/styles/modal-host.js:277
- src/styles/map.js:266 (color)
- src/styles/map.js:508 (color)
- src/styles/map.js:572 (color)
- src/styles/map.js:582 (color)
- src/styles/map.js:638 (color)
- src/styles/map.js:1002 (color)
- src/styles/map.js:1051 (color)

**`--evcc-map-compose-selected-stroke`** — Composer Selected Outline · default src/styles/modal-host.js:280
- src/styles/map.js:1387 (stroke)

**`--evcc-map-compose-cut-fill`** — Composer Cutout Fill · default src/styles/modal-host.js:283
- src/styles/map.js:1407 (fill)

**`--evcc-map-compose-cut-selected-fill`** — Composer Cutout Fill (Selected) · default src/styles/modal-host.js:286
- src/styles/map.js:1411 (fill)

**`--evcc-map-vertex-selected-glow`** — Composer Selected Vertex Glow · default src/styles/modal-host.js:289
- src/styles/map.js:1247

**`--evcc-map-ov-current`** — Overlay: Current Room · default src/styles/modal-host.js:294
- src/styles/map.js:805 (fill)
- src/styles/map.js:807 (stroke)

**`--evcc-map-ov-nogo`** — Overlay: No-Go Zone · default src/styles/modal-host.js:296
- src/styles/map.js:819 (fill)
- src/styles/map.js:820 (stroke)

**`--evcc-map-ov-nomop`** — Overlay: No-Mop Zone · default src/styles/modal-host.js:298
- src/styles/map.js:823 (fill)
- src/styles/map.js:824 (stroke)

**`--evcc-map-ov-wall`** — Overlay: Virtual Wall · default src/styles/modal-host.js:300
- src/styles/map.js:832 (stroke)

**`--evcc-map-ov-zone`** — Overlay: Saved Zone · default src/styles/modal-host.js:302
- src/styles/map.js:827 (fill)
- src/styles/map.js:828 (stroke)

**`--evcc-map-ov-path`** — Overlay: Cleaning Path · default src/styles/modal-host.js:304
- src/styles/map.js:840 (stroke)

**`--evcc-map-ov-robot`** — Overlay: Robot Marker · default src/styles/modal-host.js:306
- src/styles/map.js:867 (background)
- src/styles/map.js:878

**`--evcc-map-ov-dock`** — Overlay: Dock Marker · default src/styles/modal-host.js:308
- src/styles/map.js:860 (background)

**`--evcc-map-ov-obstacle`** — Overlay: Obstacle Marker · default src/styles/modal-host.js:310
- src/styles/map.js:886 (background)
- src/styles/map.js:890

**`--evcc-map-ov-area-text`** — Overlay: Area Label Text · default src/styles/modal-host.js:320
- src/styles/map.js:899 (color)

**`--evcc-room-fill-1`** — Map Room Color 1 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-2`** — Map Room Color 2 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-3`** — Map Room Color 3 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-4`** — Map Room Color 4 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-5`** — Map Room Color 5 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-6`** — Map Room Color 6 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-7`** — Map Room Color 7 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-8`** — Map Room Color 8 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-9`** — Map Room Color 9 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-10`** — Map Room Color 10 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-11`** — Map Room Color 11 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

**`--evcc-room-fill-12`** — Map Room Color 12 · default —
- _no STATIC consumer — consumed dynamically (room-fill): `src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7)_

## Floor Textures  ·  5 static / 5

**`--evcc-floor-textures-card-enabled`** — Card Textures Enabled (0/1) · default —
- src/styles/floor-texture-styles.js:80

**`--evcc-floor-textures-map-enabled`** — Map Textures Enabled (0/1) · default —
- src/styles/floor-texture-styles.js:104

**`--evcc-floor-texture-opacity-card`** — Card Texture Opacity (all) · default —
- src/renderers/floor-texture-surface.js:104

**`--evcc-floor-texture-opacity-map`** — Map Texture Opacity (all) · default —
- src/styles/floor-texture-styles.js:103

**`--evcc-floor-texture-map-rotate`** — Map Texture Rotation (deg) · default —
- src/bindings/map.js:853 (getPropertyValue)

## Floor Textures — Tile  ·  0 static + 7 dynamic / 7

**`--evcc-floor-tile-base`** — Tile Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-grout`** — Tile Grout Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-accent`** — Tile Grout Line Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-opacity-card`** — Tile Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-face-opacity`** — Tile Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-grout-opacity`** — Tile Grout Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-tile-line-opacity`** — Tile Grout Line Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Wood  ·  0 static + 6 dynamic / 6

**`--evcc-floor-wood-base`** — Wood Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-accent`** — Wood Grain & Seam Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-opacity-card`** — Wood Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-depth-opacity`** — Wood Depth Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-grain-opacity`** — Wood Grain Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-wood-seam-opacity`** — Wood Seam Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Marble  ·  10 static + 5 dynamic / 15

**`--evcc-floor-marble-base`** — Marble Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-marble-micro`** — Marble Micro Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-marble-accent`** — Marble Vein Color · default —
- src/textures/floor-texture-registry.js:152

**`--evcc-floor-marble-opacity-card`** — Marble Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-marble-base-opacity`** — Marble Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-marble-micro-opacity`** — Marble Micro Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

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

## Floor Textures — Concrete  ·  0 static + 5 dynamic / 5

**`--evcc-floor-concrete-base`** — Concrete Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-concrete-accent`** — Concrete Micro Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-concrete-opacity-card`** — Concrete Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-concrete-broad-opacity`** — Concrete Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-concrete-micro-opacity`** — Concrete Micro Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Carpet Low  ·  0 static + 5 dynamic / 5

**`--evcc-floor-carpet-low-base`** — Carpet Low Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-low-weave`** — Carpet Low Weave Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-low-opacity-card`** — Carpet Low Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-low-base-opacity`** — Carpet Low Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-low-weave-opacity`** — Carpet Low Weave Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Carpet High  ·  0 static + 5 dynamic / 5

**`--evcc-floor-carpet-high-base`** — Carpet High Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-high-weave`** — Carpet High Weave Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-high-opacity-card`** — Carpet High Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-high-base-opacity`** — Carpet High Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-carpet-high-weave-opacity`** — Carpet High Weave Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Floor Textures — Granite  ·  0 static + 5 dynamic / 5

**`--evcc-floor-granite-light-base`** — Granite Base Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-granite-light-aggregate`** — Granite Aggregate Color · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-granite-light-opacity-card`** — Granite Card Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-granite-light-base-opacity`** — Granite Base Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

**`--evcc-floor-granite-light-aggregate-opacity`** — Granite Aggregate Layer Opacity · default —
- _no STATIC consumer — consumed dynamically (floor-material): `src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key_

## Queue & Ordering  ·  41 static / 41

**`--evcc-drag-opacity`** — Drag Opacity · default —
- src/styles/order.js:130 (opacity)
- src/styles/theme-preview.js:485 (opacity)

**`--evcc-drag-scale`** — Drag Scale · default —
- src/styles/order.js:131
- src/styles/theme-preview.js:486

**`--evcc-drag-shadow`** — Drag Shadow · default —
- src/styles/order.js:132 (box-shadow)
- src/styles/theme-preview.js:487 (box-shadow)

**`--evcc-order-chip-bg`** — Order Chip BG · default —
- src/styles/order.js:48 (--evcc-chip-bg)
- src/styles/theme-preview.js:440 (background)

**`--evcc-order-chip-border`** — Order Chip Border · default —
- src/styles/order.js:52 (--evcc-chip-border)
- src/styles/theme-preview.js:441 (border-color)

**`--evcc-order-chip-text`** — Order Chip Text · default —
- src/styles/order.js:55 (--evcc-chip-text)
- src/styles/theme-preview.js:442 (color)

**`--evcc-order-feedback-border`** — Order Feedback Border · default —
- src/styles/order.js:173 (border-color)
- src/styles/theme-preview.js:491

**`--evcc-order-target-outline`** — Order Target Outline · default —
- src/styles/order.js:137
- src/styles/theme-preview.js:491

**`--evcc-progress-complete`** — Progress Complete · default —
- src/styles/rooms.js:1298 (background)
- src/styles/rooms.js:1306 (background)

**`--evcc-progress-fill`** — Progress Fill · default —
- src/styles/rooms.js:1200 (background)
- src/styles/rooms.js:1222 (background)

**`--evcc-queue-chip-bg`** — Queue Chip BG · default —
- src/styles/rooms.js:697 (background)
- src/styles/rooms.js:718
- src/styles/rooms.js:747
- src/styles/rooms.js:754
- src/styles/rooms.js:761
- src/styles/rooms.js:768
- src/styles/rooms.js:775

**`--evcc-queue-chip-border`** — Queue Chip Border · default —
- src/styles/rooms.js:698
- src/styles/rooms.js:748
- src/styles/rooms.js:755
- src/styles/rooms.js:762
- src/styles/rooms.js:769
- src/styles/rooms.js:776

**`--evcc-queue-chip-gap`** — Queue Chip Gap · default —
- src/styles/rooms.js:682 (gap)
- src/styles/theme-preview.js:448 (gap)

**`--evcc-queue-chip-text`** — Queue Chip Text · default —
- src/styles/rooms.js:699 (color)
- src/styles/rooms.js:721
- src/styles/rooms.js:749
- src/styles/rooms.js:756
- src/styles/rooms.js:763
- src/styles/rooms.js:770
- src/styles/rooms.js:777

**`--evcc-queue-completed-bg`** — Queue Completed BG · default —
- src/styles/rooms.js:768 (background)
- src/styles/theme-preview.js:471 (background)

**`--evcc-queue-completed-border`** — Queue Completed Border · default —
- src/styles/rooms.js:769 (border-color)
- src/styles/theme-preview.js:472 (border-color)

**`--evcc-queue-completed-opacity`** — Queue Completed Opacity · default —
- src/styles/rooms.js:771 (opacity)
- src/styles/theme-preview.js:474 (opacity)

**`--evcc-queue-completed-text`** — Queue Completed Text · default —
- src/styles/rooms.js:770 (color)
- src/styles/theme-preview.js:473 (color)

**`--evcc-queue-current-bg`** — Queue Current BG · default —
- src/styles/rooms.js:739 (background)
- src/styles/rooms.js:754 (background)
- src/styles/theme-preview.js:457 (background)

**`--evcc-queue-current-border`** — Queue Current Border · default —
- src/styles/rooms.js:741 (border-color)
- src/styles/rooms.js:755 (border-color)
- src/styles/theme-preview.js:458 (border-color)

**`--evcc-queue-current-glow`** — Queue Current Glow · default —
- src/styles/rooms.js:757 (box-shadow)
- src/styles/theme-preview.js:460 (box-shadow)

**`--evcc-queue-current-text`** — Queue Current Text · default —
- src/styles/rooms.js:743 (color)
- src/styles/rooms.js:756 (color)
- src/styles/theme-preview.js:459 (color)

**`--evcc-queue-hover-bg`** — Queue Hover BG · default —
- src/styles/rooms.js:718 (background)

**`--evcc-queue-hover-border`** — Queue Hover Border · default —
- src/styles/rooms.js:719 (border-color)

**`--evcc-queue-hover-text`** — Queue Hover Text · default —
- src/styles/rooms.js:721 (color)

**`--evcc-queue-inferred-bg`** — Queue Inferred BG · default —
- src/styles/rooms.js:761 (background)
- src/styles/theme-preview.js:478 (background)

**`--evcc-queue-inferred-border`** — Queue Inferred Border · default —
- src/styles/rooms.js:762 (border-color)
- src/styles/theme-preview.js:479 (border-color)

**`--evcc-queue-inferred-glow`** — Queue Inferred Glow · default —
- src/styles/rooms.js:764 (box-shadow)
- src/styles/theme-preview.js:481 (box-shadow)

**`--evcc-queue-inferred-text`** — Queue Inferred Text · default —
- src/styles/rooms.js:763 (color)
- src/styles/theme-preview.js:480 (color)

**`--evcc-queue-order-bg`** — Queue Order BG · default —
- src/styles/rooms.js:788 (background)
- src/styles/theme-preview.js:440

**`--evcc-queue-order-border`** — Queue Order Border · default —
- src/styles/rooms.js:789
- src/styles/theme-preview.js:441

**`--evcc-queue-order-text`** — Queue Order Text · default —
- src/styles/rooms.js:792 (color)
- src/styles/theme-preview.js:442

**`--evcc-queue-pending-bg`** — Queue Pending BG · default —
- src/styles/rooms.js:747 (background)
- src/styles/theme-preview.js:464 (background)

**`--evcc-queue-pending-border`** — Queue Pending Border · default —
- src/styles/rooms.js:748 (border-color)
- src/styles/theme-preview.js:465 (border-color)

**`--evcc-queue-pending-opacity`** — Queue Pending Opacity · default —
- src/styles/rooms.js:750 (opacity)
- src/styles/theme-preview.js:467 (opacity)

**`--evcc-queue-pending-text`** — Queue Pending Text · default —
- src/styles/rooms.js:749 (color)
- src/styles/theme-preview.js:466 (color)

**`--evcc-queue-skipped-bg`** — Queue Skipped BG · default —
- src/styles/rooms.js:775 (background)

**`--evcc-queue-skipped-border`** — Queue Skipped Border · default —
- src/styles/rooms.js:776 (border-color)

**`--evcc-queue-skipped-text`** — Queue Skipped Text · default —
- src/styles/rooms.js:777 (color)

**`--evcc-reorder-feedback-duration`** — Reorder Feedback Duration · default —
- src/styles/order.js:169

**`--evcc-reorder-flip-easing`** — Reorder Flip Easing · default —
- src/styles/order.js:170

## Status, Confidence & Alerts  ·  31 static / 31

**`--evcc-color-cleaning`** — Color Cleaning · default `var(--evcc-sem-success)` src/styles/foundation.js:260
- src/styles/theme-preview.js:517

**`--evcc-color-docked`** — Color Docked · default `var(--evcc-accent)` src/styles/foundation.js:261
- src/styles/theme-preview.js:521

**`--evcc-color-error`** — Color Error · default `var(--evcc-sem-error)` src/styles/foundation.js:262
- src/styles/theme-preview.js:525

**`--evcc-color-idle`** — Color Idle · default `var(--evcc-text-secondary)` src/styles/foundation.js:263
- src/styles/theme-preview.js:513

**`--evcc-confidence-high-bg`** — Confidence High BG · default `color-mix(in srgb, var(--evcc-sem-success) 18%, transparent)` src/styles/learning.js:125
- src/styles/rooms.js:903
- src/styles/rooms.js:905
- src/styles/theme-preview.js:530 (background)

**`--evcc-confidence-high-border`** — Confidence High Border · default `color-mix(in srgb, var(--evcc-sem-success) 40%, transparent)` src/styles/learning.js:127
- src/styles/rooms.js:904
- src/styles/theme-preview.js:531 (border-color)

**`--evcc-confidence-high-text`** — Confidence High Text · default `var(--evcc-sem-success)` src/styles/learning.js:129
- src/styles/theme-preview.js:532 (color)

**`--evcc-confidence-low-bg`** — Confidence Low BG · default `color-mix(in srgb, var(--evcc-sem-error) 18%, transparent)` src/styles/learning.js:139
- src/styles/rooms.js:917
- src/styles/rooms.js:919
- src/styles/theme-preview.js:543 (background)

**`--evcc-confidence-low-border`** — Confidence Low Border · default `color-mix(in srgb, var(--evcc-sem-error) 40%, transparent)` src/styles/learning.js:141
- src/styles/rooms.js:918
- src/styles/theme-preview.js:544 (border-color)

**`--evcc-confidence-low-text`** — Confidence Low Text · default `var(--evcc-sem-error)` src/styles/learning.js:143
- src/styles/theme-preview.js:545 (color)

**`--evcc-confidence-medium-bg`** — Confidence Medium BG · default `color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent)` src/styles/learning.js:132
- src/styles/rooms.js:910
- src/styles/rooms.js:912
- src/styles/theme-preview.js:537 (background)

**`--evcc-confidence-medium-border`** — Confidence Medium Border · default `color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent)` src/styles/learning.js:134
- src/styles/rooms.js:911
- src/styles/theme-preview.js:538 (border-color)

**`--evcc-confidence-medium-text`** — Confidence Medium Text · default `var(--evcc-sem-warning)` src/styles/learning.js:136
- src/styles/theme-preview.js:539 (color)

**`--evcc-sem-error`** — Sem Error · default `var(--error-color, #e05252)` src/styles/foundation.js:229
- custom_components/eufy_vacuum/themes/preloaded.py:87
- custom_components/eufy_vacuum/themes/preloaded.py:88
- custom_components/eufy_vacuum/themes/preloaded.py:89
- custom_components/eufy_vacuum/themes/preloaded.py:145
- custom_components/eufy_vacuum/themes/preloaded.py:150
- custom_components/eufy_vacuum/themes/preloaded.py:151
- custom_components/eufy_vacuum/themes/preloaded.py:152
- custom_components/eufy_vacuum/themes/preloaded.py:166
- custom_components/eufy_vacuum/themes/preloaded.py:181
- custom_components/eufy_vacuum/themes/preloaded.py:182
- custom_components/eufy_vacuum/themes/preloaded.py:332
- custom_components/eufy_vacuum/themes/preloaded.py:406
- custom_components/eufy_vacuum/themes/preloaded.py:429
- custom_components/eufy_vacuum/themes/preloaded.py:452
- src/cards/dashboard-card.js:1381
- src/cards/dashboard-card.js:1382
- src/cards/dashboard-card.js:1383 (color)
- src/styles/external-jobs.js:102
- src/styles/external-jobs.js:103
- src/styles/external-jobs.js:104 (color)
- src/styles/foundation.js:262 (--evcc-color-error)
- src/styles/learning.js:98
- src/styles/learning.js:101 (--evcc-learning-confidence-low-text)
- src/styles/learning.js:106
- src/styles/learning.js:107
- src/styles/learning.js:140
- src/styles/learning.js:142
- src/styles/learning.js:144 (--evcc-confidence-low-text)
- src/styles/learning.js:377
- src/styles/learning.js:378
- src/styles/learning.js:379 (color)
- src/styles/maintenance.js:38
- src/styles/maintenance.js:117
- src/styles/maintenance.js:118
- src/styles/maintenance.js:307
- src/styles/map.js:1526
- src/styles/map.js:1527 (color)
- src/styles/map.js:1528
- src/styles/map.js:1532
- src/styles/map.js:1533
- src/styles/map.js:1540 (background)
- src/styles/map.js:1542 (border-color)
- src/styles/map.js:1548
- src/styles/map.js:1549
- src/styles/map.js:1559 (color)
- src/styles/mobile.js:125 (color)
- src/styles/modal-host.js:438 (color)
- src/styles/review.js:158
- src/styles/review.js:180
- src/styles/review.js:181
- src/styles/review.js:182 (color)
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
- src/styles/rooms.js:1120 (color)
- src/styles/run-profiles.js:277 (color)
- src/styles/saved-zones.js:218 (color)
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
- src/styles/shell.js:156
- src/styles/shell.js:173 (color)
- src/styles/shell.js:478
- src/styles/theme-preview.js:568
- src/styles/theme-preview.js:569
- src/styles/theme-preview.js:570 (color)
- src/styles/theme.js:698 (color)
- src/styles/toast-host.js:81

**`--evcc-sem-info`** — Sem Info · default `#4a9fe0` src/styles/foundation.js:233
- custom_components/eufy_vacuum/themes/preloaded.py:131
- custom_components/eufy_vacuum/themes/preloaded.py:132
- custom_components/eufy_vacuum/themes/preloaded.py:133
- src/styles/external-jobs.js:83
- src/styles/job-summary.js:42
- src/styles/job-summary.js:43
- src/styles/room-access.js:57
- src/styles/setup.js:560
- src/styles/setup.js:649
- src/styles/setup.js:712 (color)
- src/styles/theme-preview.js:556
- src/styles/theme-preview.js:557
- src/styles/theme-preview.js:558 (color)

**`--evcc-sem-success`** — Sem Success · default `var(--success-color, #4caf6e)` src/styles/foundation.js:227
- custom_components/eufy_vacuum/themes/preloaded.py:93
- custom_components/eufy_vacuum/themes/preloaded.py:94
- custom_components/eufy_vacuum/themes/preloaded.py:95
- custom_components/eufy_vacuum/themes/preloaded.py:97
- custom_components/eufy_vacuum/themes/preloaded.py:98
- custom_components/eufy_vacuum/themes/preloaded.py:99
- custom_components/eufy_vacuum/themes/preloaded.py:122
- custom_components/eufy_vacuum/themes/preloaded.py:123
- custom_components/eufy_vacuum/themes/preloaded.py:124
- custom_components/eufy_vacuum/themes/preloaded.py:143
- custom_components/eufy_vacuum/themes/preloaded.py:147
- custom_components/eufy_vacuum/themes/preloaded.py:148
- custom_components/eufy_vacuum/themes/preloaded.py:149
- custom_components/eufy_vacuum/themes/preloaded.py:160
- custom_components/eufy_vacuum/themes/preloaded.py:161
- custom_components/eufy_vacuum/themes/preloaded.py:162
- custom_components/eufy_vacuum/themes/preloaded.py:164
- custom_components/eufy_vacuum/themes/preloaded.py:178
- custom_components/eufy_vacuum/themes/preloaded.py:179
- custom_components/eufy_vacuum/themes/preloaded.py:180
- custom_components/eufy_vacuum/themes/preloaded.py:330
- custom_components/eufy_vacuum/themes/preloaded.py:383
- custom_components/eufy_vacuum/themes/preloaded.py:406
- custom_components/eufy_vacuum/themes/preloaded.py:429
- custom_components/eufy_vacuum/themes/preloaded.py:452
- src/cards/dashboard-card.js:1252 (--status-success-line)
- src/styles/base-station.js:107
- src/styles/foundation.js:260 (--evcc-color-cleaning)
- src/styles/learning.js:64
- src/styles/learning.js:67
- src/styles/learning.js:70 (--evcc-learning-confidence-high-text)
- src/styles/learning.js:75
- src/styles/learning.js:76
- src/styles/learning.js:126
- src/styles/learning.js:128
- src/styles/learning.js:130 (--evcc-confidence-high-text)
- src/styles/learning.js:299
- src/styles/learning.js:300
- src/styles/learning.js:799 (accent-color)
- src/styles/maintenance.js:29
- src/styles/maintenance.js:111
- src/styles/maintenance.js:112
- src/styles/maintenance.js:298
- src/styles/map.js:1459 (color)
- src/styles/map.js:1699
- src/styles/map.js:1704
- src/styles/map.js:1705 (color)
- src/styles/map.js:1707
- src/styles/map.js:1745
- src/styles/map.js:1746 (color)
- src/styles/map.js:1748
- src/styles/modal-host.js:562
- src/styles/modal-host.js:566
- src/styles/modal-host.js:570
- src/styles/rooms.js:84
- src/styles/rooms.js:87
- src/styles/rooms.js:92
- src/styles/rooms.js:93
- src/styles/rooms.js:234 (--evcc-chip-active-text)
- src/styles/rooms.js:335
- src/styles/rooms.js:337
- src/styles/rooms.js:349
- src/styles/rooms.js:356
- src/styles/rooms.js:357
- src/styles/rooms.js:362
- src/styles/rooms.js:655
- src/styles/rooms.js:656
- src/styles/rooms.js:658
- src/styles/rooms.js:740
- src/styles/rooms.js:742
- src/styles/rooms.js:743
- src/styles/rooms.js:936 (color)
- src/styles/rooms.js:958
- src/styles/rooms.js:959
- src/styles/rooms.js:1032 (color)
- src/styles/rooms.js:1059
- src/styles/rooms.js:1060
- src/styles/rooms.js:1300
- src/styles/rooms.js:1308
- src/styles/run-profiles.js:174
- src/styles/run-profiles.js:175
- src/styles/setup.js:68 (background)
- src/styles/setup.js:141
- src/styles/setup.js:142
- src/styles/setup.js:143 (color)
- src/styles/setup.js:215
- src/styles/setup.js:216
- src/styles/setup.js:230 (color)
- src/styles/setup.js:292 (color)
- src/styles/setup.js:366 (background)
- src/styles/shell.js:153
- src/styles/shell.js:158
- src/styles/shell.js:474
- src/styles/theme.js:622 (color)
- src/styles/theme.js:623
- src/styles/theme.js:624
- src/styles/toast-host.js:80

**`--evcc-sem-warning`** — Sem Warning · default `var(--warning-color, #f5a623)` src/styles/foundation.js:228
- custom_components/eufy_vacuum/themes/preloaded.py:101
- custom_components/eufy_vacuum/themes/preloaded.py:102
- custom_components/eufy_vacuum/themes/preloaded.py:103
- custom_components/eufy_vacuum/themes/preloaded.py:140
- custom_components/eufy_vacuum/themes/preloaded.py:141
- custom_components/eufy_vacuum/themes/preloaded.py:142
- custom_components/eufy_vacuum/themes/preloaded.py:153
- custom_components/eufy_vacuum/themes/preloaded.py:154
- custom_components/eufy_vacuum/themes/preloaded.py:155
- custom_components/eufy_vacuum/themes/preloaded.py:169
- custom_components/eufy_vacuum/themes/preloaded.py:170
- custom_components/eufy_vacuum/themes/preloaded.py:183
- custom_components/eufy_vacuum/themes/preloaded.py:184
- custom_components/eufy_vacuum/themes/preloaded.py:185
- custom_components/eufy_vacuum/themes/preloaded.py:196
- custom_components/eufy_vacuum/themes/preloaded.py:225
- custom_components/eufy_vacuum/themes/preloaded.py:226
- custom_components/eufy_vacuum/themes/preloaded.py:227
- custom_components/eufy_vacuum/themes/preloaded.py:331
- custom_components/eufy_vacuum/themes/preloaded.py:406
- custom_components/eufy_vacuum/themes/preloaded.py:429
- custom_components/eufy_vacuum/themes/preloaded.py:452
- src/cards/dashboard-card.js:1250 (--status-warning-line)
- src/styles/external-jobs.js:38
- src/styles/external-jobs.js:39
- src/styles/external-jobs.js:40 (color)
- src/styles/external-jobs.js:90 (color)
- src/styles/external-jobs.js:184 (color)
- src/styles/job-summary.js:77 (color)
- src/styles/job-summary.js:116 (color)
- src/styles/learning.js:81
- src/styles/learning.js:84
- src/styles/learning.js:87 (--evcc-learning-confidence-medium-text)
- src/styles/learning.js:92
- src/styles/learning.js:93
- src/styles/learning.js:133
- src/styles/learning.js:135
- src/styles/learning.js:137 (--evcc-confidence-medium-text)
- src/styles/learning.js:293
- src/styles/learning.js:294
- src/styles/learning.js:365
- src/styles/learning.js:366
- src/styles/learning.js:367 (color)
- src/styles/learning.js:785
- src/styles/learning.js:786
- src/styles/maintenance.js:34
- src/styles/maintenance.js:303
- src/styles/map.js:306
- src/styles/metrics.js:122
- src/styles/metrics.js:123
- src/styles/metrics.js:124 (color)
- src/styles/mobile.js:124 (color)
- src/styles/modal-host.js:140
- src/styles/modal-host.js:141
- src/styles/modal-host.js:142
- src/styles/modal-host.js:579
- src/styles/modal-host.js:583
- src/styles/modal-host.js:587
- src/styles/modals.js:259 (color)
- src/styles/modals.js:260
- src/styles/modals.js:261
- src/styles/modals.js:273
- src/styles/modals.js:277
- src/styles/modals.js:281
- src/styles/review.js:54 (color)
- src/styles/review.js:162
- src/styles/review.js:187
- src/styles/review.js:188
- src/styles/review.js:189 (color)
- src/styles/room-access.js:47
- src/styles/room-access.js:48 (color)
- src/styles/room-access.js:81 (color)
- src/styles/room-access.js:87
- src/styles/room-access.js:88
- src/styles/rooms.js:98
- src/styles/rooms.js:99
- src/styles/rooms.js:101
- src/styles/rooms.js:106
- src/styles/rooms.js:107
- src/styles/rooms.js:128 (color)
- src/styles/rooms.js:150
- src/styles/rooms.js:151
- src/styles/rooms.js:242 (--evcc-chip-active-text)
- src/styles/rooms.js:262
- src/styles/rooms.js:263
- src/styles/rooms.js:369
- src/styles/rooms.js:373
- src/styles/rooms.js:545
- src/styles/rooms.js:547
- src/styles/rooms.js:548
- src/styles/rooms.js:732
- src/styles/rooms.js:734
- src/styles/rooms.js:735
- src/styles/rooms.js:835 (--evcc-learning-warning-text)
- src/styles/rooms.js:953
- src/styles/rooms.js:954
- src/styles/rooms.js:1141
- src/styles/rooms.js:1149
- src/styles/rooms.js:1150
- src/styles/run-profiles.js:169
- src/styles/run-profiles.js:170
- src/styles/run-profiles.js:191 (color)
- src/styles/setup.js:476
- src/styles/setup.js:477
- src/styles/setup.js:478
- src/styles/setup.js:563
- src/styles/setup.js:924 (color)
- src/styles/shell.js:155
- src/styles/shell.js:169 (color)
- src/styles/theme-preview.js:562
- src/styles/theme-preview.js:563
- src/styles/theme-preview.js:564

**`--evcc-status-cleaning-bg`** — Status Cleaning BG · default —
- src/styles/rooms.js:336 (background)

**`--evcc-status-cleaning-border`** — Status Cleaning Border · default —
- src/styles/rooms.js:334

**`--evcc-status-cleaning-text`** — Status Cleaning Text · default —
- src/styles/rooms.js:349 (color)

**`--evcc-status-dot-charging`** — Status Dot Charging · default —
- src/styles/shell.js:158 (background)

**`--evcc-status-dot-cleaning`** — Status Dot Cleaning · default —
- src/styles/rooms.js:356 (background)
- src/styles/rooms.js:357
- src/styles/rooms.js:362
- src/styles/shell.js:153 (background)
- src/styles/theme-preview.js:517 (background)

**`--evcc-status-dot-docked`** — Status Dot Docked · default —
- src/styles/shell.js:154 (background)
- src/styles/theme-preview.js:521 (background)

**`--evcc-status-dot-error`** — Status Dot Error · default —
- src/styles/shell.js:156 (background)
- src/styles/theme-preview.js:525 (background)

**`--evcc-status-dot-idle`** — Status Dot Idle · default —
- src/styles/shell.js:149 (background)
- src/styles/theme-preview.js:513 (background)

**`--evcc-status-dot-offline`** — Status Dot Offline · default —
- src/styles/shell.js:159 (background)

**`--evcc-status-dot-paused`** — Status Dot Paused · default —
- src/styles/shell.js:157 (background)

**`--evcc-status-dot-returning`** — Status Dot Returning · default —
- src/styles/shell.js:155 (background)

**`--evcc-status-dot-shadow`** — Status Dot Shadow · default —
- src/styles/shell.js:150 (box-shadow)
- src/styles/theme-preview.js:508 (box-shadow)

**`--evcc-status-dot-unavailable`** — Status Dot Unavailable · default —
- src/styles/shell.js:160 (background)

**`--evcc-status-pulse-duration`** — Status Pulse Duration · default —
- src/styles/rooms.js:358
- src/styles/theme-preview.js:509

## Learning & Metrics  ·  37 static / 37

**`--evcc-estimate-default-bg`** — Estimate Default BG · default `color-mix(in srgb, var(--evcc-text-muted) 12%, transparent)` src/styles/rooms.js:825
- src/styles/rooms.js:853 (background)
- src/styles/theme-preview.js:574 (background)

**`--evcc-estimate-default-border`** — Estimate Default Border · default `var(--evcc-border-default)` src/styles/rooms.js:827
- src/styles/rooms.js:854 (border-color)
- src/styles/theme-preview.js:575 (border-color)

**`--evcc-estimate-default-text`** — Estimate Default Text · default `var(--evcc-text-secondary)` src/styles/rooms.js:829
- src/styles/rooms.js:855 (color)
- src/styles/theme-preview.js:576 (color)

**`--evcc-estimate-learned-bg`** — Estimate Learned BG · default `color-mix(in srgb, var(--evcc-accent) 14%, transparent)` src/styles/rooms.js:818
- src/styles/rooms.js:847 (background)
- src/styles/theme-preview.js:580 (background)

**`--evcc-estimate-learned-border`** — Estimate Learned Border · default `color-mix(in srgb, var(--evcc-accent) 30%, transparent)` src/styles/rooms.js:820
- src/styles/rooms.js:848 (border-color)
- src/styles/theme-preview.js:581 (border-color)

**`--evcc-estimate-learned-text`** — Estimate Learned Text · default `var(--evcc-text-primary)` src/styles/rooms.js:822
- src/styles/rooms.js:849 (color)
- src/styles/theme-preview.js:582 (color)

**`--evcc-learning-anim-duration-fast`** — Learning Anim Duration Fast · default `180ms` src/styles/learning.js:147
- src/styles/learning.js:344
- src/styles/learning.js:441
- src/styles/learning.js:442
- src/styles/learning.js:443
- src/styles/learning.js:444
- src/styles/learning.js:534
- src/styles/learning.js:535
- src/styles/learning.js:536
- src/styles/learning.js:537

**`--evcc-learning-anim-duration-normal`** — Learning Anim Duration Normal · default `260ms` src/styles/learning.js:148
- src/styles/learning.js:239
- src/styles/learning.js:240
- src/styles/learning.js:241
- src/styles/learning.js:242
- src/styles/learning.js:336

**`--evcc-learning-anim-duration-slow`** — Learning Anim Duration Slow · default `520ms` src/styles/learning.js:149
- src/styles/learning.js:337
- src/styles/learning.js:345

**`--evcc-learning-anim-ease`** — Learning Anim Ease · default `cubic-bezier(0.22, 1, 0.36, 1)` src/styles/learning.js:150
- src/styles/learning.js:239
- src/styles/learning.js:240
- src/styles/learning.js:241
- src/styles/learning.js:242
- src/styles/learning.js:336
- src/styles/learning.js:337
- src/styles/learning.js:344
- src/styles/learning.js:345
- src/styles/learning.js:441
- src/styles/learning.js:442
- src/styles/learning.js:443
- src/styles/learning.js:444
- src/styles/learning.js:534
- src/styles/learning.js:535
- src/styles/learning.js:536
- src/styles/learning.js:537

**`--evcc-learning-chip-font-size`** — Learning Chip Font Size · default `0.74rem` src/styles/learning.js:59
- src/styles/learning.js:528 (font-size)

**`--evcc-learning-chip-font-weight`** — Learning Chip Font Weight · default `700` src/styles/learning.js:60
- src/styles/learning.js:529 (font-weight)

**`--evcc-learning-chip-radius`** — Learning Chip Radius · default `var(--evcc-radius-chip, 999px)` src/styles/learning.js:56
- src/styles/learning.js:522 (border-radius)

**`--evcc-learning-confidence-high-bg`** — Learning Confidence High BG · default `color-mix(in srgb, var(--evcc-sem-success) 18%, transparent)` src/styles/learning.js:63
- src/styles/theme-preview.js:530

**`--evcc-learning-confidence-high-border`** — Learning Confidence High Border · default `color-mix(in srgb, var(--evcc-sem-success) 42%, transparent)` src/styles/learning.js:66
- src/styles/learning.js:547 (border-color)
- src/styles/theme-preview.js:531

**`--evcc-learning-confidence-high-gradient`** — Learning Confidence High Gradient · default `linear-gradient( 135deg, color-mix(in srgb, var(--evcc-sem-success) 26%, transparent), color-mix(in srgb, var(--evcc-sem-success) 10%, transparent) )` src/styles/learning.js:72
- src/styles/learning.js:548 (background)

**`--evcc-learning-confidence-high-text`** — Learning Confidence High Text · default `var(--evcc-sem-success)` src/styles/learning.js:69
- src/styles/learning.js:549 (color)
- src/styles/theme-preview.js:532

**`--evcc-learning-confidence-low-border`** — Learning Confidence Low Border · default `color-mix(in srgb, var(--evcc-sem-error) 42%, transparent)` src/styles/learning.js:97
- src/styles/learning.js:559 (border-color)

**`--evcc-learning-confidence-low-gradient`** — Learning Confidence Low Gradient · default `linear-gradient( 135deg, color-mix(in srgb, var(--evcc-sem-error) 26%, transparent), color-mix(in srgb, var(--evcc-sem-error) 10%, transparent) )` src/styles/learning.js:103
- src/styles/learning.js:560 (background)

**`--evcc-learning-confidence-low-text`** — Learning Confidence Low Text · default `var(--evcc-sem-error)` src/styles/learning.js:100
- src/styles/learning.js:561 (color)

**`--evcc-learning-confidence-medium-bg`** — Learning Confidence Medium BG · default `color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent)` src/styles/learning.js:80
- src/styles/theme-preview.js:537

**`--evcc-learning-confidence-medium-border`** — Learning Confidence Medium Border · default `color-mix(in srgb, var(--evcc-sem-warning) 42%, transparent)` src/styles/learning.js:83
- src/styles/learning.js:553 (border-color)
- src/styles/theme-preview.js:538

**`--evcc-learning-confidence-medium-gradient`** — Learning Confidence Medium Gradient · default `linear-gradient( 135deg, color-mix(in srgb, var(--evcc-sem-warning) 26%, transparent), color-mix(in srgb, var(--evcc-sem-warning) 10%, transparent) )` src/styles/learning.js:89
- src/styles/learning.js:554 (background)

**`--evcc-learning-confidence-medium-text`** — Learning Confidence Medium Text · default `var(--evcc-sem-warning)` src/styles/learning.js:86
- src/styles/learning.js:555 (color)
- src/styles/theme-preview.js:539

**`--evcc-learning-confidence-neutral-border`** — Learning Confidence Neutral Border · default `var(--evcc-border-default)` src/styles/learning.js:111
- src/styles/learning.js:523
- src/styles/learning.js:565 (border-color)

**`--evcc-learning-confidence-neutral-gradient`** — Learning Confidence Neutral Gradient · default `linear-gradient( 135deg, color-mix(in srgb, var(--evcc-text-muted) 16%, transparent), color-mix(in srgb, var(--evcc-text-muted) 8%, transparent) )` src/styles/learning.js:117
- src/styles/learning.js:525 (background)
- src/styles/learning.js:566 (background)

**`--evcc-learning-confidence-neutral-text`** — Learning Confidence Neutral Text · default `var(--evcc-text-secondary)` src/styles/learning.js:114
- src/styles/learning.js:526 (color)
- src/styles/learning.js:567 (color)

**`--evcc-learning-note-text`** — Learning Note Text · default `var(--evcc-text-muted)` src/styles/rooms.js:832
- src/styles/rooms.js:885 (color)
- src/styles/theme-preview.js:598 (color)

**`--evcc-learning-panel-bg`** — Learning Panel BG · default `var(--evcc-surface-panel)` src/styles/learning.js:38
- src/styles/learning.js:233 (background)
- src/styles/theme-preview.js:592

**`--evcc-learning-panel-border`** — Learning Panel Border · default `var(--evcc-border-default)` src/styles/learning.js:41
- src/styles/learning.js:232
- src/styles/theme-preview.js:593 (border-color)

**`--evcc-learning-panel-shadow`** — Learning Panel Shadow · default `var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14))` src/styles/learning.js:44
- src/styles/learning.js:179
- src/styles/learning.js:184
- src/styles/learning.js:189
- src/styles/learning.js:234 (box-shadow)
- src/styles/theme-preview.js:594 (box-shadow)

**`--evcc-learning-reanchor-border`** — Learning Reanchor Border · default `color-mix(in srgb, var(--evcc-accent) 34%, transparent)` src/styles/learning.js:156
- src/styles/learning.js:338 (border-color)

**`--evcc-learning-reanchor-highlight`** — Learning Reanchor Highlight · default `color-mix(in srgb, var(--evcc-accent) 16%, transparent)` src/styles/learning.js:153
- src/styles/theme-preview.js:589

**`--evcc-learning-text-muted`** — Learning Text Muted · default `var(--evcc-text-muted)` src/styles/learning.js:53
- src/styles/learning.js:484 (color)

**`--evcc-learning-text-primary`** — Learning Text Primary · default `var(--evcc-text-primary)` src/styles/learning.js:47
- src/styles/learning.js:236 (color)
- src/styles/learning.js:270 (color)
- src/styles/learning.js:282 (color)
- src/styles/learning.js:460 (color)

**`--evcc-learning-text-secondary`** — Learning Text Secondary · default `var(--evcc-text-secondary)` src/styles/learning.js:50
- src/styles/learning.js:304 (color)
- src/styles/learning.js:319 (color)
- src/styles/learning.js:395 (color)
- src/styles/learning.js:421 (color)
- src/styles/learning.js:472 (color)
- src/styles/theme-preview.js:598

**`--evcc-learning-warning-text`** — Learning Warning Text · default `var(--evcc-sem-warning)` src/styles/rooms.js:834
- src/styles/rooms.js:889 (color)

## Modals & Overlays  ·  36 static / 36

**`--evcc-modal-accent`** — Modal Accent · default src/styles/modal-host.js:123
- src/styles/dialog.js:44 (border-color)
- src/styles/modal-host.js:239 (--evcc-accent)
- src/styles/modal-host.js:465
- src/styles/modal-host.js:470
- src/styles/modal-host.js:475
- src/styles/modals.js:196
- src/styles/modals.js:201
- src/styles/modals.js:206
- src/styles/modals.js:214
- src/styles/modals.js:219
- src/styles/modals.js:223
- src/styles/theme-preview.js:637
- src/styles/theme-preview.js:638
- src/styles/theme-preview.js:639

**`--evcc-modal-accent-bg`** — Modal Accent BG · default src/styles/modal-host.js:125
- custom_components/eufy_vacuum/themes/preloaded.py:207
- src/styles/modal-host.js:135 (--evcc-modal-chip-active-bg)
- src/styles/modal-host.js:464
- src/styles/modals.js:195
- src/styles/theme-preview.js:637 (background)

**`--evcc-modal-accent-border`** — Modal Accent Border · default src/styles/modal-host.js:126
- custom_components/eufy_vacuum/themes/preloaded.py:208
- src/styles/modal-host.js:136 (--evcc-modal-chip-active-border)
- src/styles/modal-host.js:474
- src/styles/modals.js:205
- src/styles/theme-preview.js:638 (border-color)

**`--evcc-modal-accent-text`** — Modal Accent Text · default src/styles/modal-host.js:124
- custom_components/eufy_vacuum/themes/preloaded.py:209
- src/styles/modal-host.js:137 (--evcc-modal-chip-active-text)
- src/styles/modal-host.js:469
- src/styles/modals.js:200
- src/styles/modals.js:218
- src/styles/theme-preview.js:639 (color)

**`--evcc-modal-backdrop-bg`** — Modal Backdrop BG · default src/styles/modal-host.js:100, src/styles/modal-host.js:608
- src/styles/modal-host.js:150 (background)
- src/styles/modal-host.js:687 (background)
- src/styles/modals.js:77 (background)
- src/styles/modals.js:414 (background)
- src/styles/theme-preview.js:612 (background)

**`--evcc-modal-backdrop-blur`** — Modal Backdrop Blur · default —
- src/styles/modal-host.js:154
- src/styles/modals.js:81
- src/styles/theme-preview.js:613

**`--evcc-modal-bg`** — Modal BG · default src/styles/modal-host.js:99, src/styles/modal-host.js:607
- src/styles/modal-host.js:179 (background)
- src/styles/modal-host.js:636 (background)
- src/styles/modal-host.js:742 (background)
- src/styles/modal-host.js:751 (background)
- src/styles/modals.js:96 (background)
- src/styles/modals.js:400 (background)
- src/styles/theme-preview.js:625 (background)

**`--evcc-modal-border`** — Modal Border · default src/styles/modal-host.js:101, src/styles/modal-host.js:609
- src/styles/modal-host.js:183
- src/styles/modal-host.js:640
- src/styles/modals.js:100
- src/styles/modals.js:298
- src/styles/modals.js:404
- src/styles/theme-preview.js:626

**`--evcc-modal-border-default`** — Modal Border Default · default src/styles/modal-host.js:102, src/styles/modal-host.js:610
- src/styles/modal-host.js:215 (--evcc-border-default)
- src/styles/modal-host.js:661 (--evcc-border-default)

**`--evcc-modal-border-strong`** — Modal Border Strong · default src/styles/modal-host.js:103, src/styles/modal-host.js:611
- src/styles/dialog.js:37
- src/styles/modal-host.js:223 (--evcc-border-strong)
- src/styles/modal-host.js:669 (--evcc-border-strong)
- src/styles/modals.js:382

**`--evcc-modal-border-subtle`** — Modal Border Subtle · default src/styles/modal-host.js:104, src/styles/modal-host.js:612
- src/styles/modal-host.js:219 (--evcc-border-subtle)
- src/styles/modal-host.js:369
- src/styles/modal-host.js:514
- src/styles/modal-host.js:529
- src/styles/modal-host.js:665 (--evcc-border-subtle)
- src/styles/modal-host.js:753
- src/styles/modals.js:131
- src/styles/modals.js:180
- src/styles/room-estimate.js:38
- src/styles/room-estimate.js:60

**`--evcc-modal-chip-active-bg`** — Modal Chip Active BG · default src/styles/modal-host.js:135
- src/styles/modal-host.js:463 (background)
- src/styles/modals.js:194 (background)

**`--evcc-modal-chip-active-border`** — Modal Chip Active Border · default src/styles/modal-host.js:136
- src/styles/modal-host.js:473 (border-color)
- src/styles/modals.js:204 (border-color)

**`--evcc-modal-chip-active-text`** — Modal Chip Active Text · default src/styles/modal-host.js:137
- src/styles/modal-host.js:468 (color)
- src/styles/modals.js:199 (color)

**`--evcc-modal-chip-bg`** — Modal Chip BG · default src/styles/modal-host.js:129, src/styles/modal-host.js:626
- src/styles/modal-host.js:328 (--evcc-chip-bg)
- src/styles/modal-host.js:482 (background)
- src/styles/modals.js:373 (background)

**`--evcc-modal-chip-border`** — Modal Chip Border · default src/styles/modal-host.js:130, src/styles/modal-host.js:627
- src/styles/modal-host.js:324 (--evcc-chip-border)
- src/styles/modal-host.js:491 (border-color)
- src/styles/modals.js:381 (border-color)

**`--evcc-modal-chip-hover-bg`** — Modal Chip Hover BG · default src/styles/modal-host.js:132, src/styles/modal-host.js:629
- src/styles/modal-host.js:342 (--evcc-chip-hover-bg)
- src/styles/modals.js:213 (background)

**`--evcc-modal-chip-hover-border`** — Modal Chip Hover Border · default src/styles/modal-host.js:133, src/styles/modal-host.js:630
- src/styles/modal-host.js:350 (--evcc-chip-hover-border)
- src/styles/modals.js:222 (border-color)

**`--evcc-modal-chip-hover-text`** — Modal Chip Hover Text · default src/styles/modal-host.js:134, src/styles/modal-host.js:631
- src/styles/modal-host.js:346 (--evcc-chip-hover-text)
- src/styles/modals.js:217 (color)

**`--evcc-modal-chip-text`** — Modal Chip Text · default src/styles/modal-host.js:131, src/styles/modal-host.js:628
- src/styles/modal-host.js:332 (--evcc-chip-text)
- src/styles/modal-host.js:486 (color)
- src/styles/modals.js:377 (color)

**`--evcc-modal-footer-bg`** — Modal Footer BG · default src/styles/modal-host.js:115, src/styles/modal-host.js:620
- src/styles/modal-host.js:518 (background)
- src/styles/modals.js:184 (background)

**`--evcc-modal-header-bg`** — Modal Header BG · default src/styles/modal-host.js:114, src/styles/modal-host.js:619
- src/styles/modal-host.js:374 (background)
- src/styles/modals.js:136 (background)

**`--evcc-modal-input-bg`** — Modal Input BG · default src/styles/modal-host.js:110, src/styles/modal-host.js:617
- src/styles/dialog.js:36 (background)
- src/styles/modal-host.js:206 (--evcc-surface-input)
- src/styles/modal-host.js:656 (--evcc-surface-input)

**`--evcc-modal-padding`** — Modal Padding · default —
- src/styles/modal-host.js:367 (padding)
- src/styles/modal-host.js:397 (padding)
- src/styles/modal-host.js:512 (padding)
- src/styles/modals.js:129 (padding)
- src/styles/modals.js:160 (padding)
- src/styles/modals.js:178 (padding)
- src/styles/theme-preview.js:624 (padding)

**`--evcc-modal-radius`** — Modal Radius · default —
- src/styles/modal-host.js:187 (border-radius)
- src/styles/modals.js:103 (border-radius)
- src/styles/modals.js:426 (border-radius)
- src/styles/theme-preview.js:627 (border-radius)

**`--evcc-modal-section-gap`** — Modal Section Gap · default —
- src/styles/modal-host.js:400 (gap)
- src/styles/modals.js:163 (gap)

**`--evcc-modal-shadow`** — Modal Shadow · default —
- src/styles/modal-host.js:190 (box-shadow)
- src/styles/modal-host.js:644 (box-shadow)
- src/styles/modals.js:106 (box-shadow)
- src/styles/modals.js:408 (box-shadow)
- src/styles/theme-preview.js:628 (box-shadow)

**`--evcc-modal-surface-input`** — Modal Surface Input · default src/styles/modal-host.js:108, src/styles/modal-host.js:615
- src/styles/modal-host.js:207
- src/styles/modal-host.js:657

**`--evcc-modal-surface-panel`** — Modal Surface Panel · default src/styles/modal-host.js:107, src/styles/modal-host.js:614
- src/styles/modal-host.js:211 (--evcc-surface-panel)
- src/styles/modal-host.js:652 (--evcc-surface-panel)
- src/styles/room-estimate.js:40
- src/styles/room-estimate.js:62

**`--evcc-modal-surface-section`** — Modal Surface Section · default src/styles/modal-host.js:109, src/styles/modal-host.js:616
- src/styles/modals.js:165 (background)

**`--evcc-modal-text-muted`** — Modal Text Muted · default src/styles/modal-host.js:120, src/styles/modal-host.js:624
- src/styles/modal-host.js:235 (--evcc-text-muted)
- src/styles/modal-host.js:451 (color)
- src/styles/modal-host.js:483
- src/styles/modal-host.js:550 (color)
- src/styles/modal-host.js:681 (--evcc-text-muted)
- src/styles/modals.js:240 (color)
- src/styles/modals.js:323 (color)
- src/styles/modals.js:374

**`--evcc-modal-text-primary`** — Modal Text Primary · default src/styles/modal-host.js:118, src/styles/modal-host.js:622
- src/styles/dialog.js:24 (color)
- src/styles/dialog.js:38 (color)
- src/styles/modal-host.js:166 (color)
- src/styles/modal-host.js:194 (color)
- src/styles/modal-host.js:227 (--evcc-text-primary)
- src/styles/modal-host.js:382 (color)
- src/styles/modal-host.js:648 (color)
- src/styles/modal-host.js:673 (--evcc-text-primary)
- src/styles/modals.js:117 (color)
- src/styles/modals.js:144 (color)
- src/styles/room-estimate.js:45 (color)

**`--evcc-modal-text-secondary`** — Modal Text Secondary · default src/styles/modal-host.js:119, src/styles/modal-host.js:623
- src/styles/modal-host.js:231 (--evcc-text-secondary)
- src/styles/modal-host.js:537 (color)
- src/styles/modal-host.js:677 (--evcc-text-secondary)
- src/styles/modals.js:378
- src/styles/room-estimate.js:17 (color)
- src/styles/room-estimate.js:41 (color)
- src/styles/room-estimate.js:61 (color)

**`--evcc-modal-warning-bg`** — Modal Warning BG · default src/styles/modal-host.js:140
- src/styles/modal-host.js:578 (background)
- src/styles/modals.js:272 (background)
- src/styles/theme-preview.js:562 (background)

**`--evcc-modal-warning-border`** — Modal Warning Border · default src/styles/modal-host.js:141
- src/styles/modal-host.js:492
- src/styles/modal-host.js:582
- src/styles/modals.js:276
- src/styles/theme-preview.js:563 (border-color)

**`--evcc-modal-warning-text`** — Modal Warning Text · default src/styles/modal-host.js:142
- src/styles/modal-host.js:487
- src/styles/modal-host.js:579
- src/styles/modal-host.js:583
- src/styles/modal-host.js:586 (color)
- src/styles/modals.js:273
- src/styles/modals.js:277
- src/styles/modals.js:280 (color)
- src/styles/theme-preview.js:564 (color)

## Animal Companion  ·  0 static + 14 dynamic / 14

**`--evcc-animal-eye-good`** — Eye — Good (>50% battery) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye-mid`** — Eye — Mid (25–50%) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye-warn`** — Eye — Warn (15–25%) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye-low`** — Eye — Low (≤15%) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye-charging`** — Eye — Charging (pulses) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-fur`** — Fur (all animals) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-fur-shadow`** — Fur Shadow (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-fur-highlight`** — Fur Highlight (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-eye`** — Eye Base (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-pupil`** — Pupil (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-nose`** — Nose (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-whisker`** — Whisker (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-ear-inner`** — Ear Inner (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-white-tip`** — White Tip / Accent (all) · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

## Animal Companion — Cat  ·  0 static + 14 dynamic / 14

*(template — Dog/Raccoon/Parrot/Snake mirror it; consumed dynamically in animal-svg/)*

**`--evcc-animal-cat-eye-good`** — Eye — Good · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye-mid`** — Eye — Mid · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye-warn`** — Eye — Warn · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye-low`** — Eye — Low · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye-charging`** — Eye — Charging · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-fur`** — Fur · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-fur-shadow`** — Fur Shadow · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-fur-highlight`** — Fur Highlight · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-eye`** — Eye Base · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-pupil`** — Pupil · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-nose`** — Nose · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-whisker`** — Whisker · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-ear-inner`** — Ear Inner · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

**`--evcc-animal-cat-white-tip`** — White Tip / Accent · default —
- _no STATIC consumer — consumed dynamically (animal): `src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`_

## Shared Foundations  ·  15 static / 15

**`--evcc-font-family`** — Font Family · default —
- src/styles/modal-host.js:163
- src/styles/shell.js:57
- src/styles/theme-preview.js:121
- src/styles/toast-host.js:59

**`--evcc-gap`** — Gap · default `var(--evcc-space-md)` src/styles/foundation.js:248
- src/styles/foundation.js:341 (gap)
- src/styles/shell.js:104 (gap)
- src/styles/theme-preview.js:79 (gap)
- src/styles/theme-preview.js:92 (gap)
- src/styles/theme-preview.js:327 (gap)

**`--evcc-grid-gap`** — Grid Gap · default `12px` src/styles/layout.js:63
- src/styles/base-station.js:7 (gap)
- src/styles/base-station.js:12 (gap)
- src/styles/layout.js:64 (--evcc-room-grid-gap)
- src/styles/layout.js:78
- src/styles/maintenance.js:134 (gap)
- src/styles/maintenance.js:139 (gap)
- src/styles/metrics.js:7 (gap)
- src/styles/metrics.js:18 (gap)
- src/styles/review.js:7 (gap)
- src/styles/review.js:12 (gap)

**`--evcc-hover-lift`** — Hover Lift · default —
- src/styles/order.js:121
- src/styles/rooms.js:422
- src/styles/rooms.js:717
- src/styles/theme-preview.js:229

**`--evcc-pad`** — Pad · default `var(--evcc-space-lg)` src/styles/foundation.js:249
- src/styles/foundation.js:342 (padding)
- src/styles/foundation.js:342
- src/styles/foundation.js:398 (padding)
- src/styles/theme-preview.js:182 (padding)

**`--evcc-press-scale`** — Press Scale · default —
- src/styles/rooms.js:727

**`--evcc-radius-card`** — Radius Card · default `var(--ha-card-border-radius, 12px)` src/styles/foundation.js:236
- src/cards/dashboard-card.js:1244 (--radius)
- src/cards/profile-card.js:41 (--radius)
- src/room-card.js:379 (--radius)
- src/styles/external-jobs.js:69 (border-radius)
- src/styles/external-jobs.js:164 (border-radius)
- src/styles/learning.js:629 (border-radius)
- src/styles/map.js:93 (border-radius)
- src/styles/map.js:553 (border-radius)
- src/styles/map.js:991 (border-radius)
- src/styles/rooms.js:390 (border-radius)
- src/styles/shell.js:48 (border-radius)
- src/styles/shell.js:266 (border-radius)
- src/styles/theme-preview.js:36 (border-radius)
- src/styles/theme-preview.js:97 (border-radius)
- src/styles/theme-preview.js:174 (border-radius)
- src/styles/theme-preview.js:605 (border-radius)
- src/styles/theme-preview.js:670 (border-radius)
- src/styles/theme.js:526 (border-radius)
- src/styles/theme.js:789 (border-radius)
- src/styles/theme.js:809 (border-radius)
- src/styles/theme.js:868 (border-radius)

**`--evcc-radius-chip`** — Radius Chip · default `999px` src/styles/foundation.js:238
- src/styles/external-jobs.js:51 (border-radius)
- src/styles/foundation.js:380 (border-radius)
- src/styles/learning.js:57 (--evcc-learning-chip-radius)
- src/styles/order.js:59 (border-radius)
- src/styles/rooms.js:630 (border-radius)
- src/styles/shell.js:211 (border-radius)
- src/styles/shell.js:287 (border-radius)
- src/styles/shell.js:355 (border-radius)
- src/styles/theme-preview.js:163 (border-radius)
- src/styles/theme-preview.js:450 (border-radius)

**`--evcc-radius-inner`** — Radius Inner · default `8px` src/styles/foundation.js:237
- src/cards/dashboard-card.js:1340 (border-radius)
- src/cards/dashboard-card.js:1363 (border-radius)
- src/cards/dashboard-card.js:1369 (border-radius)
- src/cards/dashboard-card.js:1375 (border-radius)
- src/styles/base-station.js:21 (border-radius)
- src/styles/base-station.js:65 (border-radius)
- src/styles/external-jobs.js:24 (border-radius)
- src/styles/external-jobs.js:105 (border-radius)
- src/styles/external-jobs.js:121 (border-radius)
- src/styles/external-jobs.js:132 (border-radius)
- src/styles/external-jobs.js:143 (border-radius)
- src/styles/external-jobs.js:153 (border-radius)
- src/styles/external-jobs.js:174 (border-radius)
- src/styles/job-summary.js:41 (border-radius)
- src/styles/maintenance.js:23 (border-radius)
- src/styles/maintenance.js:105 (border-radius)
- src/styles/maintenance.js:148 (border-radius)
- src/styles/maintenance.js:210 (border-radius)
- src/styles/maintenance.js:272 (border-radius)
- src/styles/maintenance.js:400 (border-radius)
- src/styles/maintenance.js:443 (border-radius)
- src/styles/metrics.js:27 (border-radius)
- src/styles/metrics.js:94 (border-radius)
- src/styles/metrics.js:187 (border-radius)
- src/styles/metrics.js:222 (border-radius)
- src/styles/metrics.js:327 (border-radius)
- src/styles/modal-host.js:424 (border-radius)
- src/styles/review.js:21 (border-radius)
- src/styles/review.js:95 (border-radius)
- src/styles/review.js:110 (border-radius)
- src/styles/review.js:131 (border-radius)
- src/styles/review.js:219 (border-radius)
- src/styles/review.js:230 (border-radius)
- src/styles/rooms.js:136 (border-radius)
- src/styles/rooms.js:149 (border-radius)
- src/styles/rooms.js:162 (border-radius)
- src/styles/rooms.js:1420 (border-radius)
- src/styles/run-profiles.js:59 (border-radius)
- src/styles/run-profiles.js:89 (border-radius)
- src/styles/run-profiles.js:158 (border-radius)
- src/styles/run-profiles.js:243 (border-radius)
- src/styles/saved-zones.js:93 (border-radius)
- src/styles/saved-zones.js:144 (border-radius)
- src/styles/saved-zones.js:231 (border-radius)
- src/styles/theme-preview.js:193 (border-radius)
- src/styles/theme-preview.js:205 (border-radius)
- src/styles/theme-preview.js:550 (border-radius)
- src/styles/theme.js:70 (border-radius)
- src/styles/theme.js:136 (border-radius)
- src/styles/theme.js:364 (border-radius)
- src/styles/theme.js:470 (border-radius)
- src/styles/theme.js:563 (border-radius)
- src/styles/theme.js:713 (border-radius)
- src/styles/theme.js:732 (border-radius)
- src/styles/theme.js:890 (border-radius)
- src/styles/theme.js:1338 (border-radius)

**`--evcc-radius-panel`** — Radius Panel · default —
- src/styles/learning.js:231 (border-radius)
- src/styles/learning.js:779 (border-radius)
- src/styles/room-access.js:14 (border-radius)
- src/styles/rooms.js:261 (border-radius)
- src/styles/rooms.js:333 (border-radius)
- src/styles/rooms.js:806 (border-radius)
- src/styles/run-profiles.js:26 (border-radius)
- src/styles/run-profiles.js:357 (border-radius)
- src/styles/saved-zones.js:15 (border-radius)
- src/styles/theme-preview.js:184 (border-radius)

**`--evcc-section-gap`** — Section Gap · default —
- src/styles/rooms.js:47 (gap)
- src/styles/theme-preview.js:643 (gap)

**`--evcc-space-lg`** — Space Lg · default `16px` src/styles/foundation.js:246
- src/styles/foundation.js:249 (--evcc-pad)
- src/styles/shell.js:385 (padding)

**`--evcc-space-md`** — Space Md · default `12px` src/styles/foundation.js:245
- src/styles/foundation.js:248 (--evcc-gap)
- src/styles/rooms.js:48 (padding-bottom)
- src/styles/rooms.js:50 (margin-bottom)
- src/styles/rooms.js:57 (gap)
- src/styles/rooms.js:332 (margin-bottom)
- src/styles/rooms.js:1423 (margin-bottom)
- src/styles/theme.js:13 (gap)
- src/styles/theme.js:21 (gap)

**`--evcc-space-sm`** — Space Sm · default `8px` src/styles/foundation.js:244
- src/styles/rooms.js:876 (margin-top)
- src/styles/rooms.js:1418 (gap)

**`--evcc-transition-normal`** — Transition Normal · default `150ms ease` src/styles/foundation.js:286, src/styles/modal-host.js:242
- src/styles/base-station.js:97
- src/styles/base-station.js:98
- src/styles/foundation.js:57
- src/styles/foundation.js:58
- src/styles/foundation.js:59
- src/styles/foundation.js:60
- src/styles/maintenance.js:288
- src/styles/maintenance.js:289
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
- src/styles/rooms.js:395
- src/styles/rooms.js:396
- src/styles/rooms.js:397
- src/styles/rooms.js:398
- src/styles/rooms.js:708
- src/styles/rooms.js:709
- src/styles/rooms.js:710
- src/styles/rooms.js:711
- src/styles/rooms.js:712
- src/styles/rooms.js:713
- src/styles/shell.js:217
- src/styles/shell.js:218
- src/styles/shell.js:293
- src/styles/shell.js:294
- src/styles/shell.js:361
- src/styles/shell.js:362
- src/styles/theme.js:139 (transition)
- src/styles/theme.js:472 (transition)

---

## Tokens with no STATIC consumer  ·  134

**134 of these are consumed DYNAMICALLY and are not dead** — this tracer is a regex scan and cannot follow a `var()` whose name is built at runtime. Only the final section is a concern.

### Consumed dynamically — animal  ·  84

`src/theme-tokens/animals.js` builds `--evcc-animal-${animal}-${suffix}`; consumed in `animal-svg/`. Working as intended.

`--evcc-animal-eye-good`, `--evcc-animal-eye-mid`, `--evcc-animal-eye-warn`, `--evcc-animal-eye-low`, `--evcc-animal-eye-charging`, `--evcc-animal-fur`, `--evcc-animal-fur-shadow`, `--evcc-animal-fur-highlight`, `--evcc-animal-eye`, `--evcc-animal-pupil`, `--evcc-animal-nose`, `--evcc-animal-whisker`, `--evcc-animal-ear-inner`, `--evcc-animal-white-tip`, `--evcc-animal-cat-eye-good`, `--evcc-animal-cat-eye-mid`, `--evcc-animal-cat-eye-warn`, `--evcc-animal-cat-eye-low`, `--evcc-animal-cat-eye-charging`, `--evcc-animal-cat-fur`, `--evcc-animal-cat-fur-shadow`, `--evcc-animal-cat-fur-highlight`, `--evcc-animal-cat-eye`, `--evcc-animal-cat-pupil`, `--evcc-animal-cat-nose`, `--evcc-animal-cat-whisker`, `--evcc-animal-cat-ear-inner`, `--evcc-animal-cat-white-tip`, `--evcc-animal-dog-eye-good`, `--evcc-animal-dog-eye-mid`, `--evcc-animal-dog-eye-warn`, `--evcc-animal-dog-eye-low`, `--evcc-animal-dog-eye-charging`, `--evcc-animal-dog-fur`, `--evcc-animal-dog-fur-shadow`, `--evcc-animal-dog-fur-highlight`, `--evcc-animal-dog-eye`, `--evcc-animal-dog-pupil`, `--evcc-animal-dog-nose`, `--evcc-animal-dog-whisker`, `--evcc-animal-dog-ear-inner`, `--evcc-animal-dog-white-tip`, `--evcc-animal-raccoon-eye-good`, `--evcc-animal-raccoon-eye-mid`, `--evcc-animal-raccoon-eye-warn`, `--evcc-animal-raccoon-eye-low`, `--evcc-animal-raccoon-eye-charging`, `--evcc-animal-raccoon-fur`, `--evcc-animal-raccoon-fur-shadow`, `--evcc-animal-raccoon-fur-highlight`, `--evcc-animal-raccoon-eye`, `--evcc-animal-raccoon-pupil`, `--evcc-animal-raccoon-nose`, `--evcc-animal-raccoon-whisker`, `--evcc-animal-raccoon-ear-inner`, `--evcc-animal-raccoon-white-tip`, `--evcc-animal-parrot-eye-good`, `--evcc-animal-parrot-eye-mid`, `--evcc-animal-parrot-eye-warn`, `--evcc-animal-parrot-eye-low`, `--evcc-animal-parrot-eye-charging`, `--evcc-animal-parrot-fur`, `--evcc-animal-parrot-fur-shadow`, `--evcc-animal-parrot-fur-highlight`, `--evcc-animal-parrot-eye`, `--evcc-animal-parrot-pupil`, `--evcc-animal-parrot-nose`, `--evcc-animal-parrot-whisker`, `--evcc-animal-parrot-ear-inner`, `--evcc-animal-parrot-white-tip`, `--evcc-animal-snake-eye-good`, `--evcc-animal-snake-eye-mid`, `--evcc-animal-snake-eye-warn`, `--evcc-animal-snake-eye-low`, `--evcc-animal-snake-eye-charging`, `--evcc-animal-snake-fur`, `--evcc-animal-snake-fur-shadow`, `--evcc-animal-snake-fur-highlight`, `--evcc-animal-snake-eye`, `--evcc-animal-snake-pupil`, `--evcc-animal-snake-nose`, `--evcc-animal-snake-whisker`, `--evcc-animal-snake-ear-inner`, `--evcc-animal-snake-white-tip`

### Consumed dynamically — floor-material  ·  38

`src/renderers/floor-texture-surface.js` and `src/bindings/map.js` build `--evcc-floor-${type}-…` from the material key. Working as intended.

`--evcc-floor-tile-base`, `--evcc-floor-tile-grout`, `--evcc-floor-tile-accent`, `--evcc-floor-tile-opacity-card`, `--evcc-floor-tile-face-opacity`, `--evcc-floor-tile-grout-opacity`, `--evcc-floor-tile-line-opacity`, `--evcc-floor-wood-base`, `--evcc-floor-wood-accent`, `--evcc-floor-wood-opacity-card`, `--evcc-floor-wood-depth-opacity`, `--evcc-floor-wood-grain-opacity`, `--evcc-floor-wood-seam-opacity`, `--evcc-floor-marble-base`, `--evcc-floor-marble-micro`, `--evcc-floor-marble-opacity-card`, `--evcc-floor-marble-base-opacity`, `--evcc-floor-marble-micro-opacity`, `--evcc-floor-concrete-base`, `--evcc-floor-concrete-accent`, `--evcc-floor-concrete-opacity-card`, `--evcc-floor-concrete-broad-opacity`, `--evcc-floor-concrete-micro-opacity`, `--evcc-floor-carpet-low-base`, `--evcc-floor-carpet-low-weave`, `--evcc-floor-carpet-low-opacity-card`, `--evcc-floor-carpet-low-base-opacity`, `--evcc-floor-carpet-low-weave-opacity`, `--evcc-floor-carpet-high-base`, `--evcc-floor-carpet-high-weave`, `--evcc-floor-carpet-high-opacity-card`, `--evcc-floor-carpet-high-base-opacity`, `--evcc-floor-carpet-high-weave-opacity`, `--evcc-floor-granite-light-base`, `--evcc-floor-granite-light-aggregate`, `--evcc-floor-granite-light-opacity-card`, `--evcc-floor-granite-light-base-opacity`, `--evcc-floor-granite-light-aggregate-opacity`

### Consumed dynamically — room-fill  ·  12

`src/cards/map-room-color.js` — `roomFillTokenName(i)` builds `--evcc-room-fill-N`, 1-based and wrapping at 12 (contract pinned by MRC-1..MRC-7). Working as intended.

`--evcc-room-fill-1`, `--evcc-room-fill-2`, `--evcc-room-fill-3`, `--evcc-room-fill-4`, `--evcc-room-fill-5`, `--evcc-room-fill-6`, `--evcc-room-fill-7`, `--evcc-room-fill-8`, `--evcc-room-fill-9`, `--evcc-room-fill-10`, `--evcc-room-fill-11`, `--evcc-room-fill-12`

### No consumer anywhere  ·  0

Seeded + exposed in the editor but nothing reads them — no-op editor knobs (wire them up or drop them). THIS is the list a cleanup pass should act on, not the count above.

None — every catalog token is consumed, statically or dynamically.

---

## var() → non-catalog tokens  ·  12

Used in CSS but not in the editor registry (dynamic fragments or intentional internals like `--evcc-grp`).

- `--evcc-animal-X` — custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js:289
- `--evcc-panel-offset` — src/styles/foundation.js:167
- `--evcc-space-xs` — src/styles/learning.js:325
- `--evcc-map-rotation` — src/styles/map.js:668, src/styles/map.js:739, src/styles/map.js:896, src/styles/map.js:933, src/styles/map.js:965
- `--evcc-mascot-flip` — src/styles/map.js:668
- `--evcc-map-ov-savedzone` — src/styles/map.js:915, src/styles/map.js:917, src/styles/map.js:946
- `--evcc-map-ov-savedzone-text` — src/styles/map.js:936
- `--evcc-grp` — src/styles/map.js:1379
- `--evcc-a11y-font-family` — src/styles/modal-host.js:163, src/styles/shell.js:57, src/styles/theme-preview.js:121, src/styles/toast-host.js:59
- `--evcc-surface-hover` — src/styles/rooms.js:1117
- `--evcc-sheen-dir` — src/styles/rooms.js:1271, src/styles/rooms.js:1284, src/styles/rooms.js:1285, src/styles/rooms.js:1324, src/styles/rooms.js:1331, src/styles/rooms.js:1333
- `--evcc-font-preview` — src/styles/theme.js:1035

---

## dynamic var(--evcc-…${…}) sites  ·  3

- custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js:316
- custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js:317
- src/renderers/floor-texture-surface.js:104

