"""Upkeep-guide translations — العربية (ar).

AI-DRAFT (pending native review) — Roborock publishes no official Arabic manual and
manuals.plus (third-party) is inaccessible, so unlike the other locales these steps
are NOT transcribed from an official manual. Consistent with the card's ar locale,
which is also an AI draft. Frequencies match the English base; overlaid PER FIELD,
so anything omitted falls back to English.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "أسبوعيًا",
        "replace_frequency": "كل 6-12 شهرًا",
        "steps": [
            "اقلب الروبوت واضغط على المزلاج لإزالة غطاء الفرشاة الرئيسية.",
            "أخرج الفرشاة الرئيسية، وأزل الأغطية وحلقات منع الشعر، ونظّف الشعر والأوساخ من الطرفين.",
            "أعد تركيب الحلقات والأغطية والمحامل، ثم الفرشاة الرئيسية.",
            "أعد الغطاء بإدخال الألسنة الأربعة بالكامل واضغط حتى تسمع صوت طقطقة.",
        ],
        "notes": [
            "لا تستخدم سوائل تنظيف كاشطة أو مواد مطهّرة.",
        ],
    },
    "side_brush": {
        "clean_frequency": "شهريًا",
        "replace_frequency": "كل 3-6 أشهر",
        "steps": [
            "فك برغي الفرشاة الجانبية.",
            "أزل الفرشاة الجانبية ونظّفها.",
            "أعد تركيب الفرشاة وأحكم ربط البرغي.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "كل أسبوعين",
        "replace_frequency": "كل 6-12 شهرًا",
        "steps": [
            "أخرج المرشح القابل للغسل.",
            "اشطفه عدة مرات واطرق عليه لإزالة أكبر قدر من الأوساخ.",
            "اترك المرشح يجف تمامًا لمدة 24 ساعة على الأقل قبل إعادة تركيبه.",
        ],
        "notes": [
            "لا تلمس سطح المرشح باليدين أو بفرشاة أو بأجسام صلبة.",
        ],
    },
    "sensor": {
        "clean_frequency": "شهريًا",
        "replace_frequency": None,
        "steps": [
            "امسح جميع المستشعرات بقطعة قماش ناعمة وجافة، وامسح كذلك نقاط الشحن في الروبوت والقاعدة.",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "أسبوعيًا",
        "replace_frequency": None,
        "steps": [
            "أزل الغطاء العلوي المغناطيسي، واضغط على مزلاج حاوية الغبار وأخرجها.",
            "أخرج المرشح القابل للغسل وأفرغ حاوية الغبار.",
            "عند الحاجة، املأ الحاوية بماء نظيف وأعد المرشح ورجّها وأفرغ الماء المتسخ.",
            "اترك الحاوية والمرشح يجفّان قبل إعادة التركيب.",
        ],
        "notes": [
            "استخدم ماءً نظيفًا فقط بدون أي سائل تنظيف.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "بعد كل استخدام",
        "replace_frequency": "كل 3-6 أشهر",
        "steps": [
            "أزل ممسحة المسح من حاملها.",
            "اغسل الممسحة واتركها تجف في الهواء.",
            "أعد تركيب الممسحة مسطحة على الحامل.",
        ],
        "notes": [
            "الممسحة المتسخة تضعف أداء المسح؛ نظّفها قبل الاستخدام.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "شهريًا",
        "replace_frequency": None,
        "steps": [
            "استخدم أداة مثل مفك صغير لإخراج المحور وسحب العجلة.",
            "اشطف العجلة والمحور بالماء لإزالة الشعر والأوساخ.",
            "اتركها تجف ثم أعد تركيبها بالضغط.",
        ],
        "notes": [
            "لا يمكن إزالة حامل العجلة متعددة الاتجاهات.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "أسبوعيًا",
        "replace_frequency": None,
        "steps": [
            "افحص العجلتين الرئيسيتين أسبوعيًا وأزل الشعر أو الخيوط الملتفة حول المحاور.",
            "نظّف العجلات الرئيسية بقطعة قماش ناعمة وجافة.",
        ],
        "notes": [],
    },
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "كل 1-3 أشهر",
    "steps": [
        "أخرج مرشحات الماء من الخزان.",
        "ركّب مرشحات جديدة وأعدها إلى مكانها.",
    ],
    "notes": [
        "استبدلها كل 1-3 أشهر حسب جودة الماء والاستخدام.",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "عند الامتلاء (كل 7 أسابيع تقريبًا)",
    "steps": [
        "افتح غطاء حجرة الغبار في القاعدة.",
        "أخرج كيس الغبار الممتلئ بسحبه للأعلى مباشرة؛ يغلق المقبض الكيس عند إخراجه.",
        "أدخل كيسًا جديدًا وأغلق الغطاء.",
    ],
    "notes": [
        "ركّب كيسًا دائمًا قبل إغلاق الغطاء.",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "عند الحاجة",
    "replace_frequency": None,
    "steps": [
        "أخرج خزان الماء النظيف وافتح الغطاء العلوي.",
        "املأه بماء بارد من الصنبور.",
        "أغلق الغطاء وأعد الخزان إلى القاعدة.",
    ],
    "notes": [
        "استخدم ماءً باردًا فقط لتجنّب التشوّه.",
    ],
}
_DIRTY_WATER_TANK = {
    "clean_frequency": "عند الحاجة",
    "replace_frequency": None,
    "steps": [
        "افتح غطاء خزان الماء المتسخ وأفرغ الماء المتسخ.",
        "أضف ماءً نظيفًا وأغلق الغطاء ورجّه ثم أفرغه مرة أخرى للشطف.",
        "أغلق الغطاء وأعد الخزان إلى مكانه.",
    ],
    "notes": [
        "استخدم ماءً باردًا فقط؛ امسح الجزء الخارجي قبل إعادته.",
    ],
}

_BASE = {**_STANDARD, "water_filter": _WATER_FILTER}
GUIDE_TRANSLATIONS = {
    "standard": _BASE,
    "auto_empty": {**_BASE, "dock_dust_bag": _DOCK_DUST_BAG},
    "wash_station": {
        **_BASE, "dock_dust_bag": _DOCK_DUST_BAG,
        "clean_water_tank": _CLEAN_WATER_TANK, "dirty_water_tank": _DIRTY_WATER_TANK,
    },
}
