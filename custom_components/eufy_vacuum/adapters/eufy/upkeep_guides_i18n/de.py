"""Upkeep-guide translations — Deutsch (de).

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
pending native review (de especially). After editing, regenerate the
frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {'x10_pro_omni': {'filter': {'clean_frequency': 'Einmal pro Woche',
                             'replace_frequency': 'Alle 3-6 Monate',
                             'steps': ['Öffnen Sie die obere Abdeckung und nehmen Sie den '
                                       'Staubbehälter heraus.',
                                       'Drücken Sie die Freigabetaste, um den Staubbehälter zu '
                                       'öffnen und zu leeren.',
                                       'Entfernen Sie den Filter.',
                                       'Tippen Sie den Filter, um Staub abzuklopfen.',
                                       'Spülen Sie den Staubbehälter und den Filter gründlich mit '
                                       'Wasser aus.',
                                       'Trocknen Sie den Staubbehälter und den Filter vor dem '
                                       'nächsten Gebrauch vollständig an der Luft.',
                                       'Setzen Sie den Filter wieder in den Staubbehälter ein.',
                                       'Schieben Sie den Staubbehälter zurück in das Hauptgerät.'],
                             'notes': ['Verwenden Sie keine Bürste, kein heißes Wasser und keine '
                                       'Reinigungsmittel.',
                                       'Ersetzen Sie den Filter alle 3-6 Monate.']},
                  'rolling_brush': {'clean_frequency': 'Einmal pro Monat',
                                    'replace_frequency': 'Alle 6 Monate',
                                    'steps': ['Ziehen Sie wie abgebildet an den '
                                              'Entriegelungslaschen, um den Bürstenschutz zu '
                                              'entriegeln.',
                                              'Heben Sie die Rollbürste an, um sie herauszunehmen. '
                                              'Reinigen Sie die Rollbürste mit einem '
                                              'Reinigungswerkzeug oder einer Schere.',
                                              'Spülen Sie die Rollbürste und den Bürstenschutz mit '
                                              'fließendem Wasser ab.',
                                              'Lassen Sie die Rollbürste und den Bürstenschutz vor '
                                              'dem nächsten Gebrauch vollständig an der Luft '
                                              'trocknen.',
                                              'Setzen Sie die Rollbürste wieder ein, indem Sie '
                                              'zuerst das hervorstehende Ende einfügen.',
                                              'Drücken Sie nach unten, um den Bürstenschutz '
                                              'einzurasten.'],
                                    'notes': ['Bürstenschutz sollte auch alle 3-6 Monate oder bei '
                                              'Verschleiß ersetzt werden.']},
                  'side_brush': {'clean_frequency': 'Einmal pro Monat',
                                 'replace_frequency': 'Alle 3-6 Monate (oder wenn sichtbar '
                                                      'abgenutzt)',
                                 'steps': ['Entfernen Sie die Seitenbürste mit einem '
                                           'Schraubenzieher.',
                                           'Entfernen Sie vorsichtig alle Haare oder Substanzen, '
                                           'die sich zwischen dem Gerät und der Seitenbürste '
                                           'befinden.',
                                           'Reinigen Sie die Seitenbürste mit Wasser.',
                                           'Lassen Sie die Seitenbürste vor dem nächsten Gebrauch '
                                           'an der Luft trocknen.',
                                           'Installieren Sie die Seitenbürste wieder am Gerät.'],
                                 'notes': ['Fremdkörper wie Haare können sich leicht in der '
                                           'Seitenbürste verfangen, daher ist es am besten, diese '
                                           'regelmäßig zu reinigen.']},
                  'sensor': {'clean_frequency': 'Einmal pro Monat',
                             'replace_frequency': None,
                             'steps': ['Reinigen Sie die Sensoren und Ladekontaktstifte mit einem '
                                       'weichen Tuch.'],
                             'notes': ['Reinigen Sie die Sensoren und Ladekontaktstifte '
                                       'regelmäßig, um eine optimale Leistung zu gewährleisten.']},
                  'cleaning_tray': {'clean_frequency': None,
                                    'replace_frequency': None,
                                    'steps': ['Entfernen Sie die Reinigungsschale aus der '
                                              'Omni-Station.',
                                              'Spülen Sie die Reinigungsschale gründlich mit '
                                              'Wasser aus.',
                                              'Setzen Sie das Tablett zurück in die Omni Station.'],
                                    'notes': ['Schmutzwassertank sollte geleert und gereinigt '
                                              'werden, wenn er voll ist.']},
                  'mopping_cloth': {'clean_frequency': 'Nach Gebrauch waschen / regelmäßig '
                                                       'überprüfen',
                                    'replace_frequency': 'Alle 3-6 Monate',
                                    'steps': ['Entfernen Sie die Wischmopps vom Roboter.',
                                              'Waschen und trocknen Sie die Mopps vollständig vor '
                                              'der Wiederverwendung.',
                                              'Ersetzen Sie die Mopps, wenn sie abgenutzt sind '
                                              'oder nicht mehr wirksam reinigen.'],
                                    'notes': []},
                  'swivel_wheel': {'clean_frequency': 'Einmal pro Monat',
                                   'replace_frequency': None,
                                   'steps': ['Überprüfen Sie das Drehrad auf verwickelte Haare '
                                             'oder Verschmutzung.',
                                             'Entfernen Sie vorsichtig Verschmutzungen und wischen '
                                             'Sie den Bereich des Rads sauber.',
                                             'Bestätigen Sie, dass das Rad frei dreht, bevor Sie '
                                             'den Roboter erneut verwenden.'],
                                   'notes': ['Die Bedienungsanleitung listet die Reinigung des '
                                             'Drehrades auf, gibt jedoch kein dediziertes '
                                             'Austauschintervall an.']}},
 's1_pro': {'filter': {'steps': ['Nehmen Sie den Hochleistungsfilter aus dem Bereich des '
                                 'Staubbehälters heraus.',
                                 'Klopfen Sie Staub und Schmutz vorsichtig ab.',
                                 'Setzen Sie den Filter wieder ein oder ersetzen Sie ihn, sobald '
                                 'er sauber und trocken ist.'],
                       'notes': ['Die Zubehördienste-Anleitung in der App ist der primäre '
                                 'offizielle Reset-Ablauf für den S1 Pro.']},
            'sensor': {'steps': ['Wischen Sie die Sensoren des Roboters mit einem weichen, '
                                 'trockenen Tuch ab.',
                                 'Reinigen Sie bei der Wartung der Sensoren auch die '
                                 'Ladekontakte.']},
            'side_brush': {'steps': ['Überprüfen Sie die Seitenbürste auf verfangene Haare und '
                                     'Schmutz.',
                                     'Entfernen Sie Ablagerungen rund um die Basis und die '
                                     'Borsten.',
                                     'Ersetzen Sie die Bürste, wenn die Borsten verbogen oder '
                                     'beschädigt sind.']},
            'rolling_brush': {'steps': ['Entfernen Sie den Bürstenschutz der Rollbürste.',
                                        'Prüfen Sie die Bürste und beide Endkappen auf verhedderte '
                                        'Haare oder Schmutz.',
                                        'Reinigen Sie die Bürste gründlich, bevor Sie sie wieder '
                                        'einsetzen.']},
            'mopping_cloth': {'steps': ['Entfernen Sie den Rollmopp bzw. die Mopp-Kontaktflächen '
                                        'und entfernen Sie Rückstände.',
                                        'Lassen Sie die gereinigten Teile vor der Wiederverwendung '
                                        'trocknen.',
                                        'Ersetzen Sie das Mopp-Verbrauchsteil, wenn Verschleiß '
                                        'sichtbar wird oder die Leistung nachlässt.'],
                              'notes': ['Die S1-Dokumentation ist auf den Rollmopp ausgerichtet '
                                        'und nicht auf abnehmbare Doppel-Pads.']},
            'cleaning_tray': {'steps': ['Entnehmen Sie die Filterschale bzw. den Schaleneinsatz '
                                        'aus dem Stationsbereich.',
                                        'Spülen Sie Rückstände und Ablagerungen ab.',
                                        'Setzen Sie sie nach der Reinigung wieder ein.'],
                              'notes': ['Reinigen Sie bei Bedarf auch den Frisch- und '
                                        'Schmutzwassertank sowie den Schmutzwasserfilter.']},
            'swivel_wheel': {'steps': ['Überprüfen Sie das Lenkrad auf Haare und Schmutz.',
                                       'Entfernen Sie Ablagerungen und stellen Sie sicher, dass '
                                       'sich das Rad frei dreht.']}},
 'omni_c20': {'filter': {'steps': ['Nehmen Sie den Staubbehälter bzw. das Filterfach heraus.',
                                   'Nehmen Sie den Filter heraus und klopfen Sie Staub ab.',
                                   'Waschen Sie ihn nur, wenn die Anleitung/App dies erlaubt, und '
                                   'lassen Sie ihn vor dem Wiedereinsetzen vollständig trocknen.'],
                         'notes': ['Die Zubehör-Anleitung des Omni C20 ist überwiegend '
                                   'videobasiert.']},
              'sensor': {'steps': ['Wischen Sie die Sensoren und Ladekontakte an Roboter und '
                                   'Station mit einem sauberen, trockenen Tuch ab.']},
              'side_brush': {'steps': ['Überprüfen Sie die Seitenbürste auf Verschleiß, '
                                       'Verhedderungen oder Beschädigungen.',
                                       'Entfernen Sie umwickelte Haare und Schmutz von der Bürste '
                                       'und der Basis.',
                                       'Ersetzen Sie die Bürste, wenn Borsten verbogen sind oder '
                                       'fehlen.']},
              'rolling_brush': {'steps': ['Überprüfen Sie die Rollbürste auf verhedderte Haare '
                                          'oder Schmutz.',
                                          'Schneiden Sie umwickeltes Material mit dem '
                                          'Reinigungswerkzeug oder einer Schere ab.',
                                          'Setzen Sie sie nach der Reinigung wieder ein.'],
                                'notes': ['Der Pro-Detangle-Kamm reduziert die manuelle Reinigung, '
                                          'macht sie aber nicht überflüssig.']},
              'mopping_cloth': {'steps': ['Entfernen Sie die Mopp-Pads vom Roboter oder von der '
                                          'Station.',
                                          'Reinigen und trocknen Sie sie vor der Wiederverwendung '
                                          'vollständig.',
                                          'Ersetzen Sie die Pads, wenn sie abgenutzt sind oder '
                                          'nicht mehr wirksam reinigen.']},
              'cleaning_tray': {'steps': ['Nehmen Sie die Stationsbasis bzw. das Bauteil des '
                                          'Moppwaschbereichs ab.',
                                          'Spülen und wischen Sie Rückstände aus dem '
                                          'Schalenbereich ab.',
                                          'Setzen Sie die Schale nach der Reinigung wieder ein.'],
                                'notes': ['Überwachen und warten Sie auch den Frisch- und '
                                          'Schmutzwassertank.']}},
 'x8_series': {'filter': {'steps': ['Entnehmen Sie den Staubbehälter und nehmen Sie den Filter '
                                    'heraus.',
                                    'Klopfen Sie den Filter vorsichtig ab, um Staub zu entfernen.',
                                    'Falls Sie ihn abgespült haben, lassen Sie ihn vor dem '
                                    'Wiedereinsetzen vollständig trocknen.']},
               'sensor': {'steps': ['Wischen Sie die Absturzsensoren, die Stoßsensoren und die '
                                    'Ladekontakte mit einem trockenen Tuch ab.']},
               'side_brush': {'steps': ['Entfernen Sie die Seitenbürste.',
                                        'Entfernen Sie Haare und Schmutz von der Bürste und ihrer '
                                        'Basis.',
                                        'Bringen Sie sie wieder an oder ersetzen Sie sie bei '
                                        'Abnutzung.']},
               'rolling_brush': {'steps': ['Drücken Sie die Laschen des Hauptbürstenschutzes '
                                           'zusammen und entfernen Sie den Schutz.',
                                           'Heben Sie die Hauptbürste heraus.',
                                           'Entfernen Sie Haare und Schmutz mit dem '
                                           'Reinigungswerkzeug oder einer Schere.',
                                           'Setzen Sie die Bürste und den Schutz wieder ein.']},
               'mopping_cloth': {'steps': ['Entfernen Sie das Wischpad aus der Halterung.',
                                           'Waschen und trocknen Sie es vor der Wiederverwendung.',
                                           'Ersetzen Sie es, wenn es abgenutzt oder unwirksam '
                                           'wird.'],
                                 'notes': ['Gilt nur für Hybrid-/wischfähige X8-Modelle.']}},
 'l60_series': {'filter': {'steps': ['Drücken Sie die Entriegelungstaste des Staubbehälters und '
                                     'entnehmen Sie den Staubbehälter.',
                                     'Nehmen Sie den Filter heraus und klopfen Sie losen Schmutz '
                                     'ab.',
                                     'Sofern die Anleitung Ihres Modells dies erlaubt, spülen Sie '
                                     'ihn ab und lassen Sie ihn vor dem Wiedereinsetzen '
                                     'vollständig trocknen.']},
                'sensor': {'steps': ['Wischen Sie die Sensoren und Ladekontakte am Roboter und an '
                                     'der Basis mit einem trockenen Tuch ab.']},
                'side_brush': {'steps': ['Ziehen Sie die Seitenbürste ab.',
                                         'Entfernen Sie verhedderte Haare und Schmutz.',
                                         'Bringen Sie sie wieder an oder ersetzen Sie sie bei '
                                         'Abnutzung.']},
                'rolling_brush': {'steps': ['Entfernen Sie die Abdeckung der Hauptbürste.',
                                            'Heben Sie die Walzenbürste heraus.',
                                            'Entfernen Sie umwickelte Haare und Schmutz von der '
                                            'Bürste und den Lagern.',
                                            'Wischen Sie sie trocken und setzen Sie die Bürste und '
                                            'den Bürstenschutz wieder ein.'],
                                  'notes': ['SES-Modelle nutzen zusätzlich ein automatisches '
                                            'Haarschneidesystem, um den Wartungsaufwand zu '
                                            'reduzieren.']},
                'mopping_cloth': {'steps': ['Entfernen Sie das Wischpad bzw. das Wischtuch.',
                                            'Reinigen und trocknen Sie es vor der Wiederverwendung '
                                            'vollständig.',
                                            'Ersetzen Sie das Wischtuch bei Abnutzung.'],
                                  'notes': ['Gilt nur für Hybrid-Varianten.']}}}
