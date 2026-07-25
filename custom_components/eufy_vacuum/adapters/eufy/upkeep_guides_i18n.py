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
