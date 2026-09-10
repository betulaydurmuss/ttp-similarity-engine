"""Stage-1 orchestrator: download -> parse -> normalise -> write.

This is the module the other three teams call (or run) to get their inputs.
It produces the identical artefact set for both datasets:

* ``--dataset attck`` runs the real ATT&CK Enterprise pipeline.
* ``--dataset mock`` delegates to
  :func:`ttp_similarity.data.mock_dataset.build_mock_dataset`.

Both write the same files with the same columns, so everything downstream is
dataset-agnostic.

Run::

    python -m ttp_similarity.data.build --dataset attck
    python -m ttp_similarity.data.build --dataset attck --force-download
    python -m ttp_similarity.data.build --dataset mock

Owner: data module.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import pandas as pd

from .. import config, paths, storage
from ..schema import TECHNIQUE_COLUMNS, Actor, BuildManifest, Technique, join_list
from . import frequency as frequency_mod
from . import mock_dataset, normalize, stix_download, stix_parse


def write_dataset(
    actors: Sequence[Actor],
    techniques: Mapping[str, Technique],
    workspace: paths.Workspace,
    *,
    source: str,
    attack_version: str | None,
    notes: str = "",
    stats: Mapping[str, Any] | None = None,
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
        stats: Ingestion counts; written to ``build_stats.json`` when given.

    Returns:
        The workspace that was written.

    Raises:
        ValueError: If ``actors`` is empty -- writing an empty dataset would
            fail much later, inside the engine, with a confusing message.
    """
    if not actors:
        raise ValueError(f"refusing to write an empty dataset to {workspace.root}")

    workspace.ensure()
    names = {tid: technique.technique_name for tid, technique in techniques.items()}

    techniques_frame = pd.DataFrame(
        [
            {
                "technique_id": technique.technique_id,
                "technique_name": technique.technique_name,
                "tactics": join_list(technique.tactics),
            }
            for technique in techniques.values()
        ],
        columns=list(TECHNIQUE_COLUMNS),
    ).sort_values("technique_id").reset_index(drop=True)

    edges = frequency_mod.build_actor_technique_frame(actors, names)
    freq = frequency_mod.compute_technique_frequency(actors, names)

    storage.write_actors(actors, workspace.actors)
    storage.write_dataframe(techniques_frame, workspace.techniques, TECHNIQUE_COLUMNS)
    storage.write_dataframe(edges, workspace.actor_technique)
    storage.write_dataframe(freq, workspace.technique_frequency)
    storage.write_manifest(
        BuildManifest(
            dataset=workspace.name,
            source=source,
            attack_version=attack_version,
            built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            actor_count=len(actors),
            technique_count=len(techniques),
            edge_count=len(edges),
            notes=notes,
        ),
        workspace.data_manifest,
    )
    if stats is not None:
        storage.write_json(workspace.build_stats, dict(stats))
    return workspace


def build_attck_dataset(
    workspace: paths.Workspace | None = None,
    *,
    force_download: bool = False,
) -> paths.Workspace:
    """Run the real ATT&CK Enterprise pipeline end to end.

    Steps:
        1. :func:`~ttp_similarity.data.stix_download.fetch_attack_bundle`
        2. :func:`~ttp_similarity.data.stix_parse.parse_bundle`
        3. :func:`~ttp_similarity.data.normalize.normalize_bundle`
        4. :func:`write_dataset` (which computes the frequency table)

    Args:
        workspace: Destination; defaults to the ``attck`` workspace.
        force_download: Re-fetch the bundle even if cached.

    Returns:
        The workspace that was written.
    """
    workspace = (workspace or paths.Workspace.get(paths.ATTCK_DATASET)).ensure()

    bundle_path = stix_download.fetch_attack_bundle(force=force_download)
    metadata = stix_download.read_bundle_metadata()

    print("[parse] reading bundle...")
    parsed = stix_parse.parse_bundle(bundle_path)
    print(f"[parse] {parsed.summary()}")
    print(
        f"[parse] dropped: {parsed.stats['actors_dropped']} intrusion-sets, "
        f"{parsed.stats['techniques_dropped']} attack-patterns "
        "(revoked/deprecated)"
    )

    print("[normalize] rolling up sub-techniques, merging aliases...")
    result = normalize.normalize_bundle(parsed)
    print(
        f"[normalize] edges {result.stats['edges_before_rollup']} -> "
        f"{result.stats['edges_after_rollup']} after roll-up; "
        f"{result.stats['alias_merge_count']} alias merges; "
        f"{result.stats['actors_dropped_sparse']} sparse actors dropped"
    )

    stats = dict(result.stats)
    stats["bundle"] = {
        "path": str(bundle_path),
        "url": metadata.get("url"),
        "downloaded_at": metadata.get("downloaded_at"),
        "sha256": metadata.get("sha256"),
        "size_bytes": metadata.get("size_bytes"),
        "etag": metadata.get("etag"),
    }
    stats["alias_merges"] = [merge.to_dict() for merge in result.merges]

    return write_dataset(
        result.actors,
        result.techniques,
        workspace,
        source="mitre-attack-stix",
        attack_version=parsed.attack_version,
        notes=(
            f"MITRE ATT&CK Enterprise v{parsed.attack_version}, downloaded "
            f"{metadata.get('downloaded_at')}. Sub-techniques rolled up to parents; "
            f"revoked/deprecated objects dropped; actors with fewer than "
            f"{config.MIN_TECHNIQUES_PER_ACTOR} techniques excluded."
        ),
        stats=stats,
    )


def build_dataset(
    dataset: str, *, force_download: bool = False, seed: int | None = None
) -> paths.Workspace:
    """Build whichever dataset was asked for.

    Args:
        dataset: ``"attck"`` or ``"mock"``.
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
    if dataset == paths.ATTCK_DATASET:
        return build_attck_dataset(workspace, force_download=force_download)
    raise ValueError(f"unknown dataset {dataset!r}; expected one of {paths.KNOWN_DATASETS}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m ttp_similarity.data.build``."""
    parser = argparse.ArgumentParser(description="Build a stage-1 actor/technique dataset.")
    parser.add_argument(
        "--dataset",
        default=paths.ATTCK_DATASET,
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
    print(f"\ndataset '{workspace.name}' written to {workspace.root}")
    print(
        f"  actors={manifest.actor_count}  techniques={manifest.technique_count}  "
        f"edges={manifest.edge_count}"
    )
    print(f"  source={manifest.source}  attack_version={manifest.attack_version}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
