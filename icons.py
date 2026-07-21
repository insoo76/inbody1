"""처방 카드·섹션 제목용 SVG 라인 아이콘."""

from __future__ import annotations

import html

_ICON_SVG: dict[str, str] = {
    "default": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>'
        '<rect x="9" y="3" width="6" height="4" rx="1"/>'
        '<path d="M9 12h6M9 16h6"/>'
        "</svg>"
    ),
    "protein": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M12 3c3 4 5 7 5 10a5 5 0 0 1-10 0c0-3 2-6 5-10z"/>'
        '<path d="M12 14v4"/>'
        "</svg>"
    ),
    "nutrition": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M7 20h10"/><path d="M12 4v16"/>'
        '<path d="M8 8c0-2 1.8-4 4-4s4 2 4 4"/>'
        "</svg>"
    ),
    "mineral": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M12 2 4 7v10l8 5 8-5V7z"/><path d="M12 22V12"/>'
        '<path d="M4 7l8 5 8-5"/>'
        "</svg>"
    ),
    "water": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M12 2.5c3.5 5 6 8.2 6 11.5a6 6 0 1 1-12 0C6 10.7 8.5 7.5 12 2.5z"/>'
        "</svg>"
    ),
    "bodyfat": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>'
        "</svg>"
    ),
    "exercise": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="m6.5 6.5 11 11"/><path d="M8 8 6 6 4 8l2 2"/>'
        '<path d="m18 18-2-2 2-2 2 2-2 2"/><path d="m14 10 4-4"/>'
        "</svg>"
    ),
    "growth": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M4 20h16"/><path d="M7 16l3-6 3 3 4-8"/>'
        "</svg>"
    ),
    "phase": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M4 20V4"/><path d="M4 20h16"/><path d="M8 16l4-8 4 5 4-9"/>'
        "</svg>"
    ),
    "bmr": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M12 3c2 4 4 6.5 4 9a4 4 0 1 1-8 0c0-2.5 2-5 4-9z"/>'
        '<path d="M12 14v3"/>'
        "</svg>"
    ),
    "heatmap": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="12" cy="12" r="9"/>'
        '<circle cx="12" cy="12" r="5"/>'
        '<circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>'
        "</svg>"
    ),
    "mission": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M9 11l3 3L22 4"/>'
        '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>'
        "</svg>"
    ),
    "slime": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M12 22V12"/><path d="M12 12c-3-4-7-4-7-8a7 7 0 0 1 14 0c0 4-4 4-7 8z"/>'
        "</svg>"
    ),
    "multidim": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<polygon points="12 2 20 7 20 17 12 22 4 17 4 7"/>'
        '<path d="M12 22V12"/><path d="M20 7 12 12 4 7"/>'
        "</svg>"
    ),
    "score": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M12 2a10 10 0 1 0 10 10"/>'
        '<path d="M12 6v6l4 2"/>'
        '<path d="M16.5 3.5 19 6"/>'
        "</svg>"
    ),
    "trend": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M4 20V4"/><path d="M4 20h16"/>'
        '<path d="M7 15l4-4 3 3 5-7"/>'
        "</svg>"
    ),
    "meal": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M4 11h16"/><path d="M12 3v14"/>'
        '<path d="M8 7c0-2 1.8-4 4-4s4 2 4 4"/><path d="M6 21h12"/>'
        "</svg>"
    ),
    "breakfast": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4'
        'M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
        "</svg>"
    ),
    "lunch": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M3 11h18v2a7 7 0 0 1-7 7H10a7 7 0 0 1-7-7v-2z"/>'
        '<path d="M7 11V7a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2"/><path d="M13 11V6a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v5"/>'
        "</svg>"
    ),
    "dinner": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M12 3c2.5 3.5 5 6 5 9a5 5 0 1 1-10 0c0-3 2.5-5.5 5-9z"/>'
        '<path d="M9 21h6"/>'
        "</svg>"
    ),
    "snack": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M12 4c3 2 5 4.5 5 8a5 5 0 1 1-10 0c0-3.5 2-6 5-8z"/>'
        '<path d="M8 20h8"/>'
        "</svg>"
    ),
    "calories": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M12 3c2 4 4 6.5 4 9a4 4 0 1 1-8 0c0-2.5 2-5 4-9z"/>'
        "</svg>"
    ),
}

_SECTION_ICON_KEYS: tuple[tuple[str, str], ...] = (
    ("단백질", "protein"),
    ("영양 유지", "nutrition"),
    ("무기질", "mineral"),
    ("수분", "water"),
    ("체지방", "bodyfat"),
    ("운동", "exercise"),
    ("성장", "growth"),
    ("위상각", "phase"),
)


def resolve_icon_key(title: str) -> str:
    for keyword, key in _SECTION_ICON_KEYS:
        if keyword in title:
            return key
    return "default"


def icon_html(key: str) -> str:
    svg = _ICON_SVG.get(key, _ICON_SVG["default"])
    return f'<span class="srx-svg-icon" data-icon="{html.escape(key)}">{svg}</span>'


def section_heading_html(
    icon_key: str,
    title: str,
    *,
    tag: str = "h3",
    extra_class: str = "title",
) -> str:
    """패널 내부 `<h3 class="title">` — 아이콘 + 제목."""
    return (
        f'<{tag} class="{extra_class} srx-heading-with-icon">'
        f"{icon_html(icon_key)}"
        f"<span>{html.escape(title)}</span>"
        f"</{tag}>"
    )


def section_title_html(icon_key: str, title: str) -> str:
    """`<div class="srx-section-title">` — 아이콘 + 제목."""
    return (
        f'<div class="srx-section-title srx-heading-with-icon">'
        f"{icon_html(icon_key)}"
        f"<span>{html.escape(title)}</span>"
        f"</div>"
    )
