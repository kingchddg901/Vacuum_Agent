"""Upkeep-guide translations — Indonesian (id).

One of the per-language modules under ``upkeep_guides_i18n/``; ``__init__.py``
assembles them into ``UPKEEP_GUIDE_TRANSLATIONS``. Pure data.

Shape::

    GUIDE_TRANSLATIONS[guide_family][component] = {
        "steps": list[str], "notes": list[str],
        "clean_frequency": str, "replace_frequency": str | None,
    }

mirrors a subset of ``UPKEEP_GUIDE_LIBRARY`` (../upkeep_guides.py). Any family,
component, or field left out falls back to English PER FIELD at overlay time, so
partial edits are safe. This module is a best-effort AI-generated draft
translated from the English source of truth and is pending native review.
After editing, regenerate the frontend bundle::

    python scripts/sync-guide-translations.py
"""

GUIDE_TRANSLATIONS = {
    "x10_pro_omni": {
        "filter": {
            "clean_frequency": "Setiap minggu",
            "replace_frequency": "Setiap 3-6 bulan",
            "steps": [
                "Buka penutup atas dan keluarkan kotak debu.",
                "Keluarkan filter dari kotak debu.",
                "Ketuk-ketuk filter untuk melepaskan debu dan kosongkan kotak debu.",
                "Bilas kotak debu dan filter hanya dengan air.",
                "Biarkan kedua bagian kering sepenuhnya dengan diangin-anginkan sebelum dipasang kembali.",
            ],
            "notes": [
                "Jangan gunakan sikat, air panas, atau deterjen.",
                "Ganti filter setiap 3-6 bulan.",
            ],
        },
        "sensor": {
            "clean_frequency": "Setiap bulan",
            "replace_frequency": None,
            "steps": [
                "Gunakan kain lembut dan kering untuk menyeka sensor dan kamera.",
                "Seka juga pin pengisian daya saat melakukan perawatan sensor.",
            ],
            "notes": [
                "Tidak ada interval penggantian yang tercantum untuk sensor dalam manual.",
            ],
        },
        "side_brush": {
            "clean_frequency": "Setiap bulan",
            "replace_frequency": "Setiap 3-6 bulan atau saat aus",
            "steps": [
                "Lepaskan sikat samping menggunakan obeng.",
                "Uraikan dan singkirkan rambut atau kotoran yang ada.",
                "Bilas sikat dengan air dan keringkan sepenuhnya dengan diangin-anginkan.",
                "Pasang kembali sikat setelah kering.",
            ],
            "notes": [],
        },
        "rolling_brush": {
            "clean_frequency": "Setiap bulan",
            "replace_frequency": "Setiap 6 bulan",
            "steps": [
                "Buka kait pelindung sikat dan angkat pelindungnya keluar.",
                "Keluarkan sikat gulung.",
                "Potong dan singkirkan rambut serta kotoran yang melilit.",
                "Bilas sikat dan pelindungnya, lalu keringkan dengan diangin-anginkan.",
                "Pasang kembali sikat dan kancingkan pelindungnya hingga terpasang di tempatnya.",
            ],
            "notes": [
                "Pelindung sikat juga sebaiknya diganti setiap 3-6 bulan atau saat aus.",
            ],
        },
        "mopping_cloth": {
            "clean_frequency": "Cuci setelah digunakan / periksa secara berkala",
            "replace_frequency": "Setiap 3-6 bulan",
            "steps": [
                "Lepaskan kain pel dari robot.",
                "Cuci dan keringkan kain pel sepenuhnya sebelum digunakan kembali.",
                "Ganti kain pel jika sudah aus atau tidak lagi membersihkan secara efektif.",
            ],
            "notes": [],
        },
        "cleaning_tray": {
            "clean_frequency": None,
            "replace_frequency": None,
            "steps": [
                "Keluarkan baki pembersih dari Omni Station.",
                "Bilas baki secara menyeluruh dengan air.",
                "Pasang kembali baki setelah dibersihkan.",
            ],
            "notes": [
                "Tangki air kotor sebaiknya dikosongkan dan dibilas saat penuh.",
            ],
        },
        "swivel_wheel": {
            "clean_frequency": "Setiap bulan",
            "replace_frequency": None,
            "steps": [
                "Periksa roda putar dari rambut atau kotoran yang melilit.",
                "Singkirkan kotoran dengan hati-hati dan seka area roda hingga bersih.",
                "Pastikan roda berputar bebas sebelum pembersihan berikutnya.",
            ],
            "notes": [
                "Manual mencantumkan pembersihan roda putar tetapi tidak memberikan interval penggantian khusus.",
            ],
        },
    },
    "s1_pro": {
        "filter": {
            "steps": [
                "Keluarkan filter berperforma tinggi dari area kotak debu.",
                "Ketuk-ketuk perlahan untuk melepaskan debu dan kotoran.",
                "Pasang kembali atau ganti filter setelah bersih dan kering.",
            ],
            "notes": [
                "Panduan servis aksesori di aplikasi adalah alur reset resmi utama untuk S1 Pro.",
            ],
        },
        "sensor": {
            "steps": [
                "Seka sensor robot dengan kain lembut dan kering.",
                "Bersihkan juga kontak pengisian daya saat menyervis sensor.",
            ],
        },
        "side_brush": {
            "steps": [
                "Periksa sikat samping dari rambut dan kotoran yang terjebak.",
                "Singkirkan penumpukan kotoran di sekitar pangkal dan bulu sikat.",
                "Ganti sikat jika bulunya bengkok atau rusak.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Lepaskan pelindung sikat gulung.",
                "Periksa sikat dan kedua tutup ujungnya dari rambut atau kotoran yang kusut.",
                "Bersihkan sikat secara menyeluruh sebelum dipasang kembali.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Lepaskan pel gulung atau permukaan kontak pel dan bersihkan sisa kotorannya.",
                "Biarkan bagian yang telah dibersihkan mengering sebelum digunakan kembali.",
                "Ganti komponen pel yang habis pakai jika keausan mulai terlihat atau performanya menurun.",
            ],
            "notes": [
                "Dokumentasi S1 berorientasi pada pel gulung, bukan pada istilah kain pel ganda yang dapat dilepas.",
            ],
        },
        "cleaning_tray": {
            "steps": [
                "Keluarkan baki filter atau sisipan baki dari area stasiun.",
                "Bilas hingga bersih dari sisa kotoran dan penumpukan.",
                "Pasang kembali setelah dibersihkan.",
            ],
            "notes": [
                "Bersihkan juga tangki air bersih/kotor dan filter air kotor sesuai kebutuhan.",
            ],
        },
        "swivel_wheel": {
            "steps": [
                "Periksa roda putar dari rambut dan kotoran.",
                "Singkirkan penumpukan kotoran dan pastikan roda berputar bebas.",
            ],
        },
    },
    "omni_c20": {
        "filter": {
            "steps": [
                "Keluarkan kotak debu atau kompartemen filter.",
                "Keluarkan filter dan ketuk-ketuk untuk melepaskan debu.",
                "Cuci hanya jika panduan manual/aplikasi mengizinkannya, lalu keringkan sepenuhnya sebelum dipasang kembali.",
            ],
            "notes": [
                "Panduan aksesori Omni C20 sebagian besar berbasis video.",
            ],
        },
        "sensor": {
            "steps": [
                "Gunakan kain bersih dan kering untuk menyeka sensor dan kontak pengisian daya pada robot maupun stasiun.",
            ],
        },
        "side_brush": {
            "steps": [
                "Periksa sikat samping dari keausan, lilitan, atau kerusakan.",
                "Singkirkan rambut dan kotoran yang melilit dari sikat dan pangkalnya.",
                "Ganti sikat jika bulunya bengkok atau hilang.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Periksa sikat gulung dari rambut atau kotoran yang kusut.",
                "Gunakan alat pembersih atau gunting untuk memotong material yang melilit.",
                "Pasang kembali setelah dibersihkan.",
            ],
            "notes": [
                "Sisir Pro-Detangle mengurangi, tetapi tidak menghilangkan, kebutuhan pembersihan manual.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Lepaskan kain pel dari robot atau stasiun.",
                "Bersihkan dan keringkan sepenuhnya sebelum digunakan kembali.",
                "Ganti kain pel jika sudah aus atau tidak lagi membersihkan secara efektif.",
            ],
        },
        "cleaning_tray": {
            "steps": [
                "Lepaskan komponen dasar stasiun atau area pencucian pel.",
                "Bilas dan seka sisa kotoran dari area baki.",
                "Pasang kembali baki setelah dibersihkan.",
            ],
            "notes": [
                "Pantau dan servis juga tangki air bersih dan kotor.",
            ],
        },
    },
    "x8_series": {
        "filter": {
            "steps": [
                "Keluarkan kotak debu dan ambil filternya.",
                "Ketuk-ketuk filter perlahan untuk melepaskan debu.",
                "Jika dibilas, biarkan kering sepenuhnya sebelum dipasang kembali.",
            ],
        },
        "sensor": {
            "steps": [
                "Seka sensor jatuh, sensor bumper, dan kontak pengisian daya dengan kain kering.",
            ],
        },
        "side_brush": {
            "steps": [
                "Lepaskan sikat samping.",
                "Bersihkan rambut dan kotoran dari sikat dan pangkalnya.",
                "Pasang kembali atau ganti jika sudah aus.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Tekan kait pelindung sikat utama dan lepaskan pelindungnya.",
                "Angkat sikat utama keluar.",
                "Gunakan alat pembersih atau gunting untuk menyingkirkan rambut dan kotoran.",
                "Pasang kembali sikat dan pelindungnya.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Lepaskan kain pel dari dudukannya.",
                "Cuci dan keringkan sebelum digunakan kembali.",
                "Ganti jika sudah aus atau tidak efektif.",
            ],
            "notes": [
                "Hanya berlaku untuk model X8 hybrid/yang mampu mengepel.",
            ],
        },
    },
    "l60_series": {
        "filter": {
            "steps": [
                "Tekan tombol pelepas kotak debu dan keluarkan kotak debunya.",
                "Keluarkan filter dan ketuk-ketuk untuk membuang kotoran yang lepas.",
                "Jika diizinkan oleh panduan model tertentu, bilas dan keringkan sepenuhnya sebelum dipasang kembali.",
            ],
        },
        "sensor": {
            "steps": [
                "Gunakan kain kering untuk menyeka sensor dan kontak pengisian daya pada robot dan pangkalan.",
            ],
        },
        "side_brush": {
            "steps": [
                "Tarik lepas sikat samping.",
                "Singkirkan rambut dan kotoran yang kusut.",
                "Pasang kembali atau ganti jika sudah aus.",
            ],
        },
        "rolling_brush": {
            "steps": [
                "Lepaskan penutup sikat utama.",
                "Angkat sikat gulung keluar.",
                "Bersihkan rambut dan kotoran yang melilit dari sikat dan bantalannya.",
                "Seka hingga kering dan pasang kembali sikat serta pelindungnya.",
            ],
            "notes": [
                "Model SES juga menggunakan pemotongan rambut otomatis untuk mengurangi perawatan.",
            ],
        },
        "mopping_cloth": {
            "steps": [
                "Lepaskan kain pel atau kainnya.",
                "Bersihkan dan keringkan sepenuhnya sebelum digunakan kembali.",
                "Ganti kain jika sudah aus.",
            ],
            "notes": [
                "Hanya berlaku untuk varian hybrid.",
            ],
        },
    },
}
