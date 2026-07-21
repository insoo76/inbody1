"""기초대사량(BMR) 비교 시각화 — plan2 §3.2."""

from __future__ import annotations

import html

from icons import section_heading_html
from dataclasses import dataclass

from parser import InBodyResult


@dataclass
class BmrReport:
    value: float
    low: float
    high: float
    status: str
    deficit: float | None
    surplus: float | None
    marker_pct: float
    low_pct: float
    high_pct: float
    fill_pct: float
    comment: str
    badge_text: str
    badge_class: str


def _estimate_bmr(result: InBodyResult) -> float | None:
    if result.bmr.value is not None:
        return result.bmr.value
    if result.weight.value and result.height_cm and result.age:
        w, h, a = result.weight.value, result.height_cm, result.age
        if result.gender == "여":
            return 10 * w + 6.25 * h - 5 * a - 161
        return 10 * w + 6.25 * h - 5 * a + 5
    return None


def _estimate_range(value: float) -> tuple[float, float]:
    """참고 범위가 없을 때 현재값 기준 근사 범위."""
    return round(value * 0.97, 1), round(value * 1.12, 1)


def _scale_positions(value: float, low: float, high: float) -> tuple[float, float, float]:
    span = max(high - low, 80.0)
    scale_min = low - span * 0.28
    scale_max = high + span * 0.1
    total = scale_max - scale_min

    def pct(v: float) -> float:
        return max(0.0, min(100.0, (v - scale_min) / total * 100.0))

    return pct(value), pct(low), pct(high)


def _generate_comment(value: float, low: float, high: float, status: str, deficit: float | None) -> str:
    if status == "low" and deficit is not None:
        return (
            f"권장 하한선(**{low:.1f} kcal**) 대비 **{deficit:.1f} kcal 부족**한 상태입니다. "
            "기초대사량은 근육량과 밀접합니다. **단백질 섭취를 늘리고** "
            "**규칙적인 하체 근력 운동**으로 근육을 키우면 BMR 개선에 도움이 됩니다."
        )
    if status == "high":
        surplus = value - high
        return (
            f"권장 상한(**{high:.1f} kcal**)보다 **{surplus:.1f} kcal** 높습니다. "
            "근육량이 많거나 최근 활동·식단 변화의 영향일 수 있습니다. "
            "체중·체지방 추이와 함께 종합적으로 확인하세요."
        )
    return (
        f"기초대사량 **{value:.1f} kcal**로 권장 범위(**{low:.1f}~{high:.1f} kcal**) "
        "안에 있습니다. 현재의 단백질·근력 운동 습관을 유지하세요."
    )


def _badge(status: str, deficit: float | None, surplus: float | None) -> tuple[str, str]:
    if status == "low" and deficit is not None:
        return f"하한 대비 {deficit:.1f} kcal 부족", "warn"
    if status == "high" and surplus is not None:
        return f"상한 대비 +{surplus:.1f} kcal", "high"
    return "권장 범위 내", "good"


def build_bmr_report(result: InBodyResult) -> BmrReport | None:
    value = _estimate_bmr(result)
    if value is None:
        return None

    low = result.bmr.low
    high = result.bmr.high
    if low is None or high is None:
        low, high = _estimate_range(value)

    status = "normal"
    deficit = surplus = None
    if value < low:
        status = "low"
        deficit = round(low - value, 1)
    elif value > high:
        status = "high"
        surplus = round(value - high, 1)

    marker_pct, low_pct, high_pct = _scale_positions(value, low, high)
    if status == "low":
        fill_pct = min(marker_pct, low_pct)
    elif status == "normal":
        fill_pct = marker_pct
    else:
        fill_pct = min(marker_pct, high_pct)

    badge_text, badge_class = _badge(status, deficit, surplus)
    comment = _generate_comment(value, low, high, status, deficit)

    return BmrReport(
        value=round(value, 1),
        low=round(low, 1),
        high=round(high, 1),
        status=status,
        deficit=deficit,
        surplus=surplus,
        marker_pct=marker_pct,
        low_pct=low_pct,
        high_pct=high_pct,
        fill_pct=fill_pct,
        comment=comment,
        badge_text=badge_text,
        badge_class=badge_class,
    )


def render_bmr_widget_html(report: BmrReport) -> str:
    zone_width = max(report.high_pct - report.low_pct, 4.0)
    fill_class = report.badge_class

    return (
        f'<div class="srx-bmr">'
        f'<div class="srx-bmr-head">'
        f'<div>'
        f'{section_heading_html("bmr", "기초대사량 (BMR) 비교")}'
        f'<p class="sub">권장 범위 대비 내 BMR 위치 — 대사 건강 목표 의식</p>'
        f"</div></div>"
        f'<div class="srx-bmr-hero">'
        f'<div class="srx-bmr-current">{report.value:.1f}<span>kcal</span></div>'
        f'<div class="srx-bmr-badge {report.badge_class}">{html.escape(report.badge_text)}</div>'
        f"</div>"
        f'<div class="srx-bmr-track" role="img" aria-label="BMR {report.value} kcal">'
        f'<div class="srx-bmr-zone" style="left:{report.low_pct:.2f}%;width:{zone_width:.2f}%;"></div>'
        f'<div class="srx-bmr-fill {fill_class}" style="width:{report.fill_pct:.2f}%;"></div>'
        f'<div class="srx-bmr-marker" style="left:{report.marker_pct:.2f}%;"></div>'
        f'<div class="srx-bmr-tick low" style="left:{report.low_pct:.2f}%;"></div>'
        f'<div class="srx-bmr-tick high" style="left:{report.high_pct:.2f}%;"></div>'
        f"</div>"
        f'<div class="srx-bmr-scale">'
        f'<span class="low">하한 {report.low:.1f}</span>'
        f'<span class="mid">내 BMR {report.value:.1f}</span>'
        f'<span class="high">상한 {report.high:.1f}</span>'
        f"</div>"
        f'<div class="srx-bmr-stats">'
        f'<div class="stat"><span class="k">내 BMR</span>'
        f'<span class="v">{report.value:.1f} kcal</span></div>'
        f'<div class="stat"><span class="k">권장 하한</span>'
        f'<span class="v">{report.low:.1f} kcal</span></div>'
        f'<div class="stat"><span class="k">권장 상한</span>'
        f'<span class="v">{report.high:.1f} kcal</span></div>'
        f"</div></div>"
    )
