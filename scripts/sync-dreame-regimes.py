# -*- coding: utf-8 -*-
"""Generate the Dreame regime table for the repo from the fixture manifest."""
import csv, io, os, sys, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
FIX = 'C:/Users/CKing/Documents/durable/dreame-port-fixture'
OUT = ('C:/Users/CKing/Documents/GITHUB/eufy-vacuum-manager/custom_components/'
       'eufy_vacuum/adapters/dreame/upkeep_regimes.py')
rows = list(csv.DictReader(io.open(os.path.join(FIX, 'derived/manifest_table.csv'),
                                   encoding='utf-8-sig', newline='')))
# THE TABLE IS NO LONGER DREAME-ONLY. It carries every brand we port, keyed by the upstream
# integration that serves the model -- which is what brands.py routes on. Without this filter
# the generator silently wrote 13 eufy T-codes into DREAME_MODEL_REGIMES, and the Dreame adapter
# would have claimed models it has never seen. `brand` cannot do this job: mova/trouver/xiaomi
# are Dreame-built rebadges served by the same integration.
PLATFORM = 'dreame_vacuum'
_all = len(rows)
rows = [r for r in rows if r.get('upstream_platform', PLATFORM) == PLATFORM]
print('manifest: %d rows, %d on %s' % (_all, len(rows), PLATFORM))
rows.sort(key=lambda r: r['model'])

L = []
a = L.append
a('# -*- coding: utf-8 -*-')
a('"""Dreame upkeep REGIMES — the three measured fields the guide is derived from.')
a('')
a('    DREAME_MODEL_REGIMES[model_id] = (mop_type, dock_tier, tanks)')
a('')
a('This replaces the model -> guide-family routing. A family was a NAME SLUG: 648 of 700 were a')
a("substring of the model's own name, 262 values over 25 real regimes, and Dreame's own accessory")
a('kits group 21 model ids across 4 product lines into ONE regime that our families split into')
a('eight. The three fields below are MEASURED off the manuals instead, and they are what the card')
a('content actually depends on — nothing else in a row reaches the guide.')
a('')
a('THE TABLE IS THE AUTHORITY, NOT A DERIVED CACHE. `upkeep_keys.py` computes the card from these')
a('three fields at import; the card sets are not stored. Shipping the derived answer instead of')
a('the inputs is how a cache starts being treated as a source.')
a('')
a('Adding a model is ONE ROW here. No authored text, no new family, no translation work — the')
# THE CARD COUNT IS DERIVED, NEVER TYPED. It was hardcoded as 7 and stayed 7 through a change
# that made it 10 -- a generator asserting a number it does not compute is a comment pretending
# to be a check. __CARDS__ is substituted after the table is written, by importing the emitter
# against the table we just produced.
a('%d models below already collapse to __CARDS__ distinct cards, so a new row almost always renders a' % len(rows))
a('card that already exists and is already translated into all 18 languages.')
a('')
a('GENERATED from durable/dreame-port-fixture/derived/manifest_table.csv (outside git — it carries')
a('the full provenance: per-model doc ties, measurement basis per field, and the hand-walk record).')
a('Regenerate with scripts/sync-dreame-regimes.py.')
a('"""')
a('')
a('from __future__ import annotations')
a('')
a('DREAME_MODEL_REGIMES: dict[str, tuple[str, str, str]] = {')
for r in rows:
    a('    %-30s ("%s", "%s", "%s"),' % ('"%s":' % r['model'], r['mop_type'], r['dock_tier'], r['tanks']))
a('}')
a('')
reg = collections.Counter((r['mop_type'], r['dock_tier'], r['tanks']) for r in rows)
a('# The %d distinct regimes present, largest first — a comment, not a second copy. Derive from' % len(reg))
a('# DREAME_MODEL_REGIMES rather than reading this:')
for k, v in reg.most_common():
    a('#   %-9s %-17s %-8s %3d models' % (k[0], k[1], k[2], v))
io.open(OUT, 'w', encoding='utf-8', newline='\n').write("\n".join(L) + "\n")
print("wrote %s" % OUT)

# Second pass: the emitter reads the table we just wrote, so the count is MEASURED.
import importlib
sys.path.insert(0, 'C:/Users/CKing/Documents/GITHUB/eufy-vacuum-manager')
_uk = importlib.import_module('custom_components.eufy_vacuum.adapters.dreame.upkeep_keys')
_cards = len({repr(_uk.emit(*k)) for k in reg})
_txt = io.open(OUT, encoding='utf-8').read().replace('__CARDS__', str(_cards))
io.open(OUT, 'w', encoding='utf-8', newline=chr(10)).write(_txt)
print("   %d models, %d bytes, %d distinct regimes, %d distinct CARD SETS"
      % (len(rows), os.path.getsize(OUT), len(reg), _cards))
