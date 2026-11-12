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
    _face_codepoints,
    _have_woff2_decoder,
    _string_values,
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


# ---------------------------------------------------------------------------
# [UF-1..3] validate_descriptor's FIELD-LEVEL behaviour
#
# The module docstring draws the line: "conservative -- reject anything that
# could smuggle CSS, a path, or an implausible face. Field-level tolerance where
# harmless". Both halves of that promise need inputs: a bad FIELD is repaired, a
# bad IDENTITY is refused outright. Tested together because the distinction is
# the design, and either half alone reads as the other being untested.
# ---------------------------------------------------------------------------

class TestDescriptorFieldHandling:
    def test_uf1_a_non_string_family_is_refused_outright(self):
        """[UF-1] `family` is the CSS identity; there is no repairing a missing one.

        Unlike weight or a fallback entry, family has no safe default -- inventing
        one would put a name on the wire that matches no font file, and the card
        would render the fallback while reporting the drop-in as present.
        """
        for bad in (None, 42, ["Atkinson"], {"name": "Atkinson"}):
            desc = dict(_good_desc())
            desc["family"] = bad
            assert validate_descriptor(desc) is None, (
                "family=%r was accepted" % (bad,)
            )

    def test_uf2_a_fallback_chain_always_ends_in_a_generic_family(self):
        """[UF-2] The chain's LAST entry must be a generic, and the code appends one.

        A fallback chain ending in a named family can dead-end: if that font is
        absent too, the browser falls back to its own default, which is the one
        outcome the chain exists to prevent. Three inputs, one rule:

          fallback absent / not a list  -> ["sans-serif"]
          fallback of named families    -> generic APPENDED, names kept in order
          fallback already generic-tailed -> left exactly as it is

        RED IF THE `not isinstance(raw_fallback, list)` ARM GOES: a string
        fallback is iterated CHARACTER BY CHARACTER, and each character that
        happens to match the name pattern becomes a font family.
        """
        desc = dict(_good_desc())
        desc["fallback"] = "Arial"              # a string, not a list
        assert validate_descriptor(desc)["fallback"] == ["sans-serif"]

        desc["fallback"] = ["Helvetica", "Arial"]   # named only, no generic tail
        assert validate_descriptor(desc)["fallback"] == [
            "Helvetica", "Arial", "sans-serif"
        ]

        desc["fallback"] = ["Arial", "monospace"]   # already ends generic
        assert validate_descriptor(desc)["fallback"] == ["Arial", "monospace"]

    def test_uf3_a_descriptor_with_no_USABLE_face_is_refused(self):
        """[UF-3] Faces are the font. A descriptor naming none is not a font.

        Three shapes reach the same refusal, and they are different failures:
        `faces` not a list at all, a list whose entries are not dicts, and a list
        whose every entry names an unusable file. The LAST is the one that matters
        -- the descriptor looks complete and every face was individually rejected,
        which is exactly when a lenient reading would catalogue an empty font and
        offer the user a typeface that cannot render a single character.

        The mixed case proves the per-face skip rather than an all-or-nothing
        refusal: one junk entry beside one good one keeps the good one.
        """
        desc = dict(_good_desc())
        desc["faces"] = {"file": "A.woff2"}         # a dict, not a list
        assert validate_descriptor(desc) is None

        desc["faces"] = ["Atkinson-Regular.woff2", 7, None]   # not dicts
        assert validate_descriptor(desc) is None

        desc["faces"] = [{"file": "../escape.woff2"}, {"file": "not-a-font.txt"}]
        assert validate_descriptor(desc) is None, (
            "a descriptor whose every face was rejected was still catalogued"
        )

        desc["faces"] = [{"file": "../escape.woff2"},
                         {"file": "Atkinson-Bold.woff2", "weight": 700}]
        out = validate_descriptor(desc)
        assert out is not None and out["faces"] == [
            {"file": "Atkinson-Bold.woff2", "weight": 700}
        ], "the junk face was not skipped independently of the good one"


# ---------------------------------------------------------------------------
# [UF-4..5] the optional dependency, absent
#
# "Verification is graceful about its own dependency" -- and the module is
# careful that CANNOT VERIFY never collapses into COVERS NOTHING. Both absences
# are simulated by putting None in sys.modules, which is what the import system
# itself does for a module that failed to load: `import x` then raises
# ImportError, exactly as a genuinely missing package does.
# ---------------------------------------------------------------------------

class TestOptionalDependencyAbsent:
    def test_uf4_no_brotli_means_no_woff2_decoder(self):
        """[UF-4] `haveBrotli` is asked for, and its ABSENCE answers False.

        The docstring explains why this flag rather than matching the error text:
        "Asking it beats substring-matching that message, which would go silently
        wrong the day upstream rewords it." If the import itself fails, there is
        no flag to ask and the answer is False -- not an exception out of a
        setup path.
        """
        import sys

        with patch.dict(sys.modules, {"fontTools.ttLib.woff2": None}):
            assert _have_woff2_decoder() is False

    def test_uf5_no_fonttools_is_CANNOT_VERIFY_not_covers_nothing(self, tmp_path):
        """[UF-5] The distinction the whole verification chain rests on.

        `None` from `_face_codepoints` means "cannot answer the coverage
        question". An empty codepoint set would mean "this font covers nothing"
        -- and that is a VERDICT, which would mark every locale unsupported and
        silently withdraw a font that is perfectly fine.

        RED IF THE ImportError ARM RETURNS `set(), False` INSTEAD OF None: the
        assertion is on `is None` specifically, because an empty set is falsy and
        a truthiness check would pass against exactly that mistake.
        """
        import sys

        face = tmp_path / "Atkinson-Regular.woff2"
        face.write_bytes(b"\x00fake")

        with patch.dict(sys.modules, {"fontTools.ttLib": None}):
            out = _face_codepoints(str(face))

        assert out is None, (
            "expected None (cannot verify); got %r. An empty set here reads as "
            "a verdict that the font covers nothing." % (out,)
        )


# ---------------------------------------------------------------------------
# [UF-6] the string walk that feeds every locale's requirement
# ---------------------------------------------------------------------------

class TestStringValues:
    def test_uf6_the_walk_descends_through_lists_as_well_as_dicts(self):
        """[UF-6] A locale file's strings can sit inside arrays, and they count.

        `_string_values` is what turns a locale JSON into the character set that
        locale's chrome needs. Every shipped locale tested here happened to be a
        flat object, so the LIST arm had never run -- and a locale whose strings
        live in an array would contribute NO characters, which does not fail: it
        makes the font look like it covers that locale when it may not. An
        under-collected requirement is the dangerous direction, because the
        verification is a promise of coverage.
        """
        out = []
        _string_values(
            {"a": "one", "b": ["two", {"c": "three"}, ["four", 5, None]], "d": 6},
            out,
        )
        assert sorted(out) == ["four", "one", "three", "two"], (
            "the walk missed strings nested in lists: %r" % (out,)
        )


# ---------------------------------------------------------------------------
# [UF-7..9] locale_char_requirements, on inputs it cannot read
#
# Every one of these is an I/O failure the module promises to survive. It runs
# during setup, so a raise here is a failed integration start over a locale file
# the user cannot be expected to know about.
# ---------------------------------------------------------------------------

class TestLocaleRequirementsDegradation:
    def test_uf7_an_unreadable_english_reference_does_not_stop_the_rest(
        self, tmp_path, caplog
    ):
        """[UF-7] English is the BASE every other locale inherits -- and it can fail.

        With the reference unreadable, `en` is an empty requirement and every
        other locale keeps its own characters. The alternative, raising, takes
        down setup; the other alternative, inheriting nothing silently, is what
        this test pins by asserting `de` still carries its own.
        """
        d = tmp_path / "locales"
        d.mkdir()
        (d / "en.reference.jsonc").write_text("{ not json at all", encoding="utf-8")
        (d / "de.json").write_text(json.dumps({"k": "Größe"}), encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            reqs = locale_char_requirements(str(d))

        assert reqs["en"] == set(), "a broken reference produced characters"
        assert {ord(c) for c in "Größe"} <= reqs["de"], (
            "de lost its own characters because the English base failed"
        )
        assert "English reference unreadable" in caplog.text, (
            "the failure was swallowed with no way for the user to find it"
        )

    def test_uf8_a_missing_locales_directory_yields_english_only(self, tmp_path):
        """[UF-8] No directory at all: answer what is known, do not raise.

        `reqs["en"]` is built before the listing is attempted, so the return is
        not empty -- it is the English entry with nothing else. The assertion is
        on the KEYS, because an empty dict and an en-only dict behave very
        differently downstream: with no `en` key at all, a font that covers
        English perfectly would be catalogued as verifying no locales.
        """
        reqs = locale_char_requirements(str(tmp_path / "nope"))
        assert list(reqs) == ["en"]
        assert reqs["en"] == set()

    def test_uf9_one_unreadable_locale_costs_only_that_locale(self, tmp_path, caplog):
        """[UF-9] A truncated locale file must not take its siblings with it.

        The loop warns and continues, so a single corrupt file costs exactly one
        language. `index.json` is in the directory too, because it is skipped by
        NAME rather than by failing to parse -- without it here, a regression that
        started parsing index.json would be invisible.
        """
        d = tmp_path / "locales"
        d.mkdir()
        (d / "en.reference.jsonc").write_text(
            json.dumps({"k": "Abc"}), encoding="utf-8"
        )
        (d / "de.json").write_text(json.dumps({"k": "Größe"}), encoding="utf-8")
        (d / "fr.json").write_text('{"k": "Café"', encoding="utf-8")   # truncated
        (d / "index.json").write_text(json.dumps(["de", "fr"]), encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            reqs = locale_char_requirements(str(d))

        assert "de" in reqs, "a good locale was lost with the broken one"
        assert "fr" not in reqs, "a locale that would not parse was catalogued"
        assert "index" not in reqs, "index.json was read as a locale"
        assert "locale fr.json unreadable" in caplog.text


# ---------------------------------------------------------------------------
# [UF-10..13] build_catalog, which "never raises"
# ---------------------------------------------------------------------------

def _escaping_dropin(tmp_path, fonts, site):
    """Plant ONE drop-in that reaches OUTSIDE the fonts directory by symlink.

    ``site`` names which of ``build_catalog``'s three containment copies --
    ``os.path.islink(dir_path)``, ``os.path.islink(desc_path)``,
    ``os.path.islink(p)`` -- is the only thing standing between this drop-in
    and the catalog. Everything else about it is deliberately VALID, and that
    is the whole difficulty of the fixture: it must have its own id (a copy of
    ``atkinson``'s would be dropped by the id dedup instead, so the ablation
    would come back dead) and its faces must be present (a missing face would
    discard it first, for the same reason). Returns the id it planted, which
    must never reach the catalog.
    """
    font_id = {
        "descriptor": "linkedfont",
        "directory": "linkeddir",
        "face": "linkedface",
    }[site]
    desc = {
        "id": font_id,
        "family": "Linked Sans",
        "faces": [{"file": "Linked-Regular.woff2", "weight": 400}],
    }
    if site == "descriptor":
        # Real directory, real face file; the DESCRIPTOR is the pointer out.
        outside = tmp_path / "elsewhere.json"
        outside.write_text(json.dumps(desc), encoding="utf-8")
        here = fonts / font_id
        here.mkdir()
        (here / "Linked-Regular.woff2").write_bytes(b"\x00fake")
        os.symlink(str(outside), str(here / "font.json"))
    elif site == "directory":
        # A complete, self-consistent drop-in that simply LIVES somewhere else
        # -- nothing inside it is a link, so only the folder check can see it.
        outside = tmp_path / "outside-dropin"
        outside.mkdir()
        (outside / "font.json").write_text(json.dumps(desc), encoding="utf-8")
        (outside / "Linked-Regular.woff2").write_bytes(b"\x00fake")
        os.symlink(str(outside), str(fonts / font_id), target_is_directory=True)
    else:
        # Directory and descriptor both real; the FACE FILE is the pointer out,
        # and it exists, so `os.path.isfile` follows the link and says yes.
        outside = tmp_path / "Linked-Regular.woff2"
        outside.write_bytes(b"\x00fake")
        here = fonts / font_id
        here.mkdir()
        (here / "font.json").write_text(json.dumps(desc), encoding="utf-8")
        os.symlink(str(outside), str(here / "Linked-Regular.woff2"))
    return font_id


class TestBuildCatalogDegradation:
    def test_uf10_a_missing_fonts_directory_catalogues_nothing(self, tmp_path):
        """[UF-10] The ordinary case for every user who never dropped a font in.

        The directory does not exist on a stock install, so this path runs at
        every single setup. It must answer 0 without raising and without writing.
        """
        missing = tmp_path / "no-fonts-here"
        assert build_catalog(str(missing), str(tmp_path / "locales")) == 0
        assert not missing.exists(), "the discovery path created the directory"

    @pytest.mark.parametrize("site", ["descriptor", "directory", "face"])
    def test_uf11_a_drop_in_reached_by_symlink_is_skipped(self, tmp_path, site):
        """[UF-11] Containment, at all THREE places build_catalog checks it.

        (Was `test_uf11_a_descriptor_that_is_not_a_regular_file_is_skipped`,
        which fenced the descriptor copy alone.)

        This is a containment rule, not a tidiness one. A symlink is a pointer
        OUT of the fonts directory, and the whole trust model here is that a
        drop-in describes itself, and carries its own faces, from inside its own
        folder. `build_catalog` says so three times -- about the drop-in
        DIRECTORY, about `font.json`, and about each FACE FILE -- and each copy
        gets its own cell here, because each is independently deletable.

        TWO OF THE THREE WERE UNFENCED UNTIL A PRE-RELEASE AUDIT ABLATED THEM,
        in a module this release range published at 100.00%, and the percentage
        is not wrong -- it is measuring something else. coverage.py records
        LINES and ARCS, not CONDITIONS: a one-line `or` chain reads fully
        covered as soon as either arc out of it is taken, so two of three
        conditions can go unevaluated at 100.00%. (Python short-circuits them,
        so `os.path.islink(dir_path)` is not even reached when
        `not DIR_RE.match(sub)` is already true.) What makes the null robust is
        the denominator rather than the two runs: before this parametrisation
        `os.symlink` appeared EXACTLY ONCE in the whole test tree, in this test,
        and it linked a descriptor -- so no test anywhere could reach the other
        two arms.

        THE DIVISION OF LABOUR IS MEASURED, one cell per site: deleting
        `or os.path.islink(dir_path)` reddens `[directory]` alone, deleting
        `or os.path.islink(desc_path)` reddens `[descriptor]` alone, and
        deleting `or os.path.islink(p)` reddens `[face]` alone.

        The good font is catalogued in the same call, so each cell is a skip and
        not a bail-out -- a refusal that also dropped the valid font would
        satisfy any assertion about the bad one alone.

        THE LINKED DROP-IN MUST BE OTHERWISE COMPLETE, which took two
        corrections on the descriptor arm and would have cost the same two on
        each of the others: with a COPY of the good descriptor it shares the id
        "atkinson" and the id dedup drops it, and with no face files beside it
        the missing-face check discards it. Either flaw alone makes an arm
        untestable while looking tested, and the ablation came back DEAD until
        both were fixed. See `_escaping_dropin`, which is where that now lives.
        """
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        (fonts / "empty").mkdir()                        # no font.json at all

        escaping = _escaping_dropin(tmp_path, fonts, site)
        _write_font_dir(str(fonts))                      # the good one

        loc = _locales_dir(tmp_path)
        with patch(
            "custom_components.eufy_vacuum.user_fonts._face_codepoints",
            return_value=({ord(c) for c in "AbcGröße"} | set(range(0x21, 0x7F)), True),
        ):
            count = build_catalog(str(fonts), loc)

        assert count == 1, (
            "expected only the good drop-in, got %d -- a drop-in whose %s was "
            "reached from OUTSIDE the fonts directory by symlink was catalogued"
            % (count, site)
        )
        written = json.loads((fonts / "catalog.json").read_text(encoding="utf-8"))
        assert [e["id"] for e in written] == ["atkinson"], (
            "catalogued %r; %r escaped containment via its %s"
            % ([e["id"] for e in written], escaping, site)
        )

    def test_uf12_an_unreadable_descriptor_is_warned_and_skipped(
        self, tmp_path, caplog
    ):
        """[UF-12] Malformed JSON in one drop-in costs that drop-in and nothing else.

        Distinct from a descriptor that PARSES and is then rejected, which is a
        different message and a different line -- this one never becomes a dict
        at all. The warning names the subdirectory, because "descriptor
        unreadable" with no name is unactionable when several fonts are present.
        """
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        broken = fonts / "brokenfont"
        broken.mkdir()
        (broken / "font.json").write_text("{ oh dear", encoding="utf-8")
        _write_font_dir(str(fonts))

        loc = _locales_dir(tmp_path)
        with caplog.at_level(logging.WARNING), patch(
            "custom_components.eufy_vacuum.user_fonts._face_codepoints",
            return_value=({ord(c) for c in "AbcGröße"} | set(range(0x21, 0x7F)), True),
        ):
            count = build_catalog(str(fonts), loc)

        assert count == 1
        assert "brokenfont" in caplog.text and "descriptor unreadable" in caplog.text

    def test_uf13_a_catalog_that_cannot_be_written_reports_ZERO(self, tmp_path, caplog):
        """[UF-13] The count is a claim about what the CARD can read, not what we built.

        Everything upstream succeeded here -- a valid drop-in, verified locales,
        an entry assembled. Only the write failed, and the function returns 0
        rather than the number it had in hand. That is the honest answer: the
        catalog is the canonical response the card consumes, so a font that is
        not in the written file does not exist as far as the UI is concerned.

        The write is made to fail by putting a DIRECTORY where catalog.json goes,
        which is a real OSError from the real `open` rather than a patched one --
        a patched `open` would also intercept every read this function makes.
        """
        fonts = tmp_path / "fonts"
        fonts.mkdir()
        _write_font_dir(str(fonts))
        (fonts / "catalog.json").mkdir()

        loc = _locales_dir(tmp_path)
        with caplog.at_level(logging.WARNING), patch(
            "custom_components.eufy_vacuum.user_fonts._face_codepoints",
            return_value=({ord(c) for c in "AbcGröße"} | set(range(0x21, 0x7F)), True),
        ):
            count = build_catalog(str(fonts), loc)

        assert count == 0, (
            "a font that never reached catalog.json was counted as catalogued"
        )
        assert "could not write catalog.json" in caplog.text
