"""식단 플랜 리포트 — plan3.md Phase 01~02."""

from __future__ import annotations

import html
from dataclasses import dataclass, field

from parser import InBodyResult
from prescription import (
    PrescriptionReport,
    _calories,
    _protein_target_g,
    _water_target_ml,
)


@dataclass
class MealSlot:
    key: str  # breakfast | lunch | dinner | snack
    title: str
    items: list[str]
    tip: str


@dataclass
class MealInsight:
    topic: str
    reason: str
    action: str
    severity: str  # high | mid | tip


@dataclass
class WeeklyMealHint:
    day_short: str
    day_label: str
    exercise: str
    hint: str
    focus: str  # protein | water | mineral | balance | recovery | prep


@dataclass
class MealPlanReport:
    calories: int
    protein_g: tuple[int, int]
    water_ml: int
    goal_label: str
    slots: list[MealSlot]
    insights: list[MealInsight]
    avoid: list[str]
    body_type: str = ""
    risk_flags: list[str] = field(default_factory=list)
    weekly_hints: list[WeeklyMealHint] = field(default_factory=list)


def _severity_rank(severity: str) -> int:
    order = {"high": 0, "mid": 1, "tip": 2}
    return order.get(severity, 9)


def _build_insights(result: InBodyResult, body_type: str, flags: list[str]) -> list[MealInsight]:
    insights: list[MealInsight] = []

    if result.protein.status == "low" or "단백질 부족" in flags:
        current = (
            f"현재 단백질 {result.protein.value} kg "
            f"(정상 {result.protein.low}~{result.protein.high} kg)"
            if result.protein.value is not None
            else "단백질이 정상 범위보다 낮습니다"
        )
        insights.append(
            MealInsight(
                topic="단백질",
                reason=current,
                action="매 끼니 손바닥 1개 분량(약 20~30g)의 단백질 식품을 포함하세요",
                severity="high",
            )
        )

    if result.body_water.status == "low" or "체수분 부족" in flags:
        current = (
            f"현재 체수분 {result.body_water.value} L "
            f"(정상 {result.body_water.low}~{result.body_water.high} L)"
            if result.body_water.value is not None
            else "체수분이 정상보다 낮습니다"
        )
        insights.append(
            MealInsight(
                topic="수분",
                reason=current,
                action="기상 직후 물 300~400ml, 이후 1~2시간마다 200ml씩 보충하세요",
                severity="high",
            )
        )

    if result.mineral.status == "low" or "무기질 부족" in flags:
        current = (
            f"현재 무기질 {result.mineral.value} kg "
            f"(정상 {result.mineral.low}~{result.mineral.high} kg)"
            if result.mineral.value is not None
            else "무기질이 부족합니다"
        )
        insights.append(
            MealInsight(
                topic="무기질",
                reason=current,
                action="유제품·두부·멸치·녹색잎채소를 하루 1~2회 챙기세요",
                severity="high",
            )
        )

    if result.obesity_pbf in ("경도비만", "비만") or result.body_fat_mass.status == "high":
        pbf = result.percent_body_fat
        label = result.obesity_pbf or "과다"
        insights.append(
            MealInsight(
                topic="체지방",
                reason=f"체지방률 {pbf}% ({label}) — 급격한 감량보다 체재구성이 우선입니다",
                action="야식·가당음료·튀김을 줄이고, 단백질·채소를 매끼 유지하세요",
                severity="mid",
            )
        )
    elif result.body_fat_mass.status == "low":
        insights.append(
            MealInsight(
                topic="체지방",
                reason="체지방이 다소 낮을 수 있습니다. 과도한 절식은 피하세요",
                action="견과·아보카도·올리브유·생선 등 건강한 지방을 적절히 포함하세요",
                severity="mid",
            )
        )

    if body_type.startswith("C") or any("C형" in f for f in flags):
        insights.append(
            MealInsight(
                topic="체형",
                reason=f"{body_type} — 골격근 대비 체지방·체중 균형이 불리한 패턴입니다",
                action="극단적 칼로리 제한 대신 단백질↑ + 근력 운동을 병행하세요",
                severity="mid",
            )
        )

    if result.bmr.status == "low":
        insights.append(
            MealInsight(
                topic="대사",
                reason=f"기초대사량 {result.bmr.value} kcal로 권장보다 낮습니다",
                action="근육량 증가가 BMR 상승에 가장 효과적입니다 — 단백질·저항 운동을 유지하세요",
                severity="tip",
            )
        )

    if result.age is not None and result.age < 20:
        insights.append(
            MealInsight(
                topic="성장",
                reason=f"현재 {result.age}세로 성장기 — 무리한 감량보다 영양·수면이 우선입니다",
                action="단백질·칼슘·비타민 D를 매일 챙기고 수면 8~9시간을 확보하세요",
                severity="tip",
            )
        )

    if not insights:
        insights.append(
            MealInsight(
                topic="유지",
                reason="전반 영양 지표가 양호한 편입니다",
                action="하루 3끼 + 필요 시 간식으로 단백질을 분산하고, 통곡물·채소를 유지하세요",
                severity="tip",
            )
        )

    insights.sort(key=lambda i: _severity_rank(i.severity))
    return insights


def _build_slots(result: InBodyResult, body_type: str) -> list[MealSlot]:
    protein_low = result.protein.status == "low"
    mineral_low = result.mineral.status == "low"
    water_low = result.body_water.status == "low"
    is_c = body_type.startswith("C")
    fat_high = result.obesity_pbf in ("경도비만", "비만") or result.body_fat_mass.status == "high"

    breakfast_tip = "하루 단백질의 1/4을 아침에 채우면 포만감·집중력에 도움이 됩니다"
    if protein_low:
        breakfast_tip = "단백질 부족 — 아침부터 계란·요거트로 20g 이상 챙기세요"

    lunch_items = ["살코기·생선·두부 중 1가지", "밥 또는 잡곡", "채소 반찬"]
    lunch_tip = "점심에 단백질+탄수화물을 균형 있게 섭취하세요"
    if mineral_low:
        lunch_items.append("해조류·멸치 등 칼슘 식품")
        lunch_tip = "무기질 보충을 위해 해조류·멸치를 점심에 포함하세요"

    if protein_low:
        dinner_items = ["고단백 식품(닭가슴살·계란·생선·두부)", "채소 충분히", "튀김·당류 제한"]
        dinner_tip = "저녁은 단백질 위주로, 야식 대신 끼니 안에서 해결하세요"
    else:
        dinner_items = ["단백질 위주 메인", "채소 충분히", "튀김·당류는 줄이기"]
        dinner_tip = "저녁 과식·야식을 줄이면 체지방 관리에 유리합니다"

    if is_c:
        dinner_tip = "C형(근력 부족) — 저녁에도 단백질을 빼지 마세요"

    if mineral_low:
        snack_items = ["유제품(우유·요거트·치즈) 1회", "견과 한 줌", "과일"]
        snack_tip = "뼈·무기질을 위해 유제품을 간식으로 챙기세요"
    else:
        snack_items = ["우유 또는 그릭요거트", "견과 한 줌", "과일", "프로틴(필요 시)"]
        snack_tip = "간식은 단백질·식이섬유 중심으로 선택하세요"

    if fat_high:
        snack_tip = "체지방 관리 — 가당 간식 대신 단백질·과일 위주로"
    if water_low:
        breakfast_tip += " · 기상 직후 물 한 잔"

    return [
        MealSlot(
            key="breakfast",
            title="아침",
            items=["계란 또는 그릭요거트", "통곡물", "과일"],
            tip=breakfast_tip,
        ),
        MealSlot(
            key="lunch",
            title="점심",
            items=lunch_items,
            tip=lunch_tip,
        ),
        MealSlot(
            key="dinner",
            title="저녁",
            items=dinner_items,
            tip=dinner_tip,
        ),
        MealSlot(
            key="snack",
            title="간식",
            items=snack_items,
            tip=snack_tip,
        ),
    ]


def _build_avoid(result: InBodyResult) -> list[str]:
    avoid = ["야식", "가당 음료", "과도한 패스트푸드", "극단적 단식"]
    if result.body_water.status == "low":
        avoid.append("과도한 카페인(이뇨 작용)")
    if result.obesity_pbf in ("경도비만", "비만") or result.body_fat_mass.status == "high":
        avoid.append("튀김·단순당 간식")
    return avoid


_DAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]
_DAY_LABELS = {
    "월": "월요일",
    "화": "화요일",
    "수": "수요일",
    "목": "목요일",
    "금": "금요일",
    "토": "토요일",
    "일": "일요일",
}

# 요일별 기본 식단 힌트 (운동 테마 연동) — plan3 §3.5
_WEEKLY_HINT_BASE: dict[str, tuple[str, str]] = {
    "월": ("protein", "하체 근력일 — 단백질·복합 탄수화물을 균형 있게"),
    "화": ("water", "유산소일 — 수분·전해질(물·무가당 차)을 충분히"),
    "수": ("protein", "상체 근력일 — 운동 후 1시간 이내 단백질 20~30g"),
    "목": ("mineral", "회복일 — 수분·무기질 식품(유제품·채소) 강화"),
    "금": ("protein", "하체+코어일 — 단백질 유지, 주간 식단 점검"),
    "토": ("balance", "활동일 — 균형 잡힌 식사, 과식·야식은 피하기"),
    "일": ("prep", "휴식일 — 다음 주 장보기·식단 준비, 수면 보충"),
}


def _build_weekly_hints(
    result: InBodyResult,
    body_type: str,
    weekly_plan: dict[str, list[str]] | None = None,
) -> list[WeeklyMealHint]:
    protein_low = result.protein.status == "low"
    water_low = result.body_water.status == "low"
    mineral_low = result.mineral.status == "low"
    is_c = body_type.startswith("C")
    water_ml = _water_target_ml(result)

    hints: list[WeeklyMealHint] = []
    for day in _DAY_ORDER:
        focus, hint = _WEEKLY_HINT_BASE[day]
        items = (weekly_plan or {}).get(day, [])
        exercise = items[0] if items else "—"

        # InBody 상태에 따라 힌트 보강
        if day == "월" and (protein_low or is_c):
            hint = "하체 근력일 — 매끼 단백질 손바닥 1개 + 잡곡·감자로 에너지 확보"
            focus = "protein"
        elif day == "화" and water_low:
            hint = f"유산소일 — 목표 수분 {water_ml}ml, 땀 많으면 전해질 포함"
            focus = "water"
        elif day == "수" and protein_low:
            hint = "상체 근력일 — 운동 직후 단백질·탄수화물 소량 필수"
            focus = "protein"
        elif day == "목" and mineral_low:
            hint = "회복일 — 유제품·두부·해조류로 무기질 보충"
            focus = "mineral"
        elif day == "목" and water_low:
            hint = f"회복일 — 수분 {water_ml}ml + 짠 음식·카페인 줄이기"
            focus = "water"
        elif day == "금" and protein_low:
            hint = "하체+코어일 — 단백질 목표 재점검, 야식 없이 끼니로 채우기"
            focus = "protein"
        elif day == "토" and (
            result.obesity_pbf in ("경도비만", "비만") or result.body_fat_mass.status == "high"
        ):
            hint = "활동일 — 외식 시 튀김·가당음료 줄이고 단백질·채소 우선"
            focus = "balance"
        elif day == "일" and mineral_low:
            hint = "휴식일 — 장보기 때 유제품·녹색잎채소·견과를 미리 준비"
            focus = "prep"

        hints.append(
            WeeklyMealHint(
                day_short=day,
                day_label=_DAY_LABELS[day],
                exercise=exercise,
                hint=hint,
                focus=focus,
            )
        )
    return hints


def build_meal_plan(
    result: InBodyResult,
    report: PrescriptionReport | None = None,
) -> MealPlanReport:
    """InBody 결과(+선택적 처방 리포트)로 구조화 식단 리포트 생성."""
    cal = _calories(result)
    p_low, p_high = _protein_target_g(result)
    water_ml = _water_target_ml(result)

    weekly_plan: dict[str, list[str]] | None = None
    if report is not None:
        body_type = report.body_type
        flags = list(report.risk_flags)
        weekly_plan = report.weekly_plan
    else:
        from prescription import _muscle_fat_shape

        body_type = _muscle_fat_shape(result)
        flags = []
        if result.body_water.status == "low":
            flags.append("체수분 부족")
        if result.protein.status == "low":
            flags.append("단백질 부족")
        if result.mineral.status == "low":
            flags.append("무기질 부족")
        if result.obesity_pbf in ("경도비만", "비만"):
            flags.append(f"체지방률 {result.obesity_pbf}")
        if body_type.startswith("C"):
            flags.append("C형(근력 부족)")

    return MealPlanReport(
        calories=int(cal["intake"]),
        protein_g=(int(p_low), int(p_high)),
        water_ml=water_ml,
        goal_label=str(cal["goal_label"]),
        slots=_build_slots(result, body_type),
        insights=_build_insights(result, body_type, flags),
        avoid=_build_avoid(result),
        body_type=body_type,
        risk_flags=flags,
        weekly_hints=_build_weekly_hints(result, body_type, weekly_plan),
    )


def meal_guide_lines(plan: MealPlanReport) -> list[str]:
    """하위 호환: MealPlanReport → 기존 meal_guide 문자열 리스트."""
    p_low, p_high = plan.protein_g
    lines = [
        f"하루 목표: {plan.calories} kcal · 단백질 {p_low}~{p_high}g · 수분 {plan.water_ml}ml"
        f" ({plan.goal_label})",
    ]
    for slot in plan.slots:
        items = " · ".join(slot.items)
        lines.append(f"{slot.title}: {items}")
    if plan.avoid:
        lines.append("피하기: " + ", ".join(plan.avoid))
    return lines


def _esc(text: object) -> str:
    return html.escape(str(text) if text is not None else "")


_SLOT_ICON: dict[str, str] = {
    "breakfast": "breakfast",
    "lunch": "lunch",
    "dinner": "dinner",
    "snack": "snack",
}

_SEVERITY_LABEL: dict[str, str] = {
    "high": "우선",
    "mid": "권장",
    "tip": "참고",
}


def render_meal_plan_html(plan: MealPlanReport) -> str:
    """plan3 Phase 02~04 — 목표 칩 + 끼니 카드 + 인사이트 + 주간 힌트."""
    from icons import icon_html

    p_low, p_high = plan.protein_g
    chips = (
        '<div class="srx-meal-goals">'
        f'<div class="srx-meal-chip kcal">'
        f'{icon_html("calories")}'
        f'<div class="srx-meal-chip-body">'
        f'<span class="label">칼로리</span>'
        f'<strong>{plan.calories:,} <small>kcal</small></strong>'
        f'<span class="sub">{_esc(plan.goal_label)}</span>'
        f"</div></div>"
        f'<div class="srx-meal-chip protein">'
        f'{icon_html("protein")}'
        f'<div class="srx-meal-chip-body">'
        f'<span class="label">단백질</span>'
        f"<strong>{p_low}~{p_high} <small>g</small></strong>"
        f'<span class="sub">하루 목표</span>'
        f"</div></div>"
        f'<div class="srx-meal-chip water">'
        f'{icon_html("water")}'
        f'<div class="srx-meal-chip-body">'
        f'<span class="label">수분</span>'
        f"<strong>{plan.water_ml:,} <small>ml</small></strong>"
        f'<span class="sub">하루 이상</span>'
        f"</div></div>"
        "</div>"
    )

    cards: list[str] = []
    for i, slot in enumerate(plan.slots):
        icon_key = _SLOT_ICON.get(slot.key, "meal")
        items = "".join(f"<li>{_esc(item)}</li>" for item in slot.items)
        delay = min(0.05 * i, 0.3)
        cards.append(
            f'<article class="srx-meal-card" style="animation-delay:{delay:.2f}s">'
            f'<header class="srx-meal-card-head">'
            f'<span class="srx-meal-card-icon" aria-hidden="true">{icon_html(icon_key)}</span>'
            f"<h4>{_esc(slot.title)}</h4>"
            f"</header>"
            f'<ul class="srx-meal-card-items">{items}</ul>'
            f'<p class="srx-meal-card-tip">{_esc(slot.tip)}</p>'
            f"</article>"
        )
    cards_html = f'<div class="srx-meal-cards">{"".join(cards)}</div>'

    insight_rows: list[str] = []
    for insight in plan.insights[:4]:
        sev = insight.severity if insight.severity in _SEVERITY_LABEL else "tip"
        label = _SEVERITY_LABEL[sev]
        insight_rows.append(
            f'<div class="srx-meal-insight sev-{sev}">'
            f'<span class="badge">{_esc(label)}</span>'
            f'<div class="body">'
            f"<strong>{_esc(insight.topic)}</strong>"
            f'<p class="reason">{_esc(insight.reason)}</p>'
            f'<p class="action">{_esc(insight.action)}</p>'
            f"</div></div>"
        )
    insights_html = ""
    if insight_rows:
        insights_html = (
            '<div class="srx-meal-insights">'
            '<div class="srx-meal-insights-title">건강 인사이트</div>'
            f"{''.join(insight_rows)}"
            "</div>"
        )

    weekly_html = ""
    if plan.weekly_hints:
        from datetime import datetime

        today_idx = datetime.now().weekday()
        rows: list[str] = []
        for hint in plan.weekly_hints:
            day_idx = _DAY_ORDER.index(hint.day_short) if hint.day_short in _DAY_ORDER else -1
            today_cls = " today" if day_idx == today_idx else ""
            rows.append(
                f'<div class="srx-meal-week-row focus-{_esc(hint.focus)}{today_cls}">'
                f'<span class="day">{_esc(hint.day_short)}</span>'
                f'<div class="week-body">'
                f'<span class="ex">{_esc(hint.exercise)}</span>'
                f'<span class="hint">{_esc(hint.hint)}</span>'
                f"</div></div>"
            )
        weekly_html = (
            '<div class="srx-meal-week">'
            '<div class="srx-meal-week-title">주간 식단 힌트</div>'
            '<p class="srx-meal-week-sub">운동 플랜과 연동된 요일별 한 줄 가이드입니다.</p>'
            f"{''.join(rows)}"
            "</div>"
        )

    avoid_html = ""
    if plan.avoid:
        tags = "".join(f"<span>{_esc(a)}</span>" for a in plan.avoid)
        avoid_html = (
            '<div class="srx-meal-avoid">'
            "<strong>피하기</strong>"
            f'<div class="tags">{tags}</div>'
            "</div>"
        )

    return (
        f'<div class="srx-meal-dashboard">'
        f"{chips}{cards_html}{insights_html}{weekly_html}{avoid_html}"
        f"</div>"
    )
