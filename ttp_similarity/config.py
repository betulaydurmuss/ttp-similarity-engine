"""Tunable constants for the whole pipeline.

Every threshold, weight and magic number lives here rather than inside the
module that happens to use it, so that changing a decision is a one-line diff
and shows up in review. The *reasoning* behind each value belongs in
``DECISIONS.md`` -- when you change a number here, update that file too.
"""

from __future__ import annotations

from typing import Final, Mapping

# --------------------------------------------------------------------------- #
# Data source (data module)
# --------------------------------------------------------------------------- #
#: MITRE ATT&CK Enterprise STIX 2.1 bundle. ``ATTACK_RELEASE`` selects the tag;
#: pin it to a release (e.g. ``"v15.1"``) before publishing any numbers, so a
#: result can be reproduced later.
ATTACK_RELEASE: Final[str] = "master"
ATTACK_STIX_URL: Final[str] = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/"
    f"{ATTACK_RELEASE}/enterprise-attack/enterprise-attack.json"
)
DOWNLOAD_TIMEOUT_SECONDS: Final[int] = 120
DOWNLOAD_CHUNK_BYTES: Final[int] = 1 << 20

# --------------------------------------------------------------------------- #
# Normalisation rules (data module)
# --------------------------------------------------------------------------- #
#: Collapse ``T1059.003`` into ``T1059``. Sub-technique coverage in ATT&CK group
#: reporting is uneven, so keeping them would mostly measure reporting depth.
ROLL_UP_SUBTECHNIQUES: Final[bool] = True

#: Drop objects ATT&CK marks as revoked or deprecated.
DROP_REVOKED: Final[bool] = True
DROP_DEPRECATED: Final[bool] = True

#: Actors below this technique count are excluded: their vector is too sparse
#: for a similarity statement to mean anything.
MIN_TECHNIQUES_PER_ACTOR: Final[int] = 5

#: Techniques used by fewer than this many actors carry no comparative signal
#: for actor-vs-actor similarity. ``1`` keeps everything (recommended default:
#: they still matter for query rarity).
MIN_ACTORS_PER_TECHNIQUE: Final[int] = 1

# --------------------------------------------------------------------------- #
# Weighting and vectorisation (engine module)
# --------------------------------------------------------------------------- #
#: ``"smooth_idf"`` -> ``ln((1 + N) / (1 + df)) + 1``  (TF-IDF style, never zero)
#: ``"plain_idf"``  -> ``ln(N / df)``                  (universal techniques -> 0)
#: ``"binary"``     -> all techniques weigh 1          (ablation baseline)
WEIGHTING_SCHEME: Final[str] = "smooth_idf"

#: Additive smoothing applied to both N and df in the IDF formula.
IDF_SMOOTHING: Final[float] = 1.0

#: Term frequency is presence/absence: an actor either uses a technique or not.
#: ATT&CK reports no usage counts, so anything else would be invented signal.
BINARY_TERM_FREQUENCY: Final[bool] = True

#: L2-normalise actor rows so that vector length (i.e. how well-documented an
#: actor is) does not dominate similarity.
NORMALIZE_VECTORS: Final[bool] = True

# --------------------------------------------------------------------------- #
# Similarity and clustering (engine module)
# --------------------------------------------------------------------------- #
#: ``"cosine"`` | ``"jaccard"`` -- cosine is the default; jaccard is kept as an
#: unweighted sanity check.
SIMILARITY_METRIC: Final[str] = "cosine"

#: ``"agglomerative"`` | ``"kmeans"`` | ``"dbscan"``
CLUSTERING_METHOD: Final[str] = "agglomerative"
CLUSTERING_LINKAGE: Final[str] = "average"

#: Merge clusters while cosine *distance* (1 - similarity) stays below this.
#: Used when ``CLUSTERING_N_CLUSTERS`` is None.
CLUSTERING_DISTANCE_THRESHOLD: Final[float] = 0.65

#: Fixed cluster count; ``None`` means "use the distance threshold instead".
CLUSTERING_N_CLUSTERS: Final[int | None] = None

#: Clusters smaller than this are relabelled ``-1`` (unassigned).
MIN_CLUSTER_SIZE: Final[int] = 2

# --------------------------------------------------------------------------- #
# Query mode (engine module)
# --------------------------------------------------------------------------- #
#: How many candidates a query returns.
QUERY_TOP_K: Final[int] = 10

#: Below this many known techniques the engine still answers, but confidence is
#: forced towards LOW by the sufficiency component.
MIN_QUERY_TECHNIQUES: Final[int] = 3

#: Technique count at which the sufficiency component saturates at 1.0.
SUFFICIENCY_SATURATION: Final[int] = 12

#: Candidates scoring below this are dropped from the result entirely.
MIN_CANDIDATE_SCORE: Final[float] = 0.05

#: How many techniques are returned as "what drove this result".
MAX_EVIDENCE_TECHNIQUES: Final[int] = 8

# --------------------------------------------------------------------------- #
# Confidence scoring (engine module)
# --------------------------------------------------------------------------- #
#: Weights of the three confidence components. Must sum to 1.0.
CONFIDENCE_COMPONENT_WEIGHTS: Final[Mapping[str, float]] = {
    "rarity": 0.40,  # how discriminative the matched techniques are
    "margin": 0.35,  # gap between candidate #1 and #2
    "sufficiency": 0.25,  # was there enough input to judge at all
}

#: score >= HIGH -> "high"; >= MEDIUM -> "medium"; otherwise "low".
CONFIDENCE_HIGH_THRESHOLD: Final[float] = 0.70
CONFIDENCE_MEDIUM_THRESHOLD: Final[float] = 0.45

#: Score gap between candidate #1 and #2 at which the margin component hits 1.0.
#: Cosine gaps are small in practice, hence the low ceiling.
MARGIN_SATURATION: Final[float] = 0.15

# --------------------------------------------------------------------------- #
# Evaluation module
# --------------------------------------------------------------------------- #
#: Query sizes swept by the benchmark, to show accuracy vs. input size.
EVAL_SAMPLE_SIZES: Final[tuple[int, ...]] = (3, 5, 8, 12)

#: Random sub-samples drawn per actor per sample size.
EVAL_TRIALS_PER_ACTOR: Final[int] = 10

#: Actors with fewer techniques than the sample size are skipped for that size.
EVAL_RANDOM_SEED: Final[int] = 1337

# --------------------------------------------------------------------------- #
# Presentation
# --------------------------------------------------------------------------- #
#: Shown on every query result, in the UI and in exported reports. The system
#: measures behavioural similarity; it does not attribute activity to anyone.
DISCLAIMER: Final[str] = (
    "Bu sonuc davranissal benzerlik olcumudur, attribution (faillik) iddiasi "
    "degildir. Benzerlik, raporlanmis ATT&CK tekniklerinin ortusmesinden gelir "
    "ve raporlama yanliligindan etkilenir."
)

#: Colormap used by the similarity heatmap.
HEATMAP_COLORMAP: Final[str] = "rocket_r"


def validate() -> None:
    """Fail fast on an inconsistent configuration.

    Called by the pipeline entry points so a bad edit surfaces at startup
    instead of halfway through a build.

    Raises:
        ValueError: If a constant is outside its allowed range.
    """
    total = sum(CONFIDENCE_COMPONENT_WEIGHTS.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"CONFIDENCE_COMPONENT_WEIGHTS must sum to 1.0, got {total}")
    if not 0.0 <= CONFIDENCE_MEDIUM_THRESHOLD <= CONFIDENCE_HIGH_THRESHOLD <= 1.0:
        raise ValueError("confidence thresholds must satisfy 0 <= medium <= high <= 1")
    if WEIGHTING_SCHEME not in {"smooth_idf", "plain_idf", "binary"}:
        raise ValueError(f"unknown WEIGHTING_SCHEME: {WEIGHTING_SCHEME}")
    if SIMILARITY_METRIC not in {"cosine", "jaccard"}:
        raise ValueError(f"unknown SIMILARITY_METRIC: {SIMILARITY_METRIC}")
    if MIN_QUERY_TECHNIQUES < 1:
        raise ValueError("MIN_QUERY_TECHNIQUES must be >= 1")
