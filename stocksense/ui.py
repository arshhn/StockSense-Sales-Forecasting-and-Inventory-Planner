"""Small presentation helpers for the Streamlit dashboard.

Typography uses the visitor's installed Helvetica with local fallbacks. No font
downloads, external stylesheets, or data-processing behavior are involved.
"""

from html import escape

import plotly.graph_objects as go
import streamlit as st


FONT_FAMILY = '"Helvetica Neue", Helvetica, Arial, sans-serif'
INK = "#172b36"
MUTED = "#627780"
TEAL = "#137c66"
PALETTE = [TEAL, "#53738b", "#c08a45", "#86779d", "#4f999f"]


def apply_style() -> None:
    """Apply the visual theme without overriding Streamlit's icon font."""
    st.markdown(
        """
        <style>
        html, body, .stApp, [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"], input, textarea, select, button,
        h1, h2, h3, h4, h5, h6, p, label,
        [data-testid="stMarkdownContainer"],
        [data-testid="stMetricLabel"], [data-testid="stMetricValue"],
        [data-baseweb="select"], [data-baseweb="popover"],
        [data-baseweb="tab"], [data-baseweb="input"] {
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
        }
        .stApp { background: #f5f7f7; color: #172b36; }
        [data-testid="stHeader"] { background: #f5f7f7; }
        [data-testid="stMainBlockContainer"] {
            max-width: 1500px;
            padding: 2.2rem 3rem 3.5rem;
        }
        [data-testid="stVerticalBlock"] { gap: 1.15rem; }
        h1, h2, h3, h4 { color: #172b36; letter-spacing: -0.035em; }
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stHeadingWithActionElements"] h1,
        .ss-page-header h1 {
            font-size: 2.15rem; line-height: 1.12; font-weight: 700;
        }
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stHeadingWithActionElements"] h2 {
            font-size: 1.45rem; font-weight: 650;
        }
        [data-testid="stMarkdownContainer"] h3,
        [data-testid="stHeadingWithActionElements"] h3 {
            font-size: 1.12rem; font-weight: 650; line-height: 1.3;
        }
        p { line-height: 1.6; }
        a { color: #137c66; }
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p { color: #627780; }
        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #e0e7e7;
        }
        [data-testid="stSidebarUserContent"] { padding: 1.6rem 1.35rem; }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 1.1rem; }
        [data-testid="stSidebar"] h2 { font-size: 0.91rem; letter-spacing: 0; }
        [data-testid="stSidebar"] label p { font-size: 0.8rem; font-weight: 600; }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
            font-size: 0.76rem; line-height: 1.55;
        }
        [data-baseweb="select"] > div, [data-baseweb="input"] {
            background: #f8faf9;
            border-color: #dce5e3;
            border-radius: 8px;
        }
        [data-baseweb="select"] { font-size: 0.85rem; }
        [data-testid="stMetric"] {
            min-height: 108px;
            padding: 1.1rem 1.2rem;
            background: #ffffff;
            border: 1px solid #e0e7e7;
            border-radius: 12px;
        }
        [data-testid="stMetricLabel"] p {
            font-size: 0.76rem;
            font-weight: 500;
            color: #627780;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.6rem;
            font-weight: 650;
            letter-spacing: -0.045em;
            line-height: 1.3;
            color: #172b36;
        }
        [data-testid="stMetricDelta"] { font-size: 0.75rem; }
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 1.7rem;
            border-bottom: 1px solid #dce5e3;
            background: transparent;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            height: 48px;
            padding: 0 0 12px;
            color: #627780;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] p {
            font-size: 0.88rem;
            font-weight: 550;
        }
        [data-testid="stTabs"] [aria-selected="true"] { color: #137c66; }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            background-color: #137c66;
            height: 3px;
            border-radius: 3px;
        }
        [data-testid="stTabs"] [data-baseweb="tab-panel"] { padding-top: 1.5rem; }
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            border-radius: 12px;
        }
        [class*="st-key-panel-"],
        [data-testid="stVerticalBlockBorderWrapper"]:has(> [class*="st-key-panel-"]) {
            background: #ffffff;
            border-color: #e0e7e7 !important;
            border-radius: 12px;
        }
        [data-testid="stPlotlyChart"] {
            background: #ffffff;
            border-radius: 10px;
            overflow: hidden;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid #e0e7e7;
            border-radius: 9px;
            overflow: hidden;
        }
        [data-testid="stExpander"] {
            background: #ffffff;
            border-color: #e0e7e7;
            border-radius: 9px;
        }
        [data-testid="stAlert"] {
            border-radius: 9px;
            font-size: 0.86rem;
        }
        .ss-brand {
            display: flex; align-items: center; gap: 0.7rem;
            padding: 0 0 1.65rem; margin-bottom: 0.3rem;
            border-bottom: 1px solid #e0e7e7;
        }
        .ss-brand-mark {
            display: flex; align-items: center; justify-content: center;
            width: 38px; height: 38px; flex: 0 0 38px;
            background: #137c66; color: #ffffff;
            border-radius: 10px; font-size: 0.85rem; font-weight: 700;
            letter-spacing: -0.03em;
        }
        .ss-brand-name { font-size: 1.2rem; font-weight: 700; letter-spacing: -0.045em; }
        .ss-brand-caption {
            margin-top: 0.1rem; font-size: 0.66rem; color: #627780;
            letter-spacing: 0.07em; text-transform: uppercase;
        }
        .ss-page-header {
            display: flex; justify-content: space-between; align-items: flex-start;
            gap: 1.5rem; margin: 0.25rem 0 0.35rem;
        }
        .ss-eyebrow {
            margin: 0 0 0.6rem; color: #627780;
            font-size: 0.67rem; font-weight: 650; letter-spacing: 0.13em;
            text-transform: uppercase;
        }
        .ss-page-header h1 { margin: 0; padding: 0; }
        .ss-page-description {
            color: #627780; font-size: 0.88rem; margin-top: 0.65rem;
            line-height: 1.6;
        }
        .ss-badge {
            display: inline-block; flex-shrink: 0;
            padding: 0.45rem 0.7rem; margin-top: 1.75rem;
            background: #edf3f1; border: 1px solid #d6e4de;
            border-radius: 6px; color: #356350;
            font-size: 0.7rem; font-weight: 550; white-space: nowrap;
        }
        .ss-section-eyebrow {
            color: #627780; font-size: 0.7rem; font-weight: 650;
            text-transform: uppercase; letter-spacing: 0.09em;
        }
        .ss-note {
            padding: 0.8rem 1rem; border-left: 3px solid #b9cfc6;
            background: #edf3f1; color: #4b645b; border-radius: 0 7px 7px 0;
            font-size: 0.8rem; line-height: 1.55;
        }
        @media (max-width: 1100px) {
            [data-testid="stMainBlockContainer"] { padding: 2rem 1.6rem 3rem; }
            [data-testid="stMetric"] { padding: 1rem; }
            [data-testid="stMetricValue"] { font-size: 1.45rem; }
            [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPlotlyChart"]) {
                flex-wrap: wrap;
            }
            [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stPlotlyChart"]) > [data-testid="stColumn"] {
                flex: 1 1 100%; width: 100%; min-width: 0;
            }
        }
        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] { padding: 1.5rem 1rem 2rem; }
            .ss-page-header { flex-direction: column; gap: 0.5rem; }
            [data-testid="stMarkdownContainer"] .ss-page-header h1 { font-size: 1.85rem; }
            .ss-badge { margin-top: 0; }
            [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 1.1rem; }
            [data-testid="stTabs"] [data-baseweb="tab"] p { font-size: 0.79rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    """Render the static product wordmark in the sidebar."""
    st.sidebar.markdown(
        '<div class="ss-brand"><div class="ss-brand-mark">SS</div>'
        '<div><div class="ss-brand-name">StockSense</div>'
        '<div class="ss-brand-caption">Sales &amp; inventory</div></div></div>',
        unsafe_allow_html=True,
    )


def page_header(
    title: str = "Sales & inventory",
    subtitle: str = "Plan weekly sales and replenishment. Forecasts begin after the last complete historical week.",
) -> None:
    """Render the page heading and the historical-data context badge."""
    st.markdown(
        '<div class="ss-page-header"><div><div class="ss-eyebrow">Planning workspace</div>'
        f'<h1>{escape(title)}</h1><div class="ss-page-description">{escape(subtitle)}</div>'
        '</div><div class="ss-badge">Historical demo · 2009–2011</div></div>',
        unsafe_allow_html=True,
    )


def style_figure(fig: go.Figure, height: int = 340) -> go.Figure:
    """Give Plotly charts the dashboard's typography, axes, and color palette.

    Explicit custom trace colors are retained. Plotly's default series colors
    are replaced so charts created with either Express or graph objects match.
    """
    plotly_defaults = {
        "#636efa", "#ef553b", "#00cc96", "#ab63fa", "#ffa15a",
        "#19d3f3", "#ff6692", "#b6e880", "#ff97ff", "#fecb52",
    }
    # Streamlit's Plotly template uses placeholder colors before rendering.
    plotly_defaults.update(f"#{number:06d}" for number in range(1, 11))
    for index, trace in enumerate(fig.data):
        color = PALETTE[index % len(PALETTE)]
        if hasattr(trace, "line"):
            current = trace.line.color
            if current is None or (isinstance(current, str) and current.lower() in plotly_defaults):
                trace.line.color = color
        if hasattr(trace, "marker"):
            current = trace.marker.color
            if current is None or (isinstance(current, str) and current.lower() in plotly_defaults):
                trace.marker.color = color
    fig.update_layout(
        font={"family": FONT_FAMILY, "size": 12, "color": MUTED},
        title={"font": {"family": FONT_FAMILY, "size": 15, "color": INK}, "x": 0.025},
        height=height,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        colorway=PALETTE,
        margin={"l": 18, "r": 22, "t": 52 if fig.layout.title.text else 24, "b": 38},
        legend={
            "orientation": "h", "yanchor": "bottom", "y": 1.03,
            "xanchor": "right", "x": 1, "title_text": "",
            "font": {"size": 11}, "bgcolor": "rgba(0,0,0,0)",
        },
        hoverlabel={"bgcolor": INK, "font": {"family": FONT_FAMILY, "color": "#ffffff", "size": 12}},
        modebar={"bgcolor": "rgba(255,255,255,0.9)", "color": MUTED, "activecolor": TEAL},
    )
    fig.update_xaxes(
        showgrid=False, zeroline=False, showline=True, linecolor="#e3eaea",
        tickfont={"size": 11}, title_font={"size": 11}, automargin=True,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="#edf1f1", gridwidth=1,
        zeroline=False, showline=False, tickfont={"size": 11},
        title_font={"size": 11}, automargin=True,
    )
    return fig
