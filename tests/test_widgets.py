"""시각화·미션 위젯 회귀 테스트."""

from __future__ import annotations

from bmr_viz import build_bmr_report, render_bmr_widget_html
from missions import generate_missions
from parser import parse_inbody_text
from phase_angle import build_phase_angle_report, make_phase_angle_chart
from prescription import build_prescription
from rx_cards import render_prescription_cards
from trend import build_trend_report, make_trend_chart
from weekly_plan_ui import build_weekly_plan_rows, collect_statuses, render_weekly_plan_table

from tests.fixtures import FIXTURE_TEEN_HISTORY


def test_bmr_report_deficit():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    bmr = build_bmr_report(result)
    assert bmr is not None
    assert bmr.status == "low"
    assert bmr.deficit == 6.0
    html = render_bmr_widget_html(bmr)
    assert "srx-bmr" in html


def test_phase_angle_chart():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_phase_angle_report(result)
    assert report is not None
    assert len(report.points) >= 2
    fig = make_phase_angle_chart(report.points, report.delta)
    assert len(fig.data) > 0


def test_trend_sunny_weather():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    trend = build_trend_report(result)
    assert trend is not None
    assert trend.weather.emoji == "☀️"
    assert len(trend.points) >= 2
    fig = make_trend_chart(trend.points, "smm", "#10B981", " kg", "SMM")
    assert len(fig.data) > 0


def test_rx_cards_and_weekly_plan():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_prescription(result)
    cards = render_prescription_cards(report.sections)
    assert "srx-card-grid" in cards

    rows = build_weekly_plan_rows(report.weekly_plan)
    assert len(rows) == 7
    table = render_weekly_plan_table(rows, collect_statuses(rows, "test", {}))
    assert "srx-wplan" in table


def test_missions_generated():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_prescription(result)
    missions = generate_missions(result, report)
    assert 1 <= len(missions) <= 3
