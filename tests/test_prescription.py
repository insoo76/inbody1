"""prescription.py 회귀 테스트."""

from __future__ import annotations

from parser import parse_inbody_text
from prescription import build_prescription

from tests.fixtures import FIXTURE_TEEN_HISTORY


def test_prescription_sections_and_weekly_plan():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_prescription(result)

    assert report.body_type
    assert len(report.sections) >= 1
    assert len(report.weekly_plan) == 7
    assert "월" in report.weekly_plan
    assert report.meal_guide


def test_prescription_priorities():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report = build_prescription(result)
    priorities = {s.priority for s in report.sections}
    assert priorities.issubset({"높음", "보통", "참고"})
