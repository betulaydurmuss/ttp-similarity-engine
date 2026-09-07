"""Load a built dataset + engine into one :class:`EngineArtifacts` object.

Implemented, because it is pure glue over :mod:`ttp_similarity.storage` and it
is what unblocks the app: the UI should never open individual files or know
which stage produced them.

Owner: engine module. Called by: app, evaluation, engine CLI.
"""

from __future__ import annotations

from functools import lru_cache

from .. import paths, storage
from ..schema import EngineArtifacts


def load_engine(
    dataset: str = paths.DEFAULT_DATASET, *, with_similarity: bool = True
) -> EngineArtifacts:
    """Read every artefact the query path and the UI need.

    Args:
        dataset: Workspace name (``"mock"`` / ``"mitre"``).
        with_similarity: Also load ``similarity.npz`` and ``clusters.csv``.
            Set ``False`` in the benchmark, which only needs the vector space.

    Returns:
        A populated :class:`~ttp_similarity.schema.EngineArtifacts`.

    Raises:
        ttp_similarity.storage.ArtifactMissingError: If a required artefact has
            not been produced yet. The message names the command to run.
    """
    workspace = paths.Workspace.get(dataset)

    actors = storage.read_actors(workspace.actors, dataset)
    technique_names = storage.read_technique_names(workspace.techniques, dataset)
    weights_frame = storage.read_dataframe(workspace.weights, dataset)
    weights = {
        str(row.technique_id): float(row.weight) for row in weights_frame.itertuples()
    }
    space = storage.read_vector_space(workspace.vector_space, dataset)

    similarity = None
    clusters = None
    if with_similarity:
        # Similarity and clustering are optional: a query works without them,
        # only the heatmap and the cluster labels need them.
        if workspace.similarity.exists():
            similarity = storage.read_similarity(workspace.similarity, dataset)
        if workspace.clusters.exists():
            clusters = storage.read_clusters(workspace.clusters, dataset)

    return EngineArtifacts(
        dataset=dataset,
        actors=actors,
        technique_names=technique_names,
        weights=weights,
        space=space,
        similarity=similarity,
        clusters=clusters,
    )


@lru_cache(maxsize=4)
def load_engine_cached(
    dataset: str = paths.DEFAULT_DATASET, with_similarity: bool = True
) -> EngineArtifacts:
    """Memoised :func:`load_engine`, keyed by dataset.

    The benchmark issues thousands of queries and the Streamlit app reruns its
    script on every widget interaction; neither should re-read the matrices.
    Call :meth:`load_engine_cached.cache_clear` after a rebuild.
    """
    return load_engine(dataset, with_similarity=with_similarity)


def describe(artifacts: EngineArtifacts) -> str:
    """One-line summary of a loaded engine, for logs and the UI sidebar."""
    parts = [
        f"dataset={artifacts.dataset}",
        f"actors={artifacts.space.n_actors}",
        f"techniques={artifacts.space.n_techniques}",
    ]
    if artifacts.clusters:
        parts.append(f"clusters={len(set(artifacts.clusters.values()))}")
    return "  ".join(parts)
