"""Ablation for the generated-doc staleness gate (`scripts/check_generated_docs.py`).

A gate over generated documentation has the same failure mode as the documents it
guards: it can be silently dead and read exactly like a clean pass. So every detector
gets a deliberate defect injected and must rise. A clean run against a clean tree
proves nothing.

The fixtures build a throwaway repo root with a throwaway generator, so nothing here
depends on `node`, on the real theme registry, or on the state of `docs/`. The one
test that touches the real registry (GDG-12) only checks its SHAPE, which is the part
a typo breaks.

  GDG-1   a current file is not reported
  GDG-2   STALE fires when the generator now emits something else
  GDG-3   MISSING fires when a registered file is absent from the tree
  GDG-4   SILENT fires when the generator exits 0 and writes nothing
  GDG-5   SILENT fires when the generator writes a file under a different name
  GDG-6   BROKEN fires on a non-zero exit
  GDG-7   BROKEN fires when the command cannot be run at all
  GDG-8   UNGATED fires on a banner-bearing doc no generator claims
  GDG-9   an empty registry is a failure, not a clean pass
  GDG-10  a CRLF working copy of a current file is NOT stale
  GDG-11  a doc that merely mentions the banner in its body is not swept up
  GDG-12  the real registry is well-formed
  GDG-13  a region generator whose own check passes reports nothing
  GDG-14  STALE fires when a region generator's own check exits non-zero
  GDG-15  a region check that cannot run is BROKEN, not STALE
  GDG-16  a registry entry declaring neither shape, or both, is rejected
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from check_generated_docs import (  # noqa: E402
    GENERATORS,
    Generator,
    banner_bearing_files,
    check,
)

BODY = "<!-- GENERATED FILE — DO NOT EDIT BY HAND. -->\n\n# Fake reference\n\nvalue: 1\n"
REL = "docs/dev/reference/FAKE.md"


def _fake_root(tmp_path: Path, *, emits: str = BODY, names=("FAKE.md",), rc: int = 0) -> Path:
    """A miniature repo: one generator script, output redirected by $FAKE_OUT."""
    root = tmp_path / "repo"
    (root / "docs" / "dev" / "reference").mkdir(parents=True)
    (root / "fakegen.py").write_text(
        textwrap.dedent(
            f"""
            import os, pathlib, sys
            if {rc}:
                sys.stderr.write("fake generator refused\\n")
                sys.exit({rc})
            if "FAKE_OUT" not in os.environ:
                sys.exit(0)   # region-generator mode: nothing to redirect
            out = pathlib.Path(os.environ["FAKE_OUT"])
            out.mkdir(parents=True, exist_ok=True)
            for name in {list(names)!r}:
                (out / name).write_text({emits!r}, encoding="utf-8")
            """
        ),
        encoding="utf-8",
    )
    return root


def _gen(cmd=None) -> tuple[Generator, ...]:
    return (
        Generator(
            id="fake",
            cmd=cmd or (sys.executable, "fakegen.py"),
            out_env="FAKE_OUT",
            files=(REL,),
        ),
    )


def _kinds(problems: list[str]) -> list[str]:
    return [p.split()[0] for p in problems]


def test_gdg1_current_file_is_clean(tmp_path):
    """[GDG-1] The comparison must not report a file that is already current."""
    root = _fake_root(tmp_path)
    (root / REL).write_text(BODY, encoding="utf-8")

    problems, checked, ran = check(_gen(), root=root)

    assert problems == []
    assert checked == [REL]
    assert ran == ["fake"]


def test_gdg2_stale_fires(tmp_path):
    """[GDG-2] The headline case: the tree holds an older render than the source."""
    root = _fake_root(tmp_path)
    (root / REL).write_text(BODY.replace("value: 1", "value: 0"), encoding="utf-8")

    problems, checked, _ = check(_gen(), root=root)

    assert _kinds(problems) == ["STALE"]
    assert REL in problems[0]
    # The diff must be in the message — "something changed" is not actionable.
    assert "-value: 0" in problems[0] and "+value: 1" in problems[0]
    assert checked == [REL]


def test_gdg3_missing_fires(tmp_path):
    """[GDG-3] A registered file absent from the tree is a failure, not a skip."""
    root = _fake_root(tmp_path)  # nothing written to REL

    problems, checked, _ = check(_gen(), root=root)

    assert _kinds(problems) == ["MISSING"]
    assert checked == []


def test_gdg4_silent_generator_fires(tmp_path):
    """[GDG-4] Exits 0, writes nothing. A naive loop iterates zero times and passes."""
    root = _fake_root(tmp_path, names=())
    (root / REL).write_text(BODY, encoding="utf-8")

    problems, checked, ran = check(_gen(), root=root)

    assert _kinds(problems) == ["SILENT"]
    assert "$FAKE_OUT" in problems[0]
    assert checked == []
    assert ran == ["fake"]  # it DID run — that is what makes silence dangerous


def test_gdg5_wrong_output_name_fires(tmp_path):
    """[GDG-5] Output under a name the registry does not claim is still silence."""
    root = _fake_root(tmp_path, names=("SOMETHING_ELSE.md",))
    (root / REL).write_text(BODY, encoding="utf-8")

    problems, checked, _ = check(_gen(), root=root)

    assert _kinds(problems) == ["SILENT"]
    assert "SOMETHING_ELSE.md" in problems[0]
    assert checked == []


def test_gdg6_nonzero_exit_fires(tmp_path):
    """[GDG-6] A generator that fails must not be mistaken for a generator that agrees."""
    root = _fake_root(tmp_path, rc=3)
    (root / REL).write_text(BODY, encoding="utf-8")

    problems, checked, ran = check(_gen(), root=root)

    assert _kinds(problems) == ["BROKEN"]
    assert "exited 3" in problems[0]
    assert "fake generator refused" in problems[0]
    assert checked == [] and ran == []


def test_gdg7_unrunnable_command_fires(tmp_path):
    """[GDG-7] `node` absent on the runner must fail loudly, not silently skip."""
    root = _fake_root(tmp_path)
    (root / REL).write_text(BODY, encoding="utf-8")

    problems, _, ran = check(_gen(cmd=("definitely-not-a-real-binary-xyz",)), root=root)

    assert _kinds(problems) == ["BROKEN"]
    assert "could not run" in problems[0]
    assert ran == []


def test_gdg8_ungated_generated_doc_fires(tmp_path):
    """[GDG-8] The omission failure — a generated doc no registry entry owns."""
    root = _fake_root(tmp_path)
    (root / REL).write_text(BODY, encoding="utf-8")
    (root / "docs" / "dev" / "reference" / "ORPHAN.md").write_text(
        BODY, encoding="utf-8"
    )

    problems, _, _ = check(_gen(), root=root)

    assert _kinds(problems) == ["UNGATED"]
    assert "ORPHAN.md" in problems[0]


def test_gdg9_empty_registry_is_a_failure(tmp_path):
    """[GDG-9] A gate wired to nothing must say so rather than report success."""
    problems, checked, ran = check((), root=_fake_root(tmp_path))

    assert _kinds(problems) == ["FAIL"]
    assert checked == [] and ran == []


def test_gdg10_crlf_working_copy_is_not_stale(tmp_path):
    """[GDG-10] Generators emit LF; a Windows checkout holds CRLF; git normalises.

    Pins the BEHAVIOUR, not a mechanism. A mutation probe showed this passes even
    with `norm()` blinded, because `Path.read_text` already does universal-newline
    translation — so the claim "the normalisation is what saves us" was wrong. What
    the test is worth keeping for is unchanged: a switch to `read_bytes().decode()`
    would report every Windows working copy stale, and a gate that cries wolf on
    every local run gets disabled.
    """
    root = _fake_root(tmp_path)
    (root / REL).write_bytes(BODY.replace("\n", "\r\n").encode("utf-8"))

    problems, checked, _ = check(_gen(), root=root)

    assert problems == []
    assert checked == [REL]


def test_gdg11_banner_in_body_is_not_a_generated_file(tmp_path):
    """[GDG-11] The design notes discuss the banner in prose. Only line one counts."""
    root = _fake_root(tmp_path)
    (root / REL).write_text(BODY, encoding="utf-8")
    (root / "docs" / "dev" / "about-generated-docs.md").write_text(
        "# How the layer works\n\nEvery one starts with a `GENERATED FILE` banner.\n",
        encoding="utf-8",
    )

    assert banner_bearing_files(root, ("docs",)) == {REL}
    assert check(_gen(), root=root)[0] == []


def test_gdg12_real_registry_is_well_formed():
    """[GDG-12] Shape of the shipped registry — the part a typo breaks.

    Deliberately does not RUN anything: the live run is the CI gate itself. This
    catches a whole-file entry whose files straddle two directories (one generator
    writes into one output dir, so the redirect could not satisfy both) and a
    duplicate id, which would silently collide in the scratch tree.
    """
    assert GENERATORS, "the registry must not be empty"

    ids = [g.id for g in GENERATORS]
    assert len(ids) == len(set(ids)), f"duplicate generator ids: {ids}"

    for gen in GENERATORS:
        assert gen.files, f"{gen.id} registers no files"
        if not gen.out_env:
            continue  # region generator: `files` is documentation, and may glob
        assert gen.out_dir  # raises ValueError if the files straddle directories
        for rel in gen.files:
            assert (REPO / rel).is_file(), f"{gen.id} names a file not in the tree: {rel}"


def test_gdg13_region_generator_clean(tmp_path):
    """[GDG-13] A region generator whose own check exits 0 reports nothing."""
    root = _fake_root(tmp_path, rc=0)
    gens = (
        Generator(
            id="region",
            cmd=(sys.executable, "fakegen.py"),
            check_cmd=(sys.executable, "fakegen.py"),
            files=("docs/testing/subsystems/*.md",),
        ),
    )

    problems, checked, ran = check(gens, root=root)

    assert problems == []
    assert checked == ["docs/testing/subsystems/*.md"] and ran == ["region"]


def test_gdg14_region_generator_stale(tmp_path):
    """[GDG-14] Non-zero from a region generator's own check is STALE, and names the fix."""
    root = _fake_root(tmp_path, rc=1)
    gens = (
        Generator(
            id="region",
            cmd=(sys.executable, "fakegen.py", "--write"),
            check_cmd=(sys.executable, "fakegen.py"),
            files=("docs/testing/subsystems/*.md",),
        ),
    )

    problems, _, ran = check(gens, root=root)

    assert _kinds(problems) == ["STALE"]
    assert "fakegen.py --write" in problems[0]
    assert ran == ["region"]


def test_gdg15_region_check_that_cannot_run_is_broken_not_stale(tmp_path):
    """[GDG-15] `node` missing from a runner must not read as "your docs are stale".

    The two are opposite instructions: STALE says run the generator, BROKEN says fix
    the environment. Collapsing them sends the reader to regenerate a document that
    was already current.
    """
    root = _fake_root(tmp_path)
    gens = (
        Generator(
            id="region",
            cmd=("definitely-not-a-real-binary-xyz",),
            check_cmd=("definitely-not-a-real-binary-xyz", "--check"),
            files=("docs/testing/subsystems/*.md",),
        ),
    )

    problems, _, ran = check(gens, root=root)

    assert _kinds(problems) == ["BROKEN"]
    assert ran == []


def test_gdg16_entry_must_declare_exactly_one_shape():
    """[GDG-16] Neither shape, or both, is a registry error rather than a silent skip."""
    with pytest.raises(ValueError, match="exactly one"):
        Generator(id="neither", cmd=("x",), files=("a.md",))

    with pytest.raises(ValueError, match="exactly one"):
        Generator(
            id="both", cmd=("x",), files=("a.md",), out_env="OUT", check_cmd=("x", "-c")
        )
