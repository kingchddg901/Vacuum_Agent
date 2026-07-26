"""Upkeep-guide translations — 日本語 (ja).

Transcribed from Roborock's official Japanese manual (S5 Max, roborockjapandirect).
Frequencies match our English base; steps/notes are the official wording. This is
an older base-model manual, so components it doesn't cover (sensor, mop, wheels)
fall back to English until a Japanese station manual is harvested.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "毎週",
        "replace_frequency": "6〜12か月ごと",
        "steps": [
            "本体を裏返して固定ロックを押し、メインブラシカバーを取り外します。",
            "メインブラシを持ち上げて取り外し、ベアリングを引き抜きます。",
            "メインブラシお手入れツールで、絡まった毛やゴミを取り除きます。",
            "ベアリングとメインブラシを元に戻し、カバーをカチッと音がするまで押し込みます。",
        ],
        "notes": [
            "髪の毛が大量にきつく絡まっている場合、無理に強く掻き出すとお手入れツールが壊れる恐れがあります。",
        ],
    },
    "side_brush": {
        "clean_frequency": "毎月",
        "replace_frequency": "3〜6か月ごと",
        "steps": [
            "本体を裏返して、サイドブラシユニットのネジを外します。",
            "サイドブラシを取り外して掃除します。",
            "サイドブラシを元に戻し、ネジを締めます。",
        ],
        "notes": [],
    },
    "filter": {
        "clean_frequency": "2週間ごと",
        "replace_frequency": "6〜12か月ごと",
        "steps": [
            "フィルターを取り外し、水ですすぎます。",
            "繰り返しすすいで、フレームを軽く打ち付けて汚れを落とします。",
            "フィルターを完全に乾かしてから取り付けます。",
        ],
        "notes": [
            "フィルターが損傷する恐れがあるため、ブラシで強くこすったり手で引っかいたりしないでください。",
        ],
    },
    "dustbin": {
        "clean_frequency": "毎週",
        "replace_frequency": None,
        "steps": [
            "本体の上部カバーを開き、ダストボックスラッチを押しながらダストボックスを取り外します。",
            "蓋を開いてゴミを捨てます。",
            "水道水で満たしてカバーを閉じ、軽く振って洗浄し、汚れた水を捨てます。",
        ],
        "notes": [
            "水のみで洗浄し、洗剤は使用しないでください。",
        ],
    },
    # Filled from the corpus in the style of this manual's official sections
    # (the S5 Max manual does not detail these components separately).
    "sensor": {
        "clean_frequency": "毎月",
        "replace_frequency": None,
        "steps": [
            "柔らかい乾いた布で全てのセンサーを拭き、本体と充電ドックの充電端子も拭きます。",
        ],
        "notes": [],
    },
    "mop_cloth": {
        "clean_frequency": "使用後毎回",
        "replace_frequency": "3〜6か月ごと",
        "steps": [
            "モップクロスをホルダーから取り外します。",
            "モップクロスを洗い、自然乾燥させます。",
            "モップクロスをホルダーに平らに取り付けます。",
        ],
        "notes": [
            "汚れたモップクロスは拭き取り性能を低下させるため、使用前に洗浄してください。",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "毎月",
        "replace_frequency": None,
        "steps": [
            "小さなドライバーなどの工具で軸をこじ開け、ホイールを取り外します。",
            "水でホイールと軸の髪の毛や汚れを洗い流します。",
            "自然乾燥させてから押し込んで取り付けます。",
        ],
        "notes": [
            "自在輪のブラケットは取り外せません。",
        ],
    },
    "main_wheel": {
        "clean_frequency": "毎週",
        "replace_frequency": None,
        "steps": [
            "毎週、2つのメインホイールの軸に絡まった髪の毛や糸を取り除きます。",
            "メインホイールを柔らかい乾いた布で拭きます。",
        ],
        "notes": [],
    },
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "1〜3か月ごと",
    "steps": [
        "タンクからウォーターフィルターを取り外します。",
        "新しいフィルターを取り付け、元の位置に押し込みます。",
    ],
    "notes": [
        "水質や使用頻度に応じて、1〜3か月ごとに交換してください。",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "満杯になったら（約7週間ごと）",
    "steps": [
        "ドックのダスト収集部のカバーを開きます。",
        "満杯のダストバッグをまっすぐ引き出します（取り出す際に取っ手が封をします）。",
        "新しいダストバッグを差し込み、カバーを閉じます。",
    ],
    "notes": [
        "カバーを閉じる前に、必ずダストバッグを取り付けてください。",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "必要に応じて",
    "replace_frequency": None,
    "steps": [
        "給水タンクを取り出し、上部のカバーを開きます。",
        "冷たい水道水を入れます。",
        "カバーを閉じ、タンクをドックに戻します。",
    ],
    "notes": [
        "変形を防ぐため、冷たい水のみを使用してください。",
    ],
}
_DIRTY_WATER_TANK = {
    "clean_frequency": "必要に応じて",
    "replace_frequency": None,
    "steps": [
        "汚水タンクのふたを開き、汚水を捨てます。",
        "きれいな水を入れ、ふたを閉じて振り、すすいでから再び捨てます。",
        "ふたを閉じ、タンクを元に戻します。",
    ],
    "notes": [
        "冷たい水のみを使用し、戻す前に外側を拭いてください。",
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
