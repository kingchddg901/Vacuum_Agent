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
}

GUIDE_TRANSLATIONS = {
    "standard": _STANDARD,
    "auto_empty": {**_STANDARD},
    "wash_station": {**_STANDARD},
}
