"""Phase 04 — 게이미피케이션 고도화 & 런칭 대시보드."""

from __future__ import annotations

import html
from dataclasses import dataclass

from missions import MissionProgress
from parser import InBodyResult
from persona import PersonaDashboard, PERSONAS
from prescription import PrescriptionReport
from slime_growth import SlimeGrowthReport
from trend import TrendReport

EVOLUTION_PROGRESS_THRESHOLD = 85.0
EVOLUTION_QUEST_RATIO = 0.8


@dataclass
class EvolutionState:
    ready: bool
    next_emoji: str
    next_name: str
    reward_message: str
    show_celebration: bool


@dataclass
class LaunchDashboard:
    version: str
    readiness_score: int
    headline: str
    subline: str
    modules: list[str]
    evolution: EvolutionState


def _next_persona_info(dashboard: PersonaDashboard) -> tuple[str, str]:
    persona = dashboard.persona
    if not persona.next_persona:
        return persona.emoji, persona.name
    nxt = PERSONAS.get(persona.next_persona, PERSONAS["?"])
    return nxt.emoji, nxt.name


def evaluate_evolution(
    growth: SlimeGrowthReport,
    mission_progress: MissionProgress,
    dashboard: PersonaDashboard,
) -> EvolutionState:
    if growth.is_max_stage:
        return EvolutionState(
            ready=False,
            next_emoji=growth.emoji,
            next_name=growth.name,
            reward_message="최종 진화 단계에 도달했습니다. 현재 루틴을 유지하세요!",
            show_celebration=False,
        )

    quests_done = growth.quests_done
    quest_total = max(growth.quests_total, 1)
    quest_ratio = quests_done / quest_total
    gold = mission_progress.has_gold_badge

    ready = growth.evolution_ready or (
        growth.progress_pct >= EVOLUTION_PROGRESS_THRESHOLD and gold
    ) or (
        growth.progress_pct >= 90
    ) or (
        quest_ratio >= EVOLUTION_QUEST_RATIO and growth.progress_pct >= 70
    )

    next_emoji, next_name = _next_persona_info(dashboard)

    if ready:
        reward = (
            f"진화 조건 달성! 다음 InBody 측정에서 {next_emoji} {next_name}(으)로 "
            f"업그레이드될 준비가 되었어요. 지금의 습관을 이어가세요!"
        )
    elif gold:
        reward = (
            "🏆 골드 미션 달성! 슬라임 성장률이 크게 올랐습니다. "
            f"진화까지 {max(0, EVOLUTION_PROGRESS_THRESHOLD - growth.progress_pct):.0f}%p 남았어요."
        )
    else:
        reward = (
            f"미션·주간 플랜을 채우면 {next_emoji} {next_name} 진화가 가까워집니다."
        )

    return EvolutionState(
        ready=ready,
        next_emoji=next_emoji,
        next_name=next_name,
        reward_message=reward,
        show_celebration=ready,
    )


def _readiness_score(
    result: InBodyResult,
    dashboard: PersonaDashboard,
    growth: SlimeGrowthReport,
    mission_progress: MissionProgress,
    trend: TrendReport | None,
) -> int:
    parts = [
        min(100, dashboard.composite_score),
        min(100, int(growth.progress_pct)),
        min(100, int(mission_progress.rate)),
    ]
    if trend and len(trend.points) >= 2:
        parts.append(85 if trend.weather.tone == "sunny" else 65)
    if result.phase_angle is not None:
        parts.append(75)
    return int(round(sum(parts) / len(parts)))


def build_launch_dashboard(
    result: InBodyResult,
    report: PrescriptionReport,
    dashboard: PersonaDashboard,
    growth: SlimeGrowthReport,
    mission_progress: MissionProgress,
    evolution: EvolutionState,
    trend: TrendReport | None = None,
) -> LaunchDashboard:
    readiness = _readiness_score(result, dashboard, growth, mission_progress, trend)

    modules = [
        "위상각 트렌드",
        "BMR 비교",
        "인체 히트맵",
        "처방 카드",
        "주간 플랜",
        "슬라임 성장",
    ]
    if trend and len(trend.points) >= 2:
        modules.insert(0, "신체 변화 트렌드")

    if evolution.ready:
        headline = f"🎉 진화 임박! {evolution.next_emoji} {evolution.next_name}를 향해"
        subline = f"런칭 준비도 {readiness}점 · 모든 핵심 모듈이 활성화되었습니다."
    elif mission_progress.has_gold_badge:
        headline = "🏆 골드 주간 달성 — SomaRx 2.0 풀 대시보드"
        subline = f"런칭 준비도 {readiness}점 · 꾸준한 실천이 데이터로 증명되고 있어요."
    else:
        headline = "SomaRx 2.0 · MY BODY DASHBOARD"
        subline = (
            f"런칭 준비도 {readiness}점 · 미션과 주간 플랜을 채우면 성장 속도가 빨라집니다."
        )

    return LaunchDashboard(
        version="2.0",
        readiness_score=readiness,
        headline=headline,
        subline=subline,
        modules=modules,
        evolution=evolution,
    )


def render_launch_banner_html(launch: LaunchDashboard) -> str:
    chips = "".join(
        f'<span class="srx-launch-chip">{html.escape(m)}</span>' for m in launch.modules
    )
    evolve_class = " evolution-ready" if launch.evolution.ready else ""
    gold_class = " gold-week" if "골드" in launch.headline else ""

    return (
        f'<div class="srx-launch-banner{evolve_class}{gold_class}">'
        f'<div class="srx-launch-top">'
        f'<span class="srx-launch-badge">SomaRx {html.escape(launch.version)}</span>'
        f'<span class="srx-launch-score">준비도 {launch.readiness_score}점</span>'
        f"</div>"
        f'<h2 class="srx-launch-headline">{html.escape(launch.headline)}</h2>'
        f'<p class="srx-launch-sub">{html.escape(launch.subline)}</p>'
        f'<div class="srx-launch-modules">{chips}</div>'
        f"</div>"
    )


def render_evolution_celebration_html(evolution: EvolutionState, growth: SlimeGrowthReport) -> str:
    if not evolution.show_celebration:
        return ""

    return (
        f'<div class="srx-evolution-celebration">'
        f'<div class="burst">✨</div>'
        f'<div class="from">{html.escape(growth.emoji)}</div>'
        f'<div class="arrow">→</div>'
        f'<div class="to">{html.escape(evolution.next_emoji)}</div>'
        f'<p class="msg">{html.escape(evolution.reward_message)}</p>'
        f"</div>"
    )


def render_rewards_strip_html(evolution: EvolutionState, mission_progress: MissionProgress) -> str:
    items: list[str] = []
    if mission_progress.has_gold_badge:
        items.append(
            '<div class="srx-reward gold">'
            "<strong>🏆 골드 뱃지</strong>"
            "<span>주간 미션 80%+ 달성</span></div>"
        )
    if evolution.ready:
        items.append(
            '<div class="srx-reward evolve">'
            f"<strong>{html.escape(evolution.next_emoji)} 진화 준비</strong>"
            "<span>다음 InBody에서 업그레이드</span></div>"
        )
    if not items:
        return ""

    return f'<div class="srx-rewards-strip">{"".join(items)}</div>'
