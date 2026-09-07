"""Cached data access for the UI.

Streamlit re-runs the whole script on every widget interaction, so anything
touching disk goes through ``st.cache_data`` / ``st.cache_resource`` here.
These are thin wrappers over :mod:`ttp_similarity.storage` and
:mod:`ttp_similarity.engine.loading` -- the UI never opens a file itself.

Owner: app module.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import paths, storage
from ..engine import loading
from ..schema import EngineArtifacts


def available_datasets() -> list[str]:
    """Dataset names that have at least a stage-1 build on disk.

    Returns:
        Workspace names, ready for the sidebar selector. Empty when nothing has
        been built yet -- the app then shows setup instructions instead of a
        broken selector.
    """
    return [
        name
        for name in paths.KNOWN_DATASETS
        if storage.dataset_exists(paths.Workspace.get(name))
    ]


@st.cache_resource(show_spinner="Motor yukleniyor...")
def get_engine(dataset: str) -> EngineArtifacts:
    """Load and cache the engine artefacts for one dataset.

    ``cache_resource`` rather than ``cache_data``: the matrices are large and
    are only read, never mutated, so they should be shared across sessions.

    Args:
        dataset: Workspace name.

    Returns:
        Loaded :class:`~ttp_similarity.schema.EngineArtifacts`.

    Raises:
        ttp_similarity.storage.ArtifactMissingError: If stage 2 has not run.
    """
    return loading.load_engine(dataset)


@st.cache_data(show_spinner=False)
def get_technique_frequency(dataset: str) -> pd.DataFrame:
    """Technique frequency table, for the technique picker and the rarity hints."""
    workspace = paths.Workspace.get(dataset)
    return storage.read_dataframe(workspace.technique_frequency, dataset)


@st.cache_data(show_spinner=False)
def get_actor_technique(dataset: str) -> pd.DataFrame:
    """The tidy actor/technique edge table, for the actor detail panel."""
    workspace = paths.Workspace.get(dataset)
    return storage.read_dataframe(workspace.actor_technique, dataset)


@st.cache_data(show_spinner=False)
def get_manifest_summary(dataset: str) -> dict[str, str]:
    """Provenance strings for the sidebar: source, ATT&CK version, build time.

    Returns:
        Display-ready mapping; empty when no manifest exists.
    """
    workspace = paths.Workspace.get(dataset)
    if not workspace.data_manifest.exists():
        return {}
    manifest = storage.read_manifest(workspace.data_manifest, dataset)
    return {
        "Kaynak": manifest.source,
        "ATT&CK surumu": manifest.attack_version or "-",
        "Olusturulma": manifest.built_at,
        "Aktor": str(manifest.actor_count),
        "Teknik": str(manifest.technique_count),
    }


def engine_is_built(dataset: str) -> bool:
    """True when stage 2 artefacts exist for ``dataset``."""
    return storage.engine_exists(paths.Workspace.get(dataset))


def clear_caches() -> None:
    """Drop every cache. Call after rebuilding a dataset from the sidebar."""
    st.cache_data.clear()
    st.cache_resource.clear()
    loading.load_engine_cached.cache_clear()
