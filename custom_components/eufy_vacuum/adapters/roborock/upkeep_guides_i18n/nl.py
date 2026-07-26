"""Upkeep-guide translations — Nederlands (nl).

Transcribed from Roborock's official Dutch manual (S8 MaxV Ultra CE NL).
Frequencies match our English base; steps/notes are the official wording.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Wekelijks",
        "replace_frequency": "Om de 6-12 maanden",
        "steps": [
            "Draai de robot om, druk op de vergrendeling en verwijder de kap van de hoofdborstel.",
            "Neem de hoofdborstel eruit, verwijder de kapjes en de haarblokkeerringen en verwijder verward haar en vuil aan beide uiteinden.",
            "Plaats de ringen, kapjes en lagers terug en vervolgens de hoofdborstel.",
            "Plaats de kap terug: steek de vier lipjes volledig in de sleuven en druk tot u een klik hoort.",
        ],
        "notes": [
            "Veeg de hoofdborstel af met een vochtige doek; is deze nat, laat hem dan aan de lucht drogen, uit direct zonlicht.",
            "Gebruik geen bijtende reinigingsvloeistoffen of desinfectiemiddelen.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Maandelijks",
        "replace_frequency": "Om de 3-6 maanden",
        "steps": [
            "Draai de schroef van de zijborstel los.",
            "Verwijder en reinig de zijborstel.",
            "Plaats de borstel terug en draai de schroef vast.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "Om de 2 weken",
        "replace_frequency": "Om de 6-12 maanden",
        "steps": [
            "Verwijder het wasbare filter.",
            "Spoel het meerdere keren en tik het uit om zo veel mogelijk vuil te verwijderen.",
            "Laat het filter minstens 24 uur grondig drogen voordat u het terugplaatst.",
        ],
        "notes": [
            "Raak het filteroppervlak niet aan met de handen, een borstel of harde voorwerpen.",
            "Het wordt aanbevolen een tweede filter achter de hand te houden om af te wisselen.",
        ],
    },
    "sensor": {
        "clean_frequency": "Maandelijks",
        "replace_frequency": None,
        "steps": [
            "Veeg alle sensoren af met een zachte, droge doek: Reactive AI-obstakelsensor, dockzoeker, tapijtsensor, muursensor, communicatiesensor en valsensoren.",
            "Veeg ook de laadcontacten van de robot en het dock af.",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "Wekelijks",
        "replace_frequency": None,
        "steps": [
            "Verwijder de magnetische bovenklep, druk op de vergrendeling van het stofreservoir en neem het eruit.",
            "Verwijder het wasbare filter en leeg het stofreservoir.",
            "Vul het reservoir indien nodig met schoon water, plaats het filter terug, schud voorzichtig en giet het vuile water eruit.",
            "Laat het stofreservoir en het filter drogen voordat u ze terugplaatst.",
        ],
        "notes": [
            "Gebruik alleen schoon water zonder reinigingsvloeistof om verstopping te voorkomen.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Na elk gebruik",
        "replace_frequency": "Om de 3-6 maanden",
        "steps": [
            "Neem de mopdoek van de houder (bij sommige modellen via een schroef in het midden).",
            "Was de mopdoek en laat hem aan de lucht drogen.",
            "Plaats de mopdoek plat terug in de houder.",
        ],
        "notes": [
            "Een vuile mopdoek verslechtert het dweilen; reinig hem vóór gebruik.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Maandelijks",
        "replace_frequency": None,
        "steps": [
            "Wrik met een stuk gereedschap, zoals een kleine schroevendraaier, de as los en neem het wiel eruit.",
            "Spoel het wiel en de as af met water om haar en vuil te verwijderen.",
            "Laat aan de lucht drogen, monteer opnieuw en druk het wiel en de as op hun plaats.",
        ],
        "notes": [
            "De zwenkwielbeugel kan niet worden verwijderd.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Wekelijks",
        "replace_frequency": None,
        "steps": [
            "Controleer de twee hoofdwielen wekelijks en verwijder haar of draden rond de assen.",
            "Reinig de hoofdwielen met een zachte, droge doek.",
        ],
        "notes": [],
    },
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "Elke 1-3 maanden",
    "steps": [
        "Trek de waterfilters uit het reservoir.",
        "Plaats nieuwe filters en schuif ze terug op hun plaats.",
    ],
    "notes": [
        "Vervang ze elke 1-3 maanden, afhankelijk van waterkwaliteit en gebruik.",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "Bij volle zak (ongeveer elke 7 weken)",
    "steps": [
        "Open de klep van het stofcompartiment van het dock.",
        "Trek de volle stofzak recht omhoog; de handgreep sluit hem af tijdens het verwijderen.",
        "Schuif een nieuwe stofzak erin en sluit de klep.",
    ],
    "notes": [
        "Plaats altijd een zak voordat u de klep sluit.",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "Indien nodig",
    "replace_frequency": None,
    "steps": [
        "Til het schoonwaterreservoir eruit en open de bovenklep.",
        "Vul het met koud kraanwater.",
        "Sluit de klep en plaats het reservoir terug in het dock.",
    ],
    "notes": [
        "Gebruik alleen koud water om vervorming te voorkomen.",
    ],
}
_DIRTY_WATER_TANK = {
    "clean_frequency": "Indien nodig",
    "replace_frequency": None,
    "steps": [
        "Open de klep van het vuilwaterreservoir en giet het vuile water eruit.",
        "Voeg schoon water toe, sluit de klep, schud en giet opnieuw uit om te spoelen.",
        "Sluit de klep en plaats het reservoir terug.",
    ],
    "notes": [
        "Gebruik alleen koud water; veeg de buitenkant droog voor het terugplaatsen.",
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
