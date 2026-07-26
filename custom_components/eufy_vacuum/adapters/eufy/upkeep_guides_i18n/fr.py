"""Upkeep-guide translations — Français (fr).

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
pending native review (fr especially). After editing, regenerate the
frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {'x10_pro_omni': {'filter': {'clean_frequency': 'Une fois par semaine',
                             'replace_frequency': 'Tous les 3-6 mois',
                             'steps': ['Ouvrez le couvercle supérieur et sortez le bac à '
                                       'poussière.',
                                       'Appuyez sur le bouton de déverrouillage pour ouvrir et '
                                       'vider le bac à poussière.',
                                       'Retirez le filtre.',
                                       'Appuyez sur le filtre pour enlever la poussière.',
                                       'Rincez soigneusement le bac à poussière et le filtre avec '
                                       "de l'eau.",
                                       "Séchez à l'air le bac à poussière et le filtre "
                                       'complètement avant la prochaine utilisation.',
                                       'Replacez le filtre dans le bac à poussière.',
                                       "Poussez le bac à poussière vers l'arrière dans l'unité "
                                       'principale.'],
                             'notes': ["Avant le nettoyage et l'entretien, éteignez l'appareil et "
                                       "débranchez l'adaptateur d'alimentation. Tout autre "
                                       'entretien doit être effectué par un représentant de '
                                       'service autorisé. Pour des performances optimales, suivez '
                                       'les instructions ci-dessous pour nettoyer et entretenir '
                                       'régulièrement. La fréquence de nettoyage et de '
                                       "remplacement dépendra de vos habitudes d'utilisation."]},
                  'rolling_brush': {'clean_frequency': 'Une fois par mois',
                                    'replace_frequency': 'Tous les 6 mois',
                                    'steps': ['Tirez sur les languettes de déverrouillage pour '
                                              'déverrouiller le protège-brosse comme indiqué.',
                                              'Soulevez pour retirer la brosse roulante. Nettoyez '
                                              'la brosse roulante avec un outil de nettoyage ou '
                                              'des ciseaux.',
                                              'Rincez la brosse roulante et le protège-brosse avec '
                                              "de l'eau courante.",
                                              "Séchez à l'air la brosse roulante et le "
                                              'protège-brosse complètement avant la prochaine '
                                              'utilisation.',
                                              "Réinstallez la brosse roulant en insérant d'abord "
                                              "l'extrémité saillante fixe.",
                                              'Appuyez vers le bas pour enclencher le '
                                              'protège-brosse en place.'],
                                    'notes': ['Le protège-brosse doit également être remplacé tous '
                                              "les 3-6 mois ou en cas d'usure."]},
                  'side_brush': {'clean_frequency': 'Une fois par mois',
                                 'replace_frequency': "Tous les 3-6 mois (ou lorsque l'usure est "
                                                      'visible)',
                                 'steps': ['Retirez la brosse latérale avec un tournevis.',
                                           'Déroulez soigneusement et retirez les cheveux ou les '
                                           "substances qui sont enroulés entre l'unité principale "
                                           'et la brosse latérale.',
                                           "Nettoyez la brosse latérale avec de l'eau.",
                                           "Séchez à l'air la brosse latérale avant la prochaine "
                                           'utilisation.',
                                           'Réinstallez la brosse latérale sur la machine.'],
                                 'notes': ['Les substances étrangères, telles que les cheveux, '
                                           "peuvent facilement s'emmêler dans la brosse latérale. "
                                           'Il est donc préférable de la nettoyer régulièrement.']},
                  'sensor': {'clean_frequency': 'Une fois par mois',
                             'replace_frequency': None,
                             'steps': ['Pour maintenir les meilleures performances, nettoyez '
                                       'régulièrement les capteurs et les broches de contact.',
                                       'Dépoussiérez les capteurs et les broches de contact de '
                                       "recharge à l'aide d'un chiffon doux."],
                             'notes': []},
                  'cleaning_tray': {'clean_frequency': None,
                                    'replace_frequency': None,
                                    'steps': ['Retirez le plateau de nettoyage de la station Omni.',
                                              'Rincez soigneusement le plateau de nettoyage avec '
                                              "de l'eau.",
                                              'Replacez le plateau dans la Station Omni.'],
                                    'notes': ["Le réservoir d'eau sale doit être vidé et rincé "
                                              'quand il est plein.']},
                  'mopping_cloth': {'clean_frequency': 'Lavez après utilisation / inspectez '
                                                       'régulièrement',
                                    'replace_frequency': 'Tous les 3-6 mois',
                                    'steps': ['Retirez les tampons de lavage du robot.',
                                              'Lavez et séchez complètement les tampons avant '
                                              'réutilisation.',
                                              'Remplacez les tampons quand ils deviennent usés ou '
                                              'ne nettoient plus efficacement.'],
                                    'notes': []},
                  'swivel_wheel': {'clean_frequency': 'Une fois par mois',
                                   'replace_frequency': None,
                                   'steps': ['Inspectez la roue pivotante pour vérifier la '
                                             'présence de cheveux ou débris.',
                                             'Retirez les débris avec soin et nettoyez la zone de '
                                             'la roue.',
                                             'Confirmez que la roue tourne librement avant le '
                                             'prochain passage.'],
                                   'notes': ['Le manuel indique le nettoyage de la roue pivotante '
                                             "mais ne précise pas d'intervalle de remplacement."]}},
 's1_pro': {'filter': {'steps': ['Retirez le filtre haute performance de la zone du bac à '
                                 'poussière.',
                                 'Tapotez délicatement pour faire tomber la poussière et les '
                                 'débris.',
                                 "Réinstallez ou remplacez le filtre une fois qu'il est propre et "
                                 'sec.'],
                       'notes': ["Les instructions d'entretien des accessoires dans l'application "
                                 'constituent la procédure de réinitialisation officielle '
                                 'principale pour le S1 Pro.']},
            'sensor': {'steps': ['Essuyez les capteurs du robot avec un chiffon doux et sec.',
                                 "Nettoyez également les contacts de charge pendant l'entretien "
                                 'des capteurs.']},
            'side_brush': {'steps': ['Vérifiez que la brosse latérale ne retient ni cheveux ni '
                                     'débris.',
                                     "Retirez l'accumulation autour de la base et des poils.",
                                     'Remplacez la brosse si les poils sont tordus ou '
                                     'endommagés.']},
            'rolling_brush': {'steps': ['Retirez le protège-brosse rotative.',
                                        'Vérifiez la présence de cheveux emmêlés ou de débris sur '
                                        'la brosse et sur les deux embouts.',
                                        'Nettoyez soigneusement la brosse avant de la '
                                        'réinstaller.']},
            'mopping_cloth': {'steps': ['Retirez la serpillière rotative ou les surfaces de '
                                        'contact de la serpillière et éliminez les résidus.',
                                        'Laissez sécher les pièces nettoyées avant de les '
                                        'réutiliser.',
                                        "Remplacez le consommable de serpillière lorsque l'usure "
                                        'devient visible ou que les performances diminuent.'],
                              'notes': ['La documentation du S1 est axée sur la serpillière '
                                        'rotative plutôt que sur des tampons jumeaux amovibles.']},
            'cleaning_tray': {'steps': ['Retirez le plateau du filtre ou le bac amovible de la '
                                        'zone de la station.',
                                        "Rincez pour éliminer les résidus et l'accumulation.",
                                        'Réinstallez-le après le nettoyage.'],
                              'notes': ["Nettoyez également les réservoirs d'eau propre et d'eau "
                                        "sale ainsi que le filtre d'eau sale selon les besoins."]},
            'swivel_wheel': {'steps': ['Vérifiez que la roue pivotante ne contient ni cheveux ni '
                                       'débris.',
                                       "Retirez l'accumulation et vérifiez que la roue tourne "
                                       'librement.']}},
 'omni_c20': {'filter': {'steps': ['Retirez le bac à poussière ou le compartiment du filtre.',
                                   'Sortez le filtre et tapotez pour en faire tomber la poussière.',
                                   'Lavez-le uniquement si les instructions du manuel/de '
                                   "l'application l'autorisent, puis séchez-le complètement avant "
                                   'de le réinstaller.'],
                         'notes': ["Le guide des accessoires de l'Omni C20 est principalement sous "
                                   'forme de vidéos.']},
              'sensor': {'steps': ['Utilisez un chiffon propre et sec pour essuyer les capteurs et '
                                   'les contacts de charge, sur le robot comme sur la station.']},
              'side_brush': {'steps': ['Vérifiez que la brosse latérale ne présente ni usure, ni '
                                       'emmêlement, ni dommage.',
                                       'Retirez les cheveux enroulés et les débris de la brosse et '
                                       'de sa base.',
                                       'Remplacez la brosse si les poils sont tordus ou '
                                       'manquants.']},
              'rolling_brush': {'steps': ['Vérifiez la présence de cheveux emmêlés ou de débris '
                                          'sur la brosse rotative.',
                                          "Utilisez l'outil de nettoyage ou des ciseaux pour "
                                          'couper les matières enroulées.',
                                          'Réinstallez-la après le nettoyage.'],
                                'notes': ['Le peigne anti-emmêlement Pro-Detangle réduit le '
                                          "nettoyage manuel sans l'éliminer."]},
              'mopping_cloth': {'steps': ['Retirez les tampons de serpillière du robot ou de la '
                                          'station.',
                                          'Nettoyez-les et séchez-les complètement avant de les '
                                          'réutiliser.',
                                          "Remplacez les tampons lorsqu'ils sont usés ou ne "
                                          'nettoient plus efficacement.']},
              'cleaning_tray': {'steps': ['Détachez la base de la station ou le composant de la '
                                          'zone de lavage de la serpillière.',
                                          'Rincez et essuyez les résidus de la zone du bac.',
                                          'Réinstallez le bac après le nettoyage.'],
                                'notes': ["Surveillez et entretenez également les réservoirs d'eau "
                                          "propre et d'eau sale."]}},
 'x8_series': {'filter': {'steps': ['Retirez le bac à poussière et sortez le filtre.',
                                    'Tapotez délicatement le filtre pour en retirer la poussière.',
                                    "S'il a été rincé, laissez-le sécher complètement avant de le "
                                    'réinstaller.']},
               'sensor': {'steps': ['Essuyez les capteurs anti-chute, les capteurs du pare-chocs '
                                    'et les contacts de charge avec un chiffon sec.']},
               'side_brush': {'steps': ['Retirez la brosse latérale.',
                                        'Éliminez les cheveux et les débris de la brosse et de sa '
                                        'base.',
                                        'Refixez-la ou remplacez-la si elle est usée.']},
               'rolling_brush': {'steps': ['Pincez les languettes du protège-brosse rotative et '
                                           'retirez le protège-brosse.',
                                           'Soulevez la brosse rotative pour la retirer.',
                                           "Utilisez l'outil de nettoyage ou des ciseaux pour "
                                           'retirer les cheveux et les débris.',
                                           'Réinstallez la brosse et le protège-brosse.']},
               'mopping_cloth': {'steps': ['Retirez le tampon de serpillière de son support.',
                                           'Lavez-le et séchez-le avant de le réutiliser.',
                                           "Remplacez-le s'il devient usé ou inefficace."],
                                 'notes': ["S'applique uniquement aux modèles X8 hybrides / "
                                           "équipés d'une serpillière."]}},
 'l60_series': {'filter': {'steps': ['Appuyez sur le bouton de déverrouillage du bac à poussière '
                                     'et retirez le bac.',
                                     'Retirez le filtre et tapotez pour en faire tomber la saleté.',
                                     "Si le guide de votre modèle l'autorise, rincez-le et "
                                     'séchez-le complètement avant de le réinstaller.']},
                'sensor': {'steps': ['Utilisez un chiffon sec pour essuyer les capteurs et les '
                                     'contacts de charge du robot et de la base.']},
                'side_brush': {'steps': ['Retirez la brosse latérale en tirant.',
                                         'Retirez les cheveux emmêlés et les débris.',
                                         'Refixez-la ou remplacez-la si elle est usée.']},
                'rolling_brush': {'steps': ['Retirez le cache de la brosse rotative.',
                                            'Soulevez la brosse rotative pour la retirer.',
                                            'Nettoyez les cheveux enroulés et les débris sur la '
                                            'brosse et les paliers.',
                                            'Essuyez pour sécher, puis réinstallez la brosse et le '
                                            'protège-brosse.'],
                                  'notes': ['Les modèles SES utilisent aussi une découpe '
                                            "automatique des poils pour réduire l'entretien."]},
                'mopping_cloth': {'steps': ['Retirez le tampon de serpillière ou le chiffon.',
                                            'Nettoyez-le et séchez-le complètement avant de le '
                                            'réutiliser.',
                                            "Remplacez le chiffon lorsqu'il est usé."],
                                  'notes': ["S'applique uniquement aux variantes hybrides."]}}}
