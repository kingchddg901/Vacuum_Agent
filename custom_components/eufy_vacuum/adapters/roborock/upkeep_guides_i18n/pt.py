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

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD},
    "wash_station": {**_STANDARD},
}
