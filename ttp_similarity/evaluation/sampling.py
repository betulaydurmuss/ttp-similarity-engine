"""Draw synthetic queries from known actors.

Implemented: the sampling rules are simple and every other part of the
benchmark depends on them being deterministic.

Owner: evaluation module.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from .. import config
from ..schema import Actor, ActorId, TechniqueId


@dataclass(frozen=True)
class TrialSpec:
    """One planned benchmark trial, before it is executed."""

    trial_id: int
    actor_id: ActorId
    sample_size: int
    technique_ids: tuple[TechniqueId, ...]


def sample_techniques(
    actor: Actor, sample_size: int, rng: random.Random
) -> tuple[TechniqueId, ...] | None:
    """Draw ``sample_size`` distinct techniques from an actor, without replacement.

    Args:
        actor: Source actor.
        sample_size: How many techniques to draw.
        rng: Seeded RNG, so a benchmark run is reproducible.

    Returns:
        The sampled ids, or ``None`` when the actor has fewer than
        ``sample_size`` techniques (that actor is skipped for this size rather
        than padded, which would leak information).
    """
    if len(actor.technique_ids) < sample_size:
        return None
    return tuple(sorted(rng.sample(list(actor.technique_ids), sample_size)))


def build_trial_plan(
    actors: Sequence[Actor],
    sample_sizes: Sequence[int] = config.EVAL_SAMPLE_SIZES,
    trials_per_actor: int = config.EVAL_TRIALS_PER_ACTOR,
    seed: int = config.EVAL_RANDOM_SEED,
) -> list[TrialSpec]:
    """Enumerate every trial the benchmark will run.

    Building the plan up front (rather than sampling inside the loop) means the
    same seed produces the same trials even if the engine changes, so two runs
    are directly comparable.

    Args:
        actors: Actors to draw from.
        sample_sizes: Query sizes to sweep.
        trials_per_actor: Draws per actor per sample size.
        seed: RNG seed.

    Returns:
        Trials ordered by sample size, then actor, then draw index.
    """
    rng = random.Random(seed)
    plan: list[TrialSpec] = []
    trial_id = 0
    for sample_size in sample_sizes:
        for actor in actors:
            for _ in range(trials_per_actor):
                sampled = sample_techniques(actor, sample_size, rng)
                if sampled is None:
                    continue
                plan.append(
                    TrialSpec(
                        trial_id=trial_id,
                        actor_id=actor.actor_id,
                        sample_size=sample_size,
                        technique_ids=sampled,
                    )
                )
                trial_id += 1
    return plan


def plan_summary(plan: Sequence[TrialSpec]) -> dict[int, int]:
    """``{sample_size: trial count}`` -- shows which sizes were under-sampled."""
    counts: dict[int, int] = {}
    for spec in plan:
        counts[spec.sample_size] = counts.get(spec.sample_size, 0) + 1
    return dict(sorted(counts.items()))


# TODO(eval): add a harder sampling mode once the basic benchmark works --
#   `sample_with_noise(actor, sample_size, noise_k, rng)` that injects
#   `noise_k` techniques the actor does NOT use. Real incident data always
#   contains techniques that turn out to be unrelated, and top-1 accuracy under
#   noise is the number that says whether this tool survives contact with a real
#   case. Note the decision in DECISIONS.md.
# TODO(eval): consider a "commodity-only" adversarial sample (draw only from the
#   most common techniques) to confirm the engine reports LOW confidence there
#   instead of a confident wrong answer.
