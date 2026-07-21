# SomaRx 2.0 식단 업그레이드 기획서
**시각 카드 식단 대시보드 및 InBody 연동 건강정보 제공**

---

## 1. 현재 식단 섹션 진단

### 현상: 텍스트 리스트 중심의 정적 UI
* **데이터:** `prescription.py`의 `meal_guide: list[str]` — 하루 목표 1줄 + 아침/점심/저녁/간식/피하기 문장
* **UI:** `app.py`에서 `<ul><li>`로만 렌더 (`srx-meal`)
* **이미 있는 값:** 목표 kcal, 단백질 g, 수분 ml, 체형(`body_type`), `risk_flags`, 처방 우선순위

### 문제점
* 정보는 있으나 **한눈에 안 보임** (숫자·끼니가 문장에 묻힘)
* “왜 이 식단인지” **건강 맥락(근거)이 약함**
* plan2 이후 처방 카드·Bento·SVG 헤더와 **시각 언어가 불일치**

---

## 2. 고도화 비전: See & Understand

* **See:** 일일 영양 목표와 끼니 구성을 **칩·카드**로 즉시 파악
* **Understand:** InBody 지표(단백질·수분·체지방 등)와 연결된 **건강 인사이트**로 “왜”를 설명
* **Align:** Clinical Minimal 디자인(단색 배경, 16px 카드, SVG 아이콘, 다크 모드) 유지

### Non-goals (1차 범위 밖)
* 실제 레시피 DB / AI 생성 식단
* 사진 업로드·칼로리 트래커 앱 연동
* 풀 주간 식단표·장보기 리스트 (→ Phase 2 / §3.5)

---

## 3. 핵심 개선 전략

### 3.1. 일일 영양 목표 스트립
기존 `meal_guide` 첫 줄에 묻혀 있던 목표를 **큰 숫자 칩 3개**로 분리합니다.

| 칩 | 예시 | 출처 |
| :--- | :--- | :--- |
| 칼로리 | `1850 kcal` | 처방 엔진 `cal['intake']` |
| 단백질 | `90~110 g` | `p_low` ~ `p_high` |
| 수분 | `2360 ml` | `_water_target_ml` |

### 3.2. 끼니별 시각 카드 (아침·점심·저녁·간식)
단순 문장 리스트를 **4장 카드 그리드**로 전환합니다. (SVG 아이콘, items, tip)

### 3.3. 건강정보 인사이트 패널
체형·`risk_flags`·단백질/수분/체지방 상태에 따라 **팁 2~4개** (`topic` / `reason` / `action` / `severity`)

### 3.4. 피하기 · 주의 배너
기존 “피하기” + 면책 문구 유지

### 3.5. (Phase 2) 주간 식단 힌트
주간 플랜과 연동한 요일별 한 줄 식단 힌트 (1차 범위 밖)

---

## 4. 데이터 모델

```python
@dataclass
class MealSlot:
    key: str          # breakfast | lunch | dinner | snack
    title: str
    items: list[str]
    tip: str

@dataclass
class MealInsight:
    topic: str
    reason: str
    action: str
    severity: str     # high | mid | tip

@dataclass
class MealPlanReport:
    calories: int
    protein_g: tuple[int, int]
    water_ml: int
    goal_label: str
    slots: list[MealSlot]
    insights: list[MealInsight]
    avoid: list[str]
```

* **생성:** `build_meal_plan(result, report=None) -> MealPlanReport`
* **하위 호환:** `meal_guide_lines(plan) -> list[str]`

---

## 5. 구현 가이드

| 파일 | 역할 |
| :--- | :--- |
| `meal_plan.py` | `MealPlanReport` 생성 + `meal_guide_lines` |
| `prescription.py` | `meal_guide`를 `build_meal_plan` 결과로 채움 |
| `icons.py` / `app.py` | Phase 02+ UI |
| `tests/test_meal_plan.py` | Phase 01 테스트 |

---

## 6. 수용 기준 (Definition of Done)

### Phase 01 (데이터)
* [x] `MealSlot` / `MealInsight` / `MealPlanReport` 정의
* [x] `build_meal_plan` — 슬롯 4개, 목표 수치, 인사이트, avoid
* [x] `meal_guide` 하위 호환
* [x] `pytest` 통과

### Phase 02~04 (UI)
* [x] 목표 칩 3개 + 끼니 카드 4장 + 인사이트 ≥ 1 표시
* [x] 피하기 배너 · SVG 아이콘
* [x] 다크 모드, 면책 문구 유지
* [x] 주간 식단 힌트 7일 (§3.5) — 운동 플랜 연동 · 오늘 하이라이트

---

## 7. 구현 로드맵 (4-Step)

1. **Phase 01:** 데이터 모델 + `build_meal_plan` ← **완료**
2. **Phase 02:** 목표 칩 + 끼니 카드 UI/CSS (§3.1 · §3.2) ← **완료**
3. **Phase 03:** 인사이트 + 피하기 배너 (§3.3 · §3.4) ← **완료**
4. **Phase 04:** 주간 식단 힌트 §3.5 ← **완료**

---

## 8. plan.md / plan2.md와의 관계

| 문서 | 초점 |
| :--- | :--- |
| `plan.md` | 트렌드·미션·히트맵·다차원·페르소나 |
| `plan2.md` | 위상각·BMR·처방 카드·주간 플랜·슬라임·브랜드 |
| **`plan3.md`** | **식단 시각화 + 건강정보 인사이트** |
