"""Run the retrieval benchmark and write the report.

Measurement design (fixed; see ``DECISIONS.md`` section 7):

* For every actor, a fixed share of its techniques (default 50%) is drawn at
  random as the query; the rest is hidden.
* 20 repetitions per actor, from one seed, so a run is reproducible exactly.
* A repetition whose query would hold fewer than 3 techniques is **skipped and
  counted**, never padded -- padding would put hidden techniques back into the
  query and leak the answer.
* The target is the actor the query came from, so this is a self-retrieval test:
  can the engine find an actor from half of its own documented behaviour?

Reported: top-1 / top-3 / top-5 accuracy, MRR, the mean rank of the correct
answer, and breakdowns by confidence level (the calibration check) and by the
target's technique count (the accuracy-side counterpart of the size bias in
``DECISIONS.md`` section 3.3).

Every threshold and weight is read from :mod:`ttp_similarity.config` at call
time, so an ablation run that changes the config actually takes effect.

Run::

    python -m ttp_similarity.evaluation.benchmark --dataset attck
    python -m ttp_similarity.evaluation.benchmark --dataset attck --compare
    python -m ttp_similarity.evaluation.benchmark --dataset attck --scheme binary

Outputs land in ``outputs/reports/<dataset>/`` as CSV plus a readable text
report.

Owner: evaluation module.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import pandas as pd

from .. import config, paths, storage
from ..data import frequency as frequency_mod
from ..data.normalize import filter_sparse_actors
from ..engine import loading, query, vectorize, weighting
from ..schema import (
    EVALUATION_TRIAL_COLUMNS,
    Actor,
    EngineArtifacts,
    EvaluationReport,
    EvaluationTrial,
)
from . import metrics, sampling


@dataclass(frozen=True)
class RunSpec:
    """One benchmark configuration.

    Everything that distinguishes one row of a comparison table from another.
    Fields left at ``None`` fall back to :mod:`ttp_similarity.config` when the
    run is executed, not when this object is created.
    """

    label: str
    regime: str = ""
    noise_ratio: float = 0.0
    scheme: str | None = None  # smooth_idf | plain_idf | binary
    metric: str | None = None  # cosine | jaccard
    min_techniques: int | None = None
    coverage_correction: bool | None = None
    fraction: float | None = None
    repeats: int | None = None
    seed: int | None = None
    top_k: int | None = None

    def resolved(self) -> dict[str, object]:
        """The effective settings, for the report header."""
        return {
            "scheme": self.scheme or config.WEIGHTING_SCHEME,
            "metric": self.metric or config.SIMILARITY_METRIC,
            "min_techniques": self.min_techniques or config.MIN_TECHNIQUES_PER_ACTOR,
            "coverage_correction": (
                config.COVERAGE_CORRECTION
                if self.coverage_correction is None
                else self.coverage_correction
            ),
            "fraction": self.fraction or config.EVAL_QUERY_FRACTION,
            "repeats": self.repeats or config.EVAL_REPEATS_PER_ACTOR,
            "seed": self.seed if self.seed is not None else config.EVAL_RANDOM_SEED,
            "top_k": self.top_k or config.QUERY_TOP_K,
            "noise_ratio": self.noise_ratio,
        }


def build_artifacts(
    actors: Sequence[Actor],
    dataset: str,
    *,
    scheme: str | None = None,
    min_techniques: int | None = None,
    technique_names: dict[str, str] | None = None,
) -> EngineArtifacts:
    """Assemble in-memory engine artefacts for one ablation variant.

    The variants differ only in the sparse-actor threshold and the weighting
    scheme, and both are cheap to recompute, so a variant is built in memory
    rather than by re-running the whole ``engine.build`` pipeline to disk.

    Filtering the already-built actor list is equivalent to rebuilding the
    dataset at that threshold: the threshold is applied after roll-up and alias
    merging, and does not change any actor's technique set.

    Args:
        actors: Canonical actors from the stage-1 build.
        dataset: Workspace name, carried into the artefacts for reporting.
        scheme: Weighting scheme; ``None`` reads config at call time.
        min_techniques: Sparse-actor threshold; ``None`` reads config.
        technique_names: ``technique_id -> name`` for readable evidence.

    Returns:
        Artefacts ready for :func:`ttp_similarity.engine.query.query_techniques`.

    Raises:
        ValueError: If the threshold leaves no actors.
    """
    kept = filter_sparse_actors(actors, min_techniques)
    if not kept:
        raise ValueError(f"min_techniques={min_techniques} leaves no actors")

    names = dict(technique_names or {})
    frequency = frequency_mod.compute_technique_frequency(kept, names)
    weights_frame = weighting.compute_weights(frequency, len(kept), scheme)
    weights = weighting.weights_to_mapping(weights_frame)
    space = vectorize.build_vector_space(kept, weights)

    return EngineArtifacts(
        dataset=dataset,
        actors=tuple(kept),
        technique_names=names,
        weights=weights,
        space=space,
    )


def run_trial(
    spec: sampling.TrialSpec,
    artifacts: EngineArtifacts,
    top_k: int | None = None,
    *,
    metric: str | None = None,
    coverage_correction: bool | None = None,
) -> EvaluationTrial:
    """Execute one planned trial against the engine.

    Args:
        spec: The planned trial.
        artifacts: Pre-loaded artefacts; loaded once by the caller because
            reloading per trial would dominate the runtime.
        top_k: Candidate list length; the true actor's rank is ``-1`` when it
            falls outside this.
        metric: Query scoring metric.
        coverage_correction: Whether to apply the coverage penalty.

    Returns:
        The executed :class:`~ttp_similarity.schema.EvaluationTrial`.
    """
    top_k = config.QUERY_TOP_K if top_k is None else top_k
    result = query.query_techniques(
        spec.technique_ids,
        artifacts,
        top_k=top_k,
        metric=metric,
        coverage_correction=coverage_correction,
    )

    rank = -1
    for candidate in result.candidates:
        if candidate.actor_id == spec.actor_id:
            rank = candidate.rank
            break

    top = result.top
    return EvaluationTrial(
        trial_id=spec.trial_id,
        true_actor_id=spec.actor_id,
        sample_size=spec.sample_size,
        sampled_technique_ids=spec.technique_ids,
        predicted_actor_id=top.actor_id if top else None,
        rank=rank,
        top1_score=top.score if top else 0.0,
        confidence_level=result.confidence.level,
        technique_count=spec.technique_count,
        noise_count=spec.noise_count,
        confidence_score=result.confidence.score,
    )


def run_spec(
    spec: RunSpec,
    actors: Sequence[Actor],
    dataset: str,
    technique_names: dict[str, str] | None = None,
    plan: sampling.TrialPlan | None = None,
) -> tuple[EvaluationReport, list[EvaluationTrial]]:
    """Run one configuration end to end.

    Args:
        spec: The configuration.
        actors: Canonical actors from the stage-1 build.
        dataset: Workspace name.

    Returns:
        ``(report, trials)``.
    """
    settings = spec.resolved()
    artifacts = build_artifacts(
        actors,
        dataset,
        scheme=spec.scheme,
        min_techniques=spec.min_techniques,
        technique_names=technique_names,
    )
    plan = plan or sampling.build_proportional_trial_plan(
        artifacts.actors,
        fraction=spec.fraction,
        repeats=spec.repeats,
        seed=spec.seed,
        noise_ratio=spec.noise_ratio,
    )
    trials = [
        run_trial(
            trial,
            artifacts,
            top_k=spec.top_k,
            metric=spec.metric,
            coverage_correction=spec.coverage_correction,
        )
        for trial in plan.trials
    ]

    mean_rank, misses = metrics.mean_rank_of_correct_answer(trials)
    report = EvaluationReport(
        dataset=dataset,
        n_trials=len(trials),
        sample_sizes=tuple(sorted({t.sample_size for t in trials})),
        top1_accuracy=metrics.top_k_accuracy(trials, 1),
        top3_accuracy=metrics.top_k_accuracy(trials, 3),
        top5_accuracy=metrics.top_k_accuracy(trials, 5),
        mean_reciprocal_rank=metrics.mean_reciprocal_rank(trials),
        mean_rank=mean_rank,
        miss_count=misses,
        skipped_trials=plan.skipped,
        actor_count=len(artifacts.actors),
        label=spec.label,
        regime=spec.regime,
        by_sample_size=metrics.breakdown_by_sample_size(trials),
        by_confidence=metrics.breakdown_by_confidence(trials),
        by_technique_count=metrics.breakdown_by_technique_count(trials),
        seed=int(settings["seed"]),
        notes=(
            f"scheme={settings['scheme']} metric={settings['metric']} "
            f"min_techniques={settings['min_techniques']} "
            f"coverage_correction={settings['coverage_correction']} "
            f"fraction={settings['fraction']} noise={settings['noise_ratio']} "
            f"repeats={settings['repeats']} "
            f"skipped_actors={len(plan.skipped_actors)}"
        ),
    )
    return report, trials


def run_benchmark(
    dataset: str = paths.DEFAULT_DATASET,
    *,
    spec: RunSpec | None = None,
) -> EvaluationReport:
    """Run the default single configuration and write its report.

    Args:
        dataset: Workspace to evaluate.
        spec: Configuration; defaults to "everything from config".

    Returns:
        The aggregate report (also written to disk).

    Raises:
        ttp_similarity.storage.ArtifactMissingError: If stage 1 has not run.
    """
    workspace = paths.Workspace.get(dataset)
    actors = storage.read_actors(workspace.actors, dataset)
    names = storage.read_technique_names(workspace.techniques, dataset)
    spec = spec or RunSpec(label="baseline")
    report, trials = run_spec(spec, actors, dataset, names)
    write_report(report, trials, workspace)
    return report


def run_comparisons(
    dataset: str = paths.DEFAULT_DATASET,
) -> tuple[list[EvaluationReport], dict[str, list[EvaluationReport]]]:
    """Run the three comparisons the project needs, on one measurement design.

    1. Weighting ablation -- ``smooth_idf`` vs ``binary`` vs plain Jaccard.
       The single most important test: does the weighting earn its cost?
    2. Sparse-actor threshold -- 5 / 8 / 10.
    3. Coverage correction -- off (current) vs on.

    Args:
        dataset: Workspace to evaluate.

    Returns:
        ``(all_reports, grouped_by_comparison)``.
    """
    workspace = paths.Workspace.get(dataset)
    actors = storage.read_actors(workspace.actors, dataset)
    names = storage.read_technique_names(workspace.techniques, dataset)

    groups: dict[str, list[RunSpec]] = {
        "weighting": [
            RunSpec(label="smooth_idf (cosine)", scheme="smooth_idf", metric="cosine"),
            RunSpec(label="binary (cosine)", scheme="binary", metric="cosine"),
            RunSpec(label="jaccard (unweighted)", scheme="binary", metric="jaccard"),
        ],
        "threshold": [
            RunSpec(label=f"min_techniques={t}", min_techniques=t)
            for t in config.EVAL_THRESHOLD_SWEEP
        ],
        "coverage": [
            RunSpec(label="coverage correction OFF", coverage_correction=False),
            RunSpec(label="coverage correction ON", coverage_correction=True),
        ],
    }

    all_reports: list[EvaluationReport] = []
    grouped: dict[str, list[EvaluationReport]] = {}
    all_trials: dict[str, list[EvaluationTrial]] = {}

    for name, specs in groups.items():
        grouped[name] = []
        for spec in specs:
            print(f"[bench] {name}: {spec.label} ...", flush=True)
            report, trials = run_spec(spec, actors, dataset, names)
            grouped[name].append(report)
            all_reports.append(report)
            all_trials[spec.label] = trials

    write_comparison(all_reports, grouped, all_trials, workspace)
    return all_reports, grouped


# --------------------------------------------------------------------------- #
# Regimes: the same design at three difficulty levels
# --------------------------------------------------------------------------- #
#: ``regime -> (query fraction, noise ratio, description)``. The rest of the
#: design (repeats, seed, skip rule, target) is identical across all three, so a
#: difference between regimes is attributable to difficulty alone.
def regimes() -> dict[str, tuple[float, float, str]]:
    """The three difficulty regimes, with regime C's noise read at call time."""
    noise = config.EVAL_NOISE_RATIO
    return {
        "A": (0.50, 0.00, "reference: 50% of the actor's techniques, no noise"),
        "B": (0.25, 0.00, "sparse query: 25% of the actor's techniques, no noise"),
        "C": (0.25, noise, f"noisy query: 25% + {noise:.0%} injected foreign techniques"),
    }

#: Weighting variants compared inside every regime.
SCHEME_VARIANTS: tuple[tuple[str, str, str], ...] = (
    ("smooth_idf", "smooth_idf", "cosine"),
    ("binary", "binary", "cosine"),
    ("jaccard", "binary", "jaccard"),
)


def per_actor_top1(trials: Sequence[EvaluationTrial]) -> dict[str, float]:
    """Top-1 accuracy per target actor -- the unit of the paired comparison."""
    hits: dict[str, list[float]] = {}
    for trial in trials:
        hits.setdefault(trial.true_actor_id, []).append(1.0 if trial.rank == 1 else 0.0)
    return {actor: sum(v) / len(v) for actor, v in hits.items()}


def paired_scheme_test(
    trials_a: Sequence[EvaluationTrial],
    trials_b: Sequence[EvaluationTrial],
) -> dict[str, float]:
    """Paired per-actor comparison of two weighting schemes.

    Both runs execute the identical seeded trial plan, so every actor is scored
    on exactly the same queries -- including identical injected noise -- and the
    comparison is genuinely paired. Each actor contributes one number: its top-1
    accuracy over its repetitions.

    A Wilcoxon signed-rank test is used rather than a t-test: per-actor accuracy
    is a bounded proportion, heavily tied at 1.0, and not remotely normal.

    Args:
        trials_a: Trials from the scheme under test.
        trials_b: Trials from the baseline scheme.

    Returns:
        ``{"delta", "n_actors", "better", "worse", "tied", "p_value"}`` where
        ``delta`` is mean(a) - mean(b) in top-1 accuracy points. ``p_value`` is
        ``nan`` when every actor is tied -- there is then nothing to test.
    """
    from scipy.stats import wilcoxon

    left = per_actor_top1(trials_a)
    right = per_actor_top1(trials_b)
    shared = sorted(set(left) & set(right))
    diffs = [left[a] - right[a] for a in shared]

    better = sum(1 for d in diffs if d > 0)
    worse = sum(1 for d in diffs if d < 0)
    tied = sum(1 for d in diffs if d == 0)

    p_value = float("nan")
    if better + worse > 0:
        try:
            p_value = float(wilcoxon(diffs, zero_method="wilcox").pvalue)
        except ValueError:
            p_value = float("nan")

    return {
        "delta": (sum(diffs) / len(diffs)) if diffs else 0.0,
        "n_actors": float(len(shared)),
        "better": float(better),
        "worse": float(worse),
        "tied": float(tied),
        "p_value": p_value,
    }


def run_regimes(
    dataset: str = paths.DEFAULT_DATASET,
) -> tuple[list[EvaluationReport], dict[str, dict[str, float]]]:
    """Run every regime x scheme combination plus the paired significance tests.

    Within a regime the trial plan is built once and reused by all three
    schemes, so the schemes see identical queries and the paired test is valid.

    Args:
        dataset: Workspace to evaluate.

    Returns:
        ``(reports, significance)`` where ``significance`` maps a regime to the
        smooth_idf-vs-binary paired test result.
    """
    workspace = paths.Workspace.get(dataset)
    actors = storage.read_actors(workspace.actors, dataset)
    names = storage.read_technique_names(workspace.techniques, dataset)

    reports: list[EvaluationReport] = []
    trials_by_key: dict[str, list[EvaluationTrial]] = {}

    all_regimes = regimes()
    for regime, (fraction, noise, _description) in all_regimes.items():
        base = build_artifacts(actors, dataset, technique_names=names)
        plan = sampling.build_proportional_trial_plan(
            base.actors, fraction=fraction, noise_ratio=noise
        )
        for name, scheme, metric in SCHEME_VARIANTS:
            spec = RunSpec(
                label=f"{regime} / {name}",
                regime=regime,
                scheme=scheme,
                metric=metric,
                fraction=fraction,
                noise_ratio=noise,
            )
            print(
                f"[bench] regime {regime} ({fraction:.0%}, noise {noise:.0%}) / {name} ...",
                flush=True,
            )
            report, trials = run_spec(spec, actors, dataset, names, plan=plan)
            reports.append(report)
            trials_by_key[f"{regime}/{name}"] = trials

    significance = {
        regime: paired_scheme_test(
            trials_by_key[f"{regime}/smooth_idf"], trials_by_key[f"{regime}/binary"]
        )
        for regime in all_regimes
    }

    write_regime_outputs(reports, significance, trials_by_key, workspace)
    return reports, significance


def write_regime_outputs(
    reports: Sequence[EvaluationReport],
    significance: dict[str, dict[str, float]],
    trials_by_key: dict[str, list[EvaluationTrial]],
    workspace: paths.Workspace,
) -> list[paths.Path]:
    """Write the regime comparison as CSVs plus a readable text report."""
    workspace.ensure()
    out = workspace.reports_dir
    written: list[paths.Path] = []

    written.append(
        storage.write_dataframe(
            pd.DataFrame([report_to_row(r) for r in reports]),
            out / "regime_summary.csv",
        )
    )
    written.append(
        storage.write_dataframe(
            pd.DataFrame([{"regime": k, **v} for k, v in significance.items()]),
            out / "regime_significance.csv",
        )
    )
    confidence_rows = [
        {"regime": r.regime, "label": r.label, "confidence": level, **row}
        for r in reports
        for level, row in r.by_confidence.items()
    ]
    written.append(
        storage.write_dataframe(
            pd.DataFrame(confidence_rows), out / "regime_by_confidence.csv"
        )
    )
    technique_rows = [
        {"regime": r.regime, "label": r.label, "bucket": bucket, **row}
        for r in reports
        for bucket, row in r.by_technique_count.items()
    ]
    written.append(
        storage.write_dataframe(
            pd.DataFrame(technique_rows), out / "regime_by_technique_count.csv"
        )
    )
    for key, trials in trials_by_key.items():
        slug = key.replace("/", "_")
        written.append(
            storage.write_dataframe(
                pd.DataFrame([t.to_row() for t in trials]),
                out / f"regime_trials_{slug}.csv",
                EVALUATION_TRIAL_COLUMNS,
            )
        )

    lines = [
        "=" * 104,
        " ttp-similarity-engine -- hardened retrieval benchmark (three regimes)",
        "=" * 104,
        f" generated : {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f" dataset   : {reports[0].dataset if reports else '-'}",
        f" shared    : {config.EVAL_REPEATS_PER_ACTOR} repeats/actor, seed "
        f"{config.EVAL_RANDOM_SEED}; repetitions with fewer than "
        f"{config.EVAL_MIN_QUERY_TECHNIQUES} own techniques are skipped and counted",
        f" scoring   : coverage_correction={config.COVERAGE_CORRECTION}, "
        f"min_techniques={config.MIN_TECHNIQUES_PER_ACTOR}",
        "",
        " regimes:",
    ]
    for regime, (fraction, noise, description) in regimes().items():
        lines.append(f"   {regime}: {description}")
    lines += ["", "", "REGIME x SCHEME", "-" * 104]
    cols = [
        "regime", "label", "actors", "trials", "skipped",
        "top1", "top3", "top5", "mrr", "mean_rank", "misses",
    ]
    lines += _fmt_table([report_to_row(r) for r in reports], cols)

    lines += [
        "",
        "",
        "PAIRED TEST: smooth_idf vs binary (per actor, Wilcoxon signed-rank)",
        "-" * 104,
    ]
    sig_rows = [
        {
            "regime": regime,
            "delta_top1": round(v["delta"], 4),
            "actors": int(v["n_actors"]),
            "smooth_better": int(v["better"]),
            "binary_better": int(v["worse"]),
            "tied": int(v["tied"]),
            "p_value": ("nan" if v["p_value"] != v["p_value"] else round(v["p_value"], 6)),
        }
        for regime, v in significance.items()
    ]
    lines += _fmt_table(sig_rows, list(sig_rows[0]))

    lines += ["", "", "CONFIDENCE CALIBRATION", "-" * 104]
    for report in reports:
        lines.append(f"  {report.label}")
        rows = [
            {"level": level, **{k: round(v, 4) for k, v in row.items()}}
            for level, row in report.by_confidence.items()
        ]
        lines += [
            "  " + line
            for line in _fmt_table(rows, ["level", "n", "share", "top1", "top3"])
        ]
        lines.append("")

    lines += ["", "ACCURACY BY TARGET TECHNIQUE COUNT", "-" * 104]
    for report in reports:
        lines.append(f"  {report.label}")
        rows = [
            {"bucket": bucket, **{k: round(v, 4) for k, v in row.items()}}
            for bucket, row in report.by_technique_count.items()
        ]
        lines += [
            "  " + line
            for line in _fmt_table(rows, ["bucket", "actors", "n", "top1", "top3", "mrr"])
        ]
        lines.append("")

    lines += [
        "",
        "=" * 104,
        " NOTE: queries are drawn from the same ATT&CK records the engine indexed,",
        " so even regime C measures retrieval robustness, not attribution accuracy.",
        "=" * 104,
    ]

    path = out / "regime_report.txt"
    storage.ensure_parent(path)
    path.write_text("\n".join(lines), encoding="utf-8")
    written.append(path)
    return written


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def report_to_row(report: EvaluationReport) -> dict[str, object]:
    """Flatten a report to one comparison-table row."""
    return {
        "regime": report.regime,
        "label": report.label,
        "actors": report.actor_count,
        "trials": report.n_trials,
        "skipped": report.skipped_trials,
        "top1": round(report.top1_accuracy, 4),
        "top3": round(report.top3_accuracy, 4),
        "top5": round(report.top5_accuracy, 4),
        "mrr": round(report.mean_reciprocal_rank, 4),
        "mean_rank": round(report.mean_rank, 3),
        "misses": report.miss_count,
        "notes": report.notes,
    }


def write_report(
    report: EvaluationReport,
    trials: Sequence[EvaluationTrial],
    workspace: paths.Workspace,
) -> paths.Workspace:
    """Persist a single run: JSON summary plus the per-trial CSV.

    Args:
        report: Aggregate metrics.
        trials: Executed trials.
        workspace: Destination workspace.

    Returns:
        The workspace that was written.
    """
    workspace.ensure()
    storage.write_json(workspace.evaluation_report, report.to_dict())
    frame = pd.DataFrame([t.to_row() for t in trials])
    storage.write_dataframe(frame, workspace.evaluation_trials, EVALUATION_TRIAL_COLUMNS)
    return workspace


def write_comparison(
    reports: Sequence[EvaluationReport],
    grouped: dict[str, list[EvaluationReport]],
    trials_by_label: dict[str, list[EvaluationTrial]],
    workspace: paths.Workspace,
) -> list[paths.Path]:
    """Write every comparison artefact: CSVs plus one readable text report.

    Args:
        reports: All runs, in execution order.
        grouped: Runs grouped by comparison name.
        trials_by_label: Per-run trials, for the detailed breakdowns.
        workspace: Destination workspace.

    Returns:
        The paths written.
    """
    workspace.ensure()
    out = workspace.reports_dir
    written: list[paths.Path] = []

    written.append(
        storage.write_dataframe(
            pd.DataFrame([report_to_row(r) for r in reports]),
            out / "comparison_summary.csv",
        )
    )

    confidence_rows = []
    technique_rows = []
    for report in reports:
        for level, row in report.by_confidence.items():
            confidence_rows.append({"label": report.label, "confidence": level, **row})
        for bucket, row in report.by_technique_count.items():
            technique_rows.append({"label": report.label, "bucket": bucket, **row})
    written.append(
        storage.write_dataframe(pd.DataFrame(confidence_rows), out / "by_confidence.csv")
    )
    written.append(
        storage.write_dataframe(
            pd.DataFrame(technique_rows), out / "by_technique_count.csv"
        )
    )

    for label, trials in trials_by_label.items():
        slug = label.replace(" ", "_").replace("(", "").replace(")", "").replace("=", "")
        written.append(
            storage.write_dataframe(
                pd.DataFrame([t.to_row() for t in trials]),
                out / f"trials_{slug}.csv",
                EVALUATION_TRIAL_COLUMNS,
            )
        )

    written.append(_write_text_report(reports, grouped, out / "benchmark_report.txt"))
    return written


def _fmt_table(rows: Sequence[dict[str, object]], columns: Sequence[str]) -> list[str]:
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    lines = ["  " + "  ".join(c.ljust(widths[c]) for c in columns)]
    lines.append("  " + "  ".join("-" * widths[c] for c in columns))
    for row in rows:
        lines.append("  " + "  ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))
    return lines


def _write_text_report(
    reports: Sequence[EvaluationReport],
    grouped: dict[str, list[EvaluationReport]],
    path: paths.Path,
) -> paths.Path:
    """Render the human-readable comparison report."""
    titles = {
        "weighting": "1) WEIGHTING ABLATION  (does the weighting earn its cost?)",
        "threshold": "2) SPARSE-ACTOR THRESHOLD",
        "coverage": "3) COVERAGE CORRECTION",
    }
    cols = ["label", "actors", "trials", "skipped", "top1", "top3", "top5", "mrr", "mean_rank", "misses"]

    lines = [
        "=" * 92,
        " ttp-similarity-engine -- retrieval benchmark",
        "=" * 92,
        f" generated : {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f" dataset   : {reports[0].dataset if reports else '-'}",
        f" design    : {config.EVAL_QUERY_FRACTION:.0%} of each actor's techniques as query, "
        f"{config.EVAL_REPEATS_PER_ACTOR} repeats/actor, seed {config.EVAL_RANDOM_SEED}",
        f"             repetitions with fewer than {config.EVAL_MIN_QUERY_TECHNIQUES} "
        "query techniques are skipped and counted",
        f" target    : the actor the query was drawn from (self-retrieval)",
        "",
    ]

    for name, group in grouped.items():
        lines += ["", titles.get(name, name), "-" * 92]
        lines += _fmt_table([report_to_row(r) for r in group], cols)

    lines += ["", "", "4) CONFIDENCE CALIBRATION  (is HIGH actually more often right?)", "-" * 92]
    for report in reports:
        lines.append(f"  {report.label}")
        rows = [
            {"level": level, **{k: round(v, 4) for k, v in row.items()}}
            for level, row in report.by_confidence.items()
        ]
        lines += ["  " + line for line in _fmt_table(rows, ["level", "n", "share", "top1", "top3"])]
        lines.append("")

    lines += ["", "5) ACCURACY BY TARGET TECHNIQUE COUNT", "-" * 92]
    for report in reports:
        lines.append(f"  {report.label}")
        rows = [
            {"bucket": bucket, **{k: round(v, 4) for k, v in row.items()}}
            for bucket, row in report.by_technique_count.items()
        ]
        lines += ["  " + line for line in _fmt_table(rows, ["bucket", "actors", "n", "top1", "top3", "mrr"])]
        lines.append("")

    lines += [
        "",
        "=" * 92,
        " NOTE: the query is drawn from the same ATT&CK records the engine indexed,",
        " so this measures retrieval consistency, not real-world attribution accuracy.",
        " Real incident data is noisier, partial, and contains techniques nobody",
        " attributed to the actor.",
        "=" * 92,
    ]

    storage.ensure_parent(path)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def print_report(report: EvaluationReport) -> None:
    """Print the headline table to stdout."""
    print(f"dataset: {report.dataset}   label: {report.label}")
    print(f"  actors: {report.actor_count}   trials: {report.n_trials}   skipped: {report.skipped_trials}")
    print(f"  top-1: {report.top1_accuracy:.3f}")
    print(f"  top-3: {report.top3_accuracy:.3f}")
    print(f"  top-5: {report.top5_accuracy:.3f}")
    print(f"  MRR  : {report.mean_reciprocal_rank:.3f}")
    print(f"  mean rank of correct answer: {report.mean_rank:.2f}  (misses: {report.miss_count})")
    if report.by_confidence:
        print("  by confidence level (calibration check):")
        for level, row in report.by_confidence.items():
            print(
                f"    {level:<7} top1={row['top1']:.3f}  "
                f"share={row['share']:.2f}  n={int(row['n'])}"
            )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m ttp_similarity.evaluation.benchmark``."""
    parser = argparse.ArgumentParser(description="Retrieval benchmark for the TTP engine.")
    parser.add_argument(
        "--dataset", default=paths.DEFAULT_DATASET, choices=list(paths.KNOWN_DATASETS)
    )
    parser.add_argument("--compare", action="store_true", help="run all three comparisons")
    parser.add_argument("--regimes", action="store_true", help="run the three difficulty regimes")
    parser.add_argument("--scheme", default=None, choices=["smooth_idf", "plain_idf", "binary"])
    parser.add_argument("--metric", default=None, choices=["cosine", "jaccard"])
    parser.add_argument("--min-techniques", type=int, default=None)
    parser.add_argument("--coverage-correction", action="store_true", default=None)
    parser.add_argument("--fraction", type=float, default=None)
    parser.add_argument("--repeats", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)

    config.validate()
    if args.regimes:
        reports, significance = run_regimes(args.dataset)
        for report in reports:
            print_report(report)
            print()
        print(f"reports: {paths.Workspace.get(args.dataset).reports_dir}")
        return 0
    if args.compare:
        reports, _ = run_comparisons(args.dataset)
        for report in reports:
            print_report(report)
            print()
        print(f"reports: {paths.Workspace.get(args.dataset).reports_dir}")
        return 0

    report = run_benchmark(
        args.dataset,
        spec=RunSpec(
            label="baseline",
            scheme=args.scheme,
            metric=args.metric,
            min_techniques=args.min_techniques,
            coverage_correction=args.coverage_correction,
            fraction=args.fraction,
            repeats=args.repeats,
            seed=args.seed,
        ),
    )
    print_report(report)
    print(f"\nreport: {paths.Workspace.get(args.dataset).evaluation_report}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
