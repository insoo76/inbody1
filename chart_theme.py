"""Plotly 차트 공통 테마 — 라이트/다크, SomaRx 브랜드 컬러."""

from __future__ import annotations

from dataclasses import dataclass

FONT = "Pretendard, Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif"

MINT = "#10B981"
BLUE = "#3B82F6"


@dataclass(frozen=True)
class ChartPalette:
    ink: str
    muted: str
    grid: str
    title: str
    marker_line: str
    annotation_bg: str
    gauge_bg: str
    gauge_axis: str
    polar_grid: str
    reference_line: str
    ideal_line: str
    ideal_fill: str


LIGHT_PALETTE = ChartPalette(
    ink="#0F172A",
    muted="#64748B",
    grid="#E2E8F0",
    title="#0F172A",
    marker_line="#FFFFFF",
    annotation_bg="rgba(255,255,255,0.92)",
    gauge_bg="rgba(255,255,255,0.4)",
    gauge_axis="#94A3B8",
    polar_grid="rgba(15,23,42,0.10)",
    reference_line="#94A3B8",
    ideal_line="rgba(120, 130, 128, 0.85)",
    ideal_fill="rgba(160, 170, 168, 0.18)",
)

DARK_PALETTE = ChartPalette(
    ink="#F1F5F9",
    muted="#94A3B8",
    grid="#334155",
    title="#F1F5F9",
    marker_line="#1E293B",
    annotation_bg="rgba(30, 41, 59, 0.94)",
    gauge_bg="rgba(15, 23, 42, 0.55)",
    gauge_axis="#64748B",
    polar_grid="rgba(148, 163, 184, 0.18)",
    reference_line="#64748B",
    ideal_line="rgba(148, 163, 184, 0.75)",
    ideal_fill="rgba(148, 163, 184, 0.12)",
)


def is_dark_mode() -> bool:
    """Streamlit 다크 모드 토글 상태 (테스트·CLI에서는 False)."""
    try:
        import streamlit as st

        return bool(st.session_state.get("srx_dark", False))
    except Exception:
        return False


def get_palette(dark: bool | None = None) -> ChartPalette:
    if dark is None:
        dark = is_dark_mode()
    return DARK_PALETTE if dark else LIGHT_PALETTE


def title_style(text: str, *, size: int = 14, dark: bool | None = None) -> dict:
    pal = get_palette(dark)
    return dict(text=text, font=dict(size=size, color=pal.title))


def axis_defaults(*, ticksuffix: str = "", dark: bool | None = None) -> dict:
    pal = get_palette(dark)
    yaxis = dict(
        showgrid=True,
        gridcolor=pal.grid,
        gridwidth=1,
        zeroline=False,
        linecolor=pal.grid,
        tickfont=dict(color=pal.muted, size=10),
        title=dict(font=dict(color=pal.muted, size=11)),
    )
    if ticksuffix:
        yaxis["ticksuffix"] = ticksuffix
    return {
        "xaxis": dict(
            showgrid=False,
            zeroline=False,
            linecolor=pal.grid,
            tickfont=dict(color=pal.muted, size=10),
            title=dict(font=dict(color=pal.muted, size=11)),
        ),
        "yaxis": yaxis,
    }


def _normalize_title(kwargs: dict, pal: ChartPalette) -> None:
    title = kwargs.get("title")
    if isinstance(title, str):
        kwargs["title"] = dict(text=title, font=dict(size=12, color=pal.title))
    elif isinstance(title, dict):
        font = dict(title.get("font") or {})
        font.setdefault("color", pal.title)
        kwargs["title"] = {**title, "font": font}


def chart_layout(**kwargs) -> dict:
    """SomaRx 표준 Plotly layout. `dark=True/False`로 강제 가능."""
    dark = kwargs.pop("dark", None)
    pal = get_palette(dark)
    _normalize_title(kwargs, pal)

    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=pal.ink, size=11),
        margin=dict(l=36, r=16, t=12, b=32),
        **axis_defaults(dark=dark),
    )
    base.update(kwargs)
    return base


def gauge_layout(**kwargs) -> dict:
    """게이지(스피도미터) 전용 layout."""
    dark = kwargs.pop("dark", None)
    pal = get_palette(dark)
    _normalize_title(kwargs, pal)

    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=pal.ink, size=12),
        margin=dict(l=24, r=24, t=42, b=8),
    )
    base.update(kwargs)
    return base


def gauge_indicator_style(*, dark: bool | None = None) -> dict:
    """스피도미터 number/title/gauge axis 색."""
    pal = get_palette(dark)
    return {
        "number": {"suffix": "점", "font": {"size": 28, "color": pal.ink}},
        "title_font": {"size": 13, "color": pal.muted},
        "gauge_axis": {"tickwidth": 1, "tickcolor": pal.gauge_axis},
        "gauge_bgcolor": pal.gauge_bg,
    }
