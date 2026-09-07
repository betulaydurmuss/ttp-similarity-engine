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
    # TODO(engine): re.split(r"[\s,;]+", ...) when given a string; then
    #   normalize.normalize_technique_ids(). Keep entries that do not look like
    #   technique ids so they can be reported as unknown.
    raise NotImplementedError("normalize_query_input")


def score_actors(query_vector: np.ndarray, space: VectorSpace) -> np.ndarray:
    """Score every actor against the query vector.

    With L2-normalised rows and query, the dot product *is* cosine similarity.

    Args:
        query_vector: Shape ``(n_techniques,)``.
        space: The dataset vector space.

    Returns:
        Shape ``(n_actors,)`` array of scores in ``[0, 1]``.
    """
    # TODO(engine): space.matrix @ query_vector, clipped to [0, 1].
    raise NotImplementedError("score_actors")


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
    # TODO(engine): intersect the query with the actor's non-zero columns;
    #   contribution(t) = weight(t) / sum(weight(matched)).
    # TODO(engine): missing_ids is what makes the result auditable -- "this
    #   actor matches 6 of your 9 techniques" is the sentence the UI needs.
    raise NotImplementedError("explain_candidate")


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
    # TODO(engine): vectorize_query -> score_actors -> np.argsort descending ->
    #   build Candidate objects via explain_candidate().
    # TODO(engine): ties -- break deterministically on actor_id so the
    #   evaluation benchmark is reproducible.
    raise NotImplementedError("rank_candidates")


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
    # TODO(engine): normalize_query_input -> vectorize_query (known/unknown
    #   split) -> rank_candidates -> confidence.score_confidence -> assemble.
    # TODO(engine): an empty known set must return an empty candidate tuple with
    #   LOW confidence, not raise -- the UI shows "sorgu bos" rather than a
    #   traceback.
    raise NotImplementedError("query_techniques")


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
