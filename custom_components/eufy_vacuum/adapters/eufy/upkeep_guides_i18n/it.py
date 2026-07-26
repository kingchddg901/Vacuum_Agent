"""Upkeep-guide translations — Italiano (it).

One of the per-language modules under ``upkeep_guides_i18n/``; ``__init__.py``
assembles them into ``UPKEEP_GUIDE_TRANSLATIONS``. Pure data.

Shape::

    GUIDE_TRANSLATIONS[guide_family][component] = {
        "steps": list[str], "notes": list[str],
        "clean_frequency": str, "replace_frequency": str | None,
    }

mirrors a subset of ``UPKEEP_GUIDE_LIBRARY`` (../upkeep_guides.py). Any family,
component, or field left out falls back to English PER FIELD at overlay time, so
partial edits are safe. Latin-script ``x10_pro_omni`` content is VERBATIM from
Eufy's official localized manuals; other families / scripts are best-effort and
pending native review (it especially). After editing, regenerate the
frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {'x10_pro_omni': {'filter': {'clean_frequency': 'Una volta a settimana',
                             'replace_frequency': 'Ogni 3-6 mesi',
                             'steps': ['Aprire il coperchio superiore e togliere il contenitore '
                                       'della polvere.',
                                       'Premere il pulsante di rilascio per aprire ed svuotare il '
                                       'contenitore della polvere.',
                                       'Rimuovere il filtro.',
                                       'Toccare il filtro per rimuovere la polvere.',
                                       'Sciacquare accuratamente la scatola della polvere e il '
                                       'filtro con acqua.',
                                       "Asciugare all'aria completamente la scatola della polvere "
                                       'e il filtro prima del prossimo utilizzo.',
                                       'Riposizionare il filtro nella scatola della polvere.',
                                       "Inserire il contenitore della polvere all'interno "
                                       "dell'unità principale."],
                             'notes': ['Frequenze dalla tabella ufficiale: Filtro — pulizia una '
                                       'volta a settimana, sostituzione ogni 3-6 mesi.',
                                       'Contenitore per la polvere — pulizia una volta a settimana '
                                       '(nessuna frequenza di sostituzione indicata).']},
                  'rolling_brush': {'clean_frequency': 'Una volta al mese',
                                    'replace_frequency': 'Ogni 6 mesi',
                                    'steps': ['Tirare le linguette di sblocco per sbloccare la '
                                              'protezione della spazzola, come indicato.',
                                              'Sollevare per estrarre la spazzola rotante. Pulisci '
                                              'il rullo spazzolino con un attrezzo per la pulizia '
                                              'o delle forbici.',
                                              'Sciacquare la spazzola rotante e la protezione '
                                              'della spazzola con acqua corrente.',
                                              'Asciugare completamente la spazzola rotante e la '
                                              'protezione della spazzola prima del prossimo '
                                              'utilizzo.',
                                              'Reinstallare la spazzola rotante inserendo prima '
                                              "l'estremità sporgente fissa.",
                                              'Premere verso il basso per far scattare il '
                                              'para-spazzola in posizione.'],
                                    'notes': ['La protezione della spazzola deve essere sostituita '
                                              'anche ogni 3-6 mesi o quando usurata.']},
                  'side_brush': {'clean_frequency': 'Una volta al mese',
                                 'replace_frequency': 'Ogni 3-6 mesi (o quando visibilmente '
                                                      'usurato)',
                                 'steps': ['Rimuovere la spazzola laterale con un cacciavite.',
                                           'Srotolare con attenzione e rimuovere i capelli o le '
                                           "sostanze avvolte tra l'unità principale e la spazzola "
                                           'laterale.',
                                           'Pulire la spazzola laterale con acqua.',
                                           "Asciugare all'aria la spazzola laterale prima del "
                                           'prossimo utilizzo.',
                                           'Reinstallare la spazzola laterale sulla macchina.'],
                                 'notes': ['Le sostanze estranee, come i capelli, possono '
                                           'facilmente aggrovigliarsi nella spazzola laterale, '
                                           'quindi è meglio pulirla regolarmente.']},
                  'sensor': {'clean_frequency': 'Una volta al mese',
                             'replace_frequency': None,
                             'steps': ['Sfregare via la polvere dai sensori e dai contatti di '
                                       'ricarica utilizzando un panno morbido.'],
                             'notes': ['Per mantenere prestazioni ottimali, pulire regolarmente i '
                                       'sensori e i pin di contatto di ricarica.',
                                       'Sezione 7.4 "Pulire i Sensori, le Telecamere e i Pin di '
                                       'Ricarica". Frequenze dalla tabella: Sensori una volta al '
                                       'mese, Pin di ricarica una volta al mese.']},
                  'cleaning_tray': {'clean_frequency': 'Svuotare e pulire quando è pieno '
                                                       "(serbatoio dell'acqua sporca)",
                                    'replace_frequency': None,
                                    'steps': ["Rimuovere il serbatoio dell'acqua sporca dalla "
                                              'stazione Omni.',
                                              "Svuotare il serbatoio dell'acqua sporca.",
                                              "Sciacquare accuratamente il serbatoio dell'acqua "
                                              'sporca con acqua corrente.',
                                              'Rimuovere il vassoio di pulizia dalla stazione '
                                              'Omni.',
                                              'Risciacquare accuratamente il vassoio di pulizia '
                                              'con acqua.',
                                              'Rimettere il vassoio nella Stazione Omni.'],
                                    'notes': ["Il serbatoio dell'acqua sporca deve essere svuotato "
                                              'e sciacquato quando è pieno.']},
                  'mopping_cloth': {'clean_frequency': "Lavare dopo l'uso / ispezionare "
                                                       'regolarmente',
                                    'replace_frequency': 'Ogni 3-6 mesi',
                                    'steps': ['Rimuovere i panni per pulire il pavimento dal '
                                              'robot.',
                                              'Lavare e asciugare completamente i panni prima del '
                                              'riutilizzo.',
                                              'Sostituire i panni quando diventano usurati o non '
                                              'puliscono più efficacemente.'],
                                    'notes': []},
                  'swivel_wheel': {'clean_frequency': 'Una volta al mese',
                                   'replace_frequency': None,
                                   'steps': ['Ispezionare la ruota girevole per capelli o detriti '
                                             'avvolti.',
                                             "Rimuovere i detriti con attenzione e pulire l'area "
                                             'della ruota.',
                                             'Verificare che la ruota giri liberamente prima della '
                                             'prossima esecuzione.'],
                                   'notes': ['Il manuale fornisce istruzioni per la pulizia della '
                                             'ruota girevole ma non specifica un intervallo di '
                                             'sostituzione.']}},
 's1_pro': {'filter': {'steps': ["Rimuovere il filtro ad alte prestazioni dall'area del "
                                 'contenitore della polvere.',
                                 'Picchiettare delicatamente per rimuovere polvere e detriti.',
                                 'Reinstallare o sostituire il filtro una volta pulito e '
                                 'asciutto.'],
                       'notes': ["La guida al servizio degli accessori nell'app è la procedura di "
                                 "reset ufficiale principale per l'S1 Pro."]},
            'sensor': {'steps': ['Pulire i sensori del robot con un panno morbido e asciutto.',
                                 'Pulire anche i contatti di ricarica durante la manutenzione dei '
                                 'sensori.']},
            'side_brush': {'steps': ['Ispezionare la spazzola laterale per capelli e detriti '
                                     'intrappolati.',
                                     'Rimuovere gli accumuli intorno alla base e alle setole.',
                                     'Sostituire la spazzola se le setole sono piegate o '
                                     'danneggiate.']},
            'rolling_brush': {'steps': ['Rimuovere la protezione della spazzola rotante.',
                                        'Controllare la spazzola ed entrambi i cappucci terminali '
                                        'per capelli aggrovigliati o detriti.',
                                        'Pulire accuratamente la spazzola prima di '
                                        'reinstallarla.']},
            'mopping_cloth': {'steps': ['Rimuovere il mop rotante o le superfici di contatto del '
                                        'mop ed eliminare i residui.',
                                        'Lasciare asciugare le parti pulite prima del riutilizzo.',
                                        "Sostituire il materiale di consumo del mop quando l'usura "
                                        'diventa visibile o le prestazioni calano.'],
                              'notes': ["La documentazione dell'S1 è orientata al mop rotante "
                                        'anziché a due panni staccabili.']},
            'cleaning_tray': {'steps': ["Rimuovere il vassoio del filtro o l'inserto del vassoio "
                                        "dall'area della stazione.",
                                        'Sciacquare via residui e accumuli.',
                                        'Reinstallare dopo la pulizia.'],
                              'notes': ["Pulire anche i serbatoi dell'acqua pulita e sporca e il "
                                        "filtro dell'acqua sporca secondo necessità."]},
            'swivel_wheel': {'steps': ['Ispezionare la ruota piroettante per capelli e detriti.',
                                       'Rimuovere gli accumuli e verificare che la ruota giri '
                                       'liberamente.']}},
 'omni_c20': {'filter': {'steps': ['Rimuovere il contenitore della polvere o il vano del filtro.',
                                   'Estrarre il filtro e picchiettare per rimuovere la polvere.',
                                   "Lavare solo se la guida del manuale o dell'app lo consente, "
                                   'poi asciugare completamente prima di reinstallare.'],
                         'notes': ["La guida agli accessori dell'Omni C20 è basata principalmente "
                                   'su video.']},
              'sensor': {'steps': ['Usare un panno pulito e asciutto per pulire i sensori e i '
                                   'contatti di ricarica sia sul robot sia sulla stazione.']},
              'side_brush': {'steps': ['Ispezionare la spazzola laterale per usura, '
                                       'aggrovigliamenti o danni.',
                                       'Rimuovere capelli e detriti avvolti dalla spazzola e dalla '
                                       'base.',
                                       'Sostituire la spazzola se le setole sono piegate o '
                                       'mancanti.']},
              'rolling_brush': {'steps': ['Ispezionare la spazzola rotante per capelli '
                                          'aggrovigliati o detriti.',
                                          'Usare lo strumento di pulizia o delle forbici per '
                                          'tagliare via il materiale avvolto.',
                                          'Reinstallare dopo la pulizia.'],
                                'notes': ['Il pettine Pro-Detangle riduce ma non elimina la '
                                          'pulizia manuale.']},
              'mopping_cloth': {'steps': ['Rimuovere i panni per lavaggio dal robot o dalla '
                                          'stazione.',
                                          'Pulirli e asciugarli completamente prima del '
                                          'riutilizzo.',
                                          'Sostituire i panni quando sono usurati o non puliscono '
                                          'più efficacemente.']},
              'cleaning_tray': {'steps': ['Staccare la base della stazione o il componente '
                                          "dell'area di lavaggio del mop.",
                                          "Sciacquare e rimuovere i residui dall'area del vassoio.",
                                          'Reinstallare il vassoio dopo la pulizia.'],
                                'notes': ['Monitorare e sottoporre a manutenzione anche i serbatoi '
                                          "dell'acqua pulita e sporca."]}},
 'x8_series': {'filter': {'steps': ['Rimuovere il contenitore della polvere ed estrarre il filtro.',
                                    'Picchiettare delicatamente il filtro per rimuovere la '
                                    'polvere.',
                                    'Se sciacquato, lasciarlo asciugare completamente prima di '
                                    'reinstallarlo.']},
               'sensor': {'steps': ['Pulire i sensori anticaduta, i sensori del paraurti e i '
                                    'contatti di ricarica con un panno asciutto.']},
               'side_brush': {'steps': ['Rimuovere la spazzola laterale.',
                                        'Eliminare capelli e detriti dalla spazzola e dalla sua '
                                        'base.',
                                        'Rimontare o sostituire se usurata.']},
               'rolling_brush': {'steps': ['Premere le linguette della protezione della spazzola '
                                           'rotante e rimuovere la protezione.',
                                           'Sollevare ed estrarre la spazzola rotante.',
                                           'Usare lo strumento di pulizia o delle forbici per '
                                           'rimuovere capelli e detriti.',
                                           'Reinstallare la spazzola e la protezione.']},
               'mopping_cloth': {'steps': ['Rimuovere il panno per lavaggio dal supporto.',
                                           'Lavarlo e asciugarlo prima del riutilizzo.',
                                           'Sostituirlo se diventa usurato o inefficace.'],
                                 'notes': ['Si applica solo ai modelli X8 ibridi o con funzione '
                                           'mop.']}},
 'l60_series': {'filter': {'steps': ['Premere il pulsante di rilascio del contenitore della '
                                     'polvere e rimuovere il contenitore della polvere.',
                                     'Rimuovere il filtro e picchiettare per eliminare lo sporco '
                                     'residuo.',
                                     'Se consentito dalla guida specifica del modello, sciacquare '
                                     'e asciugare completamente prima di reinstallare.']},
                'sensor': {'steps': ['Usare un panno asciutto per pulire i sensori e i contatti di '
                                     'ricarica sul robot e sulla base.']},
                'side_brush': {'steps': ['Staccare la spazzola laterale.',
                                         'Rimuovere capelli aggrovigliati e detriti.',
                                         'Rimontare o sostituire se usurata.']},
                'rolling_brush': {'steps': ['Rimuovere la copertura della spazzola rotante.',
                                            'Sollevare ed estrarre la spazzola rotante.',
                                            'Rimuovere capelli e detriti avvolti dalla spazzola e '
                                            'dai cuscinetti.',
                                            'Asciugare con un panno e reinstallare la spazzola e '
                                            'la protezione.'],
                                  'notes': ['I modelli SES utilizzano anche il taglio automatico '
                                            'dei capelli per ridurre la manutenzione.']},
                'mopping_cloth': {'steps': ['Rimuovere il tampone o il panno per lavaggio.',
                                            'Pulirlo e asciugarlo completamente prima del '
                                            'riutilizzo.',
                                            'Sostituire il panno quando è usurato.'],
                                  'notes': ['Si applica solo alle varianti ibride.']}}}
