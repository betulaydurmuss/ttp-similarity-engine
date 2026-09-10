"""Technique weighting -- rare techniques weigh more than common ones.

Treat an actor as a document and its techniques as terms. ATT&CK reports
presence, not counts, so term frequency is binary and all the signal lives in
the inverse-document-frequency part:

``smooth_idf`` (default)
    ``w(t) = ln((N + s) / (df(t) + s)) + 1``

    with ``N`` = number of actors, ``df(t)`` = actors using ``t``, ``s`` =
    :data:`ttp_similarity.config.IDF_SMOOTHING`. The ``+ 1`` floor keeps a
    universal technique at weight 1 rather than 0, so a query made only of
    commodity techniques still returns *something* -- with low confidence,
    which is the honest answer.

``plain_idf``
    ``w(t) = ln(N / df(t))``. Universal techniques collapse to exactly 0.
    Sharper, but query results can go completely empty.

``binary``
    ``w(t) = 1``. Ablation baseline: run the evaluation with this to show what
    the weighting actually buys.

Weights are global properties of the dataset, computed once at build time and
reused for both actor-vs-actor similarity and query scoring -- a query must be
scored in the same space the actors live in.

Owner: engine module.
"""

from __future__ import annotations

from typing import Mapping

import pandas as pd

from .. import config
from ..schema import TechniqueId


def idf(document_frequency: int, n_documents: int, smoothing: float = config.IDF_SMOOTHING) -> float:
    """Smoothed inverse document frequency for a single technique.

    Args:
        document_frequency: Number of actors using the technique (``>= 0``).
        n_documents: Total number of actors (``> 0``).
        smoothing: Additive smoothing applied to both terms.

    Returns:
        ``ln((N + s) / (df + s)) + 1``, always ``>= 1``.

    Raises:
        ValueError: If ``n_documents <= 0`` or ``document_frequency < 0``.
    """
    if n_documents <= 0:
        raise ValueError(f"n_documents must be > 0, got {n_documents}")
    if document_frequency < 0:
        raise ValueError(f"document_frequency must be >= 0, got {document_frequency}")
    
    import math
    return math.log((n_documents + smoothing) / (document_frequency + smoothing)) + 1


def compute_weights(
    frequency: pd.DataFrame,
    n_actors: int,
    scheme: str = config.WEIGHTING_SCHEME,
) -> pd.DataFrame:
    """Turn the frequency table into per-technique weights.

    Args:
        frequency: ``technique_frequency.csv`` as produced by the data module
            (:data:`~ttp_similarity.schema.TECHNIQUE_FREQUENCY_COLUMNS`).
        n_actors: Total actor count for the dataset.
        scheme: One of ``"smooth_idf"``, ``"plain_idf"``, ``"binary"``.

    Returns:
        DataFrame with :data:`~ttp_similarity.schema.WEIGHT_COLUMNS`, sorted by
        weight descending (rarest first) so the head of the file is readable.

    Raises:
        ValueError: On an unknown scheme or an empty frequency table.
    """
    import numpy as np

    if frequency.empty:
        raise ValueError("empty frequency table")
        
    actor_counts = frequency["actor_count"].values
    
    if scheme == "smooth_idf":
        smoothing = config.IDF_SMOOTHING
        w = np.log((n_actors + smoothing) / (actor_counts + smoothing)) + 1
    elif scheme == "plain_idf":
        w = np.where(actor_counts > 0, np.log(n_actors / actor_counts), 0.0)
    elif scheme == "binary":
        w = np.ones(len(actor_counts), dtype=float)
    else:
        raise ValueError(f"unknown scheme: {scheme}")

    df = pd.DataFrame({
        "technique_id": frequency["technique_id"],
        "technique_name": frequency["technique_name"],
        "actor_count": frequency["actor_count"],
        "weight": w
    })
    return df.sort_values("weight", ascending=False).reset_index(drop=True)


def weights_to_mapping(weights: pd.DataFrame) -> dict[TechniqueId, float]:
    """``weights.csv`` frame -> ``{technique_id: weight}``."""
    return {str(row.technique_id): float(row.weight) for row in weights.itertuples()}


def normalized_rarity(
    technique_ids: tuple[TechniqueId, ...], weights: Mapping[TechniqueId, float]
) -> float:
    """Mean rarity of a technique set, rescaled to ``[0, 1]``.

    Feeds the ``rarity`` component of the confidence score. The raw weights are
    unbounded above, so they are divided by the dataset's maximum weight; a set
    made only of the rarest techniques scores 1.0, one made only of universal
    techniques scores near 0.

    Args:
        technique_ids: Techniques to score (typically the matched ones).
        weights: Global technique weights.

    Returns:
        Value in ``[0, 1]``; ``0.0`` for an empty input.
    """
    if not technique_ids or not weights:
        return 0.0
    
    max_weight = max(weights.values())
    if max_weight <= 0:
        return 0.0
        
    min_weight = min(weights.values())
    collected_weights = [weights.get(tid, min_weight) for tid in technique_ids]
    
    return (sum(collected_weights) / len(collected_weights)) / max_weight
