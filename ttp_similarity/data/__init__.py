"""Stage 1 -- turn MITRE ATT&CK Enterprise into a clean actor/technique table.

Pipeline::

    stix_download.fetch_attack_bundle()      data/raw/enterprise-attack.json
        -> stix_parse.parse_bundle()         ParsedBundle (in memory)
        -> normalize.normalize_bundle()      list[Actor] + technique catalogue
        -> frequency.compute_technique_frequency()
        -> build.build_attck_dataset()       data/processed/attck/*

The synthetic fixture follows the same contract and is produced by
``mock_dataset.build_mock_dataset()`` into ``data/processed/mock/``. It is a
test fixture only; no user-facing entry point opens it by default.

Owner: data module.
"""

from __future__ import annotations

__all__ = [
    "build",
    "frequency",
    "mock_dataset",
    "normalize",
    "stix_download",
    "stix_parse",
]
