"""계기판형 게이지 & 체형 페르소나 캐릭터."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

import plotly.graph_objects as go

from chart_theme import gauge_indicator_style, gauge_layout
from parser import InBodyResult, RangeValue
from prescription import PrescriptionReport
from trend import TrendReport, build_trend_report


@dataclass
class PersonaProfile:
    key: str
    emoji: str
    name: str
    tagline: str
    next_persona: str | None
    next_label: str | None


@dataclass
class PersonaDashboard:
    growth_score: int | None
    composite_score: int
    growth_label: str
    composite_label: str
    persona: PersonaProfile
    evolution_hint: str
    animate_evolution: bool
    has_growth: bool


PERSONAS: dict[str, PersonaProfile] = {
    "C": PersonaProfile(
        key="C",
        emoji="🌱",
        name="새싹 슬라임",
        tagline="말랑말랑하지만 성장 가능성이 큰 타입이에요. 근력·단백질 보충이 핵심!",
        next_persona="I",
        next_label="🐼 대나무 대리",
    ),
    "I": PersonaProfile(
        key="I",
        emoji="🐼",
        name="대나무 대리",
        tagline="묵묵히 균형을 지키는 타입이에요. 작은 습관으로 더 단단해질 수 있어요.",
        next_persona="D",
        next_label="🐯 아기 호랑이",
    ),
    "D": PersonaProfile(
        key="D",
        emoji="🐯",
        name="아기 호랑이",
        tagline="탄탄한 근육과 에너지가 돋보이는 타입! 현재 루틴을 유지하세요.",
        next_persona=None,
        next_label=None,
    ),
    "?": PersonaProfile(
        key="?",
        emoji="✨",
        name="성장형 탐험가",
        tagline="측정 데이터를 바탕으로 나만의 체형 캐릭터를 키워보세요.",
        next_persona="I",
        next_label="🐼 대나무 대리",
    ),
}


def _body_type_key(body_type: str) -> str:
    if body_type.startswith("C"):
        return "C"
    if body_type.startswith("D"):
        return "D"
    if body_type.startswith("I"):
        return "I"
    return "?"


def _range_score(rv: RangeValue) -> float | None:
    if rv.value is None or rv.low is None or rv.high is None or rv.high == rv.low:
        return None
    mid = (rv.low + rv.high) / 2
    span = (rv.high - rv.low) / 2
    if not span:
        return 85.0
    normalized = 100 - abs(rv.value - mid) / span * 18
    return max(35.0, min(100.0, normalized))


def compute_composite_score(result: InBodyResult) -> int:
    scores: list[float] = []
    for rv in (
        result.body_water,
        result.protein,
        result.mineral,
        result.body_fat_mass,
        result.weight,
    ):
        value = _range_score(rv)
        if value is not None:
            scores.append(value)

    if result.percent_body_fat is not None:
        target = 28.0 if result.gender == "여" else 20.0
        pbf_score = 100 - abs(result.percent_body_fat - target) * 2.2
        scores.append(max(35.0, min(100.0, pbf_score)))

    if result.skeletal_muscle_mass and result.weight.value:
        ratio = result.skeletal_muscle_mass / result.weight.value
        target = 0.38 if result.gender == "여" else 0.44
        smm_score = 100 - abs(ratio - target) * 180
        scores.append(max(35.0, min(100.0, smm_score)))

    if not scores:
        return 70
    return int(round(sum(scores) / len(scores)))


def _score_zone(score: int) -> str:
    if score <= 60:
        return "위험"
    if score <= 80:
        return "주의"
    return "양호"


def _evolution_hint(
    persona: PersonaProfile,
    trend: TrendReport | None,
    body_type: str,
) -> tuple[str, bool]:
    if persona.next_label is None:
        return "최종 진화 단계에 가까워요. 지금의 관리 루틴을 이어가세요!", False

    improving = False
    if trend and len(trend.points) >= 2:
        improving = trend.weather.tone == "sunny"

    if improving:
        return (
            f"좋은 흐름이에요! 꾸준히 실천하면 {persona.next_label}(으)로 진화할 수 있어요.",
            True,
        )
    return f"다음 목표 캐릭터: {persona.next_label}. 미션 트래커를 채워보세요!", False


def build_persona_dashboard(
    result: InBodyResult,
    report: PrescriptionReport,
    trend: TrendReport | None = None,
    *,
    body_evolution: object | None = None,
) -> PersonaDashboard:
    if trend is None:
        trend = build_trend_report(result)

    persona = PERSONAS[_body_type_key(report.body_type)]
    composite = compute_composite_score(result)
    growth = result.growth_score
    hint, animate = _evolution_hint(persona, trend, report.body_type)

    if body_evolution is not None:
        animate = True
        message = getattr(body_evolution, "message", None)
        if message:
            hint = str(message)

    return PersonaDashboard(
        growth_score=growth,
        composite_score=composite,
        growth_label="성장 점수" if growth is not None else "성장 점수 (미측정)",
        composite_label="종합 웰니스 점수",
        persona=persona,
        evolution_hint=hint,
        animate_evolution=animate,
        has_growth=growth is not None,
    )


def _chart_layout(**kwargs) -> dict:
    return gauge_layout(**kwargs)


def make_speedometer(score: int, title: str) -> go.Figure:
    zone = _score_zone(score)
    bar_color = "#B43B2A" if zone == "위험" else "#B86A1C" if zone == "주의" else "#1F7A4D"
    gauge_style = gauge_indicator_style()

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number=gauge_style["number"],
            title={"text": title, "font": gauge_style["title_font"]},
            gauge={
                "shape": "angular",
                "axis": {"range": [0, 100], **gauge_style["gauge_axis"]},
                "bar": {"color": bar_color, "thickness": 0.22},
                "bgcolor": gauge_style["gauge_bgcolor"],
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 60], "color": "rgba(180,59,42,0.22)"},
                    {"range": [60, 80], "color": "rgba(184,106,28,0.20)"},
                    {"range": [80, 100], "color": "rgba(31,122,77,0.22)"},
                ],
            },
        )
    )
    fig.update_layout(**_chart_layout(height=220))
    return fig


def render_persona_card_html(
    dashboard: PersonaDashboard,
    body_type: str,
    *,
    evolution_ready: bool = False,
) -> str:
    persona = dashboard.persona
    evolve_class = " evolving"
    if evolution_ready:
        evolve_class = " evolving evolution-burst"
    elif not dashboard.animate_evolution:
        evolve_class = ""
    body_type_short = re.sub(r"\s*\(.*\)", "", body_type)

    return (
        f'<div class="srx-persona-card{evolve_class}">'
        f'<div class="srx-persona-emoji">{persona.emoji}</div>'
        f'<div class="srx-persona-name">{html.escape(persona.name)}</div>'
        f'<div class="srx-persona-type">{html.escape(body_type_short)}</div>'
        f'<p class="srx-persona-tagline">{html.escape(persona.tagline)}</p>'
        f'<div class="srx-persona-evo">{html.escape(dashboard.evolution_hint)}</div>'
        f"</div>"
    )
