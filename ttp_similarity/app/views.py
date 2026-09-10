"""Screen renderers. Each takes the loaded artefacts and draws one tab.

Three screens, matching the agreed scope:

* **Benzerlik ısı haritası** -- the actor-vs-actor matrix. 149 actors do not fit
  on a screen, so the matrix is always a subset: either one actor plus its
  nearest neighbours, or a hand-picked set.
* **TTP sorgu** -- paste technique ids, get ranked candidates, the confidence
  badge with all three components, the evidence behind the top candidate and
  the query techniques it does *not* cover.
* **Vaka çalışması** -- one actor's nearest neighbours with the mean weight of
  the techniques each pair shares. That column is the interpretation: a high
  score built on commodity overlap means something different from the same
  score built on rare overlap.

The cluster-profile panel is deliberately absent -- ``cluster_profile()`` is not
implemented.

No scoring happens here. Everything comes from the engine, so the CLI and the UI
cannot disagree. UI strings are Turkish; code and docstrings are English.

Owner: app module.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np
import pandas as pd
import streamlit as st

from .. import config, paths
from ..engine import clustering
from ..engine import query as query_mod
from ..schema import Actor, EngineArtifacts, QueryResult, SimilarityMatrix
from . import loaders, plots

#: Badge colour per confidence level, for the query screen.
CONFIDENCE_COLORS = {"high": "#1a7f37", "medium": "#b58105", "low": "#a40e26"}
CONFIDENCE_LABELS_TR = {"high": "YÜKSEK", "medium": "ORTA", "low": "DÜŞÜK"}

#: A component at or below this is called out as the weak one.
WEAK_COMPONENT = 0.34

#: Demo presets: APT40 (G0065) at both ends of its weight distribution. Loaded
#: with one click so the contrast can be shown live without typing.
PRESET_APT40_DISTINCTIVE = [
    "T1197", "T1534", "T1559", "T1595", "T1572", "T1586", "T1546", "T1589",
]
PRESET_APT40_COMMODITY = [
    "T1059", "T1204", "T1566", "T1027", "T1105", "T1078", "T1583", "T1021",
]

#: Session-state key backing the query text area.
QUERY_KEY = "query_text"


def pending(function_name: str, note: str = "") -> None:
    """Placeholder shown where a renderer is not implemented yet.

    Args:
        function_name: Fully qualified name of the function to be written.
        note: Extra context for whoever picks it up.
    """
    st.info(f"Henüz uygulanmadı: `{function_name}`" + (f"\n\n{note}" if note else ""))


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


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _actor_labels(artifacts: EngineArtifacts) -> dict[str, str]:
    """``actor_id -> "Name (G0065)"`` for selectors."""
    return {a.actor_id: f"{a.name} ({a.actor_id})" for a in artifacts.actors}


def _actor_names(artifacts: EngineArtifacts) -> dict[str, str]:
    """``actor_id -> display name`` for plot tick labels."""
    return {a.actor_id: a.name for a in artifacts.actors}


def _subset(similarity: SimilarityMatrix, actor_ids: Sequence[str]) -> SimilarityMatrix:
    """Square sub-matrix over ``actor_ids``, order preserved.

    Args:
        similarity: The full matrix.
        actor_ids: Actors to keep.

    Returns:
        A :class:`~ttp_similarity.schema.SimilarityMatrix` over the subset.
    """
    index = {a: i for i, a in enumerate(similarity.actor_ids)}
    positions = [index[a] for a in actor_ids if a in index]
    return SimilarityMatrix(
        actor_ids=tuple(similarity.actor_ids[p] for p in positions),
        matrix=similarity.matrix[np.ix_(positions, positions)],
        metric=similarity.metric,
    )


def _neighbours(
    actor: Actor, artifacts: EngineArtifacts, limit: int
) -> pd.DataFrame:
    """Nearest actors with the shared-technique diagnostics.

    ``ortak ağırlık ort.`` is the interpretation column: two pairs can share the
    same number of techniques and mean very different things depending on
    whether those techniques are rare or universal.

    Args:
        actor: The subject.
        artifacts: Loaded artefacts; requires ``artifacts.similarity``.
        limit: How many neighbours to return.

    Returns:
        A display-ready DataFrame, best first.
    """
    similarity = artifacts.similarity
    by_id = artifacts.actor_by_id()
    index = {a: i for i, a in enumerate(similarity.actor_ids)}
    own = set(actor.technique_ids)

    row = similarity.matrix[index[actor.actor_id]]
    order = [j for j in np.argsort(row)[::-1] if j != index[actor.actor_id]][:limit]

    rows = []
    for rank, position in enumerate(order, start=1):
        other = by_id[similarity.actor_ids[position]]
        shared = sorted(own & set(other.technique_ids))
        weights = [artifacts.weights.get(t, 0.0) for t in shared]
        rows.append(
            {
                "#": rank,
                "aktör": other.name,
                "id": other.actor_id,
                "skor": round(float(row[position]), 4),
                "teknik": len(other.technique_ids),
                "ortak": len(shared),
                "ortak ağırlık ort.": round(float(np.mean(weights)), 3) if shared else 0.0,
                "ortak ağırlık maks.": round(float(np.max(weights)), 2) if shared else 0.0,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def render_sidebar(datasets: list[str]) -> str:
    """Dataset selector plus build provenance.

    Args:
        datasets: Dataset names with a build on disk.

    Returns:
        The selected dataset name.
    """
    st.sidebar.header("Veri seti")
    default = datasets.index(paths.DEFAULT_DATASET) if paths.DEFAULT_DATASET in datasets else 0
    dataset = st.sidebar.selectbox("Seçin", datasets, index=default)

    summary = loaders.get_manifest_summary(dataset)
    if summary:
        st.sidebar.caption("Yapı bilgisi")
        st.sidebar.table(pd.DataFrame({"değer": summary}))

    st.sidebar.caption("Skorlama ayarları")
    st.sidebar.table(
        pd.DataFrame(
            {
                "değer": {
                    "Ağırlıklandırma": config.WEIGHTING_SCHEME,
                    "Metrik": config.SIMILARITY_METRIC,
                    "Kapsam düzeltmesi": "açık" if config.COVERAGE_CORRECTION else "kapalı",
                    "Güven eşikleri": f"{config.CONFIDENCE_HIGH_THRESHOLD} / "
                    f"{config.CONFIDENCE_MEDIUM_THRESHOLD}",
                }
            }
        )
    )

    if st.sidebar.button("Önbelleği temizle"):
        loaders.clear_caches()
        st.rerun()
    return dataset


# --------------------------------------------------------------------------- #
# 1) Heatmap
# --------------------------------------------------------------------------- #
def render_heatmap_tab(artifacts: EngineArtifacts) -> None:
    """Similarity heatmap screen.

    The full matrix is unreadable at 149 actors, so a subset is always chosen:
    either one actor plus its nearest neighbours, or a hand-picked set. Rows are
    ordered by the clustering dendrogram, without which a heatmap shows nothing.

    Args:
        artifacts: Loaded engine artefacts. ``artifacts.similarity`` is ``None``
            when the similarity stage has not run -- show a hint, do not crash.
    """
    if artifacts.similarity is None:
        st.warning(
            "Benzerlik matrisi bulunamadı. Çalıştırın: "
            f"`python -m ttp_similarity.engine.build --dataset {artifacts.dataset}`"
        )
        return

    labels = _actor_labels(artifacts)
    names = _actor_names(artifacts)
    total = len(artifacts.actors)

    mode = st.radio(
        "Gösterilecek aktörler",
        ["Bir aktör ve en yakın komşuları", "Aktörleri elle seç", "En yoğun benzerlik gösteren N aktör"],
        horizontal=True,
    )

    if mode == "Bir aktör ve en yakın komşuları":
        column_left, column_right = st.columns([3, 1])
        focus = column_left.selectbox(
            "Odak aktör", list(labels), format_func=lambda a: labels[a]
        )
        count = column_right.slider("Komşu sayısı", 5, 40, 15)
        similarity = artifacts.similarity
        index = {a: i for i, a in enumerate(similarity.actor_ids)}
        row = similarity.matrix[index[focus]]
        order = [j for j in np.argsort(row)[::-1] if j != index[focus]][:count]
        selected = [focus] + [similarity.actor_ids[j] for j in order]

    elif mode == "Aktörleri elle seç":
        selected = st.multiselect(
            "Aktörler",
            list(labels),
            default=list(labels)[:12],
            format_func=lambda a: labels[a],
        )
        if len(selected) < 2:
            st.info("En az iki aktör seçin.")
            return

    else:
        count = st.slider("Aktör sayısı", 5, min(60, total), 25)
        # Rank by mean similarity to everyone else: the actors that sit in the
        # dense middle of the space, which is where the block structure shows.
        matrix = artifacts.similarity.matrix
        n = len(artifacts.similarity.actor_ids)
        mean_similarity = (matrix.sum(axis=1) - 1.0) / max(n - 1, 1)
        top = np.argsort(mean_similarity)[::-1][:count]
        selected = [artifacts.similarity.actor_ids[i] for i in top]

    subset = _subset(artifacts.similarity, selected)
    try:
        order = clustering.order_for_heatmap(subset)
    except Exception:  # noqa: BLE001 - ordering is a nicety, never fatal
        order = None

    figure = plots.similarity_heatmap(subset, names, order)
    st.pyplot(figure, width="stretch")

    values = subset.matrix[np.triu_indices(len(subset.actor_ids), k=1)]
    if values.size:
        left, middle, right = st.columns(3)
        left.metric("Seçili aktör", len(subset.actor_ids))
        middle.metric("Ortalama benzerlik", f"{values.mean():.3f}")
        right.metric("En yüksek çift", f"{values.max():.3f}")

    with st.expander("Bu görünümdeki en benzer çiftler"):
        st.dataframe(_top_pairs(subset, names), hide_index=True, width="stretch")


def _top_pairs(similarity: SimilarityMatrix, names: dict[str, str], limit: int = 15):
    """The strongest pairs inside the displayed subset."""
    n = len(similarity.actor_ids)
    rows = []
    upper = np.triu_indices(n, k=1)
    for position in np.argsort(similarity.matrix[upper])[::-1][:limit]:
        i, j = upper[0][position], upper[1][position]
        rows.append(
            {
                "aktör A": names.get(similarity.actor_ids[i], similarity.actor_ids[i]),
                "aktör B": names.get(similarity.actor_ids[j], similarity.actor_ids[j]),
                "skor": round(float(similarity.matrix[i, j]), 4),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 2) Query
# --------------------------------------------------------------------------- #
def _load_preset(technique_ids: Sequence[str]) -> None:
    """Put a demo preset into the query box and restart the script.

    Assigning to the text area's session-state key is Streamlit's documented way
    to set a widget programmatically, but the widget below has already been
    registered with the old value for the remainder of this run. The rerun
    starts a clean run in which the box and the results underneath it agree --
    which is the whole point of a one-click demo button.
    """
    st.session_state[QUERY_KEY] = " ".join(technique_ids)
    st.rerun()


def render_query_tab(artifacts: EngineArtifacts) -> None:
    """TTP query screen -- the main deliverable of the UI.

    Args:
        artifacts: Loaded engine artefacts.
    """
    st.caption(
        "Teknik kimliklerini boşluk, virgül veya satır sonuyla ayırarak yapıştırın. "
        "Alt teknikler ana tekniğe indirgenir (T1059.001 → T1059)."
    )

    left, right, _ = st.columns([2, 2, 3])
    if left.button("APT40 — ayırt edici 8 teknik", width="stretch"):
        _load_preset(PRESET_APT40_DISTINCTIVE)
    if right.button("APT40 — emtia 8 teknik", width="stretch"):
        _load_preset(PRESET_APT40_COMMODITY)

    raw = st.text_area(
        "Teknik listesi",
        key=QUERY_KEY,
        height=110,
        placeholder="T1566 T1078 T1047 T1003 ...",
    )
    top_k = st.slider("Kaç aday gösterilsin", 3, 25, config.QUERY_TOP_K)

    if not str(raw).strip():
        st.info("Bir teknik listesi girin veya yukarıdaki hazır setlerden birini yükleyin.")
        return

    result = query_mod.query_techniques(raw, artifacts, top_k=top_k)

    if result.unknown_technique_ids:
        st.warning(
            "Bu veri setinde bulunmayan teknikler (skorlamaya girmedi): "
            + ", ".join(result.unknown_technique_ids)
        )
    if not result.candidates:
        st.error("Skorlanabilir teknik kalmadı; sonuç üretilemedi.")
        return

    st.caption(
        f"Skorlanan teknik: {len(result.query_technique_ids) - len(result.unknown_technique_ids)}"
        f" / {len(result.query_technique_ids)}"
    )

    render_confidence(result)
    st.subheader("Aday aktörler")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "#": c.rank,
                    "aktör": c.actor_name,
                    "id": c.actor_id,
                    "skor": round(c.score, 4),
                    "eşleşen": len(c.matched_technique_ids),
                    "eşleşmeyen": len(c.missing_technique_ids),
                }
                for c in result.candidates
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    render_evidence(result)


def render_confidence(result: QueryResult) -> None:
    """Confidence badge plus its three components.

    A bare percentage invites false certainty, so all three components are shown
    and the weak ones are called out by name.

    Args:
        result: The query result being displayed.
    """
    breakdown = result.confidence
    level = breakdown.level.value
    colour = CONFIDENCE_COLORS[level]

    st.markdown(
        f"### Güven: <span style='color:{colour}'>{CONFIDENCE_LABELS_TR[level]}</span> "
        f"<span style='color:#888;font-size:0.7em'>({breakdown.score:.3f})</span>",
        unsafe_allow_html=True,
    )

    components = [
        ("Nadirlik", breakdown.rarity, 0.40, "Eşleşen teknikler ne kadar ayırt edici"),
        ("Fark", breakdown.margin, 0.35, "1. aday 2. adaydan ne kadar ayrışıyor"),
        ("Yeterlilik", breakdown.sufficiency, 0.25, "Karar için yeterli teknik girildi mi"),
    ]
    for column, (name, value, weight, help_text) in zip(st.columns(3), components):
        weak = value <= WEAK_COMPONENT
        column.metric(
            f"{'⚠ ' if weak else ''}{name} ({weight:.2f})",
            f"{value:.3f}",
            help=help_text,
        )
        column.progress(min(max(value, 0.0), 1.0))

    try:
        from ..engine import confidence as confidence_mod

        for reason in confidence_mod.explain(breakdown):
            st.caption(f"• {reason}")
    except NotImplementedError:
        pass


def render_evidence(result: QueryResult) -> None:
    """Per-candidate breakdown of which techniques produced the score.

    Args:
        result: The query result being displayed.
    """
    st.subheader("Kanıt dökümü")
    for candidate in result.candidates:
        title = (
            f"{candidate.rank}. {candidate.actor_name} — {candidate.score:.4f} "
            f"({len(candidate.matched_technique_ids)} eşleşen)"
        )
        with st.expander(title, expanded=candidate.rank == 1):
            if candidate.evidence:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "teknik": e.technique_id,
                                "ad": e.technique_name,
                                "ağırlık": round(e.weight, 3),
                                "katkı %": round(e.contribution * 100, 1),
                            }
                            for e in candidate.evidence
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.caption("Bu adayda eşleşen teknik yok.")

            if candidate.missing_technique_ids:
                st.caption(
                    "Bu aktörde görülmeyen sorgu teknikleri: "
                    + ", ".join(candidate.missing_technique_ids)
                )
            else:
                st.caption("Sorgudaki her teknik bu aktörde görülmüş.")


# --------------------------------------------------------------------------- #
# 3) Case study
# --------------------------------------------------------------------------- #
def render_case_study_tab(artifacts: EngineArtifacts) -> None:
    """One actor's profile and neighbourhood.

    Args:
        artifacts: Loaded engine artefacts.
    """
    if artifacts.similarity is None:
        st.warning(
            "Benzerlik matrisi bulunamadı. Çalıştırın: "
            f"`python -m ttp_similarity.engine.build --dataset {artifacts.dataset}`"
        )
        return

    labels = _actor_labels(artifacts)
    by_id = artifacts.actor_by_id()
    default = "G0065" if "G0065" in labels else list(labels)[0]

    left, right = st.columns([3, 1])
    actor_id = left.selectbox(
        "Aktör",
        list(labels),
        index=list(labels).index(default),
        format_func=lambda a: labels[a],
    )
    limit = right.slider("Komşu sayısı", 5, 30, 15)
    actor = by_id[actor_id]

    first, second, third = st.columns(3)
    first.metric("Teknik sayısı", len(actor.technique_ids))
    second.metric("Takma ad", len(actor.aliases))
    third.metric("Küme", artifacts.clusters.get(actor_id, "-") if artifacts.clusters else "-")
    if actor.aliases:
        st.caption("Takma adlar: " + ", ".join(actor.aliases))

    st.subheader("En benzer aktörler")
    st.caption(
        "**ortak ağırlık ort.** yorumun merkezi: benzerlik nadir tekniklerden mi "
        "yoksa emtia tekniklerden mi geliyor?"
    )
    st.dataframe(
        _neighbours(actor, artifacts, limit), hide_index=True, width="stretch"
    )

    st.subheader("Teknikleri, ağırlığa göre")
    frequency = loaders.get_technique_frequency(artifacts.dataset)
    counts = dict(zip(frequency["technique_id"], frequency["actor_count"]))
    table = pd.DataFrame(
        [
            {
                "teknik": tid,
                "ad": artifacts.technique_names.get(tid, tid),
                "ağırlık": round(artifacts.weights.get(tid, float("nan")), 3),
                "kaç aktörde": int(counts.get(tid, 0)),
            }
            for tid in actor.technique_ids
        ]
    ).sort_values("ağırlık", ascending=False)
    st.dataframe(table, hide_index=True, width="stretch")


def render_setup_help(datasets: list[str]) -> None:
    """Shown when nothing has been built yet.

    Args:
        datasets: Currently available datasets (empty in this branch).
    """
    st.title("TTP Similarity Engine")
    st.error("Kullanılabilir bir veri seti bulunamadı.")
    st.markdown(
        "Önce aşağıdaki komutları çalıştırın:\n\n"
        "```bash\n"
        "# 1) Sentetik veri seti (gerçek veri olmadan denemek için)\n"
        "python -m ttp_similarity.data.mock_dataset\n\n"
        "# 2) Motor artefaktları\n"
        f"python -m ttp_similarity.engine.build --dataset {paths.MOCK_DATASET}\n"
        "```"
    )
    render_disclaimer()
