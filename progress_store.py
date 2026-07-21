"""미션·주간 플랜 진행률 로컬 저장 및 재측정 진화 연동."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parser import InBodyResult
from prescription import PrescriptionReport
from profile_keys import build_profile_key, build_user_key

STORE_VERSION = 1
STORE_DIR = Path(__file__).resolve().parent / ".somarx"
STORE_PATH = STORE_DIR / "progress.json"

BODY_TYPE_RANK = {"C": 0, "?": 1, "I": 2, "D": 3}


@dataclass
class BodyEvolutionEvent:
    from_key: str
    to_key: str
    from_label: str
    to_label: str
    message: str


def _body_type_key(body_type: str) -> str:
    if body_type.startswith("C"):
        return "C"
    if body_type.startswith("D"):
        return "D"
    if body_type.startswith("I"):
        return "I"
    return "?"


def _persona_label(key: str) -> str:
    labels = {
        "C": "🌱 새싹 슬라임",
        "I": "🐼 대나무 대리",
        "D": "🐯 아기 호랑이",
        "?": "✨ 성장형 탐험가",
    }
    return labels.get(key, labels["?"])


def _empty_store() -> dict[str, Any]:
    return {"version": STORE_VERSION, "profiles": {}, "users": {}}


def _load_store() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return _empty_store()
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_store()
    if data.get("version") != STORE_VERSION:
        data["version"] = STORE_VERSION
    data.setdefault("profiles", {})
    data.setdefault("users", {})
    return data


def _save_store(data: dict[str, Any]) -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _progress_keys_for_profile(profile_key: str, session_state: dict) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    prefixes = (f"mission_{profile_key}_", f"wplan_done_{profile_key}_")
    for key, value in session_state.items():
        if isinstance(value, bool) and any(key.startswith(p) for p in prefixes):
            checks[key] = value
    return checks


def save_profile_progress(profile_key: str, session_state: dict) -> None:
    checks = _progress_keys_for_profile(profile_key, session_state)
    if not checks:
        return
    data = _load_store()
    data["profiles"][profile_key] = {
        "checks": checks,
        "updated_at": _now_iso(),
    }
    _save_store(data)


def load_profile_progress(profile_key: str, session_state: dict) -> None:
    data = _load_store()
    entry = data["profiles"].get(profile_key)
    if not entry:
        return
    for key, value in entry.get("checks", {}).items():
        if isinstance(value, bool):
            session_state[key] = value


def ensure_profile_session(result: InBodyResult, session_state: dict) -> str:
    """프로필 전환 시 디스크 ↔ session_state 동기화."""
    profile_key = build_profile_key(result)
    active = session_state.get("somarx_active_profile_key")
    if active != profile_key:
        if active:
            save_profile_progress(active, session_state)
        load_profile_progress(profile_key, session_state)
        session_state["somarx_active_profile_key"] = profile_key
    return profile_key


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def detect_body_evolution(
    prev_type: str | None,
    curr_type: str,
) -> BodyEvolutionEvent | None:
    if not prev_type or prev_type == curr_type:
        return None
    prev_rank = BODY_TYPE_RANK.get(prev_type, 1)
    curr_rank = BODY_TYPE_RANK.get(curr_type, 1)
    if curr_rank <= prev_rank:
        return None
    return BodyEvolutionEvent(
        from_key=prev_type,
        to_key=curr_type,
        from_label=_persona_label(prev_type),
        to_label=_persona_label(curr_type),
        message=(
            f"새 InBody 결과 기준 체형이 개선되었어요! "
            f"{_persona_label(prev_type)} → {_persona_label(curr_type)}(으)로 진화했습니다."
        ),
    )


def bootstrap_user_progress(
    result: InBodyResult,
    report: PrescriptionReport,
    session_state: dict,
) -> BodyEvolutionEvent | None:
    """앱 진입 시 진행률 복원 + 재측정 진화 판정."""
    user_key = build_user_key(result)
    profile_key = ensure_profile_session(result, session_state)
    curr_type = _body_type_key(report.body_type)

    data = _load_store()
    users = data["users"]
    user = users.get(user_key, {})
    prev_profile = user.get("last_profile_key")
    prev_type = user.get("last_body_type_key")

    evolution: BodyEvolutionEvent | None = None
    if prev_profile and prev_profile != profile_key and prev_type:
        evolution = detect_body_evolution(prev_type, curr_type)

    users[user_key] = {
        "name": result.name or user.get("name", ""),
        "last_profile_key": profile_key,
        "last_body_type_key": curr_type,
        "last_test_datetime": result.test_datetime or "",
        "measurement_count": (
            int(user.get("measurement_count", 0)) + 1
            if prev_profile and prev_profile != profile_key
            else max(int(user.get("measurement_count", 0)), 1)
        ),
        "updated_at": _now_iso(),
    }

    data["users"] = users
    _save_store(data)

    if evolution:
        session_state["somarx_body_evolution"] = {
            "from_key": evolution.from_key,
            "to_key": evolution.to_key,
            "from_label": evolution.from_label,
            "to_label": evolution.to_label,
            "message": evolution.message,
        }
    return evolution


def commit_user_progress(result: InBodyResult, session_state: dict) -> None:
    """현재 세션의 체크 상태를 디스크에 저장."""
    profile_key = session_state.get("somarx_active_profile_key") or build_profile_key(result)
    save_profile_progress(profile_key, session_state)

    user_key = build_user_key(result)
    data = _load_store()
    user = data["users"].setdefault(user_key, {})
    user["name"] = result.name or user.get("name", "")
    user["last_profile_key"] = profile_key
    user["updated_at"] = _now_iso()
    _save_store(data)


def get_body_evolution(session_state: dict) -> BodyEvolutionEvent | None:
    raw = session_state.get("somarx_body_evolution")
    if not raw or not isinstance(raw, dict):
        return None
    return BodyEvolutionEvent(
        from_key=str(raw.get("from_key", "?")),
        to_key=str(raw.get("to_key", "?")),
        from_label=str(raw.get("from_label", "")),
        to_label=str(raw.get("to_label", "")),
        message=str(raw.get("message", "")),
    )


def render_body_evolution_html(event: BodyEvolutionEvent) -> str:
    import html

    return (
        f'<div class="srx-body-evolution">'
        f'<div class="burst">🎊</div>'
        f'<div class="from">{html.escape(event.from_label.split()[0])}</div>'
        f'<div class="arrow">→</div>'
        f'<div class="to">{html.escape(event.to_label.split()[0])}</div>'
        f'<p class="msg">{html.escape(event.message)}</p>'
        f"</div>"
    )
