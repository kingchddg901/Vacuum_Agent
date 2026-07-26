"""Upkeep-guide translations — Español (es).

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
pending native review (es especially). After editing, regenerate the
frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {'x10_pro_omni': {'filter': {'clean_frequency': 'Una vez a la semana',
                             'replace_frequency': 'Cada 3-6 meses',
                             'steps': ['Abra la tapa superior y saque el depósito de polvo.',
                                       'Presione el botón de liberación para abrir y vaciar el '
                                       'depósito de polvo.',
                                       'Retire el filtro.',
                                       'Toque el filtro para quitar el polvo.',
                                       'Enjuague completamente la caja de polvo y el filtro con '
                                       'agua.',
                                       'Secar al aire la caja de polvo y el filtro completamente '
                                       'antes de su próximo uso.',
                                       'Coloque el filtro de vuelta en la caja de polvo.',
                                       'Empuje la caja de polvo de vuelta dentro de la unidad '
                                       'principal.'],
                             'notes': ['No utilice cepillos, agua caliente ni detergentes para '
                                       'limpiar el filtro.',
                                       'No utilice el filtro si no está completamente seco, de lo '
                                       'contrario puede afectar el rendimiento de limpieza.']},
                  'rolling_brush': {'clean_frequency': 'Una vez al mes',
                                    'replace_frequency': 'Cada 6 meses',
                                    'steps': ['Tire de las pestañas de liberación para desbloquear '
                                              'la protección del cepillo, como se muestra.',
                                              'Levante para sacar el cepillo giratorio. Limpie el '
                                              'cepillo giratorio con una herramienta de limpieza o '
                                              'tijeras.',
                                              'Enjuague el cepillo giratorio y la protección del '
                                              'cepillo con agua corriente.',
                                              'Secar al aire el cepillo giratorio y la protección '
                                              'del cepillo completamente antes de usar de nuevo.',
                                              'Vuelva a instalar el cepillo giratorio insertando '
                                              'primero el extremo sobresaliente fijo.',
                                              'Presione hacia abajo para encajar la protección del '
                                              'cepillo en su lugar.'],
                                    'notes': ['La protección del cepillo también debe reemplazarse '
                                              'cada 3-6 meses o cuando esté desgastada.']},
                  'side_brush': {'clean_frequency': 'Una vez al mes',
                                 'replace_frequency': 'Cada 3-6 meses (o cuando esté visiblemente '
                                                      'desgastado)',
                                 'steps': ['Retire el cepillo lateral con un destornillador.',
                                           'Con cuidado desenrolle y retire cualquier cabello o '
                                           'sustancia que esté envuelta entre la unidad principal '
                                           'y el cepillo lateral.',
                                           'Limpie el cepillo lateral con agua.',
                                           'Deje secar al aire el cepillo lateral antes de usarlo '
                                           'de nuevo.',
                                           'Reinstale el cepillo lateral en la máquina.'],
                                 'notes': ['Los materiales extraños, como el cabello, pueden '
                                           'enredarse fácilmente en el cepillo lateral, por lo que '
                                           'es mejor limpiarlo con regularidad.']},
                  'sensor': {'clean_frequency': 'Una vez al mes',
                             'replace_frequency': None,
                             'steps': ['Quite el polvo de los sensores y los pines de contacto de '
                                       'carga utilizando un paño suave.'],
                             'notes': ['Para garantizar el funcionamiento más óptimo, limpie los '
                                       'sensores y las clavijas de contacto con frecuencia.']},
                  'cleaning_tray': {'clean_frequency': None,
                                    'replace_frequency': None,
                                    'steps': ['Retire la bandeja de limpieza de la Estación Omni.',
                                              'Enjuague completamente la bandeja de limpieza con '
                                              'agua.',
                                              'Coloque la bandeja de nuevo en la Estación Omni.'],
                                    'notes': ['El tanque de agua sucia debe vaciarse y enjuagarse '
                                              'cuando esté lleno.']},
                  'mopping_cloth': {'clean_frequency': 'lavar después del uso / inspeccionar '
                                                       'regularmente',
                                    'replace_frequency': 'Cada 3-6 meses',
                                    'steps': ['Retire los pads de fregado del robot.',
                                              'Lave y seque completamente los pads antes de '
                                              'reutilizarlos.',
                                              'Reemplace los pads cuando estén desgastados o ya no '
                                              'limpien eficazmente.'],
                                    'notes': []},
                  'swivel_wheel': {'clean_frequency': 'Una vez al mes',
                                   'replace_frequency': None,
                                   'steps': ['Inspeccione la rueda giratoria para detectar cabello '
                                             'o residuos enroscados.',
                                             'Retire cuidadosamente los residuos y limpie el área '
                                             'de la rueda.',
                                             'Confirme que la rueda gira libremente antes del '
                                             'siguiente uso.'],
                                   'notes': ['El manual lista la limpieza de la rueda giratoria '
                                             'pero no proporciona un intervalo de reemplazo '
                                             'dedicado.']}},
 's1_pro': {'filter': {'steps': ['Retire el filtro de alto rendimiento de la zona del depósito de '
                                 'polvo.',
                                 'Sacúdalo suavemente para eliminar el polvo y los residuos.',
                                 'Vuelva a instalar o reemplace el filtro una vez que esté limpio '
                                 'y seco.'],
                       'notes': ['La guía de servicio de accesorios en la app es el flujo oficial '
                                 'de restablecimiento principal para el S1 Pro.']},
            'sensor': {'steps': ['Limpie los sensores del robot con un paño suave y seco.',
                                 'Limpie también los contactos de carga al hacer el mantenimiento '
                                 'de los sensores.']},
            'side_brush': {'steps': ['Inspeccione el cepillo lateral en busca de cabello y '
                                     'residuos atrapados.',
                                     'Retire la acumulación alrededor de la base y las cerdas.',
                                     'Reemplace el cepillo si las cerdas están dobladas o '
                                     'dañadas.']},
            'rolling_brush': {'steps': ['Retire la protección del cepillo giratorio.',
                                        'Revise el cepillo y las tapas de ambos extremos en busca '
                                        'de cabello enredado o residuos.',
                                        'Limpie el cepillo a fondo antes de volver a instalarlo.']},
            'mopping_cloth': {'steps': ['Retire la mopa de rodillo o las superficies de contacto '
                                        'de la mopa y limpie los residuos.',
                                        'Deje secar las piezas limpias antes de reutilizarlas.',
                                        'Reemplace el consumible de fregado cuando el desgaste sea '
                                        'visible o el rendimiento disminuya.'],
                              'notes': ['La documentación del S1 está orientada a la mopa de '
                                        'rodillo, no a la terminología de doble almohadilla '
                                        'desmontable.']},
            'cleaning_tray': {'steps': ['Retire la bandeja del filtro o el inserto de la bandeja '
                                        'de la zona de la estación.',
                                        'Enjuague los residuos y la acumulación.',
                                        'Vuelva a instalarla después de limpiarla.'],
                              'notes': ['Limpie también los depósitos de agua limpia y sucia y el '
                                        'filtro de agua sucia según sea necesario.']},
            'swivel_wheel': {'steps': ['Inspeccione la rueda giratoria en busca de cabello y '
                                       'residuos.',
                                       'Retire la acumulación y confirme que la rueda gira '
                                       'libremente.']}},
 'omni_c20': {'filter': {'steps': ['Retire el depósito de polvo o el compartimento del filtro.',
                                   'Saque el filtro y sacúdalo para eliminar el polvo.',
                                   'Lávelo solo si la guía del manual/app lo permite y luego '
                                   'séquelo por completo antes de volver a instalarlo.'],
                         'notes': ['La guía de accesorios del Omni C20 se basa principalmente en '
                                   'vídeos.']},
              'sensor': {'steps': ['Use un paño limpio y seco para limpiar los sensores y los '
                                   'contactos de carga tanto del robot como de la estación.']},
              'side_brush': {'steps': ['Inspeccione el cepillo lateral en busca de desgaste, '
                                       'enredos o daños.',
                                       'Retire el cabello enrollado y los residuos del cepillo y '
                                       'la base.',
                                       'Reemplace el cepillo si las cerdas están dobladas o '
                                       'faltan.']},
              'rolling_brush': {'steps': ['Inspeccione el cepillo giratorio en busca de cabello '
                                          'enredado o residuos.',
                                          'Use la herramienta de limpieza o unas tijeras para '
                                          'cortar el material enrollado.',
                                          'Vuelva a instalarlo después de limpiarlo.'],
                                'notes': ['El peine antienredos Pro-Detangle reduce la limpieza '
                                          'manual, pero no la elimina.']},
              'mopping_cloth': {'steps': ['Retire las almohadillas de fregado del robot o de la '
                                          'estación.',
                                          'Límpielas y séquelas por completo antes de '
                                          'reutilizarlas.',
                                          'Reemplace las almohadillas cuando estén desgastadas o '
                                          'ya no limpien eficazmente.']},
              'cleaning_tray': {'steps': ['Desmonte la base de la estación o el componente de la '
                                          'zona de lavado de la mopa.',
                                          'Enjuague y limpie los residuos de la zona de la '
                                          'bandeja.',
                                          'Vuelva a instalar la bandeja después de limpiarla.'],
                                'notes': ['Vigile y realice el mantenimiento de los depósitos de '
                                          'agua limpia y sucia.']}},
 'x8_series': {'filter': {'steps': ['Retire el depósito de polvo y saque el filtro.',
                                    'Sacúdalo suavemente para eliminar el polvo.',
                                    'Si lo enjuaga, déjelo secar por completo antes de volver a '
                                    'instalarlo.']},
               'sensor': {'steps': ['Limpie los sensores de caída, los sensores del parachoques y '
                                    'los contactos de carga con un paño seco.']},
               'side_brush': {'steps': ['Retire el cepillo lateral.',
                                        'Retire el cabello y los residuos del cepillo y de su '
                                        'base.',
                                        'Vuelva a colocarlo o reemplácelo si está desgastado.']},
               'rolling_brush': {'steps': ['Apriete las pestañas de la protección del cepillo '
                                           'giratorio y retire la protección.',
                                           'Levante para sacar el cepillo giratorio.',
                                           'Use la herramienta de limpieza o unas tijeras para '
                                           'retirar el cabello y los residuos.',
                                           'Vuelva a instalar el cepillo y la protección.']},
               'mopping_cloth': {'steps': ['Retire la almohadilla de fregado del soporte.',
                                           'Lávela y séquela antes de reutilizarla.',
                                           'Reemplácela si se desgasta o pierde eficacia.'],
                                 'notes': ['Solo se aplica a los modelos X8 híbridos o con '
                                           'capacidad de fregado.']}},
 'l60_series': {'filter': {'steps': ['Presione el botón de liberación del depósito de polvo y '
                                     'retire el depósito.',
                                     'Saque el filtro y sacúdalo para eliminar la suciedad suelta.',
                                     'Si la guía de su modelo específico lo permite, enjuáguelo y '
                                     'séquelo por completo antes de volver a instalarlo.']},
                'sensor': {'steps': ['Use un paño seco para limpiar los sensores y los contactos '
                                     'de carga del robot y de la base.']},
                'side_brush': {'steps': ['Tire del cepillo lateral para extraerlo.',
                                         'Retire el cabello enredado y los residuos.',
                                         'Vuelva a colocarlo o reemplácelo si está desgastado.']},
                'rolling_brush': {'steps': ['Retire la cubierta del cepillo giratorio.',
                                            'Levante para sacar el cepillo giratorio.',
                                            'Limpie el cabello enrollado y los residuos del '
                                            'cepillo y de los cojinetes.',
                                            'Séquelo y vuelva a instalar el cepillo y la '
                                            'protección.'],
                                  'notes': ['Los modelos SES también utilizan el corte automático '
                                            'de cabello para reducir el mantenimiento.']},
                'mopping_cloth': {'steps': ['Retire la almohadilla o el paño de fregado.',
                                            'Límpielo y séquelo por completo antes de '
                                            'reutilizarlo.',
                                            'Reemplace el paño cuando esté desgastado.'],
                                  'notes': ['Solo se aplica a las variantes híbridas.']}}}
