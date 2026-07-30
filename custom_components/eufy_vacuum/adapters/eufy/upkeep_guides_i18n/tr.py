"""Upkeep-guide translations — Türkçe (tr).

One of the per-language modules under ``upkeep_guides_i18n/``; ``__init__.py``
assembles them into ``UPKEEP_GUIDE_TRANSLATIONS``. Pure data.

Shape::

    GUIDE_TRANSLATIONS[guide_family][component] = {
        "steps": list[str], "notes": list[str],
        "clean_frequency": str, "replace_frequency": str | None,
    }

mirrors a subset of ``UPKEEP_GUIDE_LIBRARY`` (../upkeep_guides.py). Any family,
component, or field left out falls back to English PER FIELD at overlay time, so
partial edits are safe. This module is a best-effort AI-generated DRAFT,
translated from the English source of truth and PENDING NATIVE REVIEW — wording,
plural forms, and terminology should be verified by a fluent Turkish speaker
before being treated as final. After editing, regenerate the frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {
    "x10_pro_omni": {
        "filter": {
            "clean_frequency": "Haftada bir",
            "replace_frequency": "Her 3-6 ayda bir",
            "steps": [
                "Üst kapağı açın ve toz haznesini çıkarın.",
                "Filtreyi toz haznesinden çıkarın.",
                "Filtreye vurarak tozunu alın ve toz haznesini boşaltın.",
                "Toz haznesini ve filtreyi yalnızca suyla durulayın.",
                "Yeniden takmadan önce her iki parçayı da tamamen kurumaya bırakın.",
            ],
            "notes": [
                "Fırça, sıcak su veya deterjan kullanmayın.",
                "Filtreyi her 3-6 ayda bir değiştirin.",
            ],
        },
        "rolling_brush": {
            "clean_frequency": "Ayda bir",
            "replace_frequency": "Her 6 ayda bir",
            "steps": [
                "Fırça koruma tırnaklarını açın ve korumayı kaldırarak çıkarın.",
                "Ana fırçayı çıkarın.",
                "Sarılmış saç ve kalıntıları keserek temizleyin.",
                "Fırçayı ve korumayı durulayın, ardından kurumaya bırakın.",
                "Fırçayı yeniden takın ve korumayı yerine oturtun.",
            ],
            "notes": [
                "Fırça koruması da her 3-6 ayda bir veya aşındığında değiştirilmelidir.",
            ],
        },
        "side_brush": {
            "clean_frequency": "Ayda bir",
            "replace_frequency": "Her 3-6 ayda bir veya aşındığında",
            "steps": [
                "Yan fırçayı bir tornavida ile çıkarın.",
                "Saç veya kalıntıları çözerek temizleyin.",
                "Fırçayı suyla durulayın ve tamamen kurumaya bırakın.",
                "Fırça kuruduktan sonra yeniden takın.",
            ],
            "notes": [],
        },
        "sensor": {
            "clean_frequency": "Ayda bir",
            "replace_frequency": None,
            "steps": [
                "Sensörleri ve kameraları silmek için yumuşak, kuru bir bez kullanın.",
                "Sensör bakımı yaparken şarj pinlerini de silin.",
            ],
            "notes": [
                "Kılavuzda sensörler için bir değiştirme aralığı belirtilmemiştir.",
            ],
        },
        "cleaning_tray": {
            "clean_frequency": "Gerektiğinde",
            "replace_frequency": None,
            "steps": [
                "Temizleme tepsisini Omni İstasyonu'ndan çıkarın.",
                "Tepsiyi suyla iyice durulayın.",
                "Temizledikten sonra tepsiyi yeniden takın.",
            ],
            "notes": [
                "Kirli su deposu dolduğunda boşaltılmalı ve durulanmalıdır.",
            ],
        },
        "mopping_cloth": {
            "clean_frequency": "Kullanımdan sonra yıkayın / düzenli olarak kontrol edin",
            "replace_frequency": "Her 3-6 ayda bir",
            "steps": [
                "Paspas bezlerini robottan çıkarın.",
                "Bezleri yeniden kullanmadan önce yıkayın ve tamamen kurutun.",
                "Bezler aşındığında veya artık etkili temizlemediğinde değiştirin.",
            ],
            "notes": [],
        },
        "swivel_wheel": {
            "clean_frequency": "Ayda bir",
            "replace_frequency": None,
            "steps": [
                "Döner tekerlekte sarılmış saç veya kalıntı olup olmadığını kontrol edin.",
                "Kalıntıları dikkatlice temizleyin ve tekerlek bölgesini silin.",
                "Bir sonraki çalıştırmadan önce tekerleğin serbestçe döndüğünü doğrulayın.",
            ],
            "notes": [
                "Kılavuz döner tekerlek temizliğini belirtir ancak özel bir değiştirme aralığı vermez.",
            ],
        },
    },
    "s1_pro": {
        "filter": {
            "steps": [
                "Yüksek performanslı filtreyi toz haznesi bölgesinden çıkarın.",
                "Toz ve kalıntıları nazikçe silkeleyin.",
                "Filtre temiz ve kuru olduğunda yeniden takın veya değiştirin.",
            ],
            "notes": [
                "Uygulamadaki aksesuar servis rehberi, S1 Pro için birincil resmi sıfırlama akışıdır.",
            ],
        },
        "sensor": {
            "steps": [
                "Robot sensörlerini yumuşak, kuru bir bezle silin.",
                "Sensörlerin bakımını yaparken şarj kontaklarını da temizleyin.",
            ],
        },
        "side_brush": {
            "steps": [
                "Yan fırçada sıkışmış saç ve kalıntı olup olmadığını kontrol edin.",
                "Taban ve kılların çevresindeki birikintileri temizleyin.",
                "Kıllar bükülmüş veya hasarlıysa fırçayı değiştirin.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Ana fırça korumasını çıkarın.",
                "Fırçayı ve her iki uç kapağını dolaşmış saç veya kalıntı için kontrol edin.",
                "Yeniden takmadan önce fırçayı iyice temizleyin.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Döner paspası veya paspas temas yüzeylerini çıkarın ve kalıntıları temizleyin.",
                "Temizlenen parçaları yeniden kullanmadan önce kurumaya bırakın.",
                "Aşınma görünür hale geldiğinde veya performans düştüğünde paspasla ilgili sarf malzemesini değiştirin.",
            ],
            "notes": [
                "S1 belgeleri, çıkarılabilir ikiz ped ifadesinden ziyade döner paspas odaklıdır.",
            ],
        },
        "cleaning_tray": {
            "steps": [
                "Filtre tepsisini veya tepsi eklentisini istasyon bölgesinden çıkarın.",
                "Kalıntı ve birikintileri durulayarak temizleyin.",
                "Temizledikten sonra yeniden takın.",
            ],
            "notes": [
                "Gerektiğinde temiz/kirli su depolarını ve kirli su filtresini de temizleyin.",
            ],
        },
        "swivel_wheel": {
            "steps": [
                "Döner tekerlekte saç ve kalıntı olup olmadığını kontrol edin.",
                "Birikintileri temizleyin ve tekerleğin serbestçe döndüğünü doğrulayın.",
            ],
        },
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Toz haznesini veya filtre bölmesini çıkarın.",
                "Filtreyi çıkarın ve vurarak tozunu alın.",
                "Yalnızca kılavuz/uygulama rehberi izin veriyorsa yıkayın, ardından yeniden takmadan önce tamamen kurutun.",
            ],
            "notes": [
                "Omni C20 aksesuar rehberi ağırlıklı olarak videoya dayalıdır.",
            ],
        },
        "sensor": {
            "steps": [
                "Hem robottaki hem de istasyondaki sensörleri ve şarj kontaklarını silmek için temiz, kuru bir bez kullanın.",
            ],
        },
        "side_brush": {
            "steps": [
                "Yan fırçada aşınma, dolaşma veya hasar olup olmadığını kontrol edin.",
                "Fırçadan ve tabandan sarılmış saç ve kalıntıları temizleyin.",
                "Kıllar bükülmüş veya eksikse fırçayı değiştirin.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Ana fırçada dolaşmış saç veya kalıntı olup olmadığını kontrol edin.",
                "Sarılmış malzemeyi kesmek için temizleme aracını veya makası kullanın.",
                "Temizledikten sonra yeniden takın.",
            ],
            "notes": [
                "Pro-Detangle Tarağı manuel temizliği azaltır ancak ortadan kaldırmaz.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Paspas bezlerini robottan veya istasyondan çıkarın.",
                "Yeniden kullanmadan önce temizleyin ve tamamen kurutun.",
                "Bezler aşındığında veya artık etkili temizlemediğinde değiştirin.",
            ],
        },
        "cleaning_tray": {
            "steps": [
                "İstasyon tabanını veya paspas yıkama bölgesi bileşenini ayırın.",
                "Tepsi bölgesindeki kalıntıları durulayın ve silin.",
                "Temizledikten sonra tepsiyi yeniden takın.",
            ],
            "notes": [
                "Temiz ve kirli su depolarını da izleyin ve bakımını yapın.",
            ],
        },
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Toz haznesini çıkarın ve filtreyi dışarı alın.",
                "Tozunu almak için filtreye nazikçe vurun.",
                "Durulandıysa, yeniden takmadan önce tamamen kurumaya bırakın.",
            ],
        },
        "sensor": {
            "steps": [
                "Düşme sensörlerini, tampon sensörlerini ve şarj kontaklarını kuru bir bezle silin.",
            ],
        },
        "side_brush": {
            "steps": [
                "Yan fırçayı çıkarın.",
                "Fırçadan ve tabanından saç ve kalıntıları temizleyin.",
                "Aşınmışsa yeniden takın veya değiştirin.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Ana fırça koruma tırnaklarını sıkın ve korumayı çıkarın.",
                "Ana fırçayı kaldırarak çıkarın.",
                "Saç ve kalıntıları temizlemek için temizleme aracını veya makası kullanın.",
                "Fırçayı ve korumayı yeniden takın.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Paspas bezini tutucusundan çıkarın.",
                "Yeniden kullanmadan önce yıkayın ve kurutun.",
                "Aşınır veya etkisiz hale gelirse değiştirin.",
            ],
            "notes": [
                "Yalnızca hibrit/paspas yapabilen X8 modelleri için geçerlidir.",
            ],
        },
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Toz haznesi serbest bırakma düğmesine basın ve toz haznesini çıkarın.",
                "Filtreyi çıkarın ve vurarak gevşek kiri alın.",
                "İlgili model kılavuzu izin veriyorsa, yeniden takmadan önce durulayın ve tamamen kurutun.",
            ],
        },
        "sensor": {
            "steps": [
                "Robottaki ve istasyondaki sensörleri ve şarj kontaklarını silmek için kuru bir bez kullanın.",
            ],
        },
        "side_brush": {
            "steps": [
                "Yan fırçayı çekerek çıkarın.",
                "Dolaşmış saç ve kalıntıları temizleyin.",
                "Aşınmışsa yeniden takın veya değiştirin.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Ana fırça kapağını çıkarın.",
                "Ana fırçayı kaldırarak çıkarın.",
                "Fırçadaki ve yataklardaki sarılmış saç ve kalıntıları temizleyin.",
                "Silerek kurulayın, ardından fırçayı ve korumayı yeniden takın.",
            ],
            "notes": [
                "SES modelleri, bakımı azaltmak için otomatik saç kesme özelliğini de kullanır.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Paspas pedini veya bezini çıkarın.",
                "Yeniden kullanmadan önce temizleyin ve tamamen kurutun.",
                "Bez aşındığında değiştirin.",
            ],
            "notes": [
                "Yalnızca hibrit varyantlar için geçerlidir.",
            ],
        },
    },
}
