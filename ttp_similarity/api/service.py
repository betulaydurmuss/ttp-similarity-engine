"""The station: everything the interface reads, assembled once per dataset.

The API layer is thin on purpose. Every number shown in the interface is
computed by the engine; this module only gathers the engine's artefacts into
the shapes the interface draws (the map, the technique matrix, the dossier)
and never scores anything itself.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .. import config, paths, storage
from ..data.normalize import normalize_technique_ids
from ..engine import clustering, confidence as confidence_mod, layout as layout_mod
from ..engine import loading, query as query_mod, similarity as similarity_mod, weighting
from ..evaluation import sampling
from ..schema import Actor, EngineArtifacts, QueryResult, split_list

TACTIC_ORDER: tuple[tuple[str, str, str], ...] = (
    ("reconnaissance", "Ön Keşif", "Reconnaissance"),
    ("resource-development", "Kaynak Geliştirme", "Resource Development"),
    ("initial-access", "İlk Erişim", "Initial Access"),
    ("execution", "Yürütme", "Execution"),
    ("persistence", "Kalıcılık", "Persistence"),
    ("privilege-escalation", "Yetki Yükseltme", "Privilege Escalation"),
    ("defense-evasion", "Savunmadan Kaçınma", "Defense Evasion"),
    ("stealth", "Gizlenme", "Stealth"),
    ("defense-impairment", "Savunmayı Bozma", "Defense Impairment"),
    ("credential-access", "Kimlik Bilgisi Erişimi", "Credential Access"),
    ("discovery", "Keşif", "Discovery"),
    ("lateral-movement", "Yanal Hareket", "Lateral Movement"),
    ("collection", "Toplama", "Collection"),
    ("command-and-control", "Komuta ve Kontrol", "Command and Control"),
    ("exfiltration", "Sızdırma", "Exfiltration"),
    ("impact", "Etki", "Impact"),
)

COMPONENT_LABELS: Mapping[str, str] = {
    "rarity": "Nadirlik",
    "margin": "Ayrışma",
    "sufficiency": "Yeterlilik",
}

MAX_QUERY_TECHNIQUES = 400
PROBE_NEIGHBOURS = 5
DOSSIER_NEIGHBOURS = 8
SIGNATURE_SIZE = 3
SIGNATURE_MIN_SHARE = 0.5
BLIND_MIN_TECHNIQUES = 10


class UnknownActorError(KeyError):
    """Raised when an actor id is not part of the station."""


@dataclass
class Station:
    """Engine artefacts plus the presentation lookups built from them."""

    artifacts: EngineArtifacts
    tactics_by_technique: Mapping[str, tuple[str, ...]]
    positions: Mapping[str, tuple[float, float]]
    clusters: Mapping[str, int]
    manifest: Mapping[str, Any]
    reports_dir: Any = None
    actor_counts: Counter = field(default_factory=Counter)
    profile: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __post_init__(self) -> None:
        self.by_id: dict[str, Actor] = self.artifacts.actor_by_id()
        self.actor_counts = Counter(
            tid for actor in self.artifacts.actors for tid in set(actor.technique_ids)
        )
        rarity = self.artifacts.rarity_weights or weighting.rarity_weights(self.artifacts.actors)
        low, high = (min(rarity.values()), max(rarity.values())) if rarity else (0.0, 1.0)
        span = (high - low) or 1.0
        self.heat = {tid: (w - low) / span for tid, w in rarity.items()}
        self.profile = clustering.cluster_profile(
            dict(self.clusters),
            _edges_frame(self.artifacts.actors, self.artifacts.technique_names),
        )
        self.similarity = self.artifacts.similarity or similarity_mod.compute_similarity(
            self.artifacts.space
        )
        self.index = {aid: i for i, aid in enumerate(self.similarity.actor_ids)}

    @classmethod
    def from_workspace(cls, dataset: str | None = None) -> "Station":
        """Load a built dataset from disk."""
        dataset = dataset or paths.DEFAULT_DATASET
        workspace = paths.Workspace.get(dataset)
        artifacts = loading.load_engine(dataset, with_similarity=True)
        techniques = storage.read_dataframe(workspace.techniques, dataset)
        tactics = {
            str(row.technique_id): split_list(row.tactics) for row in techniques.itertuples()
        }
        if workspace.layout.exists():
            positions = storage.read_layout(workspace.layout, dataset)
        else:
            positions = _layout_from(artifacts)
        clusters = artifacts.clusters or clustering.cluster_actors(
            artifacts.similarity or similarity_mod.compute_similarity(artifacts.space)
        )
        manifest = (
            storage.read_manifest(workspace.data_manifest, dataset).to_dict()
            if workspace.data_manifest.exists()
            else {}
        )
        return cls(
            artifacts=artifacts,
            tactics_by_technique=tactics,
            positions=positions,
            clusters=clusters,
            manifest=manifest,
            reports_dir=workspace.reports_dir,
        )

    @classmethod
    def from_artifacts(
        cls,
        artifacts: EngineArtifacts,
        tactics_by_technique: Mapping[str, Sequence[str]],
        manifest: Mapping[str, Any] | None = None,
        reports_dir: Any = None,
    ) -> "Station":
        """Assemble a station from in-memory artefacts, computing what is missing."""
        sim = artifacts.similarity or similarity_mod.compute_similarity(artifacts.space)
        full = EngineArtifacts(
            dataset=artifacts.dataset,
            actors=artifacts.actors,
            technique_names=artifacts.technique_names,
            weights=artifacts.weights,
            space=artifacts.space,
            similarity=sim,
            clusters=artifacts.clusters or clustering.cluster_actors(sim),
            rarity_weights=artifacts.rarity_weights,
        )
        return cls(
            artifacts=full,
            tactics_by_technique={k: tuple(v) for k, v in tactics_by_technique.items()},
            positions=_layout_from(full),
            clusters=full.clusters,
            manifest=dict(manifest or {}),
            reports_dir=reports_dir,
        )

    def tactics(self) -> list[dict[str, Any]]:
        """Tactic columns in ATT&CK matrix order, limited to those in use."""
        used = {t for tactics in self.tactics_by_technique.values() for t in tactics}
        known = [
            {"id": tid, "name": tr, "name_en": en}
            for tid, tr, en in TACTIC_ORDER
            if tid in used
        ]
        listed = {t["id"] for t in known}
        extra = [
            {"id": t, "name": t.replace("-", " ").title(), "name_en": t.replace("-", " ").title()}
            for t in sorted(used - listed)
        ]
        return known + extra

    def techniques(self) -> list[dict[str, Any]]:
        """The vocabulary with prevalence, weight and normalised heat."""
        artifacts = self.artifacts
        return [
            {
                "id": tid,
                "name": artifacts.technique_names.get(tid, tid),
                "tactics": list(self.tactics_by_technique.get(tid, ())),
                "actor_count": int(self.actor_counts.get(tid, 0)),
                "weight": round(float(artifacts.weights.get(tid, 0.0)), 4),
                "heat": round(float(self.heat.get(tid, 0.0)), 4),
            }
            for tid in artifacts.space.technique_ids
        ]

    def constellations(self) -> list[dict[str, Any]]:
        """Clusters with members and the techniques that define them."""
        members: dict[int, list[str]] = {}
        for actor_id, cluster_id in self.clusters.items():
            members.setdefault(int(cluster_id), []).append(actor_id)
        result = []
        for cluster_id in sorted(c for c in members if c >= 0):
            signature = self.signature(cluster_id)
            result.append(
                {
                    "id": cluster_id,
                    "size": len(members[cluster_id]),
                    "members": sorted(members[cluster_id]),
                    "signature": signature,
                    "label": " · ".join(s["name"] for s in signature[:2]) or f"Takımyıldız {cluster_id}",
                }
            )
        return result

    def signature(self, cluster_id: int) -> list[dict[str, Any]]:
        """Highest-lift techniques shared by at least half of a cluster."""
        if self.profile.empty or cluster_id < 0:
            return []
        cluster = self.profile[self.profile["cluster_id"] == cluster_id]
        rows = cluster[cluster["share_in_cluster"] >= SIGNATURE_MIN_SHARE].head(SIGNATURE_SIZE)
        if rows.empty:
            rows = cluster.assign(strength=cluster["share_in_cluster"] * cluster["lift"])
            rows = rows.sort_values("strength", ascending=False).head(SIGNATURE_SIZE)
        return [
            {
                "id": str(row.technique_id),
                "name": str(row.technique_name),
                "share": round(float(row.share_in_cluster), 3),
                "lift": round(float(row.lift), 3),
            }
            for row in rows.itertuples()
        ]

    def actors(self) -> list[dict[str, Any]]:
        """Every actor as a point on the map."""
        return [
            {
                "id": actor.actor_id,
                "name": actor.name,
                "aliases": list(actor.aliases),
                "technique_count": len(actor.technique_ids),
                "cluster": int(self.clusters.get(actor.actor_id, -1)),
                "x": self.positions.get(actor.actor_id, (0.0, 0.0))[0],
                "y": self.positions.get(actor.actor_id, (0.0, 0.0))[1],
            }
            for actor in self.artifacts.actors
        ]

    def overview(self) -> dict[str, Any]:
        """The full static payload the interface boots from."""
        manifest = self.manifest
        return {
            "dataset": {
                "name": self.artifacts.dataset,
                "source": manifest.get("source"),
                "attack_version": manifest.get("attack_version"),
                "built_at": manifest.get("built_at"),
                "actor_count": len(self.artifacts.actors),
                "technique_count": self.artifacts.space.n_techniques,
                "edge_count": int(sum(len(a.technique_ids) for a in self.artifacts.actors)),
            },
            "scoring": {
                "scheme": config.WEIGHTING_SCHEME,
                "metric": config.SIMILARITY_METRIC,
                "coverage_correction": config.COVERAGE_CORRECTION,
                "high_threshold": config.CONFIDENCE_HIGH_THRESHOLD,
                "medium_threshold": config.CONFIDENCE_MEDIUM_THRESHOLD,
                "component_weights": dict(config.CONFIDENCE_COMPONENT_WEIGHTS),
                "min_query_techniques": config.MIN_QUERY_TECHNIQUES,
                "sufficiency_saturation": config.SUFFICIENCY_SATURATION,
                "weak_component": config.CONFIDENCE_WEAK_COMPONENT,
            },
            "disclaimer": config.DISCLAIMER,
            "tactics": self.tactics(),
            "techniques": self.techniques(),
            "actors": self.actors(),
            "constellations": self.constellations(),
        }

    def query(self, techniques: str | Sequence[str], top_k: int | None = None) -> dict[str, Any]:
        """Run the engine's query path and attach what the map needs to draw it."""
        artifacts = self.artifacts
        result = query_mod.query_techniques(techniques, artifacts, top_k=top_k)
        known = [t for t in result.query_technique_ids if t not in result.unknown_technique_ids]
        scores = query_mod.score_query(known, artifacts) if known else np.zeros(len(artifacts.actors))
        glow = {
            artifacts.space.actor_ids[i]: round(float(s), 4)
            for i, s in enumerate(scores)
            if s > 0
        }
        return {
            "query": {
                "techniques": list(result.query_technique_ids),
                "known": known,
                "unknown": list(result.unknown_technique_ids),
            },
            "signals": [self._signal(tid, tid in known) for tid in result.query_technique_ids],
            "candidates": [self._candidate(c) for c in result.candidates],
            "confidence": self._confidence(result),
            "probe": self._probe(result),
            "field": glow,
            "disclaimer": result.disclaimer,
        }

    def resolve(self, actor_id: str) -> str:
        """Canonical actor id for user input, matching case-insensitively."""
        if actor_id in self.by_id:
            return actor_id
        folded = {aid.casefold(): aid for aid in self.by_id}
        try:
            return folded[actor_id.casefold()]
        except KeyError:
            raise UnknownActorError(actor_id) from None

    def dossier(self, actor_id: str) -> dict[str, Any]:
        """One actor's profile: techniques, constellation and neighbours."""
        actor_id = self.resolve(actor_id)
        actor = self.by_id[actor_id]
        cluster_id = int(self.clusters.get(actor_id, -1))
        weights = self.artifacts.weights
        techniques = sorted(
            (self._technique_row(tid) for tid in actor.technique_ids),
            key=lambda row: (-row["weight"], row["id"]),
        )
        return {
            "id": actor.actor_id,
            "name": actor.name,
            "aliases": list(actor.aliases),
            "technique_count": len(actor.technique_ids),
            "mean_weight": round(
                float(np.mean([weights.get(t, 0.0) for t in actor.technique_ids])), 4
            ) if actor.technique_ids else 0.0,
            "cluster": {
                "id": cluster_id,
                "signature": self.signature(cluster_id),
                "members": sorted(a for a, c in self.clusters.items() if c == cluster_id and a != actor_id)
                if cluster_id >= 0 else [],
            },
            "position": list(self.positions.get(actor_id, (0.0, 0.0))),
            "techniques": techniques,
            "neighbours": self.neighbours(actor_id),
        }

    def neighbours(self, actor_id: str, limit: int = DOSSIER_NEIGHBOURS) -> list[dict[str, Any]]:
        """Nearest actors with the mean weight of what each pair shares."""
        actor = self.by_id[actor_id]
        own = set(actor.technique_ids)
        weights = self.artifacts.weights
        rows = []
        for other_id, score in similarity_mod.nearest_actors(self.similarity, actor_id, limit):
            other = self.by_id[other_id]
            shared = sorted(own & set(other.technique_ids))
            shared_weights = [weights.get(t, 0.0) for t in shared]
            rows.append(
                {
                    "id": other_id,
                    "name": other.name,
                    "score": round(float(score), 4),
                    "technique_count": len(other.technique_ids),
                    "shared_count": len(shared),
                    "shared_mean_weight": round(float(np.mean(shared_weights)), 4) if shared else 0.0,
                    "cluster": int(self.clusters.get(other_id, -1)),
                }
            )
        return rows

    def compare(self, left_id: str, right_id: str) -> dict[str, Any]:
        """Two actors' footprints split into shared and exclusive techniques."""
        left_id, right_id = self.resolve(left_id), self.resolve(right_id)
        left, right = self.by_id[left_id], self.by_id[right_id]
        a, b = set(left.technique_ids), set(right.technique_ids)

        def rows(ids: set[str]) -> list[dict[str, Any]]:
            return sorted(
                (self._technique_row(t) for t in ids), key=lambda r: (-r["weight"], r["id"])
            )

        union = len(a | b)
        return {
            "left": {"id": left.actor_id, "name": left.name, "technique_count": len(a)},
            "right": {"id": right.actor_id, "name": right.name, "technique_count": len(b)},
            "similarity": round(
                float(self.similarity.matrix[self.index[left_id], self.index[right_id]]), 4
            ),
            "jaccard": round(len(a & b) / union, 4) if union else 0.0,
            "shared": rows(a & b),
            "left_only": rows(a - b),
            "right_only": rows(b - a),
        }

    def noise(
        self, techniques: Sequence[str], ratio: float, seed: int | None = None
    ) -> list[str]:
        """Prevalence-weighted foreign techniques, as the benchmark's regime C injects."""
        current = set(normalize_technique_ids(techniques))
        count = max(1, int(round(len(current) * ratio)))
        rng = random.Random(seed)
        return list(
            sampling.sample_noise(current, count, dict(self.actor_counts), rng)
        )

    def blind_case(
        self, fraction: float, noise_ratio: float = 0.0, seed: int | None = None
    ) -> dict[str, Any]:
        """A hidden actor's partial footprint, for the interface's blind test."""
        rng = random.Random(seed)
        pool = sorted(
            (a for a in self.artifacts.actors if len(a.technique_ids) >= BLIND_MIN_TECHNIQUES),
            key=lambda a: a.actor_id,
        ) or sorted(self.artifacts.actors, key=lambda a: a.actor_id)
        actor = rng.choice(pool)
        size = max(config.EVAL_MIN_QUERY_TECHNIQUES, int(len(actor.technique_ids) * fraction))
        size = min(size, len(actor.technique_ids))
        observed = sorted(rng.sample(list(actor.technique_ids), size))
        noise: list[str] = []
        if noise_ratio > 0:
            noise = list(
                sampling.sample_noise(
                    set(actor.technique_ids),
                    max(1, int(round(size * noise_ratio))),
                    dict(self.actor_counts),
                    rng,
                )
            )
        return {
            "techniques": observed,
            "noise": noise,
            "answer": {"id": actor.actor_id, "name": actor.name},
        }

    def trust(self) -> dict[str, Any]:
        """Benchmark results, if the regimes have been run for this dataset."""
        command = f"python -m ttp_similarity.evaluation.benchmark --dataset {self.artifacts.dataset} --regimes"
        directory = self.reports_dir
        summary_path = directory / "regime_summary.csv" if directory is not None else None
        if summary_path is None or not summary_path.exists():
            return {"available": False, "command": command}

        def frame(name: str) -> pd.DataFrame:
            path = directory / name
            return pd.read_csv(path) if path.exists() else pd.DataFrame()

        summary = frame("regime_summary.csv")
        calibration = frame("regime_by_confidence.csv")
        by_size = frame("regime_by_technique_count.csv")
        significance = frame("regime_significance.csv")
        return {
            "available": True,
            "command": command,
            "summary": _records(summary.drop(columns=["notes"], errors="ignore")),
            "calibration": _records(calibration),
            "by_size": _records(by_size),
            "significance": _records(significance),
        }

    def _technique_row(self, tid: str) -> dict[str, Any]:
        return {
            "id": tid,
            "name": self.artifacts.technique_names.get(tid, tid),
            "tactics": list(self.tactics_by_technique.get(tid, ())),
            "weight": round(float(self.artifacts.weights.get(tid, 0.0)), 4),
            "heat": round(float(self.heat.get(tid, 0.0)), 4),
            "actor_count": int(self.actor_counts.get(tid, 0)),
        }

    def _signal(self, tid: str, known: bool) -> dict[str, Any]:
        row = self._technique_row(tid)
        row["known"] = known
        return row

    def _candidate(self, candidate) -> dict[str, Any]:
        actor = self.by_id.get(candidate.actor_id)
        x, y = self.positions.get(candidate.actor_id, (0.0, 0.0))
        return {
            "rank": candidate.rank,
            "id": candidate.actor_id,
            "name": candidate.actor_name,
            "aliases": list(actor.aliases) if actor else [],
            "score": round(float(candidate.score), 5),
            "technique_count": len(actor.technique_ids) if actor else 0,
            "cluster": int(self.clusters.get(candidate.actor_id, -1)),
            "matched": list(candidate.matched_technique_ids),
            "missing": list(candidate.missing_technique_ids),
            "evidence": [
                {
                    "id": e.technique_id,
                    "name": e.technique_name,
                    "weight": round(float(e.weight), 4),
                    "share": round(float(e.contribution), 4),
                }
                for e in candidate.evidence
            ],
            "x": x,
            "y": y,
        }

    def _confidence(self, result: QueryResult) -> dict[str, Any]:
        breakdown = result.confidence
        components = {
            "rarity": breakdown.rarity,
            "margin": breakdown.margin,
            "sufficiency": breakdown.sufficiency,
        }
        weakest = min(components, key=components.get) if result.candidates else None
        return {
            "level": breakdown.level.value,
            "score": round(float(breakdown.score), 4),
            "components": [
                {
                    "id": key,
                    "label": COMPONENT_LABELS[key],
                    "value": round(float(value), 4),
                    "weight": config.CONFIDENCE_COMPONENT_WEIGHTS[key],
                    "weak": value <= config.CONFIDENCE_WEAK_COMPONENT,
                }
                for key, value in components.items()
            ],
            "weakest": weakest,
            "reasons": confidence_mod.explain(breakdown) if result.candidates else [],
        }

    def _probe(self, result: QueryResult) -> dict[str, float] | None:
        top = result.candidates[:PROBE_NEIGHBOURS]
        if not top:
            return None
        mass = np.array([c.score ** 2 for c in top])
        if mass.sum() <= 0:
            return None
        xy = np.array([self.positions.get(c.actor_id, (0.0, 0.0)) for c in top])
        point = (xy * mass[:, None]).sum(axis=0) / mass.sum()
        return {"x": round(float(point[0]), 5), "y": round(float(point[1]), 5)}


def _edges_frame(actors: Sequence[Actor], names: Mapping[str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"actor_id": a.actor_id, "technique_id": t, "technique_name": names.get(t, t)}
            for a in actors
            for t in a.technique_ids
        ],
        columns=["actor_id", "technique_id", "technique_name"],
    )


def _layout_from(artifacts: EngineArtifacts) -> dict[str, tuple[float, float]]:
    sim = artifacts.similarity or similarity_mod.compute_similarity(artifacts.space)
    frame = layout_mod.compute_layout(sim)
    return {str(r.actor_id): (float(r.x), float(r.y)) for r in frame.itertuples()}


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    clean = frame.replace({np.nan: None})
    return clean.to_dict(orient="records")
