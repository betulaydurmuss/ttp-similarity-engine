"""Retrieval metrics over a list of executed trials.

Implemented: these are standard definitions with no project-specific choices in
them, and the benchmark is easier to trust when they are unit-tested separately
from the loop that produces the trials.

Rank convention: 1-based, and ``-1`` means "the true actor was not in the
returned candidate list at all".

Owner: evaluation module.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from ..schema import EvaluationTrial


def top_k_accuracy(trials: Sequence[EvaluationTrial], k: int = 1) -> float:
    """Share of trials where the true actor ranked within the top ``k``.

    Args:
        trials: Executed trials.
        k: Cut-off rank.

    Returns:
        Value in ``[0, 1]``; ``0.0`` for an empty input.
    """
    if not trials:
        return 0.0
    hits = sum(1 for trial in trials if 1 <= trial.rank <= k)
    return hits / len(trials)


def mean_reciprocal_rank(trials: Sequence[EvaluationTrial]) -> float:
    """Mean of ``1 / rank``, counting misses (``rank == -1``) as 0.

    More informative than top-1 alone: it distinguishes "second every time" from
    "nowhere in the list".

    Args:
        trials: Executed trials.

    Returns:
        Value in ``[0, 1]``; ``0.0`` for an empty input.
    """
    if not trials:
        return 0.0
    return sum(1.0 / trial.rank if trial.rank >= 1 else 0.0 for trial in trials) / len(trials)


def mean_rank_of_correct_answer(trials: Sequence[EvaluationTrial]) -> tuple[float, int]:
    """Average 1-based rank of the true actor, over the trials that found it.

    Misses (``rank == -1``) are excluded and returned separately rather than
    folded in with a sentinel: averaging "-1" or "top_k + 1" would invent a
    number that depends on ``top_k`` rather than on the engine.

    Args:
        trials: Executed trials.

    Returns:
        ``(mean_rank, miss_count)``; ``mean_rank`` is ``0.0`` when nothing hit.
    """
    hits = [t.rank for t in trials if t.rank >= 1]
    misses = len(trials) - len(hits)
    return (sum(hits) / len(hits) if hits else 0.0, misses)


#: Technique-count buckets for the size-vs-accuracy split. Chosen around the
#: real distribution (min 5, median 21, max 87).
TECHNIQUE_COUNT_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("05-10", 5, 10),
    ("11-20", 11, 20),
    ("21-35", 21, 35),
    ("36-50", 36, 50),
    ("51+", 51, 10_000),
)


def breakdown_by_technique_count(
    trials: Sequence[EvaluationTrial],
) -> dict[str, dict[str, float]]:
    """Accuracy split by how well documented the target actor is.

    The counterpart, on the accuracy side, of the score-level size bias: if
    well-documented actors are also easier to retrieve, the headline number is
    partly measuring reporting depth rather than behavioural distinctiveness.

    Args:
        trials: Executed trials.

    Returns:
        ``{bucket: {"top1": ..., "top3": ..., "mrr": ..., "n": ..., "actors": ...}}``.
    """
    grouped: dict[str, list[EvaluationTrial]] = {name: [] for name, _, _ in TECHNIQUE_COUNT_BUCKETS}
    for trial in trials:
        for name, low, high in TECHNIQUE_COUNT_BUCKETS:
            if low <= trial.technique_count <= high:
                grouped[name].append(trial)
                break
    return {
        name: {
            "top1": top_k_accuracy(group, 1),
            "top3": top_k_accuracy(group, 3),
            "mrr": mean_reciprocal_rank(group),
            "n": float(len(group)),
            "actors": float(len({t.true_actor_id for t in group})),
        }
        for name, group in grouped.items()
        if group
    }


def breakdown_by_sample_size(
    trials: Sequence[EvaluationTrial],
) -> dict[int, dict[str, float]]:
    """Accuracy per query size -- the "how many TTPs do I need?" curve.

    Args:
        trials: Executed trials.

    Returns:
        ``{sample_size: {"top1": ..., "top3": ..., "mrr": ..., "n": ...}}``.
    """
    grouped: dict[int, list[EvaluationTrial]] = defaultdict(list)
    for trial in trials:
        grouped[trial.sample_size].append(trial)
    return {
        size: {
            "top1": top_k_accuracy(group, 1),
            "top3": top_k_accuracy(group, 3),
            "mrr": mean_reciprocal_rank(group),
            "n": float(len(group)),
        }
        for size, group in sorted(grouped.items())
    }


def breakdown_by_confidence(
    trials: Sequence[EvaluationTrial],
) -> dict[str, dict[str, float]]:
    """Accuracy per reported confidence level -- the calibration check.

    This is the table that says whether the confidence score means anything:
    ``high`` must show a materially better top-1 rate than ``low``. If it does
    not, the component weights in
    :data:`ttp_similarity.config.CONFIDENCE_COMPONENT_WEIGHTS` are wrong.

    Args:
        trials: Executed trials.

    Returns:
        ``{level: {"top1": ..., "top3": ..., "share": ..., "n": ...}}`` where
        ``share`` is the fraction of all trials that got that level.
    """
    total = len(trials)
    grouped: dict[str, list[EvaluationTrial]] = defaultdict(list)
    for trial in trials:
        grouped[trial.confidence_level.value].append(trial)
    return {
        level: {
            "top1": top_k_accuracy(group, 1),
            "top3": top_k_accuracy(group, 3),
            "share": len(group) / total if total else 0.0,
            "n": float(len(group)),
        }
        for level, group in sorted(grouped.items())
    }


def hardest_actors(
    trials: Sequence[EvaluationTrial], limit: int = 10
) -> list[tuple[str, float, int]]:
    """Actors the engine most often fails to retrieve.

    Points at the actors whose behaviour is indistinguishable from a neighbour's
    -- usually the most interesting finding in the whole benchmark.

    Args:
        trials: Executed trials.
        limit: How many actors to return.

    Returns:
        ``(actor_id, top1_accuracy, trial_count)`` sorted worst first.
    """
    grouped: dict[str, list[EvaluationTrial]] = defaultdict(list)
    for trial in trials:
        grouped[trial.true_actor_id].append(trial)
    scored = [
        (actor_id, top_k_accuracy(group, 1), len(group))
        for actor_id, group in grouped.items()
    ]
    scored.sort(key=lambda row: (row[1], -row[2]))
    return scored[:limit]


# TODO(eval): add confusion_pairs(trials) -> which wrong actor is predicted for
#   which true actor. A recurring pair means those two are genuinely similar,
#   which is a finding about the data rather than a bug in the engine, and it
#   belongs in the final report.
