"""SKELETON: reshape the care TM onto the REAL guide structure (existing families/tiers +
component keys) and emit the import-system layout:

    guides/<brand>/index.json                model->family + family->components + display names
    guides/<brand>/<locale>/<family>.json    {component_key: {clean_frequency, replace_frequency,
                                              steps:[{t,p,src}], notes:[{t,p,src}]}}

TM stays immutable evidence; the structure keys by component + carries `src` pointers back to it.
Presentation cleanup (marker/section-number strip) happens here (renderer layer). Prints the
reshape decisions + coverage; flags unmapped components + missing keys for review (not silent)."""
import sys, json, re, collections, pathlib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DUR = pathlib.Path("C:/Users/CKing/Documents/durable")
OUT = pathlib.Path(__file__).resolve().parent / "guides"
LOCALES = ["en","ar","cs","de","es","fr","he","id","it","ja","ko","nl","pl","pt","ru","tr","zh-Hans","zh-Hant"]

def strip_marker(s):
    s=(s or "").strip()
    s=re.sub(r"^[\u2460-\u2473]\s*","",s); s=re.sub(r"^\(?\d{1,2}[.)]\s*","",s); s=re.sub(r"^[\u2022\u25cf\-\*]\s*","",s)
    return re.sub(r"\s+"," ",s).strip()
_LEAD=re.compile(r"^\s*\d{1,2}[.,]\d+(?:[.,]\d+)*\s*"); _TRAIL=re.compile(r"\s*\(\s*\d{1,2}[.,]\d+.*?\)\s*$")
# section intros / preambles / general notes are NOT components -> drop, don't flag as unmapped
_META=re.compile(r"(?i)^(general (precautions|caution|note)|cleaning and maintenance|routine maintenance|"
                 r"section intro|\d?\.?\s*cleaning and maintenance|maintenance \(|precautions)")

# ---- brand config: component keys (render order), care-name -> key mapper (ordered) ----
EUFY_KEYS=["filter","sensor","side_brush","main_brush","mop_cloth","cleaning_tray","caster_wheel","main_wheel","dust_bag","hair_collection_box","clean_water_tank","dirty_water_tank"]
EUFY_MAP=[(r"side brush","side_brush"),(r"rolling brush|roller brush|main brush","main_brush"),
          (r"hair collection box|hair box","hair_collection_box"),(r"dust bag","dust_bag"),
          (r"dirty.?water (tank|reservoir)|dirty water|sewage","dirty_water_tank"),(r"clean.?water tank|clean water","clean_water_tank"),
          (r"cleaning tray|\btray\b","cleaning_tray"),(r"\bmop","mop_cloth"),
          (r"sensor|charging|camera","sensor"),(r"swivel wheel|omni.?directional wheel|caster","caster_wheel"),
          (r"\bwheels?\b","main_wheel"),
          (r"filter|dust box|dust bin|dust collector|dustbin","filter")]
EUFY_FAM={"T2351":"x10_pro_omni","T2080":"s1_pro","T2071":"s1_pro","T2280":"omni_c20",
          "T2261":"x8_series","T2262":"x8_series","T2266":"x8_series","T2276":"x8_series",
          "T2267":"l60_series","T2268":"l60_series","T2277":"l60_series","T2278":"l60_series"}
EUFY_FAMNAMES={"x10_pro_omni":"X10 Pro Omni","s1_pro":"S1 Pro / S1","omni_c20":"Omni C20",
               "x8_series":"X8 / X8 Pro Series","l60_series":"L60 / L60 Hybrid / L60 SES Series"}

ROBO_KEYS=["main_brush","side_brush","filter","sensor","dustbin","mop_cloth","water_filter",
           "caster_wheel","main_wheel","dust_bag","clean_water_tank","dirty_water_tank","air_duct","maintenance_brush"]
ROBO_DOCK={"dust_bag","clean_water_tank","dirty_water_tank"}
ROBO_MAP=[(r"moving (the )?dock","__skip__"),(r"\bbattery\b","__skip__"),
          (r"high.?speed maintenance brush|maintenance brush","maintenance_brush"),(r"air duct","air_duct"),
          (r"main brush","main_brush"),(r"side brush","side_brush"),(r"dust ?bag","dust_bag"),
          (r"clean.?water tank|clean water","clean_water_tank"),(r"dirty.?water tank|dirty water|sewage","dirty_water_tank"),
          (r"cleaning tank|cleaning tray module","dirty_water_tank"),(r"adjustable water tank|water tank","clean_water_tank"),
          (r"water filter","water_filter"),(r"\bmop","mop_cloth"),(r"washable filter|\bfilter\b","filter"),
          (r"sensor|camera|charging","sensor"),(r"dustbin|dust bin|dust box","dustbin"),
          (r"omni.?direction|caster|swivel","caster_wheel"),(r"main wheel|drive wheel|\bwheels?\b","main_wheel")]
ROBO_TIER={  # normalized care model -> tier
 "wash_station":["s8 pro ultra","s8 maxv ultra","s7 pro ultra","s7 maxv ultra","qrevo master","qrevo curv",
   "qrevo maxv","qrevo pro","qrevo s","q revo","g20s ultra","saros 10","saros 10r"],
 "auto_empty":["q5 pro","q7 max","q8 max","q10"],
 "standard":["s8","s7 maxv","s7","s6 maxv","q7","q5"]}
ROBO_FAMNAMES={"standard":"Roborock","auto_empty":"Roborock (auto-empty dock)","wash_station":"Roborock (wash & dry station)"}

def normm(s):
    s=re.sub(r"\(.*?\)","",s); s=re.sub(r"(?i)\broborock\b|\bseries\b","",s); return re.sub(r"\s+"," ",s).strip().lower()
def to_key(name, mapper):
    n=name.lower()
    for pat,key in mapper:
        if re.search(pat,n): return key
    return None

def build(brand):
    care=[c for c in json.loads((DUR/f"{brand}-port-fixture"/f"{brand}_care_corpus.json").read_text(encoding="utf-8")) if c.get("found")]
    tm=json.loads((DUR/f"{brand}-port-fixture"/"care_tm_full.json").read_text(encoding="utf-8"))["tm"]
    def cell(s,L,name=False):
        k=strip_marker(s)
        if L=="en": t,p=k,"source"
        else:
            e=tm.get(k,{}); e=e.get(L); t,p=(e["t"],e["p"]) if e else (k,"gap")
        t=_LEAD.sub("",t).strip()
        return {"t":t,"p":p,"src":k}
    def entries(strings,L): return [cell(s,L) for s in strings if s.strip()]

    mapper = EUFY_MAP if brand=="eufy" else ROBO_MAP
    keys   = EUFY_KEYS if brand=="eufy" else ROBO_KEYS
    unmapped=collections.Counter()

    # model -> family + gather per-(family,key) the component's steps/notes (first non-empty wins per family)
    fam_comp=collections.defaultdict(dict)     # family -> key -> {steps,notes}
    fam_freq=collections.defaultdict(dict)     # family -> key -> {clean,replace}
    fam_models=collections.defaultdict(list)
    def assign_family(c):
        if brand=="eufy": return EUFY_FAM.get(c.get("tcode"))
        nm=normm(c["model"])
        for tier,models in ROBO_TIER.items():
            if nm in models: return tier
        return "standard"
    # roborock builds a shared BASE then composes tiers; eufy builds per family directly
    bucket=collections.defaultdict(dict) if brand=="roborock" else None
    bfreq=collections.defaultdict(dict) if brand=="roborock" else None
    for c in care:
        fam=assign_family(c)
        if not fam: continue
        fam_models[fam].append(c.get("tcode") or c["model"])
        tgt = bucket if brand=="roborock" else fam_comp[fam]
        tfr = bfreq  if brand=="roborock" else fam_freq[fam]
        for comp in (c.get("components") or []):
            name=comp.get("component") or comp.get("name") or ""
            if _META.match(name): continue
            key=to_key(name, mapper)
            if key=="__skip__": continue  # recognized + intentionally excluded (Moving the Dock, Battery)
            if not key: unmapped[name[:40]]+=1; continue
            if key not in tgt:  # first model to define this component wins its wording
                tgt[key]={"steps":[s for s in (comp.get("steps") or []) if s.strip()],
                          "notes":[n for n in (comp.get("notes") or []) if n.strip()]}
        for fr in (c.get("frequencies") or []):
            key=to_key(fr.get("component",""),mapper)
            if key and key not in tfr:
                tfr[key]={"clean":fr.get("clean_frequency"),"replace":fr.get("replace_frequency")}

    # compose families
    if brand=="roborock":
        base={k:v for k,v in bucket.items() if k not in ROBO_DOCK}
        fam_comp["standard"]=dict(base)
        fam_comp["auto_empty"]={**base, **({k:bucket[k] for k in ["dock_dust_bag"] if k in bucket})}
        fam_comp["wash_station"]={**base, **({k:bucket[k] for k in ROBO_DOCK if k in bucket})}
        for f in fam_comp: fam_freq[f]=bfreq

    # emit
    outb=OUT/brand; outb.mkdir(parents=True,exist_ok=True)
    famnames = EUFY_FAMNAMES if brand=="eufy" else ROBO_FAMNAMES
    # model->family index
    if brand=="eufy": model_fam={code:EUFY_FAM[code] for code in EUFY_FAM}
    else:
        model_fam={}
        for tier,models in ROBO_TIER.items():
            for m in models: model_fam[m]=tier
    index={"brand":brand,"families":{f:{"name":famnames.get(f,f),
              "components":[k for k in keys if k in fam_comp.get(f,{})]} for f in sorted(fam_comp)},
           "models":model_fam}
    (outb/"index.json").write_text(json.dumps(index,ensure_ascii=False,indent=1),encoding="utf-8")
    for L in LOCALES:
        (outb/L).mkdir(exist_ok=True)
        for fam,comps in fam_comp.items():
            fj={"family":fam,"brand":brand,"locale":L,"components":{}}
            for key in keys:
                if key not in comps: continue
                fr=fam_freq.get(fam,{}).get(key,{})
                fj["components"][key]={"clean_frequency":fr.get("clean"),"replace_frequency":fr.get("replace"),
                    "steps":entries(comps[key]["steps"],L),"notes":entries(comps[key]["notes"],L)}
            (outb/L/f"{fam}.json").write_text(json.dumps(fj,ensure_ascii=False,indent=1),encoding="utf-8")

    print(f"=== {brand}: {len(fam_comp)} families/tiers, {len(LOCALES)} locales ===")
    for f in sorted(fam_comp):
        present=[k for k in keys if k in fam_comp[f]]
        missing=[k for k in keys if k not in fam_comp[f] and (brand=="eufy" or k not in ROBO_DOCK or f=="wash_station")]
        print(f"   {f:14s} components({len(present)}): {present}")
        if missing: print(f"                  MISSING vs key set: {missing}")
    if unmapped:
        print(f"   UNMAPPED care components (review): {dict(unmapped)}")

for b in ("eufy","roborock"):
    build(b)
