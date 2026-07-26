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

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD},
    "wash_station": {**_STANDARD},
}
