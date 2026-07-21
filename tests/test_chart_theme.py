"""Plotly 다크 테마 테스트."""

from chart_theme import (
    DARK_PALETTE,
    LIGHT_PALETTE,
    chart_layout,
    get_palette,
    gauge_indicator_style,
    is_dark_mode,
    title_style,
)


def test_get_palette_light():
    pal = get_palette(dark=False)
    assert pal.ink == LIGHT_PALETTE.ink
    assert pal.grid == LIGHT_PALETTE.grid


def test_get_palette_dark():
    pal = get_palette(dark=True)
    assert pal.ink == DARK_PALETTE.ink
    assert pal.grid == DARK_PALETTE.grid


def test_chart_layout_uses_palette_ink():
    layout = chart_layout(dark=True, height=200)
    assert layout["font"]["color"] == DARK_PALETTE.ink
    assert layout["yaxis"]["gridcolor"] == DARK_PALETTE.grid


def test_title_style_dark():
    title = title_style("테스트", size=12, dark=True)
    assert title["font"]["color"] == DARK_PALETTE.title


def test_gauge_indicator_style_dark():
    style = gauge_indicator_style(dark=True)
    assert style["number"]["font"]["color"] == DARK_PALETTE.ink
    assert style["gauge_bgcolor"] == DARK_PALETTE.gauge_bg


def test_is_dark_mode_without_streamlit():
    assert is_dark_mode() is False
