"""Upkeep-guide translations — 简体中文 (zh-Hans).

Per-language module under roborock/upkeep_guides_i18n/; __init__.py assembles them
into ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS. Pure data.

Steps/notes TRANSCRIBED from Roborock's official Simplified-Chinese manual (P10 /
Q Revo, files.roborock.com). Frequencies are set to match our English base (not
the source model's) so the interval reads the same in every language. The manager
overlays these on the English guide PER FIELD, so anything omitted falls back to
English. Structure: GUIDE_TRANSLATIONS[family][component] = {steps[], notes[],
clean_frequency, replace_frequency}.
"""

# Base components (shared across families via composition below).
_STANDARD = {
    "main_brush": {
        "clean_frequency": "每周",
        "replace_frequency": "每 6-12 个月",
        "steps": [
            "翻转机器人，压下卡扣，取下主刷罩。",
            "取出主刷，拔出主刷轴承，按解锁标志方向旋转取下主刷盖，清除主刷两端缠绕的毛发或脏物。",
            "将主刷装回机器人。",
            "将主刷罩装回，确保四齿插入对应卡槽，然后压紧固定卡扣。",
        ],
        "notes": [
            "主刷脏污时建议用湿布擦拭；如浸水，务必晾干并避免暴晒。",
            "请勿使用具有腐蚀性的清洁液或消毒剂清洗主刷。",
        ],
    },
    "side_brush": {
        "clean_frequency": "每月",
        "replace_frequency": "每 3-6 个月",
        "steps": [
            "拆下边刷固定螺丝。",
            "清理边刷后装回，并锁紧螺丝。",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "每 2 周",
        "replace_frequency": "每 6-12 个月",
        "steps": [
            "按图示取出可水洗滤网。",
            "用清水反复冲洗，并轻敲将污垢敲出，直至干净。",
            "晾晒滤网至少 24 小时使其完全干透，再装回使用。",
        ],
        "notes": [
            "请用清水清洗，不要添加任何洗涤剂，否则可能造成滤网堵塞。",
            "禁止用手、刷子或尖锐物触碰滤网表面，以免损伤滤网。",
        ],
    },
    "sensor": {
        "clean_frequency": "每月",
        "replace_frequency": None,
        "steps": [
            "用柔软干布擦拭清理主机各传感器，包括回充、避障、沿墙、地毯识别及悬崖传感器。",
            "同时擦拭机器人及基座的充电接触区。",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "每周",
        "replace_frequency": None,
        "steps": [
            "打开机器人上盖，取出尘盒。",
            "打开滤网并清理垃圾。",
            "如需清洗，向尘盒注入清水后关闭滤网，左右摇晃并倒出脏水。",
            "晾干尘盒及可水洗滤网后再装回。",
        ],
        "notes": [
            "请用清水清洗，不要添加任何洗涤剂。",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "每次使用后",
        "replace_frequency": "每 1-3 个月",
        "steps": [
            "从拖布支架上移除拖布。",
            "清洗拖布并晾晒。",
            "将拖布与拖布支架对位安装，并粘贴牢固。",
        ],
        "notes": [
            "如拖布较脏会影响拖地效果，请清洗后再使用。",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "每月",
        "replace_frequency": None,
        "steps": [
            "借助小螺丝刀等工具撬出轮轴，拔出轮体。",
            "冲洗轮体和轮轴上的毛发或脏物，晾干后装回并压紧。",
        ],
        "notes": [
            "万向轮支架不可取出。",
        ],
    },
    "main_wheel": {
        "clean_frequency": "每周",
        "replace_frequency": None,
        "steps": [
            "每周检查两个主轮，清除轮轴上缠绕的毛发或线头。",
            "用柔软干布擦拭清理主轮。",
        ],
        "notes": [],
    },
}

# Dock delta (auto-empty station dust bag).
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "装满时（约每 7 周）",
    "steps": [
        "取下集尘仓盖板。",
        "沿箭头方向取出一次性尘袋并丢弃（取出时尘袋提手会将其封闭，防止灰尘漏出）。",
        "用干抹布清理滤网，按图示将新的一次性尘袋插入卡槽并平整铺开。",
        "将集尘仓盖板装回，确保完全密封。",
    ],
    "notes": [
        "尘袋未安装时请勿装上集尘仓盖板，以免无尘袋自动集尘；也可在手机 App 中关闭自动集尘。",
    ],
}

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD, "dock_dust_bag": _DOCK_DUST_BAG},
    "wash_station": {**_STANDARD, "dock_dust_bag": _DOCK_DUST_BAG},
}
