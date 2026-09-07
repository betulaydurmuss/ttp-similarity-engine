"""Query mode -- "these are the TTPs I saw; which actors behave like this?".

The public entry point is :func:`query_techniques`. It is the single function
the app and the evaluation module both call, so its behaviour is the product:

1. Normalise the input (roll up sub-techniques, upper-case, de-duplicate).
2. Split into known / unknown against the dataset vocabulary; unknown ids are
   reported back, never silently dropped.
3. Project the known ids into the actor vector space and score every actor.
4. Rank, cut at ``top_k`` and at
   :data:`ttp_similarity.config.MIN_CANDIDATE_SCORE`.
5. For each candidate, work out which techniques matched and how much each one
   contributed to that candidate's score.
6. Score confidence for the top candidate and attach the disclaimer.

The result is deliberately explainable: a rank without the techniques that
produced it is not usable intelligence.

Owner: engine module. Called by: app (query screen), evaluation (benchmark).
"""

from __future__ import annotations

import argparse
import json
from typing import Sequence

import numpy as np

from .. import config, paths, storage
from ..schema import (
    Candidate,
    EngineArtifacts,
    QueryResult,
    TechniqueContribution,
    TechniqueId,
    VectorSpace,
)


def normalize_query_input(raw: str | Sequence[str]) -> tuple[TechniqueId, ...]:
    """Parse whatever the user pasted into clean technique ids.

    Accepts a list of strings or a single blob separated by commas, semicolons,
    whitespace or newlines -- analysts paste from spreadsheets and reports, and
    the UI should not make them reformat.

    Args:
        raw: Free-form input.

    Returns:
        Sorted unique parent-level technique ids (sub-techniques rolled up).
    """
    import re
    from ..data.normalize import normalize_technique_ids

    if isinstance(raw, str):
        tokens = re.split(r"[\s,;]+", raw.strip())
    else:
        tokens = list(raw)
    # Keep entries that don't look like technique ids so they can be reported
    # as unknown -- normalize_technique_ids upper-cases and de-duplicates.
    tokens = [t for t in tokens if t.strip()]
    return normalize_technique_ids(tokens)


def score_actors(query_vector: np.ndarray, space: VectorSpace) -> np.ndarray:
    """Score every actor against the query vector.

    With L2-normalised rows and query, the dot product *is* cosine similarity.

    Args:
        query_vector: Shape ``(n_techniques,)``.
        space: The dataset vector space.

    Returns:
        Shape ``(n_actors,)`` array of scores in ``[0, 1]``.
    """
    scores = space.matrix @ query_vector
    return np.clip(scores, 0.0, 1.0)


def explain_candidate(
    actor_index: int,
    query_technique_ids: Sequence[TechniqueId],
    artifacts: EngineArtifacts,
    max_evidence: int = config.MAX_EVIDENCE_TECHNIQUES,
) -> tuple[tuple[TechniqueId, ...], tuple[TechniqueId, ...], tuple[TechniqueContribution, ...]]:
    """Work out which techniques drove one candidate's score.

    Args:
        actor_index: Row index of the candidate in the vector space.
        query_technique_ids: Known query techniques.
        artifacts: Loaded engine artefacts.
        max_evidence: Cap on returned contributions.

    Returns:
        ``(matched_ids, missing_ids, evidence)`` where ``missing_ids`` are query
        techniques this actor is *not* documented as using, and ``evidence`` is
        the matched techniques ranked by their share of the score, capped at
        ``max_evidence``. Contributions across all matched techniques sum to 1.
    """
    space = artifacts.space
    tech_idx = space.technique_index()
    actor_row = space.matrix[actor_index]
    query_set = set(query_technique_ids)

    matched: list[TechniqueId] = []
    missing: list[TechniqueId] = []
    for tid in query_technique_ids:
        j = tech_idx.get(tid)
        if j is not None and actor_row[j] > 0:
            matched.append(tid)
        else:
            missing.append(tid)

    # Build evidence: how much each matched technique contributed
    evidence: list[TechniqueContribution] = []
    if matched:
        matched_weights = {tid: artifacts.weights.get(tid, 0.0) for tid in matched}
        total_weight = sum(matched_weights.values())
        if total_weight <= 0:
            total_weight = 1.0  # avoid division by zero

        for tid in matched:
            w = matched_weights[tid]
            evidence.append(TechniqueContribution(
                technique_id=tid,
                technique_name=artifacts.technique_names.get(tid, tid),
                weight=w,
                contribution=w / total_weight,
            ))
        # Sort by contribution descending, cap at max_evidence
        evidence.sort(key=lambda e: e.contribution, reverse=True)
        evidence = evidence[:max_evidence]

    return tuple(matched), tuple(missing), tuple(evidence)


def rank_candidates(
    query_technique_ids: Sequence[TechniqueId],
    artifacts: EngineArtifacts,
    top_k: int = config.QUERY_TOP_K,
    min_score: float = config.MIN_CANDIDATE_SCORE,
) -> tuple[Candidate, ...]:
    """Rank actors against a set of known technique ids.

    Args:
        query_technique_ids: Techniques present in the dataset vocabulary.
        artifacts: Loaded engine artefacts.
        top_k: Maximum candidates returned.
        min_score: Candidates below this score are dropped.

    Returns:
        Candidates ordered best first, each with its evidence filled in.
    """
    from . import vectorize

    query_vector, known_ids, unknown_ids = vectorize.vectorize_query(
        query_technique_ids, artifacts.space, artifacts.weights,
    )

    # All-zero vector means nothing matched
    if np.all(query_vector == 0):
        return ()

    scores = score_actors(query_vector, artifacts.space)

    # Argsort descending; break ties deterministically on actor_id
    order = sorted(
        range(len(scores)),
        key=lambda i: (-scores[i], artifacts.space.actor_ids[i]),
    )

    candidates: list[Candidate] = []
    for rank_0, actor_idx in enumerate(order):
        score = float(scores[actor_idx])
        if score < min_score:
            break
        if len(candidates) >= top_k:
            break

        matched_ids, missing_ids, evidence = explain_candidate(
            actor_idx, list(known_ids), artifacts,
        )
        actor_id = artifacts.space.actor_ids[actor_idx]
        # Look up actor name
        actor_name = actor_id
        for a in artifacts.actors:
            if a.actor_id == actor_id:
                actor_name = a.name
                break

        candidates.append(Candidate(
            rank=len(candidates) + 1,
            actor_id=actor_id,
            actor_name=actor_name,
            score=score,
            matched_technique_ids=matched_ids,
            missing_technique_ids=missing_ids,
            evidence=evidence,
        ))

    return tuple(candidates)


def query_techniques(
    technique_ids: str | Sequence[str],
    artifacts: EngineArtifacts | None = None,
    *,
    dataset: str = paths.DEFAULT_DATASET,
    top_k: int = config.QUERY_TOP_K,
) -> QueryResult:
    """Full query path: raw input in, ranked and explained candidates out.

    This is the function the app and the benchmark call.

    Args:
        technique_ids: Raw user input (string blob or list of ids).
        artifacts: Pre-loaded engine artefacts. When ``None`` they are loaded
            from ``dataset`` -- pass them explicitly in loops (the benchmark
            runs thousands of queries and should not reload per call).
        dataset: Workspace to query when ``artifacts`` is not given.
        top_k: Maximum candidates returned.

    Returns:
        A :class:`~ttp_similarity.schema.QueryResult` including the confidence
        breakdown and :data:`ttp_similarity.config.DISCLAIMER`.

    Raises:
        ttp_similarity.storage.ArtifactMissingError: If the engine has not been
            built for ``dataset``.
    """
    from . import confidence as confidence_mod, loading, vectorize

    # Normalise input
    technique_ids_clean = normalize_query_input(technique_ids)

    # Load engine artifacts if not provided
    if artifacts is None:
        artifacts = loading.load_engine(dataset, with_similarity=False)

    # Split into known / unknown
    tech_idx = artifacts.space.technique_index()
    known_ids = tuple(tid for tid in technique_ids_clean if tid in tech_idx)
    unknown_ids = tuple(tid for tid in technique_ids_clean if tid not in tech_idx)

    # An empty known set -> empty result with LOW confidence
    from ..schema import ConfidenceBreakdown
    if not known_ids:
        return QueryResult(
            query_technique_ids=technique_ids_clean,
            unknown_technique_ids=unknown_ids,
            candidates=(),
            confidence=ConfidenceBreakdown(
                rarity=0.0, margin=0.0, sufficiency=0.0,
                score=0.0, level=config.ConfidenceLevel.LOW if hasattr(config, 'ConfidenceLevel') else __import__('ttp_similarity.schema', fromlist=['ConfidenceLevel']).ConfidenceLevel.LOW,
            ),
            dataset=artifacts.dataset,
            disclaimer=config.DISCLAIMER,
        )

    # Rank candidates
    candidates = rank_candidates(known_ids, artifacts, top_k=top_k)

    # Compute confidence
    conf = confidence_mod.score_confidence(candidates, known_ids, artifacts.weights)

    return QueryResult(
        query_technique_ids=technique_ids_clean,
        unknown_technique_ids=unknown_ids,
        candidates=candidates,
        confidence=conf,
        dataset=artifacts.dataset,
        disclaimer=config.DISCLAIMER,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m ttp_similarity.engine.query T1566 T1059 ...``."""
    parser = argparse.ArgumentParser(description="Query a TTP set against a dataset.")
    parser.add_argument("techniques", nargs="+", help="technique ids, e.g. T1566 T1059")
    parser.add_argument("--dataset", default=paths.DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=config.QUERY_TOP_K)
    parser.add_argument("--json", action="store_true", help="print the raw result as JSON")
    args = parser.parse_args(argv)

    config.validate()
    result = query_techniques(args.techniques, dataset=args.dataset, top_k=args.top_k)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(f"dataset: {result.dataset}")
    print(f"confidence: {result.confidence.level.value} ({result.confidence.score:.2f})")
    if result.unknown_technique_ids:
        print(f"unknown ids: {', '.join(result.unknown_technique_ids)}")
    for candidate in result.candidates:
        matched = len(candidate.matched_technique_ids)
        print(f"  {candidate.rank:>2}. {candidate.actor_name:<24} "
              f"{candidate.score:.3f}  ({matched} matched)")
    print(f"\n{result.disclaimer}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
