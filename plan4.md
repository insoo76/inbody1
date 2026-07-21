# SomaRx 2.0 모바일 사용 · 배포 기획서
**스마트폰에서 InBody 처방 클리닉을 쓰기 위한 접근 전략**

---

## 1. 현재 상태 진단

### 1.1. 앱 성격
* **플랫폼:** Streamlit 웹앱 (`app.py`) — iOS/Android **네이티브 앱이 아님**
* **핵심 흐름:** InBody **PDF 또는 결과지 사진** 업로드 → OCR 파싱 → 처방·식단·운동 대시보드
* **저장소:** GitHub [`insoo76/inbody1`](https://github.com/insoo76/inbody1) (main, 51 files)
* **로컬 실행:** `streamlit run app.py` → `http://localhost:8501`

### 1.2. 모바일 대응 현황 (이미 구현됨)
| 항목 | 상태 | 근거 |
| :--- | :--- | :--- |
| 반응형 CSS | ✅ | `app.py` — `@media (max-width: 720px/520px)` 다수 |
| 사진 업로드 | ✅ | `parser.py` — `png/jpg/jpeg/webp` OCR |
| 다크 모드 | ✅ | `prefers-color-scheme: dark` |
| plan3 식단 UI | ✅ | 칩·카드·인사이트·주간 힌트 |
| 모바일 전용 UI | ❌ | 별도 앱스토어 빌드 없음 |

### 1.3. 모바일 사용 시 장애 요인
* **localhost** 는 폰에서 접근 불가 (PC 전용)
* **HTTP + IP** (`http://192.168.x.x:8501`) — iOS Safari에서 불안정, Mac 항상 켜져 있어야 함
* **OCR 의존** — 서버에 Tesseract(kor/eng) 필요
* **진행률 저장** (`.somarx/`) — Cloud 재배포 시 초기화 가능

---

## 2. 비전 · 목표

### 2.1. 비전
> **"체육관·헬스장에서 InBody 결과지를 찍어 올리면, 바로 개인 처방을 받는다."**

### 2.2. 1차 목표 (MVP)
* 스마트폰 브라우저에서 **HTTPS URL 하나**로 접속
* PDF·사진 업로드 → 분석 → 처방 탭 확인까지 **5분 이내** 완료
* **홈 화면 추가(PWA-lite)** 로 앱처럼 실행

### 2.3. Non-goals (1차 범위 밖)
* App Store / Play Store 네이티브 앱 출시
* 실시간 카메라 자세 분석 (별도 축구 POC와 혼동 주의)
* 오프라인 모드 · 푸시 알림
* 사용자 계정·로그인 (Streamlit Community Cloud 기본)

---

## 3. 배포 전략 비교

| 방식 | URL 예시 | Mac 필요 | HTTPS | OCR | 추천 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **A. Streamlit Cloud** | `https://xxx.streamlit.app` | ❌ | ✅ | ✅ (`packages.txt`) | **★★★** |
| B. 같은 Wi‑Fi | `http://192.168.x.x:8501` | ✅ | ❌ | ✅ (로컬) | 개발용 |
| C. Docker + VPS | `https://your-domain.com` | 서버 | ✅ | ✅ | 팀/상용 |
| D. 네이티브 래핑 | 앱스토어 | ❌ | ✅ | 별도 | Phase 2 |

**1차 권장:** **방식 A — Streamlit Community Cloud**

---

## 4. 사용자 시나리오 (User Flow)

```
[홈 화면 아이콘 또는 URL] ──> [메인: PDF/사진 업로드]
                                      │
                                      ▼
                            [OCR 분석 · 지표 추출]
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              [대시보드]         [처방 탭]          [미션·슬라임]
              차트·히트맵      식단·운동·주간      게이미피케이션
```

### 4.1. 화면별 모바일 UX

| 단계 | 사용자 행동 | 앱 동작 |
| :--- | :--- | :--- |
| 1. 접속 | Safari/Chrome에서 URL 열기 | 반응형 레이아웃, 세로 스크롤 |
| 2. 업로드 | PDF 선택 또는 **카메라/갤러리**에서 사진 | `st.file_uploader` (pdf/png/jpg/webp) |
| 3. 분석 | "분석하기" 탭 | OCR → `parse_inbody_upload` |
| 4. 확인 | 처방 탭 스크롤 | plan3 식단 카드·인사이트·주간 힌트 |
| 5. 재방문 | 홈 화면 아이콘 | 동일 URL 즉시 접속 |

### 4.2. 사진 촬영 가이드 (OCR 품질)
* 결과지 **전체**가 프레임에 들어오게
* **밝은 조명**, 그림자·역광 피하기
* 글자가 **흔들리지 않게** 고정 후 촬영
* PDF 원본이 있으면 PDF 우선 (정확도 최고)

---

## 5. 기술 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  스마트폰 (Safari / Chrome)                              │
│  · HTTPS 접속                                            │
│  · 파일/PDF 업로드 (브라우저 네이티브 피커)               │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Streamlit Community Cloud                               │
│  · Python 3.12 (runtime.txt)                             │
│  · requirements.txt                                      │
│  · packages.txt → tesseract-ocr + kor + eng              │
│  · app.py (Streamlit UI)                                 │
└──────────────────────────┬──────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   parser.py        prescription.py    meal_plan.py
   OCR·파싱          처방 엔진           plan3 UI
```

### 5.1. 배포에 필요한 저장소 파일 (이미 준비됨)

| 파일 | 역할 |
| :--- | :--- |
| `app.py` | Streamlit 진입점 |
| `requirements.txt` | Python 패키지 |
| `packages.txt` | Cloud용 Tesseract apt 패키지 |
| `runtime.txt` | Python 3.12 |
| `.streamlit/config.toml` | 테마·업로드 200MB |

### 5.2. Cloud에서 동작하지 않을 수 있는 것
* `.somarx/progress.json` — **인스턴스 재시작·재배포 시 초기화**
* 대용량 PDF 다수 동시 업로드 — Cold start 지연 가능

---

## 6. 구현 로드맵 (4-Step)

### Phase 01 — Streamlit Cloud 배포 (P0)
* [ ] [share.streamlit.io](https://share.streamlit.io) 에서 `insoo76/inbody1` 연결
* [ ] Main file: `app.py`, Branch: `main`
* [ ] 배포 로그에서 Tesseract·OCR OK 확인
* [ ] 배포 URL 확보 (예: `https://inbody1-xxx.streamlit.app`)

### Phase 02 — 모바일 검증 (P0)
* [ ] iPhone Safari: URL 접속 · 사진 업로드 · 처방 탭 스크롤
* [ ] Android Chrome: 동일 시나리오
* [ ] PDF 1장 + 사진 1장 QA
* [ ] `python check_deploy.py` → Cloud 로그 대조

### Phase 03 — 홈 화면 추가 안내 (P1)
* [ ] README 또는 앱 내 1회 안내 문구 (선택)
* [ ] iOS: 공유 → 홈 화면에 추가
* [ ] Android: 홈 화면에 추가 / 앱 설치

### Phase 04 — (선택) 모바일 UX 소폴리시 (P2)
* [ ] 업로드 영역 모바일 터치 타겟 확대
* [ ] 처방 탭 상단 sticky CTA
* [ ] Cloud Secrets (`TESSERACT_CMD` 등) 필요 시만 설정

---

## 7. 배포 실행 절차 (체크리스트)

### 7.1. 사전 조건
- [x] GitHub 저장소: `insoo76/inbody1`
- [x] `main` 브랜치 푸시 완료
- [x] `packages.txt` (tesseract kor/eng)
- [x] `pytest` 41 passed (로컬 기준)

### 7.2. Streamlit Cloud 설정값

| 설정 | 값 |
| :--- | :--- |
| Repository | `insoo76/inbody1` |
| Branch | `main` |
| Main file path | `app.py` |
| Python version | 3.12 |

### 7.3. 배포 후 검증

```bash
# 로컬 (참고)
python check_deploy.py
pytest
```

Cloud 앱에서:
1. 메인 화면 로드
2. `inbody.pdf` 또는 샘플 PDF 업로드
3. 처방 탭 → 식단 칩·카드 4장·주간 힌트 7일 표시
4. 사진 업로드 1회 (모바일)

---

## 8. 리스크 · 대응

| 리스크 | 영향 | 대응 |
| :--- | :--- | :--- |
| OCR 실패 (흐린 사진) | 분석 불가 | 촬영 가이드 UI, PDF 권장 |
| Cloud cold start | 첫 로딩 30~60초 | 허용 · README 안내 |
| 진행률 유실 | 미션·슬라임 리셋 | Phase 2: DB/Supabase 연동 검토 |
| iOS file:// / HTTP | 카메라·업로드 이슈 | **HTTPS Cloud URL만 안내** |
| Streamlit Cloud 한도 | 트래픽·리소스 | 필요 시 Docker VPS로 이전 |

---

## 9. plan.md / plan2.md / plan3.md와의 관계

| 문서 | 초점 |
| :--- | :--- |
| `plan.md` | 트렌드·미션·히트맵·다차원·페르소나 |
| `plan2.md` | 위상각·BMR·처방 카드·주간 플랜·슬라임·브랜드 |
| `plan3.md` | 식단 시각화 + 건강정보 인사이트 |
| **`plan4.md`** | **모바일 접근 · Streamlit Cloud 배포 · 사용 시나리오** |

---

## 10. 수용 기준 (Definition of Done)

### Phase 01~02 (필수)
* [ ] HTTPS Streamlit URL 1개 운영
* [ ] 모바일 브라우저에서 PDF·사진 업로드 성공
* [ ] 처방·식단(plan3) UI 정상 표시
* [ ] OCR(kor) 동작 (Cloud 로그 또는 실측)

### Phase 03 (권장)
* [ ] 홈 화면 추가 후 재접속 확인
* [ ] README에 모바일 URL·촬영 가이드 링크

---

## 11. 다음 액션 (승인 후 진행)

1. **Streamlit Cloud** 에 `insoo76/inbody1` 배포 요청
2. 배포 URL 공유
3. iPhone/Android에서 1회 실사용 QA
4. (선택) README·실행 매뉴얼에 모바일 섹션 추가

> **예상 소요:** 배포 10~20분 · 모바일 QA 15분 · 문서 반영 10분
