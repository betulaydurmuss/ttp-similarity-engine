"""The console's design system: tokens, stylesheet and HTML components.

Everything about how the UI *looks* lives here, so :mod:`ttp_similarity.app.views`
stays a description of what each screen shows. Same split as
:mod:`ttp_similarity.app.plots`, which owns the figures.

Why hand-written HTML instead of ``st.metric`` / ``st.dataframe``
----------------------------------------------------------------
The default widgets are the reason a Streamlit app is recognisable on sight: a
filled metric card and a grid dataframe carry their own visual language, and it
is not this one. The pieces an analyst actually reads -- the candidate ranking,
the confidence breakdown, the evidence shares -- are therefore rendered as HTML
through :func:`_html`, and Streamlit is left to do what it is good at: inputs,
layout and caching.

Two consequences worth knowing:

* Anything interpolated into markup goes through :func:`escape` first. Actor and
  technique names come from ATT&CK, i.e. from outside this repository, and an
  apostrophe or an angle bracket in a group name must not be able to reshape the
  page.
* Selectors target ``data-testid`` / ``kind`` attributes only, never the
  ``st-emotion-cache-*`` class hashes, which change between Streamlit releases.

Owner: app module. No scoring, no disk access.
"""

from __future__ import annotations

from html import escape as _escape
from typing import Iterable, Mapping, Sequence

import streamlit as st

from ..schema import Candidate, ConfidenceBreakdown, TechniqueContribution

#: Design tokens. Mirrors the five colours in ``.streamlit/config.toml``; the
#: rest exist only here. The stylesheet declares these as CSS custom properties
#: -- Python only needs the handful that end up in an inline ``style`` attribute.
PALETTE: Mapping[str, str] = {
    "bg": "#0b0f14",
    "surface": "#111720",
    "surface_2": "#161d28",
    "line": "#1f2937",
    "text": "#e3e9f2",
    "muted": "#8b97a8",
    "dim": "#5c6879",
    "accent": "#4fd1c5",
}

#: Confidence level -> colour. Chosen for contrast against ``bg`` rather than
#: for prettiness: these three are the only semantic colours in the interface,
#: so nothing else is allowed to be green, amber or red.
LEVEL_COLORS: Mapping[str, str] = {
    "high": "#3fb950",
    "medium": "#d29922",
    "low": "#f85149",
}

#: Level -> Turkish label shown in the confidence panel.
LEVEL_LABELS: Mapping[str, str] = {
    "high": "YÜKSEK",
    "medium": "ORTA",
    "low": "DÜŞÜK",
}

#: A confidence component at or below this is marked as the weak one. Matches
#: ``confidence.explain``'s threshold so the bar and the sentence agree.
WEAK_COMPONENT = 0.34

#: Web fonts, pulled in with an ``@import`` at the head of the stylesheet
#: rather than a ``<link>`` tag: Streamlit sanitises injected markup with
#: DOMPurify, whose allow-list covers ``<style>`` but not ``<link>``, so a link
#: element is silently dropped before it reaches the document. Every
#: ``font-family`` below still names a system fallback, so a blocked or slow
#: fetch costs typography, not layout.
_FONTS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Inter:wght@400;500;600;700"
    "&family=JetBrains+Mono:wght@400;500;700"
    "&display=swap"
)

# --------------------------------------------------------------------------- #
# Stylesheet
# --------------------------------------------------------------------------- #
# Deliberately a plain string, not an f-string: CSS is mostly braces, and
# doubling every one of them to interpolate four hex codes would make this
# unreadable for no gain. The palette lives in the `:root` block below.
_CSS = """
:root {
  --ttp-bg:        #0b0f14;
  --ttp-surface:   #111720;
  --ttp-surface-2: #161d28;
  --ttp-line:      #1f2937;
  --ttp-line-2:    #2b3748;
  --ttp-text:      #e3e9f2;
  --ttp-muted:     #8b97a8;
  --ttp-dim:       #5c6879;
  --ttp-accent:    #4fd1c5;
  --ttp-accent-dim:#2a7d76;
  --ttp-high:      #3fb950;
  --ttp-medium:    #d29922;
  --ttp-low:       #f85149;
  --ttp-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --ttp-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
}

/* ---------- Streamlit chrome ------------------------------------------- */
/* The header bar is emptied rather than hidden: display:none would take the
   sidebar collapse control with it. */
header[data-testid="stHeader"] { background: transparent; height: 2.2rem; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer {
  display: none !important;
}
[data-testid="stAppViewContainer"] { background: var(--ttp-bg); }
[data-testid="stMain"] .block-container {
  padding: 0.6rem 2.2rem 4rem;
  max-width: 1500px;
}
html, body, [data-testid="stAppViewContainer"], .stMarkdown, p, span, div, label {
  font-family: var(--ttp-sans);
}
.ttp-mono, .ttp-mono * { font-family: var(--ttp-mono); font-variant-numeric: tabular-nums; }

/* ---------- Left rail --------------------------------------------------- */
[data-testid="stSidebar"] {
  background: var(--ttp-surface);
  border-right: 1px solid var(--ttp-line);
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1.1rem; }

[data-testid="stSidebar"] .stButton > button {
  width: 100%;
  justify-content: flex-start;
  gap: 0.6rem;
  background: transparent;
  border: 0;
  border-left: 2px solid transparent;
  border-radius: 0;
  padding: 0.62rem 0.85rem;
  color: var(--ttp-muted);
  font-family: var(--ttp-sans);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  transition: none;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: var(--ttp-surface-2);
  color: var(--ttp-text);
  border-left-color: var(--ttp-line-2);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
  background: linear-gradient(90deg, rgba(79, 209, 197, 0.13), transparent 85%);
  border-left-color: var(--ttp-accent);
  color: var(--ttp-text);
}
[data-testid="stSidebar"] .stButton > button:focus { box-shadow: none; outline: none; }

/* ---------- Top bar ---------------------------------------------------- */
.ttp-bar {
  display: flex; align-items: baseline; gap: 0.85rem;
  padding: 0 0 0.75rem;
  border-bottom: 1px solid var(--ttp-line);
  margin-bottom: 1.3rem;
}
.ttp-bar__mark { color: var(--ttp-accent); font-size: 1.05rem; line-height: 1; }
.ttp-bar__title {
  font-size: 0.86rem; font-weight: 700; letter-spacing: 0.15em;
  text-transform: uppercase; color: var(--ttp-text);
}
.ttp-bar__meta {
  margin-left: auto; display: flex; gap: 1.4rem;
  font-family: var(--ttp-mono); font-size: 0.71rem; color: var(--ttp-dim);
}
.ttp-bar__meta b { color: var(--ttp-muted); font-weight: 500; }

/* ---------- Section heading -------------------------------------------- */
.ttp-sec { margin: 1.9rem 0 0.9rem; }
.ttp-sec__row { display: flex; align-items: center; gap: 0.7rem; }
.ttp-sec__n {
  font-family: var(--ttp-mono); font-size: 0.68rem; color: var(--ttp-accent-dim);
}
.ttp-sec__t {
  font-size: 0.74rem; font-weight: 700; letter-spacing: 0.13em;
  text-transform: uppercase; color: var(--ttp-muted); white-space: nowrap;
}
.ttp-sec__rule { flex: 1; height: 1px; background: var(--ttp-line); }
.ttp-sec__note {
  margin: 0.45rem 0 0; font-size: 0.78rem; color: var(--ttp-dim); max-width: 78ch;
}

/* ---------- Stat strip ------------------------------------------------- */
.ttp-stats { display: flex; flex-wrap: wrap; gap: 0; border: 1px solid var(--ttp-line); }
.ttp-stat {
  flex: 1 1 0; min-width: 132px; padding: 0.7rem 0.95rem;
  border-right: 1px solid var(--ttp-line);
}
.ttp-stat:last-child { border-right: 0; }
.ttp-stat__k {
  font-size: 0.63rem; font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ttp-dim);
}
.ttp-stat__v {
  font-family: var(--ttp-mono); font-size: 1.32rem; font-weight: 500;
  color: var(--ttp-text); margin-top: 0.22rem; line-height: 1.1;
}
.ttp-stat__v small { font-size: 0.72rem; color: var(--ttp-dim); margin-left: 0.3rem; }

/* ---------- Confidence panel ------------------------------------------- */
.ttp-conf { border: 1px solid var(--ttp-line); border-top-width: 2px; }
.ttp-conf__head {
  display: flex; align-items: baseline; gap: 0.8rem;
  padding: 0.85rem 1.05rem; border-bottom: 1px solid var(--ttp-line);
}
.ttp-conf__cap {
  font-size: 0.63rem; font-weight: 600; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--ttp-dim);
}
.ttp-conf__lvl { font-size: 1.28rem; font-weight: 700; letter-spacing: 0.06em; }
.ttp-conf__score {
  margin-left: auto; font-family: var(--ttp-mono); font-size: 1.28rem;
  color: var(--ttp-text);
}
.ttp-conf__body { padding: 0.9rem 1.05rem 1rem; }

.ttp-comp {
  display: grid; grid-template-columns: 11.5rem 1fr 3.4rem;
  align-items: center; gap: 0.85rem; padding: 0.3rem 0;
}
.ttp-comp__n { font-size: 0.78rem; color: var(--ttp-muted); }
.ttp-comp__n em {
  font-family: var(--ttp-mono); font-style: normal; font-size: 0.68rem;
  color: var(--ttp-dim); margin-left: 0.35rem;
}
.ttp-comp__n .ttp-warn { color: var(--ttp-low); margin-right: 0.25rem; }
.ttp-track { height: 6px; background: var(--ttp-surface-2); position: relative; }
.ttp-track > i { display: block; height: 100%; background: var(--ttp-accent); }
.ttp-track > i.is-weak { background: var(--ttp-low); }
.ttp-comp__v {
  font-family: var(--ttp-mono); font-size: 0.78rem; color: var(--ttp-text);
  text-align: right;
}
.ttp-conf__why {
  margin: 0.85rem 0 0; padding: 0.7rem 0 0; list-style: none;
  border-top: 1px dashed var(--ttp-line);
}
.ttp-conf__why li {
  font-size: 0.76rem; color: var(--ttp-muted); padding: 0.13rem 0 0.13rem 0.95rem;
  position: relative;
}
.ttp-conf__why li::before {
  content: '!'; position: absolute; left: 0; color: var(--ttp-low);
  font-family: var(--ttp-mono); font-weight: 700;
}

/* ---------- Ranking / generic table ----------------------------------- */
.ttp-tbl { border: 1px solid var(--ttp-line); }
.ttp-tr {
  display: grid; align-items: center; gap: 0.9rem;
  padding: 0.5rem 1rem; border-bottom: 1px solid var(--ttp-line);
}
.ttp-tr:last-child { border-bottom: 0; }
.ttp-tr--h {
  background: var(--ttp-surface); padding-top: 0.42rem; padding-bottom: 0.42rem;
}
.ttp-tr--h span {
  font-size: 0.61rem; font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ttp-dim);
}
.ttp-tr--b:hover { background: var(--ttp-surface); }
.ttp-tr--top { background: rgba(79, 209, 197, 0.045); }

.ttp-rank {
  font-family: var(--ttp-mono); font-size: 0.78rem; color: var(--ttp-dim);
}
.ttp-tr--top .ttp-rank { color: var(--ttp-accent); }
.ttp-name { font-size: 0.86rem; color: var(--ttp-text); font-weight: 500; }
.ttp-name em {
  font-family: var(--ttp-mono); font-style: normal; font-size: 0.68rem;
  color: var(--ttp-dim); margin-left: 0.45rem;
}
.ttp-num {
  font-family: var(--ttp-mono); font-size: 0.8rem; color: var(--ttp-text);
  text-align: right;
}
.ttp-num--sub { color: var(--ttp-muted); font-size: 0.76rem; }
.ttp-cell { font-size: 0.8rem; color: var(--ttp-muted); }
/* Identifiers are long, unbreakable and rarely read in full -- a STIX id is
   `intrusion-set--` plus a UUID. Wrapping one turns every row into a
   three-line block and destroys the scan down the numeric columns, so ids
   clip to one line instead; the full value stays in each cell's `title`. */
.ttp-id {
  font-family: var(--ttp-mono); font-size: 0.72rem; color: var(--ttp-dim);
}
.ttp-id, .ttp-name, .ttp-cell {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ttp-tgt {
  font-family: var(--ttp-mono); font-size: 0.62rem; color: var(--ttp-accent);
  border: 1px solid var(--ttp-accent-dim); padding: 0.05rem 0.3rem;
  margin-left: 0.5rem; white-space: nowrap;
}

/* ---------- Evidence --------------------------------------------------- */
.ttp-ev { display: grid; grid-template-columns: 4.6rem 1fr 5.2rem 3.3rem; }
.ttp-ev__r {
  display: grid; grid-template-columns: subgrid; grid-column: 1 / -1;
  align-items: center; gap: 0.8rem; padding: 0.32rem 0;
}
.ttp-ev__id { font-family: var(--ttp-mono); font-size: 0.76rem; color: var(--ttp-accent); }
.ttp-ev__n {
  font-size: 0.79rem; color: var(--ttp-muted); overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
.ttp-ev__b { height: 5px; background: var(--ttp-surface-2); }
.ttp-ev__b > i { display: block; height: 100%; background: var(--ttp-accent-dim); }
.ttp-ev__p {
  font-family: var(--ttp-mono); font-size: 0.76rem; color: var(--ttp-text);
  text-align: right;
}

/* ---------- Chips ------------------------------------------------------ */
.ttp-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin: 0.15rem 0 0; }
.ttp-chip {
  font-family: var(--ttp-mono); font-size: 0.7rem; padding: 0.11rem 0.4rem;
  border: 1px solid var(--ttp-line-2); color: var(--ttp-muted);
  background: var(--ttp-surface);
}
.ttp-chip--warn { border-color: rgba(210, 153, 34, 0.45); color: var(--ttp-medium); }
.ttp-chip--off { border-style: dashed; color: var(--ttp-dim); }

/* ---------- Banner ----------------------------------------------------- */
.ttp-ban {
  display: flex; gap: 0.7rem; padding: 0.6rem 0.85rem;
  border-left: 2px solid var(--ttp-line-2); background: var(--ttp-surface);
  font-size: 0.79rem; color: var(--ttp-muted); margin: 0.35rem 0;
  line-height: 1.5;
}
.ttp-ban code {
  font-family: var(--ttp-mono); font-size: 0.74rem; color: var(--ttp-accent);
  background: var(--ttp-bg); padding: 0.05rem 0.3rem;
}
.ttp-ban__i { font-family: var(--ttp-mono); font-weight: 700; line-height: 1.5; }
.ttp-ban--warn { border-left-color: var(--ttp-medium); }
.ttp-ban--warn .ttp-ban__i { color: var(--ttp-medium); }
.ttp-ban--err { border-left-color: var(--ttp-low); }
.ttp-ban--err .ttp-ban__i { color: var(--ttp-low); }
.ttp-ban--info .ttp-ban__i { color: var(--ttp-accent); }

/* The non-attribution notice. Prominent by rule (DECISIONS.md section 1), so
   it gets the full-width treatment rather than an icon in a corner. */
.ttp-disc {
  border: 1px solid rgba(210, 153, 34, 0.3);
  border-left-width: 2px; border-left-color: var(--ttp-medium);
  background: rgba(210, 153, 34, 0.05);
  padding: 0.6rem 0.9rem; margin: 0 0 1.1rem;
  font-size: 0.76rem; color: #c9b98a; line-height: 1.55;
}
.ttp-disc b {
  display: block; font-size: 0.62rem; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--ttp-medium); margin-bottom: 0.2rem;
}

/* ---------- Key/value list (rail provenance) -------------------------- */
.ttp-kv { border-top: 1px solid var(--ttp-line); }
.ttp-kv__r {
  display: flex; justify-content: space-between; gap: 0.6rem;
  padding: 0.28rem 0; border-bottom: 1px solid var(--ttp-line);
}
.ttp-kv__k { font-size: 0.68rem; color: var(--ttp-dim); }
.ttp-kv__v {
  font-family: var(--ttp-mono); font-size: 0.68rem; color: var(--ttp-muted);
  text-align: right; word-break: break-word;
}
.ttp-rail-h {
  font-size: 0.6rem; font-weight: 600; letter-spacing: 0.13em;
  text-transform: uppercase; color: var(--ttp-dim);
  margin: 1.5rem 0 0.35rem;
}

/* ---------- Native widgets that stay -------------------------------- */
.stTextArea textarea, [data-baseweb="textarea"] {
  background: var(--ttp-surface) !important;
  border: 1px solid var(--ttp-line) !important;
  border-radius: 0 !important;
  color: var(--ttp-text) !important;
  font-family: var(--ttp-mono) !important;
  font-size: 0.83rem !important;
}
.stTextArea textarea:focus { border-color: var(--ttp-accent-dim) !important; }
[data-baseweb="select"] > div {
  background: var(--ttp-surface) !important;
  border: 1px solid var(--ttp-line) !important;
  border-radius: 0 !important;
  font-size: 0.82rem;
}
[data-testid="stMain"] .stButton > button {
  background: var(--ttp-surface); color: var(--ttp-muted);
  border: 1px solid var(--ttp-line); border-radius: 0;
  font-size: 0.73rem; font-weight: 600; letter-spacing: 0.05em;
  padding: 0.42rem 0.8rem;
}
[data-testid="stMain"] .stButton > button:hover {
  border-color: var(--ttp-accent-dim); color: var(--ttp-text);
  background: var(--ttp-surface-2);
}
[data-testid="stExpander"] {
  border: 1px solid var(--ttp-line) !important; border-radius: 0 !important;
  background: transparent !important; margin-bottom: 0.4rem;
}
[data-testid="stExpander"] summary { font-size: 0.8rem; color: var(--ttp-muted); }
[data-testid="stExpander"] summary:hover { color: var(--ttp-text); }
label, .stSlider label, [data-testid="stWidgetLabel"] p {
  font-size: 0.66rem !important; font-weight: 600 !important;
  letter-spacing: 0.09em !important; text-transform: uppercase !important;
  color: var(--ttp-dim) !important;
}
[data-testid="stRadio"] [role="radiogroup"] { gap: 0.15rem; }
[data-testid="stRadio"] label p { text-transform: none !important;
  letter-spacing: 0 !important; font-size: 0.78rem !important;
  font-weight: 400 !important; color: var(--ttp-muted) !important; }
hr { border-color: var(--ttp-line); }
"""


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #
def escape(value: object) -> str:
    """HTML-escape any value for interpolation into markup.

    Args:
        value: Anything; coerced with :func:`str` first.

    Returns:
        The escaped text, quotes included, so it is safe inside an attribute.
    """
    return _escape(str(value), quote=True)


def _html(markup: str) -> None:
    """Render raw markup into the page.

    ``st.html`` rather than ``st.markdown(unsafe_allow_html=True)``: the latter
    runs the string through a CommonMark parser first, which imposes markdown's
    block rules on the markup and rewrites stray ``*`` or ``_`` inside ATT&CK
    names. ``st.html`` inserts the markup as-is (still DOMPurify-sanitised).
    """
    st.html(markup)


def _pct(value: float) -> float:
    """Clamp a ``[0, 1]`` ratio to a CSS width percentage."""
    return max(0.0, min(1.0, float(value))) * 100.0


def inject() -> None:
    """Load the fonts and the stylesheet. Call once, before anything renders.

    Sent with ``st.html``, not ``st.markdown``. Markdown parses its input as
    CommonMark before honouring the raw HTML, and a block opened by a tag on
    CommonMark's block-element list closes at the first blank line -- so a
    stylesheet with blank lines between its sections is cut off there and the
    remainder is rendered as visible paragraphs of CSS source. ``st.html``
    skips the parser, and Streamlit routes a style-only payload to the event
    container so it occupies no vertical space in the page.

    Streamlit re-runs the whole script on every interaction, so this runs on
    every rerun; the browser serves both from cache after the first paint.
    """
    st.html(f"<style>@import url('{_FONTS_URL}');{_CSS}</style>")


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
def header(title: str, meta: Mapping[str, str] | None = None) -> None:
    """The top bar: product mark on the left, build provenance on the right.

    Args:
        title: Product name.
        meta: Short ``label -> value`` pairs, e.g. dataset and ATT&CK version.
            Kept to three or four items; this is orientation, not a report.
    """
    cells = "".join(
        f"<span><b>{escape(key)}</b> {escape(value)}</span>"
        for key, value in (meta or {}).items()
    )
    _html(
        '<div class="ttp-bar">'
        '<span class="ttp-bar__mark">&#9670;</span>'
        f'<span class="ttp-bar__title">{escape(title)}</span>'
        f'<span class="ttp-bar__meta">{cells}</span>'
        "</div>"
    )


def section(number: str, title: str, note: str = "") -> None:
    """A numbered section heading with a rule running to the right margin.

    Args:
        number: Short ordinal shown in monospace, e.g. ``"01"``.
        title: Heading text.
        note: Optional one-line explanation underneath.
    """
    note_html = f'<p class="ttp-sec__note">{escape(note)}</p>' if note else ""
    _html(
        '<div class="ttp-sec"><div class="ttp-sec__row">'
        f'<span class="ttp-sec__n">{escape(number)}</span>'
        f'<span class="ttp-sec__t">{escape(title)}</span>'
        '<span class="ttp-sec__rule"></span></div>'
        f"{note_html}</div>"
    )


def stats(items: Sequence[tuple[str, object]] | Sequence[tuple[str, object, str]]) -> None:
    """A single bordered strip of figures, replacing a row of ``st.metric`` cards.

    Args:
        items: ``(label, value)`` or ``(label, value, suffix)`` tuples. The
            suffix is rendered small and dim, for units like ``"/ 149"``.
    """
    cells = []
    for item in items:
        label, value = item[0], item[1]
        suffix = item[2] if len(item) > 2 else ""
        tail = f"<small>{escape(suffix)}</small>" if suffix else ""
        cells.append(
            '<div class="ttp-stat">'
            f'<div class="ttp-stat__k">{escape(label)}</div>'
            f'<div class="ttp-stat__v">{escape(value)}{tail}</div>'
            "</div>"
        )
    _html(f'<div class="ttp-stats">{"".join(cells)}</div>')


def banner(text: str, tone: str = "info", code: str | None = None) -> None:
    """A thin left-ruled notice, replacing ``st.info`` / ``st.warning`` / ``st.error``.

    Args:
        text: Message body.
        tone: ``"info"``, ``"warn"`` or ``"err"``.
        code: Optional command shown after the message, in monospace.
    """
    marks = {"info": "i", "warn": "!", "err": "×"}
    tail = f" <code>{escape(code)}</code>" if code else ""
    _html(
        f'<div class="ttp-ban ttp-ban--{escape(tone)}">'
        f'<span class="ttp-ban__i">{marks.get(tone, "i")}</span>'
        f"<span>{escape(text)}{tail}</span></div>"
    )


def disclaimer(text: str) -> None:
    """The non-attribution notice, shown on every screen.

    Args:
        text: :data:`ttp_similarity.config.DISCLAIMER`.
    """
    _html(
        '<div class="ttp-disc"><b>Kapsam uyar&#305;s&#305;</b>'
        f"{escape(text)}</div>"
    )


def chips(values: Iterable[str], tone: str = "") -> None:
    """Technique ids as monospace chips.

    Args:
        values: Ids to show.
        tone: ``""``, ``"warn"`` (unknown to the dataset) or ``"off"`` (absent
            from the candidate).
    """
    suffix = f" ttp-chip--{tone}" if tone else ""
    cells = "".join(f'<span class="ttp-chip{suffix}">{escape(v)}</span>' for v in values)
    _html(f'<div class="ttp-chips">{cells}</div>')


def key_values(title: str, mapping: Mapping[str, str]) -> None:
    """A compact key/value list for the rail.

    Args:
        title: Small caps heading.
        mapping: Rows to render, in order.
    """
    rows = "".join(
        f'<div class="ttp-kv__r"><span class="ttp-kv__k">{escape(k)}</span>'
        f'<span class="ttp-kv__v">{escape(v)}</span></div>'
        for k, v in mapping.items()
    )
    _html(
        f'<div class="ttp-rail-h">{escape(title)}</div>'
        f'<div class="ttp-kv">{rows}</div>'
    )


# --------------------------------------------------------------------------- #
# Domain components
# --------------------------------------------------------------------------- #
def confidence_panel(
    breakdown: ConfidenceBreakdown,
    reasons: Sequence[str] = (),
    weights: Mapping[str, float] | None = None,
) -> None:
    """The confidence badge and its three components as one block.

    A bare percentage invites false certainty, so the level, the score and all
    three components are shown together, with the weak ones coloured and named.
    The component weights are printed next to each label because a reader cannot
    otherwise tell why a low margin hurts less than low rarity.

    Args:
        breakdown: Result of
            :func:`ttp_similarity.engine.confidence.score_confidence`.
        reasons: Sentences from
            :func:`ttp_similarity.engine.confidence.explain`.
        weights: ``CONFIDENCE_COMPONENT_WEIGHTS``; printed beside each label.
    """
    level = breakdown.level.value
    colour = LEVEL_COLORS.get(level, PALETTE["muted"])
    weights = weights or {}

    rows = []
    for key, label, value in (
        ("rarity", "nadirlik", breakdown.rarity),
        ("margin", "fark", breakdown.margin),
        ("sufficiency", "yeterlilik", breakdown.sufficiency),
    ):
        weak = value <= WEAK_COMPONENT
        mark = '<span class="ttp-warn">!</span>' if weak else ""
        share = f"<em>{weights[key]:.2f}</em>" if key in weights else ""
        rows.append(
            '<div class="ttp-comp">'
            f'<span class="ttp-comp__n">{mark}{escape(label)}{share}</span>'
            f'<span class="ttp-track"><i class="{"is-weak" if weak else ""}" '
            f'style="width:{_pct(value):.1f}%"></i></span>'
            f'<span class="ttp-comp__v">{value:.3f}</span>'
            "</div>"
        )

    why = ""
    if reasons:
        items = "".join(f"<li>{escape(r)}</li>" for r in reasons)
        why = f'<ul class="ttp-conf__why">{items}</ul>'

    _html(
        f'<div class="ttp-conf" style="border-top-color:{colour}">'
        '<div class="ttp-conf__head">'
        '<span class="ttp-conf__cap">G&#252;ven</span>'
        f'<span class="ttp-conf__lvl" style="color:{colour}">'
        f'{escape(LEVEL_LABELS.get(level, level.upper()))}</span>'
        f'<span class="ttp-conf__score">{breakdown.score:.3f}</span>'
        "</div>"
        f'<div class="ttp-conf__body">{"".join(rows)}{why}</div>'
        "</div>"
    )


def candidate_table(
    candidates: Sequence[Candidate],
    query_size: int,
    target_id: str | None = None,
) -> None:
    """The ranked candidate list, with each score drawn as a bar.

    Bars are scaled against the top score rather than against 1.0: cosine
    scores cluster in a narrow band, and a bar that never leaves the left edge
    communicates nothing. The point of the bar is the *gap* between ranks --
    which is exactly what the confidence margin component measures.

    Args:
        candidates: Ranked candidates, best first.
        query_size: Number of scored query techniques, for the ``matched/total``
            column.
        target_id: Actor to flag, when a screen has a subject (case study).
    """
    if not candidates:
        return
    top = max(c.score for c in candidates) or 1.0
    grid = "grid-template-columns: 2.2rem 1fr 4.4rem 7rem 4.6rem 4.6rem;"

    rows = [
        f'<div class="ttp-tr ttp-tr--h" style="{grid}">'
        "<span>#</span><span>akt&#246;r</span><span>skor</span><span></span>"
        "<span>e&#351;le&#351;en</span><span>eksik</span></div>"
    ]
    for candidate in candidates:
        classes = "ttp-tr ttp-tr--b"
        if candidate.rank == 1:
            classes += " ttp-tr--top"
        flag = '<span class="ttp-tgt">hedef</span>' if candidate.actor_id == target_id else ""
        rows.append(
            f'<div class="{classes}" style="{grid}">'
            f'<span class="ttp-rank">{candidate.rank:02d}</span>'
            f'<span class="ttp-name">{escape(candidate.actor_name)}'
            f"<em>{escape(candidate.actor_id)}</em>{flag}</span>"
            f'<span class="ttp-num">{candidate.score:.3f}</span>'
            f'<span class="ttp-track"><i style="width:'
            f'{_pct(candidate.score / top):.1f}%"></i></span>'
            f'<span class="ttp-num ttp-num--sub">'
            f"{len(candidate.matched_technique_ids)}/{query_size}</span>"
            f'<span class="ttp-num ttp-num--sub">'
            f"{len(candidate.missing_technique_ids)}</span>"
            "</div>"
        )
    _html(f'<div class="ttp-tbl">{"".join(rows)}</div>')


def evidence_bars(evidence: Sequence[TechniqueContribution]) -> None:
    """Which techniques produced a candidate's score, as contribution bars.

    Args:
        evidence: Ranked contributions from
            :func:`ttp_similarity.engine.query.explain_candidate`.
    """
    if not evidence:
        return
    top = max(e.contribution for e in evidence) or 1.0
    rows = "".join(
        '<div class="ttp-ev__r">'
        f'<span class="ttp-ev__id">{escape(e.technique_id)}</span>'
        f'<span class="ttp-ev__n">{escape(e.technique_name)}</span>'
        f'<span class="ttp-ev__b"><i style="width:'
        f'{_pct(e.contribution / top):.1f}%"></i></span>'
        f'<span class="ttp-ev__p">{e.contribution * 100:.1f}%</span>'
        "</div>"
        for e in evidence
    )
    _html(f'<div class="ttp-ev">{rows}</div>')


def table(
    columns: Sequence[tuple[str, str]],
    rows: Sequence[Sequence[object]],
    grid: str,
) -> None:
    """A generic bordered table, replacing ``st.dataframe`` for short lists.

    Used where the row count is bounded (neighbours, technique lists) and the
    grid look of a dataframe would break the page. Long or explorable tables
    should still use ``st.dataframe``.

    Args:
        columns: ``(heading, cell_class)`` per column. ``cell_class`` is one of
            ``ttp-rank``, ``ttp-name``, ``ttp-id``, ``ttp-num``,
            ``ttp-num ttp-num--sub``, ``ttp-cell``.
        rows: Cell values; already formatted, escaped here. A value may carry
            markup only if it was produced by another function in this module.
        grid: The CSS ``grid-template-columns`` value shared by every row.
    """
    style = f"grid-template-columns: {grid};"
    head = "".join(f"<span>{escape(name)}</span>" for name, _ in columns)
    out = [f'<div class="ttp-tr ttp-tr--h" style="{style}">{head}</div>']
    for row in rows:
        # Every cell carries its own value as `title`: cells clip rather than
        # wrap, so hovering has to be able to recover what was cut off.
        cells = "".join(
            f'<span class="{cls}" title="{escape(value)}">{escape(value)}</span>'
            for (_, cls), value in zip(columns, row)
        )
        out.append(f'<div class="ttp-tr ttp-tr--b" style="{style}">{cells}</div>')
    _html(f'<div class="ttp-tbl">{"".join(out)}</div>')
