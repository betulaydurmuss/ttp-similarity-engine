"""Python interpreter version guard.

The project is pinned to a single Python minor version (3.11) so that three
people on three machines run the same interpreter. This module is imported by
:mod:`ttp_similarity` before anything else, so a wrong interpreter fails
immediately with an actionable message instead of surfacing later as a subtle
behavioural difference.

Deliberately written to parse and run on **old** Python versions: it has to be
able to report "you are on 3.8" rather than raise a SyntaxError on 3.8. That
means no match statements, no ``X | Y`` runtime unions, stdlib only.

Escape hatch: setting ``TTP_SIMILARITY_ALLOW_ANY_PYTHON=1`` downgrades the
error to a warning. It exists for one-off experiments and CI matrix runs; it is
not a supported configuration and the warning says so.
"""

from __future__ import annotations

import os
import sys
import warnings

#: The one supported interpreter, as (major, minor). Patch level is free.
REQUIRED_PYTHON = (3, 11)

#: Set to "1"/"true"/"yes" to downgrade the hard error to a warning.
BYPASS_ENV_VAR = "TTP_SIMILARITY_ALLOW_ANY_PYTHON"

_TRUTHY = ("1", "true", "yes", "on")


class UnsupportedPythonError(RuntimeError):
    """Raised when the running interpreter is not the pinned version."""


def format_version(version):
    """Render a version tuple as ``"3.11.9"``.

    Args:
        version: Sequence of version components.

    Returns:
        Dotted string.
    """
    return ".".join(str(part) for part in version)


def current_version():
    """Return the running interpreter version as ``(major, minor, micro)``."""
    return (sys.version_info[0], sys.version_info[1], sys.version_info[2])


def in_virtualenv():
    """True when running inside a virtual environment."""
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def is_supported(version=None):
    """Whether ``version`` matches the pinned major.minor.

    Args:
        version: ``(major, minor, ...)``; defaults to the running interpreter.

    Returns:
        ``True`` when the major and minor components match :data:`REQUIRED_PYTHON`.
    """
    if version is None:
        version = current_version()
    return (version[0], version[1]) == REQUIRED_PYTHON


def bypass_enabled():
    """True when the escape-hatch environment variable is set to a truthy value."""
    return os.environ.get(BYPASS_ENV_VAR, "").strip().lower() in _TRUTHY


def build_message(version=None):
    """Compose the full "wrong interpreter" message.

    States what was expected, what was found, where that interpreter is, and the
    exact commands to fix it on each platform. Kept in one place so the package
    guard, the CLI and ``check_setup.py`` all say the same thing.

    Args:
        version: Version to report; defaults to the running interpreter.

    Returns:
        A multi-line, ready-to-print string.
    """
    if version is None:
        version = current_version()
    expected = "%d.%d.x" % REQUIRED_PYTHON
    venv = sys.prefix if in_virtualenv() else "yok (sanal ortam aktif degil)"
    line = "=" * 70
    return "\n".join(
        [
            line,
            " ttp-similarity-engine: yanlis Python surumu",
            line,
            "  Beklenen    : Python %s" % expected,
            "  Bulunan     : Python %s" % format_version(version),
            "  Yorumlayici : %s" % sys.executable,
            "  Sanal ortam : %s" % venv,
            "",
            " Bu proje tek bir Python surumune sabitlenmistir (bkz. DECISIONS.md).",
            " Duzeltmek icin, depo kokunde:",
            "",
            "  Windows (PowerShell):",
            "    py -3.11 -m venv .venv",
            "    .venv\\Scripts\\Activate.ps1",
            "    pip install -r requirements.txt",
            "",
            "  macOS / Linux:",
            "    python3.11 -m venv .venv",
            "    source .venv/bin/activate",
            "    pip install -r requirements.txt",
            "",
            " Kurulumu dogrulamak icin : python check_setup.py",
            " Python 3.11 kurulu degilse: README.md > Kurulum bolumu",
            "",
            " (Kontrolu gecici olarak devre disi birakmak icin %s=1;" % BYPASS_ENV_VAR,
            "  bu desteklenmeyen bir yapilandirmadir.)",
            line,
        ]
    )


def check_python_version(raise_on_mismatch=True):
    """Verify the running interpreter, loudly.

    Called at package import time, so no code path can silently run on the wrong
    interpreter.

    Args:
        raise_on_mismatch: Raise on mismatch. When ``False``, only warn and
            return the result -- used by ``check_setup.py``, which needs to
            report the problem rather than die on it.

    Returns:
        ``True`` when the interpreter matches, ``False`` otherwise.

    Raises:
        UnsupportedPythonError: On mismatch, unless ``raise_on_mismatch`` is
            ``False`` or :data:`BYPASS_ENV_VAR` is set.
    """
    if is_supported():
        return True

    message = build_message()
    if bypass_enabled():
        warnings.warn(
            "%s ayarli: desteklenmeyen Python %s uzerinde calisiliyor "
            "(beklenen %d.%d.x)."
            % (
                BYPASS_ENV_VAR,
                format_version(current_version()),
                REQUIRED_PYTHON[0],
                REQUIRED_PYTHON[1],
            ),
            RuntimeWarning,
            stacklevel=2,
        )
        return False
    if raise_on_mismatch:
        raise UnsupportedPythonError("\n" + message)
    return False
