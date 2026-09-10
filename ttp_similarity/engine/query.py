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
import re
from typing import Mapping, Sequence

import numpy as np

from .. import config, paths, storage
from ..data.normalize import normalize_technique_ids
from . import confidence as confidence_mod
from . import loading, vectorize
from ..schema import (
    Candidate,
    ConfidenceBreakdown,
    ConfidenceLevel,
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
    if isinstance(raw, str):
        tokens = re.split(r"[\s,;]+", raw.strip())
    else:
        tokens = list(raw)
    # Keep entries that don't look like technique ids so they can be reported
    # as unknown -- normalize_technique_ids upper-cases and de-duplicates.
    tokens = [t for t in tokens if t.strip()]
    return normalize_technique_ids(tokens)


def score_actors(
    query_vector: np.ndarray,
    space: VectorSpace,
    *,
    query_technique_ids: Sequence[TechniqueId] = (),
    metric: str | None = None,
    weights: Mapping[TechniqueId, float] | None = None,
) -> np.ndarray:
    """Score every actor against the query.

    ``cosine`` (default): with L2-normalised rows and query, the dot product
    *is* cosine similarity, so weights drive the ranking.

    ``jaccard``: set overlap between the query and the actor's technique set,
    ignoring weights entirely. This is the unweighted control the ablation
    needs -- it answers "what would this system score without any weighting?".

    ``weighted_jaccard`` (Ruzicka): the same set overlap, but every technique
    counts for its IDF weight instead of 1. Combines Jaccard's structural
    robustness to noise -- an injected technique enlarges the union for *every*
    candidate equally, so it cannot reorder them -- with IDF's discrimination.
    Since a technique carries the same global weight wherever it appears,
    ``min``/``max`` over the two weight vectors reduce to a weighted
    intersection over a weighted union.

    Args:
        query_vector: Shape ``(n_techniques,)``. Used by the cosine path.
        space: The dataset vector space.
        query_technique_ids: The known query ids. Required by the jaccard path,
            which works on sets rather than on the weighted vector.
        metric: ``"cosine"``, ``"jaccard"`` or ``"weighted_jaccard"``; ``None``
            reads config at call time.
        weights: ``technique_id -> weight``; required by ``weighted_jaccard``.

    Returns:
        Shape ``(n_actors,)`` array of scores in ``[0, 1]``.

    Raises:
        ValueError: On an unknown metric.
    """
    metric = config.SIMILARITY_METRIC if metric is None else metric
    if metric == "cosine":
        return np.clip(space.matrix @ query_vector, 0.0, 1.0)
    if metric in ("jaccard", "weighted_jaccard"):
        binary = (space.matrix > 0).astype(float)
        index = space.technique_index()
        indicator = np.zeros(space.n_techniques, dtype=float)
        for tid in query_technique_ids:
            position = index.get(tid)
            if position is not None:
                indicator[position] = 1.0

        if metric == "weighted_jaccard":
            if weights is None:
                raise ValueError("weighted_jaccard needs the technique weights")
            per_technique = np.array(
                [float(weights.get(tid, 0.0)) for tid in space.technique_ids]
            )
        else:
            per_technique = np.ones(space.n_techniques, dtype=float)

        intersection = binary @ (indicator * per_technique)
        actor_total = binary @ per_technique
        query_total = float(indicator @ per_technique)
        union = actor_total + query_total - intersection
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(union > 0, intersection / union, 0.0)
    raise ValueError(f"Unknown query metric: {metric}")


def coverage_of(
    query_technique_ids: Sequence[TechniqueId], space: VectorSpace
) -> np.ndarray:
    """Share of the query each actor actually covers, in ``[0, 1]``.

    ``matched / len(query)`` per actor. Used by the optional coverage
    correction; see :data:`ttp_similarity.config.COVERAGE_CORRECTION`.
    """
    if not query_technique_ids:
        return np.zeros(space.n_actors, dtype=float)
    binary = (space.matrix > 0).astype(float)
    index = space.technique_index()
    indicator = np.zeros(space.n_techniques, dtype=float)
    for tid in query_technique_ids:
        position = index.get(tid)
        if position is not None:
            indicator[position] = 1.0
    return (binary @ indicator) / len(query_technique_ids)


def explain_candidate(
    actor_index: int,
    query_technique_ids: Sequence[TechniqueId],
    artifacts: EngineArtifacts,
    max_evidence: int | None = None,
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
    max_evidence = config.MAX_EVIDENCE_TECHNIQUES if max_evidence is None else max_evidence
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
    top_k: int | None = None,
    min_score: float | None = None,
    *,
    metric: str | None = None,
    coverage_correction: bool | None = None,
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
    top_k = config.QUERY_TOP_K if top_k is None else top_k
    min_score = config.MIN_CANDIDATE_SCORE if min_score is None else min_score
    metric = config.SIMILARITY_METRIC if metric is None else metric
    if coverage_correction is None:
        coverage_correction = config.COVERAGE_CORRECTION

    query_vector, known_ids, unknown_ids = vectorize.vectorize_query(
        query_technique_ids, artifacts.space, artifacts.weights,
    )

    # All-zero vector means nothing matched
    if metric == "cosine" and np.all(query_vector == 0):
        return ()

    scores = score_actors(
        query_vector,
        artifacts.space,
        query_technique_ids=known_ids,
        metric=metric,
        weights=artifacts.weights,
    )
    if coverage_correction:
        # Penalise an actor that scores highly on a couple of heavy matches
        # while ignoring most of the query.
        exponent = config.COVERAGE_CORRECTION_EXPONENT
        scores = scores * (coverage_of(known_ids, artifacts.space) ** exponent)

    # Argsort descending; break ties deterministically on actor_id
    order = sorted(
        range(len(scores)),
        key=lambda i: (-scores[i], artifacts.space.actor_ids[i]),
    )

    names = {a.actor_id: a.name for a in artifacts.actors}
    candidates: list[Candidate] = []
    for actor_idx in order:
        score = float(scores[actor_idx])
        if score < min_score:
            break
        if len(candidates) >= top_k:
            break

        matched_ids, missing_ids, evidence = explain_candidate(
            actor_idx, list(known_ids), artifacts,
        )
        actor_id = artifacts.space.actor_ids[actor_idx]
        actor_name = names.get(actor_id, actor_id)

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
    top_k: int | None = None,
    metric: str | None = None,
    coverage_correction: bool | None = None,
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
    candidates = rank_candidates(
        known_ids,
        artifacts,
        top_k=top_k,
        metric=metric,
        coverage_correction=coverage_correction,
    )

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
    parser.add_argument(
        "--dataset",
        default=paths.DEFAULT_DATASET,
        choices=list(paths.KNOWN_DATASETS),
        help="which dataset to work on",
    )
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
