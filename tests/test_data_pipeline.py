"""Tests for the ATT&CK ingestion path.

Built on a tiny hand-written STIX bundle rather than the real 50 MB download, so
they run offline and in milliseconds. Each one pins a rule that would otherwise
be easy to break silently: identity comes from external_references, revoked and
deprecated objects are dropped, sub-techniques roll up, aliases merge but only
on distinctive tokens.
"""

from __future__ import annotations

import json

import pytest

from ttp_similarity.data import stix_parse
from ttp_similarity.data.normalize import (
    ALIAS_STOPLIST,
    alias_key,
    build_technique_catalogue,
    merge_alias_groups,
    normalize_bundle,
)
from ttp_similarity.data.stix_parse import RawActor, RawTechnique


def _ref(external_id: str, source: str = "mitre-attack") -> dict:
    return {"source_name": source, "external_id": external_id}


def _bundle_objects() -> list[dict]:
    """A miniature Enterprise bundle covering every rule under test."""
    return [
        {"type": "x-mitre-collection", "id": "x-mitre-collection--1", "x_mitre_version": "9.9"},
        # --- actors ---
        {
            "type": "intrusion-set",
            "id": "intrusion-set--a1",
            "name": "Alpha Group",
            "aliases": ["Alpha Group", "SHARED-TOKEN-XYZ", "APT"],
            "external_references": [_ref("G0001")],
        },
        {
            "type": "intrusion-set",
            "id": "intrusion-set--a2",
            "name": "Beta Group",
            "aliases": ["SHARED-TOKEN-XYZ"],  # merges with Alpha
            "external_references": [_ref("G0002")],
        },
        {
            "type": "intrusion-set",
            "id": "intrusion-set--a3",
            "name": "Gamma Group",
            "aliases": ["APT", "TA"],  # stoplisted only -> must NOT merge
            "external_references": [_ref("G0003")],
        },
        {
            "type": "intrusion-set",
            "id": "intrusion-set--a4",
            "name": "Revoked Group",
            "revoked": True,
            "external_references": [_ref("G0004")],
        },
        {
            "type": "intrusion-set",
            "id": "intrusion-set--a5",
            "name": "Deprecated Group",
            "x_mitre_deprecated": True,
            "external_references": [_ref("G0005")],
        },
        {
            "type": "intrusion-set",
            "id": "intrusion-set--a6",
            "name": "No Attack Id Group",  # no mitre-attack reference -> skipped
            "external_references": [_ref("X1", source="other-source")],
        },
        # --- techniques ---
        {
            "type": "attack-pattern",
            "id": "attack-pattern--t1",
            "name": "Command and Scripting Interpreter",
            "external_references": [_ref("T1059")],
            "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "execution"}],
        },
        {
            "type": "attack-pattern",
            "id": "attack-pattern--t1a",
            "name": "PowerShell",
            "x_mitre_is_subtechnique": True,
            "external_references": [_ref("T1059.001")],
            "kill_chain_phases": [
                {"kill_chain_name": "mitre-attack", "phase_name": "execution"},
                {"kill_chain_name": "other-chain", "phase_name": "ignored"},
            ],
        },
        {
            "type": "attack-pattern",
            "id": "attack-pattern--t1b",
            "name": "Unix Shell",
            "x_mitre_is_subtechnique": True,
            "external_references": [_ref("T1059.004")],
            "kill_chain_phases": [
                {"kill_chain_name": "mitre-attack", "phase_name": "persistence"}
            ],
        },
        {
            "type": "attack-pattern",
            "id": "attack-pattern--t2",
            "name": "Phishing",
            "external_references": [_ref("T1566")],
            "kill_chain_phases": [
                {"kill_chain_name": "mitre-attack", "phase_name": "initial-access"}
            ],
        },
        {
            "type": "attack-pattern",
            "id": "attack-pattern--t3",
            "name": "Old Technique",
            "revoked": True,
            "external_references": [_ref("T1999")],
        },
        # --- malware, to prove indirect edges are not followed ---
        {
            "type": "malware",
            "id": "malware--m1",
            "name": "SomeRAT",
            "external_references": [_ref("S0001")],
        },
        # --- relationships ---
        # Alpha uses both sub-techniques of T1059 -> must collapse to ONE edge
        {
            "type": "relationship",
            "id": "relationship--r1",
            "relationship_type": "uses",
            "source_ref": "intrusion-set--a1",
            "target_ref": "attack-pattern--t1a",
        },
        {
            "type": "relationship",
            "id": "relationship--r2",
            "relationship_type": "uses",
            "source_ref": "intrusion-set--a1",
            "target_ref": "attack-pattern--t1b",
        },
        {
            "type": "relationship",
            "id": "relationship--r3",
            "relationship_type": "uses",
            "source_ref": "intrusion-set--a1",
            "target_ref": "attack-pattern--t2",
        },
        {
            "type": "relationship",
            "id": "relationship--r4",
            "relationship_type": "uses",
            "source_ref": "intrusion-set--a2",
            "target_ref": "attack-pattern--t2",
        },
        {
            "type": "relationship",
            "id": "relationship--r5",
            "relationship_type": "uses",
            "source_ref": "intrusion-set--a3",
            "target_ref": "attack-pattern--t1",
        },
        # actor -> malware: dropped (not an attack-pattern target)
        {
            "type": "relationship",
            "id": "relationship--r6",
            "relationship_type": "uses",
            "source_ref": "intrusion-set--a1",
            "target_ref": "malware--m1",
        },
        # malware -> technique: dropped (source is not an intrusion-set)
        {
            "type": "relationship",
            "id": "relationship--r7",
            "relationship_type": "uses",
            "source_ref": "malware--m1",
            "target_ref": "attack-pattern--t2",
        },
        # non-"uses" relationship: dropped
        {
            "type": "relationship",
            "id": "relationship--r8",
            "relationship_type": "attributed-to",
            "source_ref": "intrusion-set--a1",
            "target_ref": "attack-pattern--t2",
        },
        # edge onto a revoked technique: disappears with it
        {
            "type": "relationship",
            "id": "relationship--r9",
            "relationship_type": "uses",
            "source_ref": "intrusion-set--a1",
            "target_ref": "attack-pattern--t3",
        },
    ]


@pytest.fixture()
def bundle_path(tmp_path):
    path = tmp_path / "enterprise-attack.json"
    path.write_text(
        json.dumps({"type": "bundle", "id": "bundle--1", "objects": _bundle_objects()}),
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def parsed(bundle_path):
    return stix_parse.parse_bundle(bundle_path)


# --------------------------------------------------------------------------- #
# stix_parse
# --------------------------------------------------------------------------- #
def test_rejects_a_file_that_is_not_a_bundle(tmp_path):
    path = tmp_path / "nope.json"
    path.write_text(json.dumps({"type": "grouping"}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a STIX bundle"):
        stix_parse.load_bundle_objects(path)


def test_identity_comes_from_external_references_not_the_stix_uuid(parsed):
    assert {a.attack_id for a in parsed.actors.values()} == {"G0001", "G0002", "G0003"}
    assert {t.attack_id for t in parsed.techniques.values()} == {
        "T1059",
        "T1059.001",
        "T1059.004",
        "T1566",
    }


def test_objects_without_an_attack_reference_are_skipped(parsed):
    assert all(a.name != "No Attack Id Group" for a in parsed.actors.values())


def test_revoked_and_deprecated_are_dropped_and_counted(parsed):
    names = {a.name for a in parsed.actors.values()}
    assert "Revoked Group" not in names
    assert "Deprecated Group" not in names
    assert parsed.stats["actors_revoked"] == 1
    assert parsed.stats["actors_deprecated"] == 1
    assert parsed.stats["actors_dropped"] == 2
    assert parsed.stats["techniques_revoked"] == 1
    assert parsed.stats["techniques_dropped"] == 1


def test_only_direct_actor_to_technique_uses_edges_are_kept(parsed):
    # 5 relationships qualify; the malware, non-uses and revoked-target ones do not.
    assert len(parsed.uses) == 5
    sources = {source for source, _ in parsed.uses}
    assert all(s.startswith("intrusion-set--") for s in sources)
    targets = {target for _, target in parsed.uses}
    assert all(t.startswith("attack-pattern--") for t in targets)


def test_attack_version_is_read_from_the_collection_object(parsed):
    assert parsed.attack_version == "9.9"


def test_canonical_name_is_not_repeated_in_aliases(parsed):
    alpha = next(a for a in parsed.actors.values() if a.attack_id == "G0001")
    assert "Alpha Group" not in alpha.aliases
    assert "SHARED-TOKEN-XYZ" in alpha.aliases


# --------------------------------------------------------------------------- #
# normalize
# --------------------------------------------------------------------------- #
def test_technique_catalogue_keeps_parents_and_unions_tactics(parsed):
    catalogue = build_technique_catalogue(parsed.techniques)
    assert set(catalogue) == {"T1059", "T1566"}
    # Parent object's own name wins over any sub-technique name.
    assert catalogue["T1059"].technique_name == "Command and Scripting Interpreter"
    # Tactics unioned across parent + sub-techniques, non-ATT&CK chains ignored.
    assert set(catalogue["T1059"].tactics) == {"execution", "persistence"}
    assert "ignored" not in catalogue["T1059"].tactics


def test_alias_key_rejects_stoplisted_and_short_tokens():
    assert alias_key("SHARED-TOKEN-XYZ") == "shared-token-xyz"
    assert alias_key("APT") is None
    assert alias_key("TA") is None
    assert alias_key("") is None
    for token in ("apt", "unc", "group", "team"):
        assert token in ALIAS_STOPLIST


def test_alias_merge_joins_shared_tokens_but_not_generic_ones(parsed):
    groups = merge_alias_groups(parsed.actors.values())
    sizes = {tuple(sorted(a.attack_id for a in group)) for group in groups}
    # G0001+G0002 share SHARED-TOKEN-XYZ; G0003 shares only "APT"/"TA".
    assert ("G0001", "G0002") in sizes
    assert ("G0003",) in sizes


def test_merge_is_deterministic_regardless_of_input_order():
    a = RawActor("intrusion-set--x", "G0002", "Beta", ("Zeta-Token",))
    b = RawActor("intrusion-set--y", "G0001", "Alpha", ("Zeta-Token",))
    forward = merge_alias_groups([a, b])
    backward = merge_alias_groups([b, a])
    assert [sorted(x.attack_id for x in g) for g in forward] == [
        sorted(x.attack_id for x in g) for g in backward
    ]
    # Lowest ATT&CK id becomes the canonical identity.
    assert min(forward[0], key=lambda x: x.attack_id).attack_id == "G0001"


def test_normalize_rolls_up_subtechniques_into_one_edge(parsed):
    # min_techniques=1: the fixture's actors have 1-2 techniques by design.
    result = normalize_bundle(parsed, min_techniques=1)
    actors = {a.actor_id: a for a in result.actors}

    # G0001 and G0002 merged; the merged actor uses T1059 (from two
    # sub-techniques) and T1566 -> two edges, not three.
    merged = actors["G0001"]
    assert merged.technique_ids == ("T1059", "T1566")
    assert "G0002" not in actors
    assert result.stats["edges_before_rollup"] == 5
    assert result.stats["edges_after_rollup"] == 4
    assert result.stats["edges_deduplicated_by_rollup"] == 1
    assert result.stats["alias_merge_count"] == 1


def test_normalize_output_matches_the_shared_schema(parsed):
    result = normalize_bundle(parsed, min_techniques=1)
    for actor in result.actors:
        assert actor.source == "attck"
        assert actor.actor_id.startswith("G")
        assert list(actor.technique_ids) == sorted(set(actor.technique_ids))
        assert all("." not in tid for tid in actor.technique_ids)
        assert actor.name not in actor.aliases
        assert actor.metadata["attack_version"] == "9.9"


def test_merged_actor_keeps_both_names_as_aliases(parsed):
    result = normalize_bundle(parsed, min_techniques=1)
    merged = next(a for a in result.actors if a.actor_id == "G0001")
    assert "Beta Group" in merged.aliases


def test_sparse_actors_are_dropped(parsed):
    # Default MIN_TECHNIQUES_PER_ACTOR is 5; this fixture's actors have 1-2,
    # so every one of them must be filtered out.
    result = normalize_bundle(parsed)
    assert result.actors == []
    assert result.stats["actors_dropped_sparse"] == result.stats["actors_after_alias_merge"]


def test_threshold_is_read_at_call_time_not_import_time(parsed, monkeypatch):
    from ttp_similarity import config

    monkeypatch.setattr(config, "MIN_TECHNIQUES_PER_ACTOR", 1)
    result = normalize_bundle(parsed)
    assert result.actors, "config change must take effect without a reimport"
    assert result.stats["min_techniques_per_actor"] == 1


def test_frequency_table_works_on_normalized_output(parsed):
    from ttp_similarity.data import frequency as frequency_mod

    result = normalize_bundle(parsed, min_techniques=1)
    names = {tid: t.technique_name for tid, t in result.techniques.items()}
    freq = frequency_mod.compute_technique_frequency(result.actors, names)

    assert set(freq["technique_id"]) == set(result.techniques)
    assert freq["actor_count"].max() <= len(result.actors)
    assert freq["actor_ratio"].between(0, 1).all()
