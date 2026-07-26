"""Upkeep-guide translations — 繁體中文 (zh-Hant).

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
pending native review (zh-Hant especially). After editing, regenerate the
frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {'x10_pro_omni': {'filter': {'steps': ['打開上蓋，取出集塵盒。',
                                       '從集塵盒取出濾網。',
                                       '輕拍濾網以抖落灰塵，並清空集塵盒。',
                                       '僅用清水沖洗集塵盒與濾網。',
                                       '待兩者完全風乾後再裝回。'],
                             'notes': ['請勿使用刷子、熱水或清潔劑。', '每 3 至 6 個月更換濾網。']},
                  'sensor': {'steps': ['使用柔軟乾布擦拭感測器與鏡頭。', '進行感測器保養時，一併擦拭充電接觸點。'],
                             'notes': ['手冊未列出感測器的更換週期。']},
                  'side_brush': {'steps': ['使用螺絲起子拆下邊刷。',
                                           '解開並清除纏繞的毛髮或碎屑。',
                                           '用清水沖洗邊刷，並使其完全風乾。',
                                           '待邊刷乾燥後再裝回。']},
                  'rolling_brush': {'steps': ['解開滾刷護蓋的卡榫，將護蓋取出。',
                                              '取出滾刷。',
                                              '剪除並清理纏繞的毛髮與碎屑。',
                                              '沖洗滾刷與護蓋，然後使其風乾。',
                                              '裝回滾刷，並將護蓋扣回原位。'],
                                    'notes': ['滾刷護蓋也應每 3 至 6 個月或於磨損時更換。']},
                  'mopping_cloth': {'steps': ['從機器人取下拖布。', '清洗拖布並完全晾乾後再使用。', '當拖布磨損或清潔效果變差時予以更換。']},
                  'cleaning_tray': {'steps': ['從 Omni 基站取出清潔盤。', '用清水徹底沖洗清潔盤。', '清潔後將清潔盤裝回。'],
                                    'notes': ['污水箱裝滿時應清空並沖洗。']},
                  'swivel_wheel': {'steps': ['檢查萬向輪是否纏繞毛髮或卡有碎屑。',
                                             '小心清除碎屑，並將輪子周圍擦拭乾淨。',
                                             '下次清潔前，確認輪子能自由轉動。'],
                                   'notes': ['手冊列有萬向輪的清潔說明，但未提供專屬的更換週期。']}},
 's1_pro': {'filter': {'steps': ['從集塵盒區域取出高效濾網。', '輕拍去除灰塵與碎屑。', '待濾網潔淨乾燥後再裝回或更換。'],
                       'notes': ['S1 Pro 的官方主要重設流程，是應用程式中的配件保養指引。']},
            'sensor': {'steps': ['使用柔軟乾布擦拭機器人的感測器。', '保養感測器時，一併清潔充電接觸點。']},
            'side_brush': {'steps': ['檢查邊刷是否卡有毛髮與碎屑。', '清除底座與刷毛周圍的積垢。', '若刷毛彎曲或損壞，請更換邊刷。']},
            'rolling_brush': {'steps': ['取下滾刷護蓋。', '檢查滾刷與兩端端蓋是否纏繞毛髮或卡有碎屑。', '徹底清潔滾刷後再裝回。']},
            'mopping_cloth': {'steps': ['取下滾筒拖布或拖地接觸面，清除殘留污垢。',
                                        '待清潔後的部件乾燥後再使用。',
                                        '當出現明顯磨損或效能下降時，更換拖地相關耗材。'],
                              'notes': ['S1 的說明文件以滾筒拖布為主，而非可拆式雙拖布的用語。']},
            'cleaning_tray': {'steps': ['從基站區域取出濾網托盤或托盤內襯。', '沖洗掉殘留污垢與積垢。', '清潔後裝回。'],
                              'notes': ['並視需要清潔清水箱／污水箱及污水濾網。']},
            'swivel_wheel': {'steps': ['檢查萬向輪是否卡有毛髮與碎屑。', '清除積垢，並確認輪子能自由轉動。']}},
 'omni_c20': {'filter': {'steps': ['取出集塵盒或濾網艙。', '取出濾網並輕拍去除灰塵。', '僅在手冊／應用程式指引允許時清洗，並待完全乾燥後再裝回。'],
                         'notes': ['Omni C20 的配件指南主要以影片呈現。']},
              'sensor': {'steps': ['使用潔淨乾布擦拭機器人與基站上的感測器及充電接觸點。']},
              'side_brush': {'steps': ['檢查邊刷是否磨損、纏繞或損壞。', '清除邊刷與底座上纏繞的毛髮與碎屑。', '若刷毛彎曲或缺損，請更換邊刷。']},
              'rolling_brush': {'steps': ['檢查滾刷是否纏繞毛髮或卡有碎屑。', '使用清潔工具或剪刀剪除纏繞的雜物。', '清潔後裝回。'],
                                'notes': ['Pro-Detangle 防纏梳可減少但無法完全省去手動清潔。']},
              'mopping_cloth': {'steps': ['從機器人或基站取下拖布。', '清潔並完全晾乾後再使用。', '當拖布磨損或清潔效果變差時予以更換。']},
              'cleaning_tray': {'steps': ['拆下基站底座或拖布清洗區部件。', '沖洗並擦除托盤區域的殘留污垢。', '清潔後將托盤裝回。'],
                                'notes': ['並留意及保養清水箱與污水箱。']}},
 'x8_series': {'filter': {'steps': ['取出集塵盒，並拿出濾網。', '輕拍濾網以去除灰塵。', '若有沖洗，請待其完全乾燥後再裝回。']},
               'sensor': {'steps': ['使用乾布擦拭防墜感測器、防撞感測器與充電接觸點。']},
               'side_brush': {'steps': ['拆下邊刷。', '清除邊刷及其底座上的毛髮與碎屑。', '重新裝回，若已磨損則更換。']},
               'rolling_brush': {'steps': ['捏住主滾刷護蓋的卡榫，取下護蓋。',
                                           '取出主滾刷。',
                                           '使用清潔工具或剪刀清除毛髮與碎屑。',
                                           '裝回滾刷與護蓋。']},
               'mopping_cloth': {'steps': ['從固定座取下拖布。', '清洗並晾乾後再使用。', '若拖布磨損或失去效果，請更換。'],
                                 'notes': ['僅適用於具備拖地功能的 X8 混合型機型。']}},
 'l60_series': {'filter': {'steps': ['按下集塵盒釋放鈕，取出集塵盒。',
                                     '取出濾網，輕拍去除鬆散的髒污。',
                                     '若該機型的指南允許，沖洗後待完全乾燥再裝回。']},
                'sensor': {'steps': ['使用乾布擦拭機器人與基站上的感測器及充電接觸點。']},
                'side_brush': {'steps': ['拔下邊刷。', '清除纏繞的毛髮與碎屑。', '重新裝回，若已磨損則更換。']},
                'rolling_brush': {'steps': ['取下主滾刷護蓋。',
                                            '取出滾刷。',
                                            '清除滾刷與軸承上纏繞的毛髮與碎屑。',
                                            '擦乾後裝回滾刷與護蓋。'],
                                  'notes': ['SES 機型另具備自動斷髮功能，可減少保養需求。']},
                'mopping_cloth': {'steps': ['取下拖布或抹布。', '清潔並完全晾乾後再使用。', '當抹布磨損時予以更換。'],
                                  'notes': ['僅適用於混合型機型。']}}}
