"""The shared data model. One definition, used by all four modules.

Anything crossing a module boundary -- on disk or in a function signature -- is
described here. If you need a new field, change it here first and tell the other
two owners; do not invent a parallel dict shape inside your own module.

File contract
-------------
=========================== =========== ======================================
artefact                    format      produced by
=========================== =========== ======================================
``actors.json``             JSON list   data       (:class:`Actor`)
``actor_technique.csv``     CSV         data       (:data:`ACTOR_TECHNIQUE_COLUMNS`)
``techniques.csv``          CSV         data       (:data:`TECHNIQUE_COLUMNS`)
``technique_frequency.csv`` CSV         data       (:data:`TECHNIQUE_FREQUENCY_COLUMNS`)
``manifest.json``           JSON object data       (:class:`BuildManifest`)
``weights.csv``             CSV         engine     (:data:`WEIGHT_COLUMNS`)
``vector_space.npz``        NPZ         engine     (:class:`VectorSpace`)
``similarity.npz``          NPZ         engine     (:class:`SimilarityMatrix`)
``clusters.csv``            CSV         engine     (:data:`CLUSTER_COLUMNS`)
``evaluation.json``         JSON object evaluation (:class:`EvaluationReport`)
=========================== =========== ======================================

Conventions
-----------
* ``technique_id`` is always a **parent** ATT&CK technique id (``"T1059"``).
  Sub-techniques are rolled up by the data module, so ``"T1059.001"`` never
  appears downstream. See ``DECISIONS.md``.
* ``actor_id`` is a stable slug: the ATT&CK group id for real data (``"G0016"``)
  and ``"mock--<slug>"`` for the synthetic fixture.
* List-valued CSV columns (aliases, tactics) are ``|``-separated strings; use
  :func:`join_list` / :func:`split_list` so everyone encodes them identically.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

# --------------------------------------------------------------------------- #
# Primitive aliases -- documentation value only, they are all ``str``.
# --------------------------------------------------------------------------- #
ActorId = str
TechniqueId = str

#: Separator for list-valued fields inside CSV cells.
LIST_SEPARATOR = "|"


def join_list(values: Iterable[str]) -> str:
    """Encode a list of strings into a single CSV cell."""
    return LIST_SEPARATOR.join(v for v in values if v)


def split_list(value: Any) -> tuple[str, ...]:
    """Decode a ``|``-separated CSV cell back into a tuple. NaN/empty -> ``()``."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ()
    text = str(value).strip()
    if not text:
        return ()
    return tuple(part.strip() for part in text.split(LIST_SEPARATOR) if part.strip())


# --------------------------------------------------------------------------- #
# CSV column contracts
# --------------------------------------------------------------------------- #
ACTOR_TECHNIQUE_COLUMNS: tuple[str, ...] = (
    "actor_id",
    "actor_name",
    "technique_id",
    "technique_name",
)
TECHNIQUE_COLUMNS: tuple[str, ...] = (
    "technique_id",
    "technique_name",
    "tactics",  # ``|``-separated ATT&CK tactic shortnames
)
TECHNIQUE_FREQUENCY_COLUMNS: tuple[str, ...] = (
    "technique_id",
    "technique_name",
    "actor_count",  # number of distinct actors using the technique
    "actor_ratio",  # actor_count / total actors, in [0, 1]
)
WEIGHT_COLUMNS: tuple[str, ...] = (
    "technique_id",
    "technique_name",
    "actor_count",
    "weight",  # higher = rarer = more discriminative
)
CLUSTER_COLUMNS: tuple[str, ...] = (
    "actor_id",
    "actor_name",
    "cluster_id",  # -1 means "unassigned / noise"
)
EVALUATION_TRIAL_COLUMNS: tuple[str, ...] = (
    "trial_id",
    "true_actor_id",
    "sample_size",
    "sampled_technique_ids",
    "predicted_actor_id",
    "rank",  # 1-based rank of the true actor, or -1 if outside top-k
    "top1_score",
    "confidence_level",
    "technique_count",  # how many techniques the true actor has in total
    "noise_count",  # injected techniques the true actor does not use
    "confidence_score",  # raw combined score, so thresholds can be re-swept
)


class ConfidenceLevel(str, Enum):
    """Coarse label attached to every query result."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --------------------------------------------------------------------------- #
# Stage 1 -- data module
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Actor:
    """One threat actor with its de-duplicated behavioural footprint.

    Attributes:
        actor_id: Stable identifier (``"G0016"`` / ``"mock--silent-heron"``).
        name: Canonical display name.
        aliases: Other names merged into this identity. Excludes ``name``.
        technique_ids: Sorted, unique, parent-level ATT&CK technique ids.
        source: Provenance tag, e.g. ``"attck"`` or ``"mock"``.
        metadata: Free-form extras (ATT&CK version, mock ground-truth family...).
            Do not rely on a key here across module boundaries.
    """

    actor_id: ActorId
    name: str
    aliases: tuple[str, ...] = ()
    technique_ids: tuple[TechniqueId, ...] = ()
    source: str = "attck"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["aliases"] = list(self.aliases)
        data["technique_ids"] = list(self.technique_ids)
        data["metadata"] = dict(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Actor":
        return cls(
            actor_id=str(data["actor_id"]),
            name=str(data["name"]),
            aliases=tuple(data.get("aliases") or ()),
            technique_ids=tuple(data.get("technique_ids") or ()),
            source=str(data.get("source", "attck")),
            metadata=dict(data.get("metadata") or {}),
        )

    @property
    def all_names(self) -> tuple[str, ...]:
        """Canonical name plus aliases, for free-text lookup in the UI."""
        return (self.name, *self.aliases)


@dataclass(frozen=True)
class Technique:
    """One parent-level ATT&CK technique."""

    technique_id: TechniqueId
    technique_name: str
    tactics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "technique_id": self.technique_id,
            "technique_name": self.technique_name,
            "tactics": list(self.tactics),
        }


@dataclass(frozen=True)
class TechniqueFrequency:
    """How widespread a technique is across the actor population."""

    technique_id: TechniqueId
    technique_name: str
    actor_count: int
    actor_ratio: float


@dataclass(frozen=True)
class BuildManifest:
    """Provenance written next to every dataset build.

    Lets the engine and app report *which* ATT&CK snapshot a similarity number
    came from, and lets the evaluation module refuse to compare runs built from
    different sources.
    """

    dataset: str
    source: str  # "mitre-attack-stix" | "synthetic"
    attack_version: str | None
    built_at: str  # ISO-8601 UTC
    actor_count: int
    technique_count: int
    edge_count: int
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BuildManifest":
        fields = cls.__dataclass_fields__
        return cls(**{key: data.get(key) for key in fields})  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Stage 2 -- engine module
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class VectorSpace:
    """Weighted actor x technique matrix plus its axis labels.

    ``matrix[i, j]`` is the weight of ``technique_ids[j]`` for ``actor_ids[i]``.
    Rows are L2-normalised when :data:`ttp_similarity.config.NORMALIZE_VECTORS`
    is on, which makes a dot product equal to cosine similarity.
    """

    actor_ids: tuple[ActorId, ...]
    technique_ids: tuple[TechniqueId, ...]
    matrix: np.ndarray  # shape (n_actors, n_techniques), float64

    def __post_init__(self) -> None:
        expected = (len(self.actor_ids), len(self.technique_ids))
        if self.matrix.shape != expected:
            raise ValueError(
                f"matrix shape {self.matrix.shape} does not match labels {expected}"
            )

    @property
    def n_actors(self) -> int:
        return len(self.actor_ids)

    @property
    def n_techniques(self) -> int:
        return len(self.technique_ids)

    def actor_index(self) -> dict[ActorId, int]:
        """Map actor id -> row index."""
        return {actor_id: i for i, actor_id in enumerate(self.actor_ids)}

    def technique_index(self) -> dict[TechniqueId, int]:
        """Map technique id -> column index."""
        return {tid: j for j, tid in enumerate(self.technique_ids)}


@dataclass(frozen=True)
class SimilarityMatrix:
    """Symmetric actor x actor similarity, in ``[0, 1]`` for cosine."""

    actor_ids: tuple[ActorId, ...]
    matrix: np.ndarray  # shape (n_actors, n_actors)
    metric: str = "cosine"

    def __post_init__(self) -> None:
        n = len(self.actor_ids)
        if self.matrix.shape != (n, n):
            raise ValueError(f"similarity matrix shape {self.matrix.shape} != ({n}, {n})")


@dataclass(frozen=True)
class TechniqueContribution:
    """Why a candidate scored what it scored -- one technique's share.

    Attributes:
        technique_id: Matched technique.
        technique_name: Human-readable name for the UI.
        weight: The technique's global discriminative weight.
        contribution: This technique's share of the candidate score, in ``[0, 1]``.
            Contributions of all matched techniques sum to 1.
    """

    technique_id: TechniqueId
    technique_name: str
    weight: float
    contribution: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Candidate:
    """One ranked actor in a query result."""

    rank: int  # 1-based
    actor_id: ActorId
    actor_name: str
    score: float  # similarity against the query vector
    matched_technique_ids: tuple[TechniqueId, ...] = ()
    missing_technique_ids: tuple[TechniqueId, ...] = ()  # queried, unused by actor
    evidence: tuple[TechniqueContribution, ...] = ()  # ranked, capped by config

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["matched_technique_ids"] = list(self.matched_technique_ids)
        data["missing_technique_ids"] = list(self.missing_technique_ids)
        data["evidence"] = [e.to_dict() for e in self.evidence]
        return data


@dataclass(frozen=True)
class ConfidenceBreakdown:
    """Three-component confidence score for a query result.

    All components are normalised to ``[0, 1]``; ``score`` is their weighted mean
    using :data:`ttp_similarity.config.CONFIDENCE_COMPONENT_WEIGHTS`, and ``level``
    is the thresholded label. Components are reported individually so the UI can
    explain *why* confidence is low.

    Attributes:
        rarity: How discriminative the matched techniques are. Matching three
            techniques only one actor uses beats matching ten universal ones.
        margin: Separation between the top candidate and the runner-up. A tie
            means the evidence does not distinguish them.
        sufficiency: Whether enough techniques were supplied to judge at all.
        score: Weighted combination of the three, in ``[0, 1]``.
        level: :class:`ConfidenceLevel` derived from ``score``.
    """

    rarity: float
    margin: float
    sufficiency: float
    score: float
    level: ConfidenceLevel

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["level"] = self.level.value
        return data


@dataclass(frozen=True)
class QueryResult:
    """The full answer to "which actors behave like this TTP set?".

    Attributes:
        query_technique_ids: Normalised, de-duplicated input actually scored.
        unknown_technique_ids: Input ids absent from the dataset vocabulary
            (unseen, deprecated, or mistyped). Surfaced, never silently dropped.
        candidates: Ranked actors, best first, capped at ``top_k``.
        confidence: Confidence for the *top* candidate.
        dataset: Workspace the answer came from.
        disclaimer: Constant reminder that this is similarity, not attribution.
    """

    query_technique_ids: tuple[TechniqueId, ...]
    unknown_technique_ids: tuple[TechniqueId, ...]
    candidates: tuple[Candidate, ...]
    confidence: ConfidenceBreakdown
    dataset: str
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_technique_ids": list(self.query_technique_ids),
            "unknown_technique_ids": list(self.unknown_technique_ids),
            "candidates": [c.to_dict() for c in self.candidates],
            "confidence": self.confidence.to_dict(),
            "dataset": self.dataset,
            "disclaimer": self.disclaimer,
        }

    @property
    def top(self) -> Candidate | None:
        """Best candidate, or ``None`` when the query matched nothing."""
        return self.candidates[0] if self.candidates else None


@dataclass(frozen=True)
class EngineArtifacts:
    """Everything the query path and the UI need, loaded once from disk.

    Built by :func:`ttp_similarity.engine.loading.load_engine`. Holding these
    together keeps the app from having to know which file each piece came from.
    """

    dataset: str
    actors: tuple[Actor, ...]
    technique_names: Mapping[TechniqueId, str]
    weights: Mapping[TechniqueId, float]
    space: VectorSpace
    similarity: SimilarityMatrix | None = None
    clusters: Mapping[ActorId, int] | None = None

    def actor_by_id(self) -> dict[ActorId, Actor]:
        return {a.actor_id: a for a in self.actors}


# --------------------------------------------------------------------------- #
# Stage 3 -- evaluation module
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EvaluationTrial:
    """One hold-out query: sample techniques from a known actor, ask the engine."""

    trial_id: int
    true_actor_id: ActorId
    sample_size: int
    sampled_technique_ids: tuple[TechniqueId, ...]
    predicted_actor_id: ActorId | None
    rank: int  # 1-based rank of the true actor; -1 when outside top-k
    top1_score: float
    confidence_level: ConfidenceLevel
    #: Total technique count of the true actor, for the size-vs-accuracy split.
    technique_count: int = 0
    #: Injected techniques the true actor does not use (noisy regimes).
    noise_count: int = 0
    #: Raw combined confidence score. Stored alongside the thresholded level so
    #: a threshold sweep can be run after the fact without re-running trials.
    confidence_score: float = 0.0

    @property
    def is_top1(self) -> bool:
        return self.rank == 1

    @property
    def is_top3(self) -> bool:
        return 1 <= self.rank <= 3

    @property
    def is_top5(self) -> bool:
        return 1 <= self.rank <= 5

    def to_row(self) -> dict[str, Any]:
        """Flatten to one :data:`EVALUATION_TRIAL_COLUMNS` CSV row."""
        return {
            "trial_id": self.trial_id,
            "true_actor_id": self.true_actor_id,
            "sample_size": self.sample_size,
            "sampled_technique_ids": join_list(self.sampled_technique_ids),
            "predicted_actor_id": self.predicted_actor_id or "",
            "rank": self.rank,
            "top1_score": self.top1_score,
            "confidence_level": self.confidence_level.value,
            "technique_count": self.technique_count,
            "noise_count": self.noise_count,
            "confidence_score": self.confidence_score,
        }


@dataclass(frozen=True)
class EvaluationReport:
    """Aggregate benchmark result for one dataset build."""

    dataset: str
    n_trials: int
    sample_sizes: tuple[int, ...]
    top1_accuracy: float
    top3_accuracy: float
    mean_reciprocal_rank: float
    top5_accuracy: float = 0.0
    #: Mean 1-based rank of the true actor. Misses are excluded and counted in
    #: ``miss_count`` instead, because averaging a sentinel would be meaningless.
    mean_rank: float = 0.0
    miss_count: int = 0
    #: Repetitions skipped because the query would have held too few techniques.
    skipped_trials: int = 0
    #: Measurement regime this run belongs to ("A", "B", "C").
    regime: str = ""
    #: Actors in the dataset this run was scored against.
    actor_count: int = 0
    #: Human-readable label for the configuration under test.
    label: str = ""
    #: sample size -> {"top1": float, "top3": float, "mrr": float, "n": int}
    by_sample_size: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    #: confidence level value -> {"top1": float, "share": float, "n": int}
    by_confidence: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    #: technique-count bucket -> {"top1": float, "mrr": float, "n": int}
    by_technique_count: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    seed: int | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sample_sizes"] = list(self.sample_sizes)
        data["by_sample_size"] = {str(k): dict(v) for k, v in self.by_sample_size.items()}
        data["by_confidence"] = {str(k): dict(v) for k, v in self.by_confidence.items()}
        data["by_technique_count"] = {
            str(k): dict(v) for k, v in self.by_technique_count.items()
        }
        return data

    def headline(self) -> dict[str, float]:
        """The five numbers every comparison table is built from."""
        return {
            "top1": self.top1_accuracy,
            "top3": self.top3_accuracy,
            "top5": self.top5_accuracy,
            "mrr": self.mean_reciprocal_rank,
            "mean_rank": self.mean_rank,
        }


# --------------------------------------------------------------------------- #
# Small helpers shared by more than one module
# --------------------------------------------------------------------------- #
def actors_to_edges(actors: Sequence[Actor]) -> list[dict[str, str]]:
    """Explode :class:`Actor` records into ``actor_technique.csv`` rows.

    Technique names are left blank here; the data module fills them in from the
    technique catalogue before writing.
    """
    return [
        {
            "actor_id": actor.actor_id,
            "actor_name": actor.name,
            "technique_id": technique_id,
            "technique_name": "",
        }
        for actor in actors
        for technique_id in actor.technique_ids
    ]
