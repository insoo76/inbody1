"""프로필·사용자 식별 키 (미션·주간플랜·저장소 공용)."""

from __future__ import annotations

import re

from parser import InBodyResult


def build_profile_key(result: InBodyResult) -> str:
    """측정 1회(결과지) 단위 키."""
    raw = "|".join(
        [
            result.name or "",
            result.test_datetime or "",
            str(result.weight.value or ""),
            str(result.skeletal_muscle_mass or ""),
        ]
    )
    return re.sub(r"[^\w\-|]", "_", raw)


def build_user_key(result: InBodyResult) -> str:
    """동일인 재측정 시에도 유지되는 키 (이름 기준)."""
    name = (result.name or "anonymous").strip()
    return re.sub(r"[^\w\-|가-힣]", "_", name) or "anonymous"
