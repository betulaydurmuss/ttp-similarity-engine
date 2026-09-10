"""Draw synthetic queries from known actors.

Implemented: the sampling rules are simple and every other part of the
benchmark depends on them being deterministic.

Owner: evaluation module.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping, Sequence

from .. import config
from ..schema import Actor, ActorId, TechniqueId


@dataclass(frozen=True)
class TrialSpec:
    """One planned benchmark trial, before it is executed."""

    trial_id: int
    actor_id: ActorId
    sample_size: int  # total query length, noise included
    technique_ids: tuple[TechniqueId, ...]
    #: The actor's full technique count, carried through so the report can split
    #: accuracy by how well documented the target is.
    technique_count: int = 0
    #: How many of ``technique_ids`` are injected noise the actor does not use.
    noise_count: int = 0


@dataclass(frozen=True)
class TrialPlan:
    """A planned run: the trials to execute plus what was skipped.

    ``skipped`` is reported rather than silently swallowed -- an actor whose
    50% share falls below the minimum contributes nothing, and a run where that
    happens often is measuring a smaller population than it appears to.
    """

    trials: tuple[TrialSpec, ...] = ()
    skipped: int = 0
    skipped_actors: tuple[ActorId, ...] = ()


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


def build_noise_pool(actors: Sequence[Actor]) -> dict[TechniqueId, int]:
    """``technique_id -> number of actors using it``, for prevalence-weighted noise.

    Args:
        actors: The dataset's actors.

    Returns:
        Prevalence counts over the full vocabulary.
    """
    pool: dict[TechniqueId, int] = {}
    for actor in actors:
        for technique_id in set(actor.technique_ids):
            pool[technique_id] = pool.get(technique_id, 0) + 1
    return pool


def sample_noise(
    exclude: set[TechniqueId],
    count: int,
    prevalence: Mapping[TechniqueId, int],
    rng: random.Random,
) -> tuple[TechniqueId, ...]:
    """Draw ``count`` techniques the actor does *not* use, weighted by prevalence.

    Weighted rather than uniform on purpose. A real analyst's technique list is
    dominated by commodity behaviour that happens to be present in the incident;
    uniform noise would mostly inject rare techniques, which the weighting
    discounts easily and which would make the task unrealistically easy.

    Args:
        exclude: The actor's own techniques -- never drawn as noise.
        count: How many to draw.
        prevalence: ``technique_id -> actor count``.
        rng: Seeded RNG.

    Returns:
        Sorted unique noise technique ids; shorter than ``count`` only when the
        pool is exhausted.
    """
    candidates = [t for t in sorted(prevalence) if t not in exclude]
    weights = [float(prevalence[t]) for t in candidates]
    picked: list[TechniqueId] = []
    for _ in range(min(count, len(candidates))):
        total = sum(weights)
        if total <= 0:
            break
        threshold = rng.random() * total
        cumulative = 0.0
        for index, weight in enumerate(weights):
            cumulative += weight
            if cumulative >= threshold:
                picked.append(candidates[index])
                weights[index] = 0.0  # draw without replacement
                break
    return tuple(sorted(picked))


def build_proportional_trial_plan(
    actors: Sequence[Actor],
    *,
    fraction: float | None = None,
    repeats: int | None = None,
    seed: int | None = None,
    min_query_techniques: int | None = None,
    noise_ratio: float = 0.0,
) -> TrialPlan:
    """Plan the primary benchmark: a fixed share of each actor's techniques.

    For every actor, ``fraction`` of its techniques are drawn at random as the
    query and the rest are hidden. The actor itself is the retrieval target, so
    this measures self-retrieval: can the engine find an actor from half of its
    own documented behaviour?

    A repetition whose query would hold fewer than ``min_query_techniques``
    techniques is skipped and counted. It is never padded -- padding would put
    hidden techniques back into the query and leak the answer.

    Args:
        actors: Actors to draw from.
        fraction: Share of techniques used as the query.
        repeats: Repetitions per actor.
        seed: RNG seed; the same seed reproduces the same plan exactly.
        min_query_techniques: Minimum usable query size, applied to the actor's
            own techniques before any noise is added.
        noise_ratio: Share of the query length injected as techniques the actor
            does not use. Defaults to ``0.0`` -- noise is opt-in, so an ordinary
            run is never silently made harder. Regime C passes
            :data:`ttp_similarity.config.EVAL_NOISE_RATIO`, read at call time.

    All of these default to ``None`` and are read from
    :mod:`ttp_similarity.config` at call time, so an ablation run that changes
    the config actually takes effect.

    Returns:
        A :class:`TrialPlan`.
    """
    fraction = config.EVAL_QUERY_FRACTION if fraction is None else fraction
    repeats = config.EVAL_REPEATS_PER_ACTOR if repeats is None else repeats
    seed = config.EVAL_RANDOM_SEED if seed is None else seed
    if min_query_techniques is None:
        min_query_techniques = config.EVAL_MIN_QUERY_TECHNIQUES

    prevalence = build_noise_pool(actors) if noise_ratio > 0 else {}
    rng = random.Random(seed)
    trials: list[TrialSpec] = []
    skipped = 0
    skipped_actors: list[ActorId] = []
    trial_id = 0

    for actor in sorted(actors, key=lambda a: a.actor_id):
        total = len(actor.technique_ids)
        size = int(total * fraction)
        if size < min_query_techniques:
            # Every repetition for this actor is unusable; count them all.
            skipped += repeats
            skipped_actors.append(actor.actor_id)
            continue
        owned = set(actor.technique_ids)
        for _ in range(repeats):
            sampled = tuple(sorted(rng.sample(list(actor.technique_ids), size)))
            noise: tuple[TechniqueId, ...] = ()
            if noise_ratio > 0:
                noise = sample_noise(
                    owned, int(round(size * noise_ratio)), prevalence, rng
                )
            query_ids = tuple(sorted(set(sampled) | set(noise)))
            trials.append(
                TrialSpec(
                    trial_id=trial_id,
                    actor_id=actor.actor_id,
                    sample_size=len(query_ids),
                    technique_ids=query_ids,
                    technique_count=total,
                    noise_count=len(noise),
                )
            )
            trial_id += 1

    return TrialPlan(
        trials=tuple(trials),
        skipped=skipped,
        skipped_actors=tuple(skipped_actors),
    )


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
