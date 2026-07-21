"""누적 트렌드 시각화 — 체중·골격근량·체지방률 변화 분석."""

from __future__ import annotations

import re
from dataclasses import dataclass

import plotly.graph_objects as go

from chart_theme import chart_layout, get_palette, title_style
from parser import InBodyResult

MAX_POINTS = 5
SMM_MAINTAIN = 0.2
PBF_MAINTAIN = 0.5


@dataclass
class TrendPoint:
    date: str
    weight: float | None = None
    smm: float | None = None
    pbf: float | None = None


@dataclass
class HealthWeather:
    emoji: str
    label: str
    tone: str


@dataclass
class TrendReport:
    points: list[TrendPoint]
    weather: HealthWeather
    comment: str
    smm_delta: float | None
    pbf_delta: float | None
    weight_delta: float | None


def _tail(values: list[float], length: int) -> list[float | None]:
    if not values:
        return [None] * length
    if len(values) >= length:
        return values[-length:]
    return [None] * (length - len(values)) + values


def _tail_dates(values: list[str], length: int) -> list[str]:
    if not values:
        return [f"측정 {i + 1}" for i in range(length)]
    if len(values) >= length:
        return values[-length:]
    pad = [f"측정 {i + 1}" for i in range(length - len(values))]
    return pad + values


def _short_date(label: str) -> str:
    m = re.search(r"(20\d{2})\.(\d{1,2})\.(\d{1,2})", label)
    if m:
        return f"{m.group(2).lstrip('0') or '0'}/{m.group(3).lstrip('0') or '0'}"
    return label[:8]


def build_trend_points(result: InBodyResult, max_points: int = MAX_POINTS) -> list[TrendPoint]:
    weights = list(result.weight_history)
    smms = list(result.smm_history)
    pbfs = list(result.pbf_history)
    dates = list(result.history_dates)

    if not weights and result.weight.value is not None:
        weights = [result.weight.value]
    if not smms and result.skeletal_muscle_mass is not None:
        smms = [result.skeletal_muscle_mass]
    if not pbfs and result.percent_body_fat is not None:
        pbfs = [result.percent_body_fat]
    if not dates and result.test_datetime:
        dates = [result.test_datetime]

    n = min(max(len(weights), len(smms), len(pbfs)), max_points)
    if n == 0:
        return []

    weights = _tail(weights, n)
    smms = _tail(smms, n)
    pbfs = _tail(pbfs, n)
    dates = _tail_dates(dates, n)

    return [
        TrendPoint(date=dates[i], weight=weights[i], smm=smms[i], pbf=pbfs[i])
        for i in range(n)
    ]


def _delta(prev: float | None, curr: float | None) -> float | None:
    if prev is None or curr is None:
        return None
    return curr - prev


def classify_weather(smm_delta: float | None, pbf_delta: float | None) -> HealthWeather:
    if smm_delta is None or pbf_delta is None:
        return HealthWeather("⛅", "구름 조금", "cloudy")

    smm_up = smm_delta > SMM_MAINTAIN
    smm_down = smm_delta < -SMM_MAINTAIN
    smm_maintain = not smm_up and not smm_down

    pbf_down = pbf_delta < -PBF_MAINTAIN
    pbf_up = pbf_delta > PBF_MAINTAIN
    pbf_maintain = not pbf_up and not pbf_down

    if smm_up and pbf_down:
        return HealthWeather("☀️", "맑음", "sunny")
    if smm_down and pbf_up:
        return HealthWeather("☔", "비", "rainy")
    if smm_maintain and pbf_maintain:
        return HealthWeather("⛅", "구름 조금", "cloudy")
    if smm_up and not pbf_up:
        return HealthWeather("☀️", "맑음", "sunny")
    if pbf_up:
        return HealthWeather("☔", "비", "rainy")
    return HealthWeather("⛅", "구름 조금", "cloudy")


def generate_trend_comment(
    points: list[TrendPoint],
    weather: HealthWeather,
    smm_delta: float | None,
    pbf_delta: float | None,
    weight_delta: float | None,
) -> str:
    if len(points) < 2:
        return (
            "측정 기록이 아직 1회입니다. "
            "다음 검사 때부터 변화 추이와 건강 날씨를 확인할 수 있어요."
        )

    parts: list[str] = []
    if smm_delta is not None:
        if smm_delta > SMM_MAINTAIN:
            parts.append(f"골격근량이 **+{smm_delta:.1f}kg** 늘었어요")
        elif smm_delta < -SMM_MAINTAIN:
            parts.append(f"골격근량이 {smm_delta:.1f}kg 줄었어요")
        else:
            parts.append("골격근량은 안정적으로 유지되고 있어요")

    if pbf_delta is not None:
        if pbf_delta < -PBF_MAINTAIN:
            parts.append(f"체지방률이 **{pbf_delta:.1f}%p** 낮아졌어요")
        elif pbf_delta > PBF_MAINTAIN:
            parts.append(f"체지방률이 +{pbf_delta:.1f}%p 올랐어요")
        else:
            parts.append("체지방률도 크게 변하지 않았어요")

    if weight_delta is not None and abs(weight_delta) >= 0.3:
        sign = "+" if weight_delta > 0 else ""
        parts.append(f"체중은 {sign}{weight_delta:.1f}kg 변화했어요")

    body = ". ".join(parts) + "." if parts else "최근 측정값을 기준으로 변화를 추적 중입니다."

    if weather.tone == "sunny":
        tail = " 근육은 늘고 체지방은 빠지는 이상적인 변화입니다. 훌륭해요!"
    elif weather.tone == "rainy":
        tail = " 근육 감소와 체지방 증가 신호가 보입니다. 처방 가이드를 꾸준히 실천해 보세요."
    else:
        tail = " 현재는 유지 구간입니다. 작은 습관을 이어가면 다음 검사에서 변화가 보일 거예요."

    return body + tail


def build_trend_report(result: InBodyResult) -> TrendReport | None:
    points = build_trend_points(result)
    if not points:
        return None

    smm_delta = pbf_delta = weight_delta = None
    if len(points) >= 2:
        prev, curr = points[-2], points[-1]
        smm_delta = _delta(prev.smm, curr.smm)
        pbf_delta = _delta(prev.pbf, curr.pbf)
        weight_delta = _delta(prev.weight, curr.weight)

    weather = classify_weather(smm_delta, pbf_delta)
    comment = generate_trend_comment(points, weather, smm_delta, pbf_delta, weight_delta)
    return TrendReport(
        points=points,
        weather=weather,
        comment=comment,
        smm_delta=smm_delta,
        pbf_delta=pbf_delta,
        weight_delta=weight_delta,
    )


def _chart_layout(**kwargs) -> dict:
    return chart_layout(**kwargs)


def make_trend_chart(
    points: list[TrendPoint],
    field: str,
    color: str,
    unit: str,
    title: str,
) -> go.Figure:
    pal = get_palette()
    labels = [_short_date(p.date) for p in points]
    values = [getattr(p, field) for p in points]
    clean = [(label, val) for label, val in zip(labels, values) if val is not None]

    fig = go.Figure()
    if len(clean) < 1:
        fig.update_layout(**_chart_layout(height=180, title=title_style(title, size=12)))
        return fig

    x_vals = [c[0] for c in clean]
    y_vals = [c[1] for c in clean]

    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="lines+markers",
            line=dict(color=color, width=2.5, shape="spline"),
            marker=dict(size=7, color=color, line=dict(width=1.5, color=pal.marker_line)),
            hovertemplate=f"%{{x}}<br>{title}: %{{y:.1f}}{unit}<extra></extra>",
            showlegend=False,
        )
    )
    fig.update_layout(
        **_chart_layout(
            height=180,
            title=title_style(title, size=12),
            xaxis=dict(showgrid=False, tickfont=dict(size=10, color=pal.muted)),
            yaxis=dict(showgrid=True, gridcolor=pal.grid, tickfont=dict(size=10, color=pal.muted)),
        )
    )
    return fig


def format_delta_text(delta: float | None, unit: str, positive_good: bool | None = None) -> str:
    if delta is None:
        return "—"
    sign = "+" if delta > 0 else ""
    text = f"{sign}{delta:.1f}{unit}"
    if positive_good is True and delta > 0:
        return f"+{delta:.1f}{unit}"
    if positive_good is False and delta < 0:
        return f"{delta:.1f}{unit}"
    return text
