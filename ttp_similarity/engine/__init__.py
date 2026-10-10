"""Stage 2 -- weighting, vectorisation, similarity, clustering and query.

Pipeline::

    data/processed/<ds>/actors.json + technique_frequency.csv
        -> weighting.compute_weights()        weights.csv
        -> vectorize.build_vector_space()     vector_space.npz
        -> similarity.compute_similarity()    similarity.npz
        -> clustering.cluster_actors()        clusters.csv

        -> layout.compute_layout()            layout.csv

Query path (reads the artefacts above, writes nothing)::

    loading.load_engine(ws) -> EngineArtifacts
        -> query.query_techniques([...]) -> QueryResult

The central idea is that rare techniques carry signal and common ones do not.
An actor is a weighted vector over the technique vocabulary; two actors are
similar when they share *rare* techniques, not when both use PowerShell.

Owner: engine module. Inputs come from the data module, outputs feed the
evaluation module and the app.
"""

from __future__ import annotations

__all__ = [
    "build",
    "clustering",
    "layout",
    "confidence",
    "loading",
    "query",
    "similarity",
    "vectorize",
    "weighting",
    "rank_actors",
]

from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from ..schema import EngineArtifacts


def rank_actors(
    observed_techniques: str | Sequence[str],
    top_k: int = 5,
    *,
    dataset: str | None = None,
    artifacts: "EngineArtifacts | None" = None,
) -> list[dict[str, Any]]:
    """Rank the known actors most similar to a set of observed techniques.

    Args:
        observed_techniques: ATT&CK technique ids, as a list or a pasted blob.
        top_k: Number of candidates to return.
        dataset: Workspace to query; defaults to the real ATT&CK build.
        artifacts: Pre-loaded engine artefacts, to skip loading from disk.

    Returns:
        One dict per candidate. ``confidence_score`` / ``confidence_level``
        describe the query as a whole (how far the top candidate stands out),
        so every row carries the same value.
    """
    from .. import paths
    from .query import query_techniques

    result = query_techniques(
        observed_techniques,
        artifacts,
        dataset=dataset or paths.DEFAULT_DATASET,
        top_k=top_k,
    )
    scored = len(result.query_technique_ids) - len(result.unknown_technique_ids)
    return [
        {
            "actor_id": candidate.actor_id,
            "actor_name": candidate.actor_name,
            "similarity_score": candidate.score,
            "confidence_score": result.confidence.score,
            "confidence_level": result.confidence.level.value,
            "matched_techniques": list(candidate.matched_technique_ids),
            "match_count": len(candidate.matched_technique_ids),
            "technique_coverage": (
                len(candidate.matched_technique_ids) / scored if scored else 0.0
            ),
            "evidence": [
                {
                    "technique_id": ev.technique_id,
                    "technique_name": ev.technique_name,
                    "contribution": ev.contribution,
                }
                for ev in candidate.evidence
            ],
        }
        for candidate in result.candidates
    ]
