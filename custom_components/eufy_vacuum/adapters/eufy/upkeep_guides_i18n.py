"""
Localized upkeep guides — Eufy manual translations (+ our own for gaps the manual omits).

UPKEEP_GUIDE_TRANSLATIONS[lang][guide_family][component] mirrors a subset of
UPKEEP_GUIDE_LIBRARY (upkeep_guides.py) with translated steps/notes/frequencies.
filter/rolling_brush/side_brush/sensor/cleaning_tray are VERBATIM from Eufy's
official localized X10 Pro Omni (T2351) manuals. mopping_cloth, swivel_wheel,
and the rolling_brush/cleaning_tray notes are translated BY US (the manual is
thin on those) — best-effort, pending native review; ru is AI-translated
throughout (no official RU manual exists). The maintenance manager overlays
these on the English base PER FIELD, so any component/field still absent falls
back to English.

Selected by the HA instance language (hass.config.language). Pure data.
"""

UPKEEP_GUIDE_TRANSLATIONS = {   'de': {   'x10_pro_omni': {   'filter': {   'clean_frequency': 'Einmal pro Woche',
                                                'replace_frequency': 'Alle 3-6 Monate',
                                                'steps': [   'Öffnen Sie die obere Abdeckung und nehmen Sie '
                                                             'den Staubbehälter heraus.',
                                                             'Drücken Sie die Freigabetaste, um den '
                                                             'Staubbehälter zu öffnen und zu leeren.',
                                                             'Entfernen Sie den Filter.',
                                                             'Tippen Sie den Filter, um Staub abzuklopfen.',
                                                             'Spülen Sie den Staubbehälter und den Filter '
                                                             'gründlich mit Wasser aus.',
                                                             'Trocknen Sie den Staubbehälter und den Filter '
                                                             'vor dem nächsten Gebrauch vollständig an der '
                                                             'Luft.',
                                                             'Setzen Sie den Filter wieder in den '
                                                             'Staubbehälter ein.',
                                                             'Schieben Sie den Staubbehälter zurück in das '
                                                             'Hauptgerät.'],
                                                'notes': ['Verwenden Sie keine Bürste, kein heißes Wasser und keine Reinigungsmittel.', 'Ersetzen Sie den Filter alle 3-6 Monate.']},
                                  'rolling_brush': {   'clean_frequency': 'Einmal pro Monat',
                                                       'replace_frequency': 'Alle 6 Monate',
                                                       'steps': [   'Ziehen Sie wie abgebildet an den '
                                                                    'Entriegelungslaschen, um den '
                                                                    'Bürstenschutz zu entriegeln.',
                                                                    'Heben Sie die Rollbürste an, um sie '
                                                                    'herauszunehmen. Reinigen Sie die '
                                                                    'Rollbürste mit einem Reinigungswerkzeug '
                                                                    'oder einer Schere.',
                                                                    'Spülen Sie die Rollbürste und den '
                                                                    'Bürstenschutz mit fließendem Wasser ab.',
                                                                    'Lassen Sie die Rollbürste und den '
                                                                    'Bürstenschutz vor dem nächsten Gebrauch '
                                                                    'vollständig an der Luft trocknen.',
                                                                    'Setzen Sie die Rollbürste wieder ein, '
                                                                    'indem Sie zuerst das hervorstehende Ende '
                                                                    'einfügen.',
                                                                    'Drücken Sie nach unten, um den '
                                                                    'Bürstenschutz einzurasten.'],
                                                       'notes': [   'Bürstenschutz sollte auch alle 3-6 Monate '
                                                                    'oder bei Verschleiß ersetzt werden.']},
                                  'side_brush': {   'clean_frequency': 'Einmal pro Monat',
                                                    'replace_frequency': 'Alle 3-6 Monate (oder wenn sichtbar '
                                                                         'abgenutzt)',
                                                    'steps': [   'Entfernen Sie die Seitenbürste mit einem '
                                                                 'Schraubenzieher.',
                                                                 'Entfernen Sie vorsichtig alle Haare oder '
                                                                 'Substanzen, die sich zwischen dem Gerät und '
                                                                 'der Seitenbürste befinden.',
                                                                 'Reinigen Sie die Seitenbürste mit Wasser.',
                                                                 'Lassen Sie die Seitenbürste vor dem nächsten '
                                                                 'Gebrauch an der Luft trocknen.',
                                                                 'Installieren Sie die Seitenbürste wieder am '
                                                                 'Gerät.'],
                                                    'notes': [   'Fremdkörper wie Haare können sich leicht in '
                                                                 'der Seitenbürste verfangen, daher ist es am '
                                                                 'besten, diese regelmäßig zu reinigen.']},
                                  'sensor': {   'clean_frequency': 'Einmal pro Monat',
                                                'replace_frequency': None,
                                                'steps': [   'Reinigen Sie die Sensoren und Ladekontaktstifte '
                                                             'mit einem weichen Tuch.'],
                                                'notes': [   'Reinigen Sie die Sensoren und Ladekontaktstifte '
                                                             'regelmäßig, um eine optimale Leistung zu '
                                                             'gewährleisten.']},
                                  'cleaning_tray': {   'clean_frequency': None,
                                                       'replace_frequency': None,
                                                       'steps': [   'Entfernen Sie die Reinigungsschale aus '
                                                                    'der Omni-Station.',
                                                                    'Spülen Sie die Reinigungsschale gründlich '
                                                                    'mit Wasser aus.',
                                                                    'Setzen Sie das Tablett zurück in die Omni '
                                                                    'Station.'],
                                                       'notes': [   'Schmutzwassertank sollte geleert und '
                                                                    'gereinigt werden, wenn er voll ist.']},
                                  'mopping_cloth': {   'clean_frequency': 'Nach Gebrauch waschen / regelmäßig '
                                                                          'überprüfen',
                                                       'replace_frequency': 'Alle 3-6 Monate',
                                                       'steps': [   'Entfernen Sie die Wischmopps vom Roboter.',
                                                                    'Waschen und trocknen Sie die Mopps '
                                                                    'vollständig vor der Wiederverwendung.',
                                                                    'Ersetzen Sie die Mopps, wenn sie '
                                                                    'abgenutzt sind oder nicht mehr wirksam '
                                                                    'reinigen.'],
                                                       'notes': []},
                                  'swivel_wheel': {   'clean_frequency': 'Einmal pro Monat',
                                                      'replace_frequency': None,
                                                      'steps': [   'Überprüfen Sie das Drehrad auf verwickelte '
                                                                   'Haare oder Verschmutzung.',
                                                                   'Entfernen Sie vorsichtig Verschmutzungen '
                                                                   'und wischen Sie den Bereich des Rads '
                                                                   'sauber.',
                                                                   'Bestätigen Sie, dass das Rad frei dreht, '
                                                                   'bevor Sie den Roboter erneut verwenden.'],
                                                      'notes': [   'Die Bedienungsanleitung listet die '
                                                                   'Reinigung des Drehrades auf, gibt jedoch '
                                                                   'kein dediziertes Austauschintervall '
                                                                   'an.']}}},
    'es': {   'x10_pro_omni': {   'filter': {   'clean_frequency': 'Una vez a la semana',
                                                'replace_frequency': 'Cada 3-6 meses',
                                                'steps': [   'Abra la tapa superior y saque el depósito de '
                                                             'polvo.',
                                                             'Presione el botón de liberación para abrir y '
                                                             'vaciar el depósito de polvo.',
                                                             'Retire el filtro.',
                                                             'Toque el filtro para quitar el polvo.',
                                                             'Enjuague completamente la caja de polvo y el '
                                                             'filtro con agua.',
                                                             'Secar al aire la caja de polvo y el filtro '
                                                             'completamente antes de su próximo uso.',
                                                             'Coloque el filtro de vuelta en la caja de polvo.',
                                                             'Empuje la caja de polvo de vuelta dentro de la '
                                                             'unidad principal.'],
                                                'notes': [   'No utilice cepillos, agua caliente ni '
                                                             'detergentes para limpiar el filtro.',
                                                             'No utilice el filtro si no está completamente '
                                                             'seco, de lo contrario puede afectar el '
                                                             'rendimiento de limpieza.']},
                                  'rolling_brush': {   'clean_frequency': 'Una vez al mes',
                                                       'replace_frequency': 'Cada 6 meses',
                                                       'steps': [   'Tire de las pestañas de liberación para '
                                                                    'desbloquear la protección del cepillo, '
                                                                    'como se muestra.',
                                                                    'Levante para sacar el cepillo giratorio. '
                                                                    'Limpie el cepillo giratorio con una '
                                                                    'herramienta de limpieza o tijeras.',
                                                                    'Enjuague el cepillo giratorio y la '
                                                                    'protección del cepillo con agua '
                                                                    'corriente.',
                                                                    'Secar al aire el cepillo giratorio y la '
                                                                    'protección del cepillo completamente '
                                                                    'antes de usar de nuevo.',
                                                                    'Vuelva a instalar el cepillo giratorio '
                                                                    'insertando primero el extremo '
                                                                    'sobresaliente fijo.',
                                                                    'Presione hacia abajo para encajar la '
                                                                    'protección del cepillo en su lugar.'],
                                                       'notes': [   'La protección del cepillo también debe '
                                                                    'reemplazarse cada 3-6 meses o cuando esté '
                                                                    'desgastada.']},
                                  'side_brush': {   'clean_frequency': 'Una vez al mes',
                                                    'replace_frequency': 'Cada 3-6 meses (o cuando esté '
                                                                         'visiblemente desgastado)',
                                                    'steps': [   'Retire el cepillo lateral con un '
                                                                 'destornillador.',
                                                                 'Con cuidado desenrolle y retire cualquier '
                                                                 'cabello o sustancia que esté envuelta entre '
                                                                 'la unidad principal y el cepillo lateral.',
                                                                 'Limpie el cepillo lateral con agua.',
                                                                 'Deje secar al aire el cepillo lateral antes '
                                                                 'de usarlo de nuevo.',
                                                                 'Reinstale el cepillo lateral en la máquina.'],
                                                    'notes': [   'Los materiales extraños, como el cabello, '
                                                                 'pueden enredarse fácilmente en el cepillo '
                                                                 'lateral, por lo que es mejor limpiarlo con '
                                                                 'regularidad.']},
                                  'sensor': {   'clean_frequency': 'Una vez al mes',
                                                'replace_frequency': None,
                                                'steps': [   'Quite el polvo de los sensores y los pines de '
                                                             'contacto de carga utilizando un paño suave.'],
                                                'notes': [   'Para garantizar el funcionamiento más óptimo, '
                                                             'limpie los sensores y las clavijas de contacto '
                                                             'con frecuencia.']},
                                  'cleaning_tray': {   'clean_frequency': None,
                                                       'replace_frequency': None,
                                                       'steps': [   'Retire la bandeja de limpieza de la '
                                                                    'Estación Omni.',
                                                                    'Enjuague completamente la bandeja de '
                                                                    'limpieza con agua.',
                                                                    'Coloque la bandeja de nuevo en la '
                                                                    'Estación Omni.'],
                                                       'notes': [   'El tanque de agua sucia debe vaciarse y '
                                                                    'enjuagarse cuando esté lleno.']},
                                  'mopping_cloth': {   'clean_frequency': 'lavar después del uso / '
                                                                          'inspeccionar regularmente',
                                                       'replace_frequency': 'Cada 3-6 meses',
                                                       'steps': [   'Retire los pads de fregado del robot.',
                                                                    'Lave y seque completamente los pads antes '
                                                                    'de reutilizarlos.',
                                                                    'Reemplace los pads cuando estén '
                                                                    'desgastados o ya no limpien eficazmente.'],
                                                       'notes': []},
                                  'swivel_wheel': {   'clean_frequency': 'Una vez al mes',
                                                      'replace_frequency': None,
                                                      'steps': [   'Inspeccione la rueda giratoria para '
                                                                   'detectar cabello o residuos enroscados.',
                                                                   'Retire cuidadosamente los residuos y '
                                                                   'limpie el área de la rueda.',
                                                                   'Confirme que la rueda gira libremente '
                                                                   'antes del siguiente uso.'],
                                                      'notes': [   'El manual lista la limpieza de la rueda '
                                                                   'giratoria pero no proporciona un intervalo '
                                                                   'de reemplazo dedicado.']}}},
    'fr': {   'x10_pro_omni': {   'filter': {   'clean_frequency': 'Une fois par semaine',
                                                'replace_frequency': 'Tous les 3-6 mois',
                                                'steps': [   'Ouvrez le couvercle supérieur et sortez le bac à '
                                                             'poussière.',
                                                             'Appuyez sur le bouton de déverrouillage pour '
                                                             'ouvrir et vider le bac à poussière.',
                                                             'Retirez le filtre.',
                                                             'Appuyez sur le filtre pour enlever la poussière.',
                                                             'Rincez soigneusement le bac à poussière et le '
                                                             "filtre avec de l'eau.",
                                                             "Séchez à l'air le bac à poussière et le filtre "
                                                             'complètement avant la prochaine utilisation.',
                                                             'Replacez le filtre dans le bac à poussière.',
                                                             "Poussez le bac à poussière vers l'arrière dans "
                                                             "l'unité principale."],
                                                'notes': [   "Avant le nettoyage et l'entretien, éteignez "
                                                             "l'appareil et débranchez l'adaptateur "
                                                             "d'alimentation. Tout autre entretien doit être "
                                                             'effectué par un représentant de service '
                                                             'autorisé. Pour des performances optimales, '
                                                             'suivez les instructions ci-dessous pour nettoyer '
                                                             'et entretenir régulièrement. La fréquence de '
                                                             'nettoyage et de remplacement dépendra de vos '
                                                             "habitudes d'utilisation."]},
                                  'rolling_brush': {   'clean_frequency': 'Une fois par mois',
                                                       'replace_frequency': 'Tous les 6 mois',
                                                       'steps': [   'Tirez sur les languettes de '
                                                                    'déverrouillage pour déverrouiller le '
                                                                    'protège-brosse comme indiqué.',
                                                                    'Soulevez pour retirer la brosse roulante. '
                                                                    'Nettoyez la brosse roulante avec un outil '
                                                                    'de nettoyage ou des ciseaux.',
                                                                    'Rincez la brosse roulante et le '
                                                                    "protège-brosse avec de l'eau courante.",
                                                                    "Séchez à l'air la brosse roulante et le "
                                                                    'protège-brosse complètement avant la '
                                                                    'prochaine utilisation.',
                                                                    'Réinstallez la brosse roulant en insérant '
                                                                    "d'abord l'extrémité saillante fixe.",
                                                                    'Appuyez vers le bas pour enclencher le '
                                                                    'protège-brosse en place.'],
                                                       'notes': [   'Le protège-brosse doit également être '
                                                                    'remplacé tous les 3-6 mois ou en cas '
                                                                    "d'usure."]},
                                  'side_brush': {   'clean_frequency': 'Une fois par mois',
                                                    'replace_frequency': 'Tous les 3-6 mois (ou lorsque '
                                                                         "l'usure est visible)",
                                                    'steps': [   'Retirez la brosse latérale avec un '
                                                                 'tournevis.',
                                                                 'Déroulez soigneusement et retirez les '
                                                                 'cheveux ou les substances qui sont enroulés '
                                                                 "entre l'unité principale et la brosse "
                                                                 'latérale.',
                                                                 "Nettoyez la brosse latérale avec de l'eau.",
                                                                 "Séchez à l'air la brosse latérale avant la "
                                                                 'prochaine utilisation.',
                                                                 'Réinstallez la brosse latérale sur la '
                                                                 'machine.'],
                                                    'notes': [   'Les substances étrangères, telles que les '
                                                                 "cheveux, peuvent facilement s'emmêler dans "
                                                                 'la brosse latérale. Il est donc préférable '
                                                                 'de la nettoyer régulièrement.']},
                                  'sensor': {   'clean_frequency': 'Une fois par mois',
                                                'replace_frequency': None,
                                                'steps': [   'Pour maintenir les meilleures performances, '
                                                             'nettoyez régulièrement les capteurs et les '
                                                             'broches de contact.',
                                                             'Dépoussiérez les capteurs et les broches de '
                                                             "contact de recharge à l'aide d'un chiffon doux."],
                                                'notes': []},
                                  'cleaning_tray': {   'clean_frequency': None,
                                                       'replace_frequency': None,
                                                       'steps': [   'Retirez le plateau de nettoyage de la '
                                                                    'station Omni.',
                                                                    'Rincez soigneusement le plateau de '
                                                                    "nettoyage avec de l'eau.",
                                                                    'Replacez le plateau dans la Station '
                                                                    'Omni.'],
                                                       'notes': [   "Le réservoir d'eau sale doit être vidé et "
                                                                    'rincé quand il est plein.']},
                                  'mopping_cloth': {   'clean_frequency': 'Lavez après utilisation / inspectez '
                                                                          'régulièrement',
                                                       'replace_frequency': 'Tous les 3-6 mois',
                                                       'steps': [   'Retirez les tampons de lavage du robot.',
                                                                    'Lavez et séchez complètement les tampons '
                                                                    'avant réutilisation.',
                                                                    'Remplacez les tampons quand ils '
                                                                    'deviennent usés ou ne nettoient plus '
                                                                    'efficacement.'],
                                                       'notes': []},
                                  'swivel_wheel': {   'clean_frequency': 'Une fois par mois',
                                                      'replace_frequency': None,
                                                      'steps': [   'Inspectez la roue pivotante pour vérifier '
                                                                   'la présence de cheveux ou débris.',
                                                                   'Retirez les débris avec soin et nettoyez '
                                                                   'la zone de la roue.',
                                                                   'Confirmez que la roue tourne librement '
                                                                   'avant le prochain passage.'],
                                                      'notes': [   'Le manuel indique le nettoyage de la roue '
                                                                   "pivotante mais ne précise pas d'intervalle "
                                                                   'de remplacement.']}}},
    'nl': {   'x10_pro_omni': {   'filter': {   'clean_frequency': 'Een keer per week',
                                                'replace_frequency': 'Elke drie tot zes maanden',
                                                'steps': [   'Open de bovenste klep en haal de stofbak eruit.',
                                                             'Druk op de ontgrendelingsknop om de stofbak te '
                                                             'openen en leeg te maken.',
                                                             'Verwijder het filter.',
                                                             'Tik op het filter om stof te verwijderen.',
                                                             'Spoel de stofbak en het filter grondig af met '
                                                             'water.',
                                                             'Laat de stofbak en filter volledig aan de lucht '
                                                             'drogen voordat u deze opnieuw gebruikt.',
                                                             'Plaats het filter terug in de stofbak.',
                                                             'Duw de stofbak terug in de hoofdeenheid.'],
                                                'notes': [   'Opvangbak — Reinigingsfrequentie: Eenmaal per '
                                                             'week.']},
                                  'rolling_brush': {   'clean_frequency': 'Eenmaal per maand',
                                                       'replace_frequency': 'Elke zes maanden',
                                                       'steps': [   'Trek aan de ontgrendelingslipjes om de '
                                                                    'borstelbeschermer te ontgrendelen, zoals '
                                                                    'getoond.',
                                                                    'Til de stofzuiger op om de roterende '
                                                                    'borstel eruit te halen. Reinig de '
                                                                    'roterende borstel met een '
                                                                    'reinigingsgereedschap of een schaar.',
                                                                    'Spoel de rollende borstel en '
                                                                    'borstelbeschermer af met stromend water.',
                                                                    'Laat de roterende borstel en '
                                                                    'borstelbeschermer volledig aan de lucht '
                                                                    'drogen voordat u deze opnieuw gebruikt.',
                                                                    'Installeer de roterende borstel opnieuw '
                                                                    'door eerst het vaste uitstekende uiteinde '
                                                                    'in te brengen.',
                                                                    'Druk naar beneden om de borstelbeschermer '
                                                                    'op zijn plaats te klikken.'],
                                                       'notes': [   'Borstelbeschermer moet ook elke drie tot '
                                                                    'zes maanden of wanneer versleten worden '
                                                                    'vervangen.']},
                                  'side_brush': {   'clean_frequency': 'Een keer per maand',
                                                    'replace_frequency': 'Elke drie tot zes maanden (of '
                                                                         'wanneer zichtbaar versleten)',
                                                    'steps': [   'Verwijder de zijborstel met een '
                                                                 'schroevendraaier.',
                                                                 'Wikkel voorzichtig af en trek alle haren of '
                                                                 'stoffen die tussen de hoofdeenheid en de '
                                                                 'zijborstel zijn gewikkeld eraf.',
                                                                 'Reinig de zijborstel met water.',
                                                                 'Laat de zijborstel aan de lucht drogen '
                                                                 'voordat u hem opnieuw gebruikt.',
                                                                 'Installeer de zijborstel opnieuw op de '
                                                                 'machine.'],
                                                    'notes': [   'Vreemde voorwerpen, zoals haren, kunnen '
                                                                 'gemakkelijk in de zijborstel verstrikt '
                                                                 'raken, dus die kunt u het beste regelmatig '
                                                                 'reinigen.']},
                                  'sensor': {   'clean_frequency': 'Een keer per maand',
                                                'replace_frequency': None,
                                                'steps': [   'Maak de sensoren en oplaadcontactpinnen schoon '
                                                             'met een zachte doek.'],
                                                'notes': [   'Voor de beste prestaties moet u de sensoren en '
                                                             'contactpennen regelmatig reinigen.']},
                                  'cleaning_tray': {   'clean_frequency': None,
                                                       'replace_frequency': None,
                                                       'steps': [   'Verwijder de reinigingstray van de Omni '
                                                                    'Station.',
                                                                    'Spoel de reinigingstray grondig af met '
                                                                    'water.',
                                                                    'Plaats de lade terug in het Omni '
                                                                    'Station.'],
                                                       'notes': [   'Vuilwatertank moet leeg worden gemaakt en '
                                                                    'worden gereinigd wanneer vol.']},
                                  'mopping_cloth': {   'clean_frequency': 'Na elk gebruik wassen / regelmatig '
                                                                          'controleren',
                                                       'replace_frequency': 'Elke drie tot zes maanden',
                                                       'steps': [   'Verwijder de moppeermallen van de robot.',
                                                                    'Was en droog de mallen volledig voordat u '
                                                                    'deze opnieuw gebruikt.',
                                                                    'Vervang de mallen wanneer ze slijten of '
                                                                    'niet meer effectief reinigen.'],
                                                       'notes': []},
                                  'swivel_wheel': {   'clean_frequency': 'Eenmaal per maand',
                                                      'replace_frequency': None,
                                                      'steps': [   'Controleer het zwenkelwiel op ingewikkeld '
                                                                   'haar of vuil.',
                                                                   'Verwijder voorzichtig het vuil en maak het '
                                                                   'wielgebied schoon.',
                                                                   'Zorg ervoor dat het wiel vrij kan draaien '
                                                                   'voordat u het volgende reinigingswerk '
                                                                   'uitvoert.'],
                                                      'notes': [   'De handleiding beschrijft het schoonmaken '
                                                                   'van het zwenkelwiel, maar geeft geen '
                                                                   'vervangingsinterval aan.']}}},
    'it': {   'x10_pro_omni': {   'filter': {   'clean_frequency': 'Una volta a settimana',
                                                'replace_frequency': 'Ogni 3-6 mesi',
                                                'steps': [   'Aprire il coperchio superiore e togliere il '
                                                             'contenitore della polvere.',
                                                             'Premere il pulsante di rilascio per aprire ed '
                                                             'svuotare il contenitore della polvere.',
                                                             'Rimuovere il filtro.',
                                                             'Toccare il filtro per rimuovere la polvere.',
                                                             'Sciacquare accuratamente la scatola della '
                                                             'polvere e il filtro con acqua.',
                                                             "Asciugare all'aria completamente la scatola "
                                                             'della polvere e il filtro prima del prossimo '
                                                             'utilizzo.',
                                                             'Riposizionare il filtro nella scatola della '
                                                             'polvere.',
                                                             'Inserire il contenitore della polvere '
                                                             "all'interno dell'unità principale."],
                                                'notes': [   'Frequenze dalla tabella ufficiale: Filtro — '
                                                             'pulizia una volta a settimana, sostituzione ogni '
                                                             '3-6 mesi.',
                                                             'Contenitore per la polvere — pulizia una volta a '
                                                             'settimana (nessuna frequenza di sostituzione '
                                                             'indicata).']},
                                  'rolling_brush': {   'clean_frequency': 'Una volta al mese',
                                                       'replace_frequency': 'Ogni 6 mesi',
                                                       'steps': [   'Tirare le linguette di sblocco per '
                                                                    'sbloccare la protezione della spazzola, '
                                                                    'come indicato.',
                                                                    'Sollevare per estrarre la spazzola '
                                                                    'rotante. Pulisci il rullo spazzolino con '
                                                                    'un attrezzo per la pulizia o delle '
                                                                    'forbici.',
                                                                    'Sciacquare la spazzola rotante e la '
                                                                    'protezione della spazzola con acqua '
                                                                    'corrente.',
                                                                    'Asciugare completamente la spazzola '
                                                                    'rotante e la protezione della spazzola '
                                                                    'prima del prossimo utilizzo.',
                                                                    'Reinstallare la spazzola rotante '
                                                                    "inserendo prima l'estremità sporgente "
                                                                    'fissa.',
                                                                    'Premere verso il basso per far scattare '
                                                                    'il para-spazzola in posizione.'],
                                                       'notes': [   'La protezione della spazzola deve essere '
                                                                    'sostituita anche ogni 3-6 mesi o quando '
                                                                    'usurata.']},
                                  'side_brush': {   'clean_frequency': 'Una volta al mese',
                                                    'replace_frequency': 'Ogni 3-6 mesi (o quando visibilmente '
                                                                         'usurato)',
                                                    'steps': [   'Rimuovere la spazzola laterale con un '
                                                                 'cacciavite.',
                                                                 'Srotolare con attenzione e rimuovere i '
                                                                 "capelli o le sostanze avvolte tra l'unità "
                                                                 'principale e la spazzola laterale.',
                                                                 'Pulire la spazzola laterale con acqua.',
                                                                 "Asciugare all'aria la spazzola laterale "
                                                                 'prima del prossimo utilizzo.',
                                                                 'Reinstallare la spazzola laterale sulla '
                                                                 'macchina.'],
                                                    'notes': [   'Le sostanze estranee, come i capelli, '
                                                                 'possono facilmente aggrovigliarsi nella '
                                                                 'spazzola laterale, quindi è meglio pulirla '
                                                                 'regolarmente.']},
                                  'sensor': {   'clean_frequency': 'Una volta al mese',
                                                'replace_frequency': None,
                                                'steps': [   'Sfregare via la polvere dai sensori e dai '
                                                             'contatti di ricarica utilizzando un panno '
                                                             'morbido.'],
                                                'notes': [   'Per mantenere prestazioni ottimali, pulire '
                                                             'regolarmente i sensori e i pin di contatto di '
                                                             'ricarica.',
                                                             'Sezione 7.4 "Pulire i Sensori, le Telecamere e i '
                                                             'Pin di Ricarica". Frequenze dalla tabella: '
                                                             'Sensori una volta al mese, Pin di ricarica una '
                                                             'volta al mese.']},
                                  'cleaning_tray': {   'clean_frequency': 'Svuotare e pulire quando è pieno '
                                                                          "(serbatoio dell'acqua sporca)",
                                                       'replace_frequency': None,
                                                       'steps': [   "Rimuovere il serbatoio dell'acqua sporca "
                                                                    'dalla stazione Omni.',
                                                                    "Svuotare il serbatoio dell'acqua sporca.",
                                                                    'Sciacquare accuratamente il serbatoio '
                                                                    "dell'acqua sporca con acqua corrente.",
                                                                    'Rimuovere il vassoio di pulizia dalla '
                                                                    'stazione Omni.',
                                                                    'Risciacquare accuratamente il vassoio di '
                                                                    'pulizia con acqua.',
                                                                    'Rimettere il vassoio nella Stazione '
                                                                    'Omni.'],
                                                       'notes': [   "Il serbatoio dell'acqua sporca deve "
                                                                    'essere svuotato e sciacquato quando è '
                                                                    'pieno.']},
                                  'mopping_cloth': {   'clean_frequency': "Lavare dopo l'uso / ispezionare "
                                                                          'regolarmente',
                                                       'replace_frequency': 'Ogni 3-6 mesi',
                                                       'steps': [   'Rimuovere i panni per pulire il pavimento '
                                                                    'dal robot.',
                                                                    'Lavare e asciugare completamente i panni '
                                                                    'prima del riutilizzo.',
                                                                    'Sostituire i panni quando diventano '
                                                                    'usurati o non puliscono più '
                                                                    'efficacemente.'],
                                                       'notes': []},
                                  'swivel_wheel': {   'clean_frequency': 'Una volta al mese',
                                                      'replace_frequency': None,
                                                      'steps': [   'Ispezionare la ruota girevole per capelli '
                                                                   'o detriti avvolti.',
                                                                   'Rimuovere i detriti con attenzione e '
                                                                   "pulire l'area della ruota.",
                                                                   'Verificare che la ruota giri liberamente '
                                                                   'prima della prossima esecuzione.'],
                                                      'notes': [   'Il manuale fornisce istruzioni per la '
                                                                   'pulizia della ruota girevole ma non '
                                                                   'specifica un intervallo di '
                                                                   'sostituzione.']}}},
    'pt': {   'x10_pro_omni': {   'filter': {   'clean_frequency': None,
                                                'replace_frequency': None,
                                                'steps': [   'Abra a tampa superior e retire a caixa de pó.',
                                                             'Pressione o botão de liberação para abrir e '
                                                             'esvaziar o coletor de pó.',
                                                             'Remova o filtro.',
                                                             'Toque no filtro para remover a poeira.',
                                                             'Enxágue a caixa de pó e o filtro completamente '
                                                             'com água.',
                                                             'Deixe a caixa de pó e o filtro secarem '
                                                             'completamente ao ar antes do próximo uso.',
                                                             'Coloque o filtro de volta na caixa de pó.',
                                                             'Insira o coletor de pó de volta na unidade '
                                                             'principal.'],
                                                'notes': [   'Não utilize uma escova, água quente ou qualquer '
                                                             'detergente para limpar o filtro.',
                                                             'Não utilize o filtro se ele não estiver '
                                                             'completamente seco, caso contrário, isso pode '
                                                             'afetar o desempenho da limpeza.']},
                                  'rolling_brush': {   'clean_frequency': None,
                                                       'replace_frequency': None,
                                                       'steps': [   'Puxe as abas de liberação para destravar '
                                                                    'o protetor de escova, conforme mostrado.',
                                                                    'Levante para retirar a escova rotativa. '
                                                                    'Limpe a escova rotativa com uma tesoura.',
                                                                    'Enxágue a escova rotativa e a proteção da '
                                                                    'escova com água corrente.',
                                                                    'Seque completamente a escova rotativa e a '
                                                                    'proteção da escova ao ar antes do próximo '
                                                                    'uso.',
                                                                    'Reinstale a escova rotativa inserindo '
                                                                    'primeiro a extremidade fixa saliente.',
                                                                    'Pressione para encaixar a proteção da '
                                                                    'escova no lugar.'],
                                                       'notes': [   'O protetor de escova também deve ser '
                                                                    'substituído a cada 3-6 meses ou quando '
                                                                    'estiver gasto.']},
                                  'side_brush': {   'clean_frequency': None,
                                                    'replace_frequency': None,
                                                    'steps': [   'Remova a escova lateral com uma chave de '
                                                                 'fenda.',
                                                                 'Desenrole cuidadosamente e remova qualquer '
                                                                 'cabelo ou substância que esteja enrolado '
                                                                 'entre a unidade principal e a escova '
                                                                 'lateral.',
                                                                 'Limpe a escova lateral com água.',
                                                                 'Deixe a escova lateral secar ao ar antes do '
                                                                 'próximo uso.',
                                                                 'Reinstale a escova lateral na máquina.'],
                                                    'notes': [   'Substâncias estranhas, como cabelos, podem '
                                                                 'se enroscar facilmente na escova lateral, '
                                                                 'por isso é melhor limpá-la regularmente.']},
                                  'sensor': {   'clean_frequency': None,
                                                'replace_frequency': None,
                                                'steps': [   'Limpe os sensores e os pinos de contato de '
                                                             'carregamento com um pano macio.'],
                                                'notes': [   'Para manter o melhor desempenho, limpe os '
                                                             'sensores e os pinos de contato de carregamento '
                                                             'regularmente.']},
                                  'cleaning_tray': {   'clean_frequency': None,
                                                       'replace_frequency': None,
                                                       'steps': [   'Remova o tanque de água suja da Estação '
                                                                    'Omni.',
                                                                    'Esvazie o tanque de água suja.',
                                                                    'Enxágue o tanque de água suja '
                                                                    'completamente com água corrente.',
                                                                    'Remova a bandeja de limpeza da Omni '
                                                                    'Station.',
                                                                    'Enxágue completamente a bandeja de '
                                                                    'limpeza com água.',
                                                                    'Coloque a bandeja de volta na Omni '
                                                                    'Station.'],
                                                       'notes': [   'O tanque de água suja deve ser esvaziado '
                                                                    'e enxaguado quando estiver cheio.']},
                                  'mopping_cloth': {   'clean_frequency': 'lavar após o uso / inspecionar '
                                                                          'regularmente',
                                                       'replace_frequency': 'A cada 3-6 meses',
                                                       'steps': [   'Remova os panos de esfregão do robô.',
                                                                    'Lave e seque completamente os panos antes '
                                                                    'de reutilizá-los.',
                                                                    'Substitua os panos quando estiverem '
                                                                    'gastos ou não limparem mais '
                                                                    'efetivamente.'],
                                                       'notes': []},
                                  'swivel_wheel': {   'clean_frequency': 'Uma vez por mês',
                                                      'replace_frequency': None,
                                                      'steps': [   'Inspecione a roda giratória para verificar '
                                                                   'se há cabelos ou detritos enrolados.',
                                                                   'Remova os detritos com cuidado e limpe a '
                                                                   'área da roda.',
                                                                   'Confirme que a roda gira livremente antes '
                                                                   'da próxima execução.'],
                                                      'notes': [   'O manual lista a limpeza da roda '
                                                                   'giratória, mas não fornece um intervalo de '
                                                                   'substituição específico.']}}},
    'ru': {   'x10_pro_omni': {   'filter': {   'clean_frequency': 'Раз в неделю',
                                                'replace_frequency': 'Каждые 3–6 месяцев',
                                                'steps': [   'Откройте верхнюю крышку и извлеките контейнер '
                                                             'для пыли.',
                                                             'Нажмите кнопку фиксатора, чтобы открыть и '
                                                             'опорожнить контейнер для пыли.',
                                                             'Извлеките фильтр.',
                                                             'Постучите по фильтру, чтобы стряхнуть пыль.',
                                                             'Тщательно промойте контейнер для пыли и фильтр '
                                                             'водой.',
                                                             'Перед следующим использованием полностью '
                                                             'просушите контейнер для пыли и фильтр на '
                                                             'воздухе.',
                                                             'Установите фильтр обратно в контейнер для пыли.',
                                                             'Задвиньте контейнер для пыли обратно в основной '
                                                             'блок.'],
                                                'notes': [   'Не используйте для очистки фильтра щётку, '
                                                             'горячую воду или какие-либо моющие средства.',
                                                             'Не используйте фильтр, если он не просох '
                                                             'полностью, иначе это может ухудшить качество '
                                                             'уборки.']},
                                  'rolling_brush': {   'clean_frequency': 'Раз в месяц',
                                                       'replace_frequency': 'Каждые 6 месяцев',
                                                       'steps': [   'Потяните за фиксаторы, чтобы '
                                                                    'разблокировать крышку щётки, как показано '
                                                                    'на рисунке.',
                                                                    'Приподнимите и извлеките основную щётку. '
                                                                    'Очистите основную щётку с помощью '
                                                                    'инструмента для чистки или ножниц.',
                                                                    'Промойте основную щётку и крышку щётки '
                                                                    'под проточной водой.',
                                                                    'Перед следующим использованием полностью '
                                                                    'просушите основную щётку и крышку щётки '
                                                                    'на воздухе.',
                                                                    'Установите основную щётку на место, '
                                                                    'вставив сначала фиксированный выступающий '
                                                                    'конец.',
                                                                    'Нажмите вниз, чтобы крышка щётки '
                                                                    'защёлкнулась на месте.'],
                                                       'notes': [   'Крышка щётки должна также заменяться '
                                                                    'каждые 3–6 месяцев или при видимом '
                                                                    'износе.']},
                                  'side_brush': {   'clean_frequency': 'Раз в месяц',
                                                    'replace_frequency': 'Каждые 3–6 месяцев (или при видимом '
                                                                         'износе)',
                                                    'steps': [   'Снимите боковую щётку с помощью отвёртки.',
                                                                 'Осторожно размотайте и удалите волосы или '
                                                                 'иные вещества, намотавшиеся между основным '
                                                                 'блоком и боковой щёткой.',
                                                                 'Очистите боковую щётку водой.',
                                                                 'Перед следующим использованием просушите '
                                                                 'боковую щётку на воздухе.',
                                                                 'Установите боковую щётку обратно на '
                                                                 'устройство.'],
                                                    'notes': [   'Посторонние предметы, например волосы, легко '
                                                                 'запутываются в боковой щётке, поэтому её '
                                                                 'лучше очищать регулярно.']},
                                  'sensor': {   'clean_frequency': 'Раз в месяц',
                                                'replace_frequency': None,
                                                'steps': [   'Протрите датчики и зарядные контакты мягкой '
                                                             'тканью.'],
                                                'notes': [   'Для поддержания оптимальной работы регулярно '
                                                             'очищайте датчики и зарядные контакты.']},
                                  'cleaning_tray': {   'clean_frequency': None,
                                                       'replace_frequency': None,
                                                       'steps': [   'Извлеките лоток для чистки из станции '
                                                                    'Omni.',
                                                                    'Тщательно промойте лоток для чистки '
                                                                    'водой.',
                                                                    'Установите лоток обратно в станцию Omni.'],
                                                       'notes': [   'Бак грязной воды следует опорожнять и '
                                                                    'промывать при полном заполнении.']},
                                  'mopping_cloth': {   'clean_frequency': 'Мойте после каждого использования / '
                                                                          'регулярно проверяйте',
                                                       'replace_frequency': 'Каждые 3–6 месяцев',
                                                       'steps': [   'Снимите тряпки для влажной уборки с '
                                                                    'робота.',
                                                                    'Промойте тряпки и полностью высушите '
                                                                    'перед следующим использованием.',
                                                                    'Замените тряпки, когда они изнашиваются '
                                                                    'или перестают эффективно чистить.'],
                                                       'notes': []},
                                  'swivel_wheel': {   'clean_frequency': 'Раз в месяц',
                                                      'replace_frequency': None,
                                                      'steps': [   'Проверьте поворотное колесо на наличие '
                                                                   'намотанных волос или мусора.',
                                                                   'Осторожно удалите мусор и протрите область '
                                                                   'колеса.',
                                                                   'Убедитесь, что колесо свободно вращается '
                                                                   'перед следующей уборкой.'],
                                                      'notes': [   'Руководство указывает на необходимость '
                                                                   'очистки поворотного колеса, но не содержит '
                                                                   'информацию об интервале его замены.']}}}}


# --- RTL locales (ar, he) — steps/notes AI+manual-sourced 2026-07-25, pending native review; frequencies via guide-frequency-translations.json ---
UPKEEP_GUIDE_TRANSLATIONS['ar'] = {
    "x10_pro_omni": {
        "filter": {
            "steps": [
                "افتح الغطاء العلوي وأخرج صندوق الغبار.",
                "أخرج الفلتر من صندوق الغبار.",
                "انفض الغبار عن الفلتر وأفرغ صندوق الغبار.",
                "اشطف صندوق الغبار والفلتر بالماء فقط.",
                "اترك القطعتين تجفّان في الهواء تمامًا قبل إعادة التركيب."
            ],
            "notes": [
                "لا تستخدم فرشاة أو ماءً ساخنًا أو منظّفًا.",
                "استبدل الفلتر كل 3 إلى 6 أشهر."
            ]
        },
        "sensor": {
            "steps": [
                "استخدم قطعة قماش ناعمة وجافة لمسح المستشعرات والكاميرات.",
                "امسح أيضًا أطراف الشحن أثناء صيانة المستشعرات."
            ],
            "notes": [
                "لا يذكر الدليل فترة استبدال للمستشعرات."
            ]
        },
        "side_brush": {
            "steps": [
                "أخرج الفرشاة الجانبية باستخدام مفك براغي.",
                "فُكّ وأزل أي شعر أو أوساخ.",
                "اشطف الفرشاة بالماء واتركها تجف في الهواء تمامًا.",
                "أعد تركيب الفرشاة بعد جفافها."
            ]
        },
        "rolling_brush": {
            "steps": [
                "حرّر ألسنة واقي الفرشاة وارفع الواقي للخارج.",
                "أخرج الفرشاة الدوارة.",
                "قصّ وأزل الشعر والأوساخ الملتفّة.",
                "اشطف الفرشاة والواقي، ثم اتركهما يجفّان في الهواء.",
                "أعد تركيب الفرشاة وثبّت الواقي في مكانه."
            ],
            "notes": [
                "ينبغي أيضًا استبدال واقي الفرشاة كل 3 إلى 6 أشهر أو عند تآكله."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "أزل قطع المسح من الروبوت.",
                "اغسل قطع المسح وجفّفها تمامًا قبل إعادة استخدامها.",
                "استبدل قطع المسح عندما تتآكل أو تفقد فعالية التنظيف."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "أخرج صينية التنظيف من محطة أومني.",
                "اشطف الصينية جيدًا بالماء.",
                "أعد تركيب الصينية بعد التنظيف."
            ],
            "notes": [
                "ينبغي إفراغ خزان المياه المتسخة وشطفه عند امتلائه."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "افحص العجلة الدوارة بحثًا عن شعر أو أوساخ ملتفّة.",
                "أزل الأوساخ بعناية وامسح منطقة العجلة حتى تنظُف.",
                "تأكد من دوران العجلة بحرية قبل الجولة التالية."
            ],
            "notes": [
                "يذكر الدليل تنظيف العجلة الدوارة لكنه لا يحدد فترة استبدال خاصة بها."
            ]
        }
    },
    "s1_pro": {
        "filter": {
            "steps": [
                "أخرج الفلتر عالي الأداء من منطقة صندوق الغبار.",
                "انفض الغبار والأوساخ برفق.",
                "أعد تركيب الفلتر أو استبدله بعد أن يصبح نظيفًا وجافًا."
            ],
            "notes": [
                "إرشادات صيانة الملحقات في التطبيق هي طريقة إعادة الضبط الرسمية الأساسية لطراز S1 Pro."
            ]
        },
        "sensor": {
            "steps": [
                "امسح مستشعرات الروبوت بقطعة قماش ناعمة وجافة.",
                "نظّف أيضًا نقاط تلامس الشحن أثناء صيانة المستشعرات."
            ]
        },
        "side_brush": {
            "steps": [
                "افحص الفرشاة الجانبية بحثًا عن شعر وأوساخ عالقة.",
                "أزل التراكمات حول القاعدة والشعيرات.",
                "استبدل الفرشاة إذا كانت الشعيرات ملتوية أو تالفة."
            ]
        },
        "rolling_brush": {
            "steps": [
                "أزل واقي الفرشاة الدوارة.",
                "افحص الفرشاة وغطائي طرفيها بحثًا عن شعر متشابك أو أوساخ.",
                "نظّف الفرشاة جيدًا قبل إعادة تركيبها."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "أزل ممسحة الأسطوانة أو أسطح تلامس المسح ونظّف البقايا.",
                "اترك القطع المنظّفة تجف قبل إعادة استخدامها.",
                "استبدل مستهلكات المسح عند ظهور التآكل أو انخفاض الأداء."
            ],
            "notes": [
                "توثيق طراز S1 موجّه نحو ممسحة الأسطوانة وليس نحو قطعتي مسح منفصلتين قابلتين للفك."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "أخرج صينية الفلتر أو حشوة الصينية من منطقة المحطة.",
                "اشطف البقايا والتراكمات.",
                "أعد التركيب بعد التنظيف."
            ],
            "notes": [
                "نظّف أيضًا خزاني المياه النظيفة والمتسخة وفلتر المياه المتسخة حسب الحاجة."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "افحص العجلة الدوارة بحثًا عن شعر وأوساخ.",
                "أزل التراكمات وتأكد من دوران العجلة بحرية."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "أخرج صندوق الغبار أو حجرة الفلتر.",
                "أخرج الفلتر وانفض عنه الغبار.",
                "اغسله فقط إذا سمحت إرشادات الدليل/التطبيق، ثم جفّفه تمامًا قبل إعادة التركيب."
            ],
            "notes": [
                "دليل ملحقات Omni C20 يعتمد بشكل أساسي على مقاطع الفيديو."
            ]
        },
        "sensor": {
            "steps": [
                "استخدم قطعة قماش نظيفة وجافة لمسح المستشعرات ونقاط تلامس الشحن على كل من الروبوت والمحطة."
            ]
        },
        "side_brush": {
            "steps": [
                "افحص الفرشاة الجانبية بحثًا عن التآكل أو التشابك أو التلف.",
                "أزل الشعر والأوساخ الملتفّة من الفرشاة والقاعدة.",
                "استبدل الفرشاة إذا كانت الشعيرات ملتوية أو مفقودة."
            ]
        },
        "rolling_brush": {
            "steps": [
                "افحص الفرشاة الدوارة بحثًا عن شعر متشابك أو أوساخ.",
                "استخدم أداة التنظيف أو المقص لقص المواد الملتفّة.",
                "أعد التركيب بعد التنظيف."
            ],
            "notes": [
                "يقلل مشط Pro-Detangle الحاجة إلى التنظيف اليدوي لكنه لا يلغيها."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "أزل قطع المسح من الروبوت أو المحطة.",
                "نظّفها وجفّفها تمامًا قبل إعادة استخدامها.",
                "استبدل قطع المسح عند تآكلها أو فقدانها فعالية التنظيف."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "افصل قاعدة المحطة أو مكوّن منطقة غسل الممسحة.",
                "اشطف وامسح البقايا من منطقة الصينية.",
                "أعد تركيب الصينية بعد التنظيف."
            ],
            "notes": [
                "راقب أيضًا خزاني المياه النظيفة والمتسخة وقم بصيانتهما."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "أزل صندوق الغبار وأخرج الفلتر.",
                "انفض الفلتر برفق لإزالة الغبار.",
                "إذا شُطف، فاتركه يجف تمامًا قبل إعادة التركيب."
            ]
        },
        "sensor": {
            "steps": [
                "امسح مستشعرات السقوط ومستشعرات المصدّ ونقاط تلامس الشحن بقطعة قماش جافة."
            ]
        },
        "side_brush": {
            "steps": [
                "أزل الفرشاة الجانبية.",
                "أزل الشعر والأوساخ من الفرشاة وقاعدتها.",
                "أعد التركيب أو استبدلها عند التآكل."
            ]
        },
        "rolling_brush": {
            "steps": [
                "اضغط على ألسنة واقي الفرشاة الرئيسية وأزل الواقي.",
                "ارفع الفرشاة الرئيسية للخارج.",
                "استخدم أداة التنظيف أو المقص لإزالة الشعر والأوساخ.",
                "أعد تركيب الفرشاة والواقي."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "أزل قطعة المسح من حاملها.",
                "اغسلها وجفّفها قبل إعادة استخدامها.",
                "استبدلها إذا أصبحت بالية أو غير فعّالة."
            ],
            "notes": [
                "ينطبق فقط على طرازات X8 الهجينة/القادرة على المسح."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "اضغط زر تحرير صندوق الغبار وأزل صندوق الغبار.",
                "أخرج الفلتر وانفض عنه الأوساخ السائبة.",
                "إذا سمح دليل الطراز المحدد بذلك، فاشطفه وجفّفه تمامًا قبل إعادة التركيب."
            ]
        },
        "sensor": {
            "steps": [
                "استخدم قطعة قماش جافة لمسح المستشعرات ونقاط تلامس الشحن على الروبوت والقاعدة."
            ]
        },
        "side_brush": {
            "steps": [
                "اسحب الفرشاة الجانبية للخارج.",
                "أزل الشعر المتشابك والأوساخ.",
                "أعد التركيب أو استبدلها عند التآكل."
            ]
        },
        "rolling_brush": {
            "steps": [
                "أزل غطاء الفرشاة الرئيسية.",
                "ارفع الفرشاة الدوارة للخارج.",
                "نظّف الشعر والأوساخ الملتفّة من الفرشاة والمحامل.",
                "امسحها حتى تجف وأعد تركيب الفرشاة والواقي."
            ],
            "notes": [
                "تستخدم طرازات SES أيضًا قص الشعر التلقائي لتقليل الصيانة."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "أزل قطعة المسح أو القماشة.",
                "نظّفها وجفّفها تمامًا قبل إعادة استخدامها.",
                "استبدل القماشة عند تآكلها."
            ],
            "notes": [
                "ينطبق فقط على الطُرز الهجينة."
            ]
        }
    }
}
UPKEEP_GUIDE_TRANSLATIONS['he'] = {
    "x10_pro_omni": {
        "filter": {
            "steps": [
                "פתחו את המכסה העליון והוציאו את מיכל האבק.",
                "הוציאו את המסנן ממיכל האבק.",
                "נקו את האבק מהמסנן בטפיחה ורוקנו את מיכל האבק.",
                "שטפו את מיכל האבק ואת המסנן במים בלבד.",
                "הניחו לשני החלקים להתייבש לחלוטין באוויר לפני ההרכבה מחדש."
            ],
            "notes": [
                "אין להשתמש במברשת, במים חמים או בחומר ניקוי.",
                "החליפו את המסנן כל 3–6 חודשים."
            ]
        },
        "sensor": {
            "steps": [
                "השתמשו במטלית רכה ויבשה לניגוב החיישנים והמצלמות.",
                "נגבו גם את מגעי הטעינה בזמן תחזוקת החיישנים."
            ],
            "notes": [
                "לא צוין מרווח החלפה לחיישנים במדריך."
            ]
        },
        "side_brush": {
            "steps": [
                "הסירו את המברשת הצדדית בעזרת מברג.",
                "שחררו והסירו שיער או פסולת שנכרכו.",
                "שטפו את המברשת במים והניחו לה להתייבש לחלוטין באוויר.",
                "הרכיבו את המברשת מחדש לאחר שהתייבשה."
            ]
        },
        "rolling_brush": {
            "steps": [
                "שחררו את תפסי מכסה המברשת והרימו את המכסה החוצה.",
                "הוציאו את המברשת המתגלגלת.",
                "גזרו והסירו שיער ופסולת שנכרכו.",
                "שטפו את המברשת ואת המכסה, ולאחר מכן הניחו להם להתייבש באוויר.",
                "הרכיבו מחדש את המברשת והצמידו את המכסה חזרה למקומו."
            ],
            "notes": [
                "יש להחליף גם את מכסה המברשת כל 3–6 חודשים או בעת בלאי."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "הסירו את מטליות השטיפה מהרובוט.",
                "כבסו וייבשו לחלוטין את המטליות לפני שימוש חוזר.",
                "החליפו את המטליות כאשר הן בלויות או שאינן מנקות ביעילות."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "הוציאו את מגש הניקוי מתחנת Omni.",
                "שטפו את המגש היטב במים.",
                "הרכיבו את המגש מחדש לאחר הניקוי."
            ],
            "notes": [
                "יש לרוקן ולשטוף את מיכל המים המלוכלכים כשהוא מלא."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "בדקו אם נכרכו שיער או פסולת בגלגל המסתובב.",
                "הסירו את הפסולת בזהירות ונגבו את אזור הגלגל לניקיון.",
                "ודאו שהגלגל מסתובב בחופשיות לפני הריצה הבאה."
            ],
            "notes": [
                "המדריך מציין ניקוי של הגלגל המסתובב אך אינו מספק מרווח החלפה ייעודי."
            ]
        }
    },
    "s1_pro": {
        "filter": {
            "steps": [
                "הוציאו את המסנן בעל הביצועים הגבוהים מאזור מיכל האבק.",
                "טפחו בעדינות להסרת אבק ופסולת.",
                "הרכיבו מחדש או החליפו את המסנן לאחר שהוא נקי ויבש."
            ],
            "notes": [
                "הנחיות שירות האביזרים באפליקציה הן תהליך האיפוס הרשמי העיקרי עבור S1 Pro."
            ]
        },
        "sensor": {
            "steps": [
                "נגבו את חיישני הרובוט במטלית רכה ויבשה.",
                "נקו גם את מגעי הטעינה בזמן טיפול בחיישנים."
            ]
        },
        "side_brush": {
            "steps": [
                "בדקו אם נלכדו שיער ופסולת במברשת הצדדית.",
                "הסירו הצטברות סביב הבסיס והזיפים.",
                "החליפו את המברשת אם הזיפים כפופים או פגומים."
            ]
        },
        "rolling_brush": {
            "steps": [
                "הסירו את מכסה המברשת המתגלגלת.",
                "בדקו את המברשת ואת שני מכסי הקצה לאיתור שיער סבוך או פסולת.",
                "נקו את המברשת ביסודיות לפני ההרכבה מחדש."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "הסירו את המגב המתגלגל או את משטחי המגע של המגב ונקו את השאריות.",
                "הניחו לחלקים שנוקו להתייבש לפני שימוש חוזר.",
                "החליפו את המתכלה הקשור למגב כאשר מופיע בלאי או שהביצועים יורדים."
            ],
            "notes": [
                "התיעוד של S1 מתמקד במגב מתגלגל ולא בניסוח של שתי מטליות נשלפות."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "הוציאו את מגש המסנן או את תוסף המגש מאזור התחנה.",
                "שטפו את השאריות וההצטברות.",
                "הרכיבו מחדש לאחר הניקוי."
            ],
            "notes": [
                "נקו גם את מיכלי המים הנקיים/המלוכלכים ואת מסנן המים המלוכלכים לפי הצורך."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "בדקו אם יש שיער ופסולת בגלגל המסתובב.",
                "הסירו את ההצטברות וודאו שהגלגל מסתובב בחופשיות."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "הוציאו את מיכל האבק או את תא המסנן.",
                "הוציאו את המסנן וטפחו להסרת האבק.",
                "שטפו רק אם הנחיות המדריך/האפליקציה מתירות זאת, ולאחר מכן ייבשו לחלוטין לפני ההרכבה מחדש."
            ],
            "notes": [
                "מדריך האביזרים של Omni C20 מבוסס בעיקר על סרטונים."
            ]
        },
        "sensor": {
            "steps": [
                "השתמשו במטלית נקייה ויבשה לניגוב החיישנים ומגעי הטעינה הן ברובוט והן בתחנה."
            ]
        },
        "side_brush": {
            "steps": [
                "בדקו אם יש במברשת הצדדית בלאי, סבך או נזק.",
                "הסירו שיער ופסולת שנכרכו מהמברשת ומהבסיס.",
                "החליפו את המברשת אם הזיפים כפופים או חסרים."
            ]
        },
        "rolling_brush": {
            "steps": [
                "בדקו אם יש במברשת המתגלגלת שיער סבוך או פסולת.",
                "השתמשו בכלי הניקוי או במספריים לגזירת חומר שנכרך.",
                "הרכיבו מחדש לאחר הניקוי."
            ],
            "notes": [
                "מסרק Pro-Detangle מפחית אך אינו מייתר ניקוי ידני."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "הסירו את מטליות השטיפה מהרובוט או מהתחנה.",
                "נקו וייבשו אותן לחלוטין לפני שימוש חוזר.",
                "החליפו את המטליות כאשר הן בלויות או שאינן מנקות ביעילות."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "נתקו את בסיס התחנה או את רכיב אזור שטיפת המגב.",
                "שטפו ונגבו שאריות מאזור המגש.",
                "הרכיבו את המגש מחדש לאחר הניקוי."
            ],
            "notes": [
                "עקבו ותחזקו גם את מיכלי המים הנקיים והמלוכלכים."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "הוציאו את מיכל האבק והוציאו את המסנן.",
                "טפחו על המסנן בעדינות להסרת האבק.",
                "אם שטפתם אותו, הניחו לו להתייבש לחלוטין לפני ההרכבה מחדש."
            ]
        },
        "sensor": {
            "steps": [
                "נגבו את חיישני הנפילה, חיישני הפגוש ומגעי הטעינה במטלית יבשה."
            ]
        },
        "side_brush": {
            "steps": [
                "הסירו את המברשת הצדדית.",
                "נקו שיער ופסולת מהמברשת ומהבסיס שלה.",
                "חברו מחדש או החליפו בעת בלאי."
            ]
        },
        "rolling_brush": {
            "steps": [
                "לחצו על תפסי מכסה המברשת המרכזית והסירו את המכסה.",
                "הרימו והוציאו את המברשת המרכזית.",
                "השתמשו בכלי הניקוי או במספריים להסרת שיער ופסולת.",
                "הרכיבו מחדש את המברשת ואת המכסה."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "הסירו את מטלית השטיפה מהמחזיק.",
                "כבסו וייבשו אותה לפני שימוש חוזר.",
                "החליפו אותה אם היא בלויה או לא יעילה."
            ],
            "notes": [
                "רלוונטי רק לדגמי X8 היברידיים / התומכים בשטיפה."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "לחצו על כפתור השחרור של מיכל האבק והוציאו את מיכל האבק.",
                "הוציאו את המסנן וטפחו להסרת לכלוך רופף.",
                "אם מדריך הדגם הספציפי מתיר זאת, שטפו וייבשו לחלוטין לפני ההרכבה מחדש."
            ]
        },
        "sensor": {
            "steps": [
                "השתמשו במטלית יבשה לניגוב החיישנים ומגעי הטעינה ברובוט ובבסיס."
            ]
        },
        "side_brush": {
            "steps": [
                "משכו והסירו את המברשת הצדדית.",
                "הסירו שיער סבוך ופסולת.",
                "חברו מחדש או החליפו בעת בלאי."
            ]
        },
        "rolling_brush": {
            "steps": [
                "הסירו את מכסה המברשת המרכזית.",
                "הרימו והוציאו את המברשת המתגלגלת.",
                "נקו שיער ופסולת שנכרכו מהמברשת ומהמסבים.",
                "נגבו ליובש והרכיבו מחדש את המברשת ואת המכסה."
            ],
            "notes": [
                "דגמי SES משתמשים גם בחיתוך שיער אוטומטי כדי להפחית תחזוקה."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "הסירו את מטלית השטיפה.",
                "נקו וייבשו אותה לחלוטין לפני שימוש חוזר.",
                "החליפו את המטלית כאשר היא בלויה."
            ],
            "notes": [
                "רלוונטי רק לגרסאות היברידיות."
            ]
        }
    }
}

# --- ja guide (steps/notes; AI+manual-sourced, pending native review; freqs via guide-frequency-translations.json) ---
UPKEEP_GUIDE_TRANSLATIONS['ja'] = {
    "x10_pro_omni": {
        "filter": {
            "steps": [
                "本体の上部カバーを開け、ダスト容器を取り外します。",
                "ダスト容器からフィルターを取り出します。",
                "フィルターを軽くたたいてほこりを落とし、ダスト容器を空にします。",
                "ダスト容器とフィルターを水だけですすぎます。",
                "取り付け直す前に、両方の部品を完全に自然乾燥させます。"
            ],
            "notes": [
                "ブラシ、お湯、洗剤は使用しないでください。",
                "フィルターは3～6ヶ月ごとに交換してください。"
            ]
        },
        "sensor": {
            "steps": [
                "柔らかい乾いた布でセンサーとカメラを拭きます。",
                "センサーのお手入れの際に、充電端子も一緒に拭きます。"
            ],
            "notes": [
                "取扱説明書にセンサーの交換頻度は記載されていません。"
            ]
        },
        "side_brush": {
            "steps": [
                "ドライバーでねじを緩め、サイドブラシを取り外します。",
                "絡まった髪の毛や異物をほどいて取り除きます。",
                "サイドブラシを水洗いし、完全に自然乾燥させます。",
                "乾いたら、サイドブラシを元の位置に取り付けます。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "つまみを押しながらブラシガードのロックを解除し、取り外します。",
                "ローラーブラシを取り出します。",
                "絡まった髪の毛や異物をはさみで切って取り除きます。",
                "ローラーブラシとブラシガードを水で洗い、自然乾燥させます。",
                "ローラーブラシを元の位置に戻し、ブラシガードをカチッと音がするまで押して閉じます。"
            ],
            "notes": [
                "ブラシガードも3～6ヶ月ごと、または摩耗した場合に交換してください。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "モップクロスを本体から取り外します。",
                "再使用する前に、モップクロスを洗って完全に乾かします。",
                "モップクロスが摩耗したり、十分に汚れが落ちなくなったら交換します。"
            ]
        },
        "cleaning_tray": {
            "steps": [
                "クリーニングトレイをステーションから取り外します。",
                "クリーニングトレイを水でよく洗います。",
                "清掃後、クリーニングトレイを取り付け直します。"
            ],
            "notes": [
                "汚水タンクは満杯になったら水を捨てて洗ってください。"
            ]
        },
        "swivel_wheel": {
            "steps": [
                "自在輪に髪の毛や異物が絡まっていないか点検します。",
                "異物を丁寧に取り除き、自在輪の周囲を拭いてきれいにします。",
                "次回の使用前に、自在輪がスムーズに回転することを確認します。"
            ],
            "notes": [
                "取扱説明書に自在輪の清掃は記載されていますが、専用の交換頻度は示されていません。"
            ]
        }
    },
    "s1_pro": {
        "filter": {
            "steps": [
                "ダスト容器から高性能フィルターを取り外します。",
                "ほこりやゴミを軽くたたいて落とします。",
                "フィルターがきれいで乾いたら、取り付け直すか交換します。"
            ],
            "notes": [
                "S1 Proでは、アプリ内のアクセサリーメンテナンス案内が公式の主なリセット手順です。"
            ]
        },
        "sensor": {
            "steps": [
                "柔らかい乾いた布で本体のセンサーを拭きます。",
                "センサーのお手入れの際に、充電端子も一緒に清掃します。"
            ]
        },
        "side_brush": {
            "steps": [
                "サイドブラシに絡まった髪の毛や異物がないか点検します。",
                "付け根とブラシ部分にたまった汚れを取り除きます。",
                "ブラシの毛が曲がったり傷んだりしている場合は交換します。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "ローラーブラシのブラシガードを取り外します。",
                "ローラーブラシと両側のエンドキャップに髪の毛や異物が絡まっていないか確認します。",
                "取り付け直す前に、ローラーブラシをしっかり清掃します。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "ローラーモップまたはモップの接触面を取り外し、汚れを洗い落とします。",
                "清掃した部品を再使用する前に乾かします。",
                "摩耗が目立ったり性能が低下したら、モップ関連の消耗品を交換します。"
            ],
            "notes": [
                "S1の説明書は、取り外し式のツインパッドではなくローラーモップを前提とした記載になっています。"
            ]
        },
        "cleaning_tray": {
            "steps": [
                "ステーションからフィルタートレイまたはトレイインサートを取り外します。",
                "付着した汚れやたまった汚れを洗い流します。",
                "清掃後、取り付け直します。"
            ],
            "notes": [
                "必要に応じて、清水タンク・汚水タンクおよび汚水フィルターも清掃してください。"
            ]
        },
        "swivel_wheel": {
            "steps": [
                "自在輪に髪の毛や異物がないか点検します。",
                "たまった汚れを取り除き、自在輪がスムーズに回転することを確認します。"
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "ダスト容器またはフィルター収納部を取り外します。",
                "フィルターを取り出し、軽くたたいてほこりを落とします。",
                "取扱説明書／アプリの案内で認められている場合のみ洗い、取り付け直す前に完全に乾かします。"
            ],
            "notes": [
                "Omni C20のアクセサリー清掃ガイドは主に動画で提供されています。"
            ]
        },
        "sensor": {
            "steps": [
                "清潔で乾いた布を使い、本体とステーションの両方のセンサーと充電端子を拭きます。"
            ]
        },
        "side_brush": {
            "steps": [
                "サイドブラシに摩耗・絡まり・破損がないか点検します。",
                "ブラシと付け根に絡まった髪の毛や異物を取り除きます。",
                "ブラシの毛が曲がっていたり抜けている場合は交換します。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "ローラーブラシに髪の毛や異物が絡まっていないか点検します。",
                "掃除用ツールまたははさみで、絡まった異物を切って取り除きます。",
                "清掃後、元の位置に戻します。"
            ],
            "notes": [
                "Pro-Detangleコームは手動清掃の手間を減らしますが、完全になくすものではありません。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "モップクロスを本体またはステーションから取り外します。",
                "再使用する前に洗って完全に乾かします。",
                "摩耗したり、十分に汚れが落ちなくなったら交換します。"
            ]
        },
        "cleaning_tray": {
            "steps": [
                "ステーションのベースまたはモップ洗浄部の部品を取り外します。",
                "トレイ部分の汚れを洗い流し、拭き取ります。",
                "清掃後、トレイを取り付け直します。"
            ],
            "notes": [
                "清水タンクと汚水タンクの状態も確認し、お手入れしてください。"
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "ダスト容器を取り外し、フィルターを取り出します。",
                "フィルターを軽くたたいてほこりを落とします。",
                "水洗いした場合は、取り付け直す前に完全に乾かします。"
            ]
        },
        "sensor": {
            "steps": [
                "乾いた布で落下防止センサー、バンパーセンサー、充電端子を拭きます。"
            ]
        },
        "side_brush": {
            "steps": [
                "サイドブラシを取り外します。",
                "ブラシとその付け根から髪の毛や異物を取り除きます。",
                "元に戻すか、摩耗している場合は交換します。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "ローラーブラシのブラシガードのつまみをつまんで、ブラシガードを取り外します。",
                "ローラーブラシを持ち上げて取り出します。",
                "掃除用ツールまたははさみで髪の毛や異物を取り除きます。",
                "ローラーブラシとブラシガードを取り付け直します。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "モップクロスをホルダーから取り外します。",
                "再使用する前に洗って乾かします。",
                "摩耗したり効果がなくなったら交換します。"
            ],
            "notes": [
                "水拭き対応のX8ハイブリッドモデルにのみ該当します。"
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "ダスト容器の取り外しボタンを押し、ダスト容器を取り外します。",
                "フィルターを取り出し、軽くたたいて汚れを落とします。",
                "お使いのモデルの説明書で認められている場合は、水洗いして完全に乾かしてから取り付け直します。"
            ]
        },
        "sensor": {
            "steps": [
                "乾いた布で本体とベースのセンサーと充電端子を拭きます。"
            ]
        },
        "side_brush": {
            "steps": [
                "サイドブラシを引き抜いて取り外します。",
                "絡まった髪の毛や異物を取り除きます。",
                "元に戻すか、摩耗している場合は交換します。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "ローラーブラシのカバーを取り外します。",
                "ローラーブラシを持ち上げて取り出します。",
                "ブラシと軸受けに絡まった髪の毛や異物を取り除きます。",
                "水気を拭き取り、ローラーブラシとブラシガードを取り付け直します。"
            ],
            "notes": [
                "SESモデルは自動毛切断機能も備えており、お手入れの手間を軽減します。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "モップクロスを取り外します。",
                "再使用する前に洗って完全に乾かします。",
                "摩耗したらモップクロスを交換します。"
            ],
            "notes": [
                "水拭き対応のハイブリッドモデルにのみ該当します。"
            ]
        }
    }
}

# --- zh-Hans guide (steps/notes; AI+manual-sourced, pending native review; freqs via guide-frequency-translations.json) ---
UPKEEP_GUIDE_TRANSLATIONS['zh-Hans'] = {
    "x10_pro_omni": {
        "filter": {
            "steps": [
                "打开顶盖，取出尘盒。",
                "从尘盒中取出滤网。",
                "轻拍滤网抖落灰尘，并清空尘盒。",
                "仅用清水冲洗尘盒和滤网。",
                "重新安装前，将两个部件彻底风干。"
            ],
            "notes": [
                "请勿使用刷子、热水或清洁剂。",
                "请每 3-6 个月更换一次滤网。"
            ]
        },
        "sensor": {
            "steps": [
                "用柔软的干布擦拭传感器和摄像头。",
                "保养传感器时，请一并擦拭充电电极。"
            ],
            "notes": [
                "手册未列出传感器的更换周期。"
            ]
        },
        "side_brush": {
            "steps": [
                "使用螺丝刀拆下边刷。",
                "解开并清除缠绕的头发或碎屑。",
                "用清水冲洗边刷，并将其彻底风干。",
                "待边刷干燥后重新安装。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "解锁滚刷盖板卡扣，将盖板抬出。",
                "取出滚刷。",
                "剪除并清理缠绕的头发和碎屑。",
                "冲洗滚刷和盖板，然后将其风干。",
                "重新安装滚刷，并将盖板卡回原位。"
            ],
            "notes": [
                "滚刷盖板同样应每 3-6 个月或在磨损时更换。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "从机器人上取下拖布。",
                "再次使用前，请清洗拖布并将其彻底晾干。",
                "当拖布磨损或清洁效果下降时，请及时更换。"
            ]
        },
        "cleaning_tray": {
            "steps": [
                "从 Omni 基站取出清洁托盘。",
                "用清水彻底冲洗托盘。",
                "清洁后将托盘装回。"
            ],
            "notes": [
                "污水箱装满后应及时清空并冲洗。"
            ]
        },
        "swivel_wheel": {
            "steps": [
                "检查万向轮上是否缠绕头发或碎屑。",
                "小心清除碎屑，并将轮子周围擦拭干净。",
                "在下次清扫前，确认轮子转动顺畅。"
            ],
            "notes": [
                "手册列出了万向轮的清洁方法，但未提供专门的更换周期。"
            ]
        }
    },
    "s1_pro": {
        "filter": {
            "steps": [
                "从尘盒处取出高性能滤网。",
                "轻轻抖落灰尘和碎屑。",
                "待滤网清洁并晾干后，将其重新安装或更换。"
            ],
            "notes": [
                "应用程序中的配件保养指引是 S1 Pro 主要的官方重置流程。"
            ]
        },
        "sensor": {
            "steps": [
                "用柔软的干布擦拭机器人传感器。",
                "保养传感器时，请一并清洁充电电极。"
            ]
        },
        "side_brush": {
            "steps": [
                "检查边刷是否夹有头发和碎屑。",
                "清除底座和刷毛周围的积垢。",
                "如果刷毛弯曲或损坏，请更换边刷。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "取下滚刷盖板。",
                "检查滚刷及其两端端盖是否缠有头发或碎屑。",
                "重新安装前，将滚刷彻底清洁干净。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "取下滚筒拖布或拖布接触面，清除残留污渍。",
                "清洁后待部件晾干再使用。",
                "当出现明显磨损或效果下降时，请更换拖布类耗材。"
            ],
            "notes": [
                "S1 的文档以滚筒拖布为主，而非可拆卸双拖布的表述。"
            ]
        },
        "cleaning_tray": {
            "steps": [
                "从基站处取出滤网托盘或托盘衬件。",
                "冲洗掉残留物和积垢。",
                "清洁后重新安装。"
            ],
            "notes": [
                "并按需清洁清水箱、污水箱以及污水滤网。"
            ]
        },
        "swivel_wheel": {
            "steps": [
                "检查万向轮上是否有头发和碎屑。",
                "清除积垢，并确认轮子转动顺畅。"
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "取出尘盒或滤网仓。",
                "取出滤网并轻拍抖落灰尘。",
                "仅在手册/应用指引允许时清洗，然后彻底晾干再重新安装。"
            ],
            "notes": [
                "Omni C20 的配件保养指南主要以视频形式提供。"
            ]
        },
        "sensor": {
            "steps": [
                "用干净的干布擦拭机器人和基站上的传感器与充电电极。"
            ]
        },
        "side_brush": {
            "steps": [
                "检查边刷是否磨损、缠绕或损坏。",
                "清除边刷和底座上缠绕的头发和碎屑。",
                "如果刷毛弯曲或缺失，请更换边刷。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "检查滚刷是否缠有头发或碎屑。",
                "使用清洁工具或剪刀剪除缠绕的杂物。",
                "清洁后重新安装。"
            ],
            "notes": [
                "Pro-Detangle 防缠绕梳可减少但无法完全免除手动清洁。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "从机器人或基站上取下拖布。",
                "再次使用前，请清洗并彻底晾干。",
                "当拖布磨损或清洁效果下降时，请更换。"
            ]
        },
        "cleaning_tray": {
            "steps": [
                "拆下基站底座或拖布清洗区部件。",
                "冲洗并擦除托盘区域的残留物。",
                "清洁后将托盘装回。"
            ],
            "notes": [
                "并注意查看和清洁清水箱与污水箱。"
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "取出尘盒并取下滤网。",
                "轻拍滤网以抖落灰尘。",
                "如果冲洗过，请在重新安装前将其彻底风干。"
            ]
        },
        "sensor": {
            "steps": [
                "用干布擦拭防跌落传感器、缓冲器传感器和充电电极。"
            ]
        },
        "side_brush": {
            "steps": [
                "取下边刷。",
                "清除边刷及其底座上的头发和碎屑。",
                "重新安装；如已磨损则更换。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "捏住滚刷盖板卡扣，取下盖板。",
                "提起并取出滚刷。",
                "使用清洁工具或剪刀清除头发和碎屑。",
                "重新安装滚刷和盖板。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "从支架上取下拖布。",
                "再次使用前清洗并晾干。",
                "如果磨损或效果变差则更换。"
            ],
            "notes": [
                "仅适用于支持拖地的 X8 Hybrid 机型。"
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "按下尘盒释放按钮，取出尘盒。",
                "取下滤网并轻拍抖落浮尘。",
                "如果具体机型指南允许，请冲洗并彻底晾干后再重新安装。"
            ]
        },
        "sensor": {
            "steps": [
                "用干布擦拭机器人和基站上的传感器与充电电极。"
            ]
        },
        "side_brush": {
            "steps": [
                "拔下边刷。",
                "清除缠绕的头发和碎屑。",
                "重新安装；如已磨损则更换。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "取下滚刷盖板。",
                "提起并取出滚刷。",
                "清除滚刷和轴承上缠绕的头发和碎屑。",
                "擦干后重新安装滚刷和盖板。"
            ],
            "notes": [
                "SES 机型还配备自动断发功能以减少维护。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "取下拖布或抹布。",
                "再次使用前，请清洗并彻底晾干。",
                "当拖布磨损时请更换。"
            ],
            "notes": [
                "仅适用于 Hybrid 机型。"
            ]
        }
    }
}

# --- zh-Hant guide (steps/notes; AI+manual-sourced, pending native review; freqs via guide-frequency-translations.json) ---
UPKEEP_GUIDE_TRANSLATIONS['zh-Hant'] = {
    "x10_pro_omni": {
        "filter": {
            "steps": [
                "打開上蓋，取出集塵盒。",
                "從集塵盒取出濾網。",
                "輕拍濾網以抖落灰塵，並清空集塵盒。",
                "僅用清水沖洗集塵盒與濾網。",
                "待兩者完全風乾後再裝回。"
            ],
            "notes": [
                "請勿使用刷子、熱水或清潔劑。",
                "每 3 至 6 個月更換濾網。"
            ]
        },
        "sensor": {
            "steps": [
                "使用柔軟乾布擦拭感測器與鏡頭。",
                "進行感測器保養時，一併擦拭充電接觸點。"
            ],
            "notes": [
                "手冊未列出感測器的更換週期。"
            ]
        },
        "side_brush": {
            "steps": [
                "使用螺絲起子拆下邊刷。",
                "解開並清除纏繞的毛髮或碎屑。",
                "用清水沖洗邊刷，並使其完全風乾。",
                "待邊刷乾燥後再裝回。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "解開滾刷護蓋的卡榫，將護蓋取出。",
                "取出滾刷。",
                "剪除並清理纏繞的毛髮與碎屑。",
                "沖洗滾刷與護蓋，然後使其風乾。",
                "裝回滾刷，並將護蓋扣回原位。"
            ],
            "notes": [
                "滾刷護蓋也應每 3 至 6 個月或於磨損時更換。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "從機器人取下拖布。",
                "清洗拖布並完全晾乾後再使用。",
                "當拖布磨損或清潔效果變差時予以更換。"
            ]
        },
        "cleaning_tray": {
            "steps": [
                "從 Omni 基站取出清潔盤。",
                "用清水徹底沖洗清潔盤。",
                "清潔後將清潔盤裝回。"
            ],
            "notes": [
                "污水箱裝滿時應清空並沖洗。"
            ]
        },
        "swivel_wheel": {
            "steps": [
                "檢查萬向輪是否纏繞毛髮或卡有碎屑。",
                "小心清除碎屑，並將輪子周圍擦拭乾淨。",
                "下次清潔前，確認輪子能自由轉動。"
            ],
            "notes": [
                "手冊列有萬向輪的清潔說明，但未提供專屬的更換週期。"
            ]
        }
    },
    "s1_pro": {
        "filter": {
            "steps": [
                "從集塵盒區域取出高效濾網。",
                "輕拍去除灰塵與碎屑。",
                "待濾網潔淨乾燥後再裝回或更換。"
            ],
            "notes": [
                "S1 Pro 的官方主要重設流程，是應用程式中的配件保養指引。"
            ]
        },
        "sensor": {
            "steps": [
                "使用柔軟乾布擦拭機器人的感測器。",
                "保養感測器時，一併清潔充電接觸點。"
            ]
        },
        "side_brush": {
            "steps": [
                "檢查邊刷是否卡有毛髮與碎屑。",
                "清除底座與刷毛周圍的積垢。",
                "若刷毛彎曲或損壞，請更換邊刷。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "取下滾刷護蓋。",
                "檢查滾刷與兩端端蓋是否纏繞毛髮或卡有碎屑。",
                "徹底清潔滾刷後再裝回。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "取下滾筒拖布或拖地接觸面，清除殘留污垢。",
                "待清潔後的部件乾燥後再使用。",
                "當出現明顯磨損或效能下降時，更換拖地相關耗材。"
            ],
            "notes": [
                "S1 的說明文件以滾筒拖布為主，而非可拆式雙拖布的用語。"
            ]
        },
        "cleaning_tray": {
            "steps": [
                "從基站區域取出濾網托盤或托盤內襯。",
                "沖洗掉殘留污垢與積垢。",
                "清潔後裝回。"
            ],
            "notes": [
                "並視需要清潔清水箱／污水箱及污水濾網。"
            ]
        },
        "swivel_wheel": {
            "steps": [
                "檢查萬向輪是否卡有毛髮與碎屑。",
                "清除積垢，並確認輪子能自由轉動。"
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "取出集塵盒或濾網艙。",
                "取出濾網並輕拍去除灰塵。",
                "僅在手冊／應用程式指引允許時清洗，並待完全乾燥後再裝回。"
            ],
            "notes": [
                "Omni C20 的配件指南主要以影片呈現。"
            ]
        },
        "sensor": {
            "steps": [
                "使用潔淨乾布擦拭機器人與基站上的感測器及充電接觸點。"
            ]
        },
        "side_brush": {
            "steps": [
                "檢查邊刷是否磨損、纏繞或損壞。",
                "清除邊刷與底座上纏繞的毛髮與碎屑。",
                "若刷毛彎曲或缺損，請更換邊刷。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "檢查滾刷是否纏繞毛髮或卡有碎屑。",
                "使用清潔工具或剪刀剪除纏繞的雜物。",
                "清潔後裝回。"
            ],
            "notes": [
                "Pro-Detangle 防纏梳可減少但無法完全省去手動清潔。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "從機器人或基站取下拖布。",
                "清潔並完全晾乾後再使用。",
                "當拖布磨損或清潔效果變差時予以更換。"
            ]
        },
        "cleaning_tray": {
            "steps": [
                "拆下基站底座或拖布清洗區部件。",
                "沖洗並擦除托盤區域的殘留污垢。",
                "清潔後將托盤裝回。"
            ],
            "notes": [
                "並留意及保養清水箱與污水箱。"
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "取出集塵盒，並拿出濾網。",
                "輕拍濾網以去除灰塵。",
                "若有沖洗，請待其完全乾燥後再裝回。"
            ]
        },
        "sensor": {
            "steps": [
                "使用乾布擦拭防墜感測器、防撞感測器與充電接觸點。"
            ]
        },
        "side_brush": {
            "steps": [
                "拆下邊刷。",
                "清除邊刷及其底座上的毛髮與碎屑。",
                "重新裝回，若已磨損則更換。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "捏住主滾刷護蓋的卡榫，取下護蓋。",
                "取出主滾刷。",
                "使用清潔工具或剪刀清除毛髮與碎屑。",
                "裝回滾刷與護蓋。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "從固定座取下拖布。",
                "清洗並晾乾後再使用。",
                "若拖布磨損或失去效果，請更換。"
            ],
            "notes": [
                "僅適用於具備拖地功能的 X8 混合型機型。"
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "按下集塵盒釋放鈕，取出集塵盒。",
                "取出濾網，輕拍去除鬆散的髒污。",
                "若該機型的指南允許，沖洗後待完全乾燥再裝回。"
            ]
        },
        "sensor": {
            "steps": [
                "使用乾布擦拭機器人與基站上的感測器及充電接觸點。"
            ]
        },
        "side_brush": {
            "steps": [
                "拔下邊刷。",
                "清除纏繞的毛髮與碎屑。",
                "重新裝回，若已磨損則更換。"
            ]
        },
        "rolling_brush": {
            "steps": [
                "取下主滾刷護蓋。",
                "取出滾刷。",
                "清除滾刷與軸承上纏繞的毛髮與碎屑。",
                "擦乾後裝回滾刷與護蓋。"
            ],
            "notes": [
                "SES 機型另具備自動斷髮功能，可減少保養需求。"
            ]
        },
        "mopping_cloth": {
            "steps": [
                "取下拖布或抹布。",
                "清潔並完全晾乾後再使用。",
                "當抹布磨損時予以更換。"
            ],
            "notes": [
                "僅適用於混合型機型。"
            ]
        }
    }
}

# --- ko guide (steps/notes; AI+manual-sourced, pending native review; freqs via guide-frequency-translations.json) ---
UPKEEP_GUIDE_TRANSLATIONS['ko'] = {
    "x10_pro_omni": {
        "filter": {
            "steps": [
                "상단 커버를 열고 먼지통을 분리하세요.",
                "먼지통에서 필터를 분리하세요.",
                "필터를 가볍게 두드려 먼지를 털어내고 먼지통을 비우세요.",
                "먼지통과 필터를 물로만 헹구세요.",
                "두 부품을 완전히 자연 건조한 후 다시 장착하세요."
            ],
            "notes": [
                "브러시, 뜨거운 물 또는 세제를 사용하지 마세요.",
                "필터는 3~6개월마다 교체하세요."
            ]
        },
        "sensor": {
            "steps": [
                "부드럽고 마른 천으로 센서와 카메라를 닦으세요.",
                "센서 관리 시 충전 접점도 함께 닦으세요."
            ],
            "notes": [
                "설명서에 센서 교체 주기는 명시되어 있지 않습니다."
            ]
        },
        "side_brush": {
            "steps": [
                "드라이버로 사이드 브러시를 분리하세요.",
                "감긴 머리카락이나 이물질을 풀어 제거하세요.",
                "브러시를 물로 헹군 후 완전히 자연 건조하세요.",
                "브러시가 마른 후 다시 장착하세요."
            ]
        },
        "rolling_brush": {
            "steps": [
                "브러시 커버의 잠금 탭을 풀고 커버를 들어 올려 분리하세요.",
                "롤링 브러시를 분리하세요.",
                "감긴 머리카락과 이물질을 잘라내어 제거하세요.",
                "브러시와 커버를 헹군 후 자연 건조하세요.",
                "브러시를 다시 장착하고 커버를 제자리에 끼워 넣으세요."
            ],
            "notes": [
                "브러시 커버도 3~6개월마다 또는 마모 시 교체해야 합니다."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "로봇청소기에서 물걸레 패드를 분리하세요.",
                "패드를 세척하고 완전히 건조한 후 재사용하세요.",
                "패드가 마모되거나 청소 성능이 떨어지면 교체하세요."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "옴니 스테이션에서 클리닝 트레이를 분리하세요.",
                "트레이를 물로 깨끗이 헹구세요.",
                "청소 후 트레이를 다시 장착하세요."
            ],
            "notes": [
                "오수 물통은 가득 차면 비우고 헹궈야 합니다."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "만능 바퀴에 감긴 머리카락이나 이물질이 있는지 점검하세요.",
                "이물질을 조심스럽게 제거하고 바퀴 부위를 깨끗이 닦으세요.",
                "다음 청소 전에 바퀴가 자유롭게 회전하는지 확인하세요."
            ],
            "notes": [
                "설명서에는 만능 바퀴 청소가 안내되어 있지만 별도의 교체 주기는 제공되지 않습니다."
            ]
        }
    },
    "s1_pro": {
        "filter": {
            "steps": [
                "먼지통 부위에서 고성능 필터를 분리하세요.",
                "먼지와 이물질을 가볍게 두드려 털어내세요.",
                "필터가 깨끗하고 마른 상태가 되면 다시 장착하거나 교체하세요."
            ],
            "notes": [
                "앱의 액세서리 관리 안내가 S1 Pro의 기본 공식 초기화 절차입니다."
            ]
        },
        "sensor": {
            "steps": [
                "부드럽고 마른 천으로 로봇청소기 센서를 닦으세요.",
                "센서를 관리하는 김에 충전 접점도 함께 청소하세요."
            ]
        },
        "side_brush": {
            "steps": [
                "사이드 브러시에 끼인 머리카락과 이물질이 있는지 점검하세요.",
                "베이스와 솔 주변에 쌓인 이물질을 제거하세요.",
                "솔이 휘었거나 손상된 경우 브러시를 교체하세요."
            ]
        },
        "rolling_brush": {
            "steps": [
                "롤링 브러시 커버를 분리하세요.",
                "브러시와 양쪽 끝 마개에 엉킨 머리카락이나 이물질이 있는지 확인하세요.",
                "다시 장착하기 전에 브러시를 깨끗이 청소하세요."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "롤러형 물걸레 또는 물걸레 접촉면을 분리하고 잔여물을 청소하세요.",
                "세척한 부품을 건조한 후 재사용하세요.",
                "마모가 눈에 띄거나 성능이 떨어지면 물걸레 관련 소모품을 교체하세요."
            ],
            "notes": [
                "S1 설명서는 분리형 트윈 패드가 아닌 롤러형 물걸레 방식을 기준으로 합니다."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "스테이션 부위에서 필터 트레이 또는 트레이 삽입부를 분리하세요.",
                "잔여물과 쌓인 이물질을 헹궈내세요.",
                "청소 후 다시 장착하세요."
            ],
            "notes": [
                "필요에 따라 청수/오수 물통과 오수 필터도 함께 청소하세요."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "만능 바퀴에 머리카락과 이물질이 있는지 점검하세요.",
                "쌓인 이물질을 제거하고 바퀴가 자유롭게 회전하는지 확인하세요."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "먼지통 또는 필터 칸을 분리하세요.",
                "필터를 꺼내 두드려 먼지를 털어내세요.",
                "설명서/앱 안내에서 허용하는 경우에만 세척하고, 완전히 건조한 후 다시 장착하세요."
            ],
            "notes": [
                "Omni C20 액세서리 안내는 주로 영상으로 제공됩니다."
            ]
        },
        "sensor": {
            "steps": [
                "깨끗하고 마른 천으로 로봇청소기와 스테이션의 센서와 충전 접점을 모두 닦으세요."
            ]
        },
        "side_brush": {
            "steps": [
                "사이드 브러시에 마모, 엉킴 또는 손상이 있는지 점검하세요.",
                "브러시와 베이스에 감긴 머리카락과 이물질을 제거하세요.",
                "솔이 휘었거나 빠진 경우 브러시를 교체하세요."
            ]
        },
        "rolling_brush": {
            "steps": [
                "롤링 브러시에 엉킨 머리카락이나 이물질이 있는지 점검하세요.",
                "청소 도구나 가위로 감긴 이물질을 잘라내세요.",
                "청소 후 다시 장착하세요."
            ],
            "notes": [
                "Pro-Detangle 빗은 수동 청소를 줄여주지만 완전히 없애지는 않습니다."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "로봇청소기 또는 스테이션에서 물걸레 패드를 분리하세요.",
                "패드를 세척하고 완전히 건조한 후 재사용하세요.",
                "패드가 마모되거나 청소 성능이 떨어지면 교체하세요."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "스테이션 베이스 또는 물걸레 세척부를 분리하세요.",
                "트레이 부위의 잔여물을 헹구고 닦아내세요.",
                "청소 후 트레이를 다시 장착하세요."
            ],
            "notes": [
                "청수 및 오수 물통도 함께 점검하고 관리하세요."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "먼지통을 분리하고 필터를 꺼내세요.",
                "필터를 가볍게 두드려 먼지를 털어내세요.",
                "물로 헹군 경우 완전히 건조한 후 다시 장착하세요."
            ]
        },
        "sensor": {
            "steps": [
                "마른 천으로 추락 방지 센서, 범퍼 센서, 충전 접점을 닦으세요."
            ]
        },
        "side_brush": {
            "steps": [
                "사이드 브러시를 분리하세요.",
                "브러시와 베이스에서 머리카락과 이물질을 제거하세요.",
                "다시 장착하거나 마모된 경우 교체하세요."
            ]
        },
        "rolling_brush": {
            "steps": [
                "메인 브러시 커버의 탭을 눌러 커버를 분리하세요.",
                "메인 브러시를 들어 올려 분리하세요.",
                "청소 도구나 가위로 머리카락과 이물질을 제거하세요.",
                "브러시와 커버를 다시 장착하세요."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "홀더에서 물걸레 패드를 분리하세요.",
                "패드를 세척하고 건조한 후 재사용하세요.",
                "마모되거나 성능이 떨어지면 교체하세요."
            ],
            "notes": [
                "물걸레 겸용 X8 모델에만 해당됩니다."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "먼지통 분리 버튼을 눌러 먼지통을 분리하세요.",
                "필터를 분리하고 두드려 이물질을 털어내세요.",
                "해당 모델 안내에서 허용하는 경우 물로 헹구고 완전히 건조한 후 다시 장착하세요."
            ]
        },
        "sensor": {
            "steps": [
                "마른 천으로 로봇청소기와 베이스의 센서와 충전 접점을 닦으세요."
            ]
        },
        "side_brush": {
            "steps": [
                "사이드 브러시를 당겨 분리하세요.",
                "엉킨 머리카락과 이물질을 제거하세요.",
                "다시 장착하거나 마모된 경우 교체하세요."
            ]
        },
        "rolling_brush": {
            "steps": [
                "메인 브러시 커버를 분리하세요.",
                "롤링 브러시를 들어 올려 분리하세요.",
                "브러시와 베어링에 감긴 머리카락과 이물질을 청소하세요.",
                "물기를 닦아낸 후 브러시와 커버를 다시 장착하세요."
            ],
            "notes": [
                "SES 모델은 유지 관리를 줄이기 위해 자동 머리카락 절단 기능도 사용합니다."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "물걸레 패드 또는 천을 분리하세요.",
                "완전히 세척하고 건조한 후 재사용하세요.",
                "천이 마모되면 교체하세요."
            ],
            "notes": [
                "물걸레 겸용 모델에만 해당됩니다."
            ]
        }
    }
}


# --- guide backfill: non-x10 families merged 2026-07-25 ---
UPKEEP_GUIDE_TRANSLATIONS['de'].update({
    "s1_pro": {
        "filter": {
            "steps": [
                "Nehmen Sie den Hochleistungsfilter aus dem Bereich des Staubbehälters heraus.",
                "Klopfen Sie Staub und Schmutz vorsichtig ab.",
                "Setzen Sie den Filter wieder ein oder ersetzen Sie ihn, sobald er sauber und trocken ist."
            ],
            "notes": [
                "Die Zubehördienste-Anleitung in der App ist der primäre offizielle Reset-Ablauf für den S1 Pro."
            ]
        },
        "sensor": {
            "steps": [
                "Wischen Sie die Sensoren des Roboters mit einem weichen, trockenen Tuch ab.",
                "Reinigen Sie bei der Wartung der Sensoren auch die Ladekontakte."
            ]
        },
        "side_brush": {
            "steps": [
                "Überprüfen Sie die Seitenbürste auf verfangene Haare und Schmutz.",
                "Entfernen Sie Ablagerungen rund um die Basis und die Borsten.",
                "Ersetzen Sie die Bürste, wenn die Borsten verbogen oder beschädigt sind."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Entfernen Sie den Bürstenschutz der Rollbürste.",
                "Prüfen Sie die Bürste und beide Endkappen auf verhedderte Haare oder Schmutz.",
                "Reinigen Sie die Bürste gründlich, bevor Sie sie wieder einsetzen."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Entfernen Sie den Rollmopp bzw. die Mopp-Kontaktflächen und entfernen Sie Rückstände.",
                "Lassen Sie die gereinigten Teile vor der Wiederverwendung trocknen.",
                "Ersetzen Sie das Mopp-Verbrauchsteil, wenn Verschleiß sichtbar wird oder die Leistung nachlässt."
            ],
            "notes": [
                "Die S1-Dokumentation ist auf den Rollmopp ausgerichtet und nicht auf abnehmbare Doppel-Pads."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Entnehmen Sie die Filterschale bzw. den Schaleneinsatz aus dem Stationsbereich.",
                "Spülen Sie Rückstände und Ablagerungen ab.",
                "Setzen Sie sie nach der Reinigung wieder ein."
            ],
            "notes": [
                "Reinigen Sie bei Bedarf auch den Frisch- und Schmutzwassertank sowie den Schmutzwasserfilter."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "Überprüfen Sie das Lenkrad auf Haare und Schmutz.",
                "Entfernen Sie Ablagerungen und stellen Sie sicher, dass sich das Rad frei dreht."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Nehmen Sie den Staubbehälter bzw. das Filterfach heraus.",
                "Nehmen Sie den Filter heraus und klopfen Sie Staub ab.",
                "Waschen Sie ihn nur, wenn die Anleitung/App dies erlaubt, und lassen Sie ihn vor dem Wiedereinsetzen vollständig trocknen."
            ],
            "notes": [
                "Die Zubehör-Anleitung des Omni C20 ist überwiegend videobasiert."
            ]
        },
        "sensor": {
            "steps": [
                "Wischen Sie die Sensoren und Ladekontakte an Roboter und Station mit einem sauberen, trockenen Tuch ab."
            ]
        },
        "side_brush": {
            "steps": [
                "Überprüfen Sie die Seitenbürste auf Verschleiß, Verhedderungen oder Beschädigungen.",
                "Entfernen Sie umwickelte Haare und Schmutz von der Bürste und der Basis.",
                "Ersetzen Sie die Bürste, wenn Borsten verbogen sind oder fehlen."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Überprüfen Sie die Rollbürste auf verhedderte Haare oder Schmutz.",
                "Schneiden Sie umwickeltes Material mit dem Reinigungswerkzeug oder einer Schere ab.",
                "Setzen Sie sie nach der Reinigung wieder ein."
            ],
            "notes": [
                "Der Pro-Detangle-Kamm reduziert die manuelle Reinigung, macht sie aber nicht überflüssig."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Entfernen Sie die Mopp-Pads vom Roboter oder von der Station.",
                "Reinigen und trocknen Sie sie vor der Wiederverwendung vollständig.",
                "Ersetzen Sie die Pads, wenn sie abgenutzt sind oder nicht mehr wirksam reinigen."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Nehmen Sie die Stationsbasis bzw. das Bauteil des Moppwaschbereichs ab.",
                "Spülen und wischen Sie Rückstände aus dem Schalenbereich ab.",
                "Setzen Sie die Schale nach der Reinigung wieder ein."
            ],
            "notes": [
                "Überwachen und warten Sie auch den Frisch- und Schmutzwassertank."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Entnehmen Sie den Staubbehälter und nehmen Sie den Filter heraus.",
                "Klopfen Sie den Filter vorsichtig ab, um Staub zu entfernen.",
                "Falls Sie ihn abgespült haben, lassen Sie ihn vor dem Wiedereinsetzen vollständig trocknen."
            ]
        },
        "sensor": {
            "steps": [
                "Wischen Sie die Absturzsensoren, die Stoßsensoren und die Ladekontakte mit einem trockenen Tuch ab."
            ]
        },
        "side_brush": {
            "steps": [
                "Entfernen Sie die Seitenbürste.",
                "Entfernen Sie Haare und Schmutz von der Bürste und ihrer Basis.",
                "Bringen Sie sie wieder an oder ersetzen Sie sie bei Abnutzung."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Drücken Sie die Laschen des Hauptbürstenschutzes zusammen und entfernen Sie den Schutz.",
                "Heben Sie die Hauptbürste heraus.",
                "Entfernen Sie Haare und Schmutz mit dem Reinigungswerkzeug oder einer Schere.",
                "Setzen Sie die Bürste und den Schutz wieder ein."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Entfernen Sie das Wischpad aus der Halterung.",
                "Waschen und trocknen Sie es vor der Wiederverwendung.",
                "Ersetzen Sie es, wenn es abgenutzt oder unwirksam wird."
            ],
            "notes": [
                "Gilt nur für Hybrid-/wischfähige X8-Modelle."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Drücken Sie die Entriegelungstaste des Staubbehälters und entnehmen Sie den Staubbehälter.",
                "Nehmen Sie den Filter heraus und klopfen Sie losen Schmutz ab.",
                "Sofern die Anleitung Ihres Modells dies erlaubt, spülen Sie ihn ab und lassen Sie ihn vor dem Wiedereinsetzen vollständig trocknen."
            ]
        },
        "sensor": {
            "steps": [
                "Wischen Sie die Sensoren und Ladekontakte am Roboter und an der Basis mit einem trockenen Tuch ab."
            ]
        },
        "side_brush": {
            "steps": [
                "Ziehen Sie die Seitenbürste ab.",
                "Entfernen Sie verhedderte Haare und Schmutz.",
                "Bringen Sie sie wieder an oder ersetzen Sie sie bei Abnutzung."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Entfernen Sie die Abdeckung der Hauptbürste.",
                "Heben Sie die Walzenbürste heraus.",
                "Entfernen Sie umwickelte Haare und Schmutz von der Bürste und den Lagern.",
                "Wischen Sie sie trocken und setzen Sie die Bürste und den Bürstenschutz wieder ein."
            ],
            "notes": [
                "SES-Modelle nutzen zusätzlich ein automatisches Haarschneidesystem, um den Wartungsaufwand zu reduzieren."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Entfernen Sie das Wischpad bzw. das Wischtuch.",
                "Reinigen und trocknen Sie es vor der Wiederverwendung vollständig.",
                "Ersetzen Sie das Wischtuch bei Abnutzung."
            ],
            "notes": [
                "Gilt nur für Hybrid-Varianten."
            ]
        }
    }
})
UPKEEP_GUIDE_TRANSLATIONS['es'].update({
    "s1_pro": {
        "filter": {
            "steps": [
                "Retire el filtro de alto rendimiento de la zona del depósito de polvo.",
                "Sacúdalo suavemente para eliminar el polvo y los residuos.",
                "Vuelva a instalar o reemplace el filtro una vez que esté limpio y seco."
            ],
            "notes": [
                "La guía de servicio de accesorios en la app es el flujo oficial de restablecimiento principal para el S1 Pro."
            ]
        },
        "sensor": {
            "steps": [
                "Limpie los sensores del robot con un paño suave y seco.",
                "Limpie también los contactos de carga al hacer el mantenimiento de los sensores."
            ]
        },
        "side_brush": {
            "steps": [
                "Inspeccione el cepillo lateral en busca de cabello y residuos atrapados.",
                "Retire la acumulación alrededor de la base y las cerdas.",
                "Reemplace el cepillo si las cerdas están dobladas o dañadas."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Retire la protección del cepillo giratorio.",
                "Revise el cepillo y las tapas de ambos extremos en busca de cabello enredado o residuos.",
                "Limpie el cepillo a fondo antes de volver a instalarlo."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retire la mopa de rodillo o las superficies de contacto de la mopa y limpie los residuos.",
                "Deje secar las piezas limpias antes de reutilizarlas.",
                "Reemplace el consumible de fregado cuando el desgaste sea visible o el rendimiento disminuya."
            ],
            "notes": [
                "La documentación del S1 está orientada a la mopa de rodillo, no a la terminología de doble almohadilla desmontable."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Retire la bandeja del filtro o el inserto de la bandeja de la zona de la estación.",
                "Enjuague los residuos y la acumulación.",
                "Vuelva a instalarla después de limpiarla."
            ],
            "notes": [
                "Limpie también los depósitos de agua limpia y sucia y el filtro de agua sucia según sea necesario."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "Inspeccione la rueda giratoria en busca de cabello y residuos.",
                "Retire la acumulación y confirme que la rueda gira libremente."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Retire el depósito de polvo o el compartimento del filtro.",
                "Saque el filtro y sacúdalo para eliminar el polvo.",
                "Lávelo solo si la guía del manual/app lo permite y luego séquelo por completo antes de volver a instalarlo."
            ],
            "notes": [
                "La guía de accesorios del Omni C20 se basa principalmente en vídeos."
            ]
        },
        "sensor": {
            "steps": [
                "Use un paño limpio y seco para limpiar los sensores y los contactos de carga tanto del robot como de la estación."
            ]
        },
        "side_brush": {
            "steps": [
                "Inspeccione el cepillo lateral en busca de desgaste, enredos o daños.",
                "Retire el cabello enrollado y los residuos del cepillo y la base.",
                "Reemplace el cepillo si las cerdas están dobladas o faltan."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Inspeccione el cepillo giratorio en busca de cabello enredado o residuos.",
                "Use la herramienta de limpieza o unas tijeras para cortar el material enrollado.",
                "Vuelva a instalarlo después de limpiarlo."
            ],
            "notes": [
                "El peine antienredos Pro-Detangle reduce la limpieza manual, pero no la elimina."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retire las almohadillas de fregado del robot o de la estación.",
                "Límpielas y séquelas por completo antes de reutilizarlas.",
                "Reemplace las almohadillas cuando estén desgastadas o ya no limpien eficazmente."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Desmonte la base de la estación o el componente de la zona de lavado de la mopa.",
                "Enjuague y limpie los residuos de la zona de la bandeja.",
                "Vuelva a instalar la bandeja después de limpiarla."
            ],
            "notes": [
                "Vigile y realice el mantenimiento de los depósitos de agua limpia y sucia."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Retire el depósito de polvo y saque el filtro.",
                "Sacúdalo suavemente para eliminar el polvo.",
                "Si lo enjuaga, déjelo secar por completo antes de volver a instalarlo."
            ]
        },
        "sensor": {
            "steps": [
                "Limpie los sensores de caída, los sensores del parachoques y los contactos de carga con un paño seco."
            ]
        },
        "side_brush": {
            "steps": [
                "Retire el cepillo lateral.",
                "Retire el cabello y los residuos del cepillo y de su base.",
                "Vuelva a colocarlo o reemplácelo si está desgastado."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Apriete las pestañas de la protección del cepillo giratorio y retire la protección.",
                "Levante para sacar el cepillo giratorio.",
                "Use la herramienta de limpieza o unas tijeras para retirar el cabello y los residuos.",
                "Vuelva a instalar el cepillo y la protección."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retire la almohadilla de fregado del soporte.",
                "Lávela y séquela antes de reutilizarla.",
                "Reemplácela si se desgasta o pierde eficacia."
            ],
            "notes": [
                "Solo se aplica a los modelos X8 híbridos o con capacidad de fregado."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Presione el botón de liberación del depósito de polvo y retire el depósito.",
                "Saque el filtro y sacúdalo para eliminar la suciedad suelta.",
                "Si la guía de su modelo específico lo permite, enjuáguelo y séquelo por completo antes de volver a instalarlo."
            ]
        },
        "sensor": {
            "steps": [
                "Use un paño seco para limpiar los sensores y los contactos de carga del robot y de la base."
            ]
        },
        "side_brush": {
            "steps": [
                "Tire del cepillo lateral para extraerlo.",
                "Retire el cabello enredado y los residuos.",
                "Vuelva a colocarlo o reemplácelo si está desgastado."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Retire la cubierta del cepillo giratorio.",
                "Levante para sacar el cepillo giratorio.",
                "Limpie el cabello enrollado y los residuos del cepillo y de los cojinetes.",
                "Séquelo y vuelva a instalar el cepillo y la protección."
            ],
            "notes": [
                "Los modelos SES también utilizan el corte automático de cabello para reducir el mantenimiento."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retire la almohadilla o el paño de fregado.",
                "Límpielo y séquelo por completo antes de reutilizarlo.",
                "Reemplace el paño cuando esté desgastado."
            ],
            "notes": [
                "Solo se aplica a las variantes híbridas."
            ]
        }
    }
})
UPKEEP_GUIDE_TRANSLATIONS['fr'].update({
    "s1_pro": {
        "filter": {
            "steps": [
                "Retirez le filtre haute performance de la zone du bac à poussière.",
                "Tapotez délicatement pour faire tomber la poussière et les débris.",
                "Réinstallez ou remplacez le filtre une fois qu'il est propre et sec."
            ],
            "notes": [
                "Les instructions d'entretien des accessoires dans l'application constituent la procédure de réinitialisation officielle principale pour le S1 Pro."
            ]
        },
        "sensor": {
            "steps": [
                "Essuyez les capteurs du robot avec un chiffon doux et sec.",
                "Nettoyez également les contacts de charge pendant l'entretien des capteurs."
            ]
        },
        "side_brush": {
            "steps": [
                "Vérifiez que la brosse latérale ne retient ni cheveux ni débris.",
                "Retirez l'accumulation autour de la base et des poils.",
                "Remplacez la brosse si les poils sont tordus ou endommagés."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Retirez le protège-brosse rotative.",
                "Vérifiez la présence de cheveux emmêlés ou de débris sur la brosse et sur les deux embouts.",
                "Nettoyez soigneusement la brosse avant de la réinstaller."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retirez la serpillière rotative ou les surfaces de contact de la serpillière et éliminez les résidus.",
                "Laissez sécher les pièces nettoyées avant de les réutiliser.",
                "Remplacez le consommable de serpillière lorsque l'usure devient visible ou que les performances diminuent."
            ],
            "notes": [
                "La documentation du S1 est axée sur la serpillière rotative plutôt que sur des tampons jumeaux amovibles."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Retirez le plateau du filtre ou le bac amovible de la zone de la station.",
                "Rincez pour éliminer les résidus et l'accumulation.",
                "Réinstallez-le après le nettoyage."
            ],
            "notes": [
                "Nettoyez également les réservoirs d'eau propre et d'eau sale ainsi que le filtre d'eau sale selon les besoins."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "Vérifiez que la roue pivotante ne contient ni cheveux ni débris.",
                "Retirez l'accumulation et vérifiez que la roue tourne librement."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Retirez le bac à poussière ou le compartiment du filtre.",
                "Sortez le filtre et tapotez pour en faire tomber la poussière.",
                "Lavez-le uniquement si les instructions du manuel/de l'application l'autorisent, puis séchez-le complètement avant de le réinstaller."
            ],
            "notes": [
                "Le guide des accessoires de l'Omni C20 est principalement sous forme de vidéos."
            ]
        },
        "sensor": {
            "steps": [
                "Utilisez un chiffon propre et sec pour essuyer les capteurs et les contacts de charge, sur le robot comme sur la station."
            ]
        },
        "side_brush": {
            "steps": [
                "Vérifiez que la brosse latérale ne présente ni usure, ni emmêlement, ni dommage.",
                "Retirez les cheveux enroulés et les débris de la brosse et de sa base.",
                "Remplacez la brosse si les poils sont tordus ou manquants."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Vérifiez la présence de cheveux emmêlés ou de débris sur la brosse rotative.",
                "Utilisez l'outil de nettoyage ou des ciseaux pour couper les matières enroulées.",
                "Réinstallez-la après le nettoyage."
            ],
            "notes": [
                "Le peigne anti-emmêlement Pro-Detangle réduit le nettoyage manuel sans l'éliminer."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retirez les tampons de serpillière du robot ou de la station.",
                "Nettoyez-les et séchez-les complètement avant de les réutiliser.",
                "Remplacez les tampons lorsqu'ils sont usés ou ne nettoient plus efficacement."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Détachez la base de la station ou le composant de la zone de lavage de la serpillière.",
                "Rincez et essuyez les résidus de la zone du bac.",
                "Réinstallez le bac après le nettoyage."
            ],
            "notes": [
                "Surveillez et entretenez également les réservoirs d'eau propre et d'eau sale."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Retirez le bac à poussière et sortez le filtre.",
                "Tapotez délicatement le filtre pour en retirer la poussière.",
                "S'il a été rincé, laissez-le sécher complètement avant de le réinstaller."
            ]
        },
        "sensor": {
            "steps": [
                "Essuyez les capteurs anti-chute, les capteurs du pare-chocs et les contacts de charge avec un chiffon sec."
            ]
        },
        "side_brush": {
            "steps": [
                "Retirez la brosse latérale.",
                "Éliminez les cheveux et les débris de la brosse et de sa base.",
                "Refixez-la ou remplacez-la si elle est usée."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Pincez les languettes du protège-brosse rotative et retirez le protège-brosse.",
                "Soulevez la brosse rotative pour la retirer.",
                "Utilisez l'outil de nettoyage ou des ciseaux pour retirer les cheveux et les débris.",
                "Réinstallez la brosse et le protège-brosse."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retirez le tampon de serpillière de son support.",
                "Lavez-le et séchez-le avant de le réutiliser.",
                "Remplacez-le s'il devient usé ou inefficace."
            ],
            "notes": [
                "S'applique uniquement aux modèles X8 hybrides / équipés d'une serpillière."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Appuyez sur le bouton de déverrouillage du bac à poussière et retirez le bac.",
                "Retirez le filtre et tapotez pour en faire tomber la saleté.",
                "Si le guide de votre modèle l'autorise, rincez-le et séchez-le complètement avant de le réinstaller."
            ]
        },
        "sensor": {
            "steps": [
                "Utilisez un chiffon sec pour essuyer les capteurs et les contacts de charge du robot et de la base."
            ]
        },
        "side_brush": {
            "steps": [
                "Retirez la brosse latérale en tirant.",
                "Retirez les cheveux emmêlés et les débris.",
                "Refixez-la ou remplacez-la si elle est usée."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Retirez le cache de la brosse rotative.",
                "Soulevez la brosse rotative pour la retirer.",
                "Nettoyez les cheveux enroulés et les débris sur la brosse et les paliers.",
                "Essuyez pour sécher, puis réinstallez la brosse et le protège-brosse."
            ],
            "notes": [
                "Les modèles SES utilisent aussi une découpe automatique des poils pour réduire l'entretien."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retirez le tampon de serpillière ou le chiffon.",
                "Nettoyez-le et séchez-le complètement avant de le réutiliser.",
                "Remplacez le chiffon lorsqu'il est usé."
            ],
            "notes": [
                "S'applique uniquement aux variantes hybrides."
            ]
        }
    }
})
UPKEEP_GUIDE_TRANSLATIONS['it'].update({
    "s1_pro": {
        "filter": {
            "steps": [
                "Rimuovere il filtro ad alte prestazioni dall'area del contenitore della polvere.",
                "Picchiettare delicatamente per rimuovere polvere e detriti.",
                "Reinstallare o sostituire il filtro una volta pulito e asciutto."
            ],
            "notes": [
                "La guida al servizio degli accessori nell'app è la procedura di reset ufficiale principale per l'S1 Pro."
            ]
        },
        "sensor": {
            "steps": [
                "Pulire i sensori del robot con un panno morbido e asciutto.",
                "Pulire anche i contatti di ricarica durante la manutenzione dei sensori."
            ]
        },
        "side_brush": {
            "steps": [
                "Ispezionare la spazzola laterale per capelli e detriti intrappolati.",
                "Rimuovere gli accumuli intorno alla base e alle setole.",
                "Sostituire la spazzola se le setole sono piegate o danneggiate."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Rimuovere la protezione della spazzola rotante.",
                "Controllare la spazzola ed entrambi i cappucci terminali per capelli aggrovigliati o detriti.",
                "Pulire accuratamente la spazzola prima di reinstallarla."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Rimuovere il mop rotante o le superfici di contatto del mop ed eliminare i residui.",
                "Lasciare asciugare le parti pulite prima del riutilizzo.",
                "Sostituire il materiale di consumo del mop quando l'usura diventa visibile o le prestazioni calano."
            ],
            "notes": [
                "La documentazione dell'S1 è orientata al mop rotante anziché a due panni staccabili."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Rimuovere il vassoio del filtro o l'inserto del vassoio dall'area della stazione.",
                "Sciacquare via residui e accumuli.",
                "Reinstallare dopo la pulizia."
            ],
            "notes": [
                "Pulire anche i serbatoi dell'acqua pulita e sporca e il filtro dell'acqua sporca secondo necessità."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "Ispezionare la ruota piroettante per capelli e detriti.",
                "Rimuovere gli accumuli e verificare che la ruota giri liberamente."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Rimuovere il contenitore della polvere o il vano del filtro.",
                "Estrarre il filtro e picchiettare per rimuovere la polvere.",
                "Lavare solo se la guida del manuale o dell'app lo consente, poi asciugare completamente prima di reinstallare."
            ],
            "notes": [
                "La guida agli accessori dell'Omni C20 è basata principalmente su video."
            ]
        },
        "sensor": {
            "steps": [
                "Usare un panno pulito e asciutto per pulire i sensori e i contatti di ricarica sia sul robot sia sulla stazione."
            ]
        },
        "side_brush": {
            "steps": [
                "Ispezionare la spazzola laterale per usura, aggrovigliamenti o danni.",
                "Rimuovere capelli e detriti avvolti dalla spazzola e dalla base.",
                "Sostituire la spazzola se le setole sono piegate o mancanti."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Ispezionare la spazzola rotante per capelli aggrovigliati o detriti.",
                "Usare lo strumento di pulizia o delle forbici per tagliare via il materiale avvolto.",
                "Reinstallare dopo la pulizia."
            ],
            "notes": [
                "Il pettine Pro-Detangle riduce ma non elimina la pulizia manuale."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Rimuovere i panni per lavaggio dal robot o dalla stazione.",
                "Pulirli e asciugarli completamente prima del riutilizzo.",
                "Sostituire i panni quando sono usurati o non puliscono più efficacemente."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Staccare la base della stazione o il componente dell'area di lavaggio del mop.",
                "Sciacquare e rimuovere i residui dall'area del vassoio.",
                "Reinstallare il vassoio dopo la pulizia."
            ],
            "notes": [
                "Monitorare e sottoporre a manutenzione anche i serbatoi dell'acqua pulita e sporca."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Rimuovere il contenitore della polvere ed estrarre il filtro.",
                "Picchiettare delicatamente il filtro per rimuovere la polvere.",
                "Se sciacquato, lasciarlo asciugare completamente prima di reinstallarlo."
            ]
        },
        "sensor": {
            "steps": [
                "Pulire i sensori anticaduta, i sensori del paraurti e i contatti di ricarica con un panno asciutto."
            ]
        },
        "side_brush": {
            "steps": [
                "Rimuovere la spazzola laterale.",
                "Eliminare capelli e detriti dalla spazzola e dalla sua base.",
                "Rimontare o sostituire se usurata."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Premere le linguette della protezione della spazzola rotante e rimuovere la protezione.",
                "Sollevare ed estrarre la spazzola rotante.",
                "Usare lo strumento di pulizia o delle forbici per rimuovere capelli e detriti.",
                "Reinstallare la spazzola e la protezione."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Rimuovere il panno per lavaggio dal supporto.",
                "Lavarlo e asciugarlo prima del riutilizzo.",
                "Sostituirlo se diventa usurato o inefficace."
            ],
            "notes": [
                "Si applica solo ai modelli X8 ibridi o con funzione mop."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Premere il pulsante di rilascio del contenitore della polvere e rimuovere il contenitore della polvere.",
                "Rimuovere il filtro e picchiettare per eliminare lo sporco residuo.",
                "Se consentito dalla guida specifica del modello, sciacquare e asciugare completamente prima di reinstallare."
            ]
        },
        "sensor": {
            "steps": [
                "Usare un panno asciutto per pulire i sensori e i contatti di ricarica sul robot e sulla base."
            ]
        },
        "side_brush": {
            "steps": [
                "Staccare la spazzola laterale.",
                "Rimuovere capelli aggrovigliati e detriti.",
                "Rimontare o sostituire se usurata."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Rimuovere la copertura della spazzola rotante.",
                "Sollevare ed estrarre la spazzola rotante.",
                "Rimuovere capelli e detriti avvolti dalla spazzola e dai cuscinetti.",
                "Asciugare con un panno e reinstallare la spazzola e la protezione."
            ],
            "notes": [
                "I modelli SES utilizzano anche il taglio automatico dei capelli per ridurre la manutenzione."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Rimuovere il tampone o il panno per lavaggio.",
                "Pulirlo e asciugarlo completamente prima del riutilizzo.",
                "Sostituire il panno quando è usurato."
            ],
            "notes": [
                "Si applica solo alle varianti ibride."
            ]
        }
    }
})
UPKEEP_GUIDE_TRANSLATIONS['nl'].update({
    "s1_pro": {
        "filter": {
            "steps": [
                "Haal het hoogwaardige filter uit het stofbakgedeelte.",
                "Klop stof en vuil er voorzichtig af.",
                "Plaats het filter terug of vervang het zodra het schoon en droog is."
            ],
            "notes": [
                "De accessoire-servicebegeleiding in de app is de belangrijkste officiële resetprocedure voor de S1 Pro."
            ]
        },
        "sensor": {
            "steps": [
                "Veeg de sensoren van de robot schoon met een zachte, droge doek.",
                "Reinig ook de laadcontacten terwijl u de sensoren onderhoudt."
            ]
        },
        "side_brush": {
            "steps": [
                "Controleer de zijborstel op vastzittende haren en vuil.",
                "Verwijder opgehoopt vuil rond de voet en de borstelharen.",
                "Vervang de borstel als de borstelharen verbogen of beschadigd zijn."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Verwijder de borstelbeschermer van de rolborstel.",
                "Controleer de borstel en beide eindkapjes op verwikkelde haren of vuil.",
                "Reinig de borstel grondig voordat u hem terugplaatst."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Verwijder de rollende dweil of de dweilcontactvlakken en verwijder alle resten.",
                "Laat de gereinigde onderdelen drogen voordat u ze opnieuw gebruikt.",
                "Vervang het dweilonderdeel wanneer er zichtbare slijtage optreedt of de prestaties afnemen."
            ],
            "notes": [
                "De S1-documentatie is gericht op de rollende dweil in plaats van op verwijderbare dubbele dweildoeken."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Verwijder de filterlade of het inzetstuk van de reinigingsbak uit het stationgedeelte.",
                "Spoel resten en opgehoopt vuil weg.",
                "Plaats de bak na het reinigen terug."
            ],
            "notes": [
                "Reinig indien nodig ook de schoonwater- en vuilwatertank en het vuilwaterfilter."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "Controleer het zwenkwiel op haren en vuil.",
                "Verwijder opgehoopt vuil en controleer of het wiel vrij draait."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Haal de stofbak of het filtervak eruit.",
                "Neem het filter eruit en klop het stof eraf.",
                "Was het alleen als de handleiding/app dit toestaat en laat het daarna volledig drogen voordat u het terugplaatst."
            ],
            "notes": [
                "De accessoiregids van de Omni C20 is voornamelijk videogebaseerd."
            ]
        },
        "sensor": {
            "steps": [
                "Veeg met een schone, droge doek de sensoren en laadcontacten op zowel de robot als het station schoon."
            ]
        },
        "side_brush": {
            "steps": [
                "Controleer de zijborstel op slijtage, verwikkelde haren of beschadiging.",
                "Verwijder vastgewikkelde haren en vuil van de borstel en de voet.",
                "Vervang de borstel als de borstelharen verbogen zijn of ontbreken."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Controleer de rolborstel op verwikkelde haren of vuil.",
                "Gebruik het schoonmaakgereedschap of een schaar om vastgewikkeld materiaal weg te knippen.",
                "Plaats de borstel na het reinigen terug."
            ],
            "notes": [
                "De Pro-Detangle-kam vermindert het handmatig reinigen, maar maakt het niet overbodig."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Verwijder de dweildoeken van de robot of het station.",
                "Reinig ze en laat ze volledig drogen voordat u ze opnieuw gebruikt.",
                "Vervang de dweildoeken wanneer ze versleten zijn of niet meer effectief reinigen."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Maak de stationbasis of het wasgedeelte voor de dweil los.",
                "Spoel en veeg resten uit het bakgedeelte.",
                "Plaats de bak na het reinigen terug."
            ],
            "notes": [
                "Houd ook de schoonwater- en vuilwatertank in de gaten en onderhoud ze."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Haal de stofbak eruit en neem het filter eruit.",
                "Tik voorzichtig op het filter om stof te verwijderen.",
                "Als u het afspoelt, laat het dan volledig drogen voordat u het terugplaatst."
            ]
        },
        "sensor": {
            "steps": [
                "Veeg de valsensoren, bumpersensoren en laadcontacten schoon met een droge doek."
            ]
        },
        "side_brush": {
            "steps": [
                "Verwijder de zijborstel.",
                "Verwijder haren en vuil van de borstel en de voet.",
                "Bevestig hem opnieuw of vervang hem bij slijtage."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Knijp de lipjes van de borstelbeschermer samen en verwijder de beschermer.",
                "Til de rolborstel eruit.",
                "Gebruik het schoonmaakgereedschap of een schaar om haren en vuil te verwijderen.",
                "Plaats de borstel en de beschermer terug."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Haal de dweildoek uit de houder.",
                "Was en droog hem voordat u hem opnieuw gebruikt.",
                "Vervang hem als hij versleten of niet meer effectief is."
            ],
            "notes": [
                "Geldt alleen voor hybride/dweilgeschikte X8-modellen."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Druk op de ontgrendelingsknop van de stofbak en verwijder de stofbak.",
                "Verwijder het filter en klop het losse vuil eraf.",
                "Als de handleiding van uw specifieke model dit toestaat, spoel het dan af en laat het volledig drogen voordat u het terugplaatst."
            ]
        },
        "sensor": {
            "steps": [
                "Veeg met een droge doek de sensoren en laadcontacten op de robot en het basisstation schoon."
            ]
        },
        "side_brush": {
            "steps": [
                "Trek de zijborstel eraf.",
                "Verwijder verwikkelde haren en vuil.",
                "Bevestig hem opnieuw of vervang hem bij slijtage."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Verwijder de borstelbeschermer van de rolborstel.",
                "Til de rolborstel eruit.",
                "Verwijder vastgewikkelde haren en vuil van de borstel en de lagers.",
                "Veeg hem droog en plaats de borstel en de beschermer terug."
            ],
            "notes": [
                "SES-modellen knippen haar ook automatisch af om het onderhoud te verminderen."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Verwijder de dweildoek.",
                "Reinig hem en laat hem volledig drogen voordat u hem opnieuw gebruikt.",
                "Vervang de dweildoek bij slijtage."
            ],
            "notes": [
                "Geldt alleen voor hybride varianten."
            ]
        }
    }
})
UPKEEP_GUIDE_TRANSLATIONS['pt'].update({
    "s1_pro": {
        "filter": {
            "steps": [
                "Retire o filtro de alto desempenho da zona do depósito de pó.",
                "Sacuda o pó e os detritos com cuidado.",
                "Volte a instalar ou substitua o filtro quando estiver limpo e seco."
            ],
            "notes": [
                "As orientações de manutenção de acessórios na aplicação são o fluxo de reposição oficial principal para o S1 Pro."
            ]
        },
        "sensor": {
            "steps": [
                "Limpe os sensores do robô com um pano macio e seco.",
                "Limpe também os contactos de carregamento ao fazer a manutenção dos sensores."
            ]
        },
        "side_brush": {
            "steps": [
                "Inspecione a escova lateral em busca de cabelos e detritos presos.",
                "Remova a acumulação à volta da base e das cerdas.",
                "Substitua a escova se as cerdas estiverem dobradas ou danificadas."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Retire a proteção da escova rotativa.",
                "Verifique a escova e ambas as tampas das extremidades em busca de cabelos enrolados ou detritos.",
                "Limpe bem a escova antes de a voltar a instalar."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retire a mopa rotativa ou as superfícies de contacto da mopa e limpe os resíduos.",
                "Deixe as peças limpas secar antes de as reutilizar.",
                "Substitua o consumível da mopa quando o desgaste for visível ou o desempenho diminuir."
            ],
            "notes": [
                "A documentação do S1 é orientada para a mopa rotativa e não para a terminologia de almofada dupla destacável."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Retire a bandeja do filtro ou o respetivo encaixe da zona da base.",
                "Enxague os resíduos e a acumulação.",
                "Volte a instalar após a limpeza."
            ],
            "notes": [
                "Limpe também os depósitos de água limpa e suja e o filtro de água suja conforme necessário."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "Inspecione a roda giratória em busca de cabelos e detritos.",
                "Remova a acumulação e confirme que a roda roda livremente."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Retire o depósito de pó ou o compartimento do filtro.",
                "Retire o filtro e sacuda o pó.",
                "Lave apenas se o manual/aplicação o permitir e, em seguida, seque completamente antes de voltar a instalar."
            ],
            "notes": [
                "O guia de acessórios do Omni C20 é essencialmente em vídeo."
            ]
        },
        "sensor": {
            "steps": [
                "Use um pano limpo e seco para limpar os sensores e os contactos de carregamento tanto no robô como na base."
            ]
        },
        "side_brush": {
            "steps": [
                "Inspecione a escova lateral em busca de desgaste, emaranhados ou danos.",
                "Remova os cabelos enrolados e os detritos da escova e da base.",
                "Substitua a escova se as cerdas estiverem dobradas ou em falta."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Inspecione a escova rotativa em busca de cabelos enrolados ou detritos.",
                "Use a ferramenta de limpeza ou uma tesoura para cortar o material enrolado.",
                "Volte a instalar após a limpeza."
            ],
            "notes": [
                "O Pente Pro-Detangle reduz, mas não elimina, a limpeza manual."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retire os panos de limpeza do robô ou da base.",
                "Limpe-os e seque-os completamente antes de os reutilizar.",
                "Substitua os panos quando estiverem gastos ou já não limparem eficazmente."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Solte a base da estação ou o componente da zona de lavagem da mopa.",
                "Enxague e limpe os resíduos da zona da bandeja.",
                "Volte a instalar a bandeja após a limpeza."
            ],
            "notes": [
                "Monitorize e faça também a manutenção dos depósitos de água limpa e suja."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Retire o depósito de pó e remova o filtro.",
                "Bata levemente no filtro para remover o pó.",
                "Se o enxaguar, deixe-o secar completamente antes de voltar a instalar."
            ]
        },
        "sensor": {
            "steps": [
                "Limpe os sensores de queda, os sensores do para-choques e os contactos de carregamento com um pano seco."
            ]
        },
        "side_brush": {
            "steps": [
                "Retire a escova lateral.",
                "Remova os cabelos e os detritos da escova e da sua base.",
                "Volte a colocar ou substitua se estiver gasta."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Aperte as patilhas da proteção da escova rotativa e retire a proteção.",
                "Retire a escova rotativa.",
                "Use a ferramenta de limpeza ou uma tesoura para remover os cabelos e os detritos.",
                "Volte a instalar a escova e a proteção."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retire o pano de limpeza do suporte.",
                "Lave-o e seque-o antes de o reutilizar.",
                "Substitua-o se ficar gasto ou ineficaz."
            ],
            "notes": [
                "Aplica-se apenas aos modelos X8 híbridos/com função de mopa."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Prima o botão de libertação do depósito de pó e retire o depósito de pó.",
                "Retire o filtro e sacuda a sujidade solta.",
                "Se o guia do modelo específico o permitir, enxague e seque completamente antes de voltar a instalar."
            ]
        },
        "sensor": {
            "steps": [
                "Use um pano seco para limpar os sensores e os contactos de carregamento no robô e na base."
            ]
        },
        "side_brush": {
            "steps": [
                "Retire a escova lateral.",
                "Remova os cabelos enrolados e os detritos.",
                "Volte a colocar ou substitua se estiver gasta."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Retire a tampa da escova rotativa.",
                "Retire a escova rotativa.",
                "Limpe os cabelos enrolados e os detritos da escova e dos rolamentos.",
                "Seque e volte a instalar a escova e a proteção."
            ],
            "notes": [
                "Os modelos SES usam também corte automático de cabelos para reduzir a manutenção."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Retire o pano de limpeza ou o tecido da mopa.",
                "Limpe-o e seque-o completamente antes de o reutilizar.",
                "Substitua o pano quando estiver gasto."
            ],
            "notes": [
                "Aplica-se apenas às variantes híbridas."
            ]
        }
    }
})
UPKEEP_GUIDE_TRANSLATIONS['ru'].update({
    "s1_pro": {
        "filter": {
            "steps": [
                "Извлеките высокоэффективный фильтр из отсека пылесборника.",
                "Осторожно постучите, чтобы стряхнуть пыль и мусор.",
                "Установите фильтр на место или замените его, когда он станет чистым и сухим."
            ],
            "notes": [
                "Раздел обслуживания аксессуаров в приложении — основная официальная процедура сброса для S1 Pro."
            ]
        },
        "sensor": {
            "steps": [
                "Протрите датчики робота мягкой сухой тканью.",
                "Заодно очистите зарядные контакты при обслуживании датчиков."
            ]
        },
        "side_brush": {
            "steps": [
                "Осмотрите боковую щётку на наличие намотавшихся волос и мусора.",
                "Удалите загрязнения вокруг основания и щетинок.",
                "Замените щётку, если щетинки погнуты или повреждены."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Снимите крышку турбощётки.",
                "Проверьте щётку и обе торцевые заглушки на наличие намотавшихся волос и мусора.",
                "Тщательно очистите щётку перед установкой на место."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Снимите валиковую швабру или контактные поверхности швабры и удалите остатки грязи.",
                "Дайте очищенным деталям высохнуть перед повторным использованием.",
                "Замените расходный элемент швабры, когда станет заметен износ или упадёт качество мытья."
            ],
            "notes": [
                "Документация S1 ориентирована на валиковую швабру, а не на съёмные парные накладки."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Извлеките лоток фильтра или вставку лотка из зоны станции.",
                "Промойте, удаляя остатки грязи и налёт.",
                "Установите на место после очистки."
            ],
            "notes": [
                "При необходимости также очистите баки чистой и грязной воды и фильтр грязной воды."
            ]
        },
        "swivel_wheel": {
            "steps": [
                "Осмотрите поворотное колесо на наличие волос и мусора.",
                "Удалите загрязнения и убедитесь, что колесо свободно вращается."
            ]
        }
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Извлеките пылесборник или отсек фильтра.",
                "Достаньте фильтр и постучите, чтобы стряхнуть пыль.",
                "Промывайте, только если это допускает руководство или приложение, затем полностью высушите перед установкой на место."
            ],
            "notes": [
                "Руководство по аксессуарам Omni C20 представлено в основном в виде видео."
            ]
        },
        "sensor": {
            "steps": [
                "Протрите чистой сухой тканью датчики и зарядные контакты как на роботе, так и на станции."
            ]
        },
        "side_brush": {
            "steps": [
                "Осмотрите боковую щётку на наличие износа, намотавшегося мусора или повреждений.",
                "Удалите намотавшиеся волосы и мусор со щётки и её основания.",
                "Замените щётку, если щетинки погнуты или отсутствуют."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Осмотрите турбощётку на наличие намотавшихся волос и мусора.",
                "С помощью инструмента для очистки или ножниц срежьте намотавшийся материал.",
                "Установите на место после очистки."
            ],
            "notes": [
                "Гребень Pro-Detangle снижает потребность в ручной очистке, но не устраняет её полностью."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Снимите салфетки для мытья с робота или станции.",
                "Очистите и полностью высушите их перед повторным использованием.",
                "Замените салфетки, когда они износятся или перестанут эффективно мыть."
            ]
        },
        "cleaning_tray": {
            "steps": [
                "Отсоедините основание станции или узел мойки швабры.",
                "Промойте и протрите зону лотка, удаляя остатки грязи.",
                "Установите лоток на место после очистки."
            ],
            "notes": [
                "Также следите за состоянием баков чистой и грязной воды и обслуживайте их."
            ]
        }
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Извлеките пылесборник и достаньте фильтр.",
                "Осторожно постучите по фильтру, чтобы удалить пыль.",
                "Если вы промыли фильтр, дайте ему полностью высохнуть перед установкой на место."
            ]
        },
        "sensor": {
            "steps": [
                "Протрите сухой тканью датчики перепада высоты, датчики бампера и зарядные контакты."
            ]
        },
        "side_brush": {
            "steps": [
                "Снимите боковую щётку.",
                "Удалите волосы и мусор со щётки и её основания.",
                "Установите на место или замените при износе."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Сожмите защёлки крышки турбощётки и снимите крышку.",
                "Извлеките турбощётку.",
                "С помощью инструмента для очистки или ножниц удалите волосы и мусор.",
                "Установите щётку и крышку на место."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Снимите салфетку для мытья с держателя.",
                "Вымойте и высушите её перед повторным использованием.",
                "Замените, если она износилась или перестала эффективно мыть."
            ],
            "notes": [
                "Относится только к гибридным моделям X8 с функцией мытья."
            ]
        }
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Нажмите кнопку разблокировки пылесборника и извлеките пылесборник.",
                "Достаньте фильтр и постучите, чтобы стряхнуть загрязнения.",
                "Если это допускает руководство для вашей модели, промойте фильтр и полностью высушите его перед установкой на место."
            ]
        },
        "sensor": {
            "steps": [
                "Протрите сухой тканью датчики и зарядные контакты на роботе и базе."
            ]
        },
        "side_brush": {
            "steps": [
                "Снимите боковую щётку.",
                "Удалите намотавшиеся волосы и мусор.",
                "Установите на место или замените при износе."
            ]
        },
        "rolling_brush": {
            "steps": [
                "Снимите крышку турбощётки.",
                "Извлеките турбощётку.",
                "Очистите щётку и подшипники от намотавшихся волос и мусора.",
                "Протрите насухо и установите щётку и крышку на место."
            ],
            "notes": [
                "Модели SES также используют автоматическую обрезку волос для сокращения обслуживания."
            ]
        },
        "mopping_cloth": {
            "steps": [
                "Снимите насадку или салфетку для мытья.",
                "Полностью очистите и высушите её перед повторным использованием.",
                "Замените салфетку при износе."
            ],
            "notes": [
                "Относится только к гибридным моделям."
            ]
        }
    }
})
