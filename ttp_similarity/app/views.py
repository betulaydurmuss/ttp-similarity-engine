"""Screen renderers. Each takes the loaded artefacts and draws one section.

Three screens, reached from the left rail rather than from tabs:

* **Isı haritası** -- the actor-vs-actor matrix. 149 actors do not fit on a
  screen, so the matrix is always a subset: either one actor plus its nearest
  neighbours, a hand-picked set, or the densest part of the space.
* **TTP sorgu** -- paste technique ids, get ranked candidates, the confidence
  badge with all three components, the evidence behind each candidate and the
  query techniques it does *not* cover.
* **Vaka çalışması** -- one actor's nearest neighbours with the mean weight of
  the techniques each pair shares. That column is the interpretation: a high
  score built on commodity overlap means something different from the same
  score built on rare overlap.

The cluster-profile panel is deliberately absent -- ``cluster_profile()`` is not
implemented.

No scoring happens here. Everything comes from the engine, so the CLI and the UI
cannot disagree. Presentation is likewise not here: every bordered strip, bar and
table comes from :mod:`ttp_similarity.app.theme`, so a screen reads as a list of
what it shows. UI strings are Turkish; code and docstrings are English.

Owner: app module.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np
import streamlit as st

from .. import config, paths
from ..engine import clustering
from ..engine import confidence as confidence_mod
from ..engine import query as query_mod
from ..schema import Actor, EngineArtifacts, QueryResult, SimilarityMatrix
from . import loaders, plots, theme

#: Rail entries: ``(key, label)``. The key is what
#: :func:`render_nav` returns and what ``streamlit_app`` dispatches on.
NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("heatmap", "Isı haritası"),
    ("query", "TTP sorgu"),
    ("case", "Vaka çalışması"),
)

#: Session-state key holding the active rail entry.
NAV_KEY = "nav_section"

#: Session-state key backing the query text area.
QUERY_KEY = "query_text"

#: Demo presets: APT40 (G0065) at both ends of its weight distribution. Loaded
#: with one click so the contrast can be shown live without typing.
PRESET_APT40_DISTINCTIVE = [
    "T1197", "T1534", "T1559", "T1595", "T1572", "T1586", "T1546", "T1589",
]
PRESET_APT40_COMMODITY = [
    "T1059", "T1204", "T1566", "T1027", "T1105", "T1078", "T1583", "T1021",
]


def pending(function_name: str, note: str = "") -> None:
    """Placeholder shown where a renderer is not implemented yet.

    Args:
        function_name: Fully qualified name of the function to be written.
        note: Extra context for whoever picks it up.
    """
    theme.banner(note or "Bu bölüm henüz uygulanmadı.", "warn", code=function_name)


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
    theme.disclaimer(config.DISCLAIMER)


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


def _neighbour_rows(
    actor: Actor, artifacts: EngineArtifacts, limit: int
) -> list[list[object]]:
    """Nearest actors with the shared-technique diagnostics.

    The mean shared weight is the interpretation column: two pairs can share the
    same number of techniques and mean very different things depending on
    whether those techniques are rare or universal.

    Args:
        actor: The subject.
        artifacts: Loaded artefacts; requires ``artifacts.similarity``.
        limit: How many neighbours to return.

    Returns:
        Rows shaped for :func:`ttp_similarity.app.theme.table`, best first.
    """
    similarity = artifacts.similarity
    by_id = artifacts.actor_by_id()
    index = {a: i for i, a in enumerate(similarity.actor_ids)}
    own = set(actor.technique_ids)

    row = similarity.matrix[index[actor.actor_id]]
    order = [j for j in np.argsort(row)[::-1] if j != index[actor.actor_id]][:limit]

    rows: list[list[object]] = []
    for rank, position in enumerate(order, start=1):
        other = by_id[similarity.actor_ids[position]]
        shared = sorted(own & set(other.technique_ids))
        weights = [artifacts.weights.get(t, 0.0) for t in shared]
        rows.append(
            [
                f"{rank:02d}",
                other.name,
                other.actor_id,
                f"{float(row[position]):.4f}",
                len(other.technique_ids),
                len(shared),
                f"{float(np.mean(weights)):.3f}" if shared else "0.000",
                f"{float(np.max(weights)):.2f}" if shared else "0.00",
            ]
        )
    return rows


# --------------------------------------------------------------------------- #
# Left rail
# --------------------------------------------------------------------------- #
def render_nav() -> str:
    """Draw the rail's navigation and return the active section key.

    Buttons rather than ``st.radio``: a button's ``kind`` attribute is a stable
    styling hook across Streamlit releases, whereas a radio group's internals
    are not, and the active entry needs a genuinely different look (accent rule
    on the left edge) rather than a dot.

    Returns:
        One of the keys in :data:`NAV_ITEMS`.
    """
    active = st.session_state.get(NAV_KEY, NAV_ITEMS[0][0])

    st.sidebar.html(
        '<div style="display:flex;align-items:baseline;gap:.5rem;'
        'padding:0 .85rem .9rem;border-bottom:1px solid #1f2937;margin-bottom:.7rem">'
        '<span style="color:#4fd1c5;font-size:.95rem;line-height:1">&#9670;</span>'
        '<span style="font-size:.66rem;font-weight:700;letter-spacing:.14em;'
        'text-transform:uppercase;color:#8b97a8">TTP Similarity</span></div>'
    )

    for key, label in NAV_ITEMS:
        if st.sidebar.button(
            label,
            key=f"nav_{key}",
            type="primary" if key == active else "secondary",
            width="stretch",
        ):
            st.session_state[NAV_KEY] = key
            st.rerun()
    return active


def render_sidebar(datasets: list[str]) -> str:
    """Dataset selector, build provenance and the effective scoring settings.

    The scoring settings are in the rail on purpose: a similarity number means
    nothing without the weighting scheme and metric that produced it, and the
    CLI prints those too.

    Args:
        datasets: Dataset names with a build on disk.

    Returns:
        The selected dataset name.
    """
    st.sidebar.html('<div class="ttp-rail-h">Veri seti</div>')
    default = (
        datasets.index(paths.DEFAULT_DATASET) if paths.DEFAULT_DATASET in datasets else 0
    )
    dataset = st.sidebar.selectbox(
        "Seçin", datasets, index=default, label_visibility="collapsed"
    )

    summary = loaders.get_manifest_summary(dataset)
    if summary:
        with st.sidebar:
            theme.key_values("Yapı bilgisi", summary)

    with st.sidebar:
        theme.key_values(
            "Skorlama",
            {
                "Ağırlık": config.WEIGHTING_SCHEME,
                "Metrik": config.SIMILARITY_METRIC,
                "Kapsam düzeltmesi": "açık" if config.COVERAGE_CORRECTION else "kapalı",
                "Güven eşikleri": (
                    f"{config.CONFIDENCE_HIGH_THRESHOLD:.2f} / "
                    f"{config.CONFIDENCE_MEDIUM_THRESHOLD:.2f}"
                ),
            },
        )

    st.sidebar.html("<div style='height:1.2rem'></div>")
    if st.sidebar.button("Önbelleği temizle", key="clear_caches", width="stretch"):
        loaders.clear_caches()
        st.rerun()
    return dataset


# --------------------------------------------------------------------------- #
# 1) Heatmap
# --------------------------------------------------------------------------- #
def render_heatmap_tab(artifacts: EngineArtifacts) -> None:
    """Similarity heatmap screen.

    The full matrix is unreadable at 149 actors, so a subset is always chosen.
    Rows are ordered by the clustering dendrogram, without which a heatmap shows
    nothing.

    Args:
        artifacts: Loaded engine artefacts. ``artifacts.similarity`` is ``None``
            when the similarity stage has not run -- show a hint, do not crash.
    """
    if artifacts.similarity is None:
        theme.banner(
            "Benzerlik matrisi bulunamadı.",
            "warn",
            code=f"python -m ttp_similarity.engine.build --dataset {artifacts.dataset}",
        )
        return

    labels = _actor_labels(artifacts)
    names = _actor_names(artifacts)
    total = len(artifacts.actors)

    theme.section(
        "01",
        "Görünüm",
        "Matris her zaman bir alt kümedir; 149 aktör tek ekranda okunmaz.",
    )
    mode = st.radio(
        "Gösterilecek aktörler",
        [
            "Bir aktör ve en yakın komşuları",
            "Aktörleri elle seç",
            "En yoğun benzerlik gösteren N aktör",
        ],
        horizontal=True,
        label_visibility="collapsed",
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
            theme.banner("En az iki aktör seçin.", "info")
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
    values = subset.matrix[np.triu_indices(len(subset.actor_ids), k=1)]
    if values.size:
        theme.stats(
            [
                ("Seçili aktör", len(subset.actor_ids), f"/ {total}"),
                ("Ortalama benzerlik", f"{values.mean():.3f}"),
                ("Medyan", f"{np.median(values):.3f}"),
                ("En yüksek çift", f"{values.max():.3f}"),
                ("Metrik", subset.metric),
            ]
        )

    theme.section("02", "Matris", "Satırlar kümeleme dendrogramına göre sıralanmıştır.")
    try:
        order = clustering.order_for_heatmap(subset)
    except Exception:  # noqa: BLE001 - ordering is a nicety, never fatal
        order = None
    figure = plots.similarity_heatmap(subset, names, order, dark=True)
    st.pyplot(figure, width="stretch")

    theme.section("03", "Bu görünümdeki en benzer çiftler")
    theme.table(
        columns=(
            ("#", "ttp-rank"),
            ("aktör a", "ttp-name"),
            ("aktör b", "ttp-name"),
            ("skor", "ttp-num"),
        ),
        rows=_top_pair_rows(subset, names),
        grid="2.2rem 1fr 1fr 5rem",
    )


def _top_pair_rows(
    similarity: SimilarityMatrix, names: dict[str, str], limit: int = 15
) -> list[list[object]]:
    """The strongest pairs inside the displayed subset."""
    n = len(similarity.actor_ids)
    upper = np.triu_indices(n, k=1)
    rows: list[list[object]] = []
    for rank, position in enumerate(
        np.argsort(similarity.matrix[upper])[::-1][:limit], start=1
    ):
        i, j = upper[0][position], upper[1][position]
        rows.append(
            [
                f"{rank:02d}",
                names.get(similarity.actor_ids[i], similarity.actor_ids[i]),
                names.get(similarity.actor_ids[j], similarity.actor_ids[j]),
                f"{float(similarity.matrix[i, j]):.4f}",
            ]
        )
    return rows


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
    theme.section(
        "01",
        "Gözlemlenen teknikler",
        "Boşluk, virgül veya satır sonuyla ayırın. Alt teknikler ana tekniğe "
        "indirgenir (T1059.001 → T1059).",
    )

    left, right, _ = st.columns([2, 2, 3])
    if left.button("APT40 — ayırt edici 8", key="preset_rare", width="stretch"):
        _load_preset(PRESET_APT40_DISTINCTIVE)
    if right.button("APT40 — emtia 8", key="preset_common", width="stretch"):
        _load_preset(PRESET_APT40_COMMODITY)

    raw = st.text_area(
        "Teknik listesi",
        key=QUERY_KEY,
        height=104,
        placeholder="T1566 T1078 T1047 T1003 ...",
        label_visibility="collapsed",
    )
    top_k = st.slider("Kaç aday gösterilsin", 3, 25, config.QUERY_TOP_K)

    if not str(raw).strip():
        theme.banner(
            "Bir teknik listesi girin veya yukarıdaki hazır setlerden birini yükleyin.",
            "info",
        )
        return

    result = query_mod.query_techniques(raw, artifacts, top_k=top_k)
    scored = len(result.query_technique_ids) - len(result.unknown_technique_ids)

    theme.stats(
        [
            ("Skorlanan teknik", scored, f"/ {len(result.query_technique_ids)}"),
            ("Aday", len(result.candidates)),
            ("Güven", theme.LEVEL_LABELS.get(result.confidence.level.value, "-")),
            ("Veri seti", result.dataset),
        ]
    )

    if result.unknown_technique_ids:
        theme.banner(
            "Bu veri setinde bulunmayan teknikler skorlamaya girmedi:", "warn"
        )
        theme.chips(result.unknown_technique_ids, tone="warn")

    if not result.candidates:
        theme.banner("Skorlanabilir teknik kalmadı; sonuç üretilemedi.", "err")
        return

    theme.section(
        "02",
        "Güven değerlendirmesi",
        "Tek bir benzerlik sayısı yanıltıcıdır: en iyi aday, sorgu üç yaygın "
        "teknikten ibaret olsa bile vardır.",
    )
    render_confidence(result)

    theme.section("03", "Aday aktörler", "Çubuklar en yüksek skora göre ölçeklenmiştir.")
    theme.candidate_table(result.candidates, scored)

    theme.section(
        "04",
        "Kanıt dökümü",
        "Açıklanamayan bir sıralama, denetlenemeyeceği için kullanılabilir "
        "istihbarat değildir.",
    )
    render_evidence(result)


def render_confidence(result: QueryResult) -> None:
    """Confidence badge plus its three components.

    Args:
        result: The query result being displayed.
    """
    theme.confidence_panel(
        result.confidence,
        confidence_mod.explain(result.confidence),
        config.CONFIDENCE_COMPONENT_WEIGHTS,
    )


def render_evidence(result: QueryResult) -> None:
    """Per-candidate breakdown of which techniques produced the score.

    Args:
        result: The query result being displayed.
    """
    for candidate in result.candidates:
        title = (
            f"{candidate.rank:02d}  {candidate.actor_name}   "
            f"{candidate.score:.4f}   "
            f"{len(candidate.matched_technique_ids)} eşleşen"
        )
        with st.expander(title, expanded=candidate.rank == 1):
            if candidate.evidence:
                theme.evidence_bars(candidate.evidence)
            else:
                theme.banner("Bu adayda eşleşen teknik yok.", "info")

            if candidate.missing_technique_ids:
                st.html(
                    '<div class="ttp-rail-h">Bu aktörde görülmeyen sorgu teknikleri</div>'
                )
                theme.chips(candidate.missing_technique_ids, tone="off")
            else:
                st.html(
                    '<div class="ttp-rail-h">Sorgudaki her teknik bu aktörde görülmüş</div>'
                )


# --------------------------------------------------------------------------- #
# 3) Case study
# --------------------------------------------------------------------------- #
def render_case_study_tab(artifacts: EngineArtifacts) -> None:
    """One actor's profile and neighbourhood.

    Args:
        artifacts: Loaded engine artefacts.
    """
    if artifacts.similarity is None:
        theme.banner(
            "Benzerlik matrisi bulunamadı.",
            "warn",
            code=f"python -m ttp_similarity.engine.build --dataset {artifacts.dataset}",
        )
        return

    labels = _actor_labels(artifacts)
    by_id = artifacts.actor_by_id()
    default = "G0065" if "G0065" in labels else list(labels)[0]

    theme.section("01", "Konu")
    left, right = st.columns([3, 1])
    actor_id = left.selectbox(
        "Aktör",
        list(labels),
        index=list(labels).index(default),
        format_func=lambda a: labels[a],
        label_visibility="collapsed",
    )
    limit = right.slider("Komşu sayısı", 5, 30, 15)
    actor = by_id[actor_id]

    frequency = loaders.get_technique_frequency(artifacts.dataset)
    counts = dict(zip(frequency["technique_id"], frequency["actor_count"]))
    own_weights = [artifacts.weights.get(t, 0.0) for t in actor.technique_ids]

    theme.stats(
        [
            ("Aktör", actor.actor_id),
            ("Teknik", len(actor.technique_ids)),
            ("Takma ad", len(actor.aliases)),
            ("Küme", artifacts.clusters.get(actor_id, "-") if artifacts.clusters else "-"),
            ("Ort. ağırlık", f"{np.mean(own_weights):.3f}" if own_weights else "-"),
        ]
    )
    if actor.aliases:
        theme.chips(actor.aliases)

    theme.section(
        "02",
        "En benzer aktörler",
        "«ortak ağ. ort.» yorumun merkezi: benzerlik nadir tekniklerden mi, "
        "yoksa emtia tekniklerden mi geliyor?",
    )
    theme.table(
        columns=(
            ("#", "ttp-rank"),
            ("aktör", "ttp-name"),
            ("id", "ttp-id"),
            ("skor", "ttp-num"),
            ("teknik", "ttp-num ttp-num--sub"),
            ("ortak", "ttp-num ttp-num--sub"),
            ("ortak ağ. ort.", "ttp-num"),
            ("ağ. maks.", "ttp-num ttp-num--sub"),
        ),
        rows=_neighbour_rows(actor, artifacts, limit),
        grid="2.2rem 1fr 13rem 4.8rem 4.2rem 3.8rem 7rem 5rem",
    )

    theme.section(
        "03",
        "Teknikleri, ağırlığa göre",
        "Üstteki uç ayırt edici davranış, alttaki uç emtia davranıştır.",
    )
    rows = sorted(
        (
            [
                tid,
                artifacts.technique_names.get(tid, tid),
                f"{artifacts.weights.get(tid, float('nan')):.3f}",
                int(counts.get(tid, 0)),
            ]
            for tid in actor.technique_ids
        ),
        key=lambda row: float(row[2]),
        reverse=True,
    )
    theme.table(
        columns=(
            ("teknik", "ttp-ev__id"),
            ("ad", "ttp-cell"),
            ("ağırlık", "ttp-num"),
            ("kaç aktörde", "ttp-num ttp-num--sub"),
        ),
        rows=rows,
        grid="5rem 1fr 5.4rem 7rem",
    )


def render_setup_help(datasets: list[str]) -> None:
    """Shown when nothing has been built yet.

    Args:
        datasets: Currently available datasets (empty in this branch).
    """
    theme.inject()
    theme.header("TTP Similarity Engine", {"durum": "kurulum gerekli"})
    theme.banner("Kullanılabilir bir veri seti bulunamadı.", "err")
    theme.section("01", "Önce bunları çalıştırın")
    theme.banner(
        "Sentetik veri seti (gerçek veri olmadan denemek için):",
        "info",
        code="python -m ttp_similarity.data.mock_dataset",
    )
    theme.banner(
        "Motor artefaktları:",
        "info",
        code=f"python -m ttp_similarity.engine.build --dataset {paths.MOCK_DATASET}",
    )
    render_disclaimer()
