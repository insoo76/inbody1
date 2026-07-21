#!/usr/bin/env python3
"""1단계 실사용 QA — OCR 픽스처·파이프라인·게이미피케이션 통합 검증."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from analysis import build_multidim_analysis
from bmr_viz import build_bmr_report
from gamification_engine import (
    build_launch_dashboard,
    evaluate_evolution,
    render_evolution_celebration_html,
    render_launch_banner_html,
    render_rewards_strip_html,
)
from heatmap import build_body_heatmap
from missions import (
    count_mission_progress,
    generate_missions,
    mission_checkbox_key,
)
from parser import check_ocr_ready, normalize_inbody_result, parse_inbody_text
from persona import build_persona_dashboard
from phase_angle import build_phase_angle_report, make_phase_angle_chart
from prescription import build_prescription
from rx_cards import render_prescription_cards
from slime_growth import build_slime_growth_report
from trend import build_trend_report, make_trend_chart
from weekly_plan_ui import build_weekly_plan_rows, collect_statuses, render_weekly_plan_table

# plan2·plan.md 기준 OCR 텍스트 픽스처 (실제 PDF OCR 패턴 모사)
FIXTURE_TEEN_HISTORY = """
John Doe C             168cm        17        남      2020.06.21. 16:40
체수분 29.5 (29.0~35.0)
단백질 7.8 (7.5~9.2)
무기질 3.04 (3.0~3.5)
체지방 12.5 (7.3~14.5)
체중 58.0 (47.5~64.5)
골격근량 25.0
체지방률 23.9
BMI 20.6
성장점수 82
기초대사량 1339 kcal (1345~1562)
위상각 6.1°
영양평가 단백질 부족 무기질 부족
신체변화 Body Composition History
2020.02.01 2020.04.15 2020.06.21
체중 56.2 57.1 58.0
골격근량 23.5 24.2 25.0
체지방률 26.1 25.0 23.9
위상각 5.5 5.8 6.1
오른팔 2.45
왼팔 2.38
몸통 22.1
오른다리 8.2
왼다리 8.0
"""

FIXTURE_ADULT_SINGLE = """
김민수             175cm        32        남      2024.11.05. 09:30
체수분 32.1 (32.0~39.0)
단백질 9.2 (9.0~11.0)
무기질 3.45 (3.2~3.9)
체지방 18.2 (10.0~20.0)
체중 78.5 (60.0~81.0)
골격근량 34.2
체지방률 22.5
BMI 25.6
기초대사량 1580 kcal (1550~1800)
위상각 5.8°
"""

FIXTURE_FEMALE_LOW_WATER = """
이서연             162cm        28        여      2025.01.12. 14:20
체수분 24.8 (26.0~32.0)
단백질 7.1 (7.2~8.8)
무기질 2.85 (2.8~3.4)
체지방 16.8 (12.0~22.0)
체중 55.2 (47.0~57.0)
골격근량 22.1
체지방률 28.5
BMI 21.0
기초대사량 1210 kcal (1200~1400)
위상각 4.9°
"""

FIXTURE_MINIMAL = """
테스트             170cm        25        남      2025.03.01. 10:00
체중 70.0 (55.0~75.0)
"""

FIXTURE_DECLINING = """
박지훈             172cm        19        남      2025.06.01. 11:00
체수분 30.0 (30.0~36.0)
단백질 8.0 (8.0~10.0)
체중 65.0 (55.0~72.0)
골격근량 28.0
체지방률 24.0
기초대사량 1400 kcal (1350~1600)
위상각 5.2°
신체변화
2025.03.01 2025.04.01 2025.06.01
체중 63.0 64.5 65.0
골격근량 29.5 28.8 28.0
체지방률 22.0 23.0 24.0
위상각 5.8 5.5 5.2
"""


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ScenarioReport:
    id: str
    label: str
    checks: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        failed = [c for c in self.checks if not c.passed]
        if self.id == "minimal":
            optional = {"BMR 추출", "위상각 추출", "다차원 분석"}
            failed = [c for c in failed if c.name not in optional]
        return len(failed) == 0


def _check(name: str, cond: bool, detail: str = "") -> CheckResult:
    return CheckResult(name, cond, detail)


def _simulate_gold_missions(missions, profile_key: str) -> dict:
    """주간 미션 80%+ 달성 시뮬레이션."""
    state: dict = {f"mission_profile::{profile_key}": profile_key}
    total = len(missions) * 7
    done = 0
    for mission in missions:
        for day in range(7):
            key = mission_checkbox_key(mission.id, day, profile_key)
            checked = done < int(total * 0.85)
            state[key] = checked
            if checked:
                done += 1
    return state


def validate_scenario(scenario_id: str, label: str, ocr_text: str) -> ScenarioReport:
    report = ScenarioReport(id=scenario_id, label=label)
    result = normalize_inbody_result(parse_inbody_text(ocr_text))
    rx = build_prescription(result)

    # --- OCR / 파싱 ---
    report.checks.append(
        _check("프로필(이름·신장·연령)", result.name is not None and result.height_cm is not None)
    )
    if result.name:
        report.checks[-1].detail = f"name={result.name}, h={result.height_cm}, age={result.age}"

    has_bmr = result.bmr.value is not None
    report.checks.append(_check("BMR 추출", has_bmr, f"value={result.bmr.value}"))
    if scenario_id == "minimal":
        report.warnings.append("최소 데이터 시나리오 — BMR/위상각/다차원 미표시는 정상")
    elif has_bmr:
        bmr_report = build_bmr_report(result)
        report.checks.append(_check("BMR 위젯", bmr_report is not None and bmr_report.value > 0))

    has_pa = result.phase_angle is not None
    if scenario_id != "minimal":
        report.checks.append(_check("위상각 추출", has_pa, f"value={result.phase_angle}"))
    pa_report = build_phase_angle_report(result)
    if has_pa:
        report.checks.append(_check("위상각 리포트", pa_report is not None))
        if pa_report and len(pa_report.points) >= 2:
            chart = make_phase_angle_chart(pa_report.points, pa_report.delta)
            report.checks.append(_check("위상각 차트", chart is not None and len(chart.data) > 0))
        elif result.phase_angle_history:
            report.warnings.append("위상각 이력은 있으나 차트 포인트 2개 미만")

    # --- 이력 / 트렌드 ---
    trend = build_trend_report(result)
    if len(result.history_dates) >= 2 or (
        result.weight_history and len(result.weight_history) >= 2
    ):
        report.checks.append(_check("트렌드 리포트 생성", trend is not None))
        if trend:
            report.checks.append(
                _check(
                    "트렌드 포인트 ≥2",
                    len(trend.points) >= 2,
                    f"points={len(trend.points)}, weather={trend.weather.emoji}",
                )
            )
            if len(trend.points) >= 2:
                chart = make_trend_chart(trend.points, "smm", "#10B981", " kg", "SMM")
                report.checks.append(_check("트렌드 차트", chart is not None))
    else:
        report.warnings.append("이력 데이터 없음 — 트렌드·위상각 그래프 단일 포인트만 표시")

    # --- 히트맵 / 다차원 ---
    heat = build_body_heatmap(result)
    report.checks.append(_check("히트맵 리포트", heat is not None))
    if not heat.has_data:
        report.warnings.append("부위별 근육량 미추출 — 히트맵 빈 상태 가능")

    multidim = build_multidim_analysis(result, rx)
    if scenario_id != "minimal":
        report.checks.append(
            _check(
                "다차원 분석",
                multidim.has_radar or multidim.has_quadrant,
                f"radar={multidim.has_radar}, quad={multidim.has_quadrant}",
            )
        )

    # --- 처방 / UI HTML ---
    cards_html = render_prescription_cards(rx.sections)
    report.checks.append(
        _check("처방 카드 HTML", "srx-card-grid" in cards_html and len(rx.sections) > 0)
    )
    rows = build_weekly_plan_rows(rx.weekly_plan)
    report.checks.append(_check("주간 플랜 7일", len(rows) == 7))
    plan_html = render_weekly_plan_table(rows, collect_statuses(rows, "qa", {}))
    report.checks.append(_check("주간 플랜 테이블 HTML", "srx-wplan" in plan_html))

    # --- 미션 / 게이미피케이션 ---
    missions = generate_missions(result, rx)
    report.checks.append(_check("미션 생성", len(missions) >= 1, f"count={len(missions)}"))
    if missions:
        profile_key = f"{result.name}|{result.test_datetime}|{result.weight.value}"
        session = _simulate_gold_missions(missions, profile_key)
        progress = count_mission_progress(missions, profile_key, session)
        dashboard = build_persona_dashboard(result, rx, trend)
        growth = build_slime_growth_report(result, rx, dashboard, progress, session, trend)
        evolution = evaluate_evolution(growth, progress, dashboard)
        launch = build_launch_dashboard(result, rx, dashboard, growth, progress, evolution, trend)

        report.checks.append(
            _check(
                "골드 뱃지 시뮬레이션",
                progress.has_gold_badge,
                f"rate={progress.rate:.0f}%",
            )
        )
        banner = render_launch_banner_html(launch)
        report.checks.append(_check("런칭 배너 HTML", "srx-launch-banner" in banner))
        rewards = render_rewards_strip_html(evolution, progress)
        report.checks.append(
            _check("리워드 스트립(골드)", "골드" in rewards or progress.has_gold_badge)
        )
        report.checks.append(
            _check(
                "슬라임 성장",
                growth.progress_pct >= 0,
                f"progress={growth.progress_pct}%, quests={growth.quests_done}/{growth.quests_total}",
            )
        )
        if evolution.ready:
            celeb = render_evolution_celebration_html(evolution, growth)
            report.checks.append(_check("진화 축하 UI", "srx-evolution-celebration" in celeb))

    return report


def scan_pdf_directory(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.glob("**/*.pdf"))[:10]


def main() -> int:
    print("=" * 60)
    print("SomaRx 2.0 — 1단계 실사용 QA")
    print("=" * 60)

    ocr_ok, ocr_msg = check_ocr_ready()
    print(f"\n[환경] Tesseract OCR: {'OK' if ocr_ok else 'FAIL'} — {ocr_msg}")

    scenarios = [
        ("teen_history", "청소년·이력 3회 (plan2 기준)", FIXTURE_TEEN_HISTORY),
        ("adult_single", "성인·단일 측정", FIXTURE_ADULT_SINGLE),
        ("female_low_water", "여성·체수분 부족", FIXTURE_FEMALE_LOW_WATER),
        ("minimal", "최소 데이터", FIXTURE_MINIMAL),
        ("declining", "근육↓·체지방↑ (비 날씨)", FIXTURE_DECLINING),
    ]

    all_reports: list[ScenarioReport] = []
    for sid, label, text in scenarios:
        rep = validate_scenario(sid, label, text)
        all_reports.append(rep)
        status = "PASS" if rep.ok else "FAIL"
        print(f"\n--- [{status}] {label} ({sid}) ---")
        for c in rep.checks:
            mark = "✓" if c.passed else "✗"
            extra = f" — {c.detail}" if c.detail else ""
            print(f"  {mark} {c.name}{extra}")
        for w in rep.warnings:
            print(f"  ⚠ {w}")

    pdf_dirs = [
        Path(__file__).parent / "samples",
        Path(__file__).parent,
        Path(__file__).parent.parent,
    ]
    pdfs: list[Path] = []
    for d in pdf_dirs:
        pdfs.extend(scan_pdf_directory(d))
    pdfs = list(dict.fromkeys(pdfs))

    print(f"\n[PDF 실파일] 발견: {len(pdfs)}개")
    if pdfs:
        from parser import parse_inbody_pdf

        for pdf in pdfs:
            print(f"  → {pdf.name} 파싱 중...")
            try:
                data = pdf.read_bytes()
                r = normalize_inbody_result(parse_inbody_pdf(data))
                print(
                    f"    name={r.name}, phase={r.phase_angle}, "
                    f"hist={len(r.weight_history)}회, bmr={r.bmr.value}"
                )
            except Exception as exc:
                print(f"    FAIL: {exc}")
    else:
        print("  (samples/ 폴더에 PDF를 넣으면 OCR 실파일 QA가 추가됩니다)")

    passed = sum(1 for r in all_reports if r.ok)
    total = len(all_reports)
    print(f"\n{'=' * 60}")
    print(f"픽스처 시나리오: {passed}/{total} PASS")
    if passed < total:
        print("실패 시나리오:")
        for r in all_reports:
            if not r.ok:
                fails = [c.name for c in r.checks if not c.passed]
                print(f"  - {r.id}: {', '.join(fails)}")

    out = Path(__file__).parent / "qa_step1_report.json"
    payload = {
        "ocr_ready": ocr_ok,
        "scenarios": [
            {
                "id": r.id,
                "label": r.label,
                "passed": r.ok,
                "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in r.checks],
                "warnings": r.warnings,
            }
            for r in all_reports
        ],
        "pdf_count": len(pdfs),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n리포트 저장: {out.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
