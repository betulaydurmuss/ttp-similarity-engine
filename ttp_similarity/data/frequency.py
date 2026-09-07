"""Technique frequency table -- how many actors use each technique.

This is a deliverable in its own right (it answers "which techniques are
commodity and which are distinctive?") and it is also the input the engine's
weighting stage consumes. It is implemented here rather than in the engine so
that both the real and the synthetic dataset carry the same table.

Owner: data module. Consumed by: engine (weighting), app (technique picker).
"""

from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

import pandas as pd

from ..schema import (
    ACTOR_TECHNIQUE_COLUMNS,
    TECHNIQUE_FREQUENCY_COLUMNS,
    Actor,
    TechniqueId,
)


def compute_technique_frequency(
    actors: Sequence[Actor],
    technique_names: Mapping[TechniqueId, str] | None = None,
) -> pd.DataFrame:
    """Count the actors using each technique.

    Args:
        actors: Canonical actor records.
        technique_names: ``technique_id -> name`` lookup for the display column.
            Missing names fall back to the id itself.

    Returns:
        DataFrame with :data:`~ttp_similarity.schema.TECHNIQUE_FREQUENCY_COLUMNS`,
        sorted by ``actor_count`` descending then ``technique_id``. ``actor_ratio``
        is ``actor_count / len(actors)``.

    Raises:
        ValueError: If ``actors`` is empty -- a frequency table over zero actors
            would silently produce meaningless weights downstream.
    """
    if not actors:
        raise ValueError("cannot compute technique frequency over an empty actor set")

    names = dict(technique_names or {})
    counter: Counter[TechniqueId] = Counter()
    for actor in actors:
        # set() guards against a caller passing an actor with duplicate ids.
        counter.update(set(actor.technique_ids))

    total_actors = len(actors)
    frame = pd.DataFrame(
        [
            {
                "technique_id": technique_id,
                "technique_name": names.get(technique_id, technique_id),
                "actor_count": count,
                "actor_ratio": count / total_actors,
            }
            for technique_id, count in counter.items()
        ],
        columns=list(TECHNIQUE_FREQUENCY_COLUMNS),
    )
    return frame.sort_values(
        ["actor_count", "technique_id"], ascending=[False, True]
    ).reset_index(drop=True)


def build_actor_technique_frame(
    actors: Sequence[Actor],
    technique_names: Mapping[TechniqueId, str] | None = None,
) -> pd.DataFrame:
    """Explode actors into the tidy ``actor_technique.csv`` edge table.

    Args:
        actors: Canonical actor records.
        technique_names: ``technique_id -> name`` lookup for the display column.

    Returns:
        DataFrame with :data:`~ttp_similarity.schema.ACTOR_TECHNIQUE_COLUMNS`,
        one row per (actor, technique) pair, sorted by actor then technique.
    """
    names = dict(technique_names or {})
    rows = [
        {
            "actor_id": actor.actor_id,
            "actor_name": actor.name,
            "technique_id": technique_id,
            "technique_name": names.get(technique_id, technique_id),
        }
        for actor in actors
        for technique_id in actor.technique_ids
    ]
    frame = pd.DataFrame(rows, columns=list(ACTOR_TECHNIQUE_COLUMNS))
    return frame.sort_values(["actor_id", "technique_id"]).reset_index(drop=True)


def coverage_summary(frequency: pd.DataFrame) -> dict[str, float]:
    """Descriptive stats about the frequency distribution, for build logs.

    Args:
        frequency: Output of :func:`compute_technique_frequency`.

    Returns:
        Mapping with the technique count, the share of techniques used by a
        single actor (``singleton_share`` -- the high-signal tail) and the share
        used by more than half the population (``commodity_share``).
    """
    total = len(frequency)
    if total == 0:
        return {"techniques": 0, "singleton_share": 0.0, "commodity_share": 0.0}
    return {
        "techniques": float(total),
        "singleton_share": float((frequency["actor_count"] == 1).mean()),
        "commodity_share": float((frequency["actor_ratio"] > 0.5).mean()),
    }
