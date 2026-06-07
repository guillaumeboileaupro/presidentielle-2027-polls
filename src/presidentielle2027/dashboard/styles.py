from __future__ import annotations

import streamlit as st


WIKI_DASHBOARD_CSS = """
<style>
    :root {
        color-scheme: light;
        --fi-violet: #9a36e0;
        --fi-red: #ef1926;
        --fi-pink: #e6255b;
        --fi-yellow: #ffec00;
        --fi-green: #4bb166;
        --fi-black: #1d1d1b;
        --fi-bg: #faf7ff;
        --fi-panel: #ffffff;
        --fi-border: #e4d7fa;
        --fi-border-strong: #c6a9f4;
        --fi-text: #1d1d1b;
        --fi-muted: #5f566c;
    }
    html {
        color-scheme: light !important;
    }
    #MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
        visibility: hidden;
        height: 0;
        position: fixed;
    }
    html, body {
        background: var(--fi-bg) !important;
        color: var(--fi-text) !important;
    }
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(154, 54, 224, 0.08), transparent 24%),
            radial-gradient(circle at top right, rgba(239, 25, 38, 0.06), transparent 20%),
            var(--fi-bg) !important;
        color: var(--fi-text) !important;
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stHeader"],
    [data-testid="stBottomBlockContainer"],
    section.main,
    .main,
    .block-container {
        background: transparent !important;
        color: var(--fi-text) !important;
    }
    html, body, [class*="css"] {
        font-family: "Public Sans", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    }
    [data-testid="stAppViewContainer"] > .main {
        max-width: 1380px;
        padding-top: 1rem;
    }
    h1, h2, h3 {
        color: var(--fi-text);
        font-weight: 800;
        letter-spacing: -0.01em;
        overflow-wrap: anywhere;
    }
    h1 {
        font-size: 2.2rem;
        line-height: 1;
        margin: 0;
    }
    .fi-hero {
        background:
            linear-gradient(135deg, rgba(154, 54, 224, 0.98), rgba(239, 25, 38, 0.94)),
            #fff;
        color: #fff;
        border-radius: 24px;
        padding: 1.35rem 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 18px 45px rgba(154, 54, 224, 0.18);
    }
    .fi-hero__identity {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .fi-hero__badge {
        width: 78px;
        height: 78px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 255, 255, 0.16);
        border: 1px solid rgba(255, 255, 255, 0.32);
        border-radius: 20px;
        color: #fff;
        font-size: 1.6rem;
        font-weight: 900;
        letter-spacing: 0.06em;
    }
    .fi-kicker {
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.76rem;
        font-weight: 800;
        opacity: 0.92;
        margin-bottom: 0.35rem;
    }
    .fi-hero p {
        margin: 0.45rem 0 0;
        max-width: 920px;
        color: rgba(255, 255, 255, 0.94);
        line-height: 1.5;
        font-size: 0.98rem;
    }
    .wiki-title {
        display: none;
    }
    .wiki-note {
        background: #fff;
        border: 1px solid var(--fi-border);
        border-left: 6px solid var(--fi-red);
        border-radius: 16px;
        padding: 0.9rem 1rem;
        margin: 0.6rem 0 1rem 0;
        font-size: 0.98rem;
        line-height: 1.45;
        box-shadow: 0 8px 18px rgba(154, 54, 224, 0.08);
        overflow: hidden;
        overflow-wrap: anywhere;
    }
    .wiki-panel {
        background: var(--fi-panel);
        border: 1px solid var(--fi-border);
        border-radius: 20px;
        padding: 0.95rem 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 10px 24px rgba(17, 12, 34, 0.04);
        overflow: hidden;
        overflow-wrap: anywhere;
    }
    .wiki-muted {
        color: var(--fi-muted);
        font-size: 0.96rem;
        line-height: 1.45;
        margin-bottom: 0.7rem;
        overflow-wrap: anywhere;
    }
    .stMarkdown p,
    .stMarkdown li,
    .stCaption,
    label,
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"] {
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
    }
    [data-testid="stMetric"] {
        background: #fff !important;
        border: 1px solid var(--fi-border) !important;
        border-radius: 18px;
        padding: 0.65rem 0.8rem;
        box-shadow: 0 10px 24px rgba(17, 12, 34, 0.04);
        overflow: hidden;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--fi-border);
        border-radius: 18px;
        overflow: hidden;
    }
    [data-testid="stSidebar"] {
        background: #fff !important;
        color: var(--fi-text) !important;
    }
    [data-testid="stSidebarContent"] {
        background: #fff !important;
        color: var(--fi-text) !important;
    }
    [data-testid="stSidebar"] * {
        color: var(--fi-text) !important;
    }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div {
        color: var(--fi-text) !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="input"] > div,
    [data-testid="stSidebar"] .stDateInput > div,
    [data-testid="stSidebar"] .stSelectbox > div,
    [data-testid="stSidebar"] .stMultiSelect > div,
    [data-testid="stSidebar"] .stCheckbox > label {
        background: #ffffff !important;
        color: #202122 !important;
        border-color: var(--fi-border) !important;
        border-radius: 14px !important;
    }
    [data-testid="stSidebar"] svg {
        fill: var(--fi-muted) !important;
    }
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    .stDateInput > div,
    .stSelectbox > div,
    .stMultiSelect > div {
        background: #fff !important;
        color: var(--fi-text) !important;
        border: 1px solid var(--fi-border) !important;
        border-radius: 14px !important;
        box-shadow: none !important;
    }
    [role="listbox"],
    [role="option"],
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="select"] ul,
    [data-baseweb="select"] li {
        background: #ffffff !important;
        color: var(--fi-text) !important;
    }
    [role="dialog"] {
        background: #ffffff !important;
        color: var(--fi-text) !important;
    }
    button[kind],
    button[data-testid],
    .stButton > button {
        background: #ffffff !important;
        color: var(--fi-text) !important;
        border: 1px solid var(--fi-border) !important;
        border-radius: 999px !important;
    }
    .stMarkdown,
    .stText,
    .stCaption,
    .stAlert,
    .stSelectbox label,
    .stDateInput label,
    .stCheckbox label {
        color: var(--fi-text) !important;
    }
    div[data-testid="stRadio"] {
        margin-bottom: 0.25rem;
    }
    div[data-testid="stRadio"] > label {
        font-weight: 800;
        color: var(--fi-text) !important;
        margin-bottom: 0.45rem;
    }
    div[data-testid="stRadio"] [role="radiogroup"] {
        display: flex !important;
        align-items: stretch;
        gap: 0.55rem;
        flex-wrap: wrap;
    }
    div[data-testid="stRadio"] [role="radiogroup"] label {
        margin: 0 !important;
        width: auto !important;
        min-height: 46px;
        display: inline-flex !important;
        align-items: center;
        justify-content: center;
        border-radius: 999px !important;
        border: 1px solid var(--fi-border) !important;
        background: rgba(154, 54, 224, 0.08) !important;
        padding: 0.2rem 0.95rem !important;
        box-shadow: none !important;
        transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
    }
    div[data-testid="stRadio"] [role="radiogroup"] label:hover {
        transform: translateY(-1px);
        border-color: var(--fi-border-strong) !important;
        box-shadow: 0 10px 22px rgba(154, 54, 224, 0.08);
    }
    div[data-testid="stRadio"] [role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] label p {
        margin: 0 !important;
        color: var(--fi-text) !important;
        font-weight: 700 !important;
        line-height: 1.2 !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, rgba(154, 54, 224, 0.14), rgba(239, 25, 38, 0.1)) !important;
        border-color: var(--fi-border-strong) !important;
        box-shadow: 0 14px 26px rgba(154, 54, 224, 0.12);
    }
    div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p {
        font-weight: 800 !important;
    }
    iframe {
        background: #ffffff !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.45rem;
        border-bottom: none;
        margin-bottom: 0.5rem;
        flex-wrap: wrap;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(154, 54, 224, 0.08);
        border: 1px solid var(--fi-border);
        border-radius: 999px;
        color: var(--fi-text);
        padding: 0.52rem 1rem;
        font-weight: 700;
        white-space: normal;
        min-height: 44px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(154, 54, 224, 0.12), rgba(239, 25, 38, 0.08)) !important;
        border-color: var(--fi-border-strong) !important;
        font-weight: 800;
        color: var(--fi-text) !important;
    }
    .fi-chip-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.7rem;
        margin: 0.3rem 0 1rem;
    }
    .fi-chip {
        display: grid;
        grid-template-columns: auto 1fr auto;
        gap: 0.75rem;
        align-items: center;
        background: #fff;
        border: 2px solid var(--fi-border);
        border-radius: 18px;
        padding: 0.75rem 0.85rem;
        box-shadow: 0 14px 28px rgba(17, 12, 34, 0.05);
    }
    .fi-chip__media {
        width: 44px;
        height: 44px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #fff;
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid rgba(17, 12, 34, 0.08);
    }
    .fi-chip__logo {
        width: 36px;
        height: 36px;
        object-fit: contain;
    }
    .fi-chip__fallback {
        width: 36px;
        height: 36px;
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-size: 0.72rem;
        font-weight: 800;
    }
    .fi-chip__content {
        min-width: 0;
    }
    .fi-chip__title {
        font-weight: 800;
        font-size: 0.97rem;
        line-height: 1.15;
        color: var(--fi-text);
    }
    .fi-chip__meta {
        color: var(--fi-muted);
        font-size: 0.84rem;
        margin-top: 0.18rem;
    }
    .fi-chip__value {
        font-weight: 900;
        font-size: 1.05rem;
        white-space: nowrap;
    }
    .fi-empty {
        background: #fff;
        border: 1px dashed var(--fi-border-strong);
        color: var(--fi-muted);
        border-radius: 16px;
        padding: 0.9rem 1rem;
        margin-bottom: 1rem;
    }
    [data-testid="stPlotlyChart"] {
        background: #fff;
        border: 1px solid var(--fi-border);
        border-radius: 20px;
        padding: 0.35rem 0.35rem 0.1rem 0.35rem;
        overflow: hidden;
        box-shadow: 0 10px 24px rgba(17, 12, 34, 0.04);
    }
    [data-testid="stPlotlyChart"] > div {
        max-width: 100%;
    }
    .js-plotly-plot,
    .plotly,
    .plot-container {
        max-width: 100% !important;
    }
    details {
        background: #fff;
        border: 1px solid var(--fi-border);
        border-radius: 18px;
        padding: 0.35rem 0.8rem;
        box-shadow: 0 10px 24px rgba(17, 12, 34, 0.04);
    }
    summary {
        overflow-wrap: anywhere;
    }
    div[data-testid="stPopover"] > div > button {
        min-width: 48px !important;
        min-height: 48px !important;
        width: 48px !important;
        border-radius: 999px !important;
        padding: 0 !important;
        font-size: 1.15rem !important;
        font-weight: 900 !important;
        color: #fff !important;
        background: linear-gradient(135deg, rgba(154, 54, 224, 0.96), rgba(239, 25, 38, 0.94)) !important;
        border: none !important;
        box-shadow: 0 14px 28px rgba(154, 54, 224, 0.2) !important;
    }
    div[data-testid="stPopover"] > div > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 16px 30px rgba(154, 54, 224, 0.24) !important;
    }
    @media (max-width: 1100px) {
        [data-testid="stAppViewContainer"] > .main {
            max-width: 100%;
        }
        [data-testid="stPlotlyChart"] {
            padding: 0.2rem;
        }
        div[data-testid="stPopover"] > div > button {
            min-width: 44px !important;
            min-height: 44px !important;
            width: 44px !important;
        }
    }
</style>
"""


def apply_dashboard_styles() -> None:
    st.markdown(WIKI_DASHBOARD_CSS, unsafe_allow_html=True)


def apply_browser_chrome_overrides() -> None:
    return None
