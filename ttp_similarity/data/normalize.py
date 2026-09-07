"""Turn a parsed STIX bundle into the canonical actor/technique model.

Four normalisation steps, in order:

1. **Sub-technique roll-up** -- ``T1059.003`` becomes ``T1059``. ATT&CK group
   pages document sub-techniques very unevenly, so keeping them would measure
   how thoroughly a group was written up rather than how it behaves.
2. **Alias merging** -- one actor, one identity. Groups that share an alias are
   merged and their technique sets unioned.
3. **Filtering** -- revoked/deprecated objects and actors below
   :data:`ttp_similarity.config.MIN_TECHNIQUES_PER_ACTOR` techniques are dropped.
4. **Sorting** -- ids sorted so every build is byte-identical for the same input.

Only :func:`roll_up_technique_id` and the small helpers below are implemented;
they are pure functions the other modules and the mock fixture also rely on.

Owner: data module.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Mapping, Sequence

from .. import config
from ..schema import Actor, Technique, TechniqueId
from .stix_parse import ParsedBundle, RawActor, RawTechnique

#: ``T1059`` or ``T1059.003``.
TECHNIQUE_ID_PATTERN = re.compile(r"^T\d{4}(?:\.\d{3})?$")


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


def build_technique_catalogue(
    raw_techniques: Mapping[str, RawTechnique],
) -> dict[TechniqueId, Technique]:
    """Reduce raw attack-patterns to the parent-level technique catalogue.

    Args:
        raw_techniques: ``stix_id -> RawTechnique`` from the parser.

    Returns:
        ``technique_id -> Technique`` containing parent techniques only, with
        tactics unioned across the parent and its sub-techniques.
    """
    # TODO(data): skip revoked/deprecated when config says so; roll each id up;
    #   prefer the parent object's own name when it exists, otherwise derive one;
    #   union the tactic lists.
    raise NotImplementedError("build_technique_catalogue")


def merge_alias_groups(raw_actors: Iterable[RawActor]) -> list[tuple[RawActor, ...]]:
    """Group intrusion-sets that refer to the same actor.

    ATT&CK already merges most vendor names into a single intrusion-set via its
    ``aliases`` field, but duplicates still appear across releases. Two records
    belong together when any of their :func:`slugify`-ed names or aliases match.

    Args:
        raw_actors: Parsed intrusion-sets.

    Returns:
        Groups of records to merge, each a tuple of one or more raw actors.
    """
    # TODO(data): union-find over slugified name+alias tokens.
    # TODO(data): guard against over-merging on generic aliases -- maintain an
    #   ALIAS_STOPLIST for tokens like "unc", "ta", "group" that would chain
    #   unrelated actors together. Log every merge so it can be reviewed.
    raise NotImplementedError("merge_alias_groups")


def normalize_bundle(
    bundle: ParsedBundle,
) -> tuple[list[Actor], dict[TechniqueId, Technique]]:
    """Run the full normalisation pipeline over a parsed bundle.

    Args:
        bundle: Output of :func:`ttp_similarity.data.stix_parse.parse_bundle`.

    Returns:
        ``(actors, technique_catalogue)`` -- the canonical model, with actor
        ids set to the ATT&CK group id and technique ids rolled up to parents.
    """
    # TODO(data): catalogue = build_technique_catalogue(bundle.techniques)
    # TODO(data): map uses-edges from STIX ids to (actor_id, technique_id)
    # TODO(data): merge_alias_groups(...) -> pick the canonical name (the record
    #   with the lowest ATT&CK group id), union aliases and technique sets
    # TODO(data): drop actors below config.MIN_TECHNIQUES_PER_ACTOR
    # TODO(data): stash attack_version in each Actor.metadata
    raise NotImplementedError("normalize_bundle")


def filter_sparse_actors(
    actors: Sequence[Actor], min_techniques: int = config.MIN_TECHNIQUES_PER_ACTOR
) -> list[Actor]:
    """Drop actors whose technique set is too small to compare meaningfully.

    Args:
        actors: Candidate actors.
        min_techniques: Inclusive lower bound on technique count.

    Returns:
        The actors that clear the bar, order preserved.
    """
    return [actor for actor in actors if len(actor.technique_ids) >= min_techniques]
