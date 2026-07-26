"""Upkeep-guide translations — עברית (he).

AI-DRAFT (pending native review) — Roborock publishes no official Hebrew manual and
manuals.plus (third-party) is inaccessible, so unlike the other locales these steps
are NOT transcribed from an official manual. Consistent with the card's he locale,
which is also an AI draft. Frequencies match the English base; overlaid PER FIELD.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "שבועי",
        "replace_frequency": "כל 6-12 חודשים",
        "steps": [
            "הפכו את הרובוט ולחצו על התפס כדי להסיר את מכסה המברשת הראשית.",
            "הוציאו את המברשת הראשית, הסירו את המכסים וטבעות מניעת השיער, ונקו שיער ולכלוך משני הקצוות.",
            "החזירו את הטבעות, המכסים והמסבים ולאחר מכן את המברשת הראשית.",
            "החזירו את המכסה, הכניסו את ארבע הלשוניות במלואן ולחצו עד להישמע נקישה.",
        ],
        "notes": [
            "אין להשתמש בנוזלי ניקוי משחיתים או בחומרי חיטוי.",
        ],
    },
    "side_brush": {
        "clean_frequency": "חודשי",
        "replace_frequency": "כל 3-6 חודשים",
        "steps": [
            "שחררו את בורג המברשת הצדדית.",
            "הסירו ונקו את המברשת הצדדית.",
            "החזירו את המברשת והדקו את הבורג.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "כל שבועיים",
        "replace_frequency": "כל 6-12 חודשים",
        "steps": [
            "הוציאו את המסנן הרחיץ.",
            "שטפו אותו מספר פעמים והקישו עליו כדי להסיר כמה שיותר לכלוך.",
            "הניחו למסנן להתייבש היטב לפחות 24 שעות לפני ההרכבה מחדש.",
        ],
        "notes": [
            "אין לגעת בפני השטח של המסנן בידיים, במברשת או בחפצים קשים.",
        ],
    },
    "sensor": {
        "clean_frequency": "חודשי",
        "replace_frequency": None,
        "steps": [
            "נגבו את כל החיישנים במטלית רכה ויבשה, ונגבו גם את מגעי הטעינה שברובוט ובתחנה.",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "שבועי",
        "replace_frequency": None,
        "steps": [
            "הסירו את המכסה העליון המגנטי, לחצו על תפס מיכל האבק והוציאו אותו.",
            "הוציאו את המסנן הרחיץ ורוקנו את מיכל האבק.",
            "במידת הצורך, מלאו את המיכל במים נקיים, החזירו את המסנן, נערו ורוקנו את המים המלוכלכים.",
            "הניחו למיכל ולמסנן להתייבש לפני ההרכבה מחדש.",
        ],
        "notes": [
            "השתמשו במים נקיים בלבד, ללא נוזל ניקוי.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "לאחר כל שימוש",
        "replace_frequency": "כל 3-6 חודשים",
        "steps": [
            "הסירו את מטלית הניגוב מהמחזיק.",
            "שטפו את המטלית והניחו לה להתייבש באוויר.",
            "החזירו את המטלית שטוחה למחזיק.",
        ],
        "notes": [
            "מטלית מלוכלכת פוגעת בניגוב; נקו אותה לפני השימוש.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "חודשי",
        "replace_frequency": None,
        "steps": [
            "השתמשו בכלי כמו מברג קטן כדי להוציא את הציר ולמשוך את הגלגל.",
            "שטפו את הגלגל והציר במים כדי להסיר שיער ולכלוך.",
            "הניחו להם להתייבש והחזירו אותם למקומם בלחיצה.",
        ],
        "notes": [
            "לא ניתן להסיר את תושבת הגלגל הרב-כיווני.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "שבועי",
        "replace_frequency": None,
        "steps": [
            "בדקו את שני הגלגלים הראשיים מדי שבוע והסירו שיער או חוטים הכרוכים על הצירים.",
            "נגבו את הגלגלים הראשיים במטלית רכה ויבשה.",
        ],
        "notes": [],
    },
}

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD},
    "wash_station": {**_STANDARD},
}
