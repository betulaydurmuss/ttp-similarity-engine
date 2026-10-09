import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ttp_similarity.api.app import create_app
from ttp_similarity.api.service import Station
from ttp_similarity.data import mock_dataset
from ttp_similarity.evaluation import benchmark

QUERY = ["T1566", "T1078", "T1047", "T1003", "T1560", "T1567"]


@pytest.fixture(scope="module")
def station():
    actors = mock_dataset.generate_mock_actors()
    artifacts = benchmark.build_artifacts(
        actors, "mock", technique_names=mock_dataset.technique_names()
    )
    tactics = {tid: t.tactics for tid, t in mock_dataset.technique_catalogue().items()}
    return Station.from_artifacts(artifacts, tactics, manifest={"attack_version": "test"})


@pytest.fixture(scope="module")
def client(station):
    return TestClient(create_app(station, web_dist=None))


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "dataset": "mock"}


def test_station_overview_is_complete_and_consistent(client):
    body = client.get("/api/station").json()
    assert body["dataset"]["actor_count"] == len(body["actors"]) == 15
    assert body["dataset"]["technique_count"] == len(body["techniques"])
    assert body["disclaimer"]
    tactic_ids = [t["id"] for t in body["tactics"]]
    assert tactic_ids.index("initial-access") < tactic_ids.index("impact")
    for technique in body["techniques"]:
        assert 0.0 <= technique["heat"] <= 1.0
        assert set(technique["tactics"]) <= set(tactic_ids)
    for actor in body["actors"]:
        assert -1.0 <= actor["x"] <= 1.0 and -1.0 <= actor["y"] <= 1.0
    sizes = sum(c["size"] for c in body["constellations"])
    assert sizes == sum(1 for a in body["actors"] if a["cluster"] >= 0)
    assert all(c["label"] for c in body["constellations"])


def test_rarest_technique_is_hottest(client):
    techniques = client.get("/api/station").json()["techniques"]
    hottest = max(techniques, key=lambda t: t["heat"])
    coldest = min(techniques, key=lambda t: t["heat"])
    assert hottest["actor_count"] <= coldest["actor_count"]
    assert hottest["heat"] == 1.0 and coldest["heat"] == 0.0


def test_query_returns_ranked_explained_candidates(client):
    body = client.post("/api/query", json={"techniques": QUERY, "top_k": 5}).json()
    candidates = body["candidates"]
    assert 1 <= len(candidates) <= 5
    assert [c["rank"] for c in candidates] == list(range(1, len(candidates) + 1))
    scores = [c["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)
    top = candidates[0]
    assert sum(e["share"] for e in top["evidence"]) == pytest.approx(1.0, abs=1e-3)
    assert set(top["matched"]) | set(top["missing"]) == set(body["query"]["known"])
    assert body["confidence"]["level"] in {"high", "medium", "low"}
    assert len(body["confidence"]["components"]) == 3
    assert body["probe"] is not None
    assert body["field"][top["id"]] == pytest.approx(top["score"], abs=1e-3)


def test_query_accepts_a_pasted_blob_and_reports_unknown_ids(client):
    body = client.post(
        "/api/query", json={"techniques": "t1566.001, T1078; T9999\nnot-an-id"}
    ).json()
    assert "T1566" in body["query"]["known"]
    assert set(body["query"]["unknown"]) == {"T9999", "NOT-AN-ID"}
    unknown = [s for s in body["signals"] if not s["known"]]
    assert {s["id"] for s in unknown} == {"T9999", "NOT-AN-ID"}


def test_empty_query_is_low_confidence_without_a_probe(client):
    body = client.post("/api/query", json={"techniques": ["T9999"]}).json()
    assert body["candidates"] == []
    assert body["confidence"]["level"] == "low"
    assert body["probe"] is None
    assert body["field"] == {}


def test_confidence_is_identical_whatever_top_k(client):
    wide = client.post("/api/query", json={"techniques": QUERY, "top_k": 10}).json()
    narrow = client.post("/api/query", json={"techniques": QUERY, "top_k": 1}).json()
    assert wide["confidence"] == narrow["confidence"]


@pytest.mark.parametrize(
    "payload",
    [
        {"techniques": ["T1566"] * 401},
        {"techniques": ["T" * 41]},
        {"techniques": "x" * 16_001},
        {"techniques": ["T1566"], "top_k": 0},
        {"techniques": ["T1566"], "top_k": 51},
        {"top_k": 5},
    ],
)
def test_query_input_is_bounded(client, payload):
    assert client.post("/api/query", json=payload).status_code == 422


def test_dossier(client, station):
    actor = station.artifacts.actors[0]
    body = client.get(f"/api/actors/{actor.actor_id.upper()}").json()
    assert body["id"] == actor.actor_id
    assert body["technique_count"] == len(actor.technique_ids)
    weights = [t["weight"] for t in body["techniques"]]
    assert weights == sorted(weights, reverse=True)
    assert actor.actor_id not in {n["id"] for n in body["neighbours"]}
    neighbour_scores = [n["score"] for n in body["neighbours"]]
    assert neighbour_scores == sorted(neighbour_scores, reverse=True)


@pytest.mark.parametrize("bad", ["NOPE", "G9999"])
def test_unknown_actor_is_404_json(client, bad):
    response = client.get(f"/api/actors/{bad}")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_actor_id_is_validated(client):
    assert client.get("/api/actors/%3Cscript%3E").status_code == 422


def test_compare_partitions_both_footprints(client, station):
    left, right = station.artifacts.actors[0], station.artifacts.actors[1]
    body = client.get(f"/api/compare?a={left.actor_id}&b={right.actor_id}").json()
    shared = {t["id"] for t in body["shared"]}
    left_only = {t["id"] for t in body["left_only"]}
    right_only = {t["id"] for t in body["right_only"]}
    assert shared | left_only == set(left.technique_ids)
    assert shared | right_only == set(right.technique_ids)
    assert not (left_only & right_only)
    assert 0.0 <= body["similarity"] <= 1.0
    assert body["jaccard"] == pytest.approx(len(shared) / len(shared | left_only | right_only), abs=1e-3)


def test_noise_never_repeats_the_query_and_is_reproducible(client):
    payload = {"techniques": QUERY, "ratio": 0.5, "seed": 11}
    first = client.post("/api/noise", json=payload).json()["noise"]
    second = client.post("/api/noise", json=payload).json()["noise"]
    assert first == second
    assert len(first) == 3
    assert not set(first) & set(QUERY)


def test_blind_case_draws_from_the_answer_actor(client, station):
    body = client.post("/api/blind", json={"fraction": 0.5, "noise_ratio": 0.3, "seed": 5}).json()
    actor = station.by_id[body["answer"]["id"]]
    assert set(body["techniques"]) <= set(actor.technique_ids)
    assert not set(body["noise"]) & set(actor.technique_ids)
    assert len(body["techniques"]) >= 3


def test_trust_reports_missing_results_with_the_command(client):
    body = client.get("/api/trust").json()
    assert body["available"] is False
    assert "--regimes" in body["command"]


def test_trust_reads_regime_reports(station, tmp_path):
    pd.DataFrame(
        [{"regime": "A", "label": "A / smooth_idf", "top1": 0.98, "notes": "x"}]
    ).to_csv(tmp_path / "regime_summary.csv", index=False)
    pd.DataFrame(
        [{"regime": "A", "label": "A / smooth_idf", "confidence": "high", "top1": 1.0}]
    ).to_csv(tmp_path / "regime_by_confidence.csv", index=False)
    original = station.reports_dir
    station.reports_dir = tmp_path
    try:
        body = station.trust()
    finally:
        station.reports_dir = original
    assert body["available"] is True
    assert body["summary"][0]["top1"] == 0.98
    assert "notes" not in body["summary"][0]
    assert body["by_size"] == []


def test_security_headers(client):
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "script-src 'self'" in headers["content-security-policy"]


def test_spa_fallback_serves_the_interface(station, tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>istasyon</title>", encoding="utf-8")
    app_client = TestClient(create_app(station, web_dist=tmp_path))
    assert "istasyon" in app_client.get("/").text
    assert "istasyon" in app_client.get("/harita/derin/bir/yol").text
    assert app_client.get("/api/does-not-exist").status_code == 404
    assert app_client.get("/api/does-not-exist").headers["content-type"].startswith("application/json")
