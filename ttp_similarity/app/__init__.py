"""Stage 4 -- the Streamlit UI.

Two screens:

**Benzerlik isi haritasi**
    The actor-vs-actor similarity matrix, ordered by the clustering so that
    behavioural families read as blocks, plus a "closest peers" lookup.

**TTP sorgu**
    Paste a technique list, get ranked candidate actors, a confidence badge with
    its three components, and the techniques that drove the result.

The app reads artefacts from disk and calls
:func:`ttp_similarity.engine.query.query_techniques`. It contains no scoring
logic of its own -- if a number is computed here rather than in the engine, the
CLI and the UI will eventually disagree.

Run::

    streamlit run ttp_similarity/app/streamlit_app.py

Owner: app module.
"""

from __future__ import annotations

__all__ = ["loaders", "plots", "streamlit_app", "views"]
