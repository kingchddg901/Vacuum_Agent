"""Upkeep-guide translations — Indonesian (id).

Per-language module under roborock/upkeep_guides_i18n/; __init__.py assembles them
into ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS. Pure data.

Best-effort AI DRAFT pending native review — steps/notes/frequencies translated
from the English base library (roborock_upkeep_guides.py), which is the source of
truth. Frequencies match our English base so the interval reads the same in every
language. Overlaid PER FIELD on the English guide — anything omitted falls back to
English.
"""

_STANDARD = {
    "main_brush": {
        "clean_frequency": "Mingguan",
        "replace_frequency": "Setiap 6-12 bulan",
        "steps": [
            "Balikkan robot dan tekan pengait untuk melepaskan penutup sikat utama.",
            "Angkat sikat utama, lalu tarik dan bersihkan tutup bantalan di kedua ujungnya.",
            "Gunakan alat pembersih yang disertakan untuk memotong dan menarik rambut yang melilit sikat dan bantalan.",
            "Pasang kembali tutup bantalan dan penutup ke arah kunci, lalu tekan penutup hingga pengait berbunyi klik.",
        ],
        "notes": [
            "Seka kompartemen sikat jika terlihat kotor sebelum memasang kembali.",
            "Ganti sikat utama setiap 6-12 bulan untuk hasil pembersihan terbaik.",
        ],
    },
    "side_brush": {
        "clean_frequency": "Bulanan",
        "replace_frequency": "Setiap 3-6 bulan",
        "steps": [
            "Balikkan robot dan lepaskan sekrup yang menahan sikat samping.",
            "Angkat sikat samping dan bersihkan rambut atau kotoran yang melilit porosnya.",
            "Pasang kembali sikat samping dan kencangkan sekrupnya.",
        ],
        "notes": [
            "Ganti sikat samping setiap 3-6 bulan, atau lebih cepat jika bengkok atau melebar.",
        ],
    },
    "filter": {
        "clean_frequency": "Setiap 2 minggu",
        "replace_frequency": "Setiap 6-12 bulan",
        "steps": [
            "Tekan pengait wadah debu, angkat wadah debu, buka penutupnya, dan kosongkan.",
            "Keluarkan filter yang dapat dicuci dan bilas di bawah air bersih — tanpa deterjen.",
            "Ketuk-ketukkan bingkai filter ke permukaan keras untuk melepaskan debu yang terperangkap, bilas hingga bersih.",
            "Biarkan filter kering diangin-anginkan setidaknya 24 jam sebelum dipasang kembali.",
        ],
        "notes": [
            "Jangan pernah menggunakan deterjen, air panas, mesin pencuci piring, atau pengering rambut pada filter.",
            "Menyiapkan filter kedua untuk ditukar memungkinkan satu filter benar-benar kering saat yang lain digunakan.",
        ],
    },
    "sensor": {
        "clean_frequency": "Bulanan",
        "replace_frequency": None,
        "steps": [
            "Seka keenam sensor jurang (cliff sensor) di bagian bawah dengan kain lembut dan kering.",
            "Seka sensor dinding di tepi kanan dan sensor pengisian ulang.",
            "Seka juga kontak pengisian daya di bagian bawah sekaligus.",
        ],
        "notes": [
            "Gunakan hanya kain kering — cairan pembersih dapat merusak penutup sensor.",
        ],
    },
    "dustbin": {
        "clean_frequency": "Mingguan",
        "replace_frequency": None,
        "steps": [
            "Buka penutup atas, tekan pengait wadah debu, dan angkat wadah debu keluar.",
            "Buka penutup wadah debu dan tuang isinya ke tempat sampah.",
            "Bilas wadah debu dengan air bersih bila perlu — lepaskan filter terlebih dahulu, dan jangan gunakan deterjen.",
        ],
        "notes": [
            "Keringkan wadah debu sepenuhnya sebelum dipasang kembali agar debu lembap tidak menyumbat filter.",
        ],
    },
    "mop_cloth": {
        "clean_frequency": "Setelah setiap penggunaan",
        "replace_frequency": "Setiap 3-6 bulan",
        "steps": [
            "Lepaskan kain pel dari modul pengepelan setelah setiap sesi pengepelan.",
            "Bilas hingga bersih dan biarkan mengering.",
        ],
        "notes": [
            "Selalu lepaskan kain untuk dibersihkan agar air kotor tidak mengalir kembali ke tangki dan menyumbat filter.",
            "Ganti kain yang dapat dipakai ulang setiap 3-6 bulan; ganti kain sekali pakai setelah setiap penggunaan.",
        ],
    },
    "caster_wheel": {
        "clean_frequency": "Bulanan",
        "replace_frequency": None,
        "steps": [
            "Balikkan robot dan cungkil roda omni-directional (roda kastor depan) ke atas.",
            "Bersihkan rambut dan kotoran yang melilit badan roda dan porosnya.",
            "Tekan roda dengan kuat kembali ke tempatnya.",
        ],
        "notes": [
            "Braket roda tidak dapat dilepas — hanya badan roda yang bisa diangkat keluar.",
        ],
    },
    "main_wheel": {
        "clean_frequency": "Mingguan",
        "replace_frequency": None,
        "steps": [
            "Seminggu sekali, periksa kedua roda penggerak utama dari rambut atau benang yang melilit porosnya.",
            "Potong dan tarik apa pun yang terjebak agar roda dapat berputar bebas.",
            "Seka roda dengan kain yang sedikit lembap jika ada kotoran yang menempel.",
        ],
        "notes": [
            "Roda yang berputar bebas menjaga robot tetap melaju lurus dan mampu menaiki ambang pintu.",
        ],
    },
}

_WATER_FILTER = {
    "clean_frequency": None,
    "replace_frequency": "Setiap 1-3 bulan",
    "steps": [
        "Tarik filter air keluar dari tangki seperti yang ditunjukkan dalam manual.",
        "Pasang filter baru dan geser kembali ke tempatnya.",
    ],
    "notes": [
        "Ganti setiap 1-3 bulan tergantung kualitas air Anda dan seberapa sering Anda mengepel.",
    ],
}
_DOCK_DUST_BAG = {
    "clean_frequency": None,
    "replace_frequency": "Saat penuh (sekitar setiap 7 minggu)",
    "steps": [
        "Buka penutup kompartemen debu pada dok.",
        "Angkat kantong debu yang penuh lurus ke atas — pegangannya menyegel kantong saat ditarik, sehingga debu tetap di dalam.",
        "Masukkan kantong debu baru hingga terpasang, lalu tutup penutupnya.",
    ],
    "notes": [
        "Selalu pasang kantong sebelum menutup penutup, atau dok akan mengosongkan otomatis tanpa kantong.",
        "Jika dok tidak digunakan beberapa waktu, kosongkan wadah debu robot secara manual dan pastikan saluran masuk udara tidak tersumbat.",
    ],
}
_CLEAN_WATER_TANK = {
    "clean_frequency": "Sesuai kebutuhan",
    "replace_frequency": None,
    "steps": [
        "Angkat tangki air bersih keluar dari dok dan buka penutup atasnya.",
        "Isi dengan air keran yang sejuk (tambahkan cairan pembersih Roborock hanya jika dok Anda mendukungnya).",
        "Tutup penutupnya dan pasang kembali tangki ke dalam dok.",
    ],
    "notes": [
        "Gunakan hanya air sejuk — air panas dapat merusak bentuk tangki.",
        "Seka sisa air di bagian luar sebelum dipasang kembali.",
    ],
}
_DIRTY_WATER_TANK = {
    "clean_frequency": "Sesuai kebutuhan",
    "replace_frequency": None,
    "steps": [
        "Buka tutup tangki air kotor dan buang air limbahnya.",
        "Tambahkan sedikit air bersih, tutup dan kunci tutupnya, kocok, lalu buang lagi untuk membilas.",
        "Kunci tutupnya dan pasang kembali tangki ke dalam dok.",
    ],
    "notes": [
        "Tutup tangki air kotor tidak dapat dilepas — bilas di tempatnya.",
        "Gunakan hanya air sejuk, dan seka bagian luar hingga kering sebelum dipasang kembali.",
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
