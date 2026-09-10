"""Turn a parsed STIX bundle into the canonical actor/technique model.

Four normalisation steps, in order:

1. **Sub-technique roll-up** -- ``T1059.003`` becomes ``T1059``. ATT&CK group
   pages document sub-techniques very unevenly, so keeping them would measure
   how thoroughly a group was written up rather than how it behaves.
2. **Alias merging** -- one actor, one identity. Groups that share an alias are
   merged and their technique sets unioned.
3. **Filtering** -- actors below
   :data:`ttp_similarity.config.MIN_TECHNIQUES_PER_ACTOR` techniques are dropped.
   (Revoked/deprecated objects are already gone; see :mod:`.stix_parse`.)
4. **Sorting** -- ids sorted so every build is byte-identical for the same input.

Owner: data module.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .. import config
from ..schema import Actor, Technique, TechniqueId
from .stix_parse import ParsedBundle, RawActor, RawTechnique

#: ``T1059`` or ``T1059.003``.
TECHNIQUE_ID_PATTERN = re.compile(r"^T\d{4}(?:\.\d{3})?$")

#: Alias tokens too generic to prove two records are the same actor. Merging on
#: these would chain unrelated groups together through a shared vendor prefix
#: ("TA", "UNC") or a shared common word. Slugified form, compared exactly.
ALIAS_STOPLIST: frozenset[str] = frozenset(
    {
        "apt",
        "ta",
        "unc",
        "group",
        "team",
        "crew",
        "gang",
        "actor",
        "threat",
        "cluster",
        "operation",
        "campaign",
        "unknown",
        "unattributed",
        "g",
    }
)

#: Aliases shorter than this (after slugifying) are ignored when merging: two
#: letters are far more likely to collide by accident than to identify a group.
MIN_ALIAS_LENGTH = 3


@dataclass(frozen=True)
class ActorMerge:
    """One alias-based merge, recorded so it can be reviewed.

    Attributes:
        canonical_id: ATT&CK group id kept as the identity.
        canonical_name: Display name kept.
        merged_ids: All ATT&CK group ids folded into this identity.
        merged_names: Their names, in the same order.
        shared_aliases: The alias tokens that caused the merge.
    """

    canonical_id: str
    canonical_name: str
    merged_ids: tuple[str, ...]
    merged_names: tuple[str, ...]
    shared_aliases: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "canonical_name": self.canonical_name,
            "merged_ids": list(self.merged_ids),
            "merged_names": list(self.merged_names),
            "shared_aliases": list(self.shared_aliases),
        }


@dataclass(frozen=True)
class NormalizationResult:
    """Output of :func:`normalize_bundle`.

    Attributes:
        actors: Canonical actor records, sorted by ``actor_id``.
        techniques: ``technique_id -> Technique`` parent-level catalogue.
        merges: Alias merges that actually happened (empty when none did).
        stats: Counts for the build report.
    """

    actors: list[Actor] = field(default_factory=list)
    techniques: dict[TechniqueId, Technique] = field(default_factory=dict)
    merges: tuple[ActorMerge, ...] = ()
    stats: Mapping[str, Any] = field(default_factory=dict)


def is_technique_id(value: str) -> bool:
    """True when ``value`` looks like an ATT&CK technique id."""
    return bool(TECHNIQUE_ID_PATTERN.match(value.strip().upper()))


def roll_up_technique_id(technique_id: str) -> TechniqueId:
    """Collapse a sub-technique id onto its parent.

    ``"T1059.003"`` -> ``"T1059"``; ``"T1059"`` is returned unchanged. Input is
    upper-cased and stripped, so user input from the UI can be passed straight in.

    Args:
        technique_id: ATT&CK technique or sub-technique id.

    Returns:
        The parent-level technique id.
    """
    normalized = technique_id.strip().upper()
    if not config.ROLL_UP_SUBTECHNIQUES:
        return normalized
    return normalized.split(".", 1)[0]


def normalize_technique_ids(technique_ids: Iterable[str]) -> tuple[TechniqueId, ...]:
    """Roll up, de-duplicate and sort a collection of technique ids.

    Invalid-looking entries are kept as-is (upper-cased) rather than silently
    dropped -- the query path reports them as unknown so the user sees a typo.

    Args:
        technique_ids: Raw ids, possibly with sub-techniques and duplicates.

    Returns:
        Sorted unique parent-level ids.
    """
    return tuple(sorted({roll_up_technique_id(t) for t in technique_ids if str(t).strip()}))


def slugify(value: str) -> str:
    """ASCII, lower-case, hyphen-separated form of ``value``.

    Used to build stable ids for the synthetic dataset and to compare aliases
    that differ only in punctuation or case (``"APT 29"`` vs ``"APT-29"``).
    """
    ascii_form = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_form.lower()).strip("-")


def alias_key(value: str) -> str | None:
    """Comparable key for an alias, or ``None`` when it is not usable for merging.

    Rejects stoplisted and very short tokens, which would otherwise chain
    unrelated actors into one identity.
    """
    slug = slugify(value)
    if not slug or len(slug) < MIN_ALIAS_LENGTH:
        return None
    if slug in ALIAS_STOPLIST:
        return None
    return slug


def build_technique_catalogue(
    raw_techniques: Mapping[str, RawTechnique],
) -> dict[TechniqueId, Technique]:
    """Reduce raw attack-patterns to the parent-level technique catalogue.

    Sub-techniques are folded into their parent: the parent's own name is kept
    when the parent object exists in the bundle, and tactics are unioned across
    the parent and all of its sub-techniques (a sub-technique occasionally sits
    under a tactic the parent does not list).

    Args:
        raw_techniques: ``stix_id -> RawTechnique`` from the parser.

    Returns:
        ``technique_id -> Technique`` containing parent techniques only.
    """
    names: dict[TechniqueId, str] = {}
    tactics: dict[TechniqueId, list[str]] = defaultdict(list)

    for record in raw_techniques.values():
        parent_id = roll_up_technique_id(record.attack_id)
        # A parent object's own name wins; a sub-technique only supplies a
        # fallback name for the case where the parent is absent from the bundle.
        if not record.is_subtechnique or parent_id not in names:
            if not record.is_subtechnique:
                names[parent_id] = record.name
            else:
                names.setdefault(parent_id, record.name)
        for tactic in record.tactics:
            if tactic not in tactics[parent_id]:
                tactics[parent_id].append(tactic)

    return {
        technique_id: Technique(
            technique_id=technique_id,
            technique_name=names.get(technique_id, technique_id),
            tactics=tuple(tactics.get(technique_id, ())),
        )
        for technique_id in sorted(names)
    }


def merge_alias_groups(raw_actors: Iterable[RawActor]) -> list[tuple[RawActor, ...]]:
    """Group intrusion-sets that refer to the same actor.

    ATT&CK already merges most vendor names into a single intrusion-set via its
    ``aliases`` field, but duplicates still appear across releases. Two records
    belong together when any of their usable alias keys (see :func:`alias_key`)
    match. Implemented as union-find over those keys.

    Args:
        raw_actors: Parsed intrusion-sets.

    Returns:
        Groups of records to merge, each a tuple of one or more raw actors,
        ordered by the group's lowest ATT&CK id so the result is deterministic.
    """
    actors = sorted(raw_actors, key=lambda a: a.attack_id)
    parent: dict[str, str] = {actor.attack_id: actor.attack_id for actor in actors}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        # Lowest ATT&CK id wins, so the canonical identity is stable.
        if left_root <= right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    by_key: dict[str, list[str]] = defaultdict(list)
    for actor in actors:
        for candidate in (actor.name, *actor.aliases):
            key = alias_key(candidate)
            if key and actor.attack_id not in by_key[key]:
                by_key[key].append(actor.attack_id)

    for attack_ids in by_key.values():
        for other in attack_ids[1:]:
            union(attack_ids[0], other)

    grouped: dict[str, list[RawActor]] = defaultdict(list)
    for actor in actors:
        grouped[find(actor.attack_id)].append(actor)

    return [tuple(group) for _, group in sorted(grouped.items())]


def _shared_alias_keys(group: Sequence[RawActor]) -> tuple[str, ...]:
    """Alias keys that appear in more than one member of a merged group."""
    counts: dict[str, int] = defaultdict(int)
    for actor in group:
        seen = {
            key
            for key in (alias_key(n) for n in (actor.name, *actor.aliases))
            if key
        }
        for key in seen:
            counts[key] += 1
    return tuple(sorted(key for key, count in counts.items() if count > 1))


def normalize_bundle(
    bundle: ParsedBundle, *, min_techniques: int | None = None
) -> NormalizationResult:
    """Run the full normalisation pipeline over a parsed bundle.

    Args:
        bundle: Output of :func:`ttp_similarity.data.stix_parse.parse_bundle`.
        min_techniques: Sparse-actor threshold. ``None`` reads
            :data:`ttp_similarity.config.MIN_TECHNIQUES_PER_ACTOR` *at call time*,
            so changing the config actually takes effect (a default argument
            would freeze the value at import).

    Returns:
        A :class:`NormalizationResult`: canonical actors (ATT&CK group id as
        ``actor_id``, parent-level technique ids), the technique catalogue, the
        alias merges that happened, and counts for the build report.
    """
    threshold = (
        config.MIN_TECHNIQUES_PER_ACTOR if min_techniques is None else min_techniques
    )
    catalogue = build_technique_catalogue(bundle.techniques)

    # STIX-id edges -> (attack group id, raw technique id), then rolled up.
    edges_raw: set[tuple[str, str]] = set()
    edges_rolled: set[tuple[str, str]] = set()
    for actor_stix_id, technique_stix_id in bundle.uses:
        actor = bundle.actors[actor_stix_id]
        technique = bundle.techniques[technique_stix_id]
        edges_raw.add((actor.attack_id, technique.attack_id))
        edges_rolled.add((actor.attack_id, roll_up_technique_id(technique.attack_id)))

    techniques_by_actor: dict[str, set[str]] = defaultdict(set)
    for attack_id, technique_id in edges_rolled:
        techniques_by_actor[attack_id].add(technique_id)

    groups = merge_alias_groups(bundle.actors.values())
    merges: list[ActorMerge] = []
    actors: list[Actor] = []

    for group in groups:
        # The lowest ATT&CK id is the canonical identity: stable across releases
        # and independent of parse order.
        canonical = min(group, key=lambda a: a.attack_id)
        technique_ids: set[str] = set()
        aliases: list[str] = []
        seen_aliases = {canonical.name.casefold()}
        for member in group:
            technique_ids |= techniques_by_actor.get(member.attack_id, set())
            for candidate in (member.name, *member.aliases):
                text = candidate.strip()
                if not text or text.casefold() in seen_aliases:
                    continue
                seen_aliases.add(text.casefold())
                aliases.append(text)

        if len(group) > 1:
            merges.append(
                ActorMerge(
                    canonical_id=canonical.attack_id,
                    canonical_name=canonical.name,
                    merged_ids=tuple(a.attack_id for a in group),
                    merged_names=tuple(a.name for a in group),
                    shared_aliases=_shared_alias_keys(group),
                )
            )

        actors.append(
            Actor(
                actor_id=canonical.attack_id,
                name=canonical.name,
                aliases=tuple(aliases),
                technique_ids=tuple(sorted(technique_ids)),
                source="attck",
                metadata={
                    "attack_version": bundle.attack_version,
                    "stix_id": canonical.stix_id,
                    "merged_attack_ids": [a.attack_id for a in group],
                },
            )
        )

    actors.sort(key=lambda a: a.actor_id)
    kept = filter_sparse_actors(actors, threshold)

    stats: dict[str, Any] = dict(bundle.stats)
    stats.update(
        {
            "attack_version": bundle.attack_version,
            "edges_before_rollup": len(edges_raw),
            "edges_after_rollup": len(edges_rolled),
            "edges_deduplicated_by_rollup": len(edges_raw) - len(edges_rolled),
            "techniques_before_rollup": len(bundle.techniques),
            "techniques_after_rollup": len(catalogue),
            "actors_before_alias_merge": len(bundle.actors),
            "actors_after_alias_merge": len(actors),
            "alias_merge_count": len(merges),
            "actors_dropped_sparse": len(actors) - len(kept),
            "min_techniques_per_actor": threshold,
            "actors_final": len(kept),
        }
    )

    # The catalogue is trimmed to what the surviving actors actually use, so
    # techniques.csv and technique_frequency.csv describe the same vocabulary.
    used = {tid for actor in kept for tid in actor.technique_ids}
    techniques = {tid: catalogue[tid] for tid in sorted(used) if tid in catalogue}
    stats["techniques_final"] = len(techniques)
    stats["edges_final"] = sum(len(a.technique_ids) for a in kept)

    return NormalizationResult(
        actors=kept,
        techniques=techniques,
        merges=tuple(merges),
        stats=stats,
    )


def filter_sparse_actors(
    actors: Sequence[Actor], min_techniques: int | None = None
) -> list[Actor]:
    """Drop actors whose technique set is too small to compare meaningfully.

    Args:
        actors: Candidate actors.
        min_techniques: Inclusive lower bound on technique count. ``None`` reads
            the config value at call time rather than at import time.

    Returns:
        The actors that clear the bar, order preserved.
    """
    threshold = (
        config.MIN_TECHNIQUES_PER_ACTOR if min_techniques is None else min_techniques
    )
    return [actor for actor in actors if len(actor.technique_ids) >= threshold]
