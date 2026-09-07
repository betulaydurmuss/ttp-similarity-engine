"""Run the retrieval benchmark and write the report.

Run::

    python -m ttp_similarity.evaluation.benchmark --dataset mock
    python -m ttp_similarity.evaluation.benchmark --dataset mock --sizes 3 5 10 --seed 42

Outputs (into ``outputs/reports/<dataset>/``):

``evaluation.json``
    Aggregate :class:`~ttp_similarity.schema.EvaluationReport`.
``evaluation_trials.csv``
    One row per trial, so a failure can be inspected individually.

Owner: evaluation module.
"""

from __future__ import annotations

import argparse
from typing import Sequence

from .. import config, paths, storage
from ..schema import EvaluationReport, EvaluationTrial
from ..engine import loading
from . import metrics, sampling


def run_trial(spec: sampling.TrialSpec, artifacts, top_k: int) -> EvaluationTrial:
    """Execute one planned trial against the engine.

    Args:
        spec: The planned trial.
        artifacts: Pre-loaded :class:`~ttp_similarity.schema.EngineArtifacts`.
            Loaded once by the caller -- reloading per trial would dominate the
            runtime.
        top_k: Candidate list length; the true actor's rank is ``-1`` when it
            falls outside this.

    Returns:
        The executed :class:`~ttp_similarity.schema.EvaluationTrial`.
    """
    # TODO(eval): result = query.query_techniques(spec.technique_ids, artifacts,
    #   top_k=top_k)
    # TODO(eval): rank = 1-based index of spec.actor_id among result.candidates,
    #   else -1. Do NOT fall back to "closest name match" -- a miss is a miss.
    # TODO(eval): carry result.confidence.level through so the calibration
    #   breakdown can be computed.
    raise NotImplementedError("run_trial")


def run_benchmark(
    dataset: str = paths.DEFAULT_DATASET,
    *,
    sample_sizes: Sequence[int] = config.EVAL_SAMPLE_SIZES,
    trials_per_actor: int = config.EVAL_TRIALS_PER_ACTOR,
    seed: int = config.EVAL_RANDOM_SEED,
    top_k: int = config.QUERY_TOP_K,
) -> EvaluationReport:
    """Run the full benchmark over a built dataset.

    Steps:
        1. Load the engine once (:func:`~ttp_similarity.engine.loading.load_engine`).
        2. Plan trials (:func:`~ttp_similarity.evaluation.sampling.build_trial_plan`).
        3. Execute each via :func:`run_trial`.
        4. Aggregate with :mod:`ttp_similarity.evaluation.metrics`.
        5. Write ``evaluation.json`` and ``evaluation_trials.csv``.

    Args:
        dataset: Workspace to evaluate.
        sample_sizes: Query sizes to sweep.
        trials_per_actor: Draws per actor per size.
        seed: RNG seed.
        top_k: Candidate list length.

    Returns:
        The aggregate report (also written to disk).

    Raises:
        ttp_similarity.storage.ArtifactMissingError: If the engine has not been
            built for ``dataset``.
    """
    # TODO(eval): artifacts = loading.load_engine(dataset, with_similarity=False)
    # TODO(eval): plan = sampling.build_trial_plan(artifacts.actors, sample_sizes,
    #   trials_per_actor, seed); print sampling.plan_summary(plan)
    # TODO(eval): trials = [run_trial(spec, artifacts, top_k) for spec in plan]
    # TODO(eval): assemble EvaluationReport from the metrics module, then
    #   write_report(report, trials, workspace)
    # TODO(eval): record `seed` and the dataset manifest's attack_version in
    #   `notes` -- a benchmark number without its ATT&CK version is not
    #   comparable to the next one.
    raise NotImplementedError("run_benchmark")


def write_report(
    report: EvaluationReport,
    trials: Sequence[EvaluationTrial],
    workspace: paths.Workspace,
) -> paths.Workspace:
    """Persist the aggregate report and the per-trial table.

    Args:
        report: Aggregate metrics.
        trials: Executed trials.
        workspace: Destination workspace.

    Returns:
        The workspace that was written.
    """
    # TODO(eval): storage.write_json(workspace.evaluation_report, report.to_dict())
    # TODO(eval): pd.DataFrame([t.to_row() for t in trials]) ->
    #   storage.write_dataframe(..., workspace.evaluation_trials,
    #   EVALUATION_TRIAL_COLUMNS)
    raise NotImplementedError("write_report")


def print_report(report: EvaluationReport) -> None:
    """Print the headline table to stdout.

    Args:
        report: Aggregate metrics.
    """
    print(f"dataset: {report.dataset}   trials: {report.n_trials}   seed: {report.seed}")
    print(f"  top-1: {report.top1_accuracy:.3f}")
    print(f"  top-3: {report.top3_accuracy:.3f}")
    print(f"  MRR  : {report.mean_reciprocal_rank:.3f}")
    if report.by_sample_size:
        print("  by query size:")
        for size, row in sorted(report.by_sample_size.items()):
            print(f"    n={size:>3}  top1={row['top1']:.3f}  top3={row['top3']:.3f}")
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
    parser.add_argument("--dataset", default=paths.DEFAULT_DATASET)
    parser.add_argument(
        "--sizes", type=int, nargs="+", default=list(config.EVAL_SAMPLE_SIZES)
    )
    parser.add_argument("--trials", type=int, default=config.EVAL_TRIALS_PER_ACTOR)
    parser.add_argument("--seed", type=int, default=config.EVAL_RANDOM_SEED)
    parser.add_argument("--top-k", type=int, default=config.QUERY_TOP_K)
    args = parser.parse_args(argv)

    config.validate()
    report = run_benchmark(
        args.dataset,
        sample_sizes=args.sizes,
        trials_per_actor=args.trials,
        seed=args.seed,
        top_k=args.top_k,
    )
    print_report(report)
    print(f"\nreport: {paths.Workspace.get(args.dataset).evaluation_report}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
