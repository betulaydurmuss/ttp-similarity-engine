"""ttp-similarity-engine.

Behavioural similarity engine for threat-actor TTP sets built on MITRE ATT&CK
Enterprise.

The package is split into four independently runnable modules:

* ``ttp_similarity.data``       -- ATT&CK ingestion, normalisation, frequency table
* ``ttp_similarity.engine``     -- weighting, vectorisation, similarity, clustering, query
* ``ttp_similarity.evaluation`` -- retrieval benchmark over known actors
* ``ttp_similarity.app``        -- Streamlit UI

Every module reads its inputs from disk and writes its outputs to disk, so the
three of them can be developed in parallel against the file contract described
in :mod:`ttp_similarity.schema` and :mod:`ttp_similarity.paths`.

The interpreter version is checked here, at import time. Every CLI entry point
(``python -m ttp_similarity...``), the Streamlit app and the test suite import
this package, so there is no way to run any part of the project on the wrong
Python without being told. See :mod:`ttp_similarity.pyversion`.

This project measures *behavioural similarity only*. It does not perform, nor
support, attribution claims about real-world actors.
"""

from __future__ import annotations

from .pyversion import (  # noqa: F401  (re-exported for callers and tests)
    REQUIRED_PYTHON,
    UnsupportedPythonError,
    check_python_version,
)

# Fail fast, before any dependency is imported: a wrong interpreter otherwise
# surfaces as a confusing third-party traceback (or, worse, as a silent
# behavioural difference between two developers' machines).
check_python_version()

__version__ = "0.1.0"

__all__ = [
    "REQUIRED_PYTHON",
    "UnsupportedPythonError",
    "check_python_version",
    "__version__",
]
