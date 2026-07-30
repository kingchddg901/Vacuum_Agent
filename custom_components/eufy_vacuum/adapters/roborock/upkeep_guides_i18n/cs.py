"""Upkeep-guide translations — Czech (cs).

Per-language module under roborock/upkeep_guides_i18n/; __init__.py assembles them
into ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS. Pure data.

Best-effort AI DRAFT translated from the English base guide
(roborock_upkeep_guides.py), pending native review. Mirrors the German (de) module's
structure. Frequencies match our English base (not any source model's) so the
interval reads the same in every language. Overlaid PER FIELD on the English guide —
anything omitted falls back to English.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Týdně",
        "replace_frequency": "Každých 6-12 měsíců",
        "steps": [
            "Otočte robota dnem vzhůru a stisknutím pojistky uvolněte kryt hlavního kartáče.",
            "Vyjměte hlavní kartáč a poté z obou konců sejměte a vyčistěte krytku ložiska.",
            "Přiloženým čisticím nástrojem odřízněte a odstraňte veškeré vlasy namotané na kartáči a ložiskách.",
            "Nasaďte zpět krytky ložisek a kryt ve směru uzamčení a poté kryt zatlačte, dokud pojistka nezacvakne.",
        ],
        "notes": [
            "Pokud prostor pro kartáč vypadá znečištěně, před opětovným nasazením jej vytřete.",
            "Pro nejlepší úklid vyměňujte hlavní kartáč každých 6-12 měsíců.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Měsíčně",
        "replace_frequency": "Každých 3-6 měsíců",
        "steps": [
            "Otočte robota dnem vzhůru a vyšroubujte šroub, který drží boční kartáč.",
            "Sejměte boční kartáč a odstraňte vlasy a nečistoty namotané kolem čepu.",
            "Nasaďte boční kartáč zpět a utáhněte šroub.",
        ],
        "notes": [
            "Vyměňte boční kartáč každých 3-6 měsíců, nebo dříve, pokud je ohnutý nebo roztřepený.",
        ],
    },
    "filter": {
        "clean_frequency": "Každé 2 týdny",
        "replace_frequency": "Každých 6-12 měsíců",
        "steps": [
            "Stiskněte pojistku nádoby na prach, vyjměte nádobu, otevřete její kryt a vysypte ji.",
            "Vyjměte omyvatelný filtr a opláchněte jej pod čistou vodou — bez čisticího prostředku.",
            "Poklepáním rámečku filtru o tvrdý povrch uvolněte zachycený prach a oplachujte jej, dokud není čistý.",
            "Před opětovným nasazením nechte filtr uschnout na vzduchu alespoň 24 hodin.",
        ],
        "notes": [
            "Na filtr nikdy nepoužívejte čisticí prostředek, horkou vodu, myčku nádobí ani vysoušeč vlasů.",
            "Když máte druhý filtr na výměnu, jeden může úplně uschnout, zatímco druhý se používá.",
        ],
    },
    "sensor": {
        "clean_frequency": "Měsíčně",
        "replace_frequency": None,
        "steps": [
            "Otřete šest snímačů srázu na spodní straně měkkým suchým hadříkem.",
            "Otřete nástěnný snímač na pravém okraji a snímač nabíjení.",
            "Zároveň otřete nabíjecí kontakty na spodní straně.",
        ],
        "notes": [
            "Používejte pouze suchý hadřík — čisticí kapaliny mohou poškodit kryty snímačů.",
        ],
    },
    "dustbin": {
        "clean_frequency": "Týdně",
        "replace_frequency": None,
        "steps": [
            "Otevřete horní kryt, stiskněte pojistku nádoby na prach a nádobu vyjměte.",
            "Otevřete kryt nádoby na prach a vysypte obsah do koše.",
            "V případě potřeby opláchněte nádobu na prach čistou vodou — nejprve vyjměte filtr a nepoužívejte čisticí prostředek.",
        ],
        "notes": [
            "Před opětovným nasazením nádobu na prach zcela osušte, aby vlhký prach neucpal filtr.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Po každém použití",
        "replace_frequency": "Každých 3-6 měsíců",
        "steps": [
            "Po každém vytírání sejměte mopovací hadřík z vytíracího modulu.",
            "Opláchněte jej do čista a nechte uschnout.",
        ],
        "notes": [
            "Hadřík vždy sejměte kvůli čištění, aby se špinavá voda nemohla vrátit do nádržky a ucpat filtr.",
            "Znovupoužitelný hadřík vyměňujte každých 3-6 měsíců; jednorázový hadřík vyměňte po každém použití.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Měsíčně",
        "replace_frequency": None,
        "steps": [
            "Otočte robota dnem vzhůru a vypačte všesměrové (přední otočné) kolečko.",
            "Odstraňte vlasy a nečistoty namotané kolem tělesa kolečka a osy.",
            "Pevně zatlačte kolečko zpět na místo.",
        ],
        "notes": [
            "Držák kolečka nelze odstranit — vyjmout lze pouze samotné kolečko.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Týdně",
        "replace_frequency": None,
        "steps": [
            "Jednou týdně zkontrolujte, zda na osách obou hlavních hnacích kol nejsou namotané vlasy nebo nitě.",
            "Odřízněte a odstraňte vše zachycené, aby se kola volně otáčela.",
            "Pokud jsou na kolech přilepené nečistoty, otřete je mírně navlhčeným hadříkem.",
        ],
        "notes": [
            "Volně se otáčející kola udržují robota v přímém směru a pomáhají mu překonávat prahy.",
        ],
    },
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "Každých 1-3 měsíců",
    "steps": [
        "Vytáhněte vodní filtry z nádržky podle návodu.",
        "Nasaďte nové filtry a zasuňte je zpět na místo.",
    ],
    "notes": [
        "Vyměňujte každých 1-3 měsíců podle kvality vody a četnosti vytírání.",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "Když je plný (přibližně každých 7 týdnů)",
    "steps": [
        "Otevřete kryt prachové přihrádky doku.",
        "Vytáhněte plný sáček na prach přímo ven — držadlo jej při vytahování utěsní, takže prach zůstane uvnitř.",
        "Zasuňte nový sáček na prach, dokud nezapadne, a poté zavřete kryt.",
    ],
    "notes": [
        "Před zavřením krytu vždy vložte sáček, jinak se dok automaticky vyprázdní bez něj.",
        "Pokud dok nějakou dobu nebyl používán, vyprázdněte nádobu na prach robota ručně a zkontrolujte, zda je vstup vzduchu volný.",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "Podle potřeby",
    "replace_frequency": None,
    "steps": [
        "Vyjměte nádržku na čistou vodu z doku a otevřete její horní kryt.",
        "Naplňte ji studenou vodou z kohoutku (čisticí roztok Roborock přidejte pouze tehdy, pokud to váš dok podporuje).",
        "Zavřete kryt a vraťte nádržku zpět do doku.",
    ],
    "notes": [
        "Používejte pouze studenou vodu — horká voda může nádržku zdeformovat.",
        "Před opětovným nasazením otřete z vnějšku veškerou vodu.",
    ],
}
_DIRTY_WATER_TANK = {
    "clean_frequency": "Podle potřeby",
    "replace_frequency": None,
    "steps": [
        "Otevřete víko nádržky na špinavou vodu a vylijte odpadní vodu.",
        "Přidejte trochu čisté vody, zavřete a zajistěte víko, protřepejte a poté ji znovu vylijte, abyste nádržku vypláchli.",
        "Zajistěte víko a vraťte nádržku zpět do doku.",
    ],
    "notes": [
        "Víko nádržky na špinavou vodu nelze sejmout — vypláchněte jej na místě.",
        "Používejte pouze studenou vodu a před opětovným nasazením otřete vnějšek dosucha.",
    ],
}

_BASE = {**_STANDARD, "water_filter": _WATER_FILTER}
GUIDE_TRANSLATIONS = {
    "standard": _BASE,
    "auto_empty": {**_BASE, "dock_dust_bag": _DOCK_DUST_BAG},
    "wash_station": {
        **_BASE, "dock_dust_bag": _DOCK_DUST_BAG,
        "clean_water_tank": _CLEAN_WATER_TANK, "dirty_water_tank": _DIRTY_WATER_TANK,
    },
}
