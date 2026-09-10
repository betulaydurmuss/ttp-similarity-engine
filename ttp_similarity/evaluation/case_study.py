"""Per-actor case study: the material behind a written or spoken write-up.

Produces, for one actor, everything needed to explain *why* the engine places it
where it does:

* its full technique list with each technique's weight and prevalence, so the
  distinctive behaviour can be separated from the commodity behaviour;
* its nearest neighbours under the weighted metric and under plain Jaccard,
  side by side, with the mean weight of the techniques each pair shares --
  the number that says whether a similarity comes from rare behaviour or from
  everyone-does-this behaviour;
* two contrasting queries: one built from the actor's most distinctive
  techniques, one from its most commodity ones. The contrast is the point --
  it shows what the system does when the input carries no signal.

Run::

    python -m ttp_similarity.evaluation.case_study --dataset attck --actor G0065

Owner: evaluation module.
"""

from __future__ import annotations

import argparse
from typing import Sequence

import numpy as np
import pandas as pd

from .. import config, paths, storage
from ..engine import loading, query
from ..engine import similarity as similarity_mod
from ..schema import Actor, EngineArtifacts, QueryResult

#: How many techniques each contrast query uses.
QUERY_SIZE = 8

#: How many neighbours the ranking tables list.
NEIGHBOUR_COUNT = 15


def technique_table(
    actor: Actor, artifacts: EngineArtifacts, frequency: pd.DataFrame
) -> pd.DataFrame:
    """The actor's techniques with weight and prevalence, heaviest first.

    Args:
        actor: The subject.
        artifacts: Loaded engine artefacts (for weights and names).
        frequency: ``technique_frequency.csv``, for the actor counts.

    Returns:
        DataFrame with ``technique_id``, ``technique_name``, ``weight``,
        ``actor_count``, ``actor_ratio``, ``band``.
    """
    counts = dict(zip(frequency["technique_id"], frequency["actor_count"]))
    ratios = dict(zip(frequency["technique_id"], frequency["actor_ratio"]))
    rows = [
        {
            "technique_id": tid,
            "technique_name": artifacts.technique_names.get(tid, tid),
            "weight": artifacts.weights.get(tid, float("nan")),
            "actor_count": int(counts.get(tid, 0)),
            "actor_ratio": float(ratios.get(tid, 0.0)),
        }
        for tid in actor.technique_ids
    ]
    frame = pd.DataFrame(rows).sort_values("weight", ascending=False).reset_index(drop=True)
    # A readable label for the write-up: which end of the distribution is this?
    frame["band"] = np.where(
        frame["actor_count"] <= 3,
        "distinctive",
        np.where(frame["actor_ratio"] >= 0.40, "commodity", "middle"),
    )
    return frame


def neighbour_table(
    actor: Actor,
    artifacts: EngineArtifacts,
    metric: str,
    limit: int = NEIGHBOUR_COUNT,
) -> pd.DataFrame:
    """Nearest actors under one metric, with shared-technique diagnostics.

    ``shared_mean_weight`` is the column that matters for interpretation: two
    actors can share the same number of techniques and mean very different
    things depending on whether those techniques are rare or universal.

    Args:
        actor: The subject.
        artifacts: Loaded engine artefacts.
        metric: ``"cosine"``, ``"jaccard"`` or ``"weighted_jaccard"``.
        limit: How many neighbours to return.

    Returns:
        DataFrame with ``rank``, ``actor_id``, ``actor_name``, ``score``,
        ``technique_count``, ``shared_count``, ``shared_mean_weight``,
        ``shared_max_weight``.
    """
    space = artifacts.space
    by_id = artifacts.actor_by_id()
    weights = artifacts.weights
    own = set(actor.technique_ids)

    if metric == "cosine":
        matrix = similarity_mod.cosine_similarity_matrix(space)
    elif metric == "jaccard":
        matrix = similarity_mod.jaccard_similarity_matrix(space)
    elif metric == "weighted_jaccard":
        binary = (space.matrix > 0).astype(float)
        per_technique = np.array([float(weights.get(t, 0.0)) for t in space.technique_ids])
        weighted = binary * per_technique
        totals = weighted.sum(axis=1)
        intersection = np.minimum(weighted[:, None, :], weighted[None, :, :]).sum(axis=2)
        union = totals[:, None] + totals[None, :] - intersection
        with np.errstate(divide="ignore", invalid="ignore"):
            matrix = np.where(union > 0, intersection / union, 0.0)
    else:
        raise ValueError(f"Unknown metric: {metric}")

    index = {aid: i for i, aid in enumerate(space.actor_ids)}
    row = matrix[index[actor.actor_id]]
    order = [j for j in np.argsort(row)[::-1] if j != index[actor.actor_id]][:limit]

    rows = []
    for rank, position in enumerate(order, start=1):
        other = by_id[space.actor_ids[position]]
        shared = sorted(own & set(other.technique_ids))
        shared_weights = [weights.get(t, 0.0) for t in shared]
        rows.append(
            {
                "rank": rank,
                "actor_id": other.actor_id,
                "actor_name": other.name,
                "score": float(row[position]),
                "technique_count": len(other.technique_ids),
                "shared_count": len(shared),
                "shared_mean_weight": float(np.mean(shared_weights)) if shared else 0.0,
                "shared_max_weight": float(np.max(shared_weights)) if shared else 0.0,
            }
        )
    return pd.DataFrame(rows)


def contrast_queries(
    techniques: pd.DataFrame, size: int = QUERY_SIZE
) -> tuple[list[str], list[str]]:
    """The actor's ``size`` most distinctive and ``size`` most commodity techniques."""
    distinctive = list(techniques.head(size)["technique_id"])
    commodity = list(techniques.tail(size)["technique_id"])
    return distinctive, commodity


def run_query(
    technique_ids: Sequence[str], artifacts: EngineArtifacts, top_k: int = 10
) -> QueryResult:
    """Query the engine with the configured metric and correction."""
    return query.query_techniques(technique_ids, artifacts, top_k=top_k)


def candidates_frame(result: QueryResult, target_id: str) -> pd.DataFrame:
    """Ranked candidates as a table, flagging the case-study actor."""
    return pd.DataFrame(
        [
            {
                "rank": c.rank,
                "actor_id": c.actor_id,
                "actor_name": c.actor_name,
                "score": round(c.score, 4),
                "matched": len(c.matched_technique_ids),
                "missing": len(c.missing_technique_ids),
                "is_target": c.actor_id == target_id,
            }
            for c in result.candidates
        ]
    )


def evidence_frame(result: QueryResult) -> pd.DataFrame:
    """The top candidate's evidence breakdown."""
    top = result.top
    if top is None:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "technique_id": e.technique_id,
                "technique_name": e.technique_name,
                "weight": round(e.weight, 4),
                "contribution": round(e.contribution, 4),
            }
            for e in top.evidence
        ]
    )


def _render_query(title: str, ids: Sequence[str], result: QueryResult, target: str,
                  names: dict[str, str]) -> list[str]:
    lines = ["", title, "-" * len(title), "", "  query:"]
    for tid in ids:
        lines.append(f"    {tid}  {names.get(tid, '')}")
    conf = result.confidence
    lines += [
        "",
        f"  confidence: {conf.level.value.upper()}  (score {conf.score:.3f})",
        f"    rarity      (0.40): {conf.rarity:.3f}",
        f"    margin      (0.35): {conf.margin:.3f}",
        f"    sufficiency (0.25): {conf.sufficiency:.3f}",
        "",
        "  candidates:",
    ]
    for c in result.candidates:
        mark = "   <== case-study actor" if c.actor_id == target else ""
        lines.append(
            f"    {c.rank:>2}. {c.score:.4f}  {c.actor_id}  {c.actor_name:<24} "
            f"{len(c.matched_technique_ids)}/{len(ids)} matched{mark}"
        )
    rank = next((c.rank for c in result.candidates if c.actor_id == target), None)
    lines.append(f"  -> target rank: {rank if rank else 'outside top-k'}")
    top = result.top
    if top is not None:
        lines += ["", f"  evidence for candidate #1 ({top.actor_name}):"]
        for e in top.evidence:
            lines.append(
                f"    {e.contribution * 100:5.1f}%  {e.technique_id}  "
                f"{e.technique_name[:44]:<44} (w={e.weight:.2f})"
            )
        missing = ", ".join(top.missing_technique_ids) or "none"
        lines.append(f"    not documented for this actor: {missing}")
    return lines


def build_case_study(dataset: str, actor_id: str) -> list[paths.Path]:
    """Produce every case-study artefact for one actor.

    Args:
        dataset: Workspace name.
        actor_id: ATT&CK group id, e.g. ``"G0065"``.

    Returns:
        The paths written.

    Raises:
        KeyError: If the actor is not in the dataset.
    """
    workspace = paths.Workspace.get(dataset)
    artifacts = loading.load_engine(dataset, with_similarity=False)
    frequency = storage.read_dataframe(workspace.technique_frequency, dataset)

    by_id = artifacts.actor_by_id()
    if actor_id not in by_id:
        raise KeyError(f"{actor_id} is not in dataset {dataset!r}")
    actor = by_id[actor_id]

    out = workspace.reports_dir / f"case_{actor_id}"
    out.mkdir(parents=True, exist_ok=True)
    written: list[paths.Path] = []

    techniques = technique_table(actor, artifacts, frequency)
    written.append(storage.write_dataframe(techniques, out / "techniques.csv"))

    neighbours = {
        metric: neighbour_table(actor, artifacts, metric)
        for metric in ("cosine", "jaccard", "weighted_jaccard")
    }
    for metric, frame in neighbours.items():
        written.append(storage.write_dataframe(frame, out / f"neighbours_{metric}.csv"))

    # Rank movement between the weighted and the unweighted view.
    merged = neighbours["cosine"].merge(
        neighbours["jaccard"][["actor_id", "rank", "score"]],
        on="actor_id",
        how="outer",
        suffixes=("_cosine", "_jaccard"),
    )
    written.append(storage.write_dataframe(merged, out / "neighbours_rank_shift.csv"))

    distinctive, commodity = contrast_queries(techniques)
    results = {
        "distinctive": run_query(distinctive, artifacts),
        "commodity": run_query(commodity, artifacts),
    }
    for name, result in results.items():
        written.append(
            storage.write_dataframe(
                candidates_frame(result, actor_id), out / f"query_{name}_candidates.csv"
            )
        )
        written.append(
            storage.write_dataframe(
                evidence_frame(result), out / f"query_{name}_evidence.csv"
            )
        )
        written.append(storage.write_json(out / f"query_{name}.json", result.to_dict()))

    written.append(
        _write_text(
            actor, artifacts, techniques, neighbours, distinctive, commodity,
            results, out / "case_study.txt",
        )
    )
    return written


def _write_text(actor, artifacts, techniques, neighbours, distinctive, commodity,
                results, path) -> paths.Path:
    """Render the readable case-study report."""
    names = dict(artifacts.technique_names)
    lines = [
        "=" * 96,
        f" CASE STUDY: {actor.name}  ({actor.actor_id})",
        "=" * 96,
        f" dataset  : {artifacts.dataset}",
        f" aliases  : {', '.join(actor.aliases) or '-'}",
        f" techniques: {len(actor.technique_ids)}",
        f" scoring  : metric={config.SIMILARITY_METRIC}, "
        f"coverage_correction={config.COVERAGE_CORRECTION}, "
        f"weighting={config.WEIGHTING_SCHEME}",
        "",
        "",
        "1) TECHNIQUES, HEAVIEST FIRST",
        "-" * 96,
        f"  {'weight':>6}  {'id':<7} {'name':<46} {'actors':>6} {'share':>6}  band",
    ]
    for row in techniques.itertuples():
        lines.append(
            f"  {row.weight:>6.3f}  {row.technique_id:<7} {row.technique_name[:46]:<46} "
            f"{row.actor_count:>6} {row.actor_ratio:>6.2f}  {row.band}"
        )

    for metric, title in (
        ("cosine", "2) NEAREST ACTORS -- weighted cosine (production metric)"),
        ("jaccard", "3) NEAREST ACTORS -- plain Jaccard (unweighted control)"),
        ("weighted_jaccard", "4) NEAREST ACTORS -- weighted Jaccard (Ruzicka)"),
    ):
        lines += ["", "", title, "-" * 96,
                  f"  {'#':>2} {'score':>7} {'actor':<26} {'tech':>5} {'shared':>7} "
                  f"{'shared w-mean':>13} {'w-max':>6}"]
        for row in neighbours[metric].itertuples():
            lines.append(
                f"  {row.rank:>2} {row.score:>7.4f} {row.actor_name[:26]:<26} "
                f"{row.technique_count:>5} {row.shared_count:>7} "
                f"{row.shared_mean_weight:>13.3f} {row.shared_max_weight:>6.2f}"
            )

    lines += _render_query(
        "5) QUERY FROM THE 8 MOST DISTINCTIVE TECHNIQUES",
        distinctive, results["distinctive"], actor.actor_id, names,
    )
    lines += _render_query(
        "6) QUERY FROM THE 8 MOST COMMODITY TECHNIQUES (contrast)",
        commodity, results["commodity"], actor.actor_id, names,
    )
    lines += ["", "", "=" * 96, " " + config.DISCLAIMER, "=" * 96]

    storage.ensure_parent(path)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m ttp_similarity.evaluation.case_study``."""
    parser = argparse.ArgumentParser(description="Per-actor case-study material.")
    parser.add_argument(
        "--dataset", default=paths.DEFAULT_DATASET, choices=list(paths.KNOWN_DATASETS)
    )
    parser.add_argument("--actor", required=True, help="ATT&CK group id, e.g. G0065")
    args = parser.parse_args(argv)

    config.validate()
    written = build_case_study(args.dataset, args.actor)
    print(f"{len(written)} files written to {written[0].parent}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
