"""Upkeep-guide translations — Português (pt).

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
pending native review (pt especially). After editing, regenerate the
frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {'x10_pro_omni': {'filter': {'clean_frequency': None,
                             'replace_frequency': None,
                             'steps': ['Abra a tampa superior e retire a caixa de pó.',
                                       'Pressione o botão de liberação para abrir e esvaziar o '
                                       'coletor de pó.',
                                       'Remova o filtro.',
                                       'Toque no filtro para remover a poeira.',
                                       'Enxágue a caixa de pó e o filtro completamente com água.',
                                       'Deixe a caixa de pó e o filtro secarem completamente ao ar '
                                       'antes do próximo uso.',
                                       'Coloque o filtro de volta na caixa de pó.',
                                       'Insira o coletor de pó de volta na unidade principal.'],
                             'notes': ['Não utilize uma escova, água quente ou qualquer detergente '
                                       'para limpar o filtro.',
                                       'Não utilize o filtro se ele não estiver completamente '
                                       'seco, caso contrário, isso pode afetar o desempenho da '
                                       'limpeza.']},
                  'rolling_brush': {'clean_frequency': None,
                                    'replace_frequency': None,
                                    'steps': ['Puxe as abas de liberação para destravar o protetor '
                                              'de escova, conforme mostrado.',
                                              'Levante para retirar a escova rotativa. Limpe a '
                                              'escova rotativa com uma tesoura.',
                                              'Enxágue a escova rotativa e a proteção da escova '
                                              'com água corrente.',
                                              'Seque completamente a escova rotativa e a proteção '
                                              'da escova ao ar antes do próximo uso.',
                                              'Reinstale a escova rotativa inserindo primeiro a '
                                              'extremidade fixa saliente.',
                                              'Pressione para encaixar a proteção da escova no '
                                              'lugar.'],
                                    'notes': ['O protetor de escova também deve ser substituído a '
                                              'cada 3-6 meses ou quando estiver gasto.']},
                  'side_brush': {'clean_frequency': None,
                                 'replace_frequency': None,
                                 'steps': ['Remova a escova lateral com uma chave de fenda.',
                                           'Desenrole cuidadosamente e remova qualquer cabelo ou '
                                           'substância que esteja enrolado entre a unidade '
                                           'principal e a escova lateral.',
                                           'Limpe a escova lateral com água.',
                                           'Deixe a escova lateral secar ao ar antes do próximo '
                                           'uso.',
                                           'Reinstale a escova lateral na máquina.'],
                                 'notes': ['Substâncias estranhas, como cabelos, podem se enroscar '
                                           'facilmente na escova lateral, por isso é melhor '
                                           'limpá-la regularmente.']},
                  'sensor': {'clean_frequency': None,
                             'replace_frequency': None,
                             'steps': ['Limpe os sensores e os pinos de contato de carregamento '
                                       'com um pano macio.'],
                             'notes': ['Para manter o melhor desempenho, limpe os sensores e os '
                                       'pinos de contato de carregamento regularmente.']},
                  'cleaning_tray': {'clean_frequency': None,
                                    'replace_frequency': None,
                                    'steps': ['Remova o tanque de água suja da Estação Omni.',
                                              'Esvazie o tanque de água suja.',
                                              'Enxágue o tanque de água suja completamente com '
                                              'água corrente.',
                                              'Remova a bandeja de limpeza da Omni Station.',
                                              'Enxágue completamente a bandeja de limpeza com '
                                              'água.',
                                              'Coloque a bandeja de volta na Omni Station.'],
                                    'notes': ['O tanque de água suja deve ser esvaziado e '
                                              'enxaguado quando estiver cheio.']},
                  'mopping_cloth': {'clean_frequency': 'lavar após o uso / inspecionar '
                                                       'regularmente',
                                    'replace_frequency': 'A cada 3-6 meses',
                                    'steps': ['Remova os panos de esfregão do robô.',
                                              'Lave e seque completamente os panos antes de '
                                              'reutilizá-los.',
                                              'Substitua os panos quando estiverem gastos ou não '
                                              'limparem mais efetivamente.'],
                                    'notes': []},
                  'swivel_wheel': {'clean_frequency': 'Uma vez por mês',
                                   'replace_frequency': None,
                                   'steps': ['Inspecione a roda giratória para verificar se há '
                                             'cabelos ou detritos enrolados.',
                                             'Remova os detritos com cuidado e limpe a área da '
                                             'roda.',
                                             'Confirme que a roda gira livremente antes da próxima '
                                             'execução.'],
                                   'notes': ['O manual lista a limpeza da roda giratória, mas não '
                                             'fornece um intervalo de substituição específico.']}},
 's1_pro': {'filter': {'steps': ['Retire o filtro de alto desempenho da zona do depósito de pó.',
                                 'Sacuda o pó e os detritos com cuidado.',
                                 'Volte a instalar ou substitua o filtro quando estiver limpo e '
                                 'seco.'],
                       'notes': ['As orientações de manutenção de acessórios na aplicação são o '
                                 'fluxo de reposição oficial principal para o S1 Pro.']},
            'sensor': {'steps': ['Limpe os sensores do robô com um pano macio e seco.',
                                 'Limpe também os contactos de carregamento ao fazer a manutenção '
                                 'dos sensores.']},
            'side_brush': {'steps': ['Inspecione a escova lateral em busca de cabelos e detritos '
                                     'presos.',
                                     'Remova a acumulação à volta da base e das cerdas.',
                                     'Substitua a escova se as cerdas estiverem dobradas ou '
                                     'danificadas.']},
            'rolling_brush': {'steps': ['Retire a proteção da escova rotativa.',
                                        'Verifique a escova e ambas as tampas das extremidades em '
                                        'busca de cabelos enrolados ou detritos.',
                                        'Limpe bem a escova antes de a voltar a instalar.']},
            'mopping_cloth': {'steps': ['Retire a mopa rotativa ou as superfícies de contacto da '
                                        'mopa e limpe os resíduos.',
                                        'Deixe as peças limpas secar antes de as reutilizar.',
                                        'Substitua o consumível da mopa quando o desgaste for '
                                        'visível ou o desempenho diminuir.'],
                              'notes': ['A documentação do S1 é orientada para a mopa rotativa e '
                                        'não para a terminologia de almofada dupla destacável.']},
            'cleaning_tray': {'steps': ['Retire a bandeja do filtro ou o respetivo encaixe da zona '
                                        'da base.',
                                        'Enxague os resíduos e a acumulação.',
                                        'Volte a instalar após a limpeza.'],
                              'notes': ['Limpe também os depósitos de água limpa e suja e o filtro '
                                        'de água suja conforme necessário.']},
            'swivel_wheel': {'steps': ['Inspecione a roda giratória em busca de cabelos e '
                                       'detritos.',
                                       'Remova a acumulação e confirme que a roda roda '
                                       'livremente.']}},
 'omni_c20': {'filter': {'steps': ['Retire o depósito de pó ou o compartimento do filtro.',
                                   'Retire o filtro e sacuda o pó.',
                                   'Lave apenas se o manual/aplicação o permitir e, em seguida, '
                                   'seque completamente antes de voltar a instalar.'],
                         'notes': ['O guia de acessórios do Omni C20 é essencialmente em vídeo.']},
              'sensor': {'steps': ['Use um pano limpo e seco para limpar os sensores e os '
                                   'contactos de carregamento tanto no robô como na base.']},
              'side_brush': {'steps': ['Inspecione a escova lateral em busca de desgaste, '
                                       'emaranhados ou danos.',
                                       'Remova os cabelos enrolados e os detritos da escova e da '
                                       'base.',
                                       'Substitua a escova se as cerdas estiverem dobradas ou em '
                                       'falta.']},
              'rolling_brush': {'steps': ['Inspecione a escova rotativa em busca de cabelos '
                                          'enrolados ou detritos.',
                                          'Use a ferramenta de limpeza ou uma tesoura para cortar '
                                          'o material enrolado.',
                                          'Volte a instalar após a limpeza.'],
                                'notes': ['O Pente Pro-Detangle reduz, mas não elimina, a limpeza '
                                          'manual.']},
              'mopping_cloth': {'steps': ['Retire os panos de limpeza do robô ou da base.',
                                          'Limpe-os e seque-os completamente antes de os '
                                          'reutilizar.',
                                          'Substitua os panos quando estiverem gastos ou já não '
                                          'limparem eficazmente.']},
              'cleaning_tray': {'steps': ['Solte a base da estação ou o componente da zona de '
                                          'lavagem da mopa.',
                                          'Enxague e limpe os resíduos da zona da bandeja.',
                                          'Volte a instalar a bandeja após a limpeza.'],
                                'notes': ['Monitorize e faça também a manutenção dos depósitos de '
                                          'água limpa e suja.']}},
 'x8_series': {'filter': {'steps': ['Retire o depósito de pó e remova o filtro.',
                                    'Bata levemente no filtro para remover o pó.',
                                    'Se o enxaguar, deixe-o secar completamente antes de voltar a '
                                    'instalar.']},
               'sensor': {'steps': ['Limpe os sensores de queda, os sensores do para-choques e os '
                                    'contactos de carregamento com um pano seco.']},
               'side_brush': {'steps': ['Retire a escova lateral.',
                                        'Remova os cabelos e os detritos da escova e da sua base.',
                                        'Volte a colocar ou substitua se estiver gasta.']},
               'rolling_brush': {'steps': ['Aperte as patilhas da proteção da escova rotativa e '
                                           'retire a proteção.',
                                           'Retire a escova rotativa.',
                                           'Use a ferramenta de limpeza ou uma tesoura para '
                                           'remover os cabelos e os detritos.',
                                           'Volte a instalar a escova e a proteção.']},
               'mopping_cloth': {'steps': ['Retire o pano de limpeza do suporte.',
                                           'Lave-o e seque-o antes de o reutilizar.',
                                           'Substitua-o se ficar gasto ou ineficaz.'],
                                 'notes': ['Aplica-se apenas aos modelos X8 híbridos/com função de '
                                           'mopa.']}},
 'l60_series': {'filter': {'steps': ['Prima o botão de libertação do depósito de pó e retire o '
                                     'depósito de pó.',
                                     'Retire o filtro e sacuda a sujidade solta.',
                                     'Se o guia do modelo específico o permitir, enxague e seque '
                                     'completamente antes de voltar a instalar.']},
                'sensor': {'steps': ['Use um pano seco para limpar os sensores e os contactos de '
                                     'carregamento no robô e na base.']},
                'side_brush': {'steps': ['Retire a escova lateral.',
                                         'Remova os cabelos enrolados e os detritos.',
                                         'Volte a colocar ou substitua se estiver gasta.']},
                'rolling_brush': {'steps': ['Retire a tampa da escova rotativa.',
                                            'Retire a escova rotativa.',
                                            'Limpe os cabelos enrolados e os detritos da escova e '
                                            'dos rolamentos.',
                                            'Seque e volte a instalar a escova e a proteção.'],
                                  'notes': ['Os modelos SES usam também corte automático de '
                                            'cabelos para reduzir a manutenção.']},
                'mopping_cloth': {'steps': ['Retire o pano de limpeza ou o tecido da mopa.',
                                            'Limpe-o e seque-o completamente antes de o '
                                            'reutilizar.',
                                            'Substitua o pano quando estiver gasto.'],
                                  'notes': ['Aplica-se apenas às variantes híbridas.']}}}
