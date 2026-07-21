"""meal_plan.py — plan3 Phase 01~02 테스트."""

from __future__ import annotations

from parser import InBodyResult, RangeValue, parse_inbody_text
from prescription import build_prescription
from meal_plan import build_meal_plan, meal_guide_lines, render_meal_plan_html
from icons import icon_html

from tests.fixtures import FIXTURE_TEEN_HISTORY


def test_build_meal_plan_has_four_slots():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_prescription(result)
    plan = build_meal_plan(result, report)

    assert len(plan.slots) == 4
    assert [s.key for s in plan.slots] == ["breakfast", "lunch", "dinner", "snack"]
    assert plan.calories > 0
    assert plan.protein_g[0] <= plan.protein_g[1]
    assert plan.water_ml >= 1800
    assert plan.goal_label
    assert plan.avoid


def test_protein_low_insight_is_high():
    result = InBodyResult(
        name="저단백",
        age=30,
        gender="남",
        weight=RangeValue(value=70.0, low=60, high=80, unit="kg"),
        protein=RangeValue(value=7.0, low=9.0, high=11.0, unit="kg"),
        body_water=RangeValue(value=35.0, low=32.0, high=40.0, unit="L"),
        skeletal_muscle_mass=26.0,
    )
    assert result.protein.status == "low"
    plan = build_meal_plan(result)

    protein_insights = [i for i in plan.insights if i.topic == "단백질"]
    assert protein_insights
    assert protein_insights[0].severity == "high"
    assert plan.insights[0].severity == "high"


def test_meal_guide_lines_compatible():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_prescription(result)
    plan = build_meal_plan(result, report)
    lines = meal_guide_lines(plan)

    assert any("kcal" in line for line in lines)
    assert any(line.startswith("아침") for line in lines)
    assert any(line.startswith("피하기") for line in lines)
    assert report.meal_guide


def test_build_meal_plan_without_report():
    result = InBodyResult(
        name="테스트",
        age=25,
        gender="남",
        weight=RangeValue(value=70.0, low=60, high=80, unit="kg"),
        protein=RangeValue(value=8.0, low=9.0, high=11.0, unit="kg"),
        body_water=RangeValue(value=30.0, low=32.0, high=40.0, unit="L"),
        skeletal_muscle_mass=25.0,
    )
    assert result.protein.status == "low"
    assert result.body_water.status == "low"
    plan = build_meal_plan(result)
    assert len(plan.slots) == 4
    topics = {i.topic for i in plan.insights}
    assert "단백질" in topics
    assert "수분" in topics


def test_render_meal_plan_html_has_chips_and_cards():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    plan = build_meal_plan(result, build_prescription(result))
    html_out = render_meal_plan_html(plan)

    assert "srx-meal-goals" in html_out
    assert "srx-meal-chip" in html_out
    assert "srx-meal-cards" in html_out
    assert html_out.count('class="srx-meal-card"') == 4
    assert "kcal" in html_out
    assert "<svg" in html_out
    assert "건강 인사이트" in html_out
    assert "피하기" in html_out
    assert "주간 식단 힌트" in html_out
    assert "srx-meal-week" in html_out


def test_weekly_hints_seven_days():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_prescription(result)
    plan = build_meal_plan(result, report)
    assert len(plan.weekly_hints) == 7
    assert [h.day_short for h in plan.weekly_hints] == list("월화수목금토일")
    assert plan.weekly_hints[0].exercise  # 주간 플랜 연동
    assert "하체" in plan.weekly_hints[0].hint or "단백질" in plan.weekly_hints[0].hint


def test_weekly_hints_adapt_to_protein_low():
    result = InBodyResult(
        weight=RangeValue(value=70.0, low=60, high=80, unit="kg"),
        protein=RangeValue(value=7.0, low=9.0, high=11.0, unit="kg"),
    )
    plan = build_meal_plan(result)
    monday = plan.weekly_hints[0]
    assert monday.day_short == "월"
    assert monday.focus == "protein"
    assert "단백질" in monday.hint


def test_meal_slot_icons_exist():
    for key in ("meal", "breakfast", "lunch", "dinner", "snack", "calories"):
        out = icon_html(key)
        assert "<svg" in out
        assert key in out
