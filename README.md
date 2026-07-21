# SomaRx 2.0 · InBody 처방 클리닉

InBody 결과 PDF를 업로드하면 OCR로 지표를 추출하고, 영양·운동·주간 플랜·게이미피케이션을 포함한 **개인 맞춤 처방 대시보드**를 제공합니다.

**처음 실행하는 분은 [실행_매뉴얼.md](./실행_매뉴얼.md)를 처음부터 따라가세요.**  
(Python → `venv` → 패키지 → Tesseract → 실행, macOS/Windows 순서 포함)

## 주요 기능 (SomaRx 2.0)

| 영역 | 기능 |
|------|------|
| PDF 분석 | Tesseract OCR(kor/eng) + InBody 지표 파싱 |
| 시각화 | 위상각·BMR·부위별 히트맵·트렌드 차트 |
| 처방 | 영양·운동·주간 플랜·식단 카드 UI |
| 게이미피케이션 | 미션·골드·슬라임 진화·런칭 배너 |
| 지속성 | `.somarx/progress.json`에 미션·주간플랜·재측정 진화 저장 |

## 빠른 실행 (로컬)

가상환경 이름은 **`venv`** 입니다.

```bash
# macOS / Linux
cd InBody
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

```powershell
# Windows PowerShell
cd InBody
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 로 접속합니다.

## 필요 환경

- Python **3.10+** (권장 3.12)
- Tesseract OCR + 언어팩 **`kor`**, **`eng`** (상세 설치는 실행 매뉴얼 6단계)
- pip 패키지: `requirements.txt`

### 환경 변수 (선택)

| 변수 | 설명 |
|------|------|
| `TESSERACT_CMD` | Tesseract 실행 파일 경로 (PATH에 없을 때) |

`.env.example` 참고.

## 테스트 & QA

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
pytest                    # 단위 테스트 (18개)
python check_deploy.py    # OCR·의존성 배포 점검
python qa_step1.py        # 샘플 PDF QA (inbody.pdf, 1.pdf)
```

## 배포

### A. Streamlit Community Cloud

1. GitHub에 `InBody` 폴더를 **저장소 루트**로 올리거나, 상위 저장소 사용 시 **Advanced settings → Main file path**를 `InBody/app.py`로 지정
2. [share.streamlit.io](https://share.streamlit.io)에서 저장소 연결
3. **Python version**: 3.12 (`runtime.txt`)
4. **Dependencies**: `requirements.txt` + **`packages.txt`** (Tesseract kor/eng 자동 설치)
5. 배포 후 `check_deploy.py` 로그에서 OCR OK 확인

> Cloud 빌드에 Tesseract가 포함되지 않으면 `packages.txt` 내용을 확인하세요.  
> kor/eng 언어팩이 없으면 앱 사이드바에 OCR 안내가 표시됩니다.  
> Cloud에서는 `.somarx/` 진행률이 **재배포 시 초기화**될 수 있습니다. (Docker volume 사용 시 유지)

### B. Docker (권장 — Tesseract 포함)

```bash
cd InBody
docker compose up --build
```

또는:

```bash
docker build -t somarx-inbody .
docker run -p 8501:8501 -v somarx-data:/app/.somarx somarx-inbody
```

- URL: `http://localhost:8501`
- 진행률 데이터: Docker volume `somarx-data` → 컨테이너 `/app/.somarx`

### 배포 전 체크리스트

- [ ] `python check_deploy.py` → `Deploy check passed.`
- [ ] `pytest` 전체 통과
- [ ] 실제 InBody PDF 1장 이상 업로드·처방 탭 확인
- [ ] (Cloud) `packages.txt`에 tesseract 패키지 3종 포함

## 프로젝트 구성

| 파일 | 역할 |
|------|------|
| `app.py` | Streamlit UI, 처방 탭, 런칭·진화 배너 |
| `parser.py` | PDF → OCR → 지표 파싱 |
| `prescription.py` | InBody 해석 기반 처방 엔진 |
| `gamification_engine.py` | 런칭 배너·골드·진화 |
| `progress_store.py` | 미션·주간플랜 로컬 저장 |
| `packages.txt` | Streamlit Cloud용 Tesseract apt 패키지 |
| `Dockerfile` | Docker 배포 (Tesseract 포함) |
| `check_deploy.py` | 배포·헬스체크용 OCR 점검 |
| `실행_매뉴얼.md` | 초보자용 상세 설치·실행 안내 |

## 주의

본 앱의 처방은 일반적인 생활·운동·영양 가이드이며 **의료 진단을 대체하지 않습니다.**
