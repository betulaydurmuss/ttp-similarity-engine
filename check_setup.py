#!/usr/bin/env python
"""One-command setup verification for ttp-similarity-engine.

Usage (from the repository root)::

    python check_setup.py

Checks, in order:

1. Interpreter version against the pin in ``.python-version`` /
   :data:`ttp_similarity.pyversion.REQUIRED_PYTHON`, plus whether a virtual
   environment is active.
2. Every pinned dependency in ``requirements.txt``: installed? correct version?
3. That the critical third-party imports actually work (a package can be
   installed and still fail to import -- wrong wheel, broken binary).
4. That ``ttp_similarity`` itself imports, and that the mock dataset is present.

Exits ``0`` when everything is fine, ``1`` when anything is wrong, and prints
what to do about it.

Deliberately stdlib-only and written for old Python syntax, because it must be
able to run *on the wrong interpreter* and diagnose that as its first finding.
Do not import third-party packages at module level here.
"""

from __future__ import annotations

import os
import platform
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = os.path.join(REPO_ROOT, "requirements.txt")
PYTHON_VERSION_FILE = os.path.join(REPO_ROOT, ".python-version")

#: Imports that must work for the pipeline to run at all. ``(module, label)``.
CRITICAL_IMPORTS = (
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("sklearn", "scikit-learn"),
    ("scipy", "scipy"),
    ("matplotlib", "matplotlib"),
    ("seaborn", "seaborn"),
    ("streamlit", "streamlit"),
    ("requests", "requests"),
)

#: Distribution name -> import name, where they differ.
IMPORT_NAMES = {"scikit-learn": "sklearn"}

OK = "ok"
FAIL = "HATA"
WARN = "UYARI"


class Results(object):
    """Accumulates findings and the remediation lines to print at the end."""

    def __init__(self):
        self.errors = 0
        self.warnings = 0
        self.todo = []

    def fail(self, action):
        self.errors += 1
        if action and action not in self.todo:
            self.todo.append(action)

    def warn(self, action):
        self.warnings += 1
        if action and action not in self.todo:
            self.todo.append(action)


def heading(text):
    print("")
    print(text)
    print("-" * len(text))


def read_pinned_python():
    """Read the pinned ``major.minor`` from ``.python-version``.

    Returns:
        ``(major, minor)``, or ``None`` when the file is missing or unparsable.
    """
    try:
        with open(PYTHON_VERSION_FILE) as handle:
            raw = handle.read().strip()
    except IOError:
        return None
    parts = raw.split(".")
    try:
        return (int(parts[0]), int(parts[1]))
    except (IndexError, ValueError):
        return None


def parse_requirements():
    """Parse ``requirements.txt`` into ``[(name, pinned_version_or_None), ...]``.

    Returns:
        List of requirements in file order. Comments and blank lines skipped.
    """
    requirements = []
    try:
        with open(REQUIREMENTS, encoding="utf-8") as handle:
            lines = handle.readlines()
    except IOError:
        return requirements
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, _, version = line.partition("==")
            requirements.append((name.strip(), version.strip()))
        else:
            for separator in (">=", "<=", "~=", ">", "<"):
                if separator in line:
                    requirements.append((line.split(separator)[0].strip(), None))
                    break
            else:
                requirements.append((line, None))
    return requirements


def installed_version(distribution):
    """Installed version of a distribution, or ``None`` when absent."""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # Python < 3.8
        return None
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def check_python(results):
    """Check the interpreter version and virtual-environment status."""
    heading("[1/4] Python surumu")

    pinned = read_pinned_python()
    required = pinned if pinned else (3, 11)
    running = sys.version_info[:3]
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)

    print("  beklenen     : Python %d.%d.x" % required + ("  (.python-version)" if pinned else ""))
    print("  bulunan      : Python %d.%d.%d" % running)
    print("  yorumlayici  : %s" % sys.executable)
    print("  platform     : %s" % platform.platform())
    print("  sanal ortam  : %s" % (sys.prefix if in_venv else "YOK - aktif degil"))

    if running[:2] == required:
        print("  sonuc        : %s" % OK)
    else:
        print("  sonuc        : %s - surum uyusmuyor" % FAIL)
        results.fail(
            "Python %d.%d ile sanal ortami yeniden kurun "
            "(README.md > Kurulum)." % required
        )

    if not in_venv:
        print("  not          : %s - sanal ortam aktif degil, sistem Python'u kullaniliyor" % WARN)
        results.warn("Sanal ortami aktive edin (.venv\\Scripts\\Activate.ps1 / source .venv/bin/activate).")


def check_dependencies(results):
    """Check every pinned requirement against what is installed."""
    heading("[2/4] Bagimliliklar (requirements.txt)")

    requirements = parse_requirements()
    if not requirements:
        print("  %s - requirements.txt okunamadi: %s" % (FAIL, REQUIREMENTS))
        results.fail("requirements.txt dosyasini kontrol edin.")
        return

    print("  %-18s %-12s %-12s %s" % ("paket", "beklenen", "bulunan", "durum"))
    missing = False
    mismatched = False
    for name, pinned in requirements:
        found = installed_version(name)
        expected = pinned if pinned else "(sabit degil)"
        if found is None:
            status = FAIL + " kurulu degil"
            missing = True
        elif pinned and found != pinned:
            status = FAIL + " farkli surum"
            mismatched = True
        else:
            status = OK
        print("  %-18s %-12s %-12s %s" % (name, expected, found or "-", status))

    if missing or mismatched:
        results.fail("pip install -r requirements.txt  (gerekirse --force-reinstall)")


def check_imports(results):
    """Check that the critical third-party imports actually execute."""
    heading("[3/4] Kritik importlar")

    for module_name, label in CRITICAL_IMPORTS:
        try:
            __import__(module_name)
        except Exception as error:  # noqa: BLE001 - we report anything at all
            print("  %-14s %s - %s: %s" % (label, FAIL, type(error).__name__, error))
            results.fail("pip install -r requirements.txt")
        else:
            print("  %-14s %s" % (label, OK))


def check_package(results):
    """Check that the project package imports and that a dataset is built."""
    heading("[4/4] Proje paketi")

    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    try:
        import ttp_similarity
    except Exception as error:  # noqa: BLE001
        name = type(error).__name__
        if name == "UnsupportedPythonError":
            # Already reported in step 1; do not print the full banner twice.
            print("  ttp_similarity  %s - yanlis Python surumu nedeniyle yuklenemedi" % FAIL)
        else:
            print("  ttp_similarity  %s - %s: %s" % (FAIL, name, error))
            results.fail("Paket import hatasini giderin.")
        return

    print("  ttp_similarity  %s (surum %s)" % (OK, ttp_similarity.__version__))

    try:
        from ttp_similarity import paths, storage
    except Exception as error:  # noqa: BLE001
        print("  alt moduller    %s - %s: %s" % (FAIL, type(error).__name__, error))
        results.fail("Paket import hatasini giderin.")
        return

    print("  alt moduller    %s" % OK)

    workspace = paths.Workspace.get(paths.MOCK_DATASET)
    if storage.dataset_exists(workspace):
        print("  mock veri seti  %s (%s)" % (OK, workspace.root))
    else:
        print("  mock veri seti  %s - henuz uretilmemis" % WARN)
        results.warn("python -m ttp_similarity.data.mock_dataset")

    if storage.engine_exists(workspace):
        print("  motor artefakt  %s" % OK)
    else:
        print("  motor artefakt  %s - henuz uretilmemis (engine modulu TODO)" % WARN)
        results.warn("python -m ttp_similarity.engine.build --dataset mock")


def main():
    """Run every check and print the summary. Returns the process exit code."""
    print("=" * 70)
    print(" ttp-similarity-engine  --  kurulum kontrolu")
    print("=" * 70)

    results = Results()
    check_python(results)
    check_dependencies(results)
    check_imports(results)
    check_package(results)

    print("")
    print("=" * 70)
    if results.errors:
        print(" OZET: %d hata, %d uyari" % (results.errors, results.warnings))
    elif results.warnings:
        print(" OZET: kurulum dogru, %d uyari" % results.warnings)
    else:
        print(" OZET: her sey yolunda.")
    if results.todo:
        print("")
        print(" Yapilmasi gerekenler:")
        for index, action in enumerate(results.todo, start=1):
            print("   %d. %s" % (index, action))
    print("=" * 70)
    return 1 if results.errors else 0


if __name__ == "__main__":
    sys.exit(main())
