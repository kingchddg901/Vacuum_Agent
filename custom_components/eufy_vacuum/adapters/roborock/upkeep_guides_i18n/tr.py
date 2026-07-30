"""Upkeep-guide translations — Türkçe (tr).

Per-language module under roborock/upkeep_guides_i18n/; __init__.py assembles them
into ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS. Pure data.

Best-effort AI draft TRANSLATED from the English base library
(roborock_upkeep_guides.py) — pending native (tr) review. Frequencies match our
English base (not any source model's) so the interval reads the same in every
language. Overlaid PER FIELD on the English guide — anything omitted falls back to
English.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Haftalık",
        "replace_frequency": "Her 6-12 ayda bir",
        "steps": [
            "Robotu ters çevirin ve mandala bastırarak ana fırça kapağını serbest bırakın.",
            "Ana fırçayı çıkarın, ardından her iki uçtaki yatak kapağını çekip çıkararak temizleyin.",
            "Birlikte verilen temizleme aracıyla fırçaya ve yataklara dolanmış saçları kesip çıkarın.",
            "Yatak kapaklarını ve fırça kapağını kilitleme yönünde yerine takın, ardından mandal tıklayana kadar kapağa bastırın.",
        ],
        "notes": [
            "Yerine takmadan önce fırça bölmesi kirli görünüyorsa silin.",
            "En iyi temizlik için ana fırçayı her 6-12 ayda bir değiştirin.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Aylık",
        "replace_frequency": "Her 3-6 ayda bir",
        "steps": [
            "Robotu ters çevirin ve yan fırçayı tutan vidayı sökün.",
            "Yan fırçayı çıkarın ve mile dolanmış saç veya kirleri temizleyin.",
            "Yan fırçayı yerine takın ve vidayı sıkın.",
        ],
        "notes": [
            "Yan fırçayı her 3-6 ayda bir, eğilmiş veya dağılmışsa daha erken değiştirin.",
        ],
    },
    "filter": {
        "clean_frequency": "Her 2 haftada bir",
        "replace_frequency": "Her 6-12 ayda bir",
        "steps": [
            "Toz haznesi mandalına bastırın, hazneyi çıkarın, kapağını açıp boşaltın.",
            "Yıkanabilir filtreyi çıkarın ve temiz suyla durulayın — deterjan kullanmayın.",
            "Sıkışan tozu gevşetmek için filtre çerçevesini sert bir yüzeye vurun ve temizlenene kadar durulayın.",
            "Yerine takmadan önce filtreyi en az 24 saat açık havada kurutun.",
        ],
        "notes": [
            "Filtrede asla deterjan, sıcak su, bulaşık makinesi veya saç kurutma makinesi kullanmayın.",
            "Yedek bir filtre bulundurmak, biri kullanılırken diğerinin tamamen kurumasını sağlar.",
        ],
    },
    "sensor": {
        "clean_frequency": "Aylık",
        "replace_frequency": None,
        "steps": [
            "Alt taraftaki altı uçurum sensörünü yumuşak, kuru bir bezle silin.",
            "Sağ kenardaki duvar sensörünü ve şarj sensörünü silin.",
            "Aynı anda alt taraftaki şarj kontaklarını da silin.",
        ],
        "notes": [
            "Yalnızca kuru bez kullanın — temizlik sıvıları sensör kapaklarına zarar verebilir.",
        ],
    },
    "dustbin": {
        "clean_frequency": "Haftalık",
        "replace_frequency": None,
        "steps": [
            "Üst kapağı açın, toz haznesi mandalına bastırın ve hazneyi çıkarın.",
            "Toz haznesi kapağını açın ve içindekileri çöpe boşaltın.",
            "Gerektiğinde toz haznesini temiz suyla durulayın — önce filtreyi çıkarın ve deterjan kullanmayın.",
        ],
        "notes": [
            "Nemli tozun filtreyi tıkamaması için toz haznesini yerine takmadan önce tamamen kurutun.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Her kullanımdan sonra",
        "replace_frequency": "Her 3-6 ayda bir",
        "steps": [
            "Her paspaslama işleminden sonra paspas bezini paspaslama modülünden çıkarın.",
            "Temizlenene kadar durulayın ve kurumaya bırakın.",
        ],
        "notes": [
            "Kirli suyun tanka geri kaçıp filtreyi tıkamaması için temizlik amacıyla bezi her zaman çıkarın.",
            "Yeniden kullanılabilir bezi her 3-6 ayda bir değiştirin; tek kullanımlık bezi her kullanımdan sonra değiştirin.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Aylık",
        "replace_frequency": None,
        "steps": [
            "Robotu ters çevirin ve çok yönlü (ön döner) tekerleği kaldırarak çıkarın.",
            "Tekerlek gövdesine ve aksa dolanmış saç ve kirleri temizleyin.",
            "Tekerleği sıkıca yerine bastırın.",
        ],
        "notes": [
            "Tekerlek yuvası çıkarılamaz — yalnızca tekerlek gövdesi çıkar.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Haftalık",
        "replace_frequency": None,
        "steps": [
            "Haftada bir, her iki ana tahrik tekerleğini akslara dolanmış saç veya iplik açısından kontrol edin.",
            "Tekerleklerin serbestçe dönmesi için sıkışan her şeyi kesip çıkarın.",
            "Kir yapışmışsa tekerlekleri hafif nemli bir bezle silin.",
        ],
        "notes": [
            "Serbestçe dönen tekerlekler, robotun düz gitmesini ve eşikleri aşmasını sağlar.",
        ],
    },
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "Her 1-3 ayda bir",
    "steps": [
        "Su filtrelerini kılavuzda gösterildiği gibi tanktan çekip çıkarın.",
        "Yeni filtreleri takın ve yerine kaydırın.",
    ],
    "notes": [
        "Su kalitenize ve ne sıklıkta paspasladığınıza bağlı olarak her 1-3 ayda bir değiştirin.",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "Dolduğunda (yaklaşık her 7 haftada bir)",
    "steps": [
        "Şarj istasyonunun toz bölmesi kapağını açın.",
        "Dolu toz torbasını düz bir şekilde çekip çıkarın — tutamak çekerken torbayı kapatır, böylece toz içeride kalır.",
        "Yeni bir toz torbasını yerine oturana kadar itin, ardından kapağı kapatın.",
    ],
    "notes": [
        "Kapağı kapatmadan önce her zaman bir torba takılı olsun, aksi halde şarj istasyonu torbasız otomatik boşaltma yapar.",
        "Şarj istasyonu bir süre kullanılmadıysa, robotun toz haznesini elle boşaltın ve hava girişinin açık olduğunu kontrol edin.",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "Gerektiğinde",
    "replace_frequency": None,
    "steps": [
        "Temiz su tankını şarj istasyonundan çıkarın ve üst kapağını açın.",
        "Serin musluk suyuyla doldurun (yalnızca şarj istasyonunuz destekliyorsa Roborock temizlik solüsyonu ekleyin).",
        "Kapağı kapatın ve tankı şarj istasyonundaki yerine oturtun.",
    ],
    "notes": [
        "Yalnızca serin su kullanın — sıcak su tankı deforme edebilir.",
        "Yerine takmadan önce dış yüzeydeki suyu silin.",
    ],
}
_DIRTY_WATER_TANK = {
    "clean_frequency": "Gerektiğinde",
    "replace_frequency": None,
    "steps": [
        "Kirli su tankının kapağını açın ve atık suyu boşaltın.",
        "Biraz temiz su ekleyin, kapağı kapatıp kilitleyin, çalkalayın, ardından durulamak için tekrar boşaltın.",
        "Kapağı kilitleyin ve tankı şarj istasyonundaki yerine oturtun.",
    ],
    "notes": [
        "Kirli su kapağı çıkmaz — yerinde durulayın.",
        "Yalnızca serin su kullanın ve yerine takmadan önce dış yüzeyi kurulayın.",
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
