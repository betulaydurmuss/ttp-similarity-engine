import numpy as np
import pytest
from sklearn.metrics import adjusted_rand_score

from ttp_similarity.data import mock_dataset
from ttp_similarity.engine import (
    clustering,
    confidence,
    layout,
    query,
    rank_actors,
    similarity,
    weighting,
)
from ttp_similarity.evaluation import benchmark

QUERY = ["T1566", "T1078", "T1047", "T1003", "T1059", "T1082"]


@pytest.fixture(scope="module")
def actors():
    return mock_dataset.generate_mock_actors()


@pytest.fixture(scope="module")
def artifacts(actors):
    return benchmark.build_artifacts(
        actors, "mock", technique_names=mock_dataset.technique_names()
    )


def test_confidence_does_not_depend_on_how_many_candidates_are_shown(artifacts):
    wide = query.query_techniques(QUERY, artifacts, top_k=10)
    narrow = query.query_techniques(QUERY, artifacts, top_k=1)
    assert len(narrow.candidates) == 1
    assert narrow.confidence == wide.confidence


def test_margin_is_measured_against_the_runner_up_of_the_full_ranking(artifacts):
    result = query.query_techniques(QUERY, artifacts, top_k=1)
    known = [t for t in result.query_technique_ids if t not in result.unknown_technique_ids]
    scores = query.score_query(known, artifacts)
    ordered = np.sort(scores)[::-1]
    expected = confidence.margin_component(ordered[0], ordered[1])
    assert result.confidence.margin == pytest.approx(expected)


def test_evidence_shares_are_the_true_cosine_decomposition(artifacts):
    result = query.query_techniques(QUERY, artifacts, coverage_correction=False)
    top = result.top
    row = artifacts.space.actor_ids.index(top.actor_id)
    vector, known, _ = query.vectorize.vectorize_query(
        result.query_technique_ids, artifacts.space, artifacts.weights
    )
    index = artifacts.space.technique_index()
    terms = {
        tid: artifacts.space.matrix[row, index[tid]] * vector[index[tid]]
        for tid in top.matched_technique_ids
    }
    total = sum(terms.values())
    for evidence in top.evidence:
        assert evidence.contribution == pytest.approx(terms[evidence.technique_id] / total)
    assert top.score == pytest.approx(total)


def test_evidence_shares_sum_to_one_when_nothing_is_capped(artifacts):
    result = query.query_techniques(QUERY, artifacts)
    for candidate in result.candidates:
        if len(candidate.evidence) == len(candidate.matched_technique_ids):
            assert sum(e.contribution for e in candidate.evidence) == pytest.approx(1.0)


def test_rare_evidence_outweighs_commodity_evidence(artifacts):
    result = query.query_techniques(QUERY, artifacts, coverage_correction=False)
    shares = {e.technique_id: e.contribution for e in result.top.evidence}
    weights = artifacts.weights
    rare = max(shares, key=lambda t: weights[t])
    common = min(shares, key=lambda t: weights[t])
    ratio = (weights[rare] / weights[common]) ** 2
    assert shares[rare] / shares[common] == pytest.approx(ratio)


def test_unknown_metric_has_no_contribution_model():
    with pytest.raises(ValueError):
        query.contribution_mass(["T1"], {"T1": 1.0}, metric="euclid")


def test_rarity_is_a_property_of_the_data_not_of_the_scheme(actors):
    binary = benchmark.build_artifacts(actors, "mock", scheme="binary")
    smooth = benchmark.build_artifacts(actors, "mock", scheme="smooth_idf")
    assert binary.rarity_weights == smooth.rarity_weights
    commodity = ("T1059", "T1082", "T1083", "T1105")
    rarity = weighting.normalized_rarity(commodity, binary.rarity_weights)
    assert rarity < 0.5


def test_binary_scheme_no_longer_reports_every_query_as_maximally_rare(actors):
    binary = benchmark.build_artifacts(actors, "mock", scheme="binary")
    result = query.query_techniques(["T1059", "T1082", "T1083", "T1105"], binary)
    assert result.confidence.rarity < 0.5


def test_rarity_weights_match_smooth_idf_weights(artifacts):
    for tid, weight in artifacts.weights.items():
        assert artifacts.rarity_weights[tid] == pytest.approx(weight)


def test_rank_actors_accepts_preloaded_artifacts(artifacts):
    rows = rank_actors(QUERY, top_k=3, artifacts=artifacts)
    assert 1 <= len(rows) <= 3
    assert isinstance(rows[0]["matched_techniques"], list)
    assert len({row["confidence_score"] for row in rows}) == 1
    assert all(0.0 <= row["technique_coverage"] <= 1.0 for row in rows)


def test_clustering_recovers_the_mock_families(actors, artifacts):
    sim = similarity.compute_similarity(artifacts.space)
    assignments = clustering.cluster_actors(sim)
    family = {a.actor_id: a.metadata["family"] for a in actors}
    ids = list(sim.actor_ids)
    ari = adjusted_rand_score([family[i] for i in ids], [assignments[i] for i in ids])
    assert ari >= 0.9


def test_layout_is_bounded_deterministic_and_faithful(artifacts):
    sim = similarity.compute_similarity(artifacts.space)
    first = layout.compute_layout(sim)
    second = layout.compute_layout(sim)
    assert list(first["actor_id"]) == list(sim.actor_ids)
    assert first.equals(second)
    xy = first[["x", "y"]].to_numpy()
    assert np.abs(xy).max() <= 1.0 + 1e-9
    distance = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1))
    upper = np.triu_indices(len(xy), 1)
    correlation = np.corrcoef(distance[upper], 1 - sim.matrix[upper])[0, 1]
    assert correlation > 0.6


def test_layout_handles_tiny_spaces():
    from ttp_similarity.schema import SimilarityMatrix

    single = layout.compute_layout(SimilarityMatrix(("A",), np.ones((1, 1))))
    assert single[["x", "y"]].to_numpy().tolist() == [[0.0, 0.0]]
    pair = layout.compute_layout(SimilarityMatrix(("A", "B"), np.eye(2)))
    assert len(pair) == 2
