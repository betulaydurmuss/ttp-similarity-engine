"""Tests for the shared contract: schema round-trips, config, storage.

These guard the interfaces the three modules agreed on. If one of these breaks,
someone changed a shared format and the other two modules are about to break.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ttp_similarity import config, paths, storage
from ttp_similarity.schema import (
    Actor,
    BuildManifest,
    ConfidenceLevel,
    SimilarityMatrix,
    VectorSpace,
    join_list,
    split_list,
)


def test_config_is_self_consistent():
    config.validate()


def test_confidence_weights_sum_to_one():
    assert sum(config.CONFIDENCE_COMPONENT_WEIGHTS.values()) == pytest.approx(1.0)


def test_actor_round_trip():
    actor = Actor(
        actor_id="mock--test",
        name="TEST ACTOR",
        aliases=("TA-1", "Test Crew"),
        technique_ids=("T1059", "T1566"),
        source="mock",
        metadata={"family": "espionage"},
    )
    restored = Actor.from_dict(actor.to_dict())
    assert restored == actor
    assert restored.all_names == ("TEST ACTOR", "TA-1", "Test Crew")


def test_manifest_round_trip():
    manifest = BuildManifest(
        dataset="mock",
        source="synthetic",
        attack_version=None,
        built_at="2026-01-01T00:00:00+00:00",
        actor_count=15,
        technique_count=70,
        edge_count=300,
    )
    assert BuildManifest.from_dict(manifest.to_dict()) == manifest


def test_list_cell_encoding_round_trip():
    values = ("initial-access", "persistence")
    assert split_list(join_list(values)) == values
    assert split_list("") == ()
    assert split_list(float("nan")) == ()


def test_confidence_level_is_json_friendly():
    assert ConfidenceLevel.HIGH.value == "high"
    assert ConfidenceLevel("low") is ConfidenceLevel.LOW


def test_vector_space_rejects_mismatched_labels():
    with pytest.raises(ValueError):
        VectorSpace(
            actor_ids=("a", "b"),
            technique_ids=("T1059",),
            matrix=np.zeros((3, 1)),
        )


def test_similarity_matrix_rejects_non_square():
    with pytest.raises(ValueError):
        SimilarityMatrix(actor_ids=("a", "b"), matrix=np.zeros((2, 3)))


def test_vector_space_round_trip_on_disk(tmp_path):
    space = VectorSpace(
        actor_ids=("a", "b"),
        technique_ids=("T1059", "T1566", "T1078"),
        matrix=np.array([[1.0, 0.0, 0.5], [0.0, 2.0, 0.25]]),
    )
    path = tmp_path / "vector_space.npz"
    storage.write_vector_space(space, path)
    restored = storage.read_vector_space(path)

    assert restored.actor_ids == space.actor_ids
    assert restored.technique_ids == space.technique_ids
    np.testing.assert_allclose(restored.matrix, space.matrix)


def test_similarity_round_trip_on_disk(tmp_path):
    similarity = SimilarityMatrix(
        actor_ids=("a", "b"),
        matrix=np.array([[1.0, 0.3], [0.3, 1.0]]),
        metric="cosine",
    )
    path = tmp_path / "similarity.npz"
    storage.write_similarity(similarity, path)
    restored = storage.read_similarity(path)

    assert restored.actor_ids == similarity.actor_ids
    assert restored.metric == "cosine"
    np.testing.assert_allclose(restored.matrix, similarity.matrix)


def test_write_dataframe_enforces_the_column_contract(tmp_path):
    frame = pd.DataFrame({"actor_id": ["a"], "cluster_id": [0]})
    with pytest.raises(ValueError, match="missing required columns"):
        storage.write_dataframe(frame, tmp_path / "clusters.csv", ("actor_id", "actor_name"))


def test_missing_artifact_error_names_the_command(tmp_path):
    with pytest.raises(storage.ArtifactMissingError) as excinfo:
        storage.require(tmp_path / "weights.csv", dataset="mock")
    assert "ttp_similarity.engine.build" in str(excinfo.value)


def test_workspace_paths_are_scoped_to_the_dataset():
    mock_ws = paths.Workspace.get("mock")
    mitre_ws = paths.Workspace.get("mitre")
    assert mock_ws.actors != mitre_ws.actors
    assert mock_ws.actors.parent.name == "mock"
    assert mock_ws.evaluation_report.name == "evaluation.json"
