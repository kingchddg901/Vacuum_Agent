"""Drop-in font catalog builder (user_fonts.py).

The backend owns the whole trust chain: descriptor validation, cmap-derived
locale verification (the font FILE is the evidence — never the descriptor's
claims, never a browser render check), and the canonical catalog.json.
Verification here injects codepoints instead of parsing real woff2 files, so
most of these run without fontTools; the no-fontTools degradation path is
tested explicitly. The two classes at the bottom are the exception: the C3/C4
defects lived INSIDE ``_face_codepoints``, which a patched stand-in cannot
see, so they put real bytes on disk and need the real parser (fontTools and
brotli are both hard entries in requirements_test.txt).
"""

import json
import logging
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.eufy_vacuum.user_fonts import (
    build_catalog,
    locale_char_requirements,
    strip_jsonc,
    validate_descriptor,
)

REPO = Path(__file__).resolve().parents[2]


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


class TestUnreadableFaceIsNotCoverage:
    """C3/D7 — "cannot verify" and "covers nothing" are different answers.

    Unlike the class above, these do NOT patch ``_face_codepoints``: the whole
    defect lived inside it, so a patched stand-in cannot see it. They drop real
    bytes on disk and read the catalog the card actually consumes.
    """

    def test_corrupt_single_face_is_unverified_not_verified_with_no_locales(
        self, tmp_path
    ):
        """[UF-C3-1] A drop-in whose only face is unparseable must not be
        stamped as a completed verification.

        `_write_font_dir` writes `b"\x00fake"` — not a woff2. Before the fix
        the parse failure answered "covers nothing", so the font was catalogued
        `verified` with `locales: []`: indistinguishable, to the card and to
        diagnostics, from a font that genuinely covers no locale.
        """
        pytest.importorskip("fontTools")
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        _write_font_dir(str(fonts))
        count = build_catalog(str(fonts), _locales_dir(tmp_path))
        assert count == 1
        entry = json.loads((fonts / "catalog.json").read_text(encoding="utf-8"))[0]
        assert entry["status"] == "unverified", (
            "an unparseable face was catalogued as a completed verification"
        )
        assert entry["locales"] == []

    def test_one_corrupt_face_does_not_zero_a_good_one(self, tmp_path):
        """[UF-C3-2] The ledger's sharpest case, end to end: face A parses,
        face B is corrupt.

        The caller INTERSECTS faces, so answering "covers nothing" for B
        silently zeroed A's real coverage and still reported success. Uses a
        genuinely parseable shipped woff2 for A so the intersection has
        something real to lose — with two corrupt faces the test would pass
        for the wrong reason.
        """
        pytest.importorskip("fontTools")
        pytest.importorskip("brotli")
        real = (
            REPO
            / "custom_components"
            / "eufy_vacuum"
            / "frontend"
            / "fonts"
            / "OpenDyslexic-Regular.woff2"
        )
        assert real.is_file(), "shipped woff2 missing — this test needs a real face"

        fonts = tmp_path / "fonts"
        fonts.mkdir()
        desc = {
            **_good_desc(),
            "faces": [
                {"file": "OpenDyslexic-Regular.woff2", "weight": 400},
                {"file": "Corrupt-Bold.woff2", "weight": 700},
            ],
        }
        d = _write_font_dir(
            str(fonts), desc=desc, faces=("Corrupt-Bold.woff2",)
        )
        shutil.copyfile(real, os.path.join(d, "OpenDyslexic-Regular.woff2"))

        # Face A alone verifies at least English — establishes that the
        # intersection below actually had coverage to lose.
        solo = tmp_path / "solo"
        solo.mkdir()
        d2 = _write_font_dir(
            str(solo),
            desc={
                **_good_desc(),
                "faces": [{"file": "OpenDyslexic-Regular.woff2", "weight": 400}],
            },
            faces=(),
        )
        shutil.copyfile(real, os.path.join(d2, "OpenDyslexic-Regular.woff2"))
        build_catalog(str(solo), _locales_dir(tmp_path))
        solo_entry = json.loads((solo / "catalog.json").read_text(encoding="utf-8"))[0]
        assert solo_entry["status"] == "verified"
        assert solo_entry["locales"], "control: the real face must verify something"

        build_catalog(str(fonts), _locales_dir(tmp_path))
        entry = json.loads((fonts / "catalog.json").read_text(encoding="utf-8"))[0]
        assert entry["status"] == "unverified", (
            "a corrupt second face zeroed the intersection and the font was "
            "still catalogued as verified"
        )
        assert entry["locales"] == []


class TestImportErrorInsideTheParse:
    """C4 — only a real dependency gap may claim fontTools is not installed."""

    def test_table_module_import_error_is_not_reported_as_missing_fonttools(
        self, tmp_path, caplog
    ):
        """[UF-C4-1] `getBestCmap()` pulls in fontTools table modules lazily.
        An ImportError from one of those is not a statement about fontTools
        being absent — fontTools imported fine three lines earlier.

        Before the fix that error was swallowed unlogged and the user was told
        to install a package they demonstrably have, which is the one piece of
        text they would act on.
        """
        pytest.importorskip("fontTools")
        pytest.importorskip("brotli")  # so the woff2-decoder probe says "present"
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        _write_font_dir(str(fonts))
        boom = ImportError(
            "cannot import name 'otBase' from 'fontTools.ttLib.tables'"
        )
        with caplog.at_level(
            logging.INFO, logger="custom_components.eufy_vacuum.user_fonts"
        ):
            with patch("fontTools.ttLib.TTFont", side_effect=boom):
                build_catalog(str(fonts), _locales_dir(tmp_path))
        text = caplog.text
        assert "otBase" in text, "the real ImportError was discarded unlogged"
        assert "is not installed" not in text, (
            "a table-module ImportError was reported to the user as fontTools "
            "not being installed"
        )
        entry = json.loads((fonts / "catalog.json").read_text(encoding="utf-8"))[0]
        assert entry["status"] == "unverified"

    def test_missing_woff2_decoder_still_reports_the_dependency(
        self, tmp_path, caplog
    ):
        """[UF-C4-2] The other half, so the fix cannot be a blanket mute: when
        brotli really is absent, fontTools raises ImportError from the same
        place and the user MUST still be told the dependency is the problem.

        Patches fontTools' own `haveBrotli` — the flag that produces the raise
        — rather than the message text.
        """
        pytest.importorskip("fontTools")
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        _write_font_dir(str(fonts))
        with caplog.at_level(
            logging.INFO, logger="custom_components.eufy_vacuum.user_fonts"
        ):
            with patch("fontTools.ttLib.woff2.haveBrotli", False), patch(
                "fontTools.ttLib.TTFont",
                side_effect=ImportError("No module named brotli"),
            ):
                build_catalog(str(fonts), _locales_dir(tmp_path))
        assert "is not installed" in caplog.text
        entry = json.loads((fonts / "catalog.json").read_text(encoding="utf-8"))[0]
        assert entry["status"] == "unverified"
        assert entry["locales"] == []
