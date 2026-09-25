"""Streamlit entry point.

Run from the repository root::

    streamlit run ttp_similarity/app/streamlit_app.py

This file is the shell only: page config, stylesheet injection, dataset
selection, rail dispatch and error handling. Every screen lives in
:mod:`ttp_similarity.app.views`, every style token and HTML component in
:mod:`ttp_similarity.app.theme`, every figure in
:mod:`ttp_similarity.app.plots`, and all scoring in the engine.

Sections are reached from a left rail rather than from ``st.tabs``: only one
screen's widgets are then instantiated per run, so switching screens does not
re-render the other two, and the active entry can carry a real selected state.

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
    from ttp_similarity.app import loaders, theme, views  # noqa: E402
except Exception as _import_error:  # noqa: BLE001
    if type(_import_error).__name__ != "UnsupportedPythonError":
        raise
    st.set_page_config(page_title="TTP Similarity Engine", page_icon=":material/error:")
    st.error("Yanlis Python surumu - uygulama baslatilamadi.")
    st.code(str(_import_error).strip(), language="text")
    st.caption("Kurulumu dogrulamak icin: `python check_setup.py`")
    st.stop()

PAGE_TITLE = "TTP Similarity Engine"

#: Rail key -> (renderer attribute name, subtitle shown under the top bar).
SECTIONS = {
    "heatmap": ("render_heatmap_tab", "Aktörler arası davranışsal benzerlik matrisi"),
    "query": ("render_query_tab", "Gözlemlenen TTP setini bilinen aktörlerle karşılaştır"),
    "case": ("render_case_study_tab", "Tek aktörün profili ve komşuluğu"),
}


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

    theme.inject()
    section = views.render_nav()
    dataset = views.render_sidebar(datasets)

    manifest = loaders.get_manifest_summary(dataset)
    theme.header(
        PAGE_TITLE,
        {
            "veri seti": dataset,
            "att&ck": manifest.get("ATT&CK surumu", "-"),
            "aktör": manifest.get("Aktör", "-"),
            "teknik": manifest.get("Teknik", "-"),
        },
    )
    views.render_disclaimer()

    if not loaders.engine_is_built(dataset):
        theme.banner(
            f"'{dataset}' veri seti için motor artefaktları eksik.",
            "err",
            code=f"python -m ttp_similarity.engine.build --dataset {dataset}",
        )
        return

    try:
        artifacts = loaders.get_engine(dataset)
    except storage.ArtifactMissingError as error:
        theme.banner(str(error), "err")
        return

    renderer_name, subtitle = SECTIONS[section]
    renderer = getattr(views, renderer_name)
    st.html(
        f'<div class="ttp-sec__note" style="margin:-0.5rem 0 0.2rem">{subtitle}</div>'
    )
    views.guard(lambda: renderer(artifacts), f"views.{renderer_name}")


main()
