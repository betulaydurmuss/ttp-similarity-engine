"""Stage-2 orchestrator: weights -> vectors -> similarity -> clusters.

Reads only stage-1 artefacts, writes only stage-2 artefacts. Nothing is passed
in memory between this and the data module, so the engine can be re-run against
a new dataset build without touching ingestion.

Run::

    python -m ttp_similarity.engine.build --dataset mock
    python -m ttp_similarity.engine.build --dataset mitre --scheme binary

Owner: engine module.
"""

from __future__ import annotations

import argparse

from .. import config, paths, storage
from ..schema import WEIGHT_COLUMNS
from . import clustering, similarity as similarity_mod, vectorize, weighting


def build_engine(
    dataset: str = paths.DEFAULT_DATASET,
    *,
    scheme: str = config.WEIGHTING_SCHEME,
    metric: str = config.SIMILARITY_METRIC,
    skip_clustering: bool = False,
) -> paths.Workspace:
    """Build every stage-2 artefact for one dataset.

    Steps:
        1. Read ``actors.json`` and ``technique_frequency.csv``.
        2. :func:`~ttp_similarity.engine.weighting.compute_weights` -> ``weights.csv``
        3. :func:`~ttp_similarity.engine.vectorize.build_vector_space` -> ``vector_space.npz``
        4. :func:`~ttp_similarity.engine.similarity.compute_similarity` -> ``similarity.npz``
        5. :func:`~ttp_similarity.engine.clustering.cluster_actors` -> ``clusters.csv``

    Args:
        dataset: Workspace name.
        scheme: Weighting scheme override (useful for ablation runs).
        metric: Similarity metric override.
        skip_clustering: Stop after the similarity matrix.

    Returns:
        The workspace that was written.

    Raises:
        ttp_similarity.storage.ArtifactMissingError: If stage 1 has not run.
    """
    workspace = paths.Workspace.get(dataset).ensure()

    # Stage-1 inputs. `require` inside storage raises with the exact command to
    # run when the data module has not produced this dataset yet.
    actors = storage.read_actors(workspace.actors, dataset)
    frequency = storage.read_dataframe(workspace.technique_frequency, dataset)

    # TODO(engine): weights_frame = weighting.compute_weights(frequency, len(actors), scheme)
    # TODO(engine): storage.write_dataframe(weights_frame, workspace.weights, WEIGHT_COLUMNS)
    # TODO(engine): space = vectorize.build_vector_space(actors, weighting.weights_to_mapping(weights_frame))
    # TODO(engine): storage.write_vector_space(space, workspace.vector_space)
    # TODO(engine): sim = similarity_mod.compute_similarity(space, metric)
    # TODO(engine): storage.write_similarity(sim, workspace.similarity)
    # TODO(engine): if not skip_clustering:
    #                   assignments = clustering.cluster_actors(sim)
    #                   frame = clustering.clusters_to_frame(assignments, {a.actor_id: a.name for a in actors})
    #                   storage.write_dataframe(frame, workspace.clusters, CLUSTER_COLUMNS)
    # TODO(engine): print similarity_mod.similarity_stats(sim) -- a mean cosine
    #   above ~0.8 means the weighting is not separating actors, and is the
    #   first thing to check on a fresh build.
    raise NotImplementedError("build_engine")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m ttp_similarity.engine.build``."""
    parser = argparse.ArgumentParser(description="Build weights, vectors, similarity, clusters.")
    parser.add_argument("--dataset", default=paths.DEFAULT_DATASET)
    parser.add_argument(
        "--scheme",
        default=config.WEIGHTING_SCHEME,
        choices=["smooth_idf", "plain_idf", "binary"],
    )
    parser.add_argument(
        "--metric", default=config.SIMILARITY_METRIC, choices=["cosine", "jaccard"]
    )
    parser.add_argument("--skip-clustering", action="store_true")
    args = parser.parse_args(argv)

    config.validate()
    workspace = build_engine(
        args.dataset,
        scheme=args.scheme,
        metric=args.metric,
        skip_clustering=args.skip_clustering,
    )
    print(f"engine artefacts written to {workspace.root}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
