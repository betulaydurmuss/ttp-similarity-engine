"""Property tests for the engine: the invariants the numbers depend on.

`test_engine.py` covers the individual functions. This file pins the four
structural guarantees the whole pipeline rests on, each of which would fail
silently and produce plausible-looking-but-wrong scores:

1. Weighting really separates the two ends of the frequency distribution, and
   the rare end does not blow up.
2. L2 normalisation removes the "well-documented actor" advantage.
3. The similarity matrix is symmetric with an exact 1.0 diagonal.
4. Cosine on binary weights degenerates to a set-overlap measure, so the
   weighted result must differ from the unweighted one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ttp_similarity import config
from ttp_similarity.engine import similarity as similarity_mod
from ttp_similarity.engine import vectorize, weighting
from ttp_similarity.schema import Actor


@pytest.fixture()
def frequency() -> pd.DataFrame:
    """Frequency table shaped like the real one: one universal, one singleton."""
    return pd.DataFrame(
        {
            "technique_id": ["T0001", "T0002", "T0003", "T0004", "T0005"],
            "technique_name": ["universal", "common", "mid", "rare", "singleton"],
            "actor_count": [100, 81, 40, 5, 1],
            "actor_ratio": [1.0, 0.81, 0.40, 0.05, 0.01],
        }
    )


# --------------------------------------------------------------------------- #
# 1. Weighting
# --------------------------------------------------------------------------- #
def test_weight_is_strictly_decreasing_in_actor_count(frequency):
    weights = weighting.compute_weights(frequency, n_actors=100)
    by_id = dict(zip(weights["technique_id"], weights["weight"]))
    ordered = [by_id[t] for t in ["T0005", "T0004", "T0003", "T0002", "T0001"]]
    assert ordered == sorted(ordered, reverse=True), "rarer must weigh strictly more"


def test_singleton_technique_does_not_blow_up_the_scale(frequency):
    """The rare end must stay within a small multiple of the common end.

    Without the ``+1`` floor and the smoothing, a technique used by one actor
    out of hundreds would dominate every score it appears in, and a single
    rare match would outrank a broad behavioural overlap.
    """
    weights = weighting.compute_weights(frequency, n_actors=100)
    by_id = dict(zip(weights["technique_id"], weights["weight"]))

    assert by_id["T0001"] >= 1.0, "the +1 floor keeps universal techniques usable"
    ratio = by_id["T0005"] / by_id["T0001"]
    assert 1.0 < ratio < 10.0, f"rare/common weight ratio {ratio:.1f} is out of range"
    # Hard ceiling: ln(N + s) + 1 for a technique nobody uses.
    assert by_id["T0005"] <= np.log(100 + config.IDF_SMOOTHING) + 1


def test_plain_idf_zeroes_universal_techniques(frequency):
    """The documented downside of the alternative scheme, pinned as a fact."""
    weights = weighting.compute_weights(frequency, n_actors=100, scheme="plain_idf")
    by_id = dict(zip(weights["technique_id"], weights["weight"]))
    assert by_id["T0001"] == pytest.approx(0.0)


def test_binary_scheme_is_the_ablation_baseline(frequency):
    weights = weighting.compute_weights(frequency, n_actors=100, scheme="binary")
    assert (weights["weight"] == 1.0).all()


def test_unknown_scheme_is_rejected(frequency):
    with pytest.raises(ValueError, match="unknown scheme"):
        weighting.compute_weights(frequency, n_actors=100, scheme="nope")


# --------------------------------------------------------------------------- #
# 2. Normalisation fairness
# --------------------------------------------------------------------------- #
def _space_with_uneven_actors():
    """A 'well documented' actor with 40 techniques vs a sparse one with 4.

    The sparse actor's techniques are a strict subset of the busy actor's, so
    any systematic size advantage shows up as an asymmetry in the scores.
    """
    vocabulary = [f"T{i:04d}" for i in range(40)]
    busy = Actor(actor_id="BUSY", name="Busy", technique_ids=tuple(vocabulary))
    sparse = Actor(actor_id="SPARSE", name="Sparse", technique_ids=tuple(vocabulary[:4]))
    other = Actor(actor_id="OTHER", name="Other", technique_ids=tuple(vocabulary[20:28]))
    weights = {t: 1.0 + 0.1 * i for i, t in enumerate(vocabulary)}
    return [busy, sparse, other], weights


def test_l2_normalisation_gives_every_actor_unit_length():
    actors, weights = _space_with_uneven_actors()
    space = vectorize.build_vector_space(actors, weights, normalize=True)
    norms = np.linalg.norm(space.matrix, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-12)


def test_without_normalisation_the_busy_actor_dominates():
    """Shows what normalisation is protecting against."""
    actors, weights = _space_with_uneven_actors()
    raw = vectorize.build_vector_space(actors, weights, normalize=False)
    norms = np.linalg.norm(raw.matrix, axis=1)
    busy, sparse = norms[0], norms[1]
    assert busy > 5 * sparse, "unnormalised vector length tracks technique count"


def test_normalised_similarity_is_not_driven_by_technique_count():
    actors, weights = _space_with_uneven_actors()
    space = vectorize.build_vector_space(actors, weights, normalize=True)
    sim = similarity_mod.compute_similarity(space, "cosine")
    index = {a: i for i, a in enumerate(sim.actor_ids)}

    # SPARSE is a strict subset of BUSY; OTHER is a different, larger subset.
    # Neither pair may be pushed to ~1.0 just because BUSY covers everything.
    busy_sparse = sim.matrix[index["BUSY"], index["SPARSE"]]
    assert busy_sparse < 0.9, (
        "a superset actor must not be near-identical to every subset actor"
    )


# --------------------------------------------------------------------------- #
# 3. Similarity matrix structure
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("metric", ["cosine", "jaccard"])
def test_similarity_matrix_is_symmetric_with_unit_diagonal(metric):
    actors, weights = _space_with_uneven_actors()
    space = vectorize.build_vector_space(actors, weights)
    sim = similarity_mod.compute_similarity(space, metric)

    np.testing.assert_allclose(sim.matrix, sim.matrix.T, atol=1e-12)
    np.testing.assert_allclose(np.diag(sim.matrix), 1.0, atol=1e-12)
    assert sim.matrix.min() >= 0.0
    assert sim.matrix.max() <= 1.0
    assert sim.metric == metric
    assert sim.actor_ids == space.actor_ids


def test_unknown_metric_is_rejected():
    actors, weights = _space_with_uneven_actors()
    space = vectorize.build_vector_space(actors, weights)
    with pytest.raises(ValueError, match="Unknown similarity metric"):
        similarity_mod.compute_similarity(space, "euclidean")


def test_similarity_stats_uses_only_the_off_diagonal():
    actors, weights = _space_with_uneven_actors()
    space = vectorize.build_vector_space(actors, weights)
    sim = similarity_mod.compute_similarity(space)
    stats = similarity_mod.similarity_stats(sim)
    # A diagonal of 1.0 leaking in would push the mean towards 1.
    assert stats["max"] < 1.0
    assert 0.0 <= stats["mean"] <= stats["p90"] <= stats["max"]


def test_nearest_actors_excludes_self():
    actors, weights = _space_with_uneven_actors()
    space = vectorize.build_vector_space(actors, weights)
    sim = similarity_mod.compute_similarity(space)
    neighbours = similarity_mod.nearest_actors(sim, "BUSY", top_k=5)
    assert "BUSY" not in [aid for aid, _ in neighbours]
    scores = [s for _, s in neighbours]
    assert scores == sorted(scores, reverse=True)


def test_nearest_actors_rejects_an_unknown_actor():
    actors, weights = _space_with_uneven_actors()
    space = vectorize.build_vector_space(actors, weights)
    sim = similarity_mod.compute_similarity(space)
    with pytest.raises(KeyError):
        similarity_mod.nearest_actors(sim, "NOPE")


# --------------------------------------------------------------------------- #
# 4. Weighting actually changes the answer
# --------------------------------------------------------------------------- #
def test_weighted_and_unweighted_rankings_differ(frequency):
    """If these agreed everywhere, the weighting would be buying nothing."""
    vocabulary = list(frequency["technique_id"])
    actors = [
        Actor(actor_id="A", name="A", technique_ids=("T0001", "T0002", "T0005")),
        Actor(actor_id="B", name="B", technique_ids=("T0001", "T0002", "T0003")),
        Actor(actor_id="C", name="C", technique_ids=("T0001", "T0004", "T0005")),
    ]
    idf = weighting.weights_to_mapping(weighting.compute_weights(frequency, 100))
    flat = {t: 1.0 for t in vocabulary}

    weighted = similarity_mod.compute_similarity(
        vectorize.build_vector_space(actors, idf), "cosine"
    )
    unweighted = similarity_mod.compute_similarity(
        vectorize.build_vector_space(actors, flat), "cosine"
    )
    # A and C share the singleton T0005; A and B share two commodity techniques.
    # Weighting must rate A-C relatively higher than the flat version does.
    index = {a: i for i, a in enumerate(weighted.actor_ids)}
    ac_w = weighted.matrix[index["A"], index["C"]]
    ab_w = weighted.matrix[index["A"], index["B"]]
    ac_f = unweighted.matrix[index["A"], index["C"]]
    ab_f = unweighted.matrix[index["A"], index["B"]]
    assert (ac_w / ab_w) > (ac_f / ab_f), "rare-technique overlap must be rewarded"
