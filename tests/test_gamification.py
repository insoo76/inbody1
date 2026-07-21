"""gamification_engine.py 회귀 테스트."""

from __future__ import annotations

from gamification_engine import (
    build_launch_dashboard,
    evaluate_evolution,
    render_launch_banner_html,
    render_rewards_strip_html,
)
from missions import MissionProgress, generate_missions
from parser import parse_inbody_text
from persona import build_persona_dashboard
from prescription import build_prescription
from slime_growth import SlimeGrowthReport, build_slime_growth_report

from tests.fixtures import FIXTURE_TEEN_HISTORY


def _gold_progress(missions) -> MissionProgress:
    total = len(missions) * 7
    completed = int(total * 0.85)
    return MissionProgress(
        missions=missions,
        completed=completed,
        total=total,
        rate=round(completed / total * 100, 1),
        has_gold_badge=True,
        message="ok",
    )


def test_evolution_ready_at_high_progress():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_prescription(result)
    dashboard = build_persona_dashboard(result, report)
    missions = generate_missions(result, report)
    progress = _gold_progress(missions)
    growth = build_slime_growth_report(result, report, dashboard, progress, {}, None)
    growth = SlimeGrowthReport(
        emoji=growth.emoji,
        name=growth.name,
        next_label=growth.next_label,
        progress_pct=88.0,
        quests=growth.quests,
        summary=growth.summary,
        is_max_stage=False,
        evolution_ready=True,
        quests_done=4,
        quests_total=5,
    )
    evolution = evaluate_evolution(growth, progress, dashboard)
    assert evolution.ready
    assert evolution.show_celebration


def test_launch_banner_and_rewards_html():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_prescription(result)
    dashboard = build_persona_dashboard(result, report)
    missions = generate_missions(result, report)
    progress = _gold_progress(missions)
    growth = build_slime_growth_report(result, report, dashboard, progress, {}, None)
    evolution = evaluate_evolution(growth, progress, dashboard)
    launch = build_launch_dashboard(
        result, report, dashboard, growth, progress, evolution, None
    )

    banner = render_launch_banner_html(launch)
    assert "srx-launch-banner" in banner
    assert str(launch.readiness_score) in banner

    rewards = render_rewards_strip_html(evolution, progress)
    assert "골드" in rewards
