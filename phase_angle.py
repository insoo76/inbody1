"""위상각(Phase Angle) 트렌드 시각화 — plan2 §3.1."""

from __future__ import annotations

import re
from dataclasses import dataclass

import plotly.graph_objects as go

from chart_theme import FONT, MINT, chart_layout, get_palette

from parser import InBodyResult

MAX_POINTS = 5
IMPROVE_THRESHOLD = 0.05
REFERENCE_LOW = 5.5
REFERENCE_HIGH = 7.0


@dataclass
class PhaseAnglePoint:
    date: str
    value: float


@dataclass
class PhaseAngleReport:
    points: list[PhaseAnglePoint]
    current: float | None
    delta: float | None
    trend: str
    comment: str
    has_history: bool


def _short_date(label: str) -> str:
    m = re.search(r"(20\d{2})\.(\d{1,2})\.(\d{1,2})", label)
    if m:
        return f"{m.group(2).lstrip('0') or '0'}/{m.group(3).lstrip('0') or '0'}"
    return label[:8]


def _tail(values: list[float], length: int) -> list[float]:
    if len(values) >= length:
        return values[-length:]
    return values


def _tail_dates(values: list[str], length: int) -> list[str]:
    if not values:
        return [f"측정 {i + 1}" for i in range(length)]
    if len(values) >= length:
        return values[-length:]
    pad = [f"측정 {i + 1}" for i in range(length - len(values))]
    return pad + values


def build_phase_angle_points(result: InBodyResult, max_points: int = MAX_POINTS) -> list[PhaseAnglePoint]:
    values = list(getattr(result, "phase_angle_history", None) or [])
    dates = list(getattr(result, "history_dates", None) or [])

    if not values and result.phase_angle is not None:
        values = [result.phase_angle]
    if not dates and result.test_datetime:
        dates = [result.test_datetime]

    if not values:
        return []

    n = min(len(values), max_points)
    values = _tail(values, n)
    dates = _tail_dates(dates, n)

    return [PhaseAnglePoint(date=dates[i], value=values[i]) for i in range(n)]


def _classify_trend(delta: float | None) -> str:
    if delta is None:
        return "unknown"
    if delta > IMPROVE_THRESHOLD:
        return "up"
    if delta < -IMPROVE_THRESHOLD:
        return "down"
    return "flat"


def _generate_comment(points: list[PhaseAnglePoint], delta: float | None, trend: str) -> str:
    if not points:
        return "위상각 데이터가 없습니다. InBody 연구항목 결과지를 업로드하면 추이를 확인할 수 있어요."

    current = points[-1].value
    if len(points) < 2:
        return (
            f"현재 위상각 **{current:.1f}°** 입니다. "
            "다음 검사부터 시간에 따른 개선 추이를 선 그래프로 확인할 수 있어요. "
            "규칙적인 근력 운동과 단백질 섭취가 세포 건강·위상각 개선에 도움이 됩니다."
        )

    if trend == "up" and delta is not None:
        return (
            f"위상각이 **+{delta:.1f}°** 개선되어 현재 **{current:.1f}°** 입니다. "
            "세포 건강과 영양 상태가 좋아지고 있어요. 지금의 노력이 데이터로 증명되고 있습니다!"
        )
    if trend == "down" and delta is not None:
        return (
            f"위상각이 {delta:.1f}° 낮아져 현재 **{current:.1f}°** 입니다. "
            "수면·단백질·근력 운동 루틴을 점검하고, 급격한 체중 감량이나 탈수는 피해 주세요."
        )
    return (
        f"위상각 **{current:.1f}°** 로 안정적으로 유지되고 있습니다. "
        "현재 습관을 이어가면 다음 검사에서 더 나은 변화를 기대할 수 있어요."
    )


def build_phase_angle_report(result: InBodyResult) -> PhaseAngleReport | None:
    points = build_phase_angle_points(result)
    if not points:
        return None

    current = points[-1].value
    delta = None
    if len(points) >= 2:
        delta = points[-1].value - points[-2].value

    trend = _classify_trend(delta)
    comment = _generate_comment(points, delta, trend)
    return PhaseAngleReport(
        points=points,
        current=current,
        delta=delta,
        trend=trend,
        comment=comment,
        has_history=len(points) >= 2,
    )


def _chart_layout(**kwargs) -> dict:
    return chart_layout(**kwargs)


def make_phase_angle_chart(points: list[PhaseAnglePoint], delta: float | None = None) -> go.Figure:
    pal = get_palette()
    labels = [_short_date(p.date) for p in points]
    values = [p.value for p in points]

    fig = go.Figure()

    y_min = min(min(values), REFERENCE_LOW) - 0.4
    y_max = max(max(values), REFERENCE_HIGH) + 0.4

    fig.add_hrect(
        y0=REFERENCE_LOW,
        y1=REFERENCE_HIGH,
        fillcolor="rgba(16, 185, 129, 0.08)",
        line_width=0,
        annotation_text="양호 구간",
        annotation_position="top left",
        annotation=dict(font=dict(size=9, color=MINT), showarrow=False),
    )

    fig.add_trace(
        go.Scatter(
            x=labels,
            y=values,
            mode="lines+markers",
            line=dict(color=MINT, width=3, shape="spline"),
            marker=dict(
                size=[7] * (len(values) - 1) + [10],
                color=MINT,
                line=dict(width=2, color=pal.marker_line),
            ),
            fill="tozeroy",
            fillcolor="rgba(16, 185, 129, 0.12)",
            hovertemplate="%{x}<br>위상각: %{y:.1f}°<extra></extra>",
            showlegend=False,
        )
    )

    if len(values) >= 2 and delta is not None:
        sign = "+" if delta > 0 else ""
        accent = MINT if delta > 0 else "#EA580C"
        fig.add_annotation(
            x=labels[-1],
            y=values[-1],
            text=f"{sign}{delta:.1f}°",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.8,
            arrowwidth=1.5,
            arrowcolor=accent,
            ax=28,
            ay=-28 if delta >= 0 else 28,
            font=dict(size=11, color=pal.ink, family=FONT),
            bgcolor=pal.annotation_bg,
            bordercolor=accent,
            borderwidth=1,
        )

    fig.update_layout(
        **_chart_layout(
            height=240,
            yaxis=dict(
                showgrid=True,
                gridcolor=pal.grid,
                tickfont=dict(size=10, color=pal.muted),
                ticksuffix="°",
                range=[y_min, y_max],
            ),
        )
    )
    return fig


def format_delta_badge(delta: float | None, trend: str) -> tuple[str, str]:
    """(badge_text, css_class)"""
    if delta is None or trend == "unknown":
        return "추이 데이터 수집 중", "neutral"
    sign = "+" if delta > 0 else ""
    if trend == "up":
        return f"전월 대비 {sign}{delta:.1f}° ↑", "improved"
    if trend == "down":
        return f"전월 대비 {delta:.1f}° ↓", "declined"
    return f"전월 대비 {sign}{delta:.1f}° · 유지", "neutral"
