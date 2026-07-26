"""Upkeep-guide translations — 한국어 (ko).

AI-DRAFT (pending native review). An OFFICIAL Korean manual DOES exist
(support.roborock.com ko-kr, e.g. "S6 MaxV KR 설명서", art 900002143603, PDF
attachment 900002896623) — but that older PDF uses a subsetted font with no
ToUnicode map, so pypdf extracts only garbled private-use glyphs. Decoding it
needs OCR (render → tesseract), unavailable in this env. So unlike the other
official locales these steps are AI-drafted; TO UPGRADE: OCR that KO PDF and
transcribe verbatim. Frequencies match the English base; overlaid PER FIELD.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "매주",
        "replace_frequency": "6~12개월마다",
        "steps": [
            "로봇을 뒤집고 걸쇠를 눌러 메인 브러시 커버를 분리합니다.",
            "메인 브러시를 꺼내고 캡과 헤어 방지 링을 제거한 뒤 양쪽 끝의 머리카락과 이물질을 제거합니다.",
            "링, 캡, 베어링을 다시 끼운 다음 메인 브러시를 장착합니다.",
            "커버의 네 개 탭을 홈에 완전히 끼우고 딸깍 소리가 날 때까지 눌러 다시 장착합니다.",
        ],
        "notes": [
            "부식성 세척액이나 소독제를 사용하지 마십시오.",
        ],
    },
    "side_brush": {
        "clean_frequency": "매월",
        "replace_frequency": "3~6개월마다",
        "steps": [
            "사이드 브러시의 나사를 풉니다.",
            "사이드 브러시를 분리하여 청소합니다.",
            "사이드 브러시를 다시 장착하고 나사를 조입니다.",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "2주마다",
        "replace_frequency": "6~12개월마다",
        "steps": [
            "물세척 가능한 필터를 분리합니다.",
            "여러 번 헹구고 가볍게 두드려 최대한 많은 이물질을 제거합니다.",
            "다시 장착하기 전에 최소 24시간 동안 완전히 건조시킵니다.",
        ],
        "notes": [
            "손, 브러시, 단단한 물체로 필터 표면을 만지지 마십시오.",
        ],
    },
    "sensor": {
        "clean_frequency": "매월",
        "replace_frequency": None,
        "steps": [
            "부드럽고 마른 천으로 모든 센서를 닦고, 로봇과 충전대의 충전 단자도 닦습니다.",
        ],
        "notes": [],
    },
    "dustbin": {
        "clean_frequency": "매주",
        "replace_frequency": None,
        "steps": [
            "자석식 상단 커버를 분리하고 먼지통 걸쇠를 눌러 먼지통을 꺼냅니다.",
            "물세척 필터를 분리하고 먼지통을 비웁니다.",
            "필요한 경우 깨끗한 물을 채우고 필터를 끼운 뒤 가볍게 흔들어 오염된 물을 버립니다.",
            "다시 장착하기 전에 먼지통과 필터를 건조시킵니다.",
        ],
        "notes": [
            "세제를 넣지 말고 깨끗한 물만 사용하십시오.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "사용 후 매번",
        "replace_frequency": "3~6개월마다",
        "steps": [
            "거치대에서 걸레를 분리합니다.",
            "걸레를 세척하고 자연 건조시킵니다.",
            "걸레를 거치대에 평평하게 다시 장착합니다.",
        ],
        "notes": [
            "더러운 걸레는 물걸레질 성능을 떨어뜨리므로 사용 전에 세척하십시오.",
        ],
    },
}

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD},
    "wash_station": {**_STANDARD},
}
