"""주간 플랜 테이블 UI — plan2 §3.4."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime

from parser import InBodyResult

DAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]
DAY_LABELS = {
    "월": "월요일",
    "화": "화요일",
    "수": "수요일",
    "목": "목요일",
    "금": "금요일",
    "토": "토요일",
    "일": "일요일",
}


@dataclass
class WeeklyPlanRow:
    day_short: str
    day_label: str
    exercise: str
    nutrition: str
    day_index: int


@dataclass
class PlanStatus:
    label: str
    css_class: str
    emoji: str


from profile_keys import build_profile_key


def _profile_key(result: InBodyResult) -> str:
    return build_profile_key(result)


def weekly_plan_done_key(day_index: int, profile_key: str) -> str:
    return f"wplan_done_{profile_key}_{day_index}"


def sync_weekly_plan_profile(result: InBodyResult, session_state: dict) -> str:
    """측정 프로필 동기화 — 로컬 저장소에서 진행률 복원."""
    from progress_store import ensure_profile_session

    return ensure_profile_session(result, session_state)


def build_weekly_plan_rows(weekly_plan: dict[str, list[str]]) -> list[WeeklyPlanRow]:
    rows: list[WeeklyPlanRow] = []
    for index, day in enumerate(DAY_ORDER):
        items = weekly_plan.get(day, [])
        exercise = items[0] if items else "—"
        nutrition = " · ".join(items[1:]) if len(items) > 1 else "—"
        rows.append(
            WeeklyPlanRow(
                day_short=day,
                day_label=DAY_LABELS.get(day, day),
                exercise=exercise,
                nutrition=nutrition,
                day_index=index,
            )
        )
    return rows


def classify_status(day_index: int, checked: bool, today_index: int | None = None) -> PlanStatus:
    if checked:
        return PlanStatus("완료", "done", "🟢")
    if today_index is None:
        today_index = datetime.now().weekday()
    if day_index == today_index:
        return PlanStatus("진행중", "active", "🔵")
    return PlanStatus("대기", "pending", "⚪️")


def collect_statuses(
    rows: list[WeeklyPlanRow],
    profile_key: str,
    session_state: dict,
    today_index: int | None = None,
) -> list[PlanStatus]:
    return [
        classify_status(
            row.day_index,
            bool(session_state.get(weekly_plan_done_key(row.day_index, profile_key), False)),
            today_index,
        )
        for row in rows
    ]


def count_completed(statuses: list[PlanStatus]) -> int:
    return sum(1 for s in statuses if s.css_class == "done")


def render_weekly_plan_table(
    rows: list[WeeklyPlanRow],
    statuses: list[PlanStatus],
) -> str:
    completed = count_completed(statuses)
    total = len(rows)

    body_rows: list[str] = []
    for row, status in zip(rows, statuses):
        body_rows.append(
            f'<tr class="srx-wplan-row {status.css_class}">'
            f'<td class="day"><strong>{html.escape(row.day_label)}</strong></td>'
            f'<td class="exercise">{html.escape(row.exercise)}</td>'
            f'<td class="nutrition">{html.escape(row.nutrition)}</td>'
            f'<td class="status">'
            f'<span class="srx-wplan-badge {status.css_class}">'
            f"{html.escape(status.label)} {status.emoji}</span></td>"
            f"</tr>"
        )

    return (
        f'<div class="srx-wplan">'
        f'<div class="srx-wplan-head">'
        f'<p class="srx-wplan-sub">요일별 운동·영양 가이드와 진행 상태를 한눈에 확인하세요.</p>'
        f'<div class="srx-wplan-progress">'
        f'<span class="k">이번 주 진행</span>'
        f'<span class="v">{completed}/{total}일 완료</span>'
        f"</div></div>"
        f'<div class="srx-wplan-scroll">'
        f'<table class="srx-wplan-table" role="table">'
        f"<thead><tr>"
        f"<th>요일</th><th>핵심 운동 플랜</th><th>영양 및 활동 가이드</th><th>상태</th>"
        f"</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody>'
        f"</table></div></div>"
    )
