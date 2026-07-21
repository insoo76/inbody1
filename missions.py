"""데일리 라이프스타일 미션 생성 및 주간 달성률 계산."""

from __future__ import annotations

from dataclasses import dataclass

from parser import InBodyResult
from prescription import PrescriptionReport, _water_target_ml

WEEK_DAYS = ["월", "화", "수", "목", "금", "토", "일"]
GOLD_BADGE_THRESHOLD = 80
MISSION_COUNT = 3


@dataclass
class DailyMission:
    id: str
    title: str
    emoji: str
    priority: str


@dataclass
class MissionProgress:
    missions: list[DailyMission]
    completed: int
    total: int
    rate: float
    has_gold_badge: bool
    message: str


from profile_keys import build_profile_key


def _mission_profile_key(result: InBodyResult) -> str:
    return build_profile_key(result)


def generate_missions(result: InBodyResult, report: PrescriptionReport) -> list[DailyMission]:
    """인바디·처방 결과에서 핵심 미션 3가지를 추출한다."""
    water_ml = _water_target_ml(result)
    is_c_shape = report.body_type.startswith("C")
    is_teen = result.age is not None and result.age < 20
    growth_low = result.growth_score is not None and result.growth_score < 70
    exercise_high = any(s.title == "운동 처방" and s.priority == "높음" for s in report.sections)

    pool: list[tuple[int, DailyMission]] = []

    if result.body_water.status == "low":
        pool.append(
            (
                100,
                DailyMission(
                    id="water",
                    title=f"물 {water_ml}ml 이상 마시기",
                    emoji="💧",
                    priority="높음",
                ),
            )
        )
    else:
        pool.append(
            (
                45,
                DailyMission(
                    id="water",
                    title=f"물 {water_ml}ml 이상 마시기",
                    emoji="💧",
                    priority="보통",
                ),
            )
        )

    if result.protein.status == "low":
        pool.append(
            (
                95,
                DailyMission(
                    id="protein",
                    title="매 끼니 손바닥 크기 단백질(계란/가슴살) 먹기",
                    emoji="🥩",
                    priority="높음",
                ),
            )
        )
    else:
        pool.append(
            (
                50,
                DailyMission(
                    id="protein",
                    title="매 끼니 단백질(닭가슴살/계란) 포함하기",
                    emoji="🥩",
                    priority="보통",
                ),
            )
        )

    if is_c_shape:
        pool.append(
            (
                90,
                DailyMission(
                    id="strength",
                    title="하체 중심 근력 운동 30분 하기",
                    emoji="🏋️",
                    priority="높음",
                ),
            )
        )
    elif exercise_high or result.obesity_pbf in ("경도비만", "비만"):
        pool.append(
            (
                75,
                DailyMission(
                    id="strength",
                    title="주 3회 전신 근력 운동(하체 중심) 완료하기",
                    emoji="🏋️",
                    priority="보통",
                ),
            )
        )
    else:
        pool.append(
            (
                55,
                DailyMission(
                    id="strength",
                    title="전신 근력 운동 또는 스쿼트 3세트 하기",
                    emoji="🏋️",
                    priority="보통",
                ),
            )
        )

    if growth_low or is_teen or result.bmr.status == "low":
        pool.append(
            (
                85,
                DailyMission(
                    id="sleep",
                    title="밤 11시 이전에 취침하기 (7시간 수면)",
                    emoji="🌙",
                    priority="높음" if growth_low else "보통",
                ),
            )
        )
    else:
        pool.append(
            (
                40,
                DailyMission(
                    id="sleep",
                    title="밤 11시 이전에 취침하기 (7시간 수면)",
                    emoji="🌙",
                    priority="참고",
                ),
            )
        )

    if result.mineral.status == "low":
        pool.append(
            (
                88,
                DailyMission(
                    id="mineral",
                    title="유제품·두부·녹색채소로 무기질 챙기기",
                    emoji="🥛",
                    priority="높음",
                ),
            )
        )

    if result.obesity_pbf in ("경도비만", "비만"):
        pool.append(
            (
                70,
                DailyMission(
                    id="steps",
                    title="하루 8,000보 이상 걷기",
                    emoji="👟",
                    priority="보통",
                ),
            )
        )

    pool.sort(key=lambda item: item[0], reverse=True)

    picked: list[DailyMission] = []
    used_ids: set[str] = set()
    for _, mission in pool:
        if mission.id in used_ids:
            continue
        picked.append(mission)
        used_ids.add(mission.id)
        if len(picked) >= MISSION_COUNT:
            break

    return picked[:MISSION_COUNT]


def mission_checkbox_key(mission_id: str, day_index: int, profile_key: str) -> str:
    return f"mission_{profile_key}_{mission_id}_{day_index}"


def count_mission_progress(
    missions: list[DailyMission],
    profile_key: str,
    session_state: dict,
) -> MissionProgress:
    total = len(missions) * len(WEEK_DAYS)
    completed = 0
    for mission in missions:
        for day_index in range(len(WEEK_DAYS)):
            key = mission_checkbox_key(mission.id, day_index, profile_key)
            if session_state.get(key):
                completed += 1

    rate = (completed / total * 100) if total else 0.0
    has_gold = rate >= GOLD_BADGE_THRESHOLD

    if has_gold:
        message = (
            f"이번 주 미션 달성률은 {rate:.0f}%입니다. "
            "다음 InBody 측정 시 긍정적인 변화가 기대됩니다!"
        )
    elif rate >= 50:
        message = f"현재 달성률 {rate:.0f}%. 꾸준히 이어가면 골드 뱃지가 가까워집니다!"
    else:
        message = f"현재 달성률 {rate:.0f}%. 작은 실천부터 차근차근 시작해 보세요."

    return MissionProgress(
        missions=missions,
        completed=completed,
        total=total,
        rate=rate,
        has_gold_badge=has_gold,
        message=message,
    )


def sync_mission_profile(result: InBodyResult, session_state: dict) -> str:
    """측정 프로필 동기화 — 로컬 저장소에서 진행률 복원."""
    from progress_store import ensure_profile_session

    return ensure_profile_session(result, session_state)
