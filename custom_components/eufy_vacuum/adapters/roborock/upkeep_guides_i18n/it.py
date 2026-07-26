"""Upkeep-guide translations — Italiano (it).

Transcribed from Roborock's official Italian manual (S8 MaxV Ultra CE IT).
Frequencies match our English base; steps/notes are the official wording.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Settimanale",
        "replace_frequency": "Ogni 6-12 mesi",
        "steps": [
            "Capovolgere il robot, premere il fermo e rimuovere il coperchio della spazzola principale.",
            "Estrarre la spazzola principale, rimuovere i cappucci e gli anelli anti-capelli ed eliminare capelli e sporco a entrambe le estremità.",
            "Reinstallare anelli, cappucci e cuscinetti e quindi la spazzola principale.",
            "Reinstallare il coperchio: inserire completamente le quattro linguette nelle fessure e premere fino a udire uno scatto.",
        ],
        "notes": [
            "Pulire la spazzola principale con un panno umido; se è bagnata, lasciarla asciugare all’aria e al riparo dalla luce solare diretta.",
            "Non usare liquidi detergenti corrosivi né disinfettanti.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Mensile",
        "replace_frequency": "Ogni 3-6 mesi",
        "steps": [
            "Svitare la vite della spazzola laterale.",
            "Rimuovere e pulire la spazzola laterale.",
            "Reinstallare la spazzola e serrare la vite.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "Ogni 2 settimane",
        "replace_frequency": "Ogni 6-12 mesi",
        "steps": [
            "Rimuovere il filtro lavabile.",
            "Sciacquarlo più volte e picchiettarlo per rimuovere quanto più sporco possibile.",
            "Lasciare asciugare il filtro per almeno 24 ore prima di reinstallarlo.",
        ],
        "notes": [
            "Non toccare la superficie del filtro con le mani, una spazzola o oggetti duri.",
            "Si consiglia di tenere un secondo filtro da alternare se necessario.",
        ],
    },
    "sensor": {
        "clean_frequency": "Mensile",
        "replace_frequency": None,
        "steps": [
            "Pulire tutti i sensori con un panno morbido e asciutto: sensore ostacoli Reactive AI, localizzatore della base, sensore tappeti, sensore da parete, sensore di comunicazione e sensori anticaduta.",
            "Pulire anche i contatti di ricarica del robot e della base.",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "Settimanale",
        "replace_frequency": None,
        "steps": [
            "Rimuovere il coperchio magnetico superiore, premere il fermo del contenitore della polvere ed estrarlo.",
            "Rimuovere il filtro lavabile e svuotare il contenitore della polvere.",
            "Se necessario, riempire il contenitore con acqua pulita, reinstallare il filtro, agitare delicatamente e svuotare l’acqua sporca.",
            "Lasciare asciugare il contenitore e il filtro prima di reinstallarli.",
        ],
        "notes": [
            "Per evitare intasamenti, usare solo acqua pulita senza liquidi detergenti.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Dopo ogni utilizzo",
        "replace_frequency": "Ogni 3-6 mesi",
        "steps": [
            "Rimuovere il panno mop dal supporto (in alcuni modelli tramite una vite centrale).",
            "Lavare il panno e lasciarlo asciugare all’aria.",
            "Rimettere il panno in piano nel supporto.",
        ],
        "notes": [
            "Un panno sporco compromette il lavaggio; pulirlo prima dell’uso.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Mensile",
        "replace_frequency": None,
        "steps": [
            "Con uno strumento, come un piccolo cacciavite, fare leva sull’asse ed estrarre la ruota.",
            "Sciacquare la ruota e l’asse con acqua per rimuovere peli e sporco.",
            "Lasciare asciugare all’aria, reinstallare e rimettere in posizione ruota e asse.",
        ],
        "notes": [
            "La staffa della ruota omnidirezionale non può essere rimossa.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Settimanale",
        "replace_frequency": None,
        "steps": [
            "Controllare ogni settimana le due ruote principali e rimuovere capelli o fili avvolti attorno agli assi.",
            "Pulire le ruote principali con un panno morbido e asciutto.",
        ],
        "notes": [],
    },
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "Ogni 1-3 mesi",
    "steps": [
        "Estrai i filtri dell’acqua dal serbatoio.",
        "Inserisci filtri nuovi e rimettili in posizione.",
    ],
    "notes": [
        "Sostituiscili ogni 1-3 mesi in base alla qualità dell’acqua e all’uso.",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "Quando è pieno (circa ogni 7 settimane)",
    "steps": [
        "Apri il coperchio del vano polvere della base.",
        "Estrai il sacchetto della polvere pieno tirandolo dritto; la maniglia lo sigilla durante la rimozione.",
        "Inserisci un sacchetto nuovo e chiudi il coperchio.",
    ],
    "notes": [
        "Inserisci sempre un sacchetto prima di chiudere il coperchio.",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "Se necessario",
    "replace_frequency": None,
    "steps": [
        "Estrai il serbatoio dell’acqua pulita e apri il coperchio superiore.",
        "Riempilo con acqua fredda del rubinetto.",
        "Chiudi il coperchio e rimetti il serbatoio nella base.",
    ],
    "notes": [
        "Usa solo acqua fredda per evitare deformazioni.",
    ],
}
_DIRTY_WATER_TANK = {
    "clean_frequency": "Se necessario",
    "replace_frequency": None,
    "steps": [
        "Apri il coperchio del serbatoio dell’acqua sporca e svuota l’acqua sporca.",
        "Aggiungi acqua pulita, chiudi il coperchio, agita e svuota di nuovo per risciacquare.",
        "Chiudi il coperchio e rimetti il serbatoio.",
    ],
    "notes": [
        "Usa solo acqua fredda; asciuga l’esterno prima di rimetterlo.",
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
