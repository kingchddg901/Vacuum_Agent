# -*- coding: utf-8 -*-
"""Generate a brand's regime table from the fixture manifest.

    python scripts/sync-upkeep-regimes.py [brand ...]      default: every brand below

WAS `sync-dreame-regimes.py`. It is not Dreame's any more: the manifest carries every brand we
port and the emitter now lives in `adapters/upkeep_keys.py`, so the only per-brand facts left
are the UPSTREAM PLATFORM to filter on and where to write. Adding a brand is one row in BRANDS.
"""
import collections
import csv
import importlib
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO = 'C:/Users/CKing/Documents/GITHUB/eufy-vacuum-manager'
CSV = 'C:/Users/CKing/Documents/durable/dreame-port-fixture/derived/manifest_table.csv'

# THE FILTER IS THE UPSTREAM PLATFORM, NEVER `brand`. That is what brands.py routes on. Without
# it the generator silently wrote 13 eufy T-codes into DREAME_MODEL_REGIMES and the Dreame
# adapter would have claimed models it has never seen. `brand` cannot do this job: mova, trouver
# and xiaomi are Dreame-built rebadges served by the same integration.
BRANDS = {
    'dreame': dict(
        platform='dreame_vacuum', pkg='dreame', const='DREAME_MODEL_REGIMES',
        title='Dreame upkeep REGIMES — the three measured fields the guide is derived from.',
        why=[
            'This replaces the model -> guide-family routing. A family was a NAME SLUG: 648 of 700 were a',
            "substring of the model's own name, 262 values over 25 real regimes, and Dreame's own accessory",
            'kits group 21 model ids across 4 product lines into ONE regime that our families split into',
            'eight. The three fields below are MEASURED off the manuals instead, and they are what the card',
            'content actually depends on — nothing else in a row reaches the guide.',
        ],
    ),
    'roborock': dict(
        platform='roborock', pkg='roborock', const='ROBOROCK_MODEL_REGIMES',
        title='Roborock upkeep REGIMES — the three measured fields the guide is derived from.',
        why=[
            'This replaces a MAINTENANCE TIER column (standard / auto_empty / wash_station) that was hand',
            'assigned per model and wrong on 8 of 41. The measurement is in the manifest: the four G10 and',
            'T7S Plus rows shipped as `standard` (no dock at all) actually carry one, and the four Q-series',
            "rows shipped as `auto_empty` were given the '+' variant's dock when the base SKU has none.",
            'Those 8 are not corrected here — the column is DELETED. dock_tier is measured per model now,',
            'and Roborock adds ZERO new keys and ZERO new card sets to the shared set.',
        ],
    ),
    'eufy': dict(
        platform='robovac_mqtt', pkg='eufy', const='EUFY_MODEL_REGIMES',
        title='Eufy upkeep REGIMES — the three measured fields the guide is derived from.',
        why=[
            'This replaces five hand-authored guide families and their seventeen language packs. The',
            'families were per-PRODUCT-LINE (x8_series, l60_series, s1_pro, x10_pro_omni, omni_c20), so a',
            'new model meant authoring a sixth and translating it. The card content actually depends on',
            'the three MEASURED fields below, and Eufy adds ZERO new keys to the shared set - every card',
            'it renders already existed for Dreame and is already translated into all 18 languages.',
        ],
    ),
}

# THE VENDOR'S WORD IS NORMALISED HERE, SO IT NEVER REACHES CODE. Chris: "simumop really is
# just a special cloth, its a bit of noise" -- 8 rows of 754. The CSV keeps `SimuMop` because
# that is the measurement and the manifest is the provenance record; the emitted table carries
# only the neutral vocabulary {cloth, pad, roller, track}. Doing it here rather than in emit()
# is what lets adapters/upkeep_keys.py hold no brand vocabulary and no alias parameter. The
# emitted CARDS are unchanged either way -- emit() used to alias internally -- what changes is
# that the regime ID reads `cloth|...` and the two SimuMop regimes merge into their cloth twins.
MOP_NORMALISE = {'SimuMop': 'cloth'}


def generate(cfg, all_rows):
    out = os.path.join(REPO, 'custom_components/eufy_vacuum/adapters',
                       cfg['pkg'], 'upkeep_regimes.py')
    rows = [r for r in all_rows if r.get('upstream_platform') == cfg['platform']]
    rows.sort(key=lambda r: r['model'])
    print('manifest: %d rows, %d on %s' % (len(all_rows), len(rows), cfg['platform']))

    L = []
    a = L.append
    a('# -*- coding: utf-8 -*-')
    a('"""%s' % cfg['title'])
    a('')
    a('    %s[model_id] = (mop_type, dock_tier, tanks)' % cfg['const'])
    a('')
    for line in cfg['why']:
        a(line)
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
    a('Regenerate with scripts/sync-upkeep-regimes.py.')
    a('"""')
    a('')
    a('from __future__ import annotations')
    a('')
    a('%s: dict[str, tuple[str, str, str]] = {' % cfg['const'])
    for r in rows:
        a('    %-30s ("%s", "%s", "%s"),'
          % ('"%s":' % r['model'], r['mop_type'], r['dock_tier'], r['tanks']))
    a('}')
    a('')
    reg = collections.Counter((r['mop_type'], r['dock_tier'], r['tanks']) for r in rows)
    a('# The %d distinct regimes present, largest first — a comment, not a second copy. Derive from' % len(reg))
    a('# %s rather than reading this:' % cfg['const'])
    for k, v in reg.most_common():
        a('#   %-9s %-17s %-8s %3d models' % (k[0], k[1], k[2], v))
    io.open(out, 'w', encoding='utf-8', newline='\n').write("\n".join(L) + "\n")
    print('wrote %s' % out)

    # Second pass: the count is MEASURED off the table we just wrote, never typed.
    # THE NEUTRAL EMITTER, NOT THE BRAND MODULE. `emit` is every brand's now, so reaching
    # through `adapters.<pkg>.upkeep_keys` would both re-export it for no reason and create a
    # chicken-and-egg: the brand surface imports the regime table this function is writing.
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    uk = importlib.import_module('custom_components.eufy_vacuum.adapters.upkeep_keys')
    cards = len({repr(uk.emit(*k)) for k in reg})
    txt = io.open(out, encoding='utf-8').read().replace('__CARDS__', str(cards))
    io.open(out, 'w', encoding='utf-8', newline='\n').write(txt)
    print('   %d models, %d bytes, %d distinct regimes, %d distinct CARD SETS'
          % (len(rows), os.path.getsize(out), len(reg), cards))


def main():
    wanted = sys.argv[1:] or sorted(BRANDS)
    rows = list(csv.DictReader(io.open(CSV, encoding='utf-8-sig', newline='')))
    for r in rows:
        r['mop_type'] = MOP_NORMALISE.get(r['mop_type'], r['mop_type'])
    for brand in wanted:
        if brand not in BRANDS:
            sys.exit('unknown brand %r; known: %s' % (brand, ', '.join(sorted(BRANDS))))
        generate(BRANDS[brand], rows)


main()
