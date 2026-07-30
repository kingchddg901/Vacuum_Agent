"""Upkeep-guide translations — Čeština (cs).

One of the per-language modules under ``upkeep_guides_i18n/``; ``__init__.py``
assembles them into ``UPKEEP_GUIDE_TRANSLATIONS``. Pure data.

Shape::

    GUIDE_TRANSLATIONS[guide_family][component] = {
        "steps": list[str], "notes": list[str],
        "clean_frequency": str, "replace_frequency": str | None,
    }

mirrors a subset of ``UPKEEP_GUIDE_LIBRARY`` (../upkeep_guides.py). Any family,
component, or field left out falls back to English PER FIELD at overlay time, so
partial edits are safe. This whole module — including ``x10_pro_omni`` — is a
best-effort AI draft translated from the English source of truth and is PENDING
NATIVE REVIEW (no official Czech manual was used). After editing, regenerate the
frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {
    "x10_pro_omni": {
        "filter": {
            "clean_frequency": "Jednou týdně",
            "replace_frequency": "Každé 3-6 měsíce",
            "steps": [
                "Otevřete horní kryt a vyjměte zásobník na prach.",
                "Vyjměte filtr ze zásobníku na prach.",
                "Vyklepejte prach z filtru a vyprázdněte zásobník na prach.",
                "Zásobník na prach a filtr opláchněte pouze vodou.",
                "Před opětovným vložením nechte obě části zcela uschnout na vzduchu.",
            ],
            "notes": [
                "Nepoužívejte kartáč, horkou vodu ani čisticí prostředky.",
                "Filtr vyměňte každé 3-6 měsíce.",
            ],
        },
        "rolling_brush": {
            "clean_frequency": "Jednou měsíčně",
            "replace_frequency": "Každých 6 měsíců",
            "steps": [
                "Odjistěte pojistky krytu kartáče a kryt vyjměte.",
                "Vyjměte válcový kartáč.",
                "Odstřihněte a odstraňte namotané vlasy a nečistoty.",
                "Kartáč a kryt opláchněte a poté je nechte uschnout na vzduchu.",
                "Kartáč znovu nasaďte a kryt zacvakněte zpět na místo.",
            ],
            "notes": [
                "Kryt kartáče by se měl také vyměnit každé 3-6 měsíce nebo při opotřebení.",
            ],
        },
        "side_brush": {
            "clean_frequency": "Jednou měsíčně",
            "replace_frequency": "Každé 3-6 měsíce nebo při opotřebení",
            "steps": [
                "Pomocí šroubováku odejměte boční kartáč.",
                "Odmotejte a odstraňte veškeré vlasy a nečistoty.",
                "Kartáč opláchněte vodou a nechte jej zcela uschnout na vzduchu.",
                "Po uschnutí kartáč znovu nasaďte.",
            ],
            "notes": [],
        },
        "sensor": {
            "clean_frequency": "Jednou měsíčně",
            "replace_frequency": None,
            "steps": [
                "Senzory a kamery otřete měkkým suchým hadříkem.",
                "Při údržbě senzorů otřete také nabíjecí kontakty.",
            ],
            "notes": [
                "Návod neuvádí žádný interval výměny senzorů.",
            ],
        },
        "cleaning_tray": {
            "clean_frequency": "Dle potřeby",
            "replace_frequency": None,
            "steps": [
                "Vyjměte čisticí vaničku z Omni stanice.",
                "Vaničku důkladně opláchněte vodou.",
                "Po vyčištění vaničku vraťte zpět.",
            ],
            "notes": [
                "Nádržku na špinavou vodu je třeba vyprázdnit a vypláchnout, když je plná.",
            ],
        },
        "mopping_cloth": {
            "clean_frequency": "Prát po použití / pravidelně kontrolovat",
            "replace_frequency": "Každé 3-6 měsíce",
            "steps": [
                "Sejměte mopovací hadříky z robota.",
                "Před dalším použitím hadříky vyperte a nechte zcela uschnout.",
                "Hadříky vyměňte, jakmile se opotřebují nebo přestanou účinně čistit.",
            ],
            "notes": [],
        },
        "swivel_wheel": {
            "clean_frequency": "Jednou měsíčně",
            "replace_frequency": None,
            "steps": [
                "Zkontrolujte otočné kolečko, zda na něm nejsou namotané vlasy nebo nečistoty.",
                "Nečistoty opatrně odstraňte a oblast kolečka otřete dočista.",
                "Před dalším úklidem se ujistěte, že se kolečko volně otáčí.",
            ],
            "notes": [
                "Návod uvádí čištění otočného kolečka, ale neuvádí konkrétní interval výměny.",
            ],
        },
    },
    "s1_pro": {
        "filter": {
            "steps": [
                "Vyjměte vysoce výkonný filtr z prostoru zásobníku na prach.",
                "Jemně vyklepejte prach a nečistoty.",
                "Jakmile je filtr čistý a suchý, znovu jej vložte nebo vyměňte.",
            ],
            "notes": [
                "Pokyny pro servis příslušenství v aplikaci jsou primárním oficiálním postupem resetu pro model S1 Pro.",
            ],
        },
        "sensor": {
            "steps": [
                "Otřete senzory robota měkkým suchým hadříkem.",
                "Při údržbě senzorů vyčistěte také nabíjecí kontakty.",
            ],
        },
        "side_brush": {
            "steps": [
                "Zkontrolujte boční kartáč, zda v něm nejsou zachycené vlasy a nečistoty.",
                "Odstraňte nánosy kolem základny a štětin.",
                "Kartáč vyměňte, pokud jsou štětiny ohnuté nebo poškozené.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Sejměte kryt válcového kartáče.",
                "Zkontrolujte kartáč a obě koncové krytky, zda na nich nejsou namotané vlasy nebo nečistoty.",
                "Před opětovným nasazením kartáč důkladně vyčistěte.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Sejměte válcový mop nebo kontaktní plochy mopu a odstraňte zbytky nečistot.",
                "Před dalším použitím nechte vyčištěné části uschnout.",
                "Spotřební díl mopu vyměňte, jakmile je patrné opotřebení nebo klesne výkon.",
            ],
            "notes": [
                "Dokumentace k S1 je zaměřena na válcový mop, nikoli na odnímatelné dvojité hadříky.",
            ],
        },
        "cleaning_tray": {
            "steps": [
                "Vyjměte filtrační vaničku nebo vložku vaničky z prostoru stanice.",
                "Opláchněte zbytky nečistot a nánosy.",
                "Po vyčištění ji vraťte zpět.",
            ],
            "notes": [
                "Podle potřeby vyčistěte také nádržky na čistou/špinavou vodu a filtr špinavé vody.",
            ],
        },
        "swivel_wheel": {
            "steps": [
                "Zkontrolujte otočné kolečko, zda na něm nejsou vlasy a nečistoty.",
                "Odstraňte nánosy a ujistěte se, že se kolečko volně otáčí.",
            ],
        },
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Vyjměte zásobník na prach nebo přihrádku filtru.",
                "Vyjměte filtr a vyklepejte z něj prach.",
                "Umyjte jej pouze tehdy, pokud to pokyny v návodu/aplikaci dovolují, a před opětovným vložením jej nechte zcela uschnout.",
            ],
            "notes": [
                "Průvodce příslušenstvím pro Omni C20 je založen převážně na videích.",
            ],
        },
        "sensor": {
            "steps": [
                "Čistým suchým hadříkem otřete senzory a nabíjecí kontakty na robotovi i na stanici.",
            ],
        },
        "side_brush": {
            "steps": [
                "Zkontrolujte boční kartáč, zda není opotřebený, zamotaný nebo poškozený.",
                "Odstraňte namotané vlasy a nečistoty z kartáče a základny.",
                "Kartáč vyměňte, pokud jsou štětiny ohnuté nebo chybějí.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Zkontrolujte válcový kartáč, zda na něm nejsou namotané vlasy nebo nečistoty.",
                "Namotaný materiál odstřihněte pomocí čisticího nástroje nebo nůžek.",
                "Po vyčištění jej vraťte zpět.",
            ],
            "notes": [
                "Hřeben Pro-Detangle omezuje, ale zcela neodstraňuje nutnost ručního čištění.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Sejměte mopovací hadříky z robota nebo stanice.",
                "Před dalším použitím je vyčistěte a nechte zcela uschnout.",
                "Hadříky vyměňte, jakmile se opotřebují nebo přestanou účinně čistit.",
            ],
        },
        "cleaning_tray": {
            "steps": [
                "Odejměte základnu stanice nebo díl oblasti pro mytí mopu.",
                "Opláchněte a otřete zbytky nečistot z oblasti vaničky.",
                "Po vyčištění vaničku vraťte zpět.",
            ],
            "notes": [
                "Sledujte a udržujte také nádržky na čistou a špinavou vodu.",
            ],
        },
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Vyjměte zásobník na prach a vyndejte filtr.",
                "Jemně vyklepejte filtr, abyste odstranili prach.",
                "Pokud jste jej opláchli, nechte jej před opětovným vložením zcela uschnout.",
            ],
        },
        "sensor": {
            "steps": [
                "Suchým hadříkem otřete senzory pádu, nárazníkové senzory a nabíjecí kontakty.",
            ],
        },
        "side_brush": {
            "steps": [
                "Odejměte boční kartáč.",
                "Odstraňte vlasy a nečistoty z kartáče a jeho základny.",
                "Nasaďte jej zpět nebo vyměňte, pokud je opotřebený.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Stiskněte pojistky krytu hlavního kartáče a kryt sejměte.",
                "Vyjměte hlavní kartáč.",
                "Pomocí čisticího nástroje nebo nůžek odstraňte vlasy a nečistoty.",
                "Kartáč a kryt vraťte zpět.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Sejměte mopovací hadřík z držáku.",
                "Před dalším použitím jej vyperte a usušte.",
                "Vyměňte jej, pokud se opotřebuje nebo přestane být účinný.",
            ],
            "notes": [
                "Platí pouze pro hybridní modely X8 s funkcí vytírání.",
            ],
        },
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Stiskněte uvolňovací tlačítko zásobníku na prach a zásobník vyjměte.",
                "Vyjměte filtr a vyklepejte z něj volné nečistoty.",
                "Pokud to návod k danému modelu dovoluje, opláchněte jej a před opětovným vložením nechte zcela uschnout.",
            ],
        },
        "sensor": {
            "steps": [
                "Suchým hadříkem otřete senzory a nabíjecí kontakty na robotovi a na základně.",
            ],
        },
        "side_brush": {
            "steps": [
                "Stáhněte boční kartáč.",
                "Odstraňte namotané vlasy a nečistoty.",
                "Nasaďte jej zpět nebo vyměňte, pokud je opotřebený.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Sejměte kryt hlavního kartáče.",
                "Vyjměte válcový kartáč.",
                "Odstraňte namotané vlasy a nečistoty z kartáče a ložisek.",
                "Otřete dosucha a kartáč i kryt vraťte zpět.",
            ],
            "notes": [
                "Modely SES navíc používají automatické stříhání vlasů, které snižuje nároky na údržbu.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Sejměte mopovací hadřík nebo utěrku.",
                "Před dalším použitím jej vyčistěte a nechte zcela uschnout.",
                "Hadřík vyměňte, jakmile je opotřebený.",
            ],
            "notes": [
                "Platí pouze pro hybridní varianty.",
            ],
        },
    },
}
