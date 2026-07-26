"""Upkeep-guide translations — 繁體中文 (zh-Hant).

Transcribed from Roborock's official Traditional-Chinese manual (Qrevo EdgeC 繁體,
taiwan.roborock.com). Frequencies match our English base; steps/notes are the
official wording. Overlaid PER FIELD on the English guide.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "每週",
        "replace_frequency": "每 6-12 個月",
        "steps": [
            "翻轉機器人，向內擠壓主刷罩卡扣取下主刷罩。",
            "向上提取主刷組件並拔出，再從軸承上拔下主刷，清除主刷和軸承上纏繞的毛髮或髒汙。",
            "先將主刷裝回軸承，再將主刷組件裝回機器人，確保主刷、軸承與機身上的箭頭顏色對應。",
            "將主刷罩裝回，確保四齒插入對應卡槽，然後壓緊主刷罩並確認聽到「咔噠」聲。",
        ],
        "notes": [
            "主刷髒汙時建議用濕布擦拭；如果浸水，務必晾乾並避免曝曬。",
            "請勿使用具有腐蝕性的清潔液或消毒劑清洗主刷。",
        ],
    },
    "side_brush": {
        "clean_frequency": "每月",
        "replace_frequency": "每 3-6 個月",
        "steps": [
            "拆下邊刷固定螺絲。",
            "清理邊刷後將其裝回，確保邊刷中央卡入到位後再鎖緊螺絲。",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "每 2 週",
        "replace_frequency": "每 6-12 個月",
        "steps": [
            "取下可水洗濾網。",
            "反覆沖洗並將汙垢輕敲出來，直至乾淨為止。",
            "晾曬濾網至少 24 小時使其完全乾透，再裝回使用。",
        ],
        "notes": [
            "禁止用手、刷子或尖銳物觸碰濾網表面，以免損傷濾網。",
        ],
    },
    "sensor": {
        "clean_frequency": "每月",
        "replace_frequency": None,
        "steps": [
            "用柔軟乾布擦拭清理機器人各感測器，包括 Reactive Tech 避障感測器、沿牆感測器、通訊感測器、懸崖感測器與地毯識別感測器。",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "每週",
        "replace_frequency": None,
        "steps": [
            "取下磁吸上蓋，取出塵盒。",
            "取下可水洗濾網並傾倒垃圾。",
            "如需清洗，向塵盒中注入清水後裝回濾網，左右搖晃並倒出髒水。",
            "晾乾塵盒與濾網後再裝回。",
        ],
        "notes": [
            "請用清水清洗，不要添加任何洗滌劑，否則可能造成濾網堵塞。",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "每次使用後",
        "replace_frequency": "每 1-3 個月",
        "steps": [
            "從拖布支架上移除拖布，清洗拖布並晾曬。",
            "晾乾後將拖布與拖布支架對準安裝，並黏貼牢固。",
        ],
        "notes": [
            "若拖布髒汙，會影響拖地效果，請清洗後再使用。",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "每月",
        "replace_frequency": None,
        "steps": [
            "借助小螺絲刀等工具撬出輪軸，拔出輪體。",
            "沖洗輪體和輪軸上的毛髮或髒汙，晾乾後裝回輪體並壓緊。",
        ],
        "notes": [
            "萬向輪支架不可取出。",
        ],
    },
    "main_wheel": {
        "clean_frequency": "每週",
        "replace_frequency": None,
        "steps": [
            "每週檢查兩個主輪，清除輪軸上纏繞的毛髮或線頭。",
            "用柔軟乾布擦拭清理主輪。",
        ],
        "notes": [],
    },
}

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD},
    "wash_station": {**_STANDARD},
}
