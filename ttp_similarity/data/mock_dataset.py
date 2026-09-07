"""Synthetic 15-actor fixture -- the unblocking dataset.

This module is **fully implemented on purpose**. It writes exactly the same
artefacts, with exactly the same schema, as the real ATT&CK build, so the
engine, evaluation and app owners can develop and test against
``data/processed/mock/`` from day one, before ingestion is finished.

Design of the fixture
---------------------
* Technique ids and names are the **real** ATT&CK ones, so the vocabulary the
  engine sees now matches the vocabulary it will see later.
* Actor names are **invented**. They intentionally do not correspond to any
  real threat group -- this fixture must never be mistaken for intelligence.
* The 15 actors are laid out in 5 behavioural families of 3. Each actor gets:
  a set of commodity techniques shared by nearly everyone, most of its family's
  core techniques, and a few random extras. That produces a realistic
  frequency curve (a handful of universal techniques, a long rare tail), a
  cluster structure the engine should recover, and near-duplicate pairs that
  make the confidence margin component do real work.
* The ground-truth family of each actor is written to
  ``data/mock/mock_ground_truth.csv`` and mirrored in ``Actor.metadata`` so the
  evaluation module can check clustering against a known answer.
* Generation is seeded, so the fixture is byte-identical on every machine.

Run standalone::

    python -m ttp_similarity.data.mock_dataset
    python -m ttp_similarity.data.mock_dataset --seed 7 --dataset mock

Owner: data module.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timezone
from typing import Mapping, Sequence

import pandas as pd

from .. import config, paths, storage
from ..schema import (
    TECHNIQUE_COLUMNS,
    Actor,
    BuildManifest,
    Technique,
    TechniqueId,
    join_list,
)
from . import frequency as frequency_mod
from .normalize import slugify

#: Deterministic default; override with ``--seed`` to generate a variant.
DEFAULT_SEED = 20260101

# --------------------------------------------------------------------------- #
# Vocabulary: real ATT&CK Enterprise parent techniques (id, name, tactics)
# --------------------------------------------------------------------------- #
MOCK_TECHNIQUE_CATALOGUE: tuple[tuple[str, str, str], ...] = (
    ("T1003", "OS Credential Dumping", "credential-access"),
    ("T1005", "Data from Local System", "collection"),
    ("T1007", "System Service Discovery", "discovery"),
    ("T1012", "Query Registry", "discovery"),
    ("T1016", "System Network Configuration Discovery", "discovery"),
    ("T1018", "Remote System Discovery", "discovery"),
    ("T1021", "Remote Services", "lateral-movement"),
    ("T1027", "Obfuscated Files or Information", "defense-evasion"),
    ("T1033", "System Owner/User Discovery", "discovery"),
    ("T1036", "Masquerading", "defense-evasion"),
    ("T1039", "Data from Network Shared Drive", "collection"),
    ("T1041", "Exfiltration Over C2 Channel", "exfiltration"),
    ("T1046", "Network Service Discovery", "discovery"),
    ("T1047", "Windows Management Instrumentation", "execution"),
    ("T1049", "System Network Connections Discovery", "discovery"),
    ("T1053", "Scheduled Task/Job", "execution|persistence|privilege-escalation"),
    ("T1055", "Process Injection", "defense-evasion|privilege-escalation"),
    ("T1056", "Input Capture", "collection|credential-access"),
    ("T1057", "Process Discovery", "discovery"),
    ("T1059", "Command and Scripting Interpreter", "execution"),
    ("T1068", "Exploitation for Privilege Escalation", "privilege-escalation"),
    ("T1070", "Indicator Removal", "defense-evasion"),
    ("T1071", "Application Layer Protocol", "command-and-control"),
    ("T1074", "Data Staged", "collection"),
    ("T1078", "Valid Accounts", "defense-evasion|persistence|initial-access"),
    ("T1082", "System Information Discovery", "discovery"),
    ("T1083", "File and Directory Discovery", "discovery"),
    ("T1087", "Account Discovery", "discovery"),
    ("T1090", "Proxy", "command-and-control"),
    ("T1095", "Non-Application Layer Protocol", "command-and-control"),
    ("T1102", "Web Service", "command-and-control"),
    ("T1105", "Ingress Tool Transfer", "command-and-control"),
    ("T1106", "Native API", "execution"),
    ("T1110", "Brute Force", "credential-access"),
    ("T1112", "Modify Registry", "defense-evasion"),
    ("T1113", "Screen Capture", "collection"),
    ("T1114", "Email Collection", "collection"),
    ("T1119", "Automated Collection", "collection"),
    ("T1132", "Data Encoding", "command-and-control"),
    ("T1133", "External Remote Services", "initial-access|persistence"),
    ("T1134", "Access Token Manipulation", "defense-evasion|privilege-escalation"),
    ("T1135", "Network Share Discovery", "discovery"),
    ("T1140", "Deobfuscate/Decode Files or Information", "defense-evasion"),
    ("T1189", "Drive-by Compromise", "initial-access"),
    ("T1190", "Exploit Public-Facing Application", "initial-access"),
    ("T1195", "Supply Chain Compromise", "initial-access"),
    ("T1199", "Trusted Relationship", "initial-access"),
    ("T1204", "User Execution", "execution"),
    ("T1210", "Exploitation of Remote Services", "lateral-movement"),
    ("T1213", "Data from Information Repositories", "collection"),
    ("T1218", "System Binary Proxy Execution", "defense-evasion"),
    ("T1485", "Data Destruction", "impact"),
    ("T1486", "Data Encrypted for Impact", "impact"),
    ("T1489", "Service Stop", "impact"),
    ("T1490", "Inhibit System Recovery", "impact"),
    ("T1491", "Defacement", "impact"),
    ("T1499", "Endpoint Denial of Service", "impact"),
    ("T1505", "Server Software Component", "persistence"),
    ("T1543", "Create or Modify System Process", "persistence|privilege-escalation"),
    ("T1547", "Boot or Logon Autostart Execution", "persistence|privilege-escalation"),
    ("T1550", "Use Alternate Authentication Material", "defense-evasion|lateral-movement"),
    ("T1552", "Unsecured Credentials", "credential-access"),
    ("T1553", "Subvert Trust Controls", "defense-evasion"),
    ("T1560", "Archive Collected Data", "collection"),
    ("T1562", "Impair Defenses", "defense-evasion"),
    ("T1566", "Phishing", "initial-access"),
    ("T1567", "Exfiltration Over Web Service", "exfiltration"),
    ("T1569", "System Services", "execution"),
    ("T1570", "Lateral Tool Transfer", "lateral-movement"),
    ("T1573", "Encrypted Channel", "command-and-control"),
    ("T1574", "Hijack Execution Flow", "defense-evasion|persistence"),
    ("T1583", "Acquire Infrastructure", "resource-development"),
    ("T1585", "Establish Accounts", "resource-development"),
    ("T1588", "Obtain Capabilities", "resource-development"),
    ("T1592", "Gather Victim Host Information", "reconnaissance"),
    ("T1608", "Stage Capabilities", "resource-development"),
)

#: Techniques almost every actor uses. These should end up with a low weight --
#: if the engine ranks a candidate highly on the strength of these alone, the
#: weighting is wrong.
COMMODITY_TECHNIQUES: tuple[TechniqueId, ...] = (
    "T1059",
    "T1082",
    "T1083",
    "T1105",
    "T1071",
    "T1057",
    "T1027",
)

#: family_id -> (label, core techniques)
FAMILY_CORES: Mapping[str, tuple[str, tuple[TechniqueId, ...]]] = {
    "espionage": (
        "Long-dwell espionage",
        ("T1566", "T1078", "T1047", "T1003", "T1560", "T1567", "T1114", "T1074",
         "T1021", "T1113"),
    ),
    "ransomware": (
        "Big-game ransomware",
        ("T1190", "T1133", "T1110", "T1486", "T1490", "T1489", "T1570", "T1112",
         "T1018", "T1562"),
    ),
    "implant": (
        "Supply-chain implant",
        ("T1195", "T1574", "T1573", "T1070", "T1140", "T1553", "T1218", "T1543",
         "T1132", "T1090"),
    ),
    "disruption": (
        "Disruption and defacement",
        ("T1485", "T1491", "T1499", "T1190", "T1102", "T1583", "T1585", "T1608",
         "T1204", "T1592"),
    ),
    "financial": (
        "Financially motivated intrusion",
        ("T1204", "T1036", "T1055", "T1056", "T1005", "T1041", "T1552", "T1550",
         "T1213", "T1119"),
    ),
}

#: (display name, family_id, aliases). Names are invented; any resemblance to a
#: real tracked group is coincidental and unintended.
MOCK_ACTOR_SEEDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("SILENT HERON", "espionage", ("HERON-07", "Cluster Alpha")),
    ("PALE LANTERN", "espionage", ("LANTERN GROUP",)),
    ("GLASS MERIDIAN", "espionage", ("MERIDIAN-3", "GM-Actor")),
    ("IRON TIDE", "ransomware", ("TIDE CREW", "IT-2021")),
    ("RUST HALO", "ransomware", ("HALO-9",)),
    ("BLUNT MERCURY", "ransomware", ("MERCURY CREW",)),
    ("HOLLOW ORCHID", "implant", ("ORCHID-11", "Quiet Bloom")),
    ("QUIET FILAMENT", "implant", ("FILAMENT GROUP",)),
    ("VELVET CIPHER", "implant", ("CIPHER-5",)),
    ("ASHEN KITE", "disruption", ("KITE-4", "Ash Flock")),
    ("SCARLET FURROW", "disruption", ("FURROW GROUP",)),
    ("BROKEN COMPASS", "disruption", ("COMPASS-2",)),
    ("COPPER FINCH", "financial", ("FINCH-8", "Copper Crew")),
    ("AMBER TOLL", "financial", ("TOLL GROUP",)),
    ("NIGHT LEDGER", "financial", ("LEDGER-6",)),
)

#: How many of its family's 10 core techniques an actor receives.
CORE_SAMPLE_RANGE = (7, 9)
#: How many extra techniques are drawn from the full vocabulary as noise.
EXTRA_SAMPLE_RANGE = (3, 6)


def technique_catalogue() -> dict[TechniqueId, Technique]:
    """Return the fixture's technique catalogue as :class:`Technique` records."""
    return {
        technique_id: Technique(
            technique_id=technique_id,
            technique_name=name,
            tactics=tuple(tactics.split("|")),
        )
        for technique_id, name, tactics in MOCK_TECHNIQUE_CATALOGUE
    }


def technique_names() -> dict[TechniqueId, str]:
    """``technique_id -> technique_name`` for the fixture vocabulary."""
    return {tid: name for tid, name, _ in MOCK_TECHNIQUE_CATALOGUE}


def generate_mock_actors(seed: int = DEFAULT_SEED) -> list[Actor]:
    """Build the 15 synthetic actors.

    Args:
        seed: RNG seed. The same seed always yields the same fixture.

    Returns:
        Fifteen :class:`~ttp_similarity.schema.Actor` records, each carrying its
        ground-truth family in ``metadata["family"]``.
    """
    rng = random.Random(seed)
    all_ids = [tid for tid, _, _ in MOCK_TECHNIQUE_CATALOGUE]

    actors: list[Actor] = []
    for name, family_id, aliases in MOCK_ACTOR_SEEDS:
        family_label, core = FAMILY_CORES[family_id]

        # Most of the family core, so the family is recoverable by clustering...
        core_count = rng.randint(*CORE_SAMPLE_RANGE)
        chosen = set(rng.sample(list(core), core_count))

        # ...plus commodity techniques almost everyone has (low weight)...
        for technique_id in COMMODITY_TECHNIQUES:
            if rng.random() < 0.85:
                chosen.add(technique_id)

        # ...plus noise, which creates the rare long tail that carries signal.
        extra_count = rng.randint(*EXTRA_SAMPLE_RANGE)
        chosen.update(rng.sample(all_ids, extra_count))

        actors.append(
            Actor(
                actor_id=f"mock--{slugify(name)}",
                name=name,
                aliases=tuple(aliases),
                technique_ids=tuple(sorted(chosen)),
                source="mock",
                metadata={
                    "family": family_id,
                    "family_label": family_label,
                    "synthetic": True,
                    "seed": seed,
                },
            )
        )
    return actors


def ground_truth_frame(actors: Sequence[Actor]) -> pd.DataFrame:
    """Actor-to-family mapping, for scoring the clustering step.

    Args:
        actors: Output of :func:`generate_mock_actors`.

    Returns:
        DataFrame with ``actor_id``, ``actor_name``, ``family``, ``family_label``,
        ``technique_count``.
    """
    return pd.DataFrame(
        [
            {
                "actor_id": actor.actor_id,
                "actor_name": actor.name,
                "family": actor.metadata.get("family", ""),
                "family_label": actor.metadata.get("family_label", ""),
                "technique_count": len(actor.technique_ids),
            }
            for actor in actors
        ]
    )


def build_mock_dataset(
    workspace: paths.Workspace | None = None, seed: int = DEFAULT_SEED
) -> paths.Workspace:
    """Generate the fixture and write the full stage-1 artefact set.

    Writes ``actors.json``, ``actor_technique.csv``, ``techniques.csv``,
    ``technique_frequency.csv`` and ``manifest.json`` into the workspace, plus
    ``data/mock/mock_ground_truth.csv`` for evaluation.

    Args:
        workspace: Target workspace; defaults to the ``mock`` one.
        seed: RNG seed passed to :func:`generate_mock_actors`.

    Returns:
        The workspace that was written.
    """
    workspace = (workspace or paths.Workspace.get(paths.MOCK_DATASET)).ensure()
    paths.ensure_base_dirs()

    actors = generate_mock_actors(seed)
    catalogue = technique_catalogue()
    names = technique_names()

    used_ids = sorted({tid for actor in actors for tid in actor.technique_ids})
    techniques_frame = pd.DataFrame(
        [
            {
                "technique_id": tid,
                "technique_name": catalogue[tid].technique_name,
                "tactics": join_list(catalogue[tid].tactics),
            }
            for tid in used_ids
        ],
        columns=list(TECHNIQUE_COLUMNS),
    )
    edges = frequency_mod.build_actor_technique_frame(actors, names)
    freq = frequency_mod.compute_technique_frequency(actors, names)

    storage.write_actors(actors, workspace.actors)
    storage.write_dataframe(techniques_frame, workspace.techniques, TECHNIQUE_COLUMNS)
    storage.write_dataframe(edges, workspace.actor_technique)
    storage.write_dataframe(freq, workspace.technique_frequency)
    storage.write_dataframe(
        ground_truth_frame(actors), paths.MOCK_DIR / "mock_ground_truth.csv"
    )
    storage.write_manifest(
        BuildManifest(
            dataset=workspace.name,
            source="synthetic",
            attack_version=None,
            built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            actor_count=len(actors),
            technique_count=len(used_ids),
            edge_count=len(edges),
            notes=(
                f"Synthetic fixture, seed={seed}. Actor names are invented and do "
                "not represent real threat groups. Technique ids are real ATT&CK "
                "ids so the vocabulary matches the production build."
            ),
        ),
        workspace.data_manifest,
    )
    return workspace


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m ttp_similarity.data.mock_dataset``."""
    parser = argparse.ArgumentParser(description="Generate the synthetic 15-actor fixture.")
    parser.add_argument("--dataset", default=paths.MOCK_DATASET, help="workspace name")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    config.validate()
    workspace = build_mock_dataset(paths.Workspace.get(args.dataset), seed=args.seed)
    frequency = storage.read_dataframe(workspace.technique_frequency)
    summary = frequency_mod.coverage_summary(frequency)
    print(f"mock dataset written to {workspace.root}")
    print(
        f"  actors=15  techniques={int(summary['techniques'])}  "
        f"singleton_share={summary['singleton_share']:.2f}  "
        f"commodity_share={summary['commodity_share']:.2f}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
