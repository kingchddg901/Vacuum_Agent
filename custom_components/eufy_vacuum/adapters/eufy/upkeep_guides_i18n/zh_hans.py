"""Upkeep-guide translations — 简体中文 (zh-Hans).

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
pending native review (zh-Hans especially). After editing, regenerate the
frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {'x10_pro_omni': {'filter': {'steps': ['打开顶盖，取出尘盒。',
                                       '从尘盒中取出滤网。',
                                       '轻拍滤网抖落灰尘，并清空尘盒。',
                                       '仅用清水冲洗尘盒和滤网。',
                                       '重新安装前，将两个部件彻底风干。'],
                             'notes': ['请勿使用刷子、热水或清洁剂。', '请每 3-6 个月更换一次滤网。']},
                  'sensor': {'steps': ['用柔软的干布擦拭传感器和摄像头。', '保养传感器时，请一并擦拭充电电极。'],
                             'notes': ['手册未列出传感器的更换周期。']},
                  'side_brush': {'steps': ['使用螺丝刀拆下边刷。',
                                           '解开并清除缠绕的头发或碎屑。',
                                           '用清水冲洗边刷，并将其彻底风干。',
                                           '待边刷干燥后重新安装。']},
                  'rolling_brush': {'steps': ['解锁滚刷盖板卡扣，将盖板抬出。',
                                              '取出滚刷。',
                                              '剪除并清理缠绕的头发和碎屑。',
                                              '冲洗滚刷和盖板，然后将其风干。',
                                              '重新安装滚刷，并将盖板卡回原位。'],
                                    'notes': ['滚刷盖板同样应每 3-6 个月或在磨损时更换。']},
                  'mopping_cloth': {'steps': ['从机器人上取下拖布。',
                                              '再次使用前，请清洗拖布并将其彻底晾干。',
                                              '当拖布磨损或清洁效果下降时，请及时更换。']},
                  'cleaning_tray': {'steps': ['从 Omni 基站取出清洁托盘。', '用清水彻底冲洗托盘。', '清洁后将托盘装回。'],
                                    'notes': ['污水箱装满后应及时清空并冲洗。']},
                  'swivel_wheel': {'steps': ['检查万向轮上是否缠绕头发或碎屑。',
                                             '小心清除碎屑，并将轮子周围擦拭干净。',
                                             '在下次清扫前，确认轮子转动顺畅。'],
                                   'notes': ['手册列出了万向轮的清洁方法，但未提供专门的更换周期。']}},
 's1_pro': {'filter': {'steps': ['从尘盒处取出高性能滤网。', '轻轻抖落灰尘和碎屑。', '待滤网清洁并晾干后，将其重新安装或更换。'],
                       'notes': ['应用程序中的配件保养指引是 S1 Pro 主要的官方重置流程。']},
            'sensor': {'steps': ['用柔软的干布擦拭机器人传感器。', '保养传感器时，请一并清洁充电电极。']},
            'side_brush': {'steps': ['检查边刷是否夹有头发和碎屑。', '清除底座和刷毛周围的积垢。', '如果刷毛弯曲或损坏，请更换边刷。']},
            'rolling_brush': {'steps': ['取下滚刷盖板。', '检查滚刷及其两端端盖是否缠有头发或碎屑。', '重新安装前，将滚刷彻底清洁干净。']},
            'mopping_cloth': {'steps': ['取下滚筒拖布或拖布接触面，清除残留污渍。',
                                        '清洁后待部件晾干再使用。',
                                        '当出现明显磨损或效果下降时，请更换拖布类耗材。'],
                              'notes': ['S1 的文档以滚筒拖布为主，而非可拆卸双拖布的表述。']},
            'cleaning_tray': {'steps': ['从基站处取出滤网托盘或托盘衬件。', '冲洗掉残留物和积垢。', '清洁后重新安装。'],
                              'notes': ['并按需清洁清水箱、污水箱以及污水滤网。']},
            'swivel_wheel': {'steps': ['检查万向轮上是否有头发和碎屑。', '清除积垢，并确认轮子转动顺畅。']}},
 'omni_c20': {'filter': {'steps': ['取出尘盒或滤网仓。', '取出滤网并轻拍抖落灰尘。', '仅在手册/应用指引允许时清洗，然后彻底晾干再重新安装。'],
                         'notes': ['Omni C20 的配件保养指南主要以视频形式提供。']},
              'sensor': {'steps': ['用干净的干布擦拭机器人和基站上的传感器与充电电极。']},
              'side_brush': {'steps': ['检查边刷是否磨损、缠绕或损坏。', '清除边刷和底座上缠绕的头发和碎屑。', '如果刷毛弯曲或缺失，请更换边刷。']},
              'rolling_brush': {'steps': ['检查滚刷是否缠有头发或碎屑。', '使用清洁工具或剪刀剪除缠绕的杂物。', '清洁后重新安装。'],
                                'notes': ['Pro-Detangle 防缠绕梳可减少但无法完全免除手动清洁。']},
              'mopping_cloth': {'steps': ['从机器人或基站上取下拖布。',
                                          '再次使用前，请清洗并彻底晾干。',
                                          '当拖布磨损或清洁效果下降时，请更换。']},
              'cleaning_tray': {'steps': ['拆下基站底座或拖布清洗区部件。', '冲洗并擦除托盘区域的残留物。', '清洁后将托盘装回。'],
                                'notes': ['并注意查看和清洁清水箱与污水箱。']}},
 'x8_series': {'filter': {'steps': ['取出尘盒并取下滤网。', '轻拍滤网以抖落灰尘。', '如果冲洗过，请在重新安装前将其彻底风干。']},
               'sensor': {'steps': ['用干布擦拭防跌落传感器、缓冲器传感器和充电电极。']},
               'side_brush': {'steps': ['取下边刷。', '清除边刷及其底座上的头发和碎屑。', '重新安装；如已磨损则更换。']},
               'rolling_brush': {'steps': ['捏住滚刷盖板卡扣，取下盖板。',
                                           '提起并取出滚刷。',
                                           '使用清洁工具或剪刀清除头发和碎屑。',
                                           '重新安装滚刷和盖板。']},
               'mopping_cloth': {'steps': ['从支架上取下拖布。', '再次使用前清洗并晾干。', '如果磨损或效果变差则更换。'],
                                 'notes': ['仅适用于支持拖地的 X8 Hybrid 机型。']}},
 'l60_series': {'filter': {'steps': ['按下尘盒释放按钮，取出尘盒。',
                                     '取下滤网并轻拍抖落浮尘。',
                                     '如果具体机型指南允许，请冲洗并彻底晾干后再重新安装。']},
                'sensor': {'steps': ['用干布擦拭机器人和基站上的传感器与充电电极。']},
                'side_brush': {'steps': ['拔下边刷。', '清除缠绕的头发和碎屑。', '重新安装；如已磨损则更换。']},
                'rolling_brush': {'steps': ['取下滚刷盖板。',
                                            '提起并取出滚刷。',
                                            '清除滚刷和轴承上缠绕的头发和碎屑。',
                                            '擦干后重新安装滚刷和盖板。'],
                                  'notes': ['SES 机型还配备自动断发功能以减少维护。']},
                'mopping_cloth': {'steps': ['取下拖布或抹布。', '再次使用前，请清洗并彻底晾干。', '当拖布磨损时请更换。'],
                                  'notes': ['仅适用于 Hybrid 机型。']}}}
