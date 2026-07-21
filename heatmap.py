"""2D 인체 실루엣 히트맵 — 부위별 근육·지방 상태 시각화."""

from __future__ import annotations

import base64
import html
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from parser import InBodyResult

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BODY_MODEL_IMAGE = ASSETS_DIR / "body-model-3d.png"

# InBody 5부위 → 세부 측정 구역 (부모 부위, 분할 비율)
SUBZONE_SPECS: tuple[tuple[str, str, str, float], ...] = (
    ("chest", "가슴", "trunk", 0.52),
    ("abdomen", "복부", "trunk", 0.48),
    ("right_upper_arm", "오른팔·상완", "right_arm", 0.48),
    ("right_forearm", "오른팔·전완", "right_arm", 0.52),
    ("left_upper_arm", "왼팔·상완", "left_arm", 0.48),
    ("left_forearm", "왼팔·전완", "left_arm", 0.52),
    ("right_thigh", "오른다리·허벅지", "right_leg", 0.58),
    ("right_calf", "오른발·종아리", "right_leg", 0.42),
    ("left_thigh", "왼다리·허벅지", "left_leg", 0.58),
    ("left_calf", "왼발·종아리", "left_leg", 0.42),
)

SEGMENT_RATIOS: dict[str, float] = {
    "right_arm": 0.10,
    "left_arm": 0.10,
    "trunk": 0.44,
    "right_leg": 0.18,
    "left_leg": 0.18,
}

STATUS_COLORS: dict[str, str] = {
    "normal": "#A8C9B4",
    "muscle_low": "#2563EB",
    "fat_high": "#EA580C",
    "mixed": "#B43B2A",
}

STATUS_LABELS: dict[str, str] = {
    "normal": "표준",
    "muscle_low": "근육 부족",
    "fat_high": "체지방 과다",
    "mixed": "근육↓ · 지방↑",
}

MUSCLE_LOW_THRESHOLD = 0.88

# 3D 모델(viewBox 0 0 200 300) — 골격 윤곽 SVG 경로
BONE_PATHS: dict[str, str] = {
    # 흉곽·늑골 (가슴)
    "chest": (
        "M 100 62 L 104 63 L 118 68 C 124 72 125 78 122 84 "
        "C 118 88 108 90 100 90 C 92 90 82 88 78 84 "
        "C 75 78 76 72 82 68 L 96 63 Z"
        "M 100 66 L 100 86"
    ),
    # 골반·척추 하부 (복부)
    "abdomen": (
        "M 92 90 L 108 90 L 114 96 C 110 104 90 104 86 96 Z"
        "M 98 92 L 102 92 L 101 100 L 99 100 Z"
    ),
    # 오른팔(화면 왼쪽) — 상완골
    "right_upper_arm": (
        "M 45 60 L 47 60 C 48 78 47 94 46 100 C 45.5 101 44.5 101 44 100 "
        "C 43 94 42 78 45 60 Z"
    ),
    "right_forearm": (
        "M 43 104 L 45 104 C 46 118 45 132 44 138 C 43.5 139 42.5 139 42 138 "
        "C 41 132 40 118 43 104 Z"
    ),
    # 왼팔(화면 오른쪽)
    "left_upper_arm": (
        "M 153 60 L 155 60 C 158 78 157 94 156 100 C 155.5 101 154.5 101 154 100 "
        "C 153 94 152 78 153 60 Z"
    ),
    "left_forearm": (
        "M 155 104 L 157 104 C 158 118 157 132 156 138 C 155.5 139 154.5 139 154 138 "
        "C 153 132 152 118 155 104 Z"
    ),
    # 오른다리(화면 왼쪽) — 대퇴골
    "right_thigh": (
        "M 86 118 L 89 118 C 90 150 89 182 88 200 C 87.5 202 85.5 202 85 200 "
        "C 84 182 83 150 86 118 Z"
    ),
    "right_calf": (
        "M 86 206 L 88 206 C 89 232 88 256 87 264 C 86.5 265 85.5 265 85 264 "
        "C 84 256 83 232 86 206 Z"
    ),
    # 왼다리(화면 오른쪽)
    "left_thigh": (
        "M 111 118 L 114 118 C 115 150 114 182 113 200 C 112.5 202 110.5 202 110 200 "
        "C 109 182 108 150 111 118 Z"
    ),
    "left_calf": (
        "M 112 206 L 114 206 C 115 232 114 256 113 264 C 112.5 265 111.5 265 111 264 "
        "C 110 256 109 232 112 206 Z"
    ),
}


@dataclass
class BodyZone:
    zone_id: str
    label: str
    muscle_kg: float | None
    expected_kg: float | None
    status: str
    color: str
    note: str
    parent_id: str = ""


@dataclass
class BodyHeatmapReport:
    zones: list[BodyZone]
    gender: str
    has_data: bool
    summary: str


def _segment_value(result: InBodyResult, parent_id: str) -> float | None:
    mapping = {
        "right_arm": result.right_arm_kg,
        "left_arm": result.left_arm_kg,
        "trunk": result.trunk_kg,
        "right_leg": result.right_leg_kg,
        "left_leg": result.left_leg_kg,
    }
    return mapping.get(parent_id)


def _overall_fat_stressed(result: InBodyResult) -> bool:
    return (
        result.body_fat_mass.status == "high"
        or result.obesity_pbf in ("경도비만", "비만")
        or (result.percent_body_fat is not None and result.percent_body_fat >= 25)
    )


def _zone_fat_stressed(result: InBodyResult, zone_id: str, parent_id: str) -> bool:
    if not _overall_fat_stressed(result):
        return False

    if zone_id == "abdomen":
        return True
    if zone_id == "chest":
        return result.percent_body_fat is not None and result.percent_body_fat >= 22

    if parent_id in {"right_leg", "left_leg"}:
        lower = result.balance_lower or ""
        upper_lower = result.balance_upper_lower or ""
        if zone_id.endswith("_calf"):
            return "불균형" in lower or _overall_fat_stressed(result)
        return "불균형" in lower or "불균형" in upper_lower or _overall_fat_stressed(result)

    if parent_id == "trunk":
        return zone_id == "abdomen"

    return False


def _classify_zone(
    result: InBodyResult,
    zone_id: str,
    parent_id: str,
    value: float | None,
    expected: float | None,
) -> tuple[str, str]:
    muscle_low = False
    fat_high = _zone_fat_stressed(result, zone_id, parent_id)

    if value is not None and expected is not None and expected > 0:
        muscle_low = value / expected < MUSCLE_LOW_THRESHOLD

    if muscle_low and fat_high:
        return "mixed", "근육은 부족하고 체지방은 과다한 부위입니다."
    if fat_high:
        return "fat_high", "체지방이 표준보다 많을 수 있는 부위입니다."
    if muscle_low:
        return "muscle_low", "근육량이 표준보다 낮은 부위입니다."
    return "normal", "표준 범위로 보입니다."


def build_body_heatmap(result: InBodyResult) -> BodyHeatmapReport:
    smm = result.skeletal_muscle_mass
    gender = result.gender if result.gender in ("남", "여") else "남"
    zones: list[BodyZone] = []

    for zone_id, label, parent_id, split_ratio in SUBZONE_SPECS:
        parent_value = _segment_value(result, parent_id)
        parent_ratio = SEGMENT_RATIOS[parent_id]
        parent_expected = round(smm * parent_ratio, 2) if smm else None

        value = round(parent_value * split_ratio, 2) if parent_value is not None else None
        expected = round(parent_expected * split_ratio, 2) if parent_expected is not None else None
        status, note = _classify_zone(result, zone_id, parent_id, value, expected)

        zones.append(
            BodyZone(
                zone_id=zone_id,
                label=label,
                muscle_kg=value,
                expected_kg=expected,
                status=status,
                color=STATUS_COLORS[status],
                note=note,
                parent_id=parent_id,
            )
        )

    has_data = any(z.muscle_kg is not None for z in zones)
    low_count = sum(1 for z in zones if z.status in ("muscle_low", "mixed"))
    fat_count = sum(1 for z in zones if z.status in ("fat_high", "mixed"))

    if not has_data:
        summary = "부위별 근육 데이터가 없어 전신 패턴을 추정할 수 없습니다."
    elif low_count and fat_count:
        summary = (
            f"세부 {len(zones)}개 구역 중 근육 부족 {low_count}곳, "
            f"체지방 과다 {fat_count}곳이 확인됩니다."
        )
    elif low_count:
        summary = f"세부 구역 중 근육 부족 {low_count}곳이 보입니다. 상·하체 근력 운동을 우선하세요."
    elif fat_count:
        summary = f"세부 구역 중 체지방 과다 {fat_count}곳이 보입니다. 복부·하체 관리에 집중하세요."
    else:
        summary = "가슴·복부·팔·다리 세부 구역이 비교적 균형적입니다."

    return BodyHeatmapReport(zones=zones, gender=gender, has_data=has_data, summary=summary)


@lru_cache(maxsize=1)
def _body_model_data_uri() -> str:
    image_bytes = BODY_MODEL_IMAGE.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _bone_svg_paths(zones: list[BodyZone]) -> str:
    """체지방 과다·복합 주의 구역만 골격 path에 색상을 입힌다."""
    parts: list[str] = []
    for zone in zones:
        if zone.status not in ("fat_high", "mixed"):
            continue
        path = BONE_PATHS.get(zone.zone_id)
        if not path:
            continue
        opacity = 0.92 if zone.status == "fat_high" else 0.88
        parts.append(
            f'<path class="srx-bone-{zone.status}" d="{path}" fill="{zone.color}" '
            f'fill-opacity="{opacity}" stroke="rgba(255,255,255,0.4)" stroke-width="0.5" />'
        )
    return "".join(parts)


def render_body_figure(report: BodyHeatmapReport) -> str:
    """3D 인체 모델 골격 위에만 상태 색상을 표시한다."""
    gender_label = "여성" if report.gender == "여" else "남성"
    model_class = "female" if report.gender == "여" else "male"
    bone_paths = _bone_svg_paths(report.zones)

    return (
        f'<div class="srx-heatmap-figure-wrap">'
        f'<div class="srx-heatmap-figure {model_class}">'
        f'<img class="srx-heatmap-base" src="{_body_model_data_uri()}" '
        f'alt="{html.escape(gender_label)} 3D 인체 모델" />'
        f'<svg class="srx-heatmap-bones" viewBox="0 0 200 300" preserveAspectRatio="xMidYMid meet" '
        f'aria-hidden="true">{bone_paths}</svg>'
        f"</div>"
        f'<div class="srx-heatmap-gender">{html.escape(gender_label)} 3D 인체 모델 · 체지방 과다 골격 표시</div>'
        f"</div>"
    )


def render_body_svg(report: BodyHeatmapReport) -> str:
    """하위 호환 alias."""
    return render_body_figure(report)


def render_legend_html() -> str:
    items = [
        ("muscle_low", "근육 부족 (푸른색)"),
        ("fat_high", "체지방 과다 (주황·빨강)"),
        ("normal", "표준 (연그린)"),
        ("mixed", "복합 주의"),
    ]
    chips = "".join(
        f'<span class="srx-heatmap-legend-item">'
        f'<i style="background:{STATUS_COLORS[key]}"></i>{html.escape(label)}</span>'
        for key, label in items
    )
    return f'<div class="srx-heatmap-legend">{chips}</div>'


def render_zone_cards_html(zones: list[BodyZone]) -> str:
    cards: list[str] = []
    for zone in zones:
        value_text = f"{zone.muscle_kg:.2f} kg" if zone.muscle_kg is not None else "—"
        expected_text = f"{zone.expected_kg:.2f} kg" if zone.expected_kg is not None else "—"
        cards.append(
            f'<div class="srx-heatmap-zone {zone.status}">'
            f'<div class="k">{html.escape(zone.label)}</div>'
            f'<div class="v">{html.escape(value_text)}</div>'
            f'<div class="e">기대 {html.escape(expected_text)}</div>'
            f'<div class="s">{html.escape(STATUS_LABELS[zone.status])}</div>'
            f"</div>"
        )
    return f'<div class="srx-heatmap-zones">{"".join(cards)}</div>'
