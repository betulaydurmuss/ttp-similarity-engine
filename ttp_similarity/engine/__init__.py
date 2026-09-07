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
]
