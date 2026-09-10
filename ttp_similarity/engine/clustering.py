"""Group actors into behavioural clusters.

Clusters are a descriptive aid, not a claim: "these groups are documented as
behaving alike". Agglomerative clustering on the cosine *distance* matrix is
the default because it needs no assumption about cluster shape and can be cut
at a distance threshold rather than a guessed ``k``.

Owner: engine module. Output feeds the heatmap ordering and the cluster labels
shown next to query candidates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from ..schema import ActorId, SimilarityMatrix


def to_distance_matrix(similarity: SimilarityMatrix) -> np.ndarray:
    """Convert similarity to a distance matrix suitable for sklearn/scipy.

    Args:
        similarity: Actor similarity matrix in ``[0, 1]``.

    Returns:
        ``1 - similarity``, clipped to ``[0, 1]``, with an exact zero diagonal
        (scipy rejects a condensed matrix whose diagonal is not zero).
    """
    distance = np.clip(1.0 - similarity.matrix, 0.0, 1.0)
    np.fill_diagonal(distance, 0.0)
    distance = (distance + distance.T) / 2
    return distance


def cluster_actors(
    similarity: SimilarityMatrix,
    *,
    method: str = config.CLUSTERING_METHOD,
    n_clusters: int | None = config.CLUSTERING_N_CLUSTERS,
    distance_threshold: float = config.CLUSTERING_DISTANCE_THRESHOLD,
    linkage: str = config.CLUSTERING_LINKAGE,
) -> dict[ActorId, int]:
    """Assign each actor a cluster id.

    Args:
        similarity: Actor similarity matrix.
        method: ``"agglomerative"``, ``"kmeans"`` or ``"dbscan"``.
        n_clusters: Fixed cluster count; ``None`` uses ``distance_threshold``.
        distance_threshold: Cosine-distance cut for agglomerative clustering.
        linkage: Linkage criterion (``"average"`` by default -- ``"ward"`` is
            not valid on a precomputed distance matrix).

    Returns:
        ``{actor_id: cluster_id}``. Clusters smaller than
        :data:`ttp_similarity.config.MIN_CLUSTER_SIZE` are relabelled ``-1``.

    Raises:
        ValueError: On an unknown method, or if both ``n_clusters`` and
            ``distance_threshold`` are ``None``.
    """
    from sklearn.cluster import AgglomerativeClustering
    from collections import Counter
    distance = to_distance_matrix(similarity)
    if method == 'agglomerative':
        if n_clusters is not None:
            model = AgglomerativeClustering(n_clusters=n_clusters, metric='precomputed', linkage=linkage)
        else:
            model = AgglomerativeClustering(n_clusters=None, distance_threshold=distance_threshold, metric='precomputed', linkage=linkage)
        labels = model.fit_predict(distance)
    else:
        raise ValueError(f'Unknown clustering method: {method}')
    # Apply MIN_CLUSTER_SIZE relabelling
    counts = Counter(labels)
    small_clusters = {c for c, n in counts.items() if n < config.MIN_CLUSTER_SIZE}
    # Relabel small clusters to -1
    final_labels = [(-1 if l in small_clusters else l) for l in labels]
    # Renumber surviving clusters from 0
    unique_surviving = sorted(set(l for l in final_labels if l != -1))
    remap = {old: new for new, old in enumerate(unique_surviving)}
    remap[-1] = -1
    final_labels = [remap[l] for l in final_labels]
    return {similarity.actor_ids[i]: final_labels[i] for i in range(len(similarity.actor_ids))}


def clusters_to_frame(
    assignments: dict[ActorId, int], actor_names: dict[ActorId, str]
) -> pd.DataFrame:
    """Build the ``clusters.csv`` frame.

    Args:
        assignments: ``{actor_id: cluster_id}``.
        actor_names: ``{actor_id: display name}``.

    Returns:
        DataFrame with :data:`~ttp_similarity.schema.CLUSTER_COLUMNS`, sorted by
        cluster then actor name.
    """
    frame = pd.DataFrame(
        [
            {
                "actor_id": actor_id,
                "actor_name": actor_names.get(actor_id, actor_id),
                "cluster_id": int(cluster_id),
            }
            for actor_id, cluster_id in assignments.items()
        ]
    )
    return frame.sort_values(["cluster_id", "actor_name"]).reset_index(drop=True)


def order_for_heatmap(
    similarity: SimilarityMatrix, assignments: dict[ActorId, int] | None = None
) -> list[int]:
    """Row/column ordering that puts similar actors next to each other.

    A heatmap in arbitrary order shows nothing; ordered by the clustering
    dendrogram it shows blocks. Used by the app.

    Args:
        similarity: Actor similarity matrix.
        assignments: Optional cluster assignment; when given, actors are grouped
            by cluster and ordered within it.

    Returns:
        Row indices in display order.
    """
    from scipy.cluster.hierarchy import linkage as scipy_linkage, leaves_list
    from scipy.spatial.distance import squareform
    distance = to_distance_matrix(similarity)
    n = len(similarity.actor_ids)
    if n <= 1:
        return list(range(n))
    # Ensure perfect symmetry for squareform
    np.fill_diagonal(distance, 0.0)
    condensed = squareform(distance, checks=False)
    Z = scipy_linkage(condensed, method='average')
    return list(leaves_list(Z).astype(int))


def cluster_profile(
    assignments: dict[ActorId, int],
    actor_technique: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """Describe each cluster by the techniques that define it.

    Args:
        assignments: ``{actor_id: cluster_id}``.
        actor_technique: The ``actor_technique.csv`` edge table.
        top_n: Techniques listed per cluster.

    Returns:
        DataFrame with ``cluster_id``, ``technique_id``, ``technique_name``,
        ``share_in_cluster``, ``lift`` (in-cluster share / overall share).
        Sorting by ``lift`` is what makes a cluster describable in words.
    """
    # TODO(engine): join assignments onto the edge table, group by cluster.
    raise NotImplementedError("cluster_profile")
