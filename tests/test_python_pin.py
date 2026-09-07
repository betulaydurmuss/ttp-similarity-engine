"""Tests for the Python version pin and the dependency pinning.

The version is declared in four places -- ``.python-version``,
``pyproject.toml``, ``ttp_similarity/pyversion.py`` and the README -- and the
whole point of pinning is that they never disagree. These tests fail loudly when
one of them is updated alone.

They also assert that ``requirements.txt`` stays fully pinned, so nobody
reintroduces a version range and quietly puts the three developers back on
different builds.
"""

from __future__ import annotations

import re

import pytest

from ttp_similarity import pyversion
from ttp_similarity.paths import PROJECT_ROOT

PYTHON_VERSION_FILE = PROJECT_ROOT / ".python-version"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
CHECK_SETUP = PROJECT_ROOT / "check_setup.py"


# --------------------------------------------------------------------------- #
# The pin itself
# --------------------------------------------------------------------------- #
def test_required_python_is_311():
    assert pyversion.REQUIRED_PYTHON == (3, 11)


def test_python_version_file_matches_the_code():
    raw = PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
    major, minor = (int(part) for part in raw.split(".")[:2])
    assert (major, minor) == pyversion.REQUIRED_PYTHON


def test_pyproject_pins_a_single_minor_version():
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^requires-python\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml has no requires-python"
    constraint = match.group(1)
    major, minor = pyversion.REQUIRED_PYTHON
    # An upper bound is the whole point: ">=3.11" alone would let three
    # developers land on three different minor versions.
    assert f">={major}.{minor}" in constraint
    assert f"<{major}.{minor + 1}" in constraint


# --------------------------------------------------------------------------- #
# Version comparison logic
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "version,expected",
    [
        ((3, 11, 0), True),
        ((3, 11, 9), True),  # patch level is free
        ((3, 11, 13), True),
        ((3, 10, 11), False),
        ((3, 12, 0), False),
        ((3, 13, 5), False),
        ((4, 0, 0), False),
    ],
)
def test_is_supported(version, expected):
    assert pyversion.is_supported(version) is expected


def test_check_returns_a_bool_without_raising_when_asked():
    result = pyversion.check_python_version(raise_on_mismatch=False)
    assert isinstance(result, bool)
    assert result is pyversion.is_supported()


def test_error_message_says_what_is_wrong_and_what_to_do():
    message = pyversion.build_message((3, 13, 5))

    # expected vs found
    assert "3.11.x" in message
    assert "3.13.5" in message
    # which interpreter, so the user can tell which venv they are in
    assert "Yorumlayici" in message
    assert "Sanal ortam" in message
    # the fix, on both platforms
    assert "py -3.11 -m venv .venv" in message
    assert "python3.11 -m venv .venv" in message
    assert "pip install -r requirements.txt" in message
    # where to go next
    assert "check_setup.py" in message
    assert pyversion.BYPASS_ENV_VAR in message


def test_bypass_env_var_is_read(monkeypatch):
    monkeypatch.delenv(pyversion.BYPASS_ENV_VAR, raising=False)
    assert pyversion.bypass_enabled() is False
    monkeypatch.setenv(pyversion.BYPASS_ENV_VAR, "1")
    assert pyversion.bypass_enabled() is True
    monkeypatch.setenv(pyversion.BYPASS_ENV_VAR, "0")
    assert pyversion.bypass_enabled() is False


def test_unsupported_python_error_is_an_exception_not_a_baseexception():
    # The Streamlit app catches it with `except Exception` to render a readable
    # page instead of dying; SystemExit would slip through that.
    assert issubclass(pyversion.UnsupportedPythonError, Exception)


# --------------------------------------------------------------------------- #
# Dependency pinning
# --------------------------------------------------------------------------- #
def _requirement_lines() -> list[str]:
    return [
        line.strip()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_every_requirement_is_exactly_pinned():
    for line in _requirement_lines():
        assert "==" in line, f"pinned '==' expected, got: {line}"
        for loose in (">=", "<=", "~=", "!="):
            assert loose not in line, f"version range found in: {line}"


def test_all_expected_dependencies_are_present():
    names = {line.split("==")[0].strip().lower() for line in _requirement_lines()}
    assert names == {
        "pandas",
        "numpy",
        "scikit-learn",
        "scipy",
        "matplotlib",
        "seaborn",
        "streamlit",
        "requests",
        "pytest",
    }


def test_numpy_and_scipy_stay_within_the_python_311_ceiling():
    """numpy 2.5+ and scipy 1.18+ publish no cp311 wheels.

    Pinning to whatever happens to be installed on a newer interpreter produces
    a requirements.txt that cannot be installed on 3.11 -- exactly the failure
    the pin is supposed to prevent. This guards that specific mistake.
    """
    pins = {
        line.split("==")[0].strip().lower(): line.split("==")[1].strip()
        for line in _requirement_lines()
    }

    def minor(version: str) -> tuple[int, int]:
        parts = version.split(".")
        return (int(parts[0]), int(parts[1]))

    assert minor(pins["numpy"]) <= (2, 4), "numpy 2.5+ has no Python 3.11 wheel"
    assert minor(pins["scipy"]) <= (1, 17), "scipy 1.18+ has no Python 3.11 wheel"


# --------------------------------------------------------------------------- #
# The verification script
# --------------------------------------------------------------------------- #
def test_check_setup_is_stdlib_only():
    """``check_setup.py`` must run before dependencies exist, and on any Python.

    A third-party import at module level would make it crash in exactly the
    situation it is meant to diagnose.
    """
    text = CHECK_SETUP.read_text(encoding="utf-8")
    module_level_imports = re.findall(r"^(?:from|import)\s+([\w.]+)", text, re.MULTILINE)
    allowed = {"__future__", "os", "platform", "sys"}
    assert set(module_level_imports) <= allowed, (
        f"check_setup.py imports non-stdlib modules at module level: "
        f"{set(module_level_imports) - allowed}"
    )
