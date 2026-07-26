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
}

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD},
    "wash_station": {**_STANDARD},
}
