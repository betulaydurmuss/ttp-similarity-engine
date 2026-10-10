"""Project the actor similarity space onto a 2-D map.

The map is what the interface navigates: every actor sits where its
behaviour places it, so neighbours on screen are neighbours in the engine.
Metric MDS on the cosine distance keeps global distances honest -- unlike
t-SNE it does not invent tight islands -- and a fixed seed makes the map the
same on every build.

Owner: engine module. Output feeds the API's map endpoints.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.manifold import MDS

from .. import config
from ..schema import LAYOUT_COLUMNS, SimilarityMatrix
from .clustering import to_distance_matrix


def compute_layout(
    similarity: SimilarityMatrix, seed: int | None = None
) -> pd.DataFrame:
    """2-D coordinates per actor, centred and scaled into ``[-1, 1]``.

    Args:
        similarity: Actor similarity matrix.
        seed: Projection seed; ``None`` reads :data:`config.LAYOUT_RANDOM_SEED`.

    Returns:
        DataFrame with :data:`~ttp_similarity.schema.LAYOUT_COLUMNS`.
    """
    seed = config.LAYOUT_RANDOM_SEED if seed is None else seed
    n = len(similarity.actor_ids)
    if n == 0:
        return pd.DataFrame(columns=list(LAYOUT_COLUMNS))
    if n < 3:
        coords = np.zeros((n, 2))
        coords[:, 0] = np.linspace(-0.5, 0.5, n) if n > 1 else 0.0
    else:
        model = MDS(
            n_components=2,
            metric="precomputed",
            init="classical_mds",
            n_init=1,
            max_iter=600,
            random_state=seed,
        )
        coords = model.fit_transform(to_distance_matrix(similarity))
        coords = coords - coords.mean(axis=0)
        extent = np.abs(coords).max()
        if extent > 0:
            coords = coords / extent

    return pd.DataFrame(
        {
            "actor_id": list(similarity.actor_ids),
            "x": coords[:, 0].round(5),
            "y": coords[:, 1].round(5),
        },
        columns=list(LAYOUT_COLUMNS),
    )
