"""SVG 아이콘 시스템 테스트."""

from icons import icon_html, resolve_icon_key, section_heading_html, section_title_html
from rx_cards import render_prescription_card
from prescription import PrescriptionSection


def test_resolve_icon_key_protein():
    assert resolve_icon_key("단백질 섭취") == "protein"


def test_icon_html_returns_svg():
    html_out = icon_html("protein")
    assert "<svg" in html_out
    assert "srx-svg-icon" in html_out


def test_prescription_card_uses_svg_not_emoji():
    section = PrescriptionSection(
        title="단백질 보충",
        priority="높음",
        summary="**요약** 테스트",
        details=["현재 부족"],
        actions=["하루 1회"],
    )
    card = render_prescription_card(section)
    assert "<svg" in card
    assert "🥩" not in card


def test_section_heading_uses_svg_not_emoji():
    heading = section_heading_html("phase", "위상각 트렌드")
    assert "<svg" in heading
    assert "📐" not in heading
    assert "srx-heading-with-icon" in heading


def test_section_title_uses_svg_not_emoji():
    title = section_title_html("slime", "슬라임 성장")
    assert "<svg" in title
    assert "🌱" not in title
    assert "srx-section-title" in title
