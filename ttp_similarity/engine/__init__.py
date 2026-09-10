"""Stage 2 -- weighting, vectorisation, similarity, clustering and query.

Pipeline::

    data/processed/<ds>/actors.json + technique_frequency.csv
        -> weighting.compute_weights()        weights.csv
        -> vectorize.build_vector_space()     vector_space.npz
        -> similarity.compute_similarity()    similarity.npz
        -> clustering.cluster_actors()        clusters.csv

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
    "confidence",
    "loading",
    "query",
    "similarity",
    "vectorize",
    "weighting",
    "rank_actors",
]

from typing import Any, Sequence

def rank_actors(observed_techniques: str | Sequence[str], top_k: int = 5) -> list[dict[str, Any]]:
    """Compare a list of observed techniques against known actors and rank the most similar ones.
    
    Args:
        observed_techniques: List of ATT&CK technique IDs (e.g. ['T1059', 'T1566']).
        top_k: Number of most similar candidates to return.
        
    Returns:
        List of candidate dictionaries containing actor info, scores, confidence and evidence.
    """
    from .query import query_techniques
    
    result = query_techniques(observed_techniques, top_k=top_k)
    
    out = []
    for candidate in result.candidates:
        out.append({
            "actor_id": candidate.actor_id,
            "actor_name": candidate.actor_name,
            "similarity_score": candidate.score,
            "confidence_score": result.confidence.score,
            "confidence_level": result.confidence.level.value,
            "matched_techniques": candidate.matched_technique_ids,
            "match_count": len(candidate.matched_technique_ids),
            "technique_coverage": len(candidate.matched_technique_ids) / len(result.query_technique_ids) if result.query_technique_ids else 0.0,
            "evidence": [
                {
                    "technique_id": ev.technique_id,
                    "technique_name": ev.technique_name,
                    "contribution": ev.contribution
                } for ev in candidate.evidence
            ]
        })
    return out
