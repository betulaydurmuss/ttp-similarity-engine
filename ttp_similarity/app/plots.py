"""Figure builders. Pure matplotlib/seaborn -- no Streamlit calls in here.

Keeping the figures free of ``st.*`` means the same function can render into
the UI and be saved to ``outputs/figures/<dataset>/`` for the written report.

Owner: app module.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

from .. import config
from ..schema import SimilarityMatrix


def similarity_heatmap(
    similarity: SimilarityMatrix,
    actor_names: dict[str, str],
    order: list[int] | None = None,
    *,
    annotate: bool = False,
    cmap: str = config.HEATMAP_COLORMAP,
) -> Figure:
    """Render the actor-vs-actor similarity matrix.

    Args:
        similarity: Actor similarity matrix.
        actor_names: ``{actor_id: display name}`` for the tick labels.
        order: Row/column display order from
            :func:`ttp_similarity.engine.clustering.order_for_heatmap`. Without
            it the plot is in id order and shows no structure.
        annotate: Print the value inside each cell. Only legible up to ~20
            actors, so the caller decides.
        cmap: Colormap name.

    Returns:
        A matplotlib :class:`~matplotlib.figure.Figure`.
    """
    # TODO(app): reorder matrix and labels by `order`; seaborn.heatmap with
    #   vmin=0, vmax=1, square=True; rotate the x tick labels; tight_layout.
    # TODO(app): with the real ATT&CK build this is ~150x150 -- switch to no
    #   annotations and a larger figsize above ~30 actors.
    raise NotImplementedError("similarity_heatmap")


def technique_frequency_plot(frequency: pd.DataFrame, top_n: int = 25) -> Figure:
    """Bar chart of the most widely used techniques.

    Shows the commodity end of the distribution -- the techniques the weighting
    is supposed to discount.

    Args:
        frequency: ``technique_frequency.csv`` frame.
        top_n: How many techniques to show.

    Returns:
        A matplotlib figure.
    """
    # TODO(app): frequency.head(top_n), horizontal barh with
    #   "T1059 Command and Scripting Interpreter" style labels.
    raise NotImplementedError("technique_frequency_plot")


def weight_distribution_plot(weights: pd.DataFrame) -> Figure:
    """Histogram of technique weights.

    A build sanity check: a healthy dataset has a long right tail of rare,
    heavily weighted techniques. A single spike means the weighting collapsed.

    Args:
        weights: ``weights.csv`` frame.

    Returns:
        A matplotlib figure.
    """
    # TODO(app): histogram of the weight column, with the median marked.
    raise NotImplementedError("weight_distribution_plot")


def evaluation_curve(by_sample_size: dict) -> Figure:
    """Top-1 / top-3 accuracy against query size.

    Answers the question an analyst actually asks: "how many techniques do I
    need to observe before this tool is useful?"

    Args:
        by_sample_size: ``EvaluationReport.by_sample_size``.

    Returns:
        A matplotlib figure.
    """
    # TODO(app): two lines over the sorted sample sizes, y limited to [0, 1].
    raise NotImplementedError("evaluation_curve")


def save_figure(figure: Figure, path: Path, dpi: int = 150) -> Path:
    """Write a figure to disk, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
