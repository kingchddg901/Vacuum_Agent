"""Full-corpus clone POINTERS from declared asset identity.

Chris's framing, and the output honours it: "not a proof yet but it can be a pointer."
Shared artwork is documentation lineage. It says two manuals were built from the same
drawings, which is strong circumstantial evidence for the same machine and is NOT proof
of identical hardware. Every row below is a lead to check, not a finding.

The reg-coded subset gave the calibration (2.17% base rate, 0.67-0.80 precision at
31-37x lift). This run extends it to the ~1,450 documents with NO reg code, where the
artwork is the only identity evidence there is.
"""
import json, os, sys, time, pickle, collections

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, 'C:/Users/CKing/Documents/GITHUB/eufy-vacuum-manager/scripts')
from dreame_asset_ids import doc_asset_ids  # noqa: E402

D = 'C:/Users/CKing/Documents/durable/dreame-port-fixture/derived'
MAN = 'C:/Users/CKing/Documents/durable/dreame-port-fixture/manuals'
SP = os.path.dirname(__file__)

ct = {d['file']: d for d in json.load(open(D + '/doc_model_crosstable.json', encoding='utf-8'))}
man = json.load(open(D + '/corpus-manifest.json', encoding='utf-8'))

targets = []
for x in man:
    f = x['name']
    p = os.path.join(MAN, x.get('folder') or '', f)
    if os.path.exists(p):
        d = ct.get(f, {})
        targets.append((f, p, (d.get('base_codes') or []), d.get('names_resolved') or []))
print(f'documents on disk: {len(targets)}', flush=True)

out = {}
t0 = time.time()
errs = 0
for n, (f, p, codes, names) in enumerate(targets, 1):
    try:
        dids, assets, blocks = doc_asset_ids(p)
    except Exception:
        errs += 1
        continue
    if dids:
        out[f] = {'codes': codes, 'names': names, 'dids': dids, 'blocks': blocks}
    if n % 200 == 0:
        print(f'  {n}/{len(targets)}  {time.time()-t0:6.1f}s  with-ids={len(out)}', flush=True)
print(f'done: {len(out)} documents carry asset IDs, {errs} errors, {time.time()-t0:.1f}s', flush=True)
pickle.dump(out, open(os.path.join(SP, 'full_assets.pkl'), 'wb'))

df = collections.Counter()
for v in out.values():
    for d in v['dids']:
        df[d] += 1
print(f'distinct DocumentIDs: {len(df)}')
rare = {d for d, c in df.items() if c <= 3}
print(f'rare ids (in <=3 documents): {len(rare)}')

# group documents by the rare ids they share
byid = collections.defaultdict(set)
for f, v in out.items():
    for d in v['dids'] & rare:
        byid[d].add(f)

pair = collections.Counter()
for d, fs in byid.items():
    if 2 <= len(fs) <= 3:
        for a, b in ((x, y) for i, x in enumerate(sorted(fs)) for y in sorted(fs)[i+1:]):
            pair[(a, b)] += 1

strong = {k: v for k, v in pair.items() if v >= 2}
print(f'document pairs sharing >=2 rare assets: {len(strong)}')

# collapse to code/name level and split by whether codes already answer it
rows = []
for (a, b), n in sorted(strong.items(), key=lambda kv: -kv[1]):
    ca, cb = out[a]['codes'], out[b]['codes']
    na, nb = out[a]['names'], out[b]['names']
    same_code = bool(set(ca) & set(cb)) if (ca and cb) else False
    known = 'same-code' if same_code else ('cross-code' if (ca and cb) else 'NO CODE')
    rows.append({'n': n, 'a': a, 'b': b, 'codes_a': ca, 'codes_b': cb,
                 'names_a': na, 'names_b': nb, 'class': known})
json.dump(rows, open(os.path.join(D, 'clone_pointers.json'), 'w', encoding='utf-8'),
          indent=1, ensure_ascii=False)

kinds = collections.Counter(r['class'] for r in rows)
print(f'\nby class: {dict(kinds)}')
print('\nPOINTERS INVOLVING A DOCUMENT WITH NO REG CODE (new information):')
shown = 0
for r in rows:
    if r['class'] != 'NO CODE':
        continue
    print(f"  {r['n']:3d} shared  {r['a'][:44]:46s} {str(r['names_a'])[:30]}")
    print(f"               {r['b'][:44]:46s} {str(r['names_b'])[:30]}")
    shown += 1
    if shown >= 25:
        print('   ...')
        break
print(f'\nwritten {D}/clone_pointers.json')
