"""Upkeep-guide translations — Polski (pl).

One of the per-language modules under ``upkeep_guides_i18n/``; ``__init__.py``
assembles them into ``UPKEEP_GUIDE_TRANSLATIONS``. Pure data.

Shape::

    GUIDE_TRANSLATIONS[guide_family][component] = {
        "steps": list[str], "notes": list[str],
        "clean_frequency": str, "replace_frequency": str | None,
    }

mirrors a subset of ``UPKEEP_GUIDE_LIBRARY`` (../upkeep_guides.py). Any family,
component, or field left out falls back to English PER FIELD at overlay time, so
partial edits are safe. This module is a best-effort AI draft translated from
the English source of truth and is pending native review; unlike some locales,
its content (including ``x10_pro_omni``) follows the English library rather than
a verbatim official localized manual. After editing, regenerate the frontend
bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {
    'x10_pro_omni': {
        'filter': {
            'clean_frequency': 'Co tydzień',
            'replace_frequency': 'Co 3-6 miesięcy',
            'steps': [
                'Otwórz górną pokrywę i wyjmij pojemnik na kurz.',
                'Wyjmij filtr z pojemnika na kurz.',
                'Wytrzep kurz z filtra i opróżnij pojemnik na kurz.',
                'Wypłucz pojemnik na kurz i filtr wyłącznie wodą.',
                'Przed ponownym montażem pozostaw obie części do całkowitego '
                'wyschnięcia na powietrzu.',
            ],
            'notes': [
                'Nie używaj szczotki, gorącej wody ani detergentu.',
                'Wymieniaj filtr co 3-6 miesięcy.',
            ],
        },
        'rolling_brush': {
            'clean_frequency': 'Co miesiąc',
            'replace_frequency': 'Co 6 miesięcy',
            'steps': [
                'Odblokuj zaczepy osłony szczotki i wyjmij osłonę.',
                'Wyjmij szczotkę główną.',
                'Wytnij i usuń nawinięte włosy oraz zanieczyszczenia.',
                'Wypłucz szczotkę i osłonę, a następnie wysusz je na powietrzu.',
                'Zamontuj ponownie szczotkę i zatrzaśnij osłonę na swoim miejscu.',
            ],
            'notes': [
                'Osłonę szczotki również należy wymieniać co 3-6 miesięcy lub gdy '
                'się zużyje.',
            ],
        },
        'side_brush': {
            'clean_frequency': 'Co miesiąc',
            'replace_frequency': 'Co 3-6 miesięcy lub gdy się zużyje',
            'steps': [
                'Zdejmij szczotkę boczną za pomocą śrubokręta.',
                'Rozwiń i usuń wszelkie włosy lub zanieczyszczenia.',
                'Wypłucz szczotkę wodą i pozostaw ją do całkowitego wyschnięcia '
                'na powietrzu.',
                'Zamontuj ponownie szczotkę po jej wyschnięciu.',
            ],
            'notes': [],
        },
        'sensor': {
            'clean_frequency': 'Co miesiąc',
            'replace_frequency': None,
            'steps': [
                'Przetrzyj czujniki i kamery miękką, suchą ściereczką.',
                'Podczas konserwacji czujników przetrzyj także styki ładowania.',
            ],
            'notes': [
                'W instrukcji nie podano częstotliwości wymiany czujników.',
            ],
        },
        'cleaning_tray': {
            'clean_frequency': 'W razie potrzeby',
            'replace_frequency': None,
            'steps': [
                'Wyjmij tackę czyszczącą ze stacji Omni.',
                'Dokładnie wypłucz tackę wodą.',
                'Po wyczyszczeniu zamontuj tackę ponownie.',
            ],
            'notes': [
                'Zbiornik brudnej wody należy opróżnić i wypłukać, gdy jest pełny.',
            ],
        },
        'mopping_cloth': {
            'clean_frequency': 'Myj po użyciu / regularnie sprawdzaj',
            'replace_frequency': 'Co 3-6 miesięcy',
            'steps': [
                'Zdejmij nakładki mopujące z robota.',
                'Wypierz i całkowicie wysusz nakładki przed ponownym użyciem.',
                'Wymień nakładki, gdy się zużyją lub przestaną skutecznie czyścić.',
            ],
            'notes': [],
        },
        'swivel_wheel': {
            'clean_frequency': 'Co miesiąc',
            'replace_frequency': None,
            'steps': [
                'Sprawdź, czy na kółku obrotowym nie ma nawiniętych włosów lub '
                'zanieczyszczeń.',
                'Ostrożnie usuń zanieczyszczenia i przetrzyj obszar wokół kółka '
                'do czysta.',
                'Przed kolejnym sprzątaniem upewnij się, że kółko obraca się '
                'swobodnie.',
            ],
            'notes': [
                'Instrukcja wymienia czyszczenie kółka obrotowego, ale nie podaje '
                'osobnej częstotliwości wymiany.',
            ],
        },
    },
    's1_pro': {
        'filter': {
            'steps': [
                'Wyjmij filtr wysokowydajny z obszaru pojemnika na kurz.',
                'Delikatnie wytrzep kurz i zanieczyszczenia.',
                'Zamontuj ponownie lub wymień filtr, gdy będzie czysty i suchy.',
            ],
            'notes': [
                'Wskazówki dotyczące serwisowania akcesoriów w aplikacji stanowią '
                'główną oficjalną procedurę resetowania dla modelu S1 Pro.',
            ],
        },
        'sensor': {
            'steps': [
                'Przetrzyj czujniki robota miękką, suchą ściereczką.',
                'Podczas serwisowania czujników wyczyść także styki ładowania.',
            ],
        },
        'side_brush': {
            'steps': [
                'Sprawdź, czy w szczotce bocznej nie ma uwięzionych włosów i '
                'zanieczyszczeń.',
                'Usuń nagromadzone zanieczyszczenia wokół podstawy i włosia.',
                'Wymień szczotkę, jeśli włosie jest wygięte lub uszkodzone.',
            ],
        },
        'rolling_brush': {
            'steps': [
                'Zdejmij osłonę szczotki głównej.',
                'Sprawdź szczotkę i obie nasadki końcowe pod kątem splątanych '
                'włosów lub zanieczyszczeń.',
                'Dokładnie wyczyść szczotkę przed ponownym montażem.',
            ],
        },
        'mopping_cloth': {
            'steps': [
                'Zdejmij mop obrotowy lub powierzchnie kontaktowe mopa i usuń '
                'osad.',
                'Pozostaw wyczyszczone części do wyschnięcia przed ponownym '
                'użyciem.',
                'Wymień element eksploatacyjny mopa, gdy widoczne będzie zużycie '
                'lub spadek skuteczności.',
            ],
            'notes': [
                'Dokumentacja modelu S1 odnosi się do mopa obrotowego, a nie do '
                'odłączanych podwójnych nakładek.',
            ],
        },
        'cleaning_tray': {
            'steps': [
                'Wyjmij tackę filtra lub wkład tacki z obszaru stacji.',
                'Wypłucz osad i nagromadzone zanieczyszczenia.',
                'Po wyczyszczeniu zamontuj ponownie.',
            ],
            'notes': [
                'W razie potrzeby wyczyść także zbiorniki czystej i brudnej wody '
                'oraz filtr brudnej wody.',
            ],
        },
        'swivel_wheel': {
            'steps': [
                'Sprawdź, czy na kółku obrotowym nie ma włosów i zanieczyszczeń.',
                'Usuń nagromadzone zanieczyszczenia i upewnij się, że kółko obraca '
                'się swobodnie.',
            ],
        },
    },
    'omni_c20': {
        'filter': {
            'steps': [
                'Wyjmij pojemnik na kurz lub komorę filtra.',
                'Wyjmij filtr i wytrzep kurz.',
                'Myj tylko wtedy, gdy pozwalają na to wskazówki w '
                'instrukcji/aplikacji, a następnie całkowicie wysusz przed '
                'ponownym montażem.',
            ],
            'notes': [
                'Przewodnik po akcesoriach Omni C20 opiera się głównie na '
                'materiałach wideo.',
            ],
        },
        'sensor': {
            'steps': [
                'Przetrzyj czujniki i styki ładowania zarówno na robocie, jak i '
                'na stacji, czystą, suchą ściereczką.',
            ],
        },
        'side_brush': {
            'steps': [
                'Sprawdź szczotkę boczną pod kątem zużycia, splątań lub '
                'uszkodzeń.',
                'Usuń nawinięte włosy i zanieczyszczenia ze szczotki oraz '
                'podstawy.',
                'Wymień szczotkę, jeśli włosie jest wygięte lub go brakuje.',
            ],
        },
        'rolling_brush': {
            'steps': [
                'Sprawdź szczotkę główną pod kątem splątanych włosów lub '
                'zanieczyszczeń.',
                'Za pomocą narzędzia czyszczącego lub nożyczek wytnij nawinięty '
                'materiał.',
                'Po wyczyszczeniu zamontuj ponownie.',
            ],
            'notes': [
                'Grzebień Pro-Detangle ogranicza, ale nie eliminuje ręcznego '
                'czyszczenia.',
            ],
        },
        'mopping_cloth': {
            'steps': [
                'Zdejmij nakładki mopujące z robota lub stacji.',
                'Wyczyść je i całkowicie wysusz przed ponownym użyciem.',
                'Wymień nakładki, gdy się zużyją lub przestaną skutecznie '
                'czyścić.',
            ],
        },
        'cleaning_tray': {
            'steps': [
                'Odłącz podstawę stacji lub element obszaru mycia mopa.',
                'Wypłucz i wytrzyj osad z obszaru tacki.',
                'Po wyczyszczeniu zamontuj tackę ponownie.',
            ],
            'notes': [
                'Monitoruj i serwisuj także zbiorniki czystej i brudnej wody.',
            ],
        },
    },
    'x8_series': {
        'filter': {
            'steps': [
                'Wyjmij pojemnik na kurz i wyjmij filtr.',
                'Delikatnie wytrzep filtr, aby usunąć kurz.',
                'Jeśli został wypłukany, pozostaw go do całkowitego wyschnięcia '
                'przed ponownym montażem.',
            ],
        },
        'sensor': {
            'steps': [
                'Przetrzyj czujniki upadku, czujniki zderzaka i styki ładowania '
                'suchą ściereczką.',
            ],
        },
        'side_brush': {
            'steps': [
                'Zdejmij szczotkę boczną.',
                'Usuń włosy i zanieczyszczenia ze szczotki i jej podstawy.',
                'Zamontuj ponownie lub wymień, jeśli jest zużyta.',
            ],
        },
        'rolling_brush': {
            'steps': [
                'Ściśnij zaczepy osłony szczotki głównej i zdejmij osłonę.',
                'Wyjmij szczotkę główną.',
                'Za pomocą narzędzia czyszczącego lub nożyczek usuń włosy i '
                'zanieczyszczenia.',
                'Zamontuj ponownie szczotkę i osłonę.',
            ],
        },
        'mopping_cloth': {
            'steps': [
                'Zdejmij nakładkę mopującą z uchwytu.',
                'Wypierz ją i wysusz przed ponownym użyciem.',
                'Wymień, jeśli się zużyje lub stanie się nieskuteczna.',
            ],
            'notes': [
                'Dotyczy tylko modeli X8 z funkcją hybrydową/mopującą.',
            ],
        },
    },
    'l60_series': {
        'filter': {
            'steps': [
                'Naciśnij przycisk zwalniający pojemnik na kurz i wyjmij '
                'pojemnik na kurz.',
                'Wyjmij filtr i wytrzep luźny brud.',
                'Jeśli pozwala na to przewodnik danego modelu, wypłucz i '
                'całkowicie wysusz przed ponownym montażem.',
            ],
        },
        'sensor': {
            'steps': [
                'Przetrzyj czujniki i styki ładowania na robocie i w stacji '
                'bazowej suchą ściereczką.',
            ],
        },
        'side_brush': {
            'steps': [
                'Ściągnij szczotkę boczną.',
                'Usuń splątane włosy i zanieczyszczenia.',
                'Zamontuj ponownie lub wymień, jeśli jest zużyta.',
            ],
        },
        'rolling_brush': {
            'steps': [
                'Zdejmij pokrywę szczotki głównej.',
                'Wyjmij szczotkę główną.',
                'Wyczyść nawinięte włosy i zanieczyszczenia ze szczotki oraz '
                'łożysk.',
                'Wytrzyj do sucha i zamontuj ponownie szczotkę oraz osłonę.',
            ],
            'notes': [
                'Modele SES korzystają dodatkowo z automatycznego przycinania '
                'włosów, co ogranicza konserwację.',
            ],
        },
        'mopping_cloth': {
            'steps': [
                'Zdejmij nakładkę mopującą lub ściereczkę.',
                'Wyczyść ją i całkowicie wysusz przed ponownym użyciem.',
                'Wymień ściereczkę, gdy się zużyje.',
            ],
            'notes': [
                'Dotyczy tylko wariantów hybrydowych.',
            ],
        },
    },
}
