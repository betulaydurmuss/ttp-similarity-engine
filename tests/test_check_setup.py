import os
import py_compile
import subprocess
import sys

from ttp_similarity.paths import PROJECT_ROOT

CHECK_SETUP = PROJECT_ROOT / "check_setup.py"


def test_check_setup_compiles():
    py_compile.compile(str(CHECK_SETUP), doraise=True)


def test_check_setup_runs_every_step_and_reports():
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [sys.executable, str(CHECK_SETUP)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=120,
    )
    assert completed.returncode in (0, 1), completed.stderr
    assert "Traceback" not in completed.stderr
    for step in ("[1/4]", "[2/4]", "[3/4]", "[4/4]", "OZET"):
        assert step in completed.stdout
