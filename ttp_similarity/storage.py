"""Read/write helpers for the file contract.

Modules never hand each other Python objects; they hand each other files. These
helpers are the only place that knows how those files are encoded (UTF-8 CSV
without an index, pretty JSON, compressed NPZ), so a format change is one edit
rather than four.

:func:`require` is the important one for parallel development: when a module
opens an artefact another team member has not produced yet, it raises an error
that names the exact command to run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from . import paths
from .schema import (
    Actor,
    ActorId,
    BuildManifest,
    SimilarityMatrix,
    TechniqueId,
    VectorSpace,
)

#: Which command regenerates a missing artefact. Keyed by file name so the hint
#: works for any workspace. Keep in sync with the module entry points.
_PRODUCER_HINTS: Mapping[str, str] = {
    "actors.json": "python -m ttp_similarity.data.build --dataset {dataset}",
    "actor_technique.csv": "python -m ttp_similarity.data.build --dataset {dataset}",
    "techniques.csv": "python -m ttp_similarity.data.build --dataset {dataset}",
    "technique_frequency.csv": "python -m ttp_similarity.data.build --dataset {dataset}",
    "manifest.json": "python -m ttp_similarity.data.build --dataset {dataset}",
    "weights.csv": "python -m ttp_similarity.engine.build --dataset {dataset}",
    "vector_space.npz": "python -m ttp_similarity.engine.build --dataset {dataset}",
    "similarity.npz": "python -m ttp_similarity.engine.build --dataset {dataset}",
    "clusters.csv": "python -m ttp_similarity.engine.build --dataset {dataset}",
    "evaluation.json": "python -m ttp_similarity.evaluation.benchmark --dataset {dataset}",
}


class ArtifactMissingError(FileNotFoundError):
    """Raised when a pipeline stage input has not been produced yet."""


def require(path: Path, dataset: str | None = None) -> Path:
    """Return ``path``, or raise a message telling the user how to create it.

    Args:
        path: Artefact expected to exist.
        dataset: Workspace name, used to fill in the suggested command.

    Returns:
        The same path, guaranteed to exist.

    Raises:
        ArtifactMissingError: If the file is absent.
    """
    if path.exists():
        return path
    dataset = dataset or path.parent.name
    hint = _PRODUCER_HINTS.get(path.name)
    suffix = f"\nRun: {hint.format(dataset=dataset)}" if hint else ""
    raise ArtifactMissingError(f"Missing artefact: {path}{suffix}")


def ensure_parent(path: Path) -> Path:
    """Create the parent directory of ``path`` if needed, then return ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# --------------------------------------------------------------------------- #
# JSON
# --------------------------------------------------------------------------- #
def write_json(path: Path, payload: Any) -> Path:
    """Write ``payload`` as UTF-8 JSON (indented, non-ASCII preserved)."""
    ensure_parent(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def read_json(path: Path, dataset: str | None = None) -> Any:
    """Read a JSON artefact, with a helpful error when it is missing."""
    return json.loads(require(path, dataset).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# CSV / DataFrame
# --------------------------------------------------------------------------- #
def write_dataframe(
    frame: pd.DataFrame, path: Path, columns: Sequence[str] | None = None
) -> Path:
    """Write a DataFrame as UTF-8 CSV with no index column.

    Args:
        frame: Data to write.
        path: Destination.
        columns: Expected column contract from :mod:`ttp_similarity.schema`.
            When given, the frame is reordered to match and missing columns
            raise -- this is what keeps the four modules honest.

    Raises:
        ValueError: If ``columns`` are requested and some are absent.
    """
    if columns is not None:
        missing = [c for c in columns if c not in frame.columns]
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {missing}")
        frame = frame.loc[:, list(columns)]
    ensure_parent(path)
    frame.to_csv(path, index=False, encoding="utf-8")
    return path


def read_dataframe(
    path: Path, dataset: str | None = None, columns: Sequence[str] | None = None
) -> pd.DataFrame:
    """Read a CSV artefact and optionally assert its column contract."""
    frame = pd.read_csv(require(path, dataset), encoding="utf-8")
    if columns is not None:
        missing = [c for c in columns if c not in frame.columns]
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {missing}")
    return frame


# --------------------------------------------------------------------------- #
# Actors
# --------------------------------------------------------------------------- #
def write_actors(actors: Iterable[Actor], path: Path) -> Path:
    """Serialise :class:`~ttp_similarity.schema.Actor` records to ``actors.json``."""
    return write_json(path, [actor.to_dict() for actor in actors])


def read_actors(path: Path, dataset: str | None = None) -> tuple[Actor, ...]:
    """Load ``actors.json`` back into :class:`~ttp_similarity.schema.Actor` records."""
    return tuple(Actor.from_dict(item) for item in read_json(path, dataset))


def write_manifest(manifest: BuildManifest, path: Path) -> Path:
    """Write the build provenance file."""
    return write_json(path, manifest.to_dict())


def read_manifest(path: Path, dataset: str | None = None) -> BuildManifest:
    """Read the build provenance file."""
    return BuildManifest.from_dict(read_json(path, dataset))


# --------------------------------------------------------------------------- #
# Matrices (NPZ: arrays plus their string labels, one self-contained file)
# --------------------------------------------------------------------------- #
def write_vector_space(space: VectorSpace, path: Path) -> Path:
    """Persist a :class:`~ttp_similarity.schema.VectorSpace` to ``.npz``."""
    ensure_parent(path)
    np.savez_compressed(
        path,
        matrix=space.matrix,
        actor_ids=np.array(space.actor_ids, dtype=object),
        technique_ids=np.array(space.technique_ids, dtype=object),
    )
    return path


def read_vector_space(path: Path, dataset: str | None = None) -> VectorSpace:
    """Load a :class:`~ttp_similarity.schema.VectorSpace` from ``.npz``."""
    with np.load(require(path, dataset), allow_pickle=True) as bundle:
        return VectorSpace(
            actor_ids=tuple(str(x) for x in bundle["actor_ids"]),
            technique_ids=tuple(str(x) for x in bundle["technique_ids"]),
            matrix=np.asarray(bundle["matrix"], dtype=float),
        )


def write_similarity(similarity: SimilarityMatrix, path: Path) -> Path:
    """Persist a :class:`~ttp_similarity.schema.SimilarityMatrix` to ``.npz``."""
    ensure_parent(path)
    np.savez_compressed(
        path,
        matrix=similarity.matrix,
        actor_ids=np.array(similarity.actor_ids, dtype=object),
        metric=np.array(similarity.metric),
    )
    return path


def read_similarity(path: Path, dataset: str | None = None) -> SimilarityMatrix:
    """Load a :class:`~ttp_similarity.schema.SimilarityMatrix` from ``.npz``."""
    with np.load(require(path, dataset), allow_pickle=True) as bundle:
        return SimilarityMatrix(
            actor_ids=tuple(str(x) for x in bundle["actor_ids"]),
            matrix=np.asarray(bundle["matrix"], dtype=float),
            metric=str(bundle["metric"]),
        )


def similarity_to_frame(similarity: SimilarityMatrix) -> pd.DataFrame:
    """Square, labelled DataFrame view -- convenient for seaborn heatmaps."""
    return pd.DataFrame(
        similarity.matrix,
        index=list(similarity.actor_ids),
        columns=list(similarity.actor_ids),
    )


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #
def dataset_exists(workspace: paths.Workspace) -> bool:
    """True when the data module has produced this workspace."""
    return workspace.actors.exists() and workspace.technique_frequency.exists()


def engine_exists(workspace: paths.Workspace) -> bool:
    """True when the engine module has produced this workspace."""
    return workspace.vector_space.exists() and workspace.weights.exists()


def read_clusters(path: Path, dataset: str | None = None) -> dict[ActorId, int]:
    """Load ``clusters.csv`` into ``{actor_id: cluster_id}``."""
    frame = read_dataframe(path, dataset)
    return {str(r.actor_id): int(r.cluster_id) for r in frame.itertuples()}


def read_technique_names(path: Path, dataset: str | None = None) -> dict[TechniqueId, str]:
    """Load ``techniques.csv`` into ``{technique_id: technique_name}``."""
    frame = read_dataframe(path, dataset)
    return {str(r.technique_id): str(r.technique_name) for r in frame.itertuples()}
