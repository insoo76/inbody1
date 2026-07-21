"""처방 카드 UI — plan2 §3.3 모듈형 카드 디자인 시스템."""

from __future__ import annotations

import html
import re

from icons import icon_html, resolve_icon_key
from prescription import PrescriptionSection

# 타이틀 키워드 → 기본 해시태그
SECTION_TAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("단백질", ("#영양",)),
    ("영양 유지", ("#영양",)),
    ("무기질", ("#영양", "#칼슘")),
    ("수분", ("#수분",)),
    ("체지방", ("#체형",)),
    ("운동", ("#운동",)),
    ("성장", ("#성장",)),
    ("위상각", ("#대사",)),
)

PRIORITY_META: dict[str, tuple[str, str, str, str]] = {
    "높음": ("#B43B2A", "#FCEDEA", "우선", "prio-high"),
    "보통": ("#B86A1C", "#FFF4E8", "권장", "prio-mid"),
    "참고": ("#1F6F8B", "#EAF5F9", "참고", "prio-ref"),
}

PRIORITY_TAGS: dict[str, str] = {
    "높음": "#필수",
    "보통": "#권장",
    "참고": "#참고",
}


def _plain(text: str) -> str:
    return re.sub(r"\*+", "", text).strip()


def _resolve_icon_tags(section: PrescriptionSection) -> tuple[str, list[str]]:
    icon_key = resolve_icon_key(section.title)
    tags: list[str] = []
    for key, defaults in SECTION_TAGS:
        if key in section.title:
            tags = list(defaults)
            break

    prio_tag = PRIORITY_TAGS.get(section.priority)
    if prio_tag and prio_tag not in tags:
        tags.insert(0, prio_tag)
    return icon_key, tags


def _tags_html(tags: list[str]) -> str:
    if not tags:
        return ""
    chips = "".join(f'<span class="srx-card-tag">{html.escape(t)}</span>' for t in tags)
    return f'<div class="srx-card-tags">{chips}</div>'


def _list_block(label: str, items: list[str]) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{html.escape(_plain(item))}</li>" for item in items)
    return (
        f'<div class="srx-card-block">'
        f'<div class="srx-card-block-label">{html.escape(label)}</div>'
        f"<ul>{lis}</ul></div>"
    )


def render_prescription_card(section: PrescriptionSection, index: int = 0) -> str:
    """단일 처방 카드 HTML."""
    fg, bg, label, prio_class = PRIORITY_META.get(
        section.priority, ("#0E6557", "#E7F3EE", section.priority, "prio-mid")
    )
    icon_key, tags = _resolve_icon_tags(section)
    delay = min(0.06 * index, 0.36)

    details = _list_block("현황", section.details)
    actions = _list_block("실천", section.actions)
    blocks = ""
    if details or actions:
        blocks = f'<div class="srx-card-blocks">{details}{actions}</div>'

    return (
        f'<article class="srx-card {prio_class}" style="animation-delay:{delay:.2f}s">'
        f'<header class="srx-card-head">'
        f'<span class="srx-card-icon" aria-hidden="true">{icon_html(icon_key)}</span>'
        f'<div class="srx-card-head-text">'
        f'<h3 class="srx-card-title">{html.escape(section.title)}</h3>'
        f"{_tags_html(tags)}"
        f"</div>"
        f'<span class="srx-card-prio" style="color:{fg};background:{bg};">'
        f"{html.escape(label)}</span>"
        f"</header>"
        f'<p class="srx-card-summary">{html.escape(_plain(section.summary))}</p>'
        f"{blocks}"
        f"</article>"
    )


def render_prescription_cards(sections: list[PrescriptionSection]) -> str:
    """처방 섹션 그리드 HTML."""
    if not sections:
        return ""
    cards = "".join(render_prescription_card(sec, i) for i, sec in enumerate(sections))
    return f'<div class="srx-card-grid">{cards}</div>'
