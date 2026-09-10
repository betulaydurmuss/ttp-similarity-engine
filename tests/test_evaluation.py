"""Tests for the benchmark's measurement design.

The design is fixed (50% of each actor's techniques, 20 repeats, skip below 3),
so these tests pin exactly that: a drifted sampler would quietly change every
number the project reports without any other test noticing.
"""

from __future__ import annotations

import pytest

from ttp_similarity import config
from ttp_similarity.evaluation import benchmark, metrics, sampling
from ttp_similarity.schema import Actor, ConfidenceLevel, EvaluationTrial


def _actors() -> list[Actor]:
    return [
        Actor(actor_id="G0001", name="Big", technique_ids=tuple(f"T{i:04d}" for i in range(20))),
        Actor(actor_id="G0002", name="Mid", technique_ids=tuple(f"T{i:04d}" for i in range(8))),
        Actor(actor_id="G0003", name="Tiny", technique_ids=("T0000", "T0001", "T0002", "T0003", "T0004")),
    ]


# --------------------------------------------------------------------------- #
# Sampling design
# --------------------------------------------------------------------------- #
def test_query_is_half_of_each_actors_techniques():
    plan = sampling.build_proportional_trial_plan(_actors(), fraction=0.5, repeats=2, seed=1)
    sizes = {t.actor_id: t.sample_size for t in plan.trials}
    assert sizes["G0001"] == 10  # 20 * 0.5
    assert sizes["G0002"] == 4  # 8 * 0.5
    # G0003: 5 * 0.5 -> 2, below the minimum of 3, so it is skipped entirely.
    assert "G0003" not in sizes


def test_too_small_a_query_is_skipped_and_counted_not_padded():
    plan = sampling.build_proportional_trial_plan(_actors(), fraction=0.5, repeats=20, seed=1)
    assert plan.skipped == 20  # one actor x 20 repeats
    assert plan.skipped_actors == ("G0003",)
    assert all(t.sample_size >= config.EVAL_MIN_QUERY_TECHNIQUES for t in plan.trials)


def test_repeat_count_is_honoured():
    plan = sampling.build_proportional_trial_plan(_actors(), fraction=0.5, repeats=20, seed=1)
    per_actor = {}
    for trial in plan.trials:
        per_actor[trial.actor_id] = per_actor.get(trial.actor_id, 0) + 1
    assert set(per_actor.values()) == {20}


def test_the_plan_is_reproducible_from_the_seed():
    first = sampling.build_proportional_trial_plan(_actors(), seed=99)
    second = sampling.build_proportional_trial_plan(_actors(), seed=99)
    assert [t.technique_ids for t in first.trials] == [t.technique_ids for t in second.trials]

    different = sampling.build_proportional_trial_plan(_actors(), seed=100)
    assert [t.technique_ids for t in first.trials] != [t.technique_ids for t in different.trials]


def test_sampled_techniques_belong_to_the_actor_and_are_unique():
    by_id = {a.actor_id: a for a in _actors()}
    plan = sampling.build_proportional_trial_plan(_actors(), repeats=5, seed=3)
    for trial in plan.trials:
        owned = set(by_id[trial.actor_id].technique_ids)
        assert set(trial.technique_ids) <= owned
        assert len(set(trial.technique_ids)) == len(trial.technique_ids)


def test_technique_count_is_carried_through_for_the_size_split():
    plan = sampling.build_proportional_trial_plan(_actors(), repeats=1, seed=3)
    counts = {t.actor_id: t.technique_count for t in plan.trials}
    assert counts["G0001"] == 20
    assert counts["G0002"] == 8


def test_sampling_reads_config_at_call_time(monkeypatch):
    monkeypatch.setattr(config, "EVAL_REPEATS_PER_ACTOR", 3)
    monkeypatch.setattr(config, "EVAL_QUERY_FRACTION", 0.5)
    plan = sampling.build_proportional_trial_plan(_actors(), seed=1)
    assert len(plan.trials) == 6  # two eligible actors x 3 repeats


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def _trial(rank: int, level=ConfidenceLevel.HIGH, count=10) -> EvaluationTrial:
    return EvaluationTrial(
        trial_id=0,
        true_actor_id="G0001",
        sample_size=5,
        sampled_technique_ids=(),
        predicted_actor_id="G0001",
        rank=rank,
        top1_score=0.5,
        confidence_level=level,
        technique_count=count,
    )


def test_top_k_accuracy_counts_the_right_ranks():
    trials = [_trial(1), _trial(3), _trial(5), _trial(-1)]
    assert metrics.top_k_accuracy(trials, 1) == 0.25
    assert metrics.top_k_accuracy(trials, 3) == 0.5
    assert metrics.top_k_accuracy(trials, 5) == 0.75


def test_mean_rank_excludes_misses_and_reports_them_separately():
    mean_rank, misses = metrics.mean_rank_of_correct_answer([_trial(1), _trial(3), _trial(-1)])
    assert mean_rank == 2.0  # (1 + 3) / 2, the miss is not folded in
    assert misses == 1


def test_mean_rank_of_an_all_miss_run_is_zero():
    mean_rank, misses = metrics.mean_rank_of_correct_answer([_trial(-1), _trial(-1)])
    assert mean_rank == 0.0
    assert misses == 2


def test_technique_count_buckets_split_by_target_size():
    trials = [_trial(1, count=7), _trial(2, count=15), _trial(1, count=60)]
    buckets = metrics.breakdown_by_technique_count(trials)
    assert set(buckets) == {"05-10", "11-20", "51+"}
    assert buckets["05-10"]["top1"] == 1.0
    assert buckets["11-20"]["top1"] == 0.0


def test_confidence_breakdown_shares_sum_to_one():
    trials = [_trial(1, ConfidenceLevel.HIGH), _trial(4, ConfidenceLevel.LOW)]
    breakdown = metrics.breakdown_by_confidence(trials)
    assert sum(row["share"] for row in breakdown.values()) == pytest.approx(1.0)
    assert breakdown["high"]["top1"] == 1.0
    assert breakdown["low"]["top1"] == 0.0


# --------------------------------------------------------------------------- #
# RunSpec / artefact assembly
# --------------------------------------------------------------------------- #
def test_runspec_resolves_from_config_at_run_time(monkeypatch):
    spec = benchmark.RunSpec(label="x")
    monkeypatch.setattr(config, "WEIGHTING_SCHEME", "binary")
    assert spec.resolved()["scheme"] == "binary"


def test_runspec_overrides_beat_config(monkeypatch):
    monkeypatch.setattr(config, "WEIGHTING_SCHEME", "binary")
    spec = benchmark.RunSpec(label="x", scheme="smooth_idf")
    assert spec.resolved()["scheme"] == "smooth_idf"


def test_threshold_filters_actors_the_same_way_a_rebuild_would():
    artifacts = benchmark.build_artifacts(_actors(), "test", min_techniques=8)
    assert {a.actor_id for a in artifacts.actors} == {"G0001", "G0002"}
    artifacts = benchmark.build_artifacts(_actors(), "test", min_techniques=10)
    assert {a.actor_id for a in artifacts.actors} == {"G0001"}


def test_a_threshold_that_empties_the_dataset_is_rejected():
    with pytest.raises(ValueError, match="leaves no actors"):
        benchmark.build_artifacts(_actors(), "test", min_techniques=500)


def test_binary_scheme_flattens_the_weights():
    artifacts = benchmark.build_artifacts(_actors(), "test", scheme="binary")
    assert set(artifacts.weights.values()) == {1.0}


# --------------------------------------------------------------------------- #
# Noise injection (regime C)
# --------------------------------------------------------------------------- #
def test_noise_is_off_unless_asked_for():
    plan = sampling.build_proportional_trial_plan(_actors(), repeats=3, seed=1)
    assert all(t.noise_count == 0 for t in plan.trials)


def _wide_actors() -> list[Actor]:
    """Actors that do not each cover the whole vocabulary, so noise has a pool."""
    return [
        Actor(actor_id="G0001", name="A", technique_ids=tuple(f"T{i:04d}" for i in range(20))),
        Actor(actor_id="G0002", name="B", technique_ids=tuple(f"T{i:04d}" for i in range(30, 50))),
    ]


def test_injected_noise_never_belongs_to_the_target_actor():
    by_id = {a.actor_id: a for a in _wide_actors()}
    plan = sampling.build_proportional_trial_plan(
        _wide_actors(), fraction=0.5, repeats=5, seed=2, noise_ratio=0.5
    )
    for trial in plan.trials:
        owned = set(by_id[trial.actor_id].technique_ids)
        injected = set(trial.technique_ids) - owned
        assert len(injected) == trial.noise_count
        assert injected, "regime C must actually inject something"


def test_noise_stops_when_the_pool_is_exhausted():
    """An actor covering the entire vocabulary simply gets no noise, not an error."""
    actors = [Actor(actor_id="G0001", name="A", technique_ids=tuple(f"T{i:04d}" for i in range(20)))]
    plan = sampling.build_proportional_trial_plan(
        actors, fraction=0.5, repeats=2, seed=1, noise_ratio=1.0
    )
    assert plan.trials
    assert all(t.noise_count == 0 for t in plan.trials)


def test_noise_count_scales_with_the_ratio():
    low = sampling.build_proportional_trial_plan(
        _wide_actors(), fraction=0.5, repeats=5, seed=2, noise_ratio=0.2
    )
    high = sampling.build_proportional_trial_plan(
        _wide_actors(), fraction=0.5, repeats=5, seed=2, noise_ratio=0.8
    )
    assert sum(t.noise_count for t in high.trials) > sum(t.noise_count for t in low.trials)


def test_noise_is_drawn_in_proportion_to_prevalence():
    """Commodity techniques must dominate the injected noise, not rare ones."""
    import random

    prevalence = {"T9001": 100, "T9002": 1}
    rng = random.Random(0)
    picks = [sample_one(prevalence, rng) for _ in range(200)]
    common = picks.count("T9001")
    assert common > 150, f"expected prevalence-weighted draw, got {common}/200 common"


def sample_one(prevalence, rng):
    return sampling.sample_noise(set(), 1, prevalence, rng)[0]


def test_skip_rule_applies_before_noise_is_added():
    """A tiny actor stays skipped; noise must not pad it into eligibility."""
    plan = sampling.build_proportional_trial_plan(
        _actors(), fraction=0.5, repeats=4, seed=1, noise_ratio=1.0
    )
    assert "G0003" not in {t.actor_id for t in plan.trials}
    assert plan.skipped == 4
