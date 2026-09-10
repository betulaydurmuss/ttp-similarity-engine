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

Identity comes from ``external_references``, never from the STIX UUID: the UUID
is an internal identifier that is not stable across releases and means nothing
to an analyst, while ``G0016`` / ``T1059`` are the ids on the ATT&CK website.

Sub-technique roll-up and alias merging are **not** done here; they live in
:mod:`ttp_similarity.data.normalize`. Keeping parse and normalise apart means
the normalisation rules can change and be re-run without re-reading 50 MB.

Owner: data module.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .. import config
from ..schema import TechniqueId

#: ATT&CK's own source name inside ``external_references``.
ATTACK_SOURCE_NAME = "mitre-attack"

#: The kill chain whose phases are ATT&CK tactics.
ATTACK_KILL_CHAIN = "mitre-attack"


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

    Revoked and deprecated objects have already been dropped (see
    :data:`ttp_similarity.config.DROP_REVOKED` / ``DROP_DEPRECATED``); how many
    were dropped is recorded in :attr:`stats`, so the build can report it.

    Attributes:
        actors: ``stix_id -> RawActor``.
        techniques: ``stix_id -> RawTechnique``.
        uses: Actor-to-technique edges as ``(actor_stix_id, technique_stix_id)``.
        attack_version: ATT&CK release string, when the bundle declares one.
        stats: Counts collected while parsing.
    """

    actors: Mapping[str, RawActor] = field(default_factory=dict)
    techniques: Mapping[str, RawTechnique] = field(default_factory=dict)
    uses: tuple[tuple[str, str], ...] = ()
    attack_version: str | None = None
    stats: Mapping[str, int] = field(default_factory=dict)

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
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    if payload.get("type") != "bundle":
        raise ValueError(
            f"{bundle_path} is not a STIX bundle (type={payload.get('type')!r})"
        )
    return list(payload.get("objects", []))


def extract_attack_id(stix_object: Mapping[str, Any]) -> str | None:
    """Return the ATT&CK external id (``G0016`` / ``T1059``) of an object.

    Looks through ``external_references`` for the entry whose ``source_name``
    is ``"mitre-attack"`` and returns its ``external_id``.

    Args:
        stix_object: Any STIX object.

    Returns:
        The ATT&CK id, or ``None`` when the object has no ATT&CK reference
        (a few imported objects have none, and those are skipped).
    """
    for reference in stix_object.get("external_references", []) or []:
        if reference.get("source_name") == ATTACK_SOURCE_NAME:
            external_id = reference.get("external_id")
            if external_id:
                return str(external_id).strip()
    return None


def _is_revoked(stix_object: Mapping[str, Any]) -> bool:
    return bool(stix_object.get("revoked", False))


def _is_deprecated(stix_object: Mapping[str, Any]) -> bool:
    return bool(stix_object.get("x_mitre_deprecated", False))


def _extract_tactics(stix_object: Mapping[str, Any]) -> tuple[str, ...]:
    """Tactic shortnames from the ATT&CK kill chain phases."""
    return tuple(
        str(phase.get("phase_name"))
        for phase in stix_object.get("kill_chain_phases", []) or []
        if phase.get("kill_chain_name") == ATTACK_KILL_CHAIN and phase.get("phase_name")
    )


def _clean_aliases(name: str, aliases: Iterable[Any]) -> tuple[str, ...]:
    """Normalise an intrusion-set's alias list.

    ATT&CK repeats the canonical name as the first alias; that repetition is
    dropped here so ``Actor.aliases`` really means "other names". Order is
    preserved (ATT&CK lists them roughly by prominence) while de-duplicating
    case-insensitively.
    """
    seen = {name.strip().casefold()}
    cleaned: list[str] = []
    for alias in aliases or []:
        text = str(alias).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return tuple(cleaned)


def parse_actors(objects: Iterable[Mapping[str, Any]]) -> dict[str, RawActor]:
    """Collect ``intrusion-set`` objects into :class:`RawActor` records.

    Args:
        objects: STIX objects from the bundle.

    Returns:
        ``stix_id -> RawActor``, including revoked/deprecated ones -- they are
        filtered in :func:`parse_bundle` so that the count can be reported.
    """
    actors: dict[str, RawActor] = {}
    for item in objects:
        if item.get("type") != "intrusion-set":
            continue
        attack_id = extract_attack_id(item)
        if not attack_id:
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        actors[str(item["id"])] = RawActor(
            stix_id=str(item["id"]),
            attack_id=attack_id,
            name=name,
            aliases=_clean_aliases(name, item.get("aliases")),
            revoked=_is_revoked(item),
            deprecated=_is_deprecated(item),
        )
    return actors


def parse_techniques(objects: Iterable[Mapping[str, Any]]) -> dict[str, RawTechnique]:
    """Collect ``attack-pattern`` objects into :class:`RawTechnique` records.

    Args:
        objects: STIX objects from the bundle.

    Returns:
        ``stix_id -> RawTechnique``, including revoked/deprecated ones.
    """
    techniques: dict[str, RawTechnique] = {}
    for item in objects:
        if item.get("type") != "attack-pattern":
            continue
        attack_id = extract_attack_id(item)
        if not attack_id:
            continue
        techniques[str(item["id"])] = RawTechnique(
            stix_id=str(item["id"]),
            attack_id=attack_id,
            name=str(item.get("name", attack_id)).strip(),
            tactics=_extract_tactics(item),
            is_subtechnique=bool(item.get("x_mitre_is_subtechnique", False)),
            revoked=_is_revoked(item),
            deprecated=_is_deprecated(item),
        )
    return techniques


def parse_uses_relationships(
    objects: Iterable[Mapping[str, Any]],
    actor_ids: Iterable[str],
    technique_ids: Iterable[str],
) -> tuple[tuple[str, str], ...]:
    """Collect actor-to-technique ``uses`` edges.

    Only direct ``intrusion-set -> attack-pattern`` edges are kept. Edges whose
    source or target is not in the given id sets are dropped, which removes
    actor->malware, malware->technique and tool->technique relationships as well
    as any edge pointing at a revoked object. Indirect
    ``actor -> malware -> technique`` paths are deliberately not followed; see
    ``DECISIONS.md`` section 2.3.

    Args:
        objects: STIX objects from the bundle.
        actor_ids: Known intrusion-set STIX ids (to filter ``source_ref``).
        technique_ids: Known attack-pattern STIX ids (to filter ``target_ref``).

    Returns:
        De-duplicated ``(actor_stix_id, technique_stix_id)`` pairs, sorted.
    """
    actor_id_set = set(actor_ids)
    technique_id_set = set(technique_ids)
    edges: set[tuple[str, str]] = set()
    for item in objects:
        if item.get("type") != "relationship":
            continue
        if item.get("relationship_type") != "uses":
            continue
        if _is_revoked(item) or _is_deprecated(item):
            continue
        source = str(item.get("source_ref", ""))
        target = str(item.get("target_ref", ""))
        if source in actor_id_set and target in technique_id_set:
            edges.add((source, target))
    return tuple(sorted(edges))


def extract_attack_version(objects: Iterable[Mapping[str, Any]]) -> str | None:
    """ATT&CK release version from the bundle's ``x-mitre-collection`` object."""
    for item in objects:
        if item.get("type") == "x-mitre-collection":
            version = item.get("x_mitre_version")
            if version:
                return str(version)
    return None


def parse_bundle(bundle_path: Path) -> ParsedBundle:
    """Parse the whole bundle in one pass.

    Revoked and deprecated actors and techniques are removed here (subject to
    :data:`ttp_similarity.config.DROP_REVOKED` / ``DROP_DEPRECATED``), and the
    number removed is recorded in :attr:`ParsedBundle.stats`.

    Args:
        bundle_path: Path to ``enterprise-attack.json``.

    Returns:
        A :class:`ParsedBundle` ready for :mod:`ttp_similarity.data.normalize`.
    """
    objects = load_bundle_objects(bundle_path)
    counts: Counter[str] = Counter()
    counts["stix_objects"] = len(objects)

    all_actors = parse_actors(objects)
    all_techniques = parse_techniques(objects)
    counts["intrusion_sets_total"] = len(all_actors)
    counts["attack_patterns_total"] = len(all_techniques)

    def keep(record: RawActor | RawTechnique) -> bool:
        if config.DROP_REVOKED and record.revoked:
            return False
        if config.DROP_DEPRECATED and record.deprecated:
            return False
        return True

    actors = {sid: rec for sid, rec in all_actors.items() if keep(rec)}
    techniques = {sid: rec for sid, rec in all_techniques.items() if keep(rec)}

    counts["actors_revoked"] = sum(1 for r in all_actors.values() if r.revoked)
    counts["actors_deprecated"] = sum(
        1 for r in all_actors.values() if r.deprecated and not r.revoked
    )
    counts["techniques_revoked"] = sum(1 for r in all_techniques.values() if r.revoked)
    counts["techniques_deprecated"] = sum(
        1 for r in all_techniques.values() if r.deprecated and not r.revoked
    )
    counts["actors_dropped"] = len(all_actors) - len(actors)
    counts["techniques_dropped"] = len(all_techniques) - len(techniques)
    counts["actors_kept"] = len(actors)
    counts["techniques_kept"] = len(techniques)
    counts["subtechniques_kept"] = sum(
        1 for r in techniques.values() if r.is_subtechnique
    )

    # Edges are resolved against the *kept* objects, so an edge pointing at a
    # revoked technique disappears with it rather than dangling.
    uses = parse_uses_relationships(objects, actors.keys(), techniques.keys())
    counts["uses_edges"] = len(uses)

    return ParsedBundle(
        actors=actors,
        techniques=techniques,
        uses=uses,
        attack_version=extract_attack_version(objects),
        stats=dict(counts),
    )
