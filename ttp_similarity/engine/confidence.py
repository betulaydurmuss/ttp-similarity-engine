"""Confidence scoring for a query result.

A similarity ranking on its own is misleading: the top candidate always exists,
even when the input was three universal techniques shared by every actor in the
dataset. Confidence exists to say how much the ranking is worth, and it is built
from three independent failure modes:

**1. Rarity** -- ``config.CONFIDENCE_COMPONENT_WEIGHTS["rarity"]``
    Are the matched techniques discriminative? Matching two techniques used by a
    single actor is strong evidence; matching ten techniques everyone uses is
    none. Computed as the mean weight of the *matched* techniques divided by the
    dataset's maximum weight (see
    :func:`ttp_similarity.engine.weighting.normalized_rarity`).

**2. Margin** -- ``config.CONFIDENCE_COMPONENT_WEIGHTS["margin"]``
    Is the top candidate actually ahead? ``(score_1 - score_2) / score_1``,
    divided by :data:`ttp_similarity.config.MARGIN_SATURATION` and clipped to 1.
    A near-tie means the data does not distinguish the two, and the result must
    be read as "one of these", not "this one". With a single candidate the
    component is 1.0 -- there is nothing to be confused with.

**3. Sufficiency** -- ``config.CONFIDENCE_COMPONENT_WEIGHTS["sufficiency"]``
    Was there enough input? Ramps linearly from 0 at
    :data:`ttp_similarity.config.MIN_QUERY_TECHNIQUES` to 1 at
    :data:`ttp_similarity.config.SUFFICIENCY_SATURATION` known techniques. Only
    ids present in the dataset vocabulary count.

``score = sum(component * weight)``, then thresholded into
high / medium / low. The three components are reported alongside the score so
the UI can say *why* confidence is low rather than just showing a number.

Owner: engine module.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import config
from . import weighting
from ..schema import Candidate, ConfidenceBreakdown, ConfidenceLevel, TechniqueId


def rarity_component(
    matched_technique_ids: Sequence[TechniqueId],
    weights: Mapping[TechniqueId, float],
) -> float:
    """How discriminative the matched techniques are, in ``[0, 1]``.

    Args:
        matched_technique_ids: Techniques the top candidate shares with the query.
        weights: Global technique weights from the weighting stage.

    Returns:
        Mean matched weight divided by the maximum weight in the dataset;
        ``0.0`` when nothing matched.
    """
    return weighting.normalized_rarity(tuple(matched_technique_ids), weights)


def margin_component(
    top_score: float,
    runner_up_score: float | None,
    saturation: float | None = None,
) -> float:
    """Separation between candidate #1 and #2, in ``[0, 1]``.

    Args:
        top_score: Score of the best candidate.
        runner_up_score: Score of the second candidate, or ``None`` when there
            is only one.
        saturation: Relative gap at which the component reaches 1.0.

    Returns:
        ``min(1, ((top - second) / top) / saturation)``; ``1.0`` when there is no
        runner-up, ``0.0`` when ``top_score <= 0``.
    """
    saturation = config.MARGIN_SATURATION if saturation is None else saturation
    if top_score <= 0:
        return 0.0
    if runner_up_score is None:
        return 1.0
    gap = (top_score - runner_up_score) / top_score
    return min(1.0, gap / saturation)


def sufficiency_component(
    known_technique_count: int,
    minimum: int | None = None,
    saturation: int | None = None,
) -> float:
    """Whether enough input was supplied to judge, in ``[0, 1]``.

    Args:
        known_technique_count: Query techniques present in the vocabulary.
            Unknown ids do not count towards sufficiency.
        minimum: Count below which the component is 0.
        saturation: Count at which the component reaches 1.

    Returns:
        ``clip((n - minimum) / (saturation - minimum), 0, 1)``.
    """
    minimum = config.MIN_QUERY_TECHNIQUES if minimum is None else minimum
    saturation = config.SUFFICIENCY_SATURATION if saturation is None else saturation
    if saturation <= minimum:
        return 1.0 if known_technique_count >= minimum else 0.0
    value = (known_technique_count - minimum) / (saturation - minimum)
    return max(0.0, min(1.0, value))


def level_for_score(
    score: float,
    high: float | None = None,
    medium: float | None = None,
) -> ConfidenceLevel:
    """Map a combined score onto a :class:`~ttp_similarity.schema.ConfidenceLevel`.

    Args:
        score: Combined confidence in ``[0, 1]``.
        high: Lower bound for ``HIGH``.
        medium: Lower bound for ``MEDIUM``.

    Returns:
        ``HIGH`` / ``MEDIUM`` / ``LOW``.
    """
    high = config.CONFIDENCE_HIGH_THRESHOLD if high is None else high
    medium = config.CONFIDENCE_MEDIUM_THRESHOLD if medium is None else medium
    if score >= high:
        return ConfidenceLevel.HIGH
    if score >= medium:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def score_confidence(
    candidates: Sequence[Candidate],
    known_technique_ids: Sequence[TechniqueId],
    weights: Mapping[TechniqueId, float],
    component_weights: Mapping[str, float] | None = None,
) -> ConfidenceBreakdown:
    """Compute the full confidence breakdown for a ranked candidate list.

    Args:
        candidates: Ranked candidates, best first. May be empty.
        known_technique_ids: Query techniques present in the vocabulary.
        weights: Global technique weights.
        component_weights: Relative weight of rarity / margin / sufficiency.

    Returns:
        A :class:`~ttp_similarity.schema.ConfidenceBreakdown` with all three
        components, the combined score and the level. An empty candidate list
        yields all-zero components and ``LOW``.
    """
    if component_weights is None:
        component_weights = config.CONFIDENCE_COMPONENT_WEIGHTS
    if not candidates:
        return ConfidenceBreakdown(rarity=0.0, margin=0.0, sufficiency=0.0, score=0.0, level=ConfidenceLevel.LOW)
    top = candidates[0]
    runner_up_score = candidates[1].score if len(candidates) > 1 else None
    rarity = rarity_component(top.matched_technique_ids, weights)
    margin = margin_component(top.score, runner_up_score)
    sufficiency = sufficiency_component(len(known_technique_ids))
    score = (rarity * component_weights['rarity'] + margin * component_weights['margin'] + sufficiency * component_weights['sufficiency'])
    score = max(0.0, min(1.0, score))
    if len(known_technique_ids) < config.MIN_QUERY_TECHNIQUES:
        level = ConfidenceLevel.LOW
    else:
        level = level_for_score(score)
    return ConfidenceBreakdown(rarity=rarity, margin=margin, sufficiency=sufficiency, score=score, level=level)


def explain(breakdown: ConfidenceBreakdown) -> list[str]:
    """Short human-readable reasons behind a confidence level.

    Turns the weakest component(s) into sentences the UI can show under the
    badge, e.g. "Aday 1 ve 2 arasındaki fark çok küçük" or "Girilen teknik
    sayısı az".

    Args:
        breakdown: Result of :func:`score_confidence`.

    Returns:
        Zero or more Turkish explanation strings, ordered worst component first.
    """
    reasons = []
    WEAK_THRESHOLD = 0.34
    components = [
        ('rarity', breakdown.rarity, 'Eşleşen teknikler yaygın ve ayırt edici değil'),
        ('margin', breakdown.margin, 'Aday 1 ve 2 arasındaki fark çok küçük'),
        ('sufficiency', breakdown.sufficiency, 'Girilen teknik sayısı az')
    ]
    components.sort(key=lambda x: x[1])
    for name, value, msg in components:
        if value < WEAK_THRESHOLD:
            reasons.append(msg)
    return reasons
