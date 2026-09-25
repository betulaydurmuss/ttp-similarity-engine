"""Figure builders. Pure matplotlib/seaborn -- no Streamlit calls in here.

Keeping the figures free of ``st.*`` means the same function can render into
the UI and be saved to ``outputs/figures/<dataset>/`` for the written report.

Owner: app module.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: the UI never needs an interactive backend

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from .. import config  # noqa: E402
from ..schema import SimilarityMatrix  # noqa: E402

#: Above this many actors the per-cell numbers stop being legible.
ANNOTATION_LIMIT = 20

#: Console colormap, built from the palette in
#: :mod:`ttp_similarity.app.theme` so the matrix belongs to the same design as
#: the rest of the page. Runs from the page background up through the accent, so
#: a weak similarity reads as "empty" rather than as a colour of its own.
DARK_CMAP = LinearSegmentedColormap.from_list(
    "ttp_dark",
    ["#0b0f14", "#12262e", "#17414a", "#1d6a6b", "#2f9f93", "#4fd1c5", "#b4efe8"],
)

#: Palette for the dark figure furniture (ticks, title, colourbar).
_DARK_INK = {"text": "#e3e9f2", "muted": "#8b97a8", "line": "#1f2937"}


def similarity_heatmap(
    similarity: SimilarityMatrix,
    actor_names: dict[str, str],
    order: list[int] | None = None,
    *,
    annotate: bool | None = None,
    cmap: str | None = None,
    dark: bool = False,
) -> Figure:
    """Render the actor-vs-actor similarity matrix.

    Args:
        similarity: Actor similarity matrix.
        actor_names: ``{actor_id: display name}`` for the tick labels.
        order: Row/column display order from
            :func:`ttp_similarity.engine.clustering.order_for_heatmap`. Without
            it the plot is in id order and shows no structure.
        annotate: Print the value inside each cell. ``None`` decides from the
            matrix size -- annotations stop being readable past ~20 actors.
        cmap: Colormap name. ``None`` uses :data:`DARK_CMAP` when ``dark`` is
            set, otherwise :data:`ttp_similarity.config.HEATMAP_COLORMAP`.
        dark: Render for the console: transparent figure, light ink, accent
            colormap. Left ``False`` for figures saved to
            ``outputs/figures/`` -- a dark plot is wrong in a printed report.

    Returns:
        A matplotlib :class:`~matplotlib.figure.Figure`.
    """
    labels = [actor_names.get(a, a) for a in similarity.actor_ids]
    matrix = similarity.matrix

    if order:
        matrix = matrix[np.ix_(order, order)]
        labels = [labels[i] for i in order]

    count = len(labels)
    if annotate is None:
        annotate = count <= ANNOTATION_LIMIT
    if cmap is None:
        cmap = DARK_CMAP if dark else config.HEATMAP_COLORMAP

    side = max(4.0, min(0.42 * count + 2.0, 22.0))
    figure, axes = plt.subplots(figsize=(side, side * 0.85))
    sns.heatmap(
        matrix,
        xticklabels=labels,
        yticklabels=labels,
        vmin=0.0,
        vmax=1.0,
        cmap=cmap,
        square=True,
        annot=annotate,
        fmt=".2f",
        annot_kws={"size": 7, "color": _DARK_INK["text"] if dark else None},
        linewidths=0.3 if count <= 40 else 0.0,
        linecolor=_DARK_INK["line"] if dark else "white",
        cbar_kws={"label": "benzerlik", "shrink": 0.6},
        ax=axes,
    )
    axes.set_xticklabels(axes.get_xticklabels(), rotation=90, fontsize=8)
    axes.set_yticklabels(axes.get_yticklabels(), rotation=0, fontsize=8)
    axes.set_title(f"Aktör benzerlik matrisi ({count} aktör, {similarity.metric})")
    if dark:
        _apply_dark_ink(figure, axes)
    figure.tight_layout()
    return figure


def _apply_dark_ink(figure: Figure, axes) -> None:
    """Recolour a finished figure for the dark console.

    Applied after plotting rather than through a global rcParams style so that
    the same module can still produce light figures for the written report in
    the same process.

    Args:
        figure: The figure to recolour.
        axes: Its main axes. Any colourbar is found via ``figure.axes``.
    """
    figure.patch.set_alpha(0.0)
    axes.set_facecolor("#0b0f14")
    axes.title.set_color(_DARK_INK["text"])
    axes.title.set_fontsize(10)
    for label in (*axes.get_xticklabels(), *axes.get_yticklabels()):
        label.set_color(_DARK_INK["muted"])
    for spine in axes.spines.values():
        spine.set_color(_DARK_INK["line"])
    # seaborn appends the colourbar as an extra axes on the same figure.
    for extra in figure.axes[1:]:
        extra.tick_params(colors=_DARK_INK["muted"], labelsize=7)
        extra.yaxis.label.set_color(_DARK_INK["muted"])
        extra.yaxis.label.set_fontsize(8)
        for spine in extra.spines.values():
            spine.set_color(_DARK_INK["line"])


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
    head = frequency.nlargest(top_n, "actor_count").iloc[::-1]
    labels = [
        f"{row.technique_id}  {str(row.technique_name)[:38]}" for row in head.itertuples()
    ]
    figure, axes = plt.subplots(figsize=(9, max(3.0, 0.32 * len(head))))
    axes.barh(labels, head["actor_count"], color="#4c72b0")
    axes.set_xlabel("kaç aktörde geçiyor")
    axes.set_title(f"En yaygın {len(head)} teknik")
    axes.tick_params(axis="y", labelsize=8)
    figure.tight_layout()
    return figure


def weight_distribution_plot(weights: pd.DataFrame) -> Figure:
    """Histogram of technique weights.

    A build sanity check: a healthy dataset has a long right tail of rare,
    heavily weighted techniques. A single spike means the weighting collapsed.

    Args:
        weights: ``weights.csv`` frame.

    Returns:
        A matplotlib figure.
    """
    values = weights["weight"].astype(float)
    figure, axes = plt.subplots(figsize=(8, 4))
    axes.hist(values, bins=30, color="#4c72b0", edgecolor="white")
    axes.axvline(
        values.median(),
        color="#c44e52",
        linestyle="--",
        label=f"medyan {values.median():.2f}",
    )
    axes.set_xlabel("teknik ağırlığı")
    axes.set_ylabel("teknik sayısı")
    axes.set_title("Ağırlık dağılımı")
    axes.legend()
    figure.tight_layout()
    return figure


def evaluation_curve(by_sample_size: dict) -> Figure:
    """Top-1 / top-3 accuracy against query size.

    Answers the question an analyst actually asks: "how many techniques do I
    need to observe before this tool is useful?"

    Args:
        by_sample_size: ``EvaluationReport.by_sample_size``.

    Returns:
        A matplotlib figure.
    """
    sizes = sorted(int(k) for k in by_sample_size)
    top1 = [by_sample_size[k]["top1"] for k in sizes]
    top3 = [by_sample_size[k]["top3"] for k in sizes]

    figure, axes = plt.subplots(figsize=(7, 4))
    axes.plot(sizes, top1, marker="o", label="top-1")
    axes.plot(sizes, top3, marker="s", label="top-3")
    axes.set_ylim(0.0, 1.02)
    axes.set_xlabel("sorgudaki teknik sayısı")
    axes.set_ylabel("doğruluk")
    axes.set_title("Sorgu boyutuna göre başarım")
    axes.grid(alpha=0.3)
    axes.legend()
    figure.tight_layout()
    return figure


def save_figure(figure: Figure, path: Path, dpi: int = 150) -> Path:
    """Write a figure to disk, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
