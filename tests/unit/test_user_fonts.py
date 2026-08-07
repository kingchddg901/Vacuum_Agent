"""Drop-in font catalog builder (user_fonts.py).

The backend owns the whole trust chain: descriptor validation, cmap-derived
locale verification (the font FILE is the evidence — never the descriptor's
claims, never a browser render check), and the canonical catalog.json.
Verification here injects codepoints instead of parsing real woff2 files, so
these run without fontTools; the no-fontTools degradation path is tested
explicitly.
"""

import json
import os
from unittest.mock import patch

from custom_components.eufy_vacuum.user_fonts import (
    build_catalog,
    locale_char_requirements,
    strip_jsonc,
    validate_descriptor,
)


def _good_desc():
    return {
        "id": "atkinson",
        "family": "Atkinson Hyperlegible",
        "faces": [{"file": "Atkinson-Regular.woff2", "weight": 400}],
        "fallback": ["Arial", "sans-serif"],
    }


class TestValidateDescriptor:
    def test_minimal_valid(self):
        desc = validate_descriptor(_good_desc())
        assert desc is not None
        assert desc["id"] == "atkinson"
        assert desc["label"] == "Atkinson Hyperlegible"
        assert desc["fallback"] == ["Arial", "sans-serif"]

    def test_rejections(self):
        good = _good_desc()
        for mutation in (
            {"id": "Bad Id"},
            {"id": "../evil"},
            {"family": 'Evil"; } * { color: red; } /*'},
            {"family": ""},
            {"faces": []},
            {"faces": [{"file": "../../secret.woff2", "weight": 400}]},
            {"faces": [{"file": "font.ttf", "weight": 400}]},
            {"faces": [{"file": "a/b.woff2", "weight": 400}]},
        ):
            assert validate_descriptor({**good, **mutation}) is None, mutation
        assert validate_descriptor(None) is None
        assert validate_descriptor("string") is None

    def test_field_tolerance(self):
        desc = validate_descriptor(
            {
                **_good_desc(),
                "fallback": ["Arial", 'ev"il', 42],
                "faces": [{"file": "a.woff2", "weight": 9999}],
            }
        )
        assert desc["faces"][0]["weight"] == 400
        # Non-generic tail -> sans-serif appended; junk entries dropped.
        assert desc["fallback"] == ["Arial", "sans-serif"]

    def test_locales_in_descriptor_are_ignored(self):
        # The descriptor cannot claim support — the font file is the evidence.
        desc = validate_descriptor({**_good_desc(), "locales": ["en", "ru"]})
        assert "locales" not in desc


class TestStripJsonc:
    def test_strips_comments_but_not_urls(self):
        text = '{\n  "a": "https://x/y", // comment\n  "b": "va//lue"\n}'
        data = json.loads(strip_jsonc(text))
        assert data == {"a": "https://x/y", "b": "va//lue"}

    def test_escaped_quote_in_string(self):
        text = '{"a": "say \\"hi\\" // not a comment"} // real'
        assert json.loads(strip_jsonc(text)) == {"a": 'say "hi" // not a comment'}


class TestLocaleRequirements:
    def test_locale_includes_english_base(self, tmp_path):
        d = tmp_path / "locales"
        d.mkdir()
        (d / "en.reference.jsonc").write_text(
            '{ "k": "Abc" } // english', encoding="utf-8"
        )
        (d / "de.json").write_text(
            json.dumps({"nav": {"x": "Größe"}}), encoding="utf-8"
        )
        reqs = locale_char_requirements(str(d))
        assert {ord(c) for c in "Abc"} <= reqs["en"]
        # de needs its own chars AND the English base (fallback chrome).
        assert {ord(c) for c in "GrößeAbc"} <= reqs["de"]


def _write_font_dir(root, sub="atkinson", desc=None, faces=("Atkinson-Regular.woff2",)):
    d = os.path.join(root, sub)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "font.json"), "w", encoding="utf-8") as fh:
        json.dump(desc or _good_desc(), fh)
    for f in faces:
        with open(os.path.join(d, f), "wb") as fh:
            fh.write(b"\x00fake")
    return d


def _locales_dir(tmp_path, en_text="Abc", de_text="Größe"):
    d = tmp_path / "locales"
    d.mkdir(exist_ok=True)
    (d / "en.reference.jsonc").write_text(
        json.dumps({"k": en_text}), encoding="utf-8"
    )
    (d / "de.json").write_text(json.dumps({"k": de_text}), encoding="utf-8")
    return str(d)


class TestBuildCatalog:
    def test_verified_locales_from_codepoints(self, tmp_path):
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        _write_font_dir(str(fonts))
        loc = _locales_dir(tmp_path)
        # The fake face covers ASCII but not ö/ß -> en verified, de not.
        ascii_cps = {ord(c) for c in "AbcGre"} | set(range(0x21, 0x7F))
        with patch(
            "custom_components.eufy_vacuum.user_fonts._face_codepoints",
            return_value=(ascii_cps, False),
        ):
            count = build_catalog(str(fonts), loc)
        assert count == 1
        catalog = json.loads((fonts / "catalog.json").read_text(encoding="utf-8"))
        entry = catalog[0]
        assert entry["status"] == "verified"
        assert entry["locales"] == ["en"]
        assert entry["dir"] == "atkinson"

    def test_shaping_locale_needs_gsub(self, tmp_path):
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        _write_font_dir(str(fonts))
        loc = tmp_path / "locales"
        loc.mkdir()
        (loc / "en.reference.jsonc").write_text('{"k": "A"}', encoding="utf-8")
        (loc / "ar.json").write_text(
            json.dumps({"k": "مرح"}), encoding="utf-8"
        )
        cps = {ord("A"), 0x645, 0x631, 0x62D} | set(range(0x21, 0x7F))
        with patch(
            "custom_components.eufy_vacuum.user_fonts._face_codepoints",
            return_value=(cps, False),
        ):
            build_catalog(str(fonts), str(loc))
        entry = json.loads(
            (fonts / "catalog.json").read_text(encoding="utf-8")
        )[0]
        assert "ar" not in entry["locales"], "cmap alone must not verify a shaping locale"
        with patch(
            "custom_components.eufy_vacuum.user_fonts._face_codepoints",
            return_value=(cps, True),
        ):
            build_catalog(str(fonts), str(loc))
        entry = json.loads(
            (fonts / "catalog.json").read_text(encoding="utf-8")
        )[0]
        assert "ar" in entry["locales"]

    def test_no_fonttools_degrades_to_unverified(self, tmp_path):
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        _write_font_dir(str(fonts))
        loc = _locales_dir(tmp_path)
        with patch(
            "custom_components.eufy_vacuum.user_fonts._face_codepoints",
            return_value=None,
        ):
            count = build_catalog(str(fonts), loc)
        assert count == 1
        entry = json.loads((fonts / "catalog.json").read_text(encoding="utf-8"))[0]
        assert entry["status"] == "unverified"
        assert entry["locales"] == []

    def test_missing_face_and_bad_descriptor_skipped(self, tmp_path):
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        _write_font_dir(str(fonts), sub="nofile", faces=())  # face file absent
        _write_font_dir(str(fonts), sub="bad", desc={"id": "NOPE"})
        loc = _locales_dir(tmp_path)
        with patch(
            "custom_components.eufy_vacuum.user_fonts._face_codepoints",
            return_value=(set(range(0x21, 0x7F)), False),
        ):
            count = build_catalog(str(fonts), loc)
        assert count == 0
        assert json.loads((fonts / "catalog.json").read_text(encoding="utf-8")) == []

    def test_duplicate_ids_first_wins(self, tmp_path):
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        _write_font_dir(str(fonts), sub="a_first")
        _write_font_dir(str(fonts), sub="b_second")
        loc = _locales_dir(tmp_path)
        with patch(
            "custom_components.eufy_vacuum.user_fonts._face_codepoints",
            return_value=(set(range(0x21, 0x7F)), False),
        ):
            count = build_catalog(str(fonts), loc)
        assert count == 1
        entry = json.loads((fonts / "catalog.json").read_text(encoding="utf-8"))[0]
        assert entry["dir"] == "a_first"

    def test_empty_dir_writes_empty_catalog(self, tmp_path):
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        assert build_catalog(str(fonts), _locales_dir(tmp_path)) == 0
        assert json.loads((fonts / "catalog.json").read_text(encoding="utf-8")) == []
