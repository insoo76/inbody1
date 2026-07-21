"""다차원 상태 분석 — 방사형 밸런스 차트 & 사분면 포지셔닝 맵."""

from __future__ import annotations

from dataclasses import dataclass

import plotly.graph_objects as go

from chart_theme import chart_layout, get_palette, title_style
from parser import InBodyResult, RangeValue
from prescription import PrescriptionReport

RADAR_LABELS = ["체수분", "단백질", "무기질", "골격근량", "체지방량"]

QUADRANT_LABELS = {
    "obese": "1사분면 · 비만형",
    "skinny_fat": "2사분면 · 마른 비만형",
    "slim": "3사분면 · 건강/슬림형",
    "muscular": "4사분면 · 근육형",
}


@dataclass
class MultidimAnalysis:
    radar_labels: list[str]
    radar_scores: list[float]
    radar_ideal: list[float]
    smm: float
    pbf: float
    quadrant_key: str
    quadrant_label: str
    target_smm: float
    target_pbf: float
    has_radar: bool
    has_quadrant: bool
    summary: str


def _chart_layout(**kwargs) -> dict:
    base = dict(margin=dict(l=48, r=28, t=36, b=36))
    base.update(kwargs)
    return chart_layout(**base)


def _normalize_range(rv: RangeValue) -> float | None:
    if rv.value is None or rv.low is None or rv.high is None or rv.high == rv.low:
        return None
    mid = (rv.low + rv.high) / 2
    span = (rv.high - rv.low) / 2
    if not span:
        return 100.0
    score = 100 + ((rv.value - mid) / span) * 20
    return max(45.0, min(155.0, score))


def _normalize_smm(result: InBodyResult) -> float | None:
    smm = result.skeletal_muscle_mass
    weight = result.weight.value
    if smm is None or not weight:
        return None
    ratio = 0.44 if result.gender != "여" else 0.38
    expected = weight * ratio
    if not expected:
        return None
    score = 100 + ((smm - expected) / expected) * 35
    return max(45.0, min(155.0, score))


def _collect_radar_scores(result: InBodyResult) -> tuple[list[str], list[float]]:
    specs: list[tuple[str, float | None]] = [
        ("체수분", _normalize_range(result.body_water)),
        ("단백질", _normalize_range(result.protein)),
        ("무기질", _normalize_range(result.mineral)),
        ("골격근량", _normalize_smm(result)),
        ("체지방량", _normalize_range(result.body_fat_mass)),
    ]
    labels = [name for name, score in specs if score is not None]
    scores = [score for _, score in specs if score is not None]
    return labels, scores


def _pbf_midline(gender: str | None) -> float:
    return 28.0 if gender == "여" else 20.0


def _smm_midline(result: InBodyResult) -> float:
    weight = result.weight.value or 60.0
    ratio = 0.40 if result.gender != "여" else 0.35
    return weight * ratio


def _classify_quadrant(smm: float, pbf: float, result: InBodyResult) -> tuple[str, str]:
    smm_mid = _smm_midline(result)
    pbf_mid = _pbf_midline(result.gender)

    high_smm = smm >= smm_mid
    low_pbf = pbf <= pbf_mid

    if high_smm and low_pbf:
        return "muscular", QUADRANT_LABELS["muscular"]
    if not high_smm and low_pbf:
        return "slim", QUADRANT_LABELS["slim"]
    if high_smm and not low_pbf:
        return "obese", QUADRANT_LABELS["obese"]
    return "skinny_fat", QUADRANT_LABELS["skinny_fat"]


def _compute_target(smm: float, pbf: float, result: InBodyResult) -> tuple[float, float]:
    smm_mid = _smm_midline(result)
    pbf_mid = _pbf_midline(result.gender)

    target_smm = max(smm, smm_mid * 1.05)
    target_pbf = min(pbf, pbf_mid * 0.95)

    if abs(target_smm - smm) < 0.2:
        target_smm = smm_mid * 1.12
    if abs(target_pbf - pbf) < 0.5:
        target_pbf = pbf_mid * 0.85

    return round(target_smm, 1), round(target_pbf, 1)


def build_multidim_analysis(result: InBodyResult, report: PrescriptionReport | None = None) -> MultidimAnalysis:
    radar_labels, radar_scores = _collect_radar_scores(result)
    smm = result.skeletal_muscle_mass
    pbf = result.percent_body_fat

    has_radar = len(radar_scores) >= 3
    has_quadrant = smm is not None and pbf is not None

    quadrant_key = quadrant_label = ""
    target_smm = target_pbf = 0.0
    if has_quadrant:
        quadrant_key, quadrant_label = _classify_quadrant(smm, pbf, result)
        target_smm, target_pbf = _compute_target(smm, pbf, result)

    parts: list[str] = []
    if has_radar:
        weak = [label for label, score in zip(radar_labels, radar_scores) if score < 92]
        if weak:
            parts.append(f"방사형 차트에서 {', '.join(weak)} 항목이 표준보다 낮게 치우쳐 있습니다.")
        else:
            parts.append("영양·근육·체지방 밸런스가 비교적 균형적입니다.")
    if has_quadrant:
        parts.append(f"현재 위치는 {quadrant_label} 구간입니다.")
        if quadrant_key != "muscular":
            parts.append(
                f"목표 방향은 골격근량 {target_smm}kg · 체지방률 {target_pbf}% 부근입니다."
            )
        else:
            parts.append("근육형 구간에 가까우니 현재 루틴을 유지하세요.")

    summary = " ".join(parts) if parts else "분석에 필요한 지표가 부족합니다."

    return MultidimAnalysis(
        radar_labels=radar_labels,
        radar_scores=radar_scores,
        radar_ideal=[100.0] * len(radar_labels),
        smm=smm or 0.0,
        pbf=pbf or 0.0,
        quadrant_key=quadrant_key,
        quadrant_label=quadrant_label,
        target_smm=target_smm,
        target_pbf=target_pbf,
        has_radar=has_radar,
        has_quadrant=has_quadrant,
        summary=summary,
    )


def make_radar_chart(analysis: MultidimAnalysis) -> go.Figure:
    pal = get_palette()
    fig = go.Figure()
    if not analysis.has_radar:
        fig.update_layout(**_chart_layout(height=320))
        return fig

    labels = analysis.radar_labels + [analysis.radar_labels[0]]
    ideal = analysis.radar_ideal + [analysis.radar_ideal[0]]
    current = analysis.radar_scores + [analysis.radar_scores[0]]

    fig.add_trace(
        go.Scatterpolar(
            r=ideal,
            theta=labels,
            name="이상 균형",
            line=dict(color=pal.ideal_line, width=2, dash="dot"),
            fill="toself",
            fillcolor=pal.ideal_fill,
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=current,
            theta=labels,
            name="현재",
            line=dict(color="#2563EB", width=3),
            fill="toself",
            fillcolor="rgba(37, 99, 235, 0.28)",
        )
    )
    fig.update_layout(
        **_chart_layout(
            height=320,
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[60, 140],
                    tickvals=[70, 85, 100, 115, 130],
                    gridcolor=pal.polar_grid,
                    tickfont=dict(color=pal.muted, size=10),
                ),
                angularaxis=dict(gridcolor=pal.polar_grid, tickfont=dict(color=pal.muted, size=10)),
            ),
            legend=dict(orientation="h", y=-0.08, bgcolor="rgba(0,0,0,0)", font=dict(color=pal.ink)),
            title=title_style("방사형 밸런스", size=14),
        )
    )
    return fig


def make_quadrant_chart(analysis: MultidimAnalysis, result: InBodyResult) -> go.Figure:
    pal = get_palette()
    fig = go.Figure()
    if not analysis.has_quadrant:
        fig.update_layout(**_chart_layout(height=320))
        return fig

    smm_mid = _smm_midline(result)
    pbf_mid = _pbf_midline(result.gender)
    smm_pad = max(4.0, analysis.smm * 0.18)
    pbf_pad = max(6.0, analysis.pbf * 0.25)

    x_min, x_max = smm_mid - smm_pad * 1.4, smm_mid + smm_pad * 1.8
    y_min, y_max = pbf_mid - pbf_pad * 1.5, pbf_mid + pbf_pad * 1.5

    fig.add_shape(type="rect", x0=x_min, x1=smm_mid, y0=y_min, y1=pbf_mid, fillcolor="rgba(31,122,77,0.08)", line_width=0)
    fig.add_shape(type="rect", x0=smm_mid, x1=x_max, y0=y_min, y1=pbf_mid, fillcolor="rgba(14,101,87,0.10)", line_width=0)
    fig.add_shape(type="rect", x0=x_min, x1=smm_mid, y0=pbf_mid, y1=y_max, fillcolor="rgba(180,59,42,0.08)", line_width=0)
    fig.add_shape(type="rect", x0=smm_mid, x1=x_max, y0=pbf_mid, y1=y_max, fillcolor="rgba(234,88,12,0.08)", line_width=0)

    fig.add_vline(x=smm_mid, line_dash="dot", line_color=pal.polar_grid)
    fig.add_hline(y=pbf_mid, line_dash="dot", line_color=pal.polar_grid)

    annotations = [
        dict(x=(x_min + smm_mid) / 2, y=(y_min + pbf_mid) / 2, text="3·슬림", showarrow=False, font=dict(size=10, color="#1F7A4D")),
        dict(x=(smm_mid + x_max) / 2, y=(y_min + pbf_mid) / 2, text="4·근육", showarrow=False, font=dict(size=10, color="#0E6557")),
        dict(x=(x_min + smm_mid) / 2, y=(pbf_mid + y_max) / 2, text="2·마른비만", showarrow=False, font=dict(size=10, color="#B43B2A")),
        dict(x=(smm_mid + x_max) / 2, y=(pbf_mid + y_max) / 2, text="1·비만", showarrow=False, font=dict(size=10, color="#EA580C")),
    ]

    fig.add_trace(
        go.Scatter(
            x=[analysis.smm],
            y=[analysis.pbf],
            mode="markers+text",
            name="현재",
            text=["나"],
            textposition="top center",
            marker=dict(size=14, color="#2563EB", line=dict(width=2, color=pal.marker_line)),
        )
    )

    if analysis.quadrant_key != "muscular":
        fig.add_trace(
            go.Scatter(
                x=[analysis.smm, analysis.target_smm],
                y=[analysis.pbf, analysis.target_pbf],
                mode="lines+markers",
                name="목표 경로",
                line=dict(color="#0E6557", width=2, dash="dash"),
                marker=dict(size=[10, 12], color=["#2563EB", "#0E6557"], line=dict(width=2, color=pal.marker_line)),
            )
        )
        fig.add_annotation(
            x=analysis.target_smm,
            y=analysis.target_pbf,
            ax=analysis.smm,
            ay=analysis.pbf,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.2,
            arrowwidth=2,
            arrowcolor="#0E6557",
            text="목표",
            font=dict(size=11, color=pal.ink),
        )

    fig.update_layout(
        **_chart_layout(
            height=320,
            title=title_style("체형 사분면 맵", size=14),
            xaxis=dict(title="골격근량 (kg) →", range=[x_min, x_max], zeroline=False, tickfont=dict(color=pal.muted)),
            yaxis=dict(title="체지방률 (%) ↑ 낮음", range=[y_max, y_min], zeroline=False, tickfont=dict(color=pal.muted)),
            annotations=annotations,
            showlegend=False,
        )
    )
    return fig
