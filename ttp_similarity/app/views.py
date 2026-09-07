"""Screen renderers. Each takes the loaded artefacts and draws one tab.

Every renderer degrades gracefully: an unimplemented piece shows a notice naming
the function still to be written, instead of a traceback. That is what lets the
app owner build and demo the layout while the engine is still being written.

UI strings are Turkish (the team's working language); code and docstrings are
English.

Owner: app module.
"""

from __future__ import annotations

from typing import Callable

import streamlit as st

from .. import config, paths
from ..schema import EngineArtifacts, QueryResult

#: Badge colour per confidence level, for the query screen.
CONFIDENCE_COLORS = {"high": "#1a7f37", "medium": "#b58105", "low": "#a40e26"}
CONFIDENCE_LABELS_TR = {"high": "YUKSEK", "medium": "ORTA", "low": "DUSUK"}


def pending(function_name: str, note: str = "") -> None:
    """Placeholder shown where a renderer is not implemented yet.

    Args:
        function_name: Fully qualified name of the function to be written.
        note: Extra context for whoever picks it up.
    """
    st.info(f"Henuz uygulanmadi: `{function_name}`" + (f"\n\n{note}" if note else ""))


def guard(render: Callable[[], None], function_name: str) -> None:
    """Run a renderer, turning ``NotImplementedError`` into a placeholder.

    Args:
        render: Zero-argument renderer callable.
        function_name: Name shown in the placeholder when it is not ready.
    """
    try:
        render()
    except NotImplementedError:
        pending(function_name)


def render_disclaimer() -> None:
    """The non-attribution notice. Shown on every screen, not tucked in an About tab."""
    st.warning(config.DISCLAIMER, icon=":material/info:")


def render_sidebar(datasets: list[str]) -> str:
    """Dataset selector plus build provenance.

    Args:
        datasets: Dataset names with a build on disk.

    Returns:
        The selected dataset name.
    """
    # TODO(app): st.sidebar.selectbox over `datasets`, defaulting to
    #   paths.DEFAULT_DATASET when present; below it render
    #   loaders.get_manifest_summary(dataset) as a small key/value table so the
    #   user always sees which ATT&CK snapshot they are looking at.
    # TODO(app): add a "onbellegi temizle" button wired to loaders.clear_caches().
    raise NotImplementedError("render_sidebar")


def render_heatmap_tab(artifacts: EngineArtifacts) -> None:
    """Similarity heatmap screen.

    Layout:
        * Cluster-ordered heatmap (``plots.similarity_heatmap``).
        * Actor selector -> its closest peers
          (``engine.similarity.nearest_actors``) as a small table.
        * Expander with the cluster profile
          (``engine.clustering.cluster_profile``), so a cluster can be described
          in words rather than only seen as a colour block.

    Args:
        artifacts: Loaded engine artefacts. ``artifacts.similarity`` is ``None``
            when the similarity stage has not run -- show a hint, do not crash.
    """
    # TODO(app): if artifacts.similarity is None -> st.warning naming the
    #   command `python -m ttp_similarity.engine.build --dataset <ds>`; return.
    # TODO(app): order = clustering.order_for_heatmap(artifacts.similarity,
    #   artifacts.clusters); figure = plots.similarity_heatmap(...);
    #   st.pyplot(figure).
    # TODO(app): add a "figuru kaydet" button -> plots.save_figure into
    #   Workspace.figure("similarity_heatmap.png").
    raise NotImplementedError("render_heatmap_tab")


def render_query_tab(artifacts: EngineArtifacts) -> None:
    """TTP query screen -- the main deliverable of the UI.

    Layout:
        * ``st.text_area`` for pasting technique ids, plus a multiselect backed
          by the technique frequency table (shows each technique's actor count,
          so the analyst can see what is rare while composing the query).
        * "Sorgula" button -> ``engine.query.query_techniques``.
        * Unknown ids called out explicitly.
        * Confidence badge with all three components
          (:func:`render_confidence`).
        * Candidate table with rank, actor, score, matched/total counts.
        * Per-candidate expander listing the techniques that drove the score
          (:func:`render_evidence`).

    Args:
        artifacts: Loaded engine artefacts.
    """
    # TODO(app): keep the last result in st.session_state so switching tabs does
    #   not clear it.
    # TODO(app): a "rastgele bir aktorden ornek TTP" button makes the demo
    #   possible in one click -- pull from evaluation.sampling.sample_techniques.
    raise NotImplementedError("render_query_tab")


def render_confidence(result: QueryResult) -> None:
    """Confidence badge plus its three components.

    Shows the level as a coloured badge and rarity / margin / sufficiency as
    three progress bars, with the sentences from
    :func:`ttp_similarity.engine.confidence.explain` underneath. A bare
    percentage invites false certainty; the components say what is weak.

    Args:
        result: The query result being displayed.
    """
    # TODO(app): st.columns(3) with st.progress for each component; colour the
    #   badge via CONFIDENCE_COLORS and label it via CONFIDENCE_LABELS_TR.
    raise NotImplementedError("render_confidence")


def render_evidence(result: QueryResult) -> None:
    """Per-candidate breakdown of which techniques produced the score.

    Args:
        result: The query result being displayed.
    """
    # TODO(app): for each candidate, an st.expander titled
    #   "<rank>. <actor_name> - <score>"; inside, a dataframe of
    #   candidate.evidence (technique id, name, weight, contribution as %),
    #   then the missing_technique_ids as a caption:
    #   "Bu aktorde gorulmeyen teknikler: ...".
    raise NotImplementedError("render_evidence")


def render_dataset_tab(artifacts: EngineArtifacts) -> None:
    """Dataset overview: actor list, technique frequency, weight distribution.

    Not decoration -- this is where a reviewer checks that the input data is
    what they think it is before trusting any similarity number.

    Args:
        artifacts: Loaded engine artefacts.
    """
    # TODO(app): searchable actor table (name, aliases, technique count,
    #   cluster); plots.technique_frequency_plot; plots.weight_distribution_plot.
    raise NotImplementedError("render_dataset_tab")


def render_setup_help(datasets: list[str]) -> None:
    """Shown when nothing has been built yet.

    Args:
        datasets: Currently available datasets (empty in this branch).
    """
    st.title("TTP Similarity Engine")
    st.error("Kullanilabilir bir veri seti bulunamadi.")
    st.markdown(
        "Once asagidaki komutlari calistirin:\n\n"
        "```bash\n"
        "# 1) Sentetik veri seti (gercek veri olmadan denemek icin)\n"
        "python -m ttp_similarity.data.mock_dataset\n\n"
        "# 2) Motor artefaktlari\n"
        f"python -m ttp_similarity.engine.build --dataset {paths.MOCK_DATASET}\n"
        "```"
    )
    render_disclaimer()
