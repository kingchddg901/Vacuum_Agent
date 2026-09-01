"""Content upgrade: regenerate the eufy/roborock guide libs from the provenance-merge.
DRY by default (structural checks, no writes); --emit writes the Python libs.

MERGE (per family/component):
  EN base      : lift wording if the lift covers the component; else keep current
                 (never drop a component the current shipped but the corpus missed).
  translations : per (comp, lang) pick, in order:
                   1. lift, FULLY real (every cell provenance 'lift')  -> lift
                   2. current translation exists                       -> current
                   3. lift, any (partial/draft)                        -> lift
                   4. else absent (card falls back to English)
                 Frequencies stay translated: from the chosen source's freq, or the
                 guide-frequency-translations.json map — never the lift's English freq.
"""
import importlib.util, json, os, sys, glob, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = "C:/Users/CKing/Documents/GITHUB/eufy-vacuum-manager"
SP = os.path.dirname(os.path.abspath(__file__))
ADAPTERS = os.path.join(ROOT, "custom_components", "eufy_vacuum", "adapters")
EMIT = "--emit" in sys.argv
# READ "current" FROM THE BACKUP (pristine pre-swap), never the repo — so re-emitting is
# idempotent and can never feed the merge its own previous output.
BK = open(os.path.join(SP, "backup_path.txt"), encoding="utf-8").read().strip()
FREQMAP = json.load(open(os.path.join(ROOT, "scripts/data/guide-frequency-translations.json"), encoding="utf-8"))

def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
e_g = _load(os.path.join(BK, "eufy", "eufy_upkeep_guides.py"), "bk_e_g")
r_g = _load(os.path.join(BK, "roborock", "roborock_upkeep_guides.py"), "bk_r_g")

def load_i18n(brand):
    pkg = os.path.join(BK, brand, "upkeep_guides_i18n")
    spec = importlib.util.spec_from_file_location(f"bk_{brand}_i18n", os.path.join(pkg, "__init__.py"),
                                                  submodule_search_locations=[pkg])
    m = importlib.util.module_from_spec(spec); sys.modules[f"bk_{brand}_i18n"] = m; spec.loader.exec_module(m)
    return getattr(m, "UPKEEP_GUIDE_TRANSLATIONS", getattr(m, "ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS", {}))

def load_lift(brand):
    out = collections.defaultdict(lambda: collections.defaultdict(dict))
    langs = set()
    for f in glob.glob(os.path.join(SP, "guides", brand, "*", "*.json")):
        lang = os.path.basename(os.path.dirname(f)); langs.add(lang)
        d = json.load(open(f, encoding="utf-8"))
        for comp, g in d.get("components", {}).items():
            out[d["family"]][comp][lang] = g
    return out, sorted(l for l in langs if l != "en")

BR = {"eufy": (e_g.UPKEEP_GUIDE_LIBRARY, load_i18n("eufy")),
      "roborock": (r_g.ROBOROCK_UPKEEP_GUIDE_LIBRARY, load_i18n("roborock"))}

def steps_txt(cells): return [c["t"] for c in (cells or [])]
def all_real(cells): return bool(cells) and all(c.get("p") == "lift" for c in cells)
def any_content(g): return bool((g or {}).get("steps") or (g or {}).get("notes"))
def tfreq(lang, en_freq, src_freq):
    if src_freq: return src_freq
    if not en_freq: return None
    return FREQMAP.get(lang, {}).get(en_freq)  # translate English via the map; None if unknown

for brand, (cur_en, cur_tr) in BR.items():
    lift, langs = load_lift(brand)
    merged_en = {}                                   # fam -> comp -> {clean,replace,steps,notes}
    merged_tr = {l: collections.defaultdict(dict) for l in langs}
    stats = collections.Counter()
    for fam in sorted(set(cur_en) | set(lift)):
        merged_en[fam] = {}
        comps = list(cur_en.get(fam, {})) + [c for c in lift.get(fam, {}) if c not in cur_en.get(fam, {})]
        for comp in comps:
            in_lift = comp in lift.get(fam, {})
            cen = cur_en.get(fam, {}).get(comp, {})
            len_ = lift.get(fam, {}).get(comp, {}).get("en", {})
            # --- EN base ---
            if in_lift and any_content(len_):
                # Keep the CURRENT frequency phrase (standard + already translatable via
                # the freq map / i18n); only take the lift's freq for a brand-new component.
                en_freq_c, en_freq_r = cen.get("clean_frequency") or len_.get("clean_frequency"), cen.get("replace_frequency") or len_.get("replace_frequency")
                merged_en[fam][comp] = {"clean_frequency": en_freq_c, "replace_frequency": en_freq_r,
                                        "steps": steps_txt(len_.get("steps")), "notes": steps_txt(len_.get("notes"))}
                stats["en_from_lift"] += 1 if comp in cur_en.get(fam, {}) else 0
                stats["en_new_component"] += 0 if comp in cur_en.get(fam, {}) else 1
            else:
                merged_en[fam][comp] = {"clean_frequency": cen.get("clean_frequency"), "replace_frequency": cen.get("replace_frequency"),
                                        "steps": list(cen.get("steps", [])), "notes": list(cen.get("notes", []))}
                stats["en_kept_current"] += 1
            en_c, en_r = merged_en[fam][comp]["clean_frequency"], merged_en[fam][comp]["replace_frequency"]
            # --- translations (per lang) ---
            for lang in langs:
                lg = lift.get(fam, {}).get(comp, {}).get(lang)
                cg = cur_tr.get(lang, {}).get(fam, {}).get(comp)
                pick = None
                if lg and all_real(lg.get("steps")):        pick, src = lg, "lift"
                elif any_content(cg):                        pick, src = cg, "cur"
                elif lg and any_content(lg) and any(c.get("p") in ("lift", "draft") for c in (lg.get("steps") or [])):
                    pick, src = lg, "lift"
                if not pick: continue
                if src == "lift":
                    cfr = cg or {}  # keep the manual's translated frequency if this component had one
                    tr = {"clean_frequency": cfr.get("clean_frequency") or tfreq(lang, en_c, None),
                          "replace_frequency": cfr.get("replace_frequency") or tfreq(lang, en_r, None),
                          "steps": steps_txt(pick.get("steps")), "notes": steps_txt(pick.get("notes"))}
                else:
                    tr = {"clean_frequency": pick.get("clean_frequency"), "replace_frequency": pick.get("replace_frequency"),
                          "steps": list(pick.get("steps", [])), "notes": list(pick.get("notes", []))}
                merged_tr[lang][fam][comp] = tr
                stats[f"tr_{src}"] += 1
    # structural checks
    lost = [(f, c) for f in cur_en for c in cur_en[f] if c not in merged_en.get(f, {})]
    print(f"\n=== {brand.upper()} ===")
    print(f"  families: {len(merged_en)}  components: {sum(len(v) for v in merged_en.values())}")
    print(f"  EN: from-lift {stats['en_from_lift']}, new-component {stats['en_new_component']}, kept-current {stats['en_kept_current']}")
    print(f"  translations: lift {stats['tr_lift']}, current {stats['tr_cur']}  ({len(langs)} langs)")
    print(f"  COVERAGE CHECK — components lost vs current: {len(lost)} {lost[:5] if lost else '(none)'}")
    if EMIT:
        def pylit(v): return json.dumps(v, ensure_ascii=False, indent=1).replace(": null", ": None")
        base = os.path.join(ADAPTERS, brand, f"{brand}_upkeep_guides.py")
        var = "UPKEEP_GUIDE_LIBRARY" if brand == "eufy" else "ROBOROCK_UPKEEP_GUIDE_LIBRARY"
        hdr = (f'"""GENERATED — do not hand-edit. Content upgrade from the lifted TM (real\n'
               f'manufacturer wording harvested from the parallel manual/app editions).\n'
               f'Regenerate: scripts/build_guides.py (reshape TM -> per-family) then\n'
               f'scripts/emit_libs.py --emit (provenance-merge vs the pre-swap libs).\n'
               f'Inputs frozen + hashed in durable/guide-libs-backup-20260901-072708/SNAPSHOT.txt.\n'
               f'Shape: {var}[family][component] = {{clean_frequency, replace_frequency, steps[], notes[]}}."""\n\n')
        open(base, "w", encoding="utf-8").write(hdr + f"{var} = " + pylit(merged_en) + "\n")
        for lang in langs:
            p = os.path.join(ADAPTERS, brand, "upkeep_guides_i18n", f"{lang.replace('-', '_').lower()}.py")
            lh = (f'"""GENERATED — do not hand-edit. {lang} upkeep-guide translations from the lifted TM.\n'
                  f'Regenerate: scripts/build_guides.py then scripts/emit_libs.py --emit."""\n\n')
            open(p, "w", encoding="utf-8").write(lh + "GUIDE_TRANSLATIONS = " + pylit(dict(merged_tr[lang])) + "\n")
        print(f"  EMITTED {base} + {len(langs)} i18n packs")
print("\nDRY-RUN (no writes) — pass --emit to write." if not EMIT else "\nEMITTED.")
