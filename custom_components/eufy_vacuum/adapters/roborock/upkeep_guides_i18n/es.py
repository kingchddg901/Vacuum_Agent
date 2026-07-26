"""Upkeep-guide translations — Español (es).

Transcribed from Roborock's official Spanish manual (S8 MaxV Ultra CE ES).
Frequencies match our English base; steps/notes are the official wording.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Semanal",
        "replace_frequency": "Cada 6-12 meses",
        "steps": [
            "Dé la vuelta al robot, presione el pestillo y retire la tapa del cepillo principal.",
            "Extraiga el cepillo principal, retire las tapas y los anillos antienredos y elimine los cabellos y la suciedad de ambos extremos.",
            "Vuelva a colocar los anillos, las tapas y los rodamientos y, a continuación, el cepillo principal.",
            "Vuelva a colocar la tapa: introduzca las cuatro pestañas por completo en las ranuras y presione hasta oír un clic.",
        ],
        "notes": [
            "Limpie el cepillo principal con un paño húmedo; si está mojado, déjelo secar al aire y protegido de la luz solar directa.",
            "No utilice líquidos de limpieza corrosivos ni desinfectantes.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Mensual",
        "replace_frequency": "Cada 3-6 meses",
        "steps": [
            "Desenrosque el tornillo del cepillo lateral.",
            "Retire y limpie el cepillo lateral.",
            "Vuelva a colocar el cepillo y apriete el tornillo.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "Cada 2 semanas",
        "replace_frequency": "Cada 6-12 meses",
        "steps": [
            "Retire el filtro lavable.",
            "Enjuáguelo varias veces y golpéelo suavemente para eliminar toda la suciedad posible.",
            "Deje que el filtro se seque bien durante al menos 24 horas antes de volver a colocarlo.",
        ],
        "notes": [
            "No toque la superficie del filtro con las manos, un cepillo ni objetos duros.",
            "Se recomienda tener un segundo filtro para alternarlo si es necesario.",
        ],
    },
    "sensor": {
        "clean_frequency": "Mensual",
        "replace_frequency": None,
        "steps": [
            "Limpie todos los sensores con un paño suave y seco: sensor de obstáculos Reactive AI, localizador de la estación, sensor de alfombras, sensor de pared, sensor de comunicación y sensores de vacío.",
            "Limpie también los contactos de carga del robot y de la estación.",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "Semanal",
        "replace_frequency": None,
        "steps": [
            "Retire la tapa superior magnética, presione el pestillo del depósito de polvo y extráigalo.",
            "Extraiga el filtro lavable y vacíe el depósito de polvo.",
            "Si es necesario, llene el depósito con agua limpia, vuelva a instalar el filtro, agítelo suavemente y vacíe el agua sucia.",
            "Deje que el depósito de polvo y el filtro se sequen bien antes de volver a colocarlos.",
        ],
        "notes": [
            "Para evitar posibles atascos, use solo agua limpia, sin ningún tipo de limpiador líquido.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Después de cada uso",
        "replace_frequency": "Cada 3-6 meses",
        "steps": [
            "Retire la mopa de su soporte (en algunos modelos, mediante un tornillo central).",
            "Lave la mopa y déjela secar al aire.",
            "Vuelva a colocar la mopa plana en su soporte.",
        ],
        "notes": [
            "Una mopa sucia afecta al fregado; límpiela antes de usarla.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Mensual",
        "replace_frequency": None,
        "steps": [
            "Con una herramienta, como un destornillador pequeño, extraiga la rueda haciendo palanca en el eje.",
            "Enjuague el eje y la rueda con agua para eliminar la suciedad y los cabellos atrapados.",
            "Deje secar al aire y vuelva a montar la rueda y el eje en su sitio mediante presión.",
        ],
        "notes": [
            "El soporte de la rueda omnidireccional no se puede extraer.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Semanal",
        "replace_frequency": None,
        "steps": [
            "Compruebe cada semana las dos ruedas principales y elimine los cabellos o hilos enrollados en los ejes.",
            "Limpie las ruedas principales con un paño suave y seco.",
        ],
        "notes": [],
    },
}

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD},
    "wash_station": {**_STANDARD},
}
