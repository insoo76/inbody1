"""슬라임 성장 게이미피케이션 — plan2 §3.5."""

from __future__ import annotations

import html
from dataclasses import dataclass

from missions import (
    MissionProgress,
    mission_checkbox_key,
    sync_mission_profile,
)
from parser import InBodyResult
from persona import PersonaDashboard
from phase_angle import build_phase_angle_report
from prescription import PrescriptionReport
from trend import TrendReport
from weekly_plan_ui import (
    build_weekly_plan_rows,
    collect_statuses,
    count_completed,
    sync_weekly_plan_profile,
)

PHASE_ANGLE_QUEST_TARGET = 0.1
STRENGTH_WEEKLY_TARGET = 2
GOLD_MISSION_RATE = 80


@dataclass
class SlimeQuest:
    text: str
    done: bool
    tag: str


@dataclass
class SlimeGrowthReport:
    emoji: str
    name: str
    next_label: str | None
    progress_pct: float
    quests: list[SlimeQuest]
    summary: str
    is_max_stage: bool
    evolution_ready: bool = False
    quests_done: int = 0
    quests_total: int = 0


def _strength_done_count(
    profile_key: str,
    session_state: dict,
    missions: list,
) -> int:
    strength = next((m for m in missions if m.id == "strength"), None)
    if not strength:
        return 0
    return sum(
        1
        for day_index in range(7)
        if session_state.get(mission_checkbox_key(strength.id, day_index, profile_key))
    )


def _compute_progress(
    composite_score: int,
    mission_rate: float,
    weekly_done: int,
    trend: TrendReport | None,
    is_max_stage: bool,
) -> float:
    weekly_rate = (weekly_done / 7) * 100
    base = composite_score * 0.35 + mission_rate * 0.4 + weekly_rate * 0.25
    if trend and trend.weather.tone == "sunny":
        base += 5
    if is_max_stage:
        return min(100.0, max(base, composite_score * 0.85))
    return min(99.0, max(8.0, base))


def _build_quests(
    result: InBodyResult,
    report: PrescriptionReport,
    mission_progress: MissionProgress,
    profile_key: str,
    session_state: dict,
    weekly_done: int,
    phase_delta: float | None,
) -> list[SlimeQuest]:
    quests: list[SlimeQuest] = []
    missions = mission_progress.missions
    is_c_shape = report.body_type.startswith("C")

    strength_done = _strength_done_count(profile_key, session_state, missions)
    if is_c_shape or any(m.id == "strength" for m in missions):
        need = max(0, STRENGTH_WEEKLY_TARGET - strength_done)
        quests.append(
            SlimeQuest(
                text=(
                    f"하체 근력 운동 {need}회 더 수행"
                    if need
                    else "하체 근력 운동 주간 목표 달성!"
                ),
                done=need == 0,
                tag="#운동",
            )
        )

    if result.phase_angle is not None:
        improved = phase_delta is not None and phase_delta >= PHASE_ANGLE_QUEST_TARGET
        quests.append(
            SlimeQuest(
                text=(
                    "위상각 0.1° 추가 개선"
                    if not improved
                    else "위상각 0.1°+ 개선 달성!"
                ),
                done=improved,
                tag="#대사",
            )
        )

    weekly_left = max(0, 7 - weekly_done)
    quests.append(
        SlimeQuest(
            text=(
                f"주간 플랜 {weekly_left}일 더 완료"
                if weekly_left
                else "주간 플랜 7/7 완료!"
            ),
            done=weekly_left == 0,
            tag="#루틴",
        )
    )

    gold_done = mission_progress.rate >= GOLD_MISSION_RATE
    quests.append(
        SlimeQuest(
            text=(
                f"데일리 미션 달성률 {GOLD_MISSION_RATE}% (현재 {mission_progress.rate:.0f}%)"
                if not gold_done
                else "골드 미션 뱃지 달성!"
            ),
            done=gold_done,
            tag="#미션",
        )
    )

    if result.protein.status == "low":
        quests.append(
            SlimeQuest(
                text="단백질 매끼 챙기기 (미션 체크)",
                done=any(
                    session_state.get(mission_checkbox_key("protein", d, profile_key))
                    for d in range(7)
                ),
                tag="#영양",
            )
        )

    return quests[:5]


def build_slime_growth_report(
    result: InBodyResult,
    report: PrescriptionReport,
    dashboard: PersonaDashboard,
    mission_progress: MissionProgress,
    session_state: dict,
    trend: TrendReport | None = None,
) -> SlimeGrowthReport:
    persona = dashboard.persona
    is_max_stage = persona.next_label is None

    profile_key = sync_mission_profile(result, session_state)
    sync_weekly_plan_profile(result, session_state)
    rows = build_weekly_plan_rows(report.weekly_plan)
    weekly_statuses = collect_statuses(rows, profile_key, session_state)
    weekly_done = count_completed(weekly_statuses)

    pa_report = build_phase_angle_report(result)
    phase_delta = pa_report.delta if pa_report else None

    progress_pct = _compute_progress(
        dashboard.composite_score,
        mission_progress.rate,
        weekly_done,
        trend,
        is_max_stage,
    )

    quests = _build_quests(
        result,
        report,
        mission_progress,
        profile_key,
        session_state,
        weekly_done,
        phase_delta,
    )
    done_count = sum(1 for q in quests if q.done)
    evolution_ready = (
        not is_max_stage
        and progress_pct >= 85
        and mission_progress.has_gold_badge
    ) or (
        not is_max_stage and done_count == len(quests) and len(quests) > 0
    )

    if evolution_ready:
        summary = (
            f"🎉 진화 조건 달성! {persona.next_label}(으)로 업그레이드 준비 완료. "
            f"퀘스트 {done_count}/{len(quests)}개 달성 중!"
        )
    elif is_max_stage:
        summary = (
            f"{persona.name} 최종 단계! 퀘스트 {done_count}/{len(quests)}개 달성 중. "
            "탄탄한 루틴을 유지하며 수치를 지켜보세요."
        )
    elif progress_pct >= 75:
        summary = (
            f"다음 진화 {persona.next_label}까지 {progress_pct:.0f}%! "
            f"퀘스트 {done_count}/{len(quests)}개 완료 — 거의 다 왔어요!"
        )
    else:
        summary = (
            f"{persona.name} 성장 중 · 다음 진화까지 {progress_pct:.0f}%. "
            "아래 퀘스트를 하나씩 완료해 보세요."
        )

    return SlimeGrowthReport(
        emoji=persona.emoji,
        name=persona.name,
        next_label=persona.next_label,
        progress_pct=round(progress_pct, 1),
        quests=quests,
        summary=summary,
        is_max_stage=is_max_stage,
        evolution_ready=evolution_ready,
        quests_done=done_count,
        quests_total=len(quests),
    )


def render_slime_growth_html(growth: SlimeGrowthReport) -> str:
    root_class = "srx-slime-growth"
    if growth.evolution_ready:
        root_class += " evolution-ready"

    next_line = ""
    if growth.next_label and not growth.is_max_stage:
        next_line = (
            f'<div class="srx-slime-next">다음 진화: {html.escape(growth.next_label)}</div>'
        )
    elif growth.is_max_stage:
        next_line = '<div class="srx-slime-next max">✨ 최종 진화 단계</div>'

    fill = min(100, max(0, growth.progress_pct))
    quest_items = []
    for quest in growth.quests:
        state = "done" if quest.done else "todo"
        mark = "✓" if quest.done else "○"
        quest_items.append(
            f'<li class="srx-slime-quest {state}">'
            f'<span class="mark">{mark}</span>'
            f'<span class="tag">{html.escape(quest.tag)}</span>'
            f'<span class="text">{html.escape(quest.text)}</span>'
            f"</li>"
        )

    return (
        f'<div class="{root_class}">'
        f'<div class="srx-slime-head">'
        f'<div class="srx-slime-char">'
        f'<span class="emoji">{growth.emoji}</span>'
        f'<div>'
        f'<h3 class="name">{html.escape(growth.name)} 성장</h3>'
        f"{next_line}"
        f"</div></div>"
        f'<div class="srx-slime-pct">{fill:.0f}<span>%</span></div>'
        f"</div>"
        f'<div class="srx-slime-bar" role="progressbar" aria-valuenow="{fill:.0f}" '
        f'aria-valuemin="0" aria-valuemax="100">'
        f'<div class="srx-slime-bar-fill" style="width:{fill:.1f}%;"></div>'
        f"</div>"
        f'<p class="srx-slime-summary">{html.escape(growth.summary)}</p>'
        f'<div class="srx-slime-quests-label">'
        f'성장 퀘스트 ({growth.quests_done}/{growth.quests_total})</div>'
        f'<ul class="srx-slime-quests">{"".join(quest_items)}</ul>'
        f"</div>"
    )
