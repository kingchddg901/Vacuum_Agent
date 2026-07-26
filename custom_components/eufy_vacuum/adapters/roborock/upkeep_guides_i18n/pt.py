"""Upkeep-guide translations — Português (pt).

Transcribed from Roborock's official Portuguese manual (S8 MaxV Ultra CE PT).
Frequencies match our English base; steps/notes are the official wording.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Semanal",
        "replace_frequency": "A cada 6-12 meses",
        "steps": [
            "Vire o robô ao contrário, prima o fecho e retire a tampa da escova principal.",
            "Retire a escova principal, remova as tampas e os anéis anti-cabelo e elimine cabelos e sujidade em ambas as extremidades.",
            "Volte a colocar os anéis, as tampas e os rolamentos e, em seguida, a escova principal.",
            "Volte a colocar a tampa: insira totalmente as quatro linguetas nas ranhuras e prima até ouvir um clique.",
        ],
        "notes": [
            "Limpe a escova principal com um pano húmido; se estiver molhada, deixe secar ao ar, ao abrigo da luz solar direta.",
            "Não utilize líquidos de limpeza corrosivos nem desinfetantes.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Mensal",
        "replace_frequency": "A cada 3-6 meses",
        "steps": [
            "Desaperte o parafuso da escova lateral.",
            "Retire e limpe a escova lateral.",
            "Volte a colocar a escova e aperte o parafuso.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "A cada 2 semanas",
        "replace_frequency": "A cada 6-12 meses",
        "steps": [
            "Retire o filtro lavável.",
            "Enxague-o várias vezes e bata-lhe delicadamente para remover o máximo de sujidade possível.",
            "Aguarde pelo menos 24 horas para que o filtro seque bem antes de o voltar a colocar.",
        ],
        "notes": [
            "Não toque na superfície do filtro com as mãos, escovas ou objetos duros.",
            "Recomenda-se ter um segundo filtro para alternar, se necessário.",
        ],
    },
    "sensor": {
        "clean_frequency": "Mensal",
        "replace_frequency": None,
        "steps": [
            "Limpe todos os sensores com um pano macio e seco: sensor de obstáculos Reactive AI, localizador da estação, sensor de tapetes, sensor de parede, sensor de comunicação e sensores de queda.",
            "Limpe também os contactos de carregamento do robô e da estação.",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "Semanal",
        "replace_frequency": None,
        "steps": [
            "Retire a tampa superior magnética, prima o fecho do compartimento do lixo e retire-o.",
            "Retire o filtro lavável e esvazie o compartimento do lixo.",
            "Se necessário, encha o compartimento com água limpa, volte a colocar o filtro, agite suavemente e deite fora a água suja.",
            "Deixe secar o compartimento do lixo e o filtro antes de os voltar a colocar.",
        ],
        "notes": [
            "Para evitar obstruções, utilize apenas água limpa, sem qualquer líquido de limpeza.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Após cada utilização",
        "replace_frequency": "A cada 3-6 meses",
        "steps": [
            "Retire o pano da mopa do suporte (em alguns modelos, através de um parafuso central).",
            "Lave o pano da mopa e deixe-o secar ao ar.",
            "Volte a colocar o pano da mopa plano no suporte.",
        ],
        "notes": [
            "Um pano sujo prejudica a limpeza; lave-o antes de utilizar.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Mensal",
        "replace_frequency": None,
        "steps": [
            "Com uma ferramenta, como uma pequena chave de fendas, retire o eixo e extraia a roda.",
            "Lave a roda e o eixo com água para remover cabelos e sujidade.",
            "Deixe secar ao ar, volte a colocar e exerça pressão sobre a roda e o eixo para os encaixar.",
        ],
        "notes": [
            "O suporte da roda omnidirecional não pode ser retirado.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Semanal",
        "replace_frequency": None,
        "steps": [
            "Verifique semanalmente as duas rodas principais e remova cabelos ou fios enrolados nos eixos.",
            "Limpe as rodas principais com um pano macio e seco.",
        ],
        "notes": [],
    },
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "A cada 1-3 meses",
    "steps": [
        "Retire os filtros de água do depósito.",
        "Coloque filtros novos e volte a encaixá-los.",
    ],
    "notes": [
        "Substitua-os a cada 1-3 meses consoante a qualidade da água e a utilização.",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "Quando estiver cheio (cerca de 7 semanas)",
    "steps": [
        "Abra a tampa do compartimento de pó da estação.",
        "Retire o saco de pó cheio puxando a direito; a pega sela-o ao retirar.",
        "Introduza um saco novo e feche a tampa.",
    ],
    "notes": [
        "Coloque sempre um saco antes de fechar a tampa.",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "Se necessário",
    "replace_frequency": None,
    "steps": [
        "Retire o depósito de água limpa e abra a tampa superior.",
        "Encha-o com água fria da torneira.",
        "Feche a tampa e volte a colocar o depósito na estação.",
    ],
    "notes": [
        "Utilize apenas água fria para evitar deformações.",
    ],
}
_DIRTY_WATER_TANK = {
    "clean_frequency": "Se necessário",
    "replace_frequency": None,
    "steps": [
        "Abra a tampa do depósito de água suja e despeje a água suja.",
        "Adicione água limpa, feche a tampa, agite e despeje novamente para enxaguar.",
        "Feche a tampa e volte a colocar o depósito.",
    ],
    "notes": [
        "Utilize apenas água fria; limpe o exterior antes de colocar.",
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
