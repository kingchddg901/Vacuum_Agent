"""Upkeep-guide translations — Français (fr).

Transcribed from Roborock's official French manual (S8 MaxV Ultra CE FR).
Frequencies match our English base; steps/notes are the official wording.
Overlaid PER FIELD on the English guide — anything omitted falls back to English.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Hebdomadaire",
        "replace_frequency": "Tous les 6-12 mois",
        "steps": [
            "Retournez le robot, appuyez sur le loquet et retirez le cache de la brosse principale.",
            "Sortez la brosse principale, retirez les capuchons et les anneaux anti-cheveux, puis ôtez les cheveux et saletés emmêlés à chaque extrémité.",
            "Réinstallez les anneaux, capuchons et roulements, puis la brosse principale.",
            "Réinstallez le cache : insérez entièrement les quatre dents dans les fentes et appuyez jusqu’à entendre un déclic.",
        ],
        "notes": [
            "Nettoyez la brosse principale avec un chiffon humide ; si elle est mouillée, laissez-la sécher à l’air libre, à l’abri du soleil direct.",
            "N’utilisez pas de liquide de nettoyage corrosif ni de désinfectant.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Mensuel",
        "replace_frequency": "Tous les 3-6 mois",
        "steps": [
            "Retirez la vis de la brosse latérale.",
            "Retirez et nettoyez la brosse latérale.",
            "Réinstallez la brosse et resserrez la vis.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "Toutes les 2 semaines",
        "replace_frequency": "Tous les 6-12 mois",
        "steps": [
            "Retirez le filtre lavable.",
            "Rincez-le plusieurs fois et tapotez-le pour retirer le plus de saleté possible.",
            "Laissez le filtre sécher au moins 24 heures avant de le remettre en place.",
        ],
        "notes": [
            "Ne touchez pas la surface du filtre avec les mains, une brosse ou des objets durs.",
            "Il est conseillé de garder un second filtre pour l’alterner si nécessaire.",
        ],
    },
    "sensor": {
        "clean_frequency": "Mensuel",
        "replace_frequency": None,
        "steps": [
            "Essuyez tous les capteurs avec un chiffon doux et sec : capteur d’obstacles Reactive AI, localisateur de station, capteur de tapis, capteur de murs, capteur de communication et capteurs de vide.",
            "Essuyez également les contacts de rechargement du robot et de la station.",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "Hebdomadaire",
        "replace_frequency": None,
        "steps": [
            "Retirez le cache magnétique supérieur, appuyez sur le loquet du bac à poussière et retirez-le.",
            "Retirez le filtre lavable et videz le bac à poussière.",
            "Si nécessaire, remplissez le bac d’eau propre, remettez le filtre, agitez doucement et évacuez l’eau sale.",
            "Laissez sécher le bac et le filtre avant de les remettre en place.",
        ],
        "notes": [
            "Pour éviter les obstructions, utilisez uniquement de l’eau propre, sans liquide de nettoyage.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Après chaque utilisation",
        "replace_frequency": "Tous les 3-6 mois",
        "steps": [
            "Retirez la serpillière de son support (sur certains modèles, via une vis centrale).",
            "Lavez la serpillière et laissez-la sécher à l’air libre.",
            "Remettez la serpillière à plat dans son support.",
        ],
        "notes": [
            "Une serpillière sale nuit au lavage — nettoyez-la avant utilisation.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Mensuel",
        "replace_frequency": None,
        "steps": [
            "À l’aide d’un outil, tel qu’un petit tournevis, dégagez l’axe et extrayez la roulette.",
            "Rincez la roulette et son axe à l’eau pour retirer poils et saletés.",
            "Laissez sécher à l’air libre, réinstallez et appuyez pour remettre en place.",
        ],
        "notes": [
            "Le support de la roulette omnidirectionnelle ne peut pas être retiré.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Hebdomadaire",
        "replace_frequency": None,
        "steps": [
            "Vérifiez chaque semaine les deux roulettes principales et retirez les cheveux ou fils enroulés autour des axes.",
            "Nettoyez les roulettes principales avec un chiffon doux et sec.",
        ],
        "notes": [],
    },
}

_DIRTY_WATER_TANK = {
    "clean_frequency": "Si nécessaire",
    "replace_frequency": None,
    "steps": [
        "Ouvrez le couvercle du réservoir d’eau sale et évacuez l’eau sale.",
        "Remplissez d’eau propre, refermez et verrouillez le couvercle, agitez, puis évacuez à nouveau pour rincer.",
        "Refermez le couvercle et réinstallez le réservoir.",
    ],
    "notes": [
        "N’utilisez que de l’eau froide afin d’éviter toute déformation ; essuyez l’extérieur avant de réinstaller.",
    ],
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "Tous les 1-3 mois",
    "steps": [
        "Retirez les filtres à eau du réservoir.",
        "Installez des filtres neufs et remettez-les en place.",
    ],
    "notes": [
        "À remplacer tous les 1-3 mois selon la qualité de l’eau et l’utilisation.",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "Lorsqu’il est plein (env. toutes les 7 semaines)",
    "steps": [
        "Ouvrez le couvercle du compartiment à poussière de la station.",
        "Retirez le sac à poussière plein en tirant tout droit ; la poignée le referme lors du retrait.",
        "Insérez un sac neuf et refermez le couvercle.",
    ],
    "notes": [
        "Placez toujours un sac avant de refermer le couvercle.",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "Si nécessaire",
    "replace_frequency": None,
    "steps": [
        "Retirez le réservoir d’eau propre et ouvrez le couvercle supérieur.",
        "Remplissez-le d’eau froide du robinet.",
        "Refermez le couvercle et remettez le réservoir dans la station.",
    ],
    "notes": [
        "N’utilisez que de l’eau froide pour éviter toute déformation.",
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
