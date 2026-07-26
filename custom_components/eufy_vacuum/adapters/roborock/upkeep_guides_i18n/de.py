"""Upkeep-guide translations — Deutsch (de).

Per-language module under roborock/upkeep_guides_i18n/; __init__.py assembles them
into ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS. Pure data.

Steps/notes TRANSCRIBED from Roborock's official German manual (S8 MaxV Ultra CE
DE). Frequencies match our English base (not the source model's) so the interval
reads the same in every language. Overlaid PER FIELD on the English guide —
anything omitted (e.g. the dock deltas, not in this manual) falls back to English.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Wöchentlich",
        "replace_frequency": "Alle 6-12 Monate",
        "steps": [
            "Drehen Sie den Roboter um, drücken Sie die Verriegelung und nehmen Sie die Hauptbürstenabdeckung ab.",
            "Nehmen Sie die Hauptbürste heraus, entfernen Sie Kappen und Haarblockierringe und beseitigen Sie verhedderte Haare an beiden Enden.",
            "Setzen Sie Ringe, Kappen und Lager wieder ein und danach die Hauptbürste.",
            "Setzen Sie die Abdeckung wieder ein — die vier Laschen vollständig einführen und nach unten drücken, bis sie einrastet.",
        ],
        "notes": [
            "Wischen Sie die Hauptbürste mit einem feuchten Tuch ab; ist sie feucht, vor direkter Sonne geschützt an der Luft trocknen lassen.",
            "Verwenden Sie keine ätzenden Reinigungs- oder Desinfektionsmittel.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Monatlich",
        "replace_frequency": "Alle 3-6 Monate",
        "steps": [
            "Schrauben Sie die Schraube der Seitenbürste ab.",
            "Entfernen und reinigen Sie die Seitenbürste.",
            "Setzen Sie die Bürste wieder ein und ziehen Sie die Schraube fest.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "Alle 2 Wochen",
        "replace_frequency": "Alle 6-12 Monate",
        "steps": [
            "Entfernen Sie den waschbaren Filter.",
            "Spülen Sie ihn mehrmals aus und klopfen Sie ihn ab, um so viel Schmutz wie möglich zu entfernen.",
            "Lassen Sie den Filter mindestens 24 Stunden gründlich trocknen, bevor Sie ihn wieder einsetzen.",
        ],
        "notes": [
            "Berühren Sie die Filteroberfläche nicht mit den Händen, einer Bürste oder harten Gegenständen.",
            "Es empfiehlt sich, einen zweiten Filter zum Wechseln bereitzuhalten.",
        ],
    },
    "sensor": {
        "clean_frequency": "Monatlich",
        "replace_frequency": None,
        "steps": [
            "Wischen Sie mit einem weichen, trockenen Tuch alle Sensoren ab.",
            "Wischen Sie dabei auch die Ladekontakte am Roboter und an der Dockingstation ab.",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "Wöchentlich",
        "replace_frequency": None,
        "steps": [
            "Nehmen Sie die magnetische obere Abdeckung ab und drücken Sie den Staubbehälterverschluss, um den Staubbehälter zu entnehmen.",
            "Entfernen Sie den waschbaren Filter und leeren Sie den Staubbehälter.",
            "Bei Bedarf mit sauberem Wasser befüllen, den Filter einsetzen, leicht schütteln und das Schmutzwasser ausgießen.",
            "Lassen Sie Staubbehälter und Filter vor dem Einsetzen trocknen.",
        ],
        "notes": [
            "Zum Vermeiden von Verstopfungen nur sauberes Wasser ohne Reinigungsflüssigkeit verwenden.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Nach jedem Gebrauch",
        "replace_frequency": "Alle 3-6 Monate",
        "steps": [
            "Nehmen Sie das Wischtuch von der Halterung ab (bei manchen Modellen über eine Schraube in der Mitte).",
            "Waschen Sie das Wischtuch und lassen Sie es an der Luft trocknen.",
            "Setzen Sie das Wischtuch wieder flach in die Halterung ein.",
        ],
        "notes": [
            "Ein verschmutztes Wischtuch beeinträchtigt die Wischleistung — reinigen Sie es vor dem Gebrauch.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Monatlich",
        "replace_frequency": None,
        "steps": [
            "Hebeln Sie mit einem Werkzeug, z. B. einem kleinen Schraubendreher, die Achse heraus und nehmen Sie das Rad heraus.",
            "Spülen Sie Rad und Achse mit Wasser ab, um Haare und Schmutz zu entfernen.",
            "Lassen Sie sie an der Luft trocknen, bauen Sie sie wieder ein und drücken Sie sie in Position.",
        ],
        "notes": [
            "Die Halterung des Rundlaufrads kann nicht entfernt werden.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Wöchentlich",
        "replace_frequency": None,
        "steps": [
            "Prüfen Sie beide Haupträder wöchentlich auf um die Achsen gewickelte Haare oder Fäden.",
            "Reinigen Sie die Haupträder mit einem weichen, trockenen Tuch.",
        ],
        "notes": [],
    },
}

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD},
    "wash_station": {**_STANDARD},
}
