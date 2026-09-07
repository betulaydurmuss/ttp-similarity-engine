"""Stage-1 orchestrator: download -> parse -> normalise -> write.

This is the module the other three teams call (or run) to get their inputs.
It produces the identical artefact set for both datasets:

* ``--dataset mitre`` runs the real ATT&CK pipeline (still TODO).
* ``--dataset mock`` delegates to
  :func:`ttp_similarity.data.mock_dataset.build_mock_dataset` and works today.

Run::

    python -m ttp_similarity.data.build --dataset mock
    python -m ttp_similarity.data.build --dataset mitre --force-download

Owner: data module.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Sequence

from .. import config, paths, storage
from ..schema import TECHNIQUE_COLUMNS, Actor, BuildManifest, join_list
from . import frequency as frequency_mod
from . import mock_dataset, normalize, stix_download, stix_parse


def write_dataset(
    actors: Sequence[Actor],
    techniques: dict,
    workspace: paths.Workspace,
    *,
    source: str,
    attack_version: str | None,
    notes: str = "",
) -> paths.Workspace:
    """Write the canonical model out as the stage-1 artefact set.

    Shared by the real and the synthetic pipeline so both are guaranteed to
    produce the same columns in the same order.

    Args:
        actors: Normalised actor records.
        techniques: ``technique_id -> Technique`` catalogue.
        workspace: Destination workspace.
        source: Provenance tag for the manifest.
        attack_version: ATT&CK release, when known.
        notes: Free-text note stored in the manifest.

    Returns:
        The workspace that was written.
    """
    # TODO(data): build the three frames via frequency_mod helpers and the
    #   catalogue, then hand each to storage.write_* with its column contract.
    #   Mirror mock_dataset.build_mock_dataset(), which already does exactly
    #   this -- factor the shared part here once the real path exists.
    raise NotImplementedError("write_dataset")


def build_mitre_dataset(
    workspace: paths.Workspace | None = None,
    *,
    force_download: bool = False,
) -> paths.Workspace:
    """Run the real ATT&CK Enterprise pipeline end to end.

    Steps:
        1. :func:`~ttp_similarity.data.stix_download.fetch_attack_bundle`
        2. :func:`~ttp_similarity.data.stix_parse.parse_bundle`
        3. :func:`~ttp_similarity.data.normalize.normalize_bundle`
        4. :func:`~ttp_similarity.data.frequency.compute_technique_frequency`
        5. :func:`write_dataset`

    Args:
        workspace: Destination; defaults to the ``mitre`` workspace.
        force_download: Re-fetch the bundle even if cached.

    Returns:
        The workspace that was written.
    """
    workspace = (workspace or paths.Workspace.get(paths.MITRE_DATASET)).ensure()
    # TODO(data): bundle_path = stix_download.fetch_attack_bundle(force=force_download)
    # TODO(data): parsed = stix_parse.parse_bundle(bundle_path); log parsed.summary()
    # TODO(data): actors, catalogue = normalize.normalize_bundle(parsed)
    # TODO(data): return write_dataset(actors, catalogue, workspace,
    #   source="mitre-attack-stix", attack_version=parsed.attack_version)
    raise NotImplementedError("build_mitre_dataset")


def build_dataset(dataset: str, *, force_download: bool = False, seed: int | None = None):
    """Build whichever dataset was asked for.

    Args:
        dataset: ``"mitre"`` or ``"mock"``.
        force_download: Forwarded to the ATT&CK downloader.
        seed: Forwarded to the mock generator.

    Returns:
        The workspace that was written.

    Raises:
        ValueError: On an unknown dataset name.
    """
    workspace = paths.Workspace.get(dataset)
    if dataset == paths.MOCK_DATASET:
        return mock_dataset.build_mock_dataset(
            workspace, seed=seed if seed is not None else mock_dataset.DEFAULT_SEED
        )
    if dataset == paths.MITRE_DATASET:
        return build_mitre_dataset(workspace, force_download=force_download)
    raise ValueError(f"unknown dataset {dataset!r}; expected one of {paths.KNOWN_DATASETS}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m ttp_similarity.data.build``."""
    parser = argparse.ArgumentParser(description="Build a stage-1 actor/technique dataset.")
    parser.add_argument(
        "--dataset",
        default=paths.MOCK_DATASET,
        choices=list(paths.KNOWN_DATASETS),
        help="which dataset to build",
    )
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--seed", type=int, default=None, help="mock generator seed")
    args = parser.parse_args(argv)

    config.validate()
    paths.ensure_base_dirs()
    workspace = build_dataset(
        args.dataset, force_download=args.force_download, seed=args.seed
    )
    manifest = storage.read_manifest(workspace.data_manifest)
    print(f"dataset '{workspace.name}' written to {workspace.root}")
    print(
        f"  actors={manifest.actor_count}  techniques={manifest.technique_count}  "
        f"edges={manifest.edge_count}  source={manifest.source}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
