"""InBody 결과 기반 상세 처방 엔진."""

from __future__ import annotations

from dataclasses import dataclass, field

from parser import InBodyResult


@dataclass
class PrescriptionSection:
    title: str
    priority: str  # 높음 / 보통 / 참고
    summary: str
    details: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass
class PrescriptionReport:
    overall_summary: str
    body_type: str
    risk_flags: list[str]
    sections: list[PrescriptionSection]
    weekly_plan: dict[str, list[str]]
    meal_guide: list[str]
    caution: list[str]


def _muscle_fat_shape(result: InBodyResult) -> str:
    """골격근·지방 막대 형태(C/I/D) 추정.

    InBody 해석:
    - C형: 체중·체지방 대비 골격근(단백질)이 상대적으로 짧음
    - I형: 세 막대가 비슷
    - D형: 골격근이 상대적으로 김
    """
    weight = result.weight.value
    smm = result.skeletal_muscle_mass
    fat = result.body_fat_mass.value

    # 단백질 부족 + 체지방 정상/과다 → 전형적 C형
    if result.protein.status == "low" and result.body_fat_mass.status in (
        "normal",
        "high",
        "unknown",
    ):
        if result.obesity_pbf in ("경도비만", "비만", "표준") or result.body_fat_mass.status in (
            "normal",
            "high",
        ):
            return "C형 (근력 부족형)"

    if weight is None or smm is None or fat is None:
        if result.protein.status == "low":
            return "C형 (근력 부족형)"
        return "판정불가"

    w_idx = 100.0
    if result.weight.low and result.weight.high:
        mid = (result.weight.low + result.weight.high) / 2
        w_idx = (weight / mid) * 100 if mid else 100
    elif result.weight.status == "normal":
        w_idx = 100.0

    # InBody 막대 100%는 이상체중 대비 골격근; 체중 대비 비율로 근사
    expected_ratio = 0.44 if result.gender != "여" else 0.38
    expected_smm = weight * expected_ratio
    s_idx = (smm / expected_smm) * 100 if expected_smm else 100

    if result.body_fat_mass.low and result.body_fat_mass.high:
        f_mid = (result.body_fat_mass.low + result.body_fat_mass.high) / 2
        f_idx = (fat / f_mid) * 100 if f_mid else 100
    else:
        f_idx = 100

    if s_idx + 6 < w_idx and s_idx + 6 < f_idx:
        return "C형 (근력 부족형)"
    if s_idx > w_idx + 5 and s_idx > f_idx + 5:
        return "D형 (근력 우세형)"
    if result.protein.status == "low" and f_idx >= 90:
        return "C형 (근력 부족형)"
    return "I형 (균형형)"


def _protein_target_g(result: InBodyResult) -> tuple[float, float]:
    weight = result.weight.value or 60
    # 성장기·근력 부족 시 체중 1.4~1.8g/kg, 일반 1.2~1.6
    if result.age is not None and result.age < 20:
        return round(weight * 1.4, 0), round(weight * 1.8, 0)
    if result.skeletal_muscle_mass and result.weight.value:
        if result.skeletal_muscle_mass < result.weight.value * 0.38:
            return round(weight * 1.4, 0), round(weight * 1.8, 0)
    return round(weight * 1.2, 0), round(weight * 1.6, 0)


def _water_target_ml(result: InBodyResult) -> int:
    weight = result.weight.value or 60
    base = int(weight * 35)  # ml
    if result.body_water.status == "low":
        base = int(weight * 40)
    return max(1800, min(base, 3500))


def _calories(result: InBodyResult) -> dict[str, int]:
    bmr = result.bmr.value
    if bmr is None and result.weight.value and result.height_cm and result.age:
        # Mifflin-St Jeor 근사
        w, h, a = result.weight.value, result.height_cm, result.age
        if result.gender == "여":
            bmr = 10 * w + 6.25 * h - 5 * a - 161
        else:
            bmr = 10 * w + 6.25 * h - 5 * a + 5
    if bmr is None:
        bmr = 1400
    # 활동계수: 성장기·근력강화 목표면 lightly~moderately active
    tdee = int(bmr * 1.55)
    # 체재구성: 근증가 + 지방 관리 → 소폭 잉여 또는 유지
    if result.obesity_pbf in ("경도비만", "비만") and result.nutrition_protein == "부족":
        intake = tdee  # 유지 칼로리에서 단백질↑, 근력운동
        goal = "유지(체재구성)"
    elif result.protein.status == "low" or (
        result.skeletal_muscle_mass and result.weight.value
        and result.skeletal_muscle_mass < result.weight.value * 0.38
    ):
        intake = tdee + 150
        goal = "소폭 증량(근성장)"
    else:
        intake = tdee
        goal = "유지"
    return {
        "bmr": int(bmr),
        "tdee": tdee,
        "intake": int(intake),
        "goal_label": goal,  # type: ignore[dict-item]
    }


def build_prescription(result: InBodyResult) -> PrescriptionReport:
    body_type = _muscle_fat_shape(result)
    flags: list[str] = []
    sections: list[PrescriptionSection] = []

    if result.body_water.status == "low":
        flags.append("체수분 부족")
    if result.protein.status == "low":
        flags.append("단백질 부족")
    if result.mineral.status == "low":
        flags.append("무기질 부족")
    if result.obesity_pbf in ("경도비만", "비만"):
        flags.append(f"체지방률 {result.obesity_pbf}")
    if body_type.startswith("C"):
        flags.append("C형(근력 부족)")
    if result.bmr.status == "low":
        flags.append("기초대사량 낮음")
    if result.balance_upper_lower and "불균형" in result.balance_upper_lower:
        flags.append(f"상하체 {result.balance_upper_lower}")

    # --- 종합 요약 ---
    age_note = ""
    if result.age is not None and result.age < 20:
        age_note = (
            f"현재 {result.age}세로 성장기이므로, 무리한 감량보다 "
            "근육·뼈·영양 보충을 우선합니다. "
        )

    overall = (
        f"{result.name or '회원'}님의 InBody 결과를 종합하면 "
        f"{body_type} 패턴입니다. {age_note}"
    )
    if flags:
        overall += "우선 개선 포인트는 " + ", ".join(f"{f}" for f in flags[:4]) + "입니다."
    else:
        overall += "전반적으로 양호한 편이며, 현재 상태를 유지·강화하는 처방을 권합니다."

    # --- 1. 영양 처방 ---
    p_low, p_high = _protein_target_g(result)
    water_ml = _water_target_ml(result)
    cal = _calories(result)

    nutrition_details = [
        f"목표 섭취 칼로리: 약 {cal['intake']} kcal/일 ({cal['goal_label']}, "
        f"추정 BMR {cal['bmr']} / TDEE {cal['tdee']})",
        f"단백질: {int(p_low)}~{int(p_high)} g/일 "
        f"(체중 1kg당 약 {round(p_low / (result.weight.value or 60), 1)}"
        f"~{round(p_high / (result.weight.value or 60), 1)} g)",
        f"수분: 하루 {water_ml} ml 이상 (체중·체수분 상태 반영)",
    ]
    nutrition_actions = []

    if result.protein.status == "low":
        nutrition_actions.extend(
            [
                "매 끼니 손바닥 1개 분량(약 20~30g)의 단백질 식품 포함",
                "추천: 닭가슴살, 계란, 생선, 두부, 그릭요거트, 저지방 우유, 살코기",
                "운동 후 1시간 이내 단백질 20~30g + 탄수화물 소량 섭취",
            ]
        )
        sections.append(
            PrescriptionSection(
                title="단백질·영양 보충",
                priority="높음",
                summary="단백질이 정상 범위보다 낮아 근육 합성·성장에 불리합니다.",
                details=nutrition_details
                + [
                    f"현재 단백질: {result.protein.value} kg "
                    f"(정상 {result.protein.low}~{result.protein.high} kg)",
                ],
                actions=nutrition_actions,
            )
        )
    else:
        sections.append(
            PrescriptionSection(
                title="영양 유지",
                priority="보통",
                summary="단백질 상태는 양호합니다. 현재 섭취 패턴을 유지하며 질을 높입니다.",
                details=nutrition_details,
                actions=[
                    "하루 3끼 + 필요 시 간식으로 단백질을 분산 섭취",
                    "가공식품·단순당 비중을 줄이고 통곡물·채소를 늘리기",
                ],
            )
        )

    if result.mineral.status == "low":
        sections.append(
            PrescriptionSection(
                title="무기질·뼈 건강",
                priority="높음",
                summary="무기질이 부족해 뼈 밀도·전해질·성장에 부담이 될 수 있습니다.",
                details=[
                    f"현재 무기질: {result.mineral.value} kg "
                    f"(정상 {result.mineral.low}~{result.mineral.high} kg)",
                    "칼슘·마그네슘·아연·철분 섭취를 의식적으로 늘리세요.",
                ],
                actions=[
                    "유제품(우유·요거트·치즈) 하루 1~2회",
                    "멸치·두부·녹색잎채소·견과류·해조류 정기 섭취",
                    "햇볕 노출 또는 비타민 D 충분 섭취(의사와 상담 후 보충제 고려)",
                    "탄산음료·과도한 카페인은 칼슘 배출을 늘릴 수 있어 제한",
                ],
            )
        )
    else:
        sections.append(
            PrescriptionSection(
                title="무기질·뼈 건강 유지",
                priority="보통",
                summary="무기질 상태가 양호합니다. 뼈 건강과 신체 전해질 균형을 위해 현재 패턴을 유지하세요.",
                details=[
                    f"현재 무기질: {result.mineral.value} kg "
                    f"(정상 {result.mineral.low}~{result.mineral.high} kg)"
                    if result.mineral.value else "현재 무기질: 정상 범위 내",
                    "뼈 밀도와 미네랄 균형이 건강하게 유지되고 있습니다.",
                ],
                actions=[
                    "하루 1회 이상 칼슘 식품(유제품, 두부, 뼈째 먹는 생선 등) 섭취 권장",
                    "비타민 D 활성화를 위해 가벼운 낮 야외 활동(햇볕 쬐기) 추천",
                    "카페인 및 나트륨 과다 섭취는 미네랄 배출을 촉진하므로 적정선 유지",
                ],
            )
        )

    if result.body_water.status == "low":
        sections.append(
            PrescriptionSection(
                title="수분·컨디션",
                priority="높음",
                summary="체수분이 정상보다 낮습니다. 탈수·나트륨 과다·근손실과 연관될 수 있습니다.",
                details=[
                    f"현재 체수분: {result.body_water.value} L "
                    f"(정상 {result.body_water.low}~{result.body_water.high} L)",
                    f"목표 수분 섭취: {water_ml} ml/일",
                ],
                actions=[
                    "기상 직후 물 300~400ml, 이후 1~2시간마다 200ml씩",
                    "운동 전·중·후 수분 보충 (땀이 많으면 전해질 포함)",
                    "짠 음식·단 음료를 줄이고 물·무가당 차 위주로",
                    "검사 전날 과도한 운동·사우나·단식은 수치를 왜곡할 수 있음",
                ],
            )
        )
    else:
        sections.append(
            PrescriptionSection(
                title="수분·컨디션 유지",
                priority="보통",
                summary="체수분 상태가 양호합니다. 세포 활성도와 대사 순환을 위해 꾸준한 수분 보충을 이어가세요.",
                details=[
                    f"현재 체수분: {result.body_water.value} L "
                    f"(정상 {result.body_water.low}~{result.body_water.high} L)"
                    if result.body_water.value else "현재 체수분: 정상 범위 내",
                    f"목표 수분 섭취: {water_ml} ml/일",
                ],
                actions=[
                    "아침 기상 후 물 한 잔으로 신진대사 깨우기",
                    "운동 중 및 운동 후에 손실되는 수분을 적절히 보충",
                    "단 음료나 커피 대신 깨끗한 물 또는 무가당 차 위주 섭취 습관 유지",
                ],
            )
        )

    # --- 2. 체지방·비만 ---
    fat_priority = "보통"
    fat_summary = "체지방 상태는 대체로 관리 가능한 범위입니다."
    fat_actions = [
        "급격한 칼로리 제한은 피하고, 근력운동 + 단백질로 체재구성",
        "유산소는 주 2~3회, 20~40분 (빠르게 걷기·자전거·수영)",
    ]
    if result.obesity_pbf in ("경도비만", "비만") or result.body_fat_mass.status == "high":
        fat_priority = "높음"
        fat_summary = (
            f"체지방률 {result.percent_body_fat}%로 "
            f"{result.obesity_pbf or '과다'} 경향입니다. "
            "체중 감량보다 근육량 유지·증가와 지방 비율 개선이 목표입니다."
        )
        fat_actions = [
            "주간 체중 변화 ±0.25kg 이내로 천천히 관리",
            "야식·가당음료·튀김류를 먼저 줄이기",
            "하루 총 걸음 8,000~10,000보 + 주 2~3회 유산소",
            "수면 7~8시간 확보 (수면 부족은 체지방 증가와 관련)",
        ]
    elif result.body_fat_mass.status == "low":
        fat_priority = "보통"
        fat_summary = "체지방이 다소 낮을 수 있습니다. 과도한 감량·절식은 피하세요."
        fat_actions = [
            "건강한 지방(아보카도, 견과, 올리브유, 생선) 적절히 포함",
            "에너지 섭취가 너무 낮지 않은지 점검",
        ]

    sections.append(
        PrescriptionSection(
            title="체지방·체형 관리",
            priority=fat_priority,
            summary=fat_summary,
            details=[
                f"BMI: {result.bmi} ({result.obesity_bmi or '-'})",
                f"체지방률: {result.percent_body_fat}% ({result.obesity_pbf or '-'})",
                f"체지방량: {result.body_fat_mass.value} kg",
                f"골격근량: {result.skeletal_muscle_mass} kg",
                f"골격근·지방 형태: {body_type}",
            ],
            actions=fat_actions,
        )
    )

    # --- 3. 운동 처방 ---
    is_c_shape = body_type.startswith("C")
    is_teen = result.age is not None and result.age < 20
    exercise = PrescriptionSection(
        title="운동 처방",
        priority="높음" if is_c_shape else "보통",
        summary=(
            "C형(근력 부족형)으로, 유산소보다 저항성 운동(근력 운동)을 우선해야 합니다."
            if is_c_shape
            else "현재 체형을 유지·강화하기 위한 균형 잡힌 운동이 필요합니다."
        ),
        details=[
            "주 3~4회 전신 근력 운동 (휴식일 확보)",
            "세트당 8~12회, 2~4세트, 점진적 과부하",
            "유산소는 근력 운동 후 또는 별도 날에 중강도",
        ],
        actions=[],
    )

    upper_lower_imbalance = result.balance_upper_lower and "불균형" in result.balance_upper_lower
    exercise.actions = [
        "하체: 스쿼트, 런지, 루마니안 데드리프트, 레그프레스",
        "상체: 푸시업/벤치프레스, 로우, 풀업/랫풀다운, 오버헤드 프레스",
        "코어: 플랭크, 데드버그, 사이드 플랭크",
        "워밍업 5~10분 + 쿨다운·스트레칭 5~10분",
    ]
    if upper_lower_imbalance:
        exercise.actions.insert(
            0,
            f"상하체 {result.balance_upper_lower}: 하체·엉덩이 근력과 상체 당기기 동작을 균형 있게 배치",
        )
    if result.balance_upper and "불균형" in result.balance_upper:
        exercise.actions.append(
            f"상체 좌우 {result.balance_upper}: 단측(한팔) 운동으로 약한 쪽을 먼저·동일 횟수"
        )
    if result.balance_lower and "불균형" in result.balance_lower:
        exercise.actions.append(
            f"하체 좌우 {result.balance_lower}: 싱글레그 스쿼트·런지로 좌우 균등 자극"
        )
    if is_teen:
        exercise.actions.append(
            "성장기: 최대 중량·무리한 고강도보다 정확한 자세와 전신 발달 우선 "
            "(가능하면 지도자 지도 하에 진행)"
        )
    if result.bmr.status == "low":
        exercise.actions.append(
            f"기초대사량 {result.bmr.value} kcal로 정상보다 낮음 → "
            "근육량 증가가 BMR 상승에 가장 효과적"
        )
    sections.append(exercise)

    # --- 4. 성장/점수 ---
    if result.growth_score is not None or is_teen:
        score_note = (
            f"성장점수 {result.growth_score}/100. "
            if result.growth_score is not None
            else ""
        )
        sections.append(
            PrescriptionSection(
                title="성장·발달 관점",
                priority="보통" if is_teen else "참고",
                summary=score_note
                + "키·체중 백분위와 함께 근육·무기질·수면·영양의 질을 봅니다.",
                details=[
                    f"신장: {result.height_cm} cm",
                    f"체중: {result.weight.value} kg",
                    f"소아비만도: {result.child_obesity_index.value}%"
                    if result.child_obesity_index.value
                    else "소아비만도: -",
                ],
                actions=[
                    "하루 수면 8~9시간 (성장호르몬 분비)",
                    "단백질·칼슘·비타민 D를 매일 챙기기",
                    "과도한 다이어트·장시간 앉아 있기 줄이기",
                    "3개월 간격으로 InBody 재측정하여 골격근·무기질 추이 확인",
                ],
            )
        )

    # --- 5. 연구항목 ---
    if result.phase_angle is not None:
        pa_comment = (
            "세포 건강·영양 상태를 반영하는 지표로, "
            "일반적으로 높을수록 양호한 편입니다."
        )
        sections.append(
            PrescriptionSection(
                title="위상각·대사",
                priority="참고",
                summary=f"전신 위상각 {result.phase_angle}°. {pa_comment}",
                details=[
                    f"BMR: {result.bmr.value} kcal "
                    f"(참고 {result.bmr.low}~{result.bmr.high})"
                    if result.bmr.value
                    else "BMR: -",
                ],
                actions=[
                    "규칙적인 근력 운동과 단백질 섭취가 위상각·BMR 개선에 도움",
                    "급성 질환·심한 탈수 시 수치가 변할 수 있음",
                ],
            )
        )

    # 주간 플랜
    weekly = {
        "월": ["전신 근력 A (하체 중심)", f"물 {water_ml}ml", "단백질 매끼 챙기기"],
        "화": ["유산소 25~35분 또는 활동량 증가", "스트레칭·폼롤러", "유제품·채소 포함"],
        "수": ["전신 근력 B (상체·등 중심)", "운동 후 단백질 보충", "수면 7~8시간+"],
        "목": ["가벼운 산책·활동 회복일", "수분·무기질 식품 강화", "자세·호흡 점검"],
        "금": ["전신 근력 C (하체+코어)", "유산소 선택적 15~20분", "주간 식단 점검"],
        "토": ["취미 스포츠·야외 활동", "균형 잡힌 식사", "충분한 휴식"],
        "일": ["완전 휴식 또는 가벼운 스트레칭", "다음 주 장보기·식단 준비", "수면 보충"],
    }

    # plan3 Phase 01 — 구조화 식단 리포트에서 meal_guide 생성 (하위 호환)
    from meal_plan import build_meal_plan, meal_guide_lines

    meal_guide = meal_guide_lines(build_meal_plan(result))

    caution = [
        "본 처방은 InBody 결과 해석에 기반한 일반적 생활·운동·영양 가이드이며, "
        "의료 진단이나 치료 대체가 아닙니다.",
        "질환·알레르기·성장·선수 특수가 있으면 의사·임상영양사·지도자와 상담하세요.",
        "보충제(단백질 파우더, 비타민 D, 칼슘 등)는 필요 시 전문가와 상의 후 사용하세요.",
        "InBody는 측정 전 식사·운동·수분·생리 주기에 따라 변동될 수 있습니다. "
        "동일 조건에서 재측정하는 것이 좋습니다.",
    ]

    return PrescriptionReport(
        overall_summary=overall,
        body_type=body_type,
        risk_flags=flags,
        sections=sections,
        weekly_plan=weekly,
        meal_guide=meal_guide,
        caution=caution,
    )
