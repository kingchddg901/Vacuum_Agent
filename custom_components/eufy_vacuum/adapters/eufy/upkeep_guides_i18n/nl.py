"""Upkeep-guide translations — Nederlands (nl).

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
pending native review (nl especially). After editing, regenerate the
frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {'x10_pro_omni': {'filter': {'clean_frequency': 'Een keer per week',
                             'replace_frequency': 'Elke drie tot zes maanden',
                             'steps': ['Open de bovenste klep en haal de stofbak eruit.',
                                       'Druk op de ontgrendelingsknop om de stofbak te openen en '
                                       'leeg te maken.',
                                       'Verwijder het filter.',
                                       'Tik op het filter om stof te verwijderen.',
                                       'Spoel de stofbak en het filter grondig af met water.',
                                       'Laat de stofbak en filter volledig aan de lucht drogen '
                                       'voordat u deze opnieuw gebruikt.',
                                       'Plaats het filter terug in de stofbak.',
                                       'Duw de stofbak terug in de hoofdeenheid.'],
                             'notes': ['Opvangbak — Reinigingsfrequentie: Eenmaal per week.']},
                  'rolling_brush': {'clean_frequency': 'Eenmaal per maand',
                                    'replace_frequency': 'Elke zes maanden',
                                    'steps': ['Trek aan de ontgrendelingslipjes om de '
                                              'borstelbeschermer te ontgrendelen, zoals getoond.',
                                              'Til de stofzuiger op om de roterende borstel eruit '
                                              'te halen. Reinig de roterende borstel met een '
                                              'reinigingsgereedschap of een schaar.',
                                              'Spoel de rollende borstel en borstelbeschermer af '
                                              'met stromend water.',
                                              'Laat de roterende borstel en borstelbeschermer '
                                              'volledig aan de lucht drogen voordat u deze opnieuw '
                                              'gebruikt.',
                                              'Installeer de roterende borstel opnieuw door eerst '
                                              'het vaste uitstekende uiteinde in te brengen.',
                                              'Druk naar beneden om de borstelbeschermer op zijn '
                                              'plaats te klikken.'],
                                    'notes': ['Borstelbeschermer moet ook elke drie tot zes '
                                              'maanden of wanneer versleten worden vervangen.']},
                  'side_brush': {'clean_frequency': 'Een keer per maand',
                                 'replace_frequency': 'Elke drie tot zes maanden (of wanneer '
                                                      'zichtbaar versleten)',
                                 'steps': ['Verwijder de zijborstel met een schroevendraaier.',
                                           'Wikkel voorzichtig af en trek alle haren of stoffen '
                                           'die tussen de hoofdeenheid en de zijborstel zijn '
                                           'gewikkeld eraf.',
                                           'Reinig de zijborstel met water.',
                                           'Laat de zijborstel aan de lucht drogen voordat u hem '
                                           'opnieuw gebruikt.',
                                           'Installeer de zijborstel opnieuw op de machine.'],
                                 'notes': ['Vreemde voorwerpen, zoals haren, kunnen gemakkelijk in '
                                           'de zijborstel verstrikt raken, dus die kunt u het '
                                           'beste regelmatig reinigen.']},
                  'sensor': {'clean_frequency': 'Een keer per maand',
                             'replace_frequency': None,
                             'steps': ['Maak de sensoren en oplaadcontactpinnen schoon met een '
                                       'zachte doek.'],
                             'notes': ['Voor de beste prestaties moet u de sensoren en '
                                       'contactpennen regelmatig reinigen.']},
                  'cleaning_tray': {'clean_frequency': None,
                                    'replace_frequency': None,
                                    'steps': ['Verwijder de reinigingstray van de Omni Station.',
                                              'Spoel de reinigingstray grondig af met water.',
                                              'Plaats de lade terug in het Omni Station.'],
                                    'notes': ['Vuilwatertank moet leeg worden gemaakt en worden '
                                              'gereinigd wanneer vol.']},
                  'mopping_cloth': {'clean_frequency': 'Na elk gebruik wassen / regelmatig '
                                                       'controleren',
                                    'replace_frequency': 'Elke drie tot zes maanden',
                                    'steps': ['Verwijder de moppeermallen van de robot.',
                                              'Was en droog de mallen volledig voordat u deze '
                                              'opnieuw gebruikt.',
                                              'Vervang de mallen wanneer ze slijten of niet meer '
                                              'effectief reinigen.'],
                                    'notes': []},
                  'swivel_wheel': {'clean_frequency': 'Eenmaal per maand',
                                   'replace_frequency': None,
                                   'steps': ['Controleer het zwenkelwiel op ingewikkeld haar of '
                                             'vuil.',
                                             'Verwijder voorzichtig het vuil en maak het '
                                             'wielgebied schoon.',
                                             'Zorg ervoor dat het wiel vrij kan draaien voordat u '
                                             'het volgende reinigingswerk uitvoert.'],
                                   'notes': ['De handleiding beschrijft het schoonmaken van het '
                                             'zwenkelwiel, maar geeft geen vervangingsinterval '
                                             'aan.']}},
 's1_pro': {'filter': {'steps': ['Haal het hoogwaardige filter uit het stofbakgedeelte.',
                                 'Klop stof en vuil er voorzichtig af.',
                                 'Plaats het filter terug of vervang het zodra het schoon en droog '
                                 'is.'],
                       'notes': ['De accessoire-servicebegeleiding in de app is de belangrijkste '
                                 'officiële resetprocedure voor de S1 Pro.']},
            'sensor': {'steps': ['Veeg de sensoren van de robot schoon met een zachte, droge doek.',
                                 'Reinig ook de laadcontacten terwijl u de sensoren onderhoudt.']},
            'side_brush': {'steps': ['Controleer de zijborstel op vastzittende haren en vuil.',
                                     'Verwijder opgehoopt vuil rond de voet en de borstelharen.',
                                     'Vervang de borstel als de borstelharen verbogen of '
                                     'beschadigd zijn.']},
            'rolling_brush': {'steps': ['Verwijder de borstelbeschermer van de rolborstel.',
                                        'Controleer de borstel en beide eindkapjes op verwikkelde '
                                        'haren of vuil.',
                                        'Reinig de borstel grondig voordat u hem terugplaatst.']},
            'mopping_cloth': {'steps': ['Verwijder de rollende dweil of de dweilcontactvlakken en '
                                        'verwijder alle resten.',
                                        'Laat de gereinigde onderdelen drogen voordat u ze opnieuw '
                                        'gebruikt.',
                                        'Vervang het dweilonderdeel wanneer er zichtbare slijtage '
                                        'optreedt of de prestaties afnemen.'],
                              'notes': ['De S1-documentatie is gericht op de rollende dweil in '
                                        'plaats van op verwijderbare dubbele dweildoeken.']},
            'cleaning_tray': {'steps': ['Verwijder de filterlade of het inzetstuk van de '
                                        'reinigingsbak uit het stationgedeelte.',
                                        'Spoel resten en opgehoopt vuil weg.',
                                        'Plaats de bak na het reinigen terug.'],
                              'notes': ['Reinig indien nodig ook de schoonwater- en vuilwatertank '
                                        'en het vuilwaterfilter.']},
            'swivel_wheel': {'steps': ['Controleer het zwenkwiel op haren en vuil.',
                                       'Verwijder opgehoopt vuil en controleer of het wiel vrij '
                                       'draait.']}},
 'omni_c20': {'filter': {'steps': ['Haal de stofbak of het filtervak eruit.',
                                   'Neem het filter eruit en klop het stof eraf.',
                                   'Was het alleen als de handleiding/app dit toestaat en laat het '
                                   'daarna volledig drogen voordat u het terugplaatst.'],
                         'notes': ['De accessoiregids van de Omni C20 is voornamelijk '
                                   'videogebaseerd.']},
              'sensor': {'steps': ['Veeg met een schone, droge doek de sensoren en laadcontacten '
                                   'op zowel de robot als het station schoon.']},
              'side_brush': {'steps': ['Controleer de zijborstel op slijtage, verwikkelde haren of '
                                       'beschadiging.',
                                       'Verwijder vastgewikkelde haren en vuil van de borstel en '
                                       'de voet.',
                                       'Vervang de borstel als de borstelharen verbogen zijn of '
                                       'ontbreken.']},
              'rolling_brush': {'steps': ['Controleer de rolborstel op verwikkelde haren of vuil.',
                                          'Gebruik het schoonmaakgereedschap of een schaar om '
                                          'vastgewikkeld materiaal weg te knippen.',
                                          'Plaats de borstel na het reinigen terug.'],
                                'notes': ['De Pro-Detangle-kam vermindert het handmatig reinigen, '
                                          'maar maakt het niet overbodig.']},
              'mopping_cloth': {'steps': ['Verwijder de dweildoeken van de robot of het station.',
                                          'Reinig ze en laat ze volledig drogen voordat u ze '
                                          'opnieuw gebruikt.',
                                          'Vervang de dweildoeken wanneer ze versleten zijn of '
                                          'niet meer effectief reinigen.']},
              'cleaning_tray': {'steps': ['Maak de stationbasis of het wasgedeelte voor de dweil '
                                          'los.',
                                          'Spoel en veeg resten uit het bakgedeelte.',
                                          'Plaats de bak na het reinigen terug.'],
                                'notes': ['Houd ook de schoonwater- en vuilwatertank in de gaten '
                                          'en onderhoud ze.']}},
 'x8_series': {'filter': {'steps': ['Haal de stofbak eruit en neem het filter eruit.',
                                    'Tik voorzichtig op het filter om stof te verwijderen.',
                                    'Als u het afspoelt, laat het dan volledig drogen voordat u '
                                    'het terugplaatst.']},
               'sensor': {'steps': ['Veeg de valsensoren, bumpersensoren en laadcontacten schoon '
                                    'met een droge doek.']},
               'side_brush': {'steps': ['Verwijder de zijborstel.',
                                        'Verwijder haren en vuil van de borstel en de voet.',
                                        'Bevestig hem opnieuw of vervang hem bij slijtage.']},
               'rolling_brush': {'steps': ['Knijp de lipjes van de borstelbeschermer samen en '
                                           'verwijder de beschermer.',
                                           'Til de rolborstel eruit.',
                                           'Gebruik het schoonmaakgereedschap of een schaar om '
                                           'haren en vuil te verwijderen.',
                                           'Plaats de borstel en de beschermer terug.']},
               'mopping_cloth': {'steps': ['Haal de dweildoek uit de houder.',
                                           'Was en droog hem voordat u hem opnieuw gebruikt.',
                                           'Vervang hem als hij versleten of niet meer effectief '
                                           'is.'],
                                 'notes': ['Geldt alleen voor hybride/dweilgeschikte '
                                           'X8-modellen.']}},
 'l60_series': {'filter': {'steps': ['Druk op de ontgrendelingsknop van de stofbak en verwijder de '
                                     'stofbak.',
                                     'Verwijder het filter en klop het losse vuil eraf.',
                                     'Als de handleiding van uw specifieke model dit toestaat, '
                                     'spoel het dan af en laat het volledig drogen voordat u het '
                                     'terugplaatst.']},
                'sensor': {'steps': ['Veeg met een droge doek de sensoren en laadcontacten op de '
                                     'robot en het basisstation schoon.']},
                'side_brush': {'steps': ['Trek de zijborstel eraf.',
                                         'Verwijder verwikkelde haren en vuil.',
                                         'Bevestig hem opnieuw of vervang hem bij slijtage.']},
                'rolling_brush': {'steps': ['Verwijder de borstelbeschermer van de rolborstel.',
                                            'Til de rolborstel eruit.',
                                            'Verwijder vastgewikkelde haren en vuil van de borstel '
                                            'en de lagers.',
                                            'Veeg hem droog en plaats de borstel en de beschermer '
                                            'terug.'],
                                  'notes': ['SES-modellen knippen haar ook automatisch af om het '
                                            'onderhoud te verminderen.']},
                'mopping_cloth': {'steps': ['Verwijder de dweildoek.',
                                            'Reinig hem en laat hem volledig drogen voordat u hem '
                                            'opnieuw gebruikt.',
                                            'Vervang de dweildoek bij slijtage.'],
                                  'notes': ['Geldt alleen voor hybride varianten.']}}}
