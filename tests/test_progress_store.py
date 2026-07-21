"""progress_store.py 회귀 테스트."""

from __future__ import annotations

from missions import mission_checkbox_key
from parser import InBodyResult, RangeValue, parse_inbody_text
from prescription import build_prescription
from progress_store import (
    detect_body_evolution,
    bootstrap_user_progress,
    load_profile_progress,
    save_profile_progress,
)
from profile_keys import build_profile_key, build_user_key
from weekly_plan_ui import weekly_plan_done_key

from tests.fixtures import FIXTURE_TEEN_HISTORY


def test_profile_and_user_keys():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    assert build_user_key(result) == "John_Doe_C"
    assert "2020_06_21" in build_profile_key(result) or "2020" in build_profile_key(result)


def test_save_and_load_profile_progress(tmp_path, monkeypatch):
    monkeypatch.setattr("progress_store.STORE_PATH", tmp_path / "progress.json")
    monkeypatch.setattr("progress_store.STORE_DIR", tmp_path)

    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    profile_key = build_profile_key(result)
    session: dict = {}

    session[mission_checkbox_key("water", 0, profile_key)] = True
    session[weekly_plan_done_key(0, profile_key)] = True
    save_profile_progress(profile_key, session)

    fresh: dict = {}
    load_profile_progress(profile_key, fresh)
    assert fresh[mission_checkbox_key("water", 0, profile_key)] is True
    assert fresh[weekly_plan_done_key(0, profile_key)] is True


def test_detect_body_evolution():
    evo = detect_body_evolution("C", "I")
    assert evo is not None
    assert evo.from_key == "C"
    assert evo.to_key == "I"
    assert detect_body_evolution("D", "I") is None


def test_bootstrap_new_measurement_evolution(tmp_path, monkeypatch):
    monkeypatch.setattr("progress_store.STORE_PATH", tmp_path / "progress.json")
    monkeypatch.setattr("progress_store.STORE_DIR", tmp_path)

    result1 = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    report1 = build_prescription(result1)
    report1.body_type = "C형 (근력 부족형)"
    session: dict = {}
    bootstrap_user_progress(result1, report1, session)

    result2 = InBodyResult(
        name="John Doe C",
        test_datetime="2021.01.01. 10:00",
        weight=RangeValue(value=60.0),
        skeletal_muscle_mass=26.0,
    )
    report2 = build_prescription(result2)
    report2.body_type = "I형 (표준)"

    session2: dict = {}
    bootstrap_user_progress(result2, report2, session2)
    evo = session2.get("somarx_body_evolution")
    assert evo is not None
    assert evo["from_key"] == "C"
    assert evo["to_key"] == "I"
