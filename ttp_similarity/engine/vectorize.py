"""Turn actors and free-form TTP lists into vectors in one shared space.

Both an actor and a user query become a row over the same technique vocabulary,
weighted by :mod:`ttp_similarity.engine.weighting`. That is what makes
"which actor is this TTP set like?" the same operation as "which actors are
alike?" -- a dot product in one space.

Vocabulary ordering is fixed (sorted technique ids) and stored alongside the
matrix, so a query built later still lines up with a matrix built earlier.

Owner: engine module.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from .. import config
from ..schema import Actor, TechniqueId, VectorSpace


def build_vocabulary(actors: Sequence[Actor]) -> tuple[TechniqueId, ...]:
    """Sorted, de-duplicated technique vocabulary for a dataset.

    Args:
        actors: Canonical actor records.

    Returns:
        Sorted unique technique ids -- the column order of every matrix and
        query vector in this dataset.
    """
    return tuple(sorted({tid for actor in actors for tid in actor.technique_ids}))


def build_vector_space(
    actors: Sequence[Actor],
    weights: Mapping[TechniqueId, float],
    *,
    normalize: bool = config.NORMALIZE_VECTORS,
) -> VectorSpace:
    """Build the weighted actor x technique matrix.

    ``matrix[i, j] = weights[technique_j]`` when actor ``i`` uses technique ``j``,
    else 0. With ``normalize=True`` each row is L2-normalised, so a dot product
    between two rows is their cosine similarity and a heavily documented actor
    does not outrank everyone by sheer vector length.

    Args:
        actors: Canonical actor records (row order is preserved).
        weights: ``technique_id -> weight`` from the weighting stage.
        normalize: Whether to L2-normalise rows.

    Returns:
        A :class:`~ttp_similarity.schema.VectorSpace`.

    Raises:
        ValueError: If ``actors`` is empty, or a technique has no weight.
    """
    if not actors:
        raise ValueError("actors must not be empty")

    vocab = build_vocabulary(actors)
    tech_idx = {tid: j for j, tid in enumerate(vocab)}
    n_actors = len(actors)
    n_techniques = len(vocab)

    matrix = np.zeros((n_actors, n_techniques), dtype=np.float64)
    for i, actor in enumerate(actors):
        for tid in actor.technique_ids:
            j = tech_idx.get(tid)
            if j is not None:
                w = weights.get(tid)
                if w is None:
                    raise ValueError(f"technique {tid} has no weight")
                matrix[i, j] = w

    if normalize:
        # Guard against all-zero rows: normalization would produce NaN.
        row_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        row_norms[row_norms == 0] = 1.0  # leave zero rows as zero
        matrix = matrix / row_norms

    actor_ids = tuple(a.actor_id for a in actors)
    return VectorSpace(actor_ids=actor_ids, technique_ids=vocab, matrix=matrix)


def vectorize_query(
    technique_ids: Sequence[TechniqueId],
    space: VectorSpace,
    weights: Mapping[TechniqueId, float],
    *,
    normalize: bool = config.NORMALIZE_VECTORS,
) -> tuple[np.ndarray, tuple[TechniqueId, ...], tuple[TechniqueId, ...]]:
    """Project a user-supplied technique list into the actor vector space.

    Ids outside the dataset vocabulary cannot be scored, but they are returned
    rather than dropped so the UI can tell the analyst "3 of your 12 techniques
    are unknown to this dataset" instead of quietly answering a different
    question.

    Args:
        technique_ids: Already normalised (rolled-up, upper-cased) ids.
        space: The dataset vector space, for its vocabulary ordering.
        weights: ``technique_id -> weight``.
        normalize: Whether to L2-normalise the query vector.

    Returns:
        ``(vector, known_ids, unknown_ids)`` where ``vector`` has shape
        ``(n_techniques,)``.
    """
    tech_idx = space.technique_index()
    known: list[TechniqueId] = []
    unknown: list[TechniqueId] = []
    for tid in technique_ids:
        if tid in tech_idx:
            known.append(tid)
        else:
            unknown.append(tid)

    vector = np.zeros(space.n_techniques, dtype=np.float64)
    for tid in known:
        j = tech_idx[tid]
        vector[j] = weights.get(tid, 0.0)

    if normalize:
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

    return vector, tuple(known), tuple(unknown)


def to_binary(space: VectorSpace) -> np.ndarray:
    """Presence/absence view of the matrix, for Jaccard and for set overlap.

    Args:
        space: Weighted vector space.

    Returns:
        A ``(n_actors, n_techniques)`` array of 0.0/1.0.
    """
    return (space.matrix > 0).astype(float)
