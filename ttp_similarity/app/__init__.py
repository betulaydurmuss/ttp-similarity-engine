"""Stage 4 -- the Streamlit UI, laid out as a dark analysis console.

Three screens, reached from a left rail:

**Isi haritasi**
    The actor-vs-actor similarity matrix, ordered by the clustering so that
    behavioural families read as blocks, plus the strongest pairs in view.

**TTP sorgu**
    Paste a technique list, get ranked candidate actors, a confidence panel with
    its three components, and the techniques that drove each result.

**Vaka calismasi**
    One actor's profile: its neighbours with the mean weight of the techniques
    each pair shares, and its own techniques ordered by weight.

Module split:

* ``streamlit_app`` -- the shell: page config, rail dispatch, error handling
* ``views``         -- one function per screen, describing *what* it shows
* ``theme``         -- design tokens, the stylesheet, and the HTML components
                       that replace ``st.metric`` / ``st.dataframe``
* ``plots``         -- matplotlib figures, no ``st.*`` calls
* ``loaders``       -- cached disk access

The app reads artefacts from disk and calls
:func:`ttp_similarity.engine.query.query_techniques`. It contains no scoring
logic of its own -- if a number is computed here rather than in the engine, the
CLI and the UI will eventually disagree.

Run::

    streamlit run ttp_similarity/app/streamlit_app.py

Owner: app module.
"""

from __future__ import annotations

__all__ = ["loaders", "plots", "streamlit_app", "theme", "views"]
