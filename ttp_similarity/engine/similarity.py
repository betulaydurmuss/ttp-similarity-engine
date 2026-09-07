"""Actor-vs-actor similarity.

Cosine over the weighted vectors is the default: it ignores how many techniques
an actor has documented and asks only whether the *shape* of their behaviour
matches. Jaccard over the binary matrix is kept as an unweighted control -- if
the two rankings agree everywhere, the weighting is not earning its place.

Owner: engine module. Output feeds the app's heatmap and the clustering step.
"""

from __future__ import annotations

import numpy as np

from .. import config
from ..schema import ActorId, SimilarityMatrix, VectorSpace


def cosine_similarity_matrix(space: VectorSpace) -> np.ndarray:
    """Pairwise cosine similarity between all actors.

    Args:
        space: Weighted vector space.

    Returns:
        Symmetric ``(n_actors, n_actors)`` array in ``[0, 1]`` with 1.0 on the
        diagonal.
    """
    # TODO(engine): sklearn.metrics.pairwise.cosine_similarity(space.matrix);
    #   clip to [0, 1] (float error can produce 1.0000000002) and force the
    #   diagonal to exactly 1.0 so the heatmap does not show artefacts.
    raise NotImplementedError("cosine_similarity_matrix")


def jaccard_similarity_matrix(space: VectorSpace) -> np.ndarray:
    """Pairwise Jaccard similarity over technique *sets*, ignoring weights.

    Args:
        space: Vector space; only the sparsity pattern is used.

    Returns:
        Symmetric ``(n_actors, n_actors)`` array in ``[0, 1]``.
    """
    # TODO(engine): binary = vectorize.to_binary(space);
    #   intersection = binary @ binary.T;
    #   union = counts[:, None] + counts[None, :] - intersection;
    #   divide with np.errstate to keep 0/0 at 0.
    raise NotImplementedError("jaccard_similarity_matrix")


def compute_similarity(
    space: VectorSpace, metric: str = config.SIMILARITY_METRIC
) -> SimilarityMatrix:
    """Compute the actor similarity matrix under the configured metric.

    Args:
        space: Weighted vector space.
        metric: ``"cosine"`` or ``"jaccard"``.

    Returns:
        A labelled :class:`~ttp_similarity.schema.SimilarityMatrix`.

    Raises:
        ValueError: On an unknown metric.
    """
    # TODO(engine): dispatch, wrap with space.actor_ids and the metric name.
    raise NotImplementedError("compute_similarity")


def nearest_actors(
    similarity: SimilarityMatrix, actor_id: ActorId, top_k: int = 5
) -> list[tuple[ActorId, float]]:
    """Most similar actors to one actor, excluding itself.

    Powers the "closest peers" panel in the UI and is a quick sanity check on a
    fresh build: an actor's nearest neighbours should be plausible.

    Args:
        similarity: Actor similarity matrix.
        actor_id: Actor to look up.
        top_k: How many neighbours to return.

    Returns:
        ``(actor_id, score)`` pairs, best first.

    Raises:
        KeyError: If ``actor_id`` is not in the matrix.
    """
    # TODO(engine): locate the row, mask the diagonal, np.argsort descending.
    raise NotImplementedError("nearest_actors")


def similarity_stats(similarity: SimilarityMatrix) -> dict[str, float]:
    """Distribution summary over the off-diagonal entries.

    Useful in build logs: if the mean pairwise similarity is very high, the
    weighting is not separating actors and the thresholds need revisiting.

    Args:
        similarity: Actor similarity matrix.

    Returns:
        ``{"mean": ..., "median": ..., "p90": ..., "max": ...}``.
    """
    # TODO(engine): take the upper triangle with np.triu_indices(n, k=1).
    raise NotImplementedError("similarity_stats")
