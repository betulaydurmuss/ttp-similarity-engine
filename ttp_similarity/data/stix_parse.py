"""Extract intrusion-sets, attack-patterns and their ``uses`` relationships.

Only three STIX object types matter for this project:

``intrusion-set``
    A tracked threat actor. Carries ``name``, ``aliases`` and an external
    reference with ``source_name == "mitre-attack"`` whose ``external_id`` is the
    ATT&CK group id (``G0016``) -- that id becomes our ``actor_id``.

``attack-pattern``
    A technique or sub-technique. Its ``external_id`` is ``T1059`` /
    ``T1059.003``; ``kill_chain_phases`` carry the tactic shortnames.

``relationship`` with ``relationship_type == "uses"``
    The edge. ``source_ref`` points at an intrusion-set, ``target_ref`` at an
    attack-pattern. Relationships also target malware and tools, which are
    dropped here -- this project models actor behaviour, not tooling.

Nothing is normalised in this module: sub-technique roll-up, alias merging and
filtering all happen in :mod:`ttp_similarity.data.normalize`. Keeping parse and
normalise apart means the normalisation rules can be changed and re-run without
re-reading a 40 MB bundle.

Owner: data module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..schema import TechniqueId


@dataclass(frozen=True)
class RawActor:
    """An ``intrusion-set`` as it appears in the bundle, before normalisation."""

    stix_id: str  # "intrusion-set--<uuid>"
    attack_id: str  # "G0016"
    name: str
    aliases: tuple[str, ...]
    revoked: bool = False
    deprecated: bool = False


@dataclass(frozen=True)
class RawTechnique:
    """An ``attack-pattern`` as it appears in the bundle, before roll-up."""

    stix_id: str  # "attack-pattern--<uuid>"
    attack_id: TechniqueId  # "T1059" or "T1059.003"
    name: str
    tactics: tuple[str, ...] = ()
    is_subtechnique: bool = False
    revoked: bool = False
    deprecated: bool = False


@dataclass(frozen=True)
class ParsedBundle:
    """Everything the normaliser needs, keyed by STIX id.

    Attributes:
        actors: ``stix_id -> RawActor``.
        techniques: ``stix_id -> RawTechnique``.
        uses: Actor-to-technique edges as ``(actor_stix_id, technique_stix_id)``.
        attack_version: ATT&CK release string, when the bundle declares one.
    """

    actors: Mapping[str, RawActor] = field(default_factory=dict)
    techniques: Mapping[str, RawTechnique] = field(default_factory=dict)
    uses: tuple[tuple[str, str], ...] = ()
    attack_version: str | None = None

    def summary(self) -> str:
        """One-line count summary, for build logs."""
        return (
            f"{len(self.actors)} intrusion-sets, {len(self.techniques)} attack-patterns, "
            f"{len(self.uses)} uses-edges"
        )


def load_bundle_objects(bundle_path: Path) -> list[dict[str, Any]]:
    """Read the STIX bundle and return its ``objects`` array.

    Args:
        bundle_path: Path to ``enterprise-attack.json``.

    Returns:
        The raw STIX object dictionaries.

    Raises:
        ValueError: If the file is not a STIX bundle.
    """
    # TODO(data): json.loads(bundle_path.read_text(encoding="utf-8")); check
    #   payload.get("type") == "bundle"; return payload["objects"].
    raise NotImplementedError("load_bundle_objects")


def extract_attack_id(stix_object: Mapping[str, Any]) -> str | None:
    """Return the ATT&CK external id (``G0016`` / ``T1059``) of an object.

    Looks through ``external_references`` for the entry whose ``source_name``
    is ``"mitre-attack"`` and returns its ``external_id``.

    Args:
        stix_object: Any STIX object.

    Returns:
        The ATT&CK id, or ``None`` when the object has no ATT&CK reference
        (which happens for a few imported objects and means "skip it").
    """
    # TODO(data): iterate stix_object.get("external_references", []).
    raise NotImplementedError("extract_attack_id")


def parse_actors(objects: Iterable[Mapping[str, Any]]) -> dict[str, RawActor]:
    """Collect ``intrusion-set`` objects into :class:`RawActor` records.

    Args:
        objects: STIX objects from the bundle.

    Returns:
        ``stix_id -> RawActor``, including revoked/deprecated ones; filtering is
        the normaliser's job so that counts can be reported.
    """
    # TODO(data): filter type == "intrusion-set"; read name, aliases
    #   (ATT&CK repeats the canonical name as aliases[0] -- drop it),
    #   revoked and x_mitre_deprecated flags.
    raise NotImplementedError("parse_actors")


def parse_techniques(objects: Iterable[Mapping[str, Any]]) -> dict[str, RawTechnique]:
    """Collect ``attack-pattern`` objects into :class:`RawTechnique` records.

    Args:
        objects: STIX objects from the bundle.

    Returns:
        ``stix_id -> RawTechnique``.
    """
    # TODO(data): filter type == "attack-pattern"; take x_mitre_is_subtechnique,
    #   and tactics from [p["phase_name"] for p in kill_chain_phases
    #   if p["kill_chain_name"] == "mitre-attack"].
    raise NotImplementedError("parse_techniques")


def parse_uses_relationships(
    objects: Iterable[Mapping[str, Any]],
    actor_ids: Iterable[str],
    technique_ids: Iterable[str],
) -> tuple[tuple[str, str], ...]:
    """Collect actor-to-technique ``uses`` edges.

    Args:
        objects: STIX objects from the bundle.
        actor_ids: Known intrusion-set STIX ids (to filter ``source_ref``).
        technique_ids: Known attack-pattern STIX ids (to filter ``target_ref``).

    Returns:
        De-duplicated ``(actor_stix_id, technique_stix_id)`` pairs.
    """
    # TODO(data): filter type == "relationship" and relationship_type == "uses";
    #   keep only edges whose source is an intrusion-set and target an
    #   attack-pattern (this drops actor->malware and malware->technique edges).
    # TODO(data): decide whether to also fold in indirect
    #   actor -> malware -> technique edges. Default answer is NO; record the
    #   choice in DECISIONS.md if it changes.
    raise NotImplementedError("parse_uses_relationships")


def parse_bundle(bundle_path: Path) -> ParsedBundle:
    """Parse the whole bundle in one pass.

    Args:
        bundle_path: Path to ``enterprise-attack.json``.

    Returns:
        A :class:`ParsedBundle` ready for :mod:`ttp_similarity.data.normalize`.
    """
    # TODO(data): objects = load_bundle_objects(bundle_path); call the three
    #   parsers; pull attack_version from the x-mitre-collection object.
    raise NotImplementedError("parse_bundle")
