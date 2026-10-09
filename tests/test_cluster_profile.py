import pandas as pd
import pytest

from ttp_similarity.engine.clustering import cluster_profile


@pytest.fixture
def edges() -> pd.DataFrame:
    rows = [
        ("A1", "T1", "Common"), ("A2", "T1", "Common"), ("B1", "T1", "Common"), ("B2", "T1", "Common"),
        ("A1", "T2", "Alpha"), ("A2", "T2", "Alpha"),
        ("B1", "T3", "Beta"), ("B2", "T3", "Beta"),
        ("N1", "T4", "Noise"),
    ]
    return pd.DataFrame(rows, columns=["actor_id", "technique_id", "technique_name"]).assign(
        actor_name=lambda d: d["actor_id"]
    )


ASSIGNMENTS = {"A1": 0, "A2": 0, "B1": 1, "B2": 1, "N1": -1}


def test_columns_and_noise_excluded(edges):
    profile = cluster_profile(ASSIGNMENTS, edges)
    assert list(profile.columns) == [
        "cluster_id", "technique_id", "technique_name", "share_in_cluster", "lift",
    ]
    assert set(profile["cluster_id"]) == {0, 1}
    assert "T4" not in set(profile["technique_id"])


def test_lift_values_and_ordering(edges):
    profile = cluster_profile(ASSIGNMENTS, edges)
    first = profile[profile["cluster_id"] == 0].iloc[0]
    assert first["technique_id"] == "T2"
    assert first["share_in_cluster"] == pytest.approx(1.0)
    assert first["lift"] == pytest.approx(1.0 / (2 / 5))

    common = profile[(profile["cluster_id"] == 0) & (profile["technique_id"] == "T1")].iloc[0]
    assert common["lift"] == pytest.approx(1.0 / (4 / 5))
    lifts = profile[profile["cluster_id"] == 0]["lift"].tolist()
    assert lifts == sorted(lifts, reverse=True)


def test_top_n_limits_each_cluster(edges):
    profile = cluster_profile(ASSIGNMENTS, edges, top_n=1)
    assert profile.groupby("cluster_id").size().tolist() == [1, 1]


def test_empty_inputs(edges):
    assert cluster_profile({}, edges).empty
    assert cluster_profile({"N1": -1}, edges).empty
