"""Streamlit entry point.

Run from the repository root::

    streamlit run ttp_similarity/app/streamlit_app.py

This file is the shell only: page config, dataset selection, tab layout and
error handling. Every screen lives in :mod:`ttp_similarity.app.views`, every
figure in :mod:`ttp_similarity.app.plots`, and all scoring in the engine.

The shell is implemented so the app runs today: each tab shows a placeholder
naming the function still to be written, and the whole app degrades to setup
instructions when nothing has been built yet.

Owner: app module.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `streamlit run ttp_similarity/app/streamlit_app.py` from the repo root:
# Streamlit executes the file as a script, so the package root is not yet on
# sys.path when the imports below run.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402

# The package guards the interpreter version at import time. In a Streamlit
# session that would otherwise render as a raw traceback in the browser, so it
# is caught and shown as a readable page instead. Caught by class name because
# the exception type lives inside the package that failed to import.
try:
    from ttp_similarity import config, paths, storage  # noqa: E402
    from ttp_similarity.app import loaders, views  # noqa: E402
except Exception as _import_error:  # noqa: BLE001
    if type(_import_error).__name__ != "UnsupportedPythonError":
        raise
    st.set_page_config(page_title="TTP Similarity Engine", page_icon=":material/error:")
    st.error("Yanlis Python surumu - uygulama baslatilamadi.")
    st.code(str(_import_error).strip(), language="text")
    st.caption("Kurulumu dogrulamak icin: `python check_setup.py`")
    st.stop()

PAGE_TITLE = "TTP Similarity Engine"
TAB_LABELS = ("Benzerlik Isi Haritasi", "TTP Sorgu", "Veri Seti")


def configure_page() -> None:
    """Set page-level Streamlit options. Must run before any other st call."""
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=":material/hub:",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def main() -> None:
    """Compose the application."""
    configure_page()
    config.validate()

    datasets = loaders.available_datasets()
    if not datasets:
        views.render_setup_help(datasets)
        return

    # The sidebar is still a TODO; fall back to the default dataset so the rest
    # of the layout is reviewable in the meantime.
    try:
        dataset = views.render_sidebar(datasets)
    except NotImplementedError:
        dataset = paths.DEFAULT_DATASET if paths.DEFAULT_DATASET in datasets else datasets[0]
        st.sidebar.info("Henuz uygulanmadi: `views.render_sidebar`")
        st.sidebar.caption(f"Varsayilan veri seti: {dataset}")

    st.title(PAGE_TITLE)
    st.caption(
        "MITRE ATT&CK tabanli davranissal benzerlik olcumu - "
        f"veri seti: `{dataset}`"
    )
    views.render_disclaimer()

    if not loaders.engine_is_built(dataset):
        st.error(
            f"'{dataset}' veri seti icin motor artefaktlari eksik. "
            f"Calistirin: `python -m ttp_similarity.engine.build --dataset {dataset}`"
        )
        return

    try:
        artifacts = loaders.get_engine(dataset)
    except storage.ArtifactMissingError as error:
        st.error(str(error))
        return

    heatmap_tab, query_tab, case_tab = st.tabs(list(TAB_LABELS))
    with heatmap_tab:
        views.guard(lambda: views.render_heatmap_tab(artifacts), "views.render_heatmap_tab")
    with query_tab:
        views.guard(lambda: views.render_query_tab(artifacts), "views.render_query_tab")
    with case_tab:
        views.guard(
            lambda: views.render_case_study_tab(artifacts), "views.render_case_study_tab"
        )


main()
