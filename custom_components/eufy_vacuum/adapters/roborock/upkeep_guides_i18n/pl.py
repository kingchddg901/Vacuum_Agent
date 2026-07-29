"""Upkeep-guide translations — Polski (pl).

Per-language module under roborock/upkeep_guides_i18n/; __init__.py assembles them
into ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS. Pure data.

Best-effort AI DRAFT — pending native review. Steps/notes translated from the
English base library (roborock_upkeep_guides.py); frequencies match our English
base (not any source model's) so the interval reads the same in every language.
Overlaid PER FIELD on the English guide — anything omitted falls back to English.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Co tydzień",
        "replace_frequency": "Co 6-12 miesięcy",
        "steps": [
            "Odwróć robota spodem do góry i naciśnij zatrzask, aby zwolnić pokrywę szczotki głównej.",
            "Wyjmij szczotkę główną, a następnie zdejmij i wyczyść nasadki łożysk na obu końcach.",
            "Za pomocą dołączonego narzędzia czyszczącego przetnij i usuń włosy nawinięte na szczotkę i łożyska.",
            "Załóż z powrotem nasadki łożysk oraz pokrywę w kierunku blokady, a następnie dociśnij pokrywę, aż zatrzask kliknie.",
        ],
        "notes": [
            "Jeśli komora szczotki wygląda na zabrudzoną, przetrzyj ją przed ponownym montażem.",
            "Wymieniaj szczotkę główną co 6-12 miesięcy, aby zapewnić najlepsze sprzątanie.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Co miesiąc",
        "replace_frequency": "Co 3-6 miesięcy",
        "steps": [
            "Odwróć robota spodem do góry i wykręć śrubę mocującą szczotkę boczną.",
            "Zdejmij szczotkę boczną i usuń włosy lub zanieczyszczenia nawinięte na trzpień.",
            "Załóż z powrotem szczotkę boczną i dokręć śrubę.",
        ],
        "notes": [
            "Wymieniaj szczotkę boczną co 3-6 miesięcy lub wcześniej, jeśli jest wygięta bądź postrzępiona.",
        ],
    },
    "filter": {
        "clean_frequency": "Co 2 tygodnie",
        "replace_frequency": "Co 6-12 miesięcy",
        "steps": [
            "Naciśnij zatrzask pojemnika na kurz, wyjmij pojemnik, otwórz jego pokrywę i opróżnij go.",
            "Wyjmij filtr nadający się do mycia i wypłucz go pod czystą wodą — bez detergentu.",
            "Postukaj ramką filtra o twardą powierzchnię, aby strząsnąć nagromadzony kurz, i płucz, aż będzie czysty.",
            "Pozostaw filtr do wyschnięcia na powietrzu przez co najmniej 24 godziny przed ponownym montażem.",
        ],
        "notes": [
            "Nigdy nie używaj do filtra detergentu, gorącej wody, zmywarki ani suszarki do włosów.",
            "Trzymanie drugiego filtra na wymianę pozwala jednemu całkowicie wyschnąć, gdy drugi jest w użyciu.",
        ],
    },
    "sensor": {
        "clean_frequency": "Co miesiąc",
        "replace_frequency": None,
        "steps": [
            "Przetrzyj sześć czujników krawędzi na spodzie miękką, suchą ściereczką.",
            "Przetrzyj czujnik ściany na prawej krawędzi oraz czujnik ładowania.",
            "Przy okazji przetrzyj również styki ładowania na spodzie.",
        ],
        "notes": [
            "Używaj wyłącznie suchej ściereczki — płyny czyszczące mogą uszkodzić osłony czujników.",
        ],
    },
    "dustbin": {
        "clean_frequency": "Co tydzień",
        "replace_frequency": None,
        "steps": [
            "Otwórz górną pokrywę, naciśnij zatrzask pojemnika na kurz i wyjmij pojemnik.",
            "Otwórz pokrywę pojemnika i wysyp zawartość do kosza.",
            "W razie potrzeby wypłucz pojemnik czystą wodą — najpierw wyjmij filtr i nie używaj detergentu.",
        ],
        "notes": [
            "Przed ponownym montażem całkowicie osusz pojemnik, aby wilgotny kurz nie zatkał filtra.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Po każdym użyciu",
        "replace_frequency": "Co 3-6 miesięcy",
        "steps": [
            "Zdejmij nakładkę mopującą z modułu mopującego po każdym mopowaniu.",
            "Wypłucz ją do czysta i pozostaw do wyschnięcia.",
        ],
        "notes": [
            "Zawsze zdejmuj nakładkę do czyszczenia, aby brudna woda nie spłynęła z powrotem do zbiornika i nie zatkała filtra.",
            "Nakładkę wielokrotnego użytku wymieniaj co 3-6 miesięcy; nakładkę jednorazową wymieniaj po każdym użyciu.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Co miesiąc",
        "replace_frequency": None,
        "steps": [
            "Odwróć robota spodem do góry i podważ przednie kółko wielokierunkowe (samonastawne).",
            "Usuń włosy i brud nawinięte na korpus kółka oraz oś.",
            "Wciśnij kółko mocno z powrotem na miejsce.",
        ],
        "notes": [
            "Wspornika kółka nie da się wyjąć — wyjmuje się jedynie sam korpus kółka.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Co tydzień",
        "replace_frequency": None,
        "steps": [
            "Raz w tygodniu sprawdź oba główne koła napędowe pod kątem włosów lub nitek nawiniętych na osie.",
            "Przetnij i usuń wszystko, co się zaplątało, aby koła obracały się swobodnie.",
            "Jeśli zanieczyszczenia są przyklejone, przetrzyj koła lekko wilgotną ściereczką.",
        ],
        "notes": [
            "Swobodnie obracające się koła pomagają robotowi jechać prosto i pokonywać progi.",
        ],
    },
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "Co 1-3 miesiące",
    "steps": [
        "Wyciągnij filtry wody ze zbiornika zgodnie z instrukcją obsługi.",
        "Zamontuj nowe filtry i wsuń je z powrotem na miejsce.",
    ],
    "notes": [
        "Wymieniaj co 1-3 miesiące, w zależności od jakości wody i częstotliwości mopowania.",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "Gdy pełny (mniej więcej co 7 tygodni)",
    "steps": [
        "Otwórz pokrywę komory na kurz w stacji dokującej.",
        "Wyjmij pełny worek na kurz, ciągnąc go prosto do góry — uchwyt zamyka go podczas wyciągania, dzięki czemu kurz pozostaje w środku.",
        "Wsuń nowy worek na kurz, aż osiądzie na miejscu, a następnie zamknij pokrywę.",
    ],
    "notes": [
        "Zawsze zainstaluj worek przed zamknięciem pokrywy — w przeciwnym razie stacja przeprowadzi automatyczne opróżnianie bez worka.",
        "Jeśli stacja przez pewien czas była nieużywana, opróżnij ręcznie pojemnik na kurz robota i sprawdź, czy wlot powietrza jest drożny.",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "W razie potrzeby",
    "replace_frequency": None,
    "steps": [
        "Wyjmij zbiornik czystej wody ze stacji dokującej i otwórz jego górną pokrywę.",
        "Napełnij go chłodną wodą z kranu (płyn czyszczący Roborock dodawaj tylko wtedy, gdy Twoja stacja to obsługuje).",
        "Zamknij pokrywę i umieść zbiornik z powrotem w stacji dokującej.",
    ],
    "notes": [
        "Używaj wyłącznie chłodnej wody — gorąca woda może odkształcić zbiornik.",
        "Przed ponownym montażem zetrzyj wodę z zewnętrznej powierzchni.",
    ],
}
_DIRTY_WATER_TANK = {
    "clean_frequency": "W razie potrzeby",
    "replace_frequency": None,
    "steps": [
        "Otwórz pokrywę zbiornika brudnej wody i wylej brudną wodę.",
        "Dodaj trochę czystej wody, zamknij i zablokuj pokrywę, wstrząśnij, a następnie ponownie wylej wodę, aby wypłukać zbiornik.",
        "Zablokuj pokrywę i umieść zbiornik z powrotem w stacji dokującej.",
    ],
    "notes": [
        "Pokrywa zbiornika brudnej wody nie odłącza się — płucz ją na miejscu.",
        "Używaj wyłącznie chłodnej wody i przed ponownym montażem wytrzyj zewnętrzną powierzchnię do sucha.",
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
