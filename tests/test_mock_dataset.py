"""Tests for the synthetic fixture and the frequency table.

The fixture is what unblocks the engine and app owners, so its properties are
asserted rather than assumed: 15 actors, deterministic output, a usable rarity
spread, and a recoverable family structure.
"""

from __future__ import annotations

import pytest

from ttp_similarity import paths, storage
from ttp_similarity.data import frequency as frequency_mod
from ttp_similarity.data import mock_dataset
from ttp_similarity.data.normalize import (
    normalize_technique_ids,
    roll_up_technique_id,
    slugify,
)
from ttp_similarity.schema import TECHNIQUE_FREQUENCY_COLUMNS


@pytest.fixture(scope="module")
def actors():
    return mock_dataset.generate_mock_actors()


def test_fixture_has_fifteen_actors(actors):
    assert len(actors) == 15
    assert len({a.actor_id for a in actors}) == 15


def test_fixture_is_deterministic():
    first = mock_dataset.generate_mock_actors(seed=42)
    second = mock_dataset.generate_mock_actors(seed=42)
    assert [a.technique_ids for a in first] == [a.technique_ids for a in second]


def test_a_different_seed_gives_a_different_fixture():
    default = mock_dataset.generate_mock_actors()
    other = mock_dataset.generate_mock_actors(seed=999)
    assert [a.technique_ids for a in default] != [a.technique_ids for a in other]


def test_every_actor_is_dense_enough_to_compare(actors):
    for actor in actors:
        assert len(actor.technique_ids) >= 10, actor.name
        # No duplicates and sorted, as the schema promises.
        assert list(actor.technique_ids) == sorted(set(actor.technique_ids))


def test_technique_ids_are_real_parent_level_ids(actors):
    vocabulary = {tid for tid, _, _ in mock_dataset.MOCK_TECHNIQUE_CATALOGUE}
    for actor in actors:
        for technique_id in actor.technique_ids:
            assert technique_id in vocabulary
            assert "." not in technique_id


def test_actors_carry_ground_truth_family(actors):
    families = {actor.metadata["family"] for actor in actors}
    assert families == set(mock_dataset.FAMILY_CORES)
    # Five families of three, so clustering has something to recover.
    for family in families:
        assert sum(1 for a in actors if a.metadata["family"] == family) == 3


def test_every_actor_has_at_least_one_alias(actors):
    for actor in actors:
        assert actor.aliases, actor.name
        assert actor.name not in actor.aliases


def test_frequency_table_shape_and_bounds(actors):
    frequency = frequency_mod.compute_technique_frequency(
        actors, mock_dataset.technique_names()
    )
    assert list(frequency.columns) == list(TECHNIQUE_FREQUENCY_COLUMNS)
    assert (frequency["actor_count"] >= 1).all()
    assert (frequency["actor_count"] <= len(actors)).all()
    assert frequency["actor_ratio"].between(0, 1).all()
    # Sorted most common first.
    assert frequency["actor_count"].is_monotonic_decreasing


def test_frequency_spread_gives_the_weighting_something_to_work_with(actors):
    frequency = frequency_mod.compute_technique_frequency(actors)
    summary = frequency_mod.coverage_summary(frequency)
    # A rare tail must exist, otherwise IDF weighting is meaningless.
    assert summary["singleton_share"] > 0.0
    # ...and some commodity techniques, otherwise there is nothing to discount.
    assert summary["commodity_share"] > 0.0


def test_frequency_rejects_an_empty_actor_set():
    with pytest.raises(ValueError):
        frequency_mod.compute_technique_frequency([])


def test_edge_table_matches_the_actor_records(actors):
    edges = frequency_mod.build_actor_technique_frame(actors)
    assert len(edges) == sum(len(a.technique_ids) for a in actors)
    assert set(edges["actor_id"]) == {a.actor_id for a in actors}


def test_subtechnique_roll_up():
    assert roll_up_technique_id("T1059.003") == "T1059"
    assert roll_up_technique_id("t1059") == "T1059"
    assert roll_up_technique_id(" T1566.001 ") == "T1566"
    assert normalize_technique_ids(["T1059.003", "T1059", "T1566.001"]) == (
        "T1059",
        "T1566",
    )


def test_slugify_makes_stable_ids():
    assert slugify("SILENT HERON") == "silent-heron"
    assert slugify("APT 29") == slugify("APT-29")


def test_build_writes_the_full_stage_one_artifact_set(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(paths, "MOCK_DIR", tmp_path / "mock")
    monkeypatch.setattr(paths, "FIGURES_DIR", tmp_path / "figures")
    monkeypatch.setattr(paths, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(paths, "INTERIM_DIR", tmp_path / "interim")

    workspace = mock_dataset.build_mock_dataset(paths.Workspace.get("mock"))

    for artefact in (
        workspace.actors,
        workspace.actor_technique,
        workspace.techniques,
        workspace.technique_frequency,
        workspace.data_manifest,
    ):
        assert artefact.exists(), artefact

    manifest = storage.read_manifest(workspace.data_manifest)
    assert manifest.actor_count == 15
    assert manifest.source == "synthetic"

    reloaded = storage.read_actors(workspace.actors)
    assert len(reloaded) == 15
    assert reloaded[0].source == "mock"
