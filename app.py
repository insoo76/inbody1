"""InBody PDF 업로드 → 분석 → 상세 처방 Streamlit 앱."""

from __future__ import annotations

import html
import re
from copy import deepcopy
from dataclasses import dataclass

import plotly.graph_objects as go
import streamlit as st

from chart_theme import chart_layout, get_palette

from parser import (
    InBodyResult,
    OcrNotAvailableError,
    check_ocr_ready,
    is_image_filename,
    normalize_inbody_result,
    parse_inbody_pdf,
    parse_inbody_upload,
)
from prescription import PrescriptionReport, build_prescription
from trend import (
    TrendReport,
    build_trend_report,
    format_delta_text,
    make_trend_chart,
)
from missions import (
    WEEK_DAYS,
    count_mission_progress,
    generate_missions,
    mission_checkbox_key,
    sync_mission_profile,
)
from heatmap import (
    build_body_heatmap,
    render_body_figure,
    render_legend_html,
    render_zone_cards_html,
)
from analysis import (
    build_multidim_analysis,
    make_quadrant_chart,
    make_radar_chart,
)
from persona import (
    PersonaDashboard,
    build_persona_dashboard,
    make_speedometer,
    render_persona_card_html,
)
from phase_angle import (
    PhaseAngleReport,
    build_phase_angle_report,
    format_delta_badge,
    make_phase_angle_chart,
)
from bmr_viz import BmrReport, build_bmr_report, render_bmr_widget_html
from icons import section_heading_html, section_title_html
from meal_plan import build_meal_plan, render_meal_plan_html
from rx_cards import render_prescription_cards
from progress_store import (
    bootstrap_user_progress,
    commit_user_progress,
    get_body_evolution,
    render_body_evolution_html,
)
from weekly_plan_ui import (
    build_weekly_plan_rows,
    collect_statuses,
    render_weekly_plan_table,
    sync_weekly_plan_profile,
    weekly_plan_done_key,
)
from gamification_engine import (
    EvolutionState,
    LaunchDashboard,
    build_launch_dashboard,
    evaluate_evolution,
    render_evolution_celebration_html,
    render_launch_banner_html,
    render_rewards_strip_html,
)
from slime_growth import SlimeGrowthReport, build_slime_growth_report, render_slime_growth_html


@dataclass
class PrescriptionContext:
    trend: TrendReport | None
    dashboard: PersonaDashboard
    body_evo: object
    missions: list
    mission_progress: object | None
    growth: SlimeGrowthReport | None
    evolution: EvolutionState | None
    launch: LaunchDashboard | None
    phase_report: PhaseAngleReport | None
    bmr_report: BmrReport | None

st.set_page_config(
    page_title="SomaRx 2.0 · InBody 처방 클리닉",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PRIORITY_META = {
    "높음": ("#B43B2A", "#FCEDEA", "우선"),
    "보통": ("#B86A1C", "#FFF4E8", "권장"),
    "참고": ("#1F6F8B", "#EAF5F9", "참고"),
}

STATUS_META = {
    "low": ("부족", "#B43B2A", "#FCEDEA"),
    "normal": ("정상", "#1F7A4D", "#E8F6EE"),
    "high": ("과다", "#B86A1C", "#FFF4E8"),
    "unknown": ("미확인", "#6B7C76", "#EEF1F0"),
}


def _esc(text: object) -> str:
    return html.escape(str(text) if text is not None else "")


def _plain(text: object) -> str:
    """마크다운 강조 기호 제거."""
    s = str(text) if text is not None else ""
    return re.sub(r"\*+", "", s).strip()


def _inject_css(*, dark_mode: bool = False) -> None:
    dark_block = _dark_theme_css() if dark_mode else ""
    css = """
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&display=swap');
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

        :root {
          --primary: #0F172A;
          --mint: #10B981;
          --trust-blue: #3B82F6;
          --ink: #0F172A;
          --ink-soft: #334155;
          --muted: #64748B;
          --line: #CBD5E1;
          --line-soft: #E2E8F0;
          --surface: #FFFFFF;
          --surface-solid: #FFFFFF;
          --srx-radius: 16px;
          --srx-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
          --srx-shadow-hover: 0 4px 12px rgba(15, 23, 42, 0.08);
          --brand: #10B981;
          --brand-deep: #0F172A;
          --brand-mid: #059669;
          --brand-mist: #D1FAE5;
          --sand: #F3EADF;
          --warn: #8A6A1F;
          --font-sans: 'Pretendard', 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo',
                       'Segoe UI', sans-serif;
          --font-display: 'Poppins', 'Pretendard', 'Noto Sans KR', sans-serif;
        }

        @keyframes srxFadeUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes srxShimmer {
          0% { background-position: 0% 50%; }
          100% { background-position: 100% 50%; }
        }
        @keyframes srxBreathe {
          0%, 100% { opacity: 0.45; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(1.04); }
        }

        html, body, [class*="css"] {
          font-family: var(--font-sans);
        }

        .stApp {
          background: #F8FAFC;
          color: var(--ink);
        }
        .stApp::before {
          display: none;
        }
        .block-container {
          position: relative;
          z-index: 1;
          padding-top: 1.35rem !important;
          padding-bottom: 3.5rem !important;
          max-width: 1080px;
        }

        /* 2단계 — Sticky 요약 바 */
        .srx-sticky-bar {
          position: sticky;
          top: 0;
          z-index: 999;
          margin: 0 0 1rem;
          padding: 0.65rem 0;
          background: rgba(248, 250, 252, 0.92);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          border-bottom: 1px solid var(--line-soft);
          animation: srxFadeUp 0.4s ease both;
        }
        .srx-sticky-inner {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 0.45rem;
        }
        .srx-sticky-chip {
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          padding: 0.38rem 0.72rem;
          border-radius: 999px;
          font-size: 0.78rem;
          font-weight: 600;
          color: var(--ink-soft) !important;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          box-shadow: var(--srx-shadow);
          white-space: nowrap;
        }
        .srx-sticky-chip.name {
          font-family: var(--font-display);
          font-weight: 700;
          color: var(--brand-deep) !important;
          border-color: rgba(16, 185, 129, 0.28);
          background: #ECFDF5;
        }
        .srx-sticky-chip.type {
          color: var(--brand-deep) !important;
          background: #F8FAFC;
        }
        .srx-sticky-chip.metric strong {
          color: var(--brand-deep) !important;
          font-variant-numeric: tabular-nums;
        }
        .srx-sticky-chip.metric.up strong { color: #047857 !important; }
        .srx-sticky-chip.metric.down strong { color: #C2410C !important; }
        .srx-sticky-chip.score {
          margin-left: auto;
          color: #1D4ED8 !important;
          background: #EFF6FF;
          border-color: rgba(59, 130, 246, 0.25);
        }
        .srx-sticky-chip.score strong {
          color: #1D4ED8 !important;
          font-variant-numeric: tabular-nums;
        }

        /* 2단계 — Bento 섹션 */
        .srx-bento {
          margin-bottom: 1.5rem;
        }
        .srx-bento-row {
          margin-bottom: 0.85rem;
        }
        .srx-bento-row:last-child {
          margin-bottom: 0;
        }
        .srx-bento-cell {
          min-width: 0;
        }
        .srx-bento-cell .srx-verdict,
        .srx-bento-cell .srx-phase-angle,
        .srx-bento-cell .srx-bmr,
        .srx-bento-cell .srx-heatmap,
        .srx-bento-cell .srx-mission,
        .srx-bento-cell .srx-slime-growth {
          margin-bottom: 0;
        }
        .srx-bento-cell .srx-phase-comment,
        .srx-bento-cell .srx-bmr-comment {
          margin-top: 0.65rem;
        }

        section[data-testid="stSidebar"] {
          background: #FFFFFF !important;
          border-right: 1px solid var(--line-soft);
        }
        section[data-testid="stSidebar"] > div {
          padding-top: 1.25rem;
        }
        section[data-testid="stSidebar"] * { color: var(--ink) !important; }
        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stMarkdown li {
          color: var(--muted) !important;
          font-size: 0.88rem;
          line-height: 1.55;
        }
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
          background: var(--surface-solid);
          border: 1.5px dashed #9BBFB4;
          border-radius: 16px;
          padding: 0.85rem 0.75rem 0.4rem;
          transition: border-color 0.2s ease, background 0.2s ease;
        }
        section[data-testid="stSidebar"] [data-testid="stFileUploader"]:hover {
          border-color: var(--brand);
          background: #F4FBFT;
          background: #F4FBF8;
        }
        section[data-testid="stSidebar"] button {
          background: var(--brand) !important;
          color: #FFFFFF !important;
          border: none !important;
          border-radius: 12px !important;
          font-weight: 700 !important;
          letter-spacing: -0.01em;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] {
          background: rgba(255,255,255,0.65);
          border: 1px solid var(--line-soft);
          border-radius: 14px;
        }

        #MainMenu, footer, header { visibility: hidden; }

        .stTabs [data-baseweb="tab-list"] {
          gap: 0.25rem;
          background: #F1F5F9;
          border: none;
          border-radius: 12px;
          padding: 4px;
          margin-bottom: 0.75rem;
        }
        .stTabs [data-baseweb="tab"] {
          border-radius: 10px;
          padding: 0.65rem 1.15rem;
          font-weight: 600;
          font-size: 0.9rem;
          color: var(--muted);
          background: transparent;
          border: none !important;
        }
        .stTabs [aria-selected="true"] {
          color: var(--brand-deep) !important;
          background: #FFFFFF !important;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
          border-bottom: none !important;
        }
        .stTabs [data-baseweb="tab-highlight"],
        .stTabs [data-baseweb="tab-border"] {
          display: none;
        }

        /* 처방 탭 접기 — 메인 expander */
        .stMain [data-testid="stExpander"] {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
          margin-bottom: 0.65rem;
          overflow: hidden;
        }
        .stMain [data-testid="stExpander"] details {
          border: none;
        }
        .stMain [data-testid="stExpander"] summary {
          font-family: var(--font-sans);
          font-weight: 700;
          font-size: 0.95rem;
          color: var(--ink);
          padding: 0.65rem 0.85rem;
          letter-spacing: -0.02em;
        }
        .stMain [data-testid="stExpander"] summary:hover {
          color: var(--brand);
        }
        .stMain [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
          padding: 0.35rem 0.85rem 0.85rem;
          border-top: 1px solid var(--line-soft);
        }
        .srx-section-hint {
          margin: 0.15rem 0 0.75rem;
          font-size: 0.82rem;
          color: var(--muted);
          letter-spacing: -0.01em;
        }

        .stSpinner > div {
          border-top-color: var(--brand) !important;
        }

        /* —— Empty state (PDF 업로드 전) —— */
        .srx-empty-hero {
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 1.5rem;
          align-items: center;
          padding: 1.75rem 1.65rem;
          margin: 0.2rem 0 1rem;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
          animation: srxFadeUp 0.55s ease both;
        }
        @media (max-width: 720px) {
          .srx-empty-hero { grid-template-columns: 1fr; text-align: center; }
        }
        .srx-empty-visual {
          width: 112px;
          height: 112px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 20px;
          background: linear-gradient(165deg, #ECFDF5 0%, #EFF6FF 100%);
          border: 1px solid var(--line-soft);
          color: var(--brand);
        }
        .srx-empty-visual svg {
          width: 72px;
          height: 72px;
        }
        .srx-empty-kicker {
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--brand) !important;
          margin: 0 0 0.45rem;
        }
        .srx-empty-brand {
          font-family: var(--font-display);
          font-size: clamp(1.75rem, 4vw, 2.35rem);
          font-weight: 700;
          margin: 0;
          letter-spacing: -0.03em;
          color: var(--brand-deep) !important;
          line-height: 1.15;
        }
        .srx-empty-lede {
          margin: 0.65rem 0 0;
          max-width: 34rem;
          font-size: 0.95rem;
          line-height: 1.65;
          color: var(--muted) !important;
        }
        .srx-empty-cta {
          margin-top: 1rem;
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.55rem 0.9rem;
          border-radius: 999px;
          background: #ECFDF5;
          border: 1px solid rgba(16, 185, 129, 0.28);
          font-size: 0.84rem;
          font-weight: 600;
          color: #047857 !important;
        }
        .srx-empty-cta-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--brand);
        }

        /* 메인 PDF 드롭존 */
        .srx-upload-zone {
          margin: 0 0 1rem;
          padding: 1.35rem 1.25rem 0.35rem;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
        }
        .srx-upload-zone-inner {
          display: flex;
          align-items: center;
          gap: 1rem;
          margin-bottom: 0.65rem;
        }
        .srx-upload-zone-icon {
          width: 52px;
          height: 52px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 14px;
          background: linear-gradient(165deg, #ECFDF5 0%, #EFF6FF 100%);
          border: 1px solid var(--line-soft);
          color: var(--brand);
          flex-shrink: 0;
        }
        .srx-upload-zone-icon svg {
          width: 28px;
          height: 28px;
        }
        .srx-upload-zone-title {
          margin: 0;
          font-family: var(--font-display);
          font-size: 1.05rem;
          font-weight: 700;
          color: var(--ink);
          letter-spacing: -0.02em;
        }
        .srx-upload-zone-sub {
          margin: 0.2rem 0 0;
          font-size: 0.86rem;
          color: var(--muted);
          line-height: 1.45;
        }
        .srx-reupload-row {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 0.65rem;
          margin: 0 0 0.65rem;
        }
        .srx-reupload-text {
          font-size: 0.82rem;
          font-weight: 600;
          color: var(--muted);
          letter-spacing: -0.01em;
        }
        .srx-upload-marker { display: none; }
        .stMain [data-testid="stFileUploader"] {
          background: var(--surface-solid);
          border: 2px dashed #94A3B8;
          border-radius: 14px;
          padding: 0.85rem 0.75rem 0.5rem;
          transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
        }
        .stMain [data-testid="stFileUploader"]:hover {
          border-color: var(--brand);
          background: #F4FBF8;
          box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.12);
        }
        .stMain [data-testid="stFileUploader"] button {
          background: var(--brand) !important;
          color: #FFFFFF !important;
          border: none !important;
          border-radius: 10px !important;
          font-weight: 700 !important;
        }
        .stMain:has(.srx-upload-marker.hero) [data-testid="stFileUploader"] {
          min-height: 120px;
          border-color: #6EE7B7;
          background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 100%);
        }
        .stMain:has(.srx-upload-marker.hero) [data-testid="stFileUploader"] section {
          padding: 0.35rem 0;
        }
        .stMain:has(.srx-upload-marker.compact) [data-testid="stFileUploader"] {
          min-height: 0;
          padding: 0.35rem 0.55rem 0.25rem;
          border-style: solid;
          border-width: 1px;
          max-width: 280px;
          margin-left: auto;
        }
        .stMain:has(.srx-upload-marker.compact) [data-testid="stFileUploader"] small {
          display: none;
        }
        .srx-disclaimer {
          margin: 1.25rem 0 0;
          padding: 0.85rem 1rem;
          font-size: 0.8rem;
          color: var(--muted);
          line-height: 1.5;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: 12px;
        }

        .srx-kicker {
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--brand) !important;
        }
        .srx-brand {
          font-family: var(--font-display);
          font-weight: 700;
          letter-spacing: -0.02em;
        }

        .srx-steps {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 1rem;
          margin: 0.5rem 0 1.5rem;
          animation: srxFadeUp 0.75s ease 0.12s both;
        }
        .srx-step {
          padding: 1.15rem 1.1rem 1.2rem;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
        }
        .srx-step .n {
          font-family: var(--font-display);
          font-size: 1.35rem;
          color: var(--brand) !important;
          margin-bottom: 0.35rem;
        }
        .srx-step .t {
          font-weight: 700;
          color: var(--ink) !important;
          margin-bottom: 0.25rem;
          font-size: 0.95rem;
        }
        .srx-step .d {
          color: var(--muted) !important;
          font-size: 0.84rem;
          line-height: 1.5;
          word-break: keep-all;
        }

        /* —— Compact top bar (results) —— */
        .srx-topbar {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 1rem;
          margin-bottom: 1.15rem;
          padding-bottom: 0.85rem;
          border-bottom: 1px solid var(--line);
          animation: srxFadeUp 0.45s ease both;
        }
        .srx-topbar .mark {
          font-family: var(--font-display);
          font-size: 1.45rem;
          font-weight: 700;
          letter-spacing: -0.02em;
          color: var(--brand-deep) !important;
          margin: 0;
        }
        .srx-topbar .sub {
          font-size: 0.78rem;
          font-weight: 600;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--muted) !important;
        }

        /* —— Patient identity —— */
        .srx-identity {
          display: grid;
          grid-template-columns: 1.4fr repeat(4, 1fr);
          gap: 0;
          margin-bottom: 1.25rem;
          padding: 1.1rem 0;
          border-top: 1px solid var(--line);
          border-bottom: 1px solid var(--line);
          animation: srxFadeUp 0.5s ease 0.05s both;
        }
        .srx-id-cell {
          padding: 0.15rem 1rem 0.15rem 0;
          border-right: 1px solid var(--line-soft);
        }
        .srx-id-cell:last-child { border-right: none; padding-right: 0; }
        .srx-id-cell .k {
          font-size: 0.75rem;
          font-weight: 500;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          color: var(--muted) !important;
        }
        .srx-id-cell .v {
          margin-top: 0.28rem;
          font-size: 1.05rem;
          font-weight: 700;
          color: var(--ink) !important;
          line-height: 1.3;
          word-break: keep-all;
        }
        .srx-id-cell.name .v {
          font-family: var(--font-display);
          font-size: 1.5rem;
          font-weight: 650;
          letter-spacing: -0.02em;
        }

        .srx-metric {
          padding: 1rem 1.05rem;
          height: 100%;
          min-height: 108px;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
        }
        .srx-metric .k {
          color: var(--muted) !important;
          font-size: 0.75rem;
          font-weight: 500;
          letter-spacing: 0.04em;
        }
        .srx-metric .v {
          margin-top: 0.35rem;
          font-size: 2rem;
          font-weight: 700;
          color: var(--ink) !important;
          font-variant-numeric: tabular-nums;
          line-height: 1.15;
          letter-spacing: -0.02em;
          word-break: keep-all;
        }
        .srx-metric .s {
          margin-top: 0.3rem;
          font-size: 0.74rem;
          color: #6B817A !important;
          line-height: 1.35;
          word-break: keep-all;
        }
        .srx-badge {
          display: inline-block;
          margin-top: 0.45rem;
          padding: 0.16rem 0.45rem;
          border-radius: 4px;
          font-size: 0.7rem;
          font-weight: 700;
          letter-spacing: 0.02em;
        }

        .srx-verdict {
          position: relative;
          padding: 1.4rem 1.5rem 1.45rem 1.65rem;
          margin-bottom: 1.35rem;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-left: 3px solid var(--brand);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
          animation: srxFadeUp 0.55s ease both;
        }
        .srx-verdict .label {
          font-size: 0.7rem;
          font-weight: 700;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--brand) !important;
        }
        .srx-verdict .shape {
          font-family: var(--font-display);
          font-size: clamp(1.5rem, 3vw, 1.85rem);
          color: var(--brand-deep) !important;
          margin: 0.35rem 0 0.5rem;
          letter-spacing: -0.02em;
          word-break: keep-all;
        }
        .srx-verdict .summary {
          color: var(--ink-soft) !important;
          line-height: 1.7;
          word-break: keep-all;
          margin-bottom: 0.85rem;
          max-width: 52rem;
        }
        .srx-flags { display: flex; flex-wrap: wrap; gap: 0.4rem; }
        .srx-flag {
          background: #FCEDEA;
          color: #8E2F22 !important;
          border-left: 2px solid #E3A59A;
          padding: 0.28rem 0.6rem;
          font-size: 0.8rem;
          font-weight: 600;
        }

        .srx-rx {
          background: var(--surface-solid);
          margin: 0 0 0.85rem 0;
          border-top: 1px solid var(--line-soft);
          border-bottom: 1px solid var(--line-soft);
          overflow: hidden;
          animation: srxFadeUp 0.5s ease both;
        }
        .srx-rx-head {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 0.75rem;
          padding: 0.95rem 1.15rem;
          background: linear-gradient(90deg, #F5FAF8 0%, #FFFFFF 100%);
        }
        .srx-rx-title {
          font-family: var(--font-display);
          font-size: 1.18rem;
          color: var(--brand-deep) !important;
          margin: 0;
          letter-spacing: -0.015em;
          word-break: keep-all;
        }
        .srx-prio {
          font-size: 0.7rem;
          font-weight: 700;
          padding: 0.28rem 0.55rem;
          letter-spacing: 0.03em;
          white-space: nowrap;
        }
        .srx-rx-body { padding: 0.15rem 1.15rem 1.15rem; }
        .srx-rx-summary {
          margin: 0 0 0.75rem 0;
          line-height: 1.65;
          color: var(--ink-soft) !important;
          word-break: keep-all;
        }
        .srx-rx-label {
          margin: 0.65rem 0 0.35rem;
          font-size: 0.7rem;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--brand) !important;
        }
        .srx-rx-body ul { margin: 0; padding-left: 1.05rem; }
        .srx-rx-body li {
          margin: 0.3rem 0;
          line-height: 1.55;
          color: #243833 !important;
          word-break: keep-all;
        }

        /* plan2 §3.3 — 처방 모듈형 카드 */
        .srx-card-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 16px;
          margin-bottom: 16px;
        }
        @media (max-width: 768px) {
          .srx-card-grid { grid-template-columns: 1fr; }
        }
        .srx-card {
          --card-bg: var(--surface-solid);
          --card-border: var(--line-soft);
          --card-ink: var(--ink-soft);
          --card-title: var(--brand-deep);
          --card-tag-bg: #EFF6FF;
          --card-tag-ink: #1D4ED8;
          --card-block-bg: #F8FAFC;
          background: var(--card-bg);
          border: 1px solid var(--card-border);
          border-radius: var(--srx-radius);
          padding: 16px;
          animation: srxFadeUp 0.5s ease both;
          box-shadow: var(--srx-shadow);
          transition: box-shadow 0.2s ease, transform 0.2s ease;
          display: flex;
          flex-direction: column;
          gap: 8px;
          min-height: 0;
        }
        .srx-card:hover {
          box-shadow: var(--srx-shadow-hover);
          transform: translateY(-2px);
        }
        .srx-card.prio-high {
          border-top: 3px solid #B43B2A;
        }
        .srx-card.prio-mid {
          border-top: 3px solid #B86A1C;
        }
        .srx-card.prio-ref {
          border-top: 3px solid #3B82F6;
        }
        .srx-card-head {
          display: flex;
          align-items: flex-start;
          gap: 8px;
        }
        .srx-card-icon {
          flex-shrink: 0;
          width: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--brand);
          background: #F0FDF4;
          border-radius: 10px;
          border: 1px solid var(--line-soft);
        }
        .srx-card-icon .srx-svg-icon,
        .srx-card-icon .srx-svg-icon svg {
          display: block;
          width: 22px;
          height: 22px;
        }
        .srx-card-head-text {
          flex: 1;
          min-width: 0;
        }
        .srx-card-title {
          font-family: var(--font-display);
          font-size: 1.05rem;
          font-weight: 650;
          color: var(--card-title) !important;
          margin: 0;
          letter-spacing: -0.015em;
          word-break: keep-all;
          line-height: 1.35;
        }
        .srx-card-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          margin-top: 6px;
        }
        .srx-card-tag {
          display: inline-block;
          padding: 2px 8px;
          border-radius: 999px;
          font-size: 0.68rem;
          font-weight: 700;
          letter-spacing: 0.01em;
          background: var(--card-tag-bg);
          color: var(--card-tag-ink) !important;
          border: 1px solid rgba(59, 130, 246, 0.2);
        }
        .srx-card.prio-high .srx-card-tag:first-child {
          background: #FCEDEA;
          color: #B43B2A !important;
          border-color: rgba(180, 59, 42, 0.25);
        }
        .srx-card-prio {
          flex-shrink: 0;
          font-size: 0.68rem;
          font-weight: 700;
          padding: 4px 8px;
          border-radius: 6px;
          letter-spacing: 0.03em;
          white-space: nowrap;
        }
        .srx-card-summary {
          margin: 0;
          font-size: 0.88rem;
          line-height: 1.6;
          color: var(--card-ink) !important;
          word-break: keep-all;
        }
        .srx-card-blocks {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-top: 4px;
        }
        .srx-card-block {
          padding: 8px 10px;
          background: var(--card-block-bg);
          border-radius: 8px;
          border: 1px solid var(--line-soft);
        }
        .srx-card-block-label {
          font-size: 0.68rem;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--brand) !important;
          margin-bottom: 4px;
        }
        .srx-card-block ul {
          margin: 0;
          padding-left: 1rem;
        }
        .srx-card-block li {
          font-size: 0.82rem;
          line-height: 1.5;
          color: #243833 !important;
          margin: 4px 0;
          word-break: keep-all;
        }
        @media (prefers-color-scheme: dark) {
          .srx-card {
            --card-bg: #1E293B;
            --card-border: #334155;
            --card-ink: #CBD5E1;
            --card-title: #F1F5F9;
            --card-tag-bg: #1E3A5F;
            --card-tag-ink: #93C5FD;
            --card-block-bg: #0F172A;
          }
          .srx-card-icon {
            background: linear-gradient(135deg, #064E3B 0%, #1E3A5F 100%);
            border-color: #334155;
          }
          .srx-card-block li { color: #CBD5E1 !important; }
          .srx-card.prio-high .srx-card-tag:first-child {
            background: #431407;
            color: #FDBA74 !important;
          }
        }

        /* plan2 §3.4 — 주간 플랜 테이블 */
        .srx-wplan {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 16px;
          margin-bottom: 16px;
          animation: srxFadeUp 0.5s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-wplan-head {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 12px;
          flex-wrap: wrap;
          margin-bottom: 12px;
        }
        .srx-wplan-sub {
          margin: 0;
          font-size: 0.84rem;
          color: var(--muted) !important;
          line-height: 1.5;
        }
        .srx-wplan-progress {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 6px 12px;
          border-radius: 999px;
          background: #EFF6FF;
          border: 1px solid rgba(59, 130, 246, 0.25);
        }
        .srx-wplan-progress .k {
          font-size: 0.72rem;
          font-weight: 600;
          color: var(--muted) !important;
        }
        .srx-wplan-progress .v {
          font-size: 0.82rem;
          font-weight: 700;
          color: #1D4ED8 !important;
        }
        .srx-wplan-scroll {
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
        }
        .srx-wplan-table {
          width: 100%;
          min-width: 640px;
          border-collapse: collapse;
          font-size: 0.86rem;
        }
        .srx-wplan-table thead th {
          text-align: left;
          padding: 10px 12px;
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          color: var(--brand) !important;
          background: linear-gradient(90deg, #F5FAF8 0%, #FFFFFF 100%);
          border-bottom: 2px solid var(--line-soft);
        }
        .srx-wplan-table tbody td {
          padding: 12px;
          vertical-align: top;
          border-bottom: 1px solid var(--line-soft);
          color: var(--ink-soft) !important;
          line-height: 1.55;
          word-break: keep-all;
        }
        .srx-wplan-table tbody tr:last-child td {
          border-bottom: none;
        }
        .srx-wplan-table td.day {
          width: 88px;
          color: #0F172A !important;
          white-space: nowrap;
        }
        .srx-wplan-table td.exercise {
          width: 28%;
          font-weight: 600;
          color: #0F172A !important;
        }
        .srx-wplan-table td.nutrition {
          width: 38%;
        }
        .srx-wplan-table td.status {
          width: 96px;
          white-space: nowrap;
        }
        .srx-wplan-row.active td {
          background: rgba(59, 130, 246, 0.06);
        }
        .srx-wplan-row.done td {
          background: rgba(16, 185, 129, 0.05);
        }
        .srx-wplan-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 4px 10px;
          border-radius: 999px;
          font-size: 0.76rem;
          font-weight: 700;
        }
        .srx-wplan-badge.done {
          background: #ECFDF5;
          color: #047857 !important;
          border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .srx-wplan-badge.active {
          background: #EFF6FF;
          color: #1D4ED8 !important;
          border: 1px solid rgba(59, 130, 246, 0.3);
        }
        .srx-wplan-badge.pending {
          background: #F8FAFC;
          color: #64748B !important;
          border: 1px solid #E2E8F0;
        }
        .srx-wplan-checks {
          display: grid;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          gap: 8px;
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid var(--line-soft);
        }
        @media (max-width: 768px) {
          .srx-wplan-checks { grid-template-columns: repeat(2, 1fr); }
        }
        .srx-wplan-check-label {
          font-size: 0.72rem;
          font-weight: 600;
          color: var(--muted) !important;
          margin-bottom: 4px;
        }
        @media (prefers-color-scheme: dark) {
          .srx-wplan {
            background: #1E293B;
            border-color: #334155;
          }
          .srx-wplan-table thead th {
            background: #0F172A;
            color: #93C5FD !important;
          }
          .srx-wplan-table tbody td {
            color: #CBD5E1 !important;
            border-color: #334155;
          }
          .srx-wplan-table td.exercise,
          .srx-wplan-table td.day { color: #F1F5F9 !important; }
          .srx-wplan-progress {
            background: #1E3A5F;
            border-color: #334155;
          }
          .srx-wplan-progress .v { color: #93C5FD !important; }
        }

        .srx-meal {
          padding: 1.1rem 0 0.4rem;
          margin-bottom: 0.85rem;
          border-top: 1px solid var(--line-soft);
        }
        .srx-meal li {
          color: var(--ink-soft) !important;
          line-height: 1.6;
          margin: 0.35rem 0;
          word-break: keep-all;
        }

        /* plan3 Phase 02 — 식단 대시보드 */
        .srx-meal-dashboard {
          margin: 0.35rem 0 1rem;
        }
        .srx-meal-goals {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 0.75rem;
          margin-bottom: 0.9rem;
        }
        @media (max-width: 720px) {
          .srx-meal-goals { grid-template-columns: 1fr; }
        }
        .srx-meal-chip {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.95rem 1rem;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
        }
        .srx-meal-chip .srx-svg-icon {
          display: inline-flex;
          color: var(--brand);
          flex-shrink: 0;
        }
        .srx-meal-chip .srx-svg-icon svg {
          width: 1.35rem;
          height: 1.35rem;
        }
        .srx-meal-chip.protein .srx-svg-icon { color: #059669; }
        .srx-meal-chip.water .srx-svg-icon { color: #3B82F6; }
        .srx-meal-chip-body {
          display: flex;
          flex-direction: column;
          gap: 0.1rem;
          min-width: 0;
        }
        .srx-meal-chip .label {
          font-size: 0.72rem;
          font-weight: 600;
          color: var(--muted) !important;
          letter-spacing: 0.04em;
        }
        .srx-meal-chip strong {
          font-family: var(--font-display);
          font-size: 1.35rem;
          font-weight: 700;
          color: var(--ink) !important;
          letter-spacing: -0.03em;
          line-height: 1.2;
        }
        .srx-meal-chip strong small {
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--muted) !important;
        }
        .srx-meal-chip .sub {
          font-size: 0.78rem;
          color: var(--muted) !important;
        }
        .srx-meal-cards {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 0.75rem;
          margin-bottom: 0.85rem;
        }
        @media (max-width: 960px) {
          .srx-meal-cards { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 520px) {
          .srx-meal-cards { grid-template-columns: 1fr; }
        }
        .srx-meal-card {
          padding: 1rem 0.95rem 0.95rem;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
          animation: srxFadeUp 0.45s ease both;
        }
        .srx-meal-card-head {
          display: flex;
          align-items: center;
          gap: 0.55rem;
          margin-bottom: 0.65rem;
        }
        .srx-meal-card-icon {
          width: 2rem;
          height: 2rem;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 10px;
          background: #ECFDF5;
          border: 1px solid rgba(16, 185, 129, 0.25);
          color: var(--brand);
          flex-shrink: 0;
        }
        .srx-meal-card-icon .srx-svg-icon svg {
          width: 1.05rem;
          height: 1.05rem;
        }
        .srx-meal-card-head h4 {
          margin: 0;
          font-size: 0.95rem;
          font-weight: 700;
          color: var(--ink) !important;
          letter-spacing: -0.02em;
        }
        .srx-meal-card-items {
          margin: 0 0 0.65rem;
          padding: 0 0 0 1.05rem;
        }
        .srx-meal-card-items li {
          margin: 0.28rem 0;
          font-size: 0.86rem;
          line-height: 1.45;
          color: var(--ink-soft) !important;
          word-break: keep-all;
        }
        .srx-meal-card-tip {
          margin: 0;
          padding-top: 0.55rem;
          border-top: 1px solid var(--line-soft);
          font-size: 0.8rem;
          line-height: 1.5;
          color: var(--muted) !important;
          word-break: keep-all;
        }
        .srx-meal-insights {
          margin: 0.25rem 0 0.75rem;
          padding: 0.95rem 1rem;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
        }
        .srx-meal-insights-title {
          font-size: 0.82rem;
          font-weight: 700;
          color: var(--ink) !important;
          margin-bottom: 0.65rem;
          letter-spacing: -0.01em;
        }
        .srx-meal-insight {
          display: flex;
          gap: 0.7rem;
          align-items: flex-start;
          padding: 0.55rem 0;
          border-top: 1px solid var(--line-soft);
        }
        .srx-meal-insight:first-of-type { border-top: none; padding-top: 0; }
        .srx-meal-insight .badge {
          flex-shrink: 0;
          font-size: 0.68rem;
          font-weight: 700;
          padding: 0.2rem 0.45rem;
          border-radius: 6px;
          letter-spacing: 0.02em;
        }
        .srx-meal-insight.sev-high .badge {
          color: #B43B2A;
          background: #FCEDEA;
        }
        .srx-meal-insight.sev-mid .badge {
          color: #B86A1C;
          background: #FFF4E8;
        }
        .srx-meal-insight.sev-tip .badge {
          color: #1F6F8B;
          background: #EAF5F9;
        }
        .srx-meal-insight .body strong {
          display: block;
          font-size: 0.88rem;
          color: var(--ink) !important;
          margin-bottom: 0.15rem;
        }
        .srx-meal-insight .reason,
        .srx-meal-insight .action {
          margin: 0.15rem 0 0;
          font-size: 0.82rem;
          line-height: 1.45;
          color: var(--muted) !important;
          word-break: keep-all;
        }
        .srx-meal-insight .action {
          color: var(--ink-soft) !important;
          font-weight: 500;
        }
        .srx-meal-avoid {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 0.55rem;
          padding: 0.75rem 0.95rem;
          background: linear-gradient(90deg, #FFF7E8 0%, #FFFBF2 100%);
          border: 1px solid rgba(212, 179, 91, 0.35);
          border-radius: 12px;
        }
        .srx-meal-avoid strong {
          font-size: 0.8rem;
          color: #9A6B1F !important;
        }
        .srx-meal-avoid .tags {
          display: flex;
          flex-wrap: wrap;
          gap: 0.35rem;
        }
        .srx-meal-avoid .tags span {
          font-size: 0.76rem;
          font-weight: 600;
          padding: 0.2rem 0.5rem;
          border-radius: 999px;
          background: rgba(255,255,255,0.75);
          border: 1px solid rgba(212, 179, 91, 0.4);
          color: #7A5518 !important;
        }

        /* plan3 Phase 04 — 주간 식단 힌트 */
        .srx-meal-week {
          margin: 0.25rem 0 0.85rem;
          padding: 0.95rem 1rem;
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          box-shadow: var(--srx-shadow);
        }
        .srx-meal-week-title {
          font-size: 0.88rem;
          font-weight: 700;
          color: var(--ink) !important;
          letter-spacing: -0.01em;
        }
        .srx-meal-week-sub {
          margin: 0.2rem 0 0.75rem;
          font-size: 0.8rem;
          color: var(--muted) !important;
        }
        .srx-meal-week-row {
          display: grid;
          grid-template-columns: 2.4rem 1fr;
          gap: 0.65rem;
          align-items: start;
          padding: 0.55rem 0.45rem;
          border-top: 1px solid var(--line-soft);
        }
        .srx-meal-week-row:first-of-type { border-top: none; }
        .srx-meal-week-row.today {
          background: #ECFDF5;
          border-radius: 10px;
          border-top-color: transparent;
          margin-top: 0.15rem;
        }
        .srx-meal-week-row .day {
          font-family: var(--font-display);
          font-size: 0.9rem;
          font-weight: 700;
          color: var(--brand) !important;
          padding-top: 0.1rem;
        }
        .srx-meal-week-row .week-body {
          display: flex;
          flex-direction: column;
          gap: 0.15rem;
          min-width: 0;
        }
        .srx-meal-week-row .ex {
          font-size: 0.78rem;
          font-weight: 600;
          color: var(--muted) !important;
          word-break: keep-all;
        }
        .srx-meal-week-row .hint {
          font-size: 0.86rem;
          line-height: 1.45;
          color: var(--ink-soft) !important;
          word-break: keep-all;
        }
        .srx-meal-week-row.focus-protein .day { color: #059669 !important; }
        .srx-meal-week-row.focus-water .day { color: #3B82F6 !important; }
        .srx-meal-week-row.focus-mineral .day { color: #7C3AED !important; }

        .srx-caution {
          background: linear-gradient(90deg, #FFF7E8 0%, #FFFBF2 100%);
          border-left: 3px solid #D4B35B;
          padding: 1rem 1.15rem;
          color: var(--warn) !important;
          font-size: 0.86rem;
          line-height: 1.6;
          word-break: keep-all;
          margin-top: 0.5rem;
        }
        .srx-caution * { color: var(--warn) !important; }

        .srx-section-title {
          font-family: var(--font-display);
          font-size: 1.15rem;
          font-weight: 600;
          color: var(--brand-deep) !important;
          margin: 1.6rem 0 0.85rem;
          letter-spacing: -0.02em;
          display: flex;
          align-items: baseline;
          gap: 0.65rem;
        }
        .srx-section-title::after {
          content: "";
          flex: 1;
          height: 1px;
          background: var(--line);
          transform: translateY(-0.2em);
        }
        .srx-heading-with-icon {
          align-items: center !important;
        }
        .srx-heading-with-icon .srx-svg-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          color: var(--brand);
          flex-shrink: 0;
          line-height: 0;
        }
        .srx-heading-with-icon .srx-svg-icon svg {
          width: 1.12em;
          height: 1.12em;
        }

        .srx-trend {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 1.25rem 1.35rem 1.1rem;
          margin-bottom: 1.35rem;
          animation: srxFadeUp 0.55s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-trend-head {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 0.75rem;
          flex-wrap: wrap;
          margin-bottom: 1rem;
        }
        .srx-trend-head .title {
          font-family: var(--font-display);
          font-size: 1.25rem;
          color: var(--brand-deep) !important;
          margin: 0;
          letter-spacing: -0.02em;
        }
        .srx-trend-weather {
          display: inline-flex;
          align-items: center;
          gap: 0.45rem;
          padding: 0.35rem 0.75rem;
          border-radius: 999px;
          font-size: 0.88rem;
          font-weight: 600;
        }
        .srx-trend-weather.sunny { background: #FFF8E6; color: #8A6A1F !important; }
        .srx-trend-weather.cloudy { background: #EEF3F6; color: #3D5A66 !important; }
        .srx-trend-weather.rainy { background: #EAF0F8; color: #2F4F7A !important; }
        .srx-trend-weather .icon { font-size: 1.25rem; line-height: 1; }
        .srx-trend-deltas {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 0.65rem;
          margin-bottom: 0.85rem;
        }
        @media (max-width: 720px) {
          .srx-trend-deltas { grid-template-columns: 1fr; }
        }
        .srx-trend-delta {
          background: rgba(255,255,255,0.7);
          border-top: 1px solid var(--line-soft);
          padding: 0.65rem 0.75rem;
        }
        .srx-trend-delta .k {
          font-size: 0.72rem;
          font-weight: 700;
          color: var(--muted) !important;
          letter-spacing: 0.04em;
        }
        .srx-trend-delta .flow {
          margin-top: 0.35rem;
          font-size: 0.95rem;
          color: var(--ink) !important;
          font-variant-numeric: tabular-nums;
        }
        .srx-trend-delta .chg {
          margin-top: 0.2rem;
          font-size: 0.82rem;
          font-weight: 700;
        }
        .srx-trend-delta .chg.up-good { color: #1F7A4D !important; }
        .srx-trend-delta .chg.down-good { color: #1F7A4D !important; }
        .srx-trend-delta .chg.warn { color: #B43B2A !important; }
        .srx-trend-delta .chg.neutral { color: var(--muted) !important; }
        .srx-trend-comment {
          margin-top: 0.85rem;
          padding: 0.85rem 1rem;
          background: linear-gradient(90deg, #F5FAF8 0%, #FFFFFF 100%);
          border-left: 3px solid var(--brand);
          color: var(--ink-soft) !important;
          line-height: 1.65;
          word-break: keep-all;
          font-size: 0.92rem;
        }

        .srx-phase-angle {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 1.25rem 1.35rem 1.1rem;
          margin-bottom: 1.35rem;
          animation: srxFadeUp 0.55s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-phase-head {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 0.75rem;
          flex-wrap: wrap;
          margin-bottom: 1rem;
        }
        .srx-phase-head .title {
          font-family: var(--font-display);
          font-size: 1.25rem;
          color: var(--brand-deep) !important;
          margin: 0;
          letter-spacing: -0.02em;
        }
        .srx-phase-head .sub {
          margin: 0.25rem 0 0;
          font-size: 0.84rem;
          color: var(--muted) !important;
        }
        .srx-phase-hero {
          display: flex;
          align-items: center;
          gap: 0.85rem;
          flex-wrap: wrap;
          margin-bottom: 0.85rem;
        }
        .srx-phase-current {
          font-size: clamp(2.25rem, 4vw, 2.75rem);
          font-weight: 800;
          color: #0F172A !important;
          font-variant-numeric: tabular-nums;
          letter-spacing: -0.03em;
          line-height: 1;
        }
        .srx-phase-current span {
          font-size: 0.55em;
          font-weight: 700;
          color: #10B981 !important;
        }
        .srx-phase-badge {
          display: inline-flex;
          align-items: center;
          padding: 0.35rem 0.75rem;
          border-radius: 999px;
          font-size: 0.86rem;
          font-weight: 700;
        }
        .srx-phase-badge.improved {
          background: #ECFDF5;
          color: #047857 !important;
          border: 1px solid rgba(16, 185, 129, 0.35);
        }
        .srx-phase-badge.declined {
          background: #FFF7ED;
          color: #C2410C !important;
          border: 1px solid rgba(234, 88, 12, 0.35);
        }
        .srx-phase-badge.neutral {
          background: #F1F5F9;
          color: #475569 !important;
          border: 1px solid rgba(148, 163, 184, 0.35);
        }
        .srx-phase-comment {
          margin-top: 0.75rem;
          padding: 0.75rem 0.95rem;
          background: linear-gradient(90deg, #ECFDF5 0%, #FFFFFF 100%);
          border-left: 3px solid #10B981;
          color: var(--ink-soft) !important;
          font-size: 0.92rem;
          line-height: 1.65;
          word-break: keep-all;
        }

        .srx-bmr {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 1.25rem 1.35rem 1.1rem;
          margin-bottom: 1.35rem;
          animation: srxFadeUp 0.55s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-bmr-head .title {
          font-family: var(--font-display);
          font-size: 1.25rem;
          color: var(--brand-deep) !important;
          margin: 0;
          letter-spacing: -0.02em;
        }
        .srx-bmr-head .sub {
          margin: 0.25rem 0 0;
          font-size: 0.84rem;
          color: var(--muted) !important;
        }
        .srx-bmr-hero {
          display: flex;
          align-items: center;
          gap: 0.85rem;
          flex-wrap: wrap;
          margin: 1rem 0 1.1rem;
        }
        .srx-bmr-current {
          font-size: clamp(2.25rem, 4vw, 2.75rem);
          font-weight: 800;
          color: #0F172A !important;
          font-variant-numeric: tabular-nums;
          letter-spacing: -0.03em;
          line-height: 1;
        }
        .srx-bmr-current span {
          margin-left: 0.15rem;
          font-size: 0.38em;
          font-weight: 700;
          color: #3B82F6 !important;
        }
        .srx-bmr-badge {
          display: inline-flex;
          align-items: center;
          padding: 0.35rem 0.75rem;
          border-radius: 999px;
          font-size: 0.86rem;
          font-weight: 700;
        }
        .srx-bmr-badge.warn {
          background: #FFF7ED;
          color: #C2410C !important;
          border: 1px solid rgba(234, 88, 12, 0.35);
        }
        .srx-bmr-badge.good {
          background: #EFF6FF;
          color: #1D4ED8 !important;
          border: 1px solid rgba(59, 130, 246, 0.35);
        }
        .srx-bmr-badge.high {
          background: #FEF3C7;
          color: #B45309 !important;
          border: 1px solid rgba(245, 158, 11, 0.35);
        }
        .srx-bmr-track {
          position: relative;
          height: 14px;
          border-radius: 999px;
          background: #E2E8F0;
          overflow: visible;
          margin-bottom: 0.55rem;
        }
        .srx-bmr-zone {
          position: absolute;
          top: 0;
          height: 100%;
          border-radius: 999px;
          background: rgba(59, 130, 246, 0.22);
          border: 1px solid rgba(59, 130, 246, 0.35);
        }
        .srx-bmr-fill {
          position: absolute;
          top: 0;
          left: 0;
          height: 100%;
          border-radius: 999px 0 0 999px;
          max-width: 100%;
        }
        .srx-bmr-fill.warn { background: linear-gradient(90deg, #FB923C, #F97316); }
        .srx-bmr-fill.good { background: linear-gradient(90deg, #60A5FA, #3B82F6); }
        .srx-bmr-fill.high { background: linear-gradient(90deg, #FBBF24, #F59E0B); }
        .srx-bmr-marker {
          position: absolute;
          top: 50%;
          width: 4px;
          height: 22px;
          margin-left: -2px;
          transform: translateY(-50%);
          background: #0F172A;
          border-radius: 2px;
          box-shadow: 0 0 0 2px #FFFFFF;
          z-index: 2;
        }
        .srx-bmr-tick {
          position: absolute;
          top: -4px;
          width: 2px;
          height: 22px;
          margin-left: -1px;
          background: rgba(15, 23, 42, 0.35);
          z-index: 1;
        }
        .srx-bmr-scale {
          display: flex;
          justify-content: space-between;
          gap: 0.5rem;
          font-size: 0.76rem;
          color: var(--muted) !important;
          margin-bottom: 0.85rem;
        }
        .srx-bmr-scale .mid {
          color: #0F172A !important;
          font-weight: 700;
        }
        .srx-bmr-stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 0.55rem;
        }
        @media (max-width: 640px) {
          .srx-bmr-stats { grid-template-columns: 1fr; }
        }
        .srx-bmr-stats .stat {
          padding: 0.55rem 0.65rem;
          background: rgba(255,255,255,0.7);
          border: 1px solid var(--line-soft);
        }
        .srx-bmr-stats .k {
          display: block;
          font-size: 0.75rem;
          color: var(--muted) !important;
          font-weight: 500;
        }
        .srx-bmr-stats .v {
          display: block;
          margin-top: 0.2rem;
          font-size: 1.1rem;
          font-weight: 700;
          color: #0F172A !important;
          font-variant-numeric: tabular-nums;
        }
        .srx-bmr-comment {
          margin-top: 0.85rem;
          padding: 0.75rem 0.95rem;
          background: linear-gradient(90deg, #EFF6FF 0%, #FFFFFF 100%);
          border-left: 3px solid #3B82F6;
          color: var(--ink-soft) !important;
          font-size: 0.92rem;
          line-height: 1.65;
          word-break: keep-all;
        }

        .srx-mission {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 1.25rem 1.35rem 1.15rem;
          margin-bottom: 1.35rem;
          animation: srxFadeUp 0.55s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-mission-head .title {
          font-family: var(--font-display);
          font-size: 1.25rem;
          color: var(--brand-deep) !important;
          margin: 0 0 0.35rem;
        }
        .srx-mission-head .sub {
          color: var(--muted) !important;
          font-size: 0.88rem;
          line-height: 1.55;
          margin: 0 0 1rem;
        }
        .srx-mission-row {
          padding: 0.85rem 0;
          border-top: 1px solid var(--line-soft);
        }
        .srx-mission-row:first-of-type { border-top: none; padding-top: 0.2rem; }
        .srx-mission-row .label {
          font-weight: 700;
          color: var(--ink) !important;
          margin-bottom: 0.55rem;
          font-size: 0.95rem;
        }
        .srx-mission-row .prio {
          display: inline-block;
          margin-left: 0.45rem;
          font-size: 0.68rem;
          font-weight: 700;
          padding: 0.15rem 0.4rem;
          border-radius: 4px;
          vertical-align: middle;
        }
        .srx-mission-days {
          display: grid;
          grid-template-columns: repeat(7, 1fr);
          gap: 0.35rem;
        }
        .srx-mission-progress {
          margin-top: 1rem;
          padding-top: 0.95rem;
          border-top: 1px solid var(--line-soft);
        }
        .srx-mission-progress .rate-line {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 0.75rem;
          margin-bottom: 0.45rem;
          font-size: 0.9rem;
          color: var(--ink) !important;
          font-weight: 600;
        }
        .srx-mission-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          margin-top: 0.65rem;
          padding: 0.45rem 0.75rem;
          border-radius: 999px;
          font-size: 0.84rem;
          font-weight: 700;
        }
        .srx-mission-badge.gold {
          background: linear-gradient(90deg, #FFF4D6 0%, #FFE8A3 100%);
          color: #8A6A1F !important;
        }
        .srx-mission-note {
          margin-top: 0.75rem;
          font-size: 0.8rem;
          color: var(--muted) !important;
          line-height: 1.5;
        }
        div[data-testid="stCheckbox"] label p {
          font-size: 0.82rem !important;
          font-weight: 700 !important;
          color: var(--brand-deep) !important;
        }
        div[data-testid="stCheckbox"] {
          background: rgba(255,255,255,0.65);
          border: 1px solid var(--line-soft);
          border-radius: 10px;
          padding: 0.15rem 0.35rem 0.35rem;
          transition: border-color 0.2s ease, background 0.2s ease;
        }
        div[data-testid="stCheckbox"]:has(input:checked) {
          background: #E8F6EE;
          border-color: #9BD4B5;
        }

        .srx-heatmap {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 1.25rem 1.35rem 1.15rem;
          margin-bottom: 1.35rem;
          animation: srxFadeUp 0.55s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-heatmap-head .title {
          font-family: var(--font-display);
          font-size: 1.25rem;
          color: var(--brand-deep) !important;
          margin: 0 0 0.35rem;
        }
        .srx-heatmap-head .sub {
          color: var(--muted) !important;
          font-size: 0.88rem;
          line-height: 1.55;
          margin: 0 0 1rem;
        }
        .srx-heatmap-body {
          display: grid;
          grid-template-columns: minmax(180px, 240px) 1fr;
          gap: 1.25rem;
          align-items: start;
        }
        @media (max-width: 760px) {
          .srx-heatmap-body { grid-template-columns: 1fr; }
        }
        .srx-heatmap-svg-wrap,
        .srx-heatmap-figure-wrap {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 0.5rem;
        }
        .srx-heatmap-figure {
          position: relative;
          width: min(100%, 240px);
          aspect-ratio: 2 / 3;
        }
        .srx-heatmap-base {
          width: 100%;
          height: 100%;
          object-fit: contain;
          display: block;
          border-radius: 12px;
        }
        .srx-heatmap-figure.male .srx-heatmap-base {
          filter: saturate(0.85) contrast(1.05);
        }
        .srx-heatmap-bones {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
          pointer-events: none;
          mix-blend-mode: multiply;
        }
        .srx-heatmap-bones path {
          filter: drop-shadow(0 0 1px rgba(18,47,42,0.2));
        }
        .srx-heatmap-svg {
          width: 100%;
          max-width: 220px;
          height: auto;
        }
        .srx-heatmap-gender {
          margin-top: 0.45rem;
          font-size: 0.78rem;
          color: var(--muted) !important;
          font-weight: 600;
        }
        .srx-heatmap-legend {
          display: flex;
          flex-wrap: wrap;
          gap: 0.45rem 0.75rem;
          margin-bottom: 0.85rem;
        }
        .srx-heatmap-legend-item {
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          font-size: 0.78rem;
          color: var(--ink-soft) !important;
          font-weight: 600;
        }
        .srx-heatmap-legend-item i {
          width: 12px;
          height: 12px;
          border-radius: 3px;
          display: inline-block;
          border: 1px solid rgba(18,47,42,0.12);
        }
        .srx-heatmap-zones {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 0.45rem;
          max-height: 420px;
          overflow-y: auto;
          padding-right: 0.15rem;
        }
        @media (max-width: 520px) {
          .srx-heatmap-zones { grid-template-columns: 1fr; }
        }
        .srx-heatmap-zone {
          padding: 0.65rem 0.75rem;
          border-top: 3px solid var(--line);
          background: rgba(255,255,255,0.65);
        }
        .srx-heatmap-zone.muscle_low { border-top-color: #2563EB; }
        .srx-heatmap-zone.fat_high { border-top-color: #EA580C; }
        .srx-heatmap-zone.normal { border-top-color: #A8C9B4; }
        .srx-heatmap-zone.mixed { border-top-color: #B43B2A; }
        .srx-heatmap-zone .k {
          font-size: 0.75rem;
          font-weight: 500;
          color: var(--muted) !important;
        }
        .srx-heatmap-zone .v {
          margin-top: 0.2rem;
          font-size: 1.15rem;
          font-weight: 700;
          color: var(--ink) !important;
        }
        .srx-heatmap-zone .e {
          margin-top: 0.15rem;
          font-size: 0.75rem;
          color: var(--muted) !important;
        }
        .srx-heatmap-zone .s {
          margin-top: 0.25rem;
          font-size: 0.78rem;
          font-weight: 700;
          color: var(--brand-deep) !important;
        }
        .srx-heatmap-summary {
          margin-top: 0.85rem;
          padding: 0.75rem 0.95rem;
          background: linear-gradient(90deg, #F5FAF8 0%, #FFFFFF 100%);
          border-left: 3px solid var(--brand);
          color: var(--ink-soft) !important;
          line-height: 1.6;
          font-size: 0.9rem;
        }

        .srx-multidim {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 1.15rem 1.25rem 0.85rem;
          margin-bottom: 1.35rem;
          animation: srxFadeUp 0.55s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-multidim .title {
          font-family: var(--font-display);
          font-size: 1.15rem;
          color: var(--brand-deep) !important;
          margin: 0 0 0.35rem;
        }
        .srx-multidim .sub {
          color: var(--muted) !important;
          font-size: 0.86rem;
          line-height: 1.55;
          margin: 0 0 0.85rem;
        }
        .srx-multidim-summary {
          margin-top: 0.65rem;
          padding: 0.75rem 0.95rem;
          background: linear-gradient(90deg, #F5FAF8 0%, #FFFFFF 100%);
          border-left: 3px solid var(--brand);
          color: var(--ink-soft) !important;
          line-height: 1.6;
          font-size: 0.9rem;
        }

        .srx-score-persona {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 1.15rem 1.25rem 0.95rem;
          margin-bottom: 1.35rem;
          animation: srxFadeUp 0.55s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-score-persona .title {
          font-family: var(--font-display);
          font-size: 1.15rem;
          color: var(--brand-deep) !important;
          margin: 0 0 0.85rem;
        }
        .srx-persona-card {
          background: #FFFFFF;
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 1.1rem 1rem 1rem;
          text-align: center;
          min-height: 220px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          box-shadow: var(--srx-shadow);
        }
        .srx-persona-card.evolving {
          animation: srxPersonaGlow 2.4s ease-in-out infinite;
          border-color: #9BD4B5;
        }
        @keyframes srxPersonaGlow {
          0%, 100% { box-shadow: 0 0 0 rgba(14,101,87,0); transform: scale(1); }
          50% { box-shadow: 0 0 22px rgba(14,101,87,0.18); transform: scale(1.02); }
        }
        .srx-persona-emoji {
          font-size: 3rem;
          line-height: 1;
          margin-bottom: 0.35rem;
        }
        .srx-persona-name {
          font-family: var(--font-display);
          font-size: 1.15rem;
          font-weight: 700;
          color: var(--brand-deep) !important;
        }
        .srx-persona-type {
          margin-top: 0.2rem;
          font-size: 0.78rem;
          font-weight: 700;
          color: var(--brand) !important;
          letter-spacing: 0.04em;
        }
        .srx-persona-tagline {
          margin: 0.65rem 0 0;
          font-size: 0.84rem;
          line-height: 1.55;
          color: var(--ink-soft) !important;
        }
        .srx-persona-evo {
          margin-top: 0.75rem;
          padding: 0.55rem 0.65rem;
          border-radius: 10px;
          background: rgba(14,101,87,0.08);
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--brand-deep) !important;
          line-height: 1.45;
        }

        /* plan2 §3.5 — 슬라임 성장 */
        .srx-slime-growth {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 16px;
          margin-bottom: 16px;
          animation: srxFadeUp 0.55s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-slime-head {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 12px;
          margin-bottom: 12px;
        }
        .srx-slime-char {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .srx-slime-char .emoji {
          font-size: 2.5rem;
          line-height: 1;
        }
        .srx-slime-char .name {
          margin: 0;
          font-family: var(--font-display);
          font-size: 1.15rem;
          color: #0F172A !important;
          letter-spacing: -0.02em;
        }
        .srx-slime-next {
          margin-top: 4px;
          font-size: 0.78rem;
          font-weight: 600;
          color: #047857 !important;
        }
        .srx-slime-next.max {
          color: #1D4ED8 !important;
        }
        .srx-slime-pct {
          font-size: 2rem;
          font-weight: 800;
          color: #10B981 !important;
          font-variant-numeric: tabular-nums;
          line-height: 1;
        }
        .srx-slime-pct span {
          font-size: 0.45em;
          font-weight: 700;
        }
        .srx-slime-bar {
          height: 10px;
          border-radius: 999px;
          background: #E2E8F0;
          overflow: hidden;
          margin-bottom: 12px;
        }
        .srx-slime-bar-fill {
          height: 100%;
          border-radius: 999px;
          background: linear-gradient(90deg, #10B981, #3B82F6);
          transition: width 0.4s ease;
        }
        .srx-slime-summary {
          margin: 0 0 12px;
          font-size: 0.88rem;
          line-height: 1.6;
          color: var(--ink-soft) !important;
          word-break: keep-all;
        }
        .srx-slime-quests-label {
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: var(--brand) !important;
          margin-bottom: 8px;
        }
        .srx-slime-quests {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .srx-slime-quest {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          padding: 8px 10px;
          border-radius: 8px;
          background: rgba(255,255,255,0.75);
          border: 1px solid var(--line-soft);
          font-size: 0.84rem;
          line-height: 1.45;
        }
        .srx-slime-quest.done {
          background: rgba(16, 185, 129, 0.08);
          border-color: rgba(16, 185, 129, 0.25);
        }
        .srx-slime-quest .mark {
          flex-shrink: 0;
          width: 18px;
          font-weight: 700;
          color: #64748B !important;
        }
        .srx-slime-quest.done .mark {
          color: #10B981 !important;
        }
        .srx-slime-quest .tag {
          flex-shrink: 0;
          font-size: 0.68rem;
          font-weight: 700;
          color: #3B82F6 !important;
        }
        .srx-slime-quest .text {
          color: #0F172A !important;
          word-break: keep-all;
        }
        @media (prefers-color-scheme: dark) {
          .srx-slime-growth {
            background: linear-gradient(165deg, #064E3B 0%, #1E293B 60%, #1E3A5F 100%);
            border-color: #334155;
          }
          .srx-slime-char .name,
          .srx-slime-quest .text { color: #F1F5F9 !important; }
          .srx-slime-quest {
            background: rgba(15, 23, 42, 0.6);
            border-color: #334155;
          }
        }

        @keyframes srxEvolveBurst {
          0%, 100% { transform: scale(1) rotate(0deg); filter: brightness(1); }
          50% { transform: scale(1.18) rotate(-3deg); filter: brightness(1.15); }
        }
        @keyframes srxEvolvePulse {
          0%, 100% { box-shadow: 0 0 0 rgba(16,185,129,0); }
          50% { box-shadow: 0 0 28px rgba(16,185,129,0.45); }
        }

        /* Phase 04 — 런칭 & 진화 */
        .srx-launch-banner {
          background: linear-gradient(135deg, #0F172A 0%, #1E293B 55%, #064E3B 100%);
          border-radius: var(--srx-radius);
          padding: 18px 20px;
          margin-bottom: 16px;
          color: #F8FAFC !important;
          animation: srxFadeUp 0.55s ease both;
          box-shadow: var(--srx-shadow);
        }
        .srx-launch-banner.gold-week {
          background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 50%, #065F46 100%);
        }
        .srx-launch-banner.evolution-ready {
          animation: srxEvolvePulse 2.4s ease-in-out infinite;
          border: 1px solid rgba(16, 185, 129, 0.45);
        }
        .srx-launch-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 8px;
          margin-bottom: 10px;
        }
        .srx-launch-badge {
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          padding: 4px 10px;
          border-radius: 999px;
          background: rgba(16, 185, 129, 0.2);
          color: #6EE7B7 !important;
          border: 1px solid rgba(16, 185, 129, 0.35);
        }
        .srx-launch-score {
          font-size: 0.82rem;
          font-weight: 700;
          color: #93C5FD !important;
        }
        .srx-launch-headline {
          margin: 0 0 6px;
          font-family: var(--font-display);
          font-size: clamp(1.15rem, 2.5vw, 1.45rem);
          font-weight: 700;
          color: #F8FAFC !important;
          letter-spacing: -0.02em;
        }
        .srx-launch-sub {
          margin: 0 0 12px;
          font-size: 0.88rem;
          line-height: 1.55;
          color: #CBD5E1 !important;
        }
        .srx-launch-modules {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .srx-launch-chip {
          font-size: 0.68rem;
          font-weight: 600;
          padding: 3px 8px;
          border-radius: 6px;
          background: rgba(255,255,255,0.1);
          color: #E2E8F0 !important;
          border: 1px solid rgba(255,255,255,0.12);
        }
        .srx-rewards-strip {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          margin-bottom: 16px;
        }
        .srx-reward {
          flex: 1;
          min-width: 180px;
          padding: 10px 14px;
          border-radius: 10px;
          border: 1px solid var(--line-soft);
          background: var(--surface-solid);
        }
        .srx-reward strong {
          display: block;
          font-size: 0.88rem;
          color: var(--primary) !important;
        }
        .srx-reward span {
          display: block;
          margin-top: 2px;
          font-size: 0.76rem;
          color: var(--muted) !important;
        }
        .srx-reward.gold {
          border-color: rgba(245, 158, 11, 0.35);
          background: linear-gradient(90deg, #FFFBEB, #FFFFFF);
        }
        .srx-reward.evolve {
          border-color: rgba(16, 185, 129, 0.35);
          background: linear-gradient(90deg, #ECFDF5, #FFFFFF);
        }
        .srx-evolution-celebration {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 10px;
          padding: 14px 16px;
          margin-bottom: 12px;
          border-radius: 12px;
          background: linear-gradient(90deg, #ECFDF5, #EFF6FF);
          border: 1px solid rgba(16, 185, 129, 0.35);
          animation: srxFadeUp 0.5s ease both;
        }
        .srx-evolution-celebration .from,
        .srx-evolution-celebration .to {
          font-size: 2rem;
          line-height: 1;
          animation: srxEvolveBurst 1.8s ease-in-out infinite;
        }
        .srx-evolution-celebration .arrow {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--mint) !important;
        }
        .srx-evolution-celebration .msg {
          flex: 1;
          min-width: 200px;
          margin: 0;
          font-size: 0.86rem;
          line-height: 1.55;
          color: var(--ink-soft) !important;
        }
        .srx-body-evolution {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 10px;
          padding: 14px 16px;
          margin-bottom: 14px;
          border-radius: 12px;
          background: linear-gradient(90deg, #FEF3C7, #ECFDF5);
          border: 1px solid rgba(245, 158, 11, 0.35);
          animation: srxFadeUp 0.5s ease both;
        }
        .srx-body-evolution .from,
        .srx-body-evolution .to {
          font-size: 1.75rem;
          line-height: 1;
        }
        .srx-body-evolution .arrow {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--mint) !important;
        }
        .srx-body-evolution .msg {
          flex: 1;
          min-width: 200px;
          margin: 0;
          font-size: 0.86rem;
          line-height: 1.55;
          color: var(--ink-soft) !important;
        }
        .srx-persist-note {
          font-size: 0.72rem;
          color: var(--muted) !important;
          margin: 0 0 0.85rem;
        }
        .srx-slime-growth.evolution-ready .emoji {
          animation: srxEvolveBurst 1.8s ease-in-out infinite;
        }
        .srx-persona-card.evolution-burst {
          animation: srxEvolvePulse 2.4s ease-in-out infinite;
          border-color: rgba(16, 185, 129, 0.45) !important;
        }
        .srx-persona-card.evolution-burst .srx-persona-emoji {
          animation: srxEvolveBurst 1.8s ease-in-out infinite;
        }

        .srx-bal-item {
          padding: 0.85rem 0;
          border-top: 1px solid var(--line-soft);
          color: var(--brand-deep) !important;
          font-size: 0.9rem;
          font-weight: 600;
          word-break: keep-all;
        }

        .srx-seg-item {
          padding: 0.75rem 0.2rem;
          text-align: left;
          border-top: 1px solid var(--line);
        }
        .srx-seg-item .k { font-size: 0.72rem; color: var(--muted) !important; font-weight: 600; }
        .srx-seg-item .v {
          font-size: 1.12rem;
          font-weight: 700;
          color: var(--ink) !important;
          margin-top: 0.25rem;
          font-variant-numeric: tabular-nums;
        }

        .srx-panel {
          background: var(--surface-solid);
          border: 1px solid var(--line-soft);
          border-radius: var(--srx-radius);
          padding: 0.75rem 0.85rem 0.4rem;
          margin-bottom: 0.5rem;
          box-shadow: var(--srx-shadow);
        }

        .srx-side-brand {
          font-family: var(--font-display);
          font-size: 1.35rem;
          font-weight: 700;
          color: var(--brand-deep) !important;
          letter-spacing: -0.02em;
          margin: 0 0 0.15rem;
        }
        .srx-side-cap {
          font-size: 0.72rem;
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--muted) !important;
          margin-bottom: 1.1rem;
        }
        .srx-side-label {
          font-size: 0.78rem;
          font-weight: 700;
          color: var(--brand-deep) !important;
          margin: 0.85rem 0 0.45rem;
        }
        .srx-side-note {
          margin-top: 0.85rem;
          padding-top: 0.85rem;
          border-top: 1px solid var(--line-soft);
          font-size: 0.8rem !important;
          color: var(--muted) !important;
          line-height: 1.5;
        }

        .srx-analyzing {
          padding: 2.5rem 1.5rem;
          text-align: center;
          animation: srxFadeUp 0.4s ease both;
        }
        .srx-analyzing .t {
          font-family: var(--font-display);
          font-size: 1.5rem;
          color: var(--brand-deep) !important;
          margin-bottom: 0.4rem;
        }
        .srx-analyzing .d {
          color: var(--muted) !important;
          font-size: 0.92rem;
        }

        .srx-original-note {
          font-size: 0.85rem;
          color: var(--muted) !important;
          margin-bottom: 0.75rem;
          line-height: 1.5;
        }

        @media (max-width: 900px) {
          .srx-steps { grid-template-columns: 1fr; gap: 0.35rem; }
          .srx-identity { grid-template-columns: 1fr 1fr; gap: 0.75rem 0; }
          .srx-id-cell { border-right: none; padding: 0.4rem 0.5rem 0.4rem 0; }
          .srx-landing { min-height: 52vh; border-radius: 20px; }
          .srx-empty-hero { grid-template-columns: 1fr; text-align: center; }
          .srx-empty-visual { margin: 0 auto; }
          .srx-sticky-chip.score { margin-left: 0; }
        }

        /* plan2 §3.3 — 다크 모드 · 접근성 (브랜드 팔레트 통일) */
        @media (prefers-color-scheme: dark) {
          :root {
            --ink: #F1F5F9;
            --ink-soft: #CBD5E1;
            --muted: #94A3B8;
            --line: #334155;
            --line-soft: #1E293B;
            --surface: rgba(15, 23, 42, 0.88);
            --surface-solid: #1E293B;
            --brand-deep: #F1F5F9;
            --brand-mist: #064E3B;
            --sand: #1E293B;
            --warn: #FCD34D;
          }
          .srx-sticky-bar {
            background: rgba(15, 23, 42, 0.92);
            border-bottom-color: var(--line);
          }
          .srx-sticky-chip.name {
            background: #064E3B;
            border-color: #047857;
            color: #D1FAE5 !important;
          }
          .srx-sticky-chip.score {
            background: #1E3A5F;
            border-color: #334155;
            color: #93C5FD !important;
          }
          .srx-sticky-chip.score strong { color: #93C5FD !important; }
          .srx-panel,
          .srx-trend,
          .srx-phase-angle,
          .srx-bmr,
          .srx-heatmap,
          .srx-multidim,
          .srx-score-persona,
          .srx-mission,
          .srx-persona-card,
          .srx-landing,
          .srx-step {
            background: var(--surface-solid) !important;
            border-color: var(--line) !important;
          }
          .srx-topbar .mark,
          .srx-section-title,
          .srx-trend-head .title,
          .srx-phase-head .title,
          .srx-heatmap-head .title,
          .srx-multidim .title,
          .srx-score-persona .title,
          .srx-mission-head .title {
            color: var(--ink) !important;
          }
          .srx-reward {
            background: #0F172A !important;
            border-color: var(--line) !important;
          }
          .srx-reward strong { color: #F1F5F9 !important; }
          .srx-reward span { color: var(--muted) !important; }
          .srx-reward.gold {
            background: linear-gradient(90deg, #422006, #0F172A) !important;
          }
          .srx-reward.evolve {
            background: linear-gradient(90deg, #064E3B, #0F172A) !important;
          }
          .srx-evolution-celebration {
            background: linear-gradient(90deg, #064E3B, #1E3A5F) !important;
            border-color: rgba(16, 185, 129, 0.35) !important;
          }
          .srx-evolution-celebration .msg { color: #CBD5E1 !important; }
          .srx-body-evolution {
            background: linear-gradient(90deg, #422006, #064E3B) !important;
            border-color: rgba(245, 158, 11, 0.35) !important;
          }
          .srx-body-evolution .msg { color: #CBD5E1 !important; }
          .srx-meal li { color: var(--ink-soft) !important; }
          .srx-caution {
            background: linear-gradient(90deg, #422006 0%, #1E293B 100%) !important;
            border-left-color: #F59E0B !important;
            color: #FCD34D !important;
          }
          .srx-caution * { color: #FCD34D !important; }
          .srx-persona-card {
            background: linear-gradient(165deg, #0F172A, #1E293B) !important;
            border-color: var(--line) !important;
          }
          .srx-persona-name { color: #F1F5F9 !important; }
          .srx-persona-tagline,
          .srx-persona-evo { color: #94A3B8 !important; }
        }

        /* 접근성 — 키보드 포커스 · 모션 감소 */
        .srx-card:focus-within,
        .srx-wplan-row:focus-within,
        .srx-reward:focus-within {
          outline: 2px solid #3B82F6;
          outline-offset: 2px;
        }
        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
          }
          .srx-card:hover {
            transform: none !important;
          }
        }
        """
    st.markdown(f"<style>{css}{dark_block}</style>", unsafe_allow_html=True)


def _dark_theme_css() -> str:
    """사이드바 토글용 다크 테마 (시스템 설정보다 우선)."""
    return """
        :root {
          --ink: #F1F5F9;
          --ink-soft: #CBD5E1;
          --muted: #94A3B8;
          --line: #334155;
          --line-soft: #1E293B;
          --surface: #1E293B;
          --surface-solid: #1E293B;
          --brand-deep: #F1F5F9;
          --brand-mist: #064E3B;
          --sand: #1E293B;
          --warn: #FCD34D;
          --srx-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
        }
        .stApp { background: #0F172A !important; color: var(--ink); }
        section[data-testid="stSidebar"] {
          background: #1E293B !important;
          border-right-color: var(--line) !important;
        }
        .stTabs [data-baseweb="tab-list"] { background: #0F172A; }
        .stTabs [aria-selected="true"] {
          background: #1E293B !important;
          color: var(--ink) !important;
        }
        .srx-sticky-bar {
          background: rgba(15, 23, 42, 0.94);
          border-bottom-color: var(--line);
        }
        .srx-sticky-chip {
          background: #1E293B;
          border-color: var(--line);
          color: var(--ink-soft) !important;
        }
        .srx-sticky-chip.name {
          background: #064E3B;
          border-color: #047857;
          color: #D1FAE5 !important;
        }
        .srx-sticky-chip.score {
          background: #1E3A5F;
          border-color: #334155;
          color: #93C5FD !important;
        }
        .srx-sticky-chip.score strong { color: #93C5FD !important; }
        .srx-card-icon { background: #064E3B; border-color: #334155; color: #6EE7B7; }
        .srx-empty-visual { background: linear-gradient(165deg, #064E3B, #1E3A5F); border-color: #334155; }
        .srx-empty-visual svg { color: #6EE7B7; }
        .srx-panel, .srx-trend, .srx-phase-angle, .srx-bmr, .srx-heatmap,
        .srx-multidim, .srx-score-persona, .srx-mission, .srx-persona-card,
        .srx-step, .srx-empty-hero, .srx-verdict, .srx-card, .srx-wplan,
        .srx-slime-growth {
          background: var(--surface-solid) !important;
          border-color: var(--line) !important;
        }
        .srx-topbar .mark, .srx-section-title, .srx-trend-head .title,
        .srx-phase-head .title, .srx-heatmap-head .title, .srx-multidim .title,
        .srx-score-persona .title, .srx-mission-head .title, .srx-empty-brand {
          color: var(--ink) !important;
        }
        .srx-reward { background: #0F172A !important; border-color: var(--line) !important; }
        .srx-reward strong { color: #F1F5F9 !important; }
        .srx-reward span { color: var(--muted) !important; }
        .srx-reward.gold { background: linear-gradient(90deg, #422006, #0F172A) !important; }
        .srx-reward.evolve { background: linear-gradient(90deg, #064E3B, #0F172A) !important; }
        .srx-evolution-celebration {
          background: linear-gradient(90deg, #064E3B, #1E3A5F) !important;
          border-color: rgba(16, 185, 129, 0.35) !important;
        }
        .srx-evolution-celebration .msg { color: #CBD5E1 !important; }
        .srx-body-evolution {
          background: linear-gradient(90deg, #422006, #064E3B) !important;
          border-color: rgba(245, 158, 11, 0.35) !important;
        }
        .srx-body-evolution .msg { color: #CBD5E1 !important; }
        .stMain [data-testid="stExpander"] {
          background: var(--surface-solid) !important;
          border-color: var(--line) !important;
        }
        .stMain [data-testid="stExpander"] summary {
          color: var(--ink) !important;
        }
        .stMain [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
          border-top-color: var(--line) !important;
        }
        .srx-section-hint { color: var(--muted) !important; }
        .stMain [data-testid="stFileUploader"] {
          background: var(--surface-solid) !important;
          border-color: var(--line) !important;
        }
        .stMain:has(.srx-upload-marker.hero) [data-testid="stFileUploader"] {
          background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%) !important;
          border-color: #047857 !important;
        }
        .stMain [data-testid="stFileUploader"]:hover {
          background: #064E3B !important;
        }
        .srx-upload-zone-icon {
          background: linear-gradient(165deg, #064E3B, #1E3A5F) !important;
          border-color: #334155 !important;
          color: #6EE7B7 !important;
        }
        .srx-upload-zone-title { color: var(--ink) !important; }
        .srx-disclaimer {
          background: var(--surface-solid) !important;
          border-color: var(--line) !important;
          color: var(--muted) !important;
        }
        .srx-meal li { color: var(--ink-soft) !important; }
        .srx-meal-chip,
        .srx-meal-card,
        .srx-meal-insights {
          background: var(--surface-solid) !important;
          border-color: var(--line) !important;
        }
        .srx-meal-card-icon {
          background: #064E3B !important;
          border-color: #334155 !important;
          color: #6EE7B7 !important;
        }
        .srx-meal-chip strong,
        .srx-meal-card-head h4,
        .srx-meal-insights-title,
        .srx-meal-insight .body strong {
          color: var(--ink) !important;
        }
        .srx-meal-avoid {
          background: linear-gradient(90deg, #422006 0%, #1E293B 100%) !important;
          border-color: rgba(245, 158, 11, 0.35) !important;
        }
        .srx-meal-avoid strong { color: #FCD34D !important; }
        .srx-meal-avoid .tags span {
          background: #0F172A !important;
          border-color: #78350F !important;
          color: #FCD34D !important;
        }
        .srx-meal-week {
          background: var(--surface-solid) !important;
          border-color: var(--line) !important;
        }
        .srx-meal-week-title { color: var(--ink) !important; }
        .srx-meal-week-row.today {
          background: #064E3B !important;
        }
        .srx-meal-week-row .hint { color: var(--ink-soft) !important; }
        .srx-caution {
          background: linear-gradient(90deg, #422006 0%, #1E293B 100%) !important;
          border-left-color: #F59E0B !important;
          color: #FCD34D !important;
        }
        .srx-caution * { color: #FCD34D !important; }
        .srx-persona-name { color: #F1F5F9 !important; }
        .srx-persona-tagline, .srx-persona-evo { color: #94A3B8 !important; }
        .srx-card-block li, .srx-rx-body li { color: var(--ink-soft) !important; }
    """


def _fmt(val, unit: str = "") -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        text = f"{val:.2f}".rstrip("0").rstrip(".")
    else:
        text = str(val)
    return f"{text}{unit}"


def _metric_html(label: str, value: str, sub: str = "", status: str | None = None) -> str:
    badge = ""
    if status and status in STATUS_META:
        text, fg, bg = STATUS_META[status]
        badge = f'<span class="srx-badge" style="color:{fg};background:{bg};">{_esc(text)}</span>'
    return (
        f'<div class="srx-metric"><div class="k">{_esc(label)}</div>'
        f'<div class="v">{_esc(value)}</div>'
        f'<div class="s">{_esc(sub)}</div>{badge}</div>'
    )


def _render_metric_row(items: list[tuple[str, str, str, str | None]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, sub, status) in zip(cols, items):
        with col:
            st.markdown(_metric_html(label, value, sub, status), unsafe_allow_html=True)


def _chart_layout(**kwargs) -> dict:
    return chart_layout(**kwargs)


# parser.INBODY_RESULT_SCHEMA_VERSION 과 동일하게 유지 (필드 변경 시 둘 다 올릴 것)
UPLOAD_CACHE_SCHEMA_VERSION = 4


@st.cache_data(show_spinner=False)
def _analyze_upload(
    file_bytes: bytes,
    filename: str,
    *,
    _schema_version: int = UPLOAD_CACHE_SCHEMA_VERSION,
) -> InBodyResult:
    """PDF/사진 OCR 결과 캐시. _schema_version 변경 시 캐시가 자동 무효화된다."""
    del _schema_version
    return normalize_inbody_result(parse_inbody_upload(file_bytes, filename))


# 하위 호환 별칭
PDF_CACHE_SCHEMA_VERSION = UPLOAD_CACHE_SCHEMA_VERSION


@st.cache_data(show_spinner=False)
def _analyze_pdf(
    pdf_bytes: bytes,
    *,
    _schema_version: int = UPLOAD_CACHE_SCHEMA_VERSION,
) -> InBodyResult:
    del _schema_version
    return normalize_inbody_result(parse_inbody_pdf(pdf_bytes))


def _build_prescription_context(
    result: InBodyResult,
    report: PrescriptionReport,
    session_state: dict,
) -> PrescriptionContext:
    trend = build_trend_report(result)
    body_evo = get_body_evolution(session_state)
    dashboard = build_persona_dashboard(result, report, trend, body_evolution=body_evo)
    profile_key = sync_mission_profile(result, session_state)
    missions = generate_missions(result, report)
    mission_progress = None
    growth = None
    evolution = None
    launch = None

    if missions:
        mission_progress = count_mission_progress(missions, profile_key, session_state)
        growth = build_slime_growth_report(
            result, report, dashboard, mission_progress, session_state, trend
        )
        evolution = evaluate_evolution(growth, mission_progress, dashboard)
        launch = build_launch_dashboard(
            result, report, dashboard, growth, mission_progress, evolution, trend
        )

    return PrescriptionContext(
        trend=trend,
        dashboard=dashboard,
        body_evo=body_evo,
        missions=missions,
        mission_progress=mission_progress,
        growth=growth,
        evolution=evolution,
        launch=launch,
        phase_report=build_phase_angle_report(result),
        bmr_report=build_bmr_report(result),
    )


def _sticky_phase_text(phase_report: PhaseAngleReport | None) -> tuple[str, str]:
    if not phase_report or phase_report.current is None:
        return "—", ""
    suffix = ""
    chip_class = "metric"
    if phase_report.trend == "up":
        suffix = " ↑"
        chip_class = "metric up"
    elif phase_report.trend == "down":
        suffix = " ↓"
        chip_class = "metric down"
    return f"{phase_report.current:.1f}°{suffix}", chip_class


def render_sticky_summary_bar(
    result: InBodyResult,
    report: PrescriptionReport,
    ctx: PrescriptionContext,
) -> None:
    name = result.name or "회원"
    body_type = report.body_type or "—"
    phase_value, phase_class = _sticky_phase_text(ctx.phase_report)
    if ctx.bmr_report:
        bmr_value = f"{ctx.bmr_report.value:.0f} kcal"
    else:
        bmr_value = "—"
    readiness = (
        ctx.launch.readiness_score
        if ctx.launch
        else ctx.dashboard.composite_score
    )

    st.markdown(
        f"""
        <div class="srx-sticky-bar">
          <div class="srx-sticky-inner">
            <span class="srx-sticky-chip name">{_esc(name)}</span>
            <span class="srx-sticky-chip type">{_esc(body_type)}</span>
            <span class="srx-sticky-chip {phase_class}">위상각 <strong>{_esc(phase_value)}</strong></span>
            <span class="srx-sticky-chip metric">BMR <strong>{_esc(bmr_value)}</strong></span>
            <span class="srx-sticky-chip score">준비도 <strong>{readiness}점</strong></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_landing() -> None:
    st.markdown(
        """
        <div class="srx-empty-hero">
          <div class="srx-empty-visual" aria-hidden="true">
            <svg viewBox="0 0 96 120" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round" stroke-linejoin="round">
              <circle cx="48" cy="22" r="14"/>
              <path d="M48 36v34"/>
              <path d="M48 48H28"/>
              <path d="M48 48H68"/>
              <path d="M48 70 34 98"/>
              <path d="M48 70 62 98"/>
              <path d="M34 98h28"/>
            </svg>
          </div>
          <div>
            <p class="srx-empty-kicker">SomaRx 2.0 · MY BODY DASHBOARD</p>
            <h1 class="srx-empty-brand">InBody 처방 클리닉</h1>
            <p class="srx-empty-lede">결과지를 업로드하면 체성분 해석, 성장 캐릭터, 맞춤 처방을 한 화면에서 확인할 수 있습니다.</p>
          </div>
        </div>
        <div class="srx-steps">
          <div class="srx-step">
            <div class="n">01</div>
            <div class="t">결과지 업로드</div>
            <div class="d">위 드롭존에 InBody PDF 또는 결과지 사진을 올립니다.</div>
          </div>
          <div class="srx-step">
            <div class="n">02</div>
            <div class="t">자동 분석</div>
            <div class="d">OCR로 지표를 읽고 체형을 판정합니다.</div>
          </div>
          <div class="srx-step">
            <div class="n">03</div>
            <div class="t">처방 확인</div>
            <div class="d">영양·운동·주간 플랜을 한곳에서 확인합니다.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_topbar() -> None:
    st.markdown(
        """
        <div class="srx-topbar">
          <h1 class="mark">SomaRx 2.0</h1>
          <div class="sub">MY BODY DASHBOARD · InBody 처방 클리닉</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_patient_strip(result: InBodyResult) -> None:
    items = [
        ("이름", result.name or "—", True),
        ("신장", _fmt(result.height_cm, " cm"), False),
        ("연령", _fmt(result.age, "세"), False),
        ("성별", result.gender or "—", False),
        ("검사일시", result.test_datetime or "—", False),
    ]
    cells = []
    for k, v, is_name in items:
        cls = "srx-id-cell name" if is_name else "srx-id-cell"
        cells.append(
            f'<div class="{cls}"><div class="k">{_esc(k)}</div>'
            f'<div class="v">{_esc(v)}</div></div>'
        )
    st.markdown(f'<div class="srx-identity">{"".join(cells)}</div>', unsafe_allow_html=True)


def _composition_chart(result: InBodyResult) -> go.Figure:
    pal = get_palette()
    rows: list[dict] = []
    specs = [
        ("체수분", result.body_water),
        ("단백질", result.protein),
        ("무기질", result.mineral),
        ("체지방", result.body_fat_mass),
        ("체중", result.weight),
    ]
    for name, rv in specs:
        if rv.value is None or rv.low is None or rv.high is None or rv.high == rv.low:
            continue
        mid = (rv.low + rv.high) / 2
        span = (rv.high - rv.low) / 2
        score = 100 + ((rv.value - mid) / span) * 20 if span else 100
        rows.append({"지표": name, "현재": round(score, 1)})

    fig = go.Figure()
    if not rows:
        fig.update_layout(**_chart_layout(height=280))
        return fig

    names = [r["지표"] for r in rows]
    fig.add_trace(
        go.Scatter(
            x=names + names[::-1],
            y=[80] * len(names) + [120] * len(names),
            fill="toself",
            fillcolor="rgba(14,101,87,0.11)",
            line=dict(width=0),
            name="정상 대역",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=names,
            y=[r["현재"] for r in rows],
            mode="lines+markers",
            name="현재",
            line=dict(color="#10B981", width=3, shape="spline"),
            marker=dict(size=9, color=pal.ink, line=dict(width=2, color=pal.marker_line)),
        )
    )
    fig.add_hline(
        y=100,
        line_dash="dot",
        line_color=pal.reference_line,
        annotation_text="정상 중앙",
        annotation_font_color=pal.muted,
    )
    fig.update_layout(
        **_chart_layout(
            height=300,
            yaxis_title="상대 점수",
            legend=dict(orientation="h", y=1.14, bgcolor="rgba(0,0,0,0)"),
        )
    )
    return fig


def _segment_chart(result: InBodyResult) -> go.Figure:
    pal = get_palette()
    labels = ["오른팔", "왼팔", "몸통", "오른다리", "왼다리"]
    values = [
        result.right_arm_kg,
        result.left_arm_kg,
        result.trunk_kg,
        result.right_leg_kg,
        result.left_leg_kg,
    ]
    data = [(l, v) for l, v in zip(labels, values) if v is not None]
    fig = go.Figure(
        go.Bar(
            x=[v for _, v in data],
            y=[l for l, _ in data],
            orientation="h",
            marker_color=["#10B981", "#059669", "#0F172A", "#3B82F6", "#34D399"],
            text=[f"{v:.2f} kg" for _, v in data],
            textposition="outside",
            textfont=dict(color=pal.ink, size=11),
            marker_line_width=0,
        )
    )
    fig.update_layout(
        **_chart_layout(
            height=280,
            margin=dict(l=70, r=60, t=10, b=30),
            xaxis_title="kg",
            showlegend=False,
        )
    )
    return fig


def _priority_chart(report: PrescriptionReport) -> go.Figure:
    pal = get_palette()
    counts = {"높음": 0, "보통": 0, "참고": 0}
    for s in report.sections:
        if s.priority in counts:
            counts[s.priority] += 1
    labels = [k for k, v in counts.items() if v]
    values = [counts[k] for k in labels]
    colors = [PRIORITY_META[k][0] for k in labels]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            marker=dict(colors=colors, line=dict(color=pal.marker_line, width=2)),
            textinfo="label+value",
            textfont=dict(size=12, color=pal.ink),
        )
    )
    fig.update_layout(
        **_chart_layout(
            height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
            annotations=[
                dict(
                    text="우선순위",
                    x=0.5,
                    y=0.5,
                    font_size=13,
                    showarrow=False,
                    font_color=pal.ink,
                )
            ],
        )
    )
    return fig


def render_verdict(report: PrescriptionReport) -> None:
    summary = _plain(report.overall_summary)
    flags = "".join(f'<span class="srx-flag">{_esc(f)}</span>' for f in report.risk_flags)
    st.markdown(
        f"""
        <div class="srx-verdict">
          <div class="label">종합 판정</div>
          <div class="shape">{_esc(report.body_type)}</div>
          <div class="summary">{_esc(summary)}</div>
          <div class="srx-flags">{flags}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _delta_class(delta: float | None, positive_good: bool) -> str:
    if delta is None or abs(delta) < 0.05:
        return "neutral"
    if positive_good:
        return "up-good" if delta > 0 else "warn"
    return "down-good" if delta < 0 else "warn"


def _trend_delta_cell(
    label: str,
    points: list,
    field: str,
    unit: str,
    delta: float | None,
    positive_good: bool,
) -> str:
    values = [getattr(p, field) for p in points if getattr(p, field) is not None]
    if not values:
        flow = "—"
        chg = "—"
        cls = "neutral"
    elif len(values) == 1:
        flow = f"[ {_fmt(values[0], unit)} ]"
        chg = "비교 기록 없음"
        cls = "neutral"
    else:
        flow = f"[ {_fmt(values[-2], unit)} ] → [ {_fmt(values[-1], unit)} ]"
        chg = format_delta_text(delta, unit, positive_good)
        cls = _delta_class(delta, positive_good)
    return (
        f'<div class="srx-trend-delta">'
        f'<div class="k">{_esc(label)}</div>'
        f'<div class="flow">{_esc(flow)}</div>'
        f'<div class="chg {cls}">{_esc(chg)}</div>'
        f"</div>"
    )


def _rich_comment(text: str) -> str:
    parts = re.split(r"\*\*(.+?)\*\*", text)
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(f"<strong>{_esc(part)}</strong>")
        else:
            out.append(_esc(part))
    return "".join(out)


def render_trend_report(report: TrendReport, *, compact: bool = False) -> None:
    points = report.points
    weather = report.weather
    deltas_html = "".join(
        [
            _trend_delta_cell(
                "골격근량 (kg) 📈",
                points,
                "smm",
                " kg",
                report.smm_delta,
                positive_good=True,
            ),
            _trend_delta_cell(
                "체지방률 (%) 📉",
                points,
                "pbf",
                "%",
                report.pbf_delta,
                positive_good=False,
            ),
            _trend_delta_cell(
                "체중 (kg)",
                points,
                "weight",
                " kg",
                report.weight_delta,
                positive_good=False,
            ),
        ]
    )
    trend_head = (
        f'<div class="srx-trend-weather {weather.tone}">'
        f'<span class="icon">{weather.emoji}</span>'
        f"<span>이번 달 건강 날씨: {_esc(weather.label)}</span>"
        f"</div>"
    )
    if compact:
        st.markdown(
            f'<div class="srx-trend"><div class="srx-trend-head">{trend_head}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="srx-trend">
              <div class="srx-trend-head">
                {section_heading_html("trend", "나의 신체 변화 트렌드")}
                {trend_head}
              </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div class="srx-trend-deltas">{deltas_html}</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(
            make_trend_chart(points, "smm", "#2563EB", " kg", "골격근량"),
            width="stretch",
            key="trend_smm",
        )
    with c2:
        st.plotly_chart(
            make_trend_chart(points, "pbf", "#EA580C", "%", "체지방률"),
            width="stretch",
            key="trend_pbf",
        )
    with c3:
        st.plotly_chart(
            make_trend_chart(points, "weight", "#10B981", " kg", "체중"),
            width="stretch",
            key="trend_weight",
        )

    st.markdown(
        f'<div class="srx-trend-comment">{_rich_comment(report.comment)}</div></div>',
        unsafe_allow_html=True,
    )


def render_phase_angle_widget(result: InBodyResult) -> None:
    report = build_phase_angle_report(result)
    if not report:
        return

    badge_text, badge_class = format_delta_badge(report.delta, report.trend)
    st.markdown(
        f"""
        <div class="srx-phase-angle">
          <div class="srx-phase-head">
            <div>
              {section_heading_html("phase", "위상각 (Phase Angle) 트렌드")}
              <p class="sub">세포 건강·영양 상태를 반영하는 연구항목 — 시간에 따른 개선 추이</p>
            </div>
          </div>
          <div class="srx-phase-hero">
            <div class="srx-phase-current">{report.current:.1f}<span>°</span></div>
            <div class="srx-phase-badge {badge_class}">{_esc(badge_text)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        make_phase_angle_chart(report.points, report.delta),
        width="stretch",
        key="phase_angle_trend",
    )
    st.markdown(
        f'<div class="srx-phase-comment">{_rich_comment(report.comment)}</div>',
        unsafe_allow_html=True,
    )


def render_bmr_widget(result: InBodyResult) -> None:
    report = build_bmr_report(result)
    if not report:
        return

    st.markdown(render_bmr_widget_html(report), unsafe_allow_html=True)
    st.markdown(
        f'<div class="srx-bmr-comment">{_rich_comment(report.comment)}</div>',
        unsafe_allow_html=True,
    )


def render_mission_tracker(result: InBodyResult, report: PrescriptionReport) -> None:
    profile_key = sync_mission_profile(result, st.session_state)
    missions = generate_missions(result, report)
    if not missions:
        return

    st.markdown(
        f"""
        <div class="srx-mission">
          <div class="srx-mission-head">
            {section_heading_html("mission", "이번 주 데일리 미션")}
            <p class="sub">처방에 맞춘 핵심 미션 3가지 — 매일 실천 후 체크하세요.</p>
          </div>
        """,
        unsafe_allow_html=True,
    )

    for index, mission in enumerate(missions, start=1):
        fg, bg, _ = PRIORITY_META.get(mission.priority, ("#10B981", "#D1FAE5", mission.priority))
        st.markdown(
            f'<div class="srx-mission-row">'
            f'<div class="label">{index}. {_esc(mission.title)} {mission.emoji}'
            f'<span class="prio" style="color:{fg};background:{bg};">{_esc(mission.priority)}</span>'
            f"</div></div>",
            unsafe_allow_html=True,
        )
        cols = st.columns(len(WEEK_DAYS))
        for day_index, (col, day) in enumerate(zip(cols, WEEK_DAYS)):
            with col:
                st.checkbox(
                    day,
                    key=mission_checkbox_key(mission.id, day_index, profile_key),
                )

    progress = count_mission_progress(missions, profile_key, st.session_state)
    badge_html = ""
    if progress.has_gold_badge:
        badge_html = '<div class="srx-mission-badge gold">🏆 골드 뱃지 달성!</div>'

    st.progress(min(progress.rate / 100, 1.0))
    st.markdown(
        f"""
          <div class="srx-mission-progress">
            <div class="rate-line">
              <span>현재 달성률: {progress.rate:.0f}% ({progress.completed}/{progress.total})</span>
            </div>
            {badge_html}
            <p class="srx-mission-note">{_esc(progress.message)}<br/>
            오프라인에서는 결과지 후면에 인쇄해 냉장고 등에 붙여두고 펜으로 체크해도 좋습니다.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_slime_growth_widget(
    result: InBodyResult,
    report: PrescriptionReport,
    trend: TrendReport | None = None,
    *,
    growth: SlimeGrowthReport | None = None,
    evolution: EvolutionState | None = None,
    embedded: bool = False,
) -> None:
    if growth is None:
        dashboard = build_persona_dashboard(result, report, trend)
        profile_key = sync_mission_profile(result, st.session_state)
        missions = generate_missions(result, report)
        if not missions:
            return

        progress = count_mission_progress(missions, profile_key, st.session_state)
        growth = build_slime_growth_report(
            result, report, dashboard, progress, st.session_state, trend
        )
        if evolution is None:
            evolution = evaluate_evolution(growth, progress, dashboard)

    if not embedded:
        st.markdown(section_title_html("slime", "슬라임 성장"), unsafe_allow_html=True)
    if evolution:
        st.markdown(render_evolution_celebration_html(evolution, growth), unsafe_allow_html=True)
    st.markdown(render_slime_growth_html(growth), unsafe_allow_html=True)


def render_body_heatmap(result: InBodyResult, *, stacked: bool = False) -> None:
    report = build_body_heatmap(result)
    st.markdown(
        f"""
        <div class="srx-heatmap">
          <div class="srx-heatmap-head">
            {section_heading_html("heatmap", "2D 인체 실루엣 히트맵")}
            <p class="sub">부위별 근육·체지방 상태를 색으로 한눈에 확인하세요.</p>
          </div>
        """,
        unsafe_allow_html=True,
    )

    if not report.has_data:
        st.markdown(
            f'<p class="srx-heatmap-summary">{_esc(report.summary)}</p></div>',
            unsafe_allow_html=True,
        )
        return

    if stacked:
        st.markdown(render_body_figure(report), unsafe_allow_html=True)
        st.markdown(
            render_legend_html() + render_zone_cards_html(report.zones),
            unsafe_allow_html=True,
        )
    else:
        col_svg, col_info = st.columns([0.85, 1.15], gap="medium")
        with col_svg:
            st.markdown(render_body_figure(report), unsafe_allow_html=True)
        with col_info:
            st.markdown(
                render_legend_html() + render_zone_cards_html(report.zones),
                unsafe_allow_html=True,
            )

    st.markdown(
        f'<p class="srx-heatmap-summary">{_esc(report.summary)}</p></div>',
        unsafe_allow_html=True,
    )


def render_multidim_analysis(
    result: InBodyResult,
    report: PrescriptionReport,
    *,
    compact: bool = False,
) -> None:
    analysis = build_multidim_analysis(result, report)
    if not analysis.has_radar and not analysis.has_quadrant:
        return

    heading_block = (
        ""
        if compact
        else f"""
          {section_heading_html("multidim", "다차원 상태 분석")}
          <p class="sub">영양·근육 균형(방사형)과 체형 위치(사분면)를 함께 확인하세요.</p>
        """
    )
    st.markdown(
        f"""
        <div class="srx-multidim">
          {heading_block}
        """,
        unsafe_allow_html=True,
    )

    col_radar, col_quad = st.columns(2, gap="medium")
    with col_radar:
        if analysis.has_radar:
            st.plotly_chart(
                make_radar_chart(analysis),
                width="stretch",
                key="multidim_radar",
            )
    with col_quad:
        if analysis.has_quadrant:
            st.plotly_chart(
                make_quadrant_chart(analysis, result),
                width="stretch",
                key="multidim_quadrant",
            )

    st.markdown(
        f'<p class="srx-multidim-summary">{_esc(analysis.summary)}</p></div>',
        unsafe_allow_html=True,
    )


def render_score_persona_dashboard(
    result: InBodyResult,
    report: PrescriptionReport,
    trend: TrendReport | None = None,
    *,
    dashboard: PersonaDashboard | None = None,
    evolution_ready: bool = False,
    compact: bool = False,
) -> None:
    if dashboard is None:
        dashboard = build_persona_dashboard(result, report, trend)

    heading_block = (
        ""
        if compact
        else section_heading_html("score", "나의 점수 & 체형 캐릭터")
    )
    st.markdown(
        f"""
        <div class="srx-score-persona">
          {heading_block}
        """,
        unsafe_allow_html=True,
    )

    col_gauge, col_persona = st.columns([1.35, 0.65], gap="medium")
    with col_gauge:
        if dashboard.has_growth and dashboard.growth_score is not None:
            g1, g2 = st.columns(2)
            with g1:
                st.plotly_chart(
                    make_speedometer(dashboard.growth_score, dashboard.growth_label),
                    width="stretch",
                    key="gauge_growth",
                )
            with g2:
                st.plotly_chart(
                    make_speedometer(dashboard.composite_score, dashboard.composite_label),
                    width="stretch",
                    key="gauge_composite",
                )
        else:
            st.plotly_chart(
                make_speedometer(dashboard.composite_score, dashboard.composite_label),
                width="stretch",
                key="gauge_composite_only",
            )

    with col_persona:
        st.markdown(
            render_persona_card_html(
                dashboard, report.body_type, evolution_ready=evolution_ready
            ),
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_bento_dashboard(
    report: PrescriptionReport,
    result: InBodyResult,
    ctx: PrescriptionContext,
) -> None:
    """2단계 Bento 레이아웃 — 핵심 지표를 한 화면에 배치."""
    st.markdown('<div class="srx-section-title">핵심 대시보드</div>', unsafe_allow_html=True)
    st.markdown('<div class="srx-bento">', unsafe_allow_html=True)

    row1_left, row1_right = st.columns([3, 2], gap="medium")
    with row1_left:
        st.markdown('<div class="srx-bento-cell">', unsafe_allow_html=True)
        render_verdict(report)
        st.markdown("</div>", unsafe_allow_html=True)
    with row1_right:
        st.markdown('<div class="srx-bento-cell">', unsafe_allow_html=True)
        render_phase_angle_widget(result)
        st.markdown("</div>", unsafe_allow_html=True)

    row2_left, row2_right = st.columns([2, 3], gap="medium")
    with row2_left:
        st.markdown('<div class="srx-bento-cell">', unsafe_allow_html=True)
        render_bmr_widget(result)
        st.markdown("</div>", unsafe_allow_html=True)
    with row2_right:
        st.markdown('<div class="srx-bento-cell">', unsafe_allow_html=True)
        render_body_heatmap(result, stacked=True)
        st.markdown("</div>", unsafe_allow_html=True)

    row3_left, row3_right = st.columns(2, gap="medium")
    with row3_left:
        st.markdown('<div class="srx-bento-cell">', unsafe_allow_html=True)
        render_mission_tracker(result, report)
        st.markdown("</div>", unsafe_allow_html=True)
    with row3_right:
        st.markdown('<div class="srx-bento-cell">', unsafe_allow_html=True)
        render_slime_growth_widget(
            result,
            report,
            ctx.trend,
            growth=ctx.growth,
            evolution=ctx.evolution,
            embedded=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_prescription(
    report: PrescriptionReport,
    result: InBodyResult,
    ctx: PrescriptionContext | None = None,
) -> None:
    if ctx is None:
        ctx = _build_prescription_context(result, report, st.session_state)

    if ctx.body_evo:
        st.markdown(render_body_evolution_html(ctx.body_evo), unsafe_allow_html=True)

    if ctx.launch and ctx.evolution and ctx.mission_progress:
        st.markdown(render_launch_banner_html(ctx.launch), unsafe_allow_html=True)
        st.markdown(
            render_rewards_strip_html(ctx.evolution, ctx.mission_progress),
            unsafe_allow_html=True,
        )

    render_bento_dashboard(report, result, ctx)

    render_score_persona_dashboard(
        result,
        report,
        ctx.trend,
        dashboard=ctx.dashboard,
        evolution_ready=bool(ctx.evolution and ctx.evolution.ready) or bool(ctx.body_evo),
    )

    render_multidim_analysis(result, report)

    if ctx.trend:
        render_trend_report(ctx.trend)

    st.markdown('<div class="srx-section-title">한눈에 보기</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.45, 1])
    with c1:
        st.markdown('<div class="srx-panel">', unsafe_allow_html=True)
        st.plotly_chart(
            _composition_chart(result), width="stretch", key="prescription_composition"
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="srx-panel">', unsafe_allow_html=True)
        st.plotly_chart(
            _priority_chart(report), width="stretch", key="prescription_priorities"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="srx-section-title">처방</div>', unsafe_allow_html=True)
    st.markdown(render_prescription_cards(report.sections), unsafe_allow_html=True)

    st.markdown('<div class="srx-section-title">주간 플랜</div>', unsafe_allow_html=True)
    render_weekly_plan_widget(result, report)

    st.markdown(section_title_html("meal", "식단"), unsafe_allow_html=True)
    meal_plan = build_meal_plan(result, report)
    st.markdown(render_meal_plan_html(meal_plan), unsafe_allow_html=True)

    caution = "<br/>".join(f"• {_esc(_plain(c))}" for c in report.caution)
    st.markdown(f'<div class="srx-caution">{caution}</div>', unsafe_allow_html=True)


def render_weekly_plan_widget(result: InBodyResult, report: PrescriptionReport) -> None:
    rows = build_weekly_plan_rows(report.weekly_plan)
    profile_key = sync_weekly_plan_profile(result, st.session_state)
    statuses = collect_statuses(rows, profile_key, st.session_state)

    st.markdown(render_weekly_plan_table(rows, statuses), unsafe_allow_html=True)

    st.markdown('<div class="srx-wplan-check-label">요일별 완료 체크</div>', unsafe_allow_html=True)
    cols = st.columns(len(rows))
    for col, row in zip(cols, rows):
        with col:
            st.checkbox(
                f"{row.day_short} 완료",
                key=weekly_plan_done_key(row.day_index, profile_key),
            )


def render_body_metrics(result: InBodyResult) -> None:
    st.markdown('<div class="srx-section-title">체성분</div>', unsafe_allow_html=True)
    row1: list[tuple[str, str, str, str | None]] = []
    for label, rv, unit in [
        ("체수분", result.body_water, " L"),
        ("단백질", result.protein, " kg"),
        ("무기질", result.mineral, " kg"),
        ("체지방량", result.body_fat_mass, " kg"),
        ("체중", result.weight, " kg"),
    ]:
        sub = ""
        if rv.low is not None and rv.high is not None:
            sub = f"정상 {_fmt(rv.low)}~{_fmt(rv.high)}{unit}"
        row1.append((label, _fmt(rv.value, unit), sub, rv.status))
    _render_metric_row(row1)

    st.markdown('<div class="srx-panel">', unsafe_allow_html=True)
    st.plotly_chart(_composition_chart(result), width="stretch", key="metrics_composition")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="srx-section-title">주요 지표</div>', unsafe_allow_html=True)
    row2 = [
        ("골격근량", _fmt(result.skeletal_muscle_mass, " kg"), "", None),
        ("BMI", _fmt(result.bmi), result.obesity_bmi or "", None),
        ("체지방률", _fmt(result.percent_body_fat, "%"), result.obesity_pbf or "", None),
        (
            "기초대사량",
            _fmt(result.bmr.value, " kcal"),
            f"정상 {_fmt(result.bmr.low)}~{_fmt(result.bmr.high)}" if result.bmr.low else "",
            result.bmr.status,
        ),
        (
            "성장점수",
            _fmt(result.growth_score, " /100") if result.growth_score else "—",
            "",
            None,
        ),
    ]
    _render_metric_row(row2)

    st.markdown('<div class="srx-section-title">부위별 근육 · 균형</div>', unsafe_allow_html=True)
    st.markdown('<div class="srx-panel">', unsafe_allow_html=True)
    st.plotly_chart(_segment_chart(result), width="stretch", key="metrics_segment")
    st.markdown("</div>", unsafe_allow_html=True)

    segs = [
        ("오른팔", result.right_arm_kg),
        ("왼팔", result.left_arm_kg),
        ("몸통", result.trunk_kg),
        ("오른다리", result.right_leg_kg),
        ("왼다리", result.left_leg_kg),
    ]
    cols = st.columns(5)
    for col, (k, v) in zip(cols, segs):
        with col:
            st.markdown(
                f'<div class="srx-seg-item"><div class="k">{_esc(k)}</div>'
                f'<div class="v">{_esc(_fmt(v, " kg"))}</div></div>',
                unsafe_allow_html=True,
            )

    b1, b2, b3 = st.columns(3)
    for col, text in zip(
        (b1, b2, b3),
        [
            f"상체 좌우 · {result.balance_upper or '—'}",
            f"하체 좌우 · {result.balance_lower or '—'}",
            f"상하체 · {result.balance_upper_lower or '—'}",
        ],
    ):
        with col:
            st.markdown(f'<div class="srx-bal-item">{_esc(text)}</div>', unsafe_allow_html=True)


def manual_override_sidebar(result: InBodyResult) -> InBodyResult:
    with st.sidebar.expander("지표 수동 보정", expanded=False):
        st.caption("OCR 값이 어긋날 때만 수정하세요. 처방이 즉시 다시 계산됩니다.")
        result.name = st.text_input("이름", result.name or "")
        result.height_cm = st.number_input(
            "신장 (cm)", value=float(result.height_cm or 0) or 0.0, step=0.1
        )
        result.age = int(
            st.number_input("연령", value=int(result.age or 0), step=1, min_value=0)
        )
        gender = st.selectbox(
            "성별",
            ["", "남", "여"],
            index=["", "남", "여"].index(result.gender)
            if result.gender in ("남", "여")
            else 0,
        )
        result.gender = gender or None

        result.weight.value = st.number_input(
            "체중 (kg)", value=float(result.weight.value or 0) or 0.0, step=0.1
        )
        result.skeletal_muscle_mass = st.number_input(
            "골격근량 (kg)",
            value=float(result.skeletal_muscle_mass or 0) or 0.0,
            step=0.1,
        )
        result.percent_body_fat = st.number_input(
            "체지방률 (%)",
            value=float(result.percent_body_fat or 0) or 0.0,
            step=0.1,
        )
        result.body_fat_mass.value = st.number_input(
            "체지방량 (kg)",
            value=float(result.body_fat_mass.value or 0) or 0.0,
            step=0.1,
        )
        result.protein.value = st.number_input(
            "단백질 (kg)", value=float(result.protein.value or 0) or 0.0, step=0.1
        )
        result.mineral.value = st.number_input(
            "무기질 (kg)", value=float(result.mineral.value or 0) or 0.0, step=0.01
        )
        result.body_water.value = st.number_input(
            "체수분 (L)", value=float(result.body_water.value or 0) or 0.0, step=0.1
        )
        result.bmi = st.number_input("BMI", value=float(result.bmi or 0) or 0.0, step=0.1)
        result.bmr.value = st.number_input(
            "기초대사량 (kcal)",
            value=float(result.bmr.value or 0) or 0.0,
            step=1.0,
        )
        result.bmr.low = st.number_input(
            "BMR 권장 하한 (kcal)",
            value=float(result.bmr.low or 0) or 0.0,
            step=1.0,
        )
        result.bmr.high = st.number_input(
            "BMR 권장 상한 (kcal)",
            value=float(result.bmr.high or 0) or 0.0,
            step=1.0,
        )
        result.phase_angle = st.number_input(
            "위상각 (°)",
            value=float(result.phase_angle or 0) or 0.0,
            step=0.1,
            min_value=0.0,
            max_value=15.0,
        )
        result.growth_score = int(
            st.number_input(
                "성장점수",
                value=int(result.growth_score or 0),
                step=1,
                min_value=0,
                max_value=100,
            )
        )

        if result.height_cm == 0:
            result.height_cm = None
        if result.age == 0:
            result.age = None
        if result.skeletal_muscle_mass == 0:
            result.skeletal_muscle_mass = None
        if result.percent_body_fat == 0:
            result.percent_body_fat = None
        if result.bmi == 0:
            result.bmi = None
        if result.growth_score == 0:
            result.growth_score = None
        if result.phase_angle == 0:
            result.phase_angle = None

        for rv in (
            result.body_water,
            result.protein,
            result.mineral,
            result.body_fat_mass,
            result.weight,
            result.bmr,
        ):
            if rv.value == 0:
                rv.value = None
            if rv.low == 0:
                rv.low = None
            if rv.high == 0:
                rv.high = None

        result.nutrition_protein = {
            "low": "부족",
            "normal": "양호",
            "high": "과다",
        }.get(result.protein.status)
        result.nutrition_mineral = {
            "low": "부족",
            "normal": "양호",
            "high": "과다",
        }.get(result.mineral.status)
        result.nutrition_fat = {
            "low": "부족",
            "normal": "양호",
            "high": "과다",
        }.get(result.body_fat_mass.status)

        if result.bmi is not None:
            if result.bmi < 18.5:
                result.obesity_bmi = "저체중"
            elif result.bmi < 23:
                result.obesity_bmi = "표준"
            elif result.bmi < 25:
                result.obesity_bmi = "과체중"
            else:
                result.obesity_bmi = "비만"

        if result.percent_body_fat is not None and result.gender:
            pbf = result.percent_body_fat
            if result.gender == "남":
                if pbf < 10:
                    result.obesity_pbf = "부족"
                elif pbf <= 20:
                    result.obesity_pbf = "표준"
                elif pbf <= 25:
                    result.obesity_pbf = "경도비만"
                else:
                    result.obesity_pbf = "비만"
            else:
                if pbf < 18:
                    result.obesity_pbf = "부족"
                elif pbf <= 28:
                    result.obesity_pbf = "표준"
                elif pbf <= 33:
                    result.obesity_pbf = "경도비만"
                else:
                    result.obesity_pbf = "비만"

    return result


def render_sidebar_chrome() -> None:
    st.markdown(
        """
        <div class="srx-side-brand">SomaRx 2.0</div>
        <div class="srx-side-cap">MY BODY DASHBOARD</div>
        """,
        unsafe_allow_html=True,
    )


SRX_UPLOAD_KEY = "srx_result_upload"
SRX_PDF_UPLOAD_KEY = SRX_UPLOAD_KEY  # 하위 호환


def render_app_sidebar(*, show_disclaimer: bool = True) -> None:
    """사이드바 — 브랜드·테마·(선택) 안내. 업로드는 메인 드롭존."""
    with st.sidebar:
        render_sidebar_chrome()
        st.session_state.srx_dark = st.toggle(
            "다크 모드",
            value=st.session_state.srx_dark,
            help="라이트/다크 테마를 전환합니다.",
        )
        if show_disclaimer:
            st.markdown(
                '<p class="srx-side-note">분석은 기기에서 이루어지며, '
                "처방은 생활·운동·영양 가이드입니다. 의료 진단을 대체하지 않습니다.</p>",
                unsafe_allow_html=True,
            )


def render_pdf_upload_zone(*, compact: bool = False):
    """메인 영역 결과지 드롭존 (PDF · 사진)."""
    mode = "compact" if compact else "hero"
    if compact:
        st.markdown(
            f"""
            <div class="srx-reupload-row">
              <span class="srx-reupload-text">다른 결과지로 교체</span>
              <span class="srx-upload-marker {mode}"></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="srx-upload-zone">
              <div class="srx-upload-zone-inner">
                <div class="srx-upload-zone-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"
                       stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <path d="M14 2v6h6M12 18v-6M9 15l3 3 3-3"/>
                  </svg>
                </div>
                <div>
                  <p class="srx-upload-zone-title">InBody 결과지 업로드</p>
                  <p class="srx-upload-zone-sub">PDF 또는 종이 결과지 사진(JPG·PNG) — 모바일에서는 촬영도 가능합니다</p>
                </div>
              </div>
              <span class="srx-upload-marker {mode}"></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "촬영 팁: 결과지 전체가 보이게, 흔들림·그림자 없이, 밝은 곳에서 수직으로 찍어 주세요."
        )
    return st.file_uploader(
        "InBody 결과지",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
        key=SRX_UPLOAD_KEY,
        help="디지털 PDF, 스캔본, 종이 결과지 사진 모두 가능합니다.",
    )


def render_main_disclaimer() -> None:
    st.markdown(
        '<p class="srx-disclaimer">분석은 기기에서 이루어지며, '
        "처방은 생활·운동·영양 가이드입니다. 의료 진단을 대체하지 않습니다.</p>",
        unsafe_allow_html=True,
    )


def main() -> None:
    if "srx_dark" not in st.session_state:
        st.session_state.srx_dark = False

    _inject_css(dark_mode=st.session_state.srx_dark)

    ocr_ok, ocr_msg = check_ocr_ready()
    if not ocr_ok:
        render_app_sidebar(show_disclaimer=False)
        st.error(ocr_msg)
        st.info(
            "macOS: `brew install tesseract tesseract-lang`  \n"
            "Windows: [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) 설치 시 "
            "Korean / English 언어팩을 선택하고, 필요하면 `TESSERACT_CMD`에 "
            "`C:\\\\Program Files\\\\Tesseract-OCR\\\\tesseract.exe` 를 지정하세요."
        )
        render_landing()
        render_main_disclaimer()
        return

    render_app_sidebar(show_disclaimer=False)

    compact_upload = bool(st.session_state.get("srx_had_upload", False))
    uploaded = render_pdf_upload_zone(compact=compact_upload)

    if uploaded:
        st.session_state.srx_had_upload = True
    else:
        st.session_state.srx_had_upload = False
        render_landing()
        render_main_disclaimer()
        return

    try:
        with st.spinner("결과지를 읽고 처방을 구성 중입니다…"):
            cached = _analyze_upload(uploaded.getvalue(), uploaded.name or "")
            if is_image_filename(uploaded.name):
                st.info(
                    "사진으로 분석했습니다. 숫자가 어긋나면 사이드바 「지표 수동 보정」을 이용해 주세요."
                )
    except OcrNotAvailableError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"결과지를 읽지 못했습니다. PDF 또는 더 선명한 사진으로 다시 시도해 주세요. ({exc})")
        return

    # 캐시 객체를 직접 수정하지 않도록 복사본으로 보정·처방
    working = normalize_inbody_result(deepcopy(cached))
    working = manual_override_sidebar(working)
    report = build_prescription(working)
    bootstrap_user_progress(working, report, st.session_state)
    rx_ctx = _build_prescription_context(working, report, st.session_state)

    render_topbar()
    render_sticky_summary_bar(working, report, rx_ctx)
    render_patient_strip(working)

    st.markdown(
        '<p class="srx-persist-note">💾 미션·주간 플랜 진행률은 이 기기에 자동 저장됩니다.</p>',
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["처방", "지표", "원본"])

    with tab1:
        render_prescription(report, working, rx_ctx)

    with tab2:
        render_body_metrics(working)

    with tab3:
        st.markdown(
            '<p class="srx-original-note">OCR이 읽은 원본 이미지와 텍스트입니다. '
            "수치가 어긋나면 사이드바 「지표 수동 보정」에서 수정할 수 있습니다.</p>",
            unsafe_allow_html=True,
        )
        if working.preview_image_path:
            st.image(working.preview_image_path, width="stretch")
        with st.expander("OCR 원문 보기"):
            st.text(working.raw_text or "(텍스트 없음)")

    commit_user_progress(working, st.session_state)
    render_main_disclaimer()


if __name__ == "__main__":
    main()
