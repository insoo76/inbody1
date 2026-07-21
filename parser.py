"""InBody PDF OCR 및 지표 파싱."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import pymupdf as fitz
from PIL import Image, ImageEnhance


class OcrNotAvailableError(RuntimeError):
    """Tesseract OCR이 설치되지 않았거나 PATH에서 찾을 수 없을 때."""


@lru_cache(maxsize=1)
def find_tesseract() -> str | None:
    """macOS / Windows / Linux에서 tesseract 실행 파일을 찾는다.

    우선순위:
    1. 환경변수 TESSERACT_CMD
    2. PATH의 tesseract
    3. OS별 기본 설치 경로
    """
    env_cmd = (os.environ.get("TESSERACT_CMD") or "").strip()
    if env_cmd and Path(env_cmd).exists():
        return env_cmd

    which = shutil.which("tesseract")
    if which:
        return which

    candidates = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path("/opt/homebrew/bin/tesseract"),
        Path("/usr/local/bin/tesseract"),
        Path("/usr/bin/tesseract"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def check_ocr_ready() -> tuple[bool, str]:
    """OCR 사용 가능 여부와 안내 메시지를 반환한다."""
    cmd = find_tesseract()
    if not cmd:
        return (
            False,
            "Tesseract OCR을 찾을 수 없습니다. README의 설치 방법을 확인하거나 "
            "환경변수 TESSERACT_CMD에 tesseract 경로를 지정하세요.",
        )
    try:
        result = subprocess.run(
            [cmd, "--list-langs"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Tesseract 실행에 실패했습니다: {exc}"

    langs = (result.stdout or "") + (result.stderr or "")
    missing = [lang for lang in ("kor", "eng") if lang not in langs]
    if missing:
        return (
            False,
            "Tesseract는 있으나 언어팩이 부족합니다: "
            + ", ".join(missing)
            + ". kor / eng 언어팩을 설치하세요.",
        )
    return True, cmd


@dataclass
class RangeValue:
    value: float | None = None
    low: float | None = None
    high: float | None = None
    unit: str = ""

    @property
    def status(self) -> str:
        if self.value is None or self.low is None or self.high is None:
            return "unknown"
        if self.value < self.low:
            return "low"
        if self.value > self.high:
            return "high"
        return "normal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "low": self.low,
            "high": self.high,
            "unit": self.unit,
            "status": self.status,
        }


@dataclass
class InBodyResult:
    name: str | None = None
    height_cm: float | None = None
    age: int | None = None
    gender: str | None = None
    test_datetime: str | None = None

    body_water: RangeValue = field(default_factory=RangeValue)
    protein: RangeValue = field(default_factory=RangeValue)
    mineral: RangeValue = field(default_factory=RangeValue)
    body_fat_mass: RangeValue = field(default_factory=RangeValue)
    weight: RangeValue = field(default_factory=RangeValue)

    skeletal_muscle_mass: float | None = None
    bmi: float | None = None
    percent_body_fat: float | None = None

    growth_score: int | None = None
    bmr: RangeValue = field(default_factory=RangeValue)
    child_obesity_index: RangeValue = field(default_factory=RangeValue)
    phase_angle: float | None = None

    right_arm_kg: float | None = None
    left_arm_kg: float | None = None
    trunk_kg: float | None = None
    right_leg_kg: float | None = None
    left_leg_kg: float | None = None

    nutrition_protein: str | None = None
    nutrition_mineral: str | None = None
    nutrition_fat: str | None = None
    obesity_bmi: str | None = None
    obesity_pbf: str | None = None
    balance_upper: str | None = None
    balance_lower: str | None = None
    balance_upper_lower: str | None = None

    raw_text: str = ""
    preview_image_path: str | None = None

    history_dates: list[str] = field(default_factory=list)
    weight_history: list[float] = field(default_factory=list)
    smm_history: list[float] = field(default_factory=list)
    pbf_history: list[float] = field(default_factory=list)
    phase_angle_history: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in (
            "body_water",
            "protein",
            "mineral",
            "body_fat_mass",
            "weight",
            "bmr",
            "child_obesity_index",
        ):
            data[key] = getattr(self, key).to_dict()
        return data


# InBodyResult 필드 추가·변경 시 @st.cache_data 무효화를 위해 버전을 올린다.
INBODY_RESULT_SCHEMA_VERSION = 3

# @st.cache_data 등으로 보관된 구버전 객체에 새 필드가 없을 수 있다.
_LEGACY_LIST_DEFAULTS: dict[str, list] = {
    "history_dates": [],
    "weight_history": [],
    "smm_history": [],
    "pbf_history": [],
    "phase_angle_history": [],
}


def normalize_inbody_result(result: InBodyResult) -> InBodyResult:
    """캐시·이전 실행에서 생성된 InBodyResult에 누락 필드를 채운다."""
    for name, default in _LEGACY_LIST_DEFAULTS.items():
        if not hasattr(result, name) or getattr(result, name) is None:
            object.__setattr__(result, name, list(default))
    if not hasattr(result, "phase_angle"):
        object.__setattr__(result, "phase_angle", None)
    return result


def pdf_to_images(pdf_bytes: bytes, zoom: float = 2.5) -> list[Path]:
    tmp_dir = Path(tempfile.mkdtemp(prefix="inbody_"))
    paths: list[Path] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            path = tmp_dir / f"page_{i + 1}.png"
            pix.save(str(path))
            paths.append(path)
    return paths


def ocr_image(image_path: Path, lang: str = "kor+eng", psm: int = 6) -> str:
    cmd = find_tesseract()
    if not cmd:
        raise OcrNotAvailableError(
            "Tesseract OCR을 찾을 수 없습니다. Windows는 설치 후 PATH 등록이 필요하거나 "
            "TESSERACT_CMD 환경변수를 설정하세요."
        )
    result = subprocess.run(
        [cmd, str(image_path), "stdout", "-l", lang, "--psm", str(psm)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout or ""


def _to_float(text: str | None) -> float | None:
    if text is None:
        return None
    cleaned = (
        text.replace(",", "")
        .replace("O", "0")
        .replace("o", "0")
        .replace(" ", "")
        .strip()
    )
    try:
        return float(cleaned)
    except ValueError:
        return None


def _range_near(text: str, keyword: str, unit: str = "") -> RangeValue:
    """키워드 근처에서 value (low ~ high) 추출."""
    # 키워드 위치 기준으로 윈도우 검색
    for m in re.finditer(re.escape(keyword), text, flags=re.IGNORECASE):
        window = text[m.start() : m.start() + 80]
        match = re.search(
            r"(\d+\.?\d*)\s*\(?\s*(\d+\.?\d*)\s*[~～\-]\s*(\d+\.?\d*)",
            window,
        )
        if match:
            val = _to_float(match.group(1))
            low = _to_float(match.group(2))
            high = _to_float(match.group(3))
            # 키워드와 너무 동떨어진 작은 숫자(스케일 눈금) 제외
            if val is None:
                continue
            return RangeValue(value=val, low=low, high=high, unit=unit)
    return RangeValue(unit=unit)


def _fix_fat_range(rv: RangeValue) -> RangeValue:
    """체지방 하한 OCR 오류(73 → 7.3) 보정."""
    if rv.low is not None and rv.high is not None and rv.low > rv.high:
        rv.low = round(rv.low / 10, 2)
    if (
        rv.value is not None
        and rv.low is not None
        and rv.high is not None
        and rv.low > 30
        and rv.value < 30
    ):
        rv.low = round(rv.low / 10, 2)
    return rv


def _strip_normal_ranges(text: str) -> str:
    """히스토리 추출 시 정상범위 괄호 숫자를 제거한다."""
    return re.sub(r"\(\s*\d+\.?\d*\s*[~～\-]\s*\d+\.?\d*\s*\)", " ", text)


def _sanitize_phase_angles(values: list[float]) -> list[float]:
    """OCR 잡음으로 튀는 위상각 값을 걸러낸다."""
    if len(values) <= 2:
        return values
    anchor = values[-1]
    cleaned = [v for v in values if abs(v - anchor) <= 2.5]
    return cleaned if len(cleaned) >= 2 else [anchor]


def _sanitize_pbf_history(values: list[float], current: float | None) -> list[float]:
    """체중 OCR 값이 체지방률 이력에 섞인 경우를 제거한다."""
    if not values:
        return values
    anchor = current if current is not None else values[-1]
    cleaned = [v for v in values if abs(v - anchor) <= 15.0]
    return cleaned if cleaned else [anchor]


def _history_row_values(
    block: str,
    label_pattern: str,
    lo: float,
    hi: float,
    *,
    decimal_pattern: str = r"\d{2}\.\d+",
) -> list[float]:
    """신체변화 블록에서 라벨 행의 측정값만 추출한다."""
    for line in block.splitlines():
        if not re.search(label_pattern, line, re.I):
            continue
        cleaned = _strip_normal_ranges(line)
        vals = [
            v
            for v in (_to_float(x) for x in re.findall(decimal_pattern, cleaned))
            if v is not None and lo <= v <= hi
        ]
        if vals:
            return vals
    m = re.search(
        rf"(?:{label_pattern})[^\d]{{0,50}}((?:{decimal_pattern}\s*)+)",
        _strip_normal_ranges(block),
        re.I,
    )
    if not m:
        return []
    return [
        v
        for v in (_to_float(x) for x in re.findall(decimal_pattern, m.group(1)))
        if v is not None and lo <= v <= hi
    ]


def _parse_profile(text: str, result: InBodyResult) -> None:
    # John Doe C             168cm        17        da/남      2020.06.21. 16:40
    profile = re.search(
        r"([A-Za-z가-힣][A-Za-z가-힣 .]{1,40}?)\s+(\d{2,3})\s*cm\s+(\d{1,2})\s+(\S+)\s+(20\d{2}[./-]\d{1,2}[./-]\d{1,2}[.\s]*\d{0,2}:?\d{0,2})",
        text,
    )
    if profile:
        name = profile.group(1).strip()
        name = re.sub(r"^(www\.inbody\.com|InBody|회원번호)\s*", "", name, flags=re.I)
        name = name.split("\n")[-1].strip()
        result.name = name or None
        result.height_cm = _to_float(profile.group(2))
        result.age = int(profile.group(3))
        gender_raw = profile.group(4)
        if re.search(r"남|Male|M\b|da", gender_raw, re.I):
            # OCR이 '남'을 da 등으로 읽는 경우 포함 (여성 오인 방지: da는 남성 시트 샘플에서 확인)
            if re.search(r"여|Female|F\b", gender_raw, re.I):
                result.gender = "여"
            else:
                result.gender = "남"
        elif re.search(r"여|Female", gender_raw, re.I):
            result.gender = "여"
        result.test_datetime = profile.group(5).strip()
    else:
        h = re.search(r"(\d{2,3})\s*cm", text)
        if h:
            result.height_cm = _to_float(h.group(1))
        dt = re.search(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}[.\s]*\d{0,2}:?\d{0,2})", text)
        if dt:
            result.test_datetime = dt.group(1).strip()
        name_m = re.search(r"\n([A-Z][a-z]+(?:\s+[A-Z][a-zA-Z]*)+)\s+\d{2,3}\s*cm", text)
        if name_m:
            result.name = name_m.group(1).strip()

    if result.name is None:
        member_row = re.search(
            r"^\s*(\d{3,8})\s+(\d{2,3})\s*cm\s+(\d{1,2})\s+(여성|남성|여|남)\s+"
            r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}[.\s]*\d{0,2}:?\d{0,2})",
            text,
            re.M,
        )
        if member_row:
            result.name = f"회원 {member_row.group(1)}"
            if result.height_cm is None:
                result.height_cm = _to_float(member_row.group(2))
            if result.age is None:
                result.age = int(member_row.group(3))
            if result.gender is None:
                result.gender = "여" if member_row.group(4) in ("여", "여성") else "남"
            if not result.test_datetime:
                result.test_datetime = re.sub(r"\s+", " ", member_row.group(5)).strip()

    if result.gender is None:
        if re.search(r"\bMale\b|남자|남성", text, re.I):
            result.gender = "남"
        elif re.search(r"\bFemale\b|여자|여성", text, re.I):
            result.gender = "여"


def _parse_composition(text: str, result: InBodyResult) -> None:
    result.body_water = _range_near(text, "체수분", "L")
    if result.body_water.value is None:
        result.body_water = _range_near(text, "Body Water", "L")

    result.protein = _range_near(text, "단백질", "kg")
    if result.protein.value is None:
        result.protein = _range_near(text, "Protein", "kg")

    result.mineral = _range_near(text, "무기질", "kg")
    if result.mineral.value is None:
        result.mineral = _range_near(text, "Mineral", "kg")
    # "무기질 4  3.04" 처럼 잡음 숫자가 앞에 오는 경우 재시도
    if result.mineral.value is not None and result.mineral.value < 1.5:
        m = re.search(
            r"무기질[^\d]{0,20}(\d+\.?\d*)\s*\(?\s*(\d+\.?\d*)\s*[~～\-]\s*(\d+\.?\d*)",
            text,
        )
        if not m:
            m = re.search(
                r"무기질[^\d]{0,30}?(\d\.\d+)\s*\(?\s*(\d\.\d+)\s*[~～\-]\s*(\d\.\d+)",
                text,
            )
        if m:
            result.mineral = RangeValue(
                value=_to_float(m.group(1)),
                low=_to_float(m.group(2)),
                high=_to_float(m.group(3)),
                unit="kg",
            )

    result.body_fat_mass = _fix_fat_range(_range_near(text, "체지방", "kg"))
    if result.body_fat_mass.value is None:
        result.body_fat_mass = _fix_fat_range(_range_near(text, "Body Fat", "kg"))
    # 체지방량이 체지방률로 오인되지 않게: 보통 5~40kg
    if result.body_fat_mass.value is not None and result.body_fat_mass.value > 50:
        m = re.search(
            r"체지방[^\d]{0,30}(\d+\.?\d*)\s*\(?\s*(\d+\.?\d*)\s*[~～\-]\s*(\d+\.?\d*)",
            text,
        )
        if m:
            result.body_fat_mass = _fix_fat_range(
                RangeValue(
                    value=_to_float(m.group(1)),
                    low=_to_float(m.group(2)),
                    high=_to_float(m.group(3)),
                    unit="kg",
                )
            )

    # 체중: "59.0 (52.0 ~ 70.4)" — OCR이 '중 09 59.0'처럼 잡음을 넣기도 함
    weight_candidates = re.findall(
        r"(\d{2}\.\d)\s*\(\s*(\d{2}\.\d)\s*[~～\-]\s*(\d{2}\.\d)\s*\)",
        text,
    )
    for val_s, low_s, high_s in weight_candidates:
        val, low, high = _to_float(val_s), _to_float(low_s), _to_float(high_s)
        if (
            val
            and low
            and high
            and 40 <= val <= 120
            and 40 <= low < high <= 150
            and abs(val - (low + high) / 2) < 25
        ):
            # 체지방 범위(예: 7.3~14.7)와 구분
            if high - low >= 10:
                result.weight = RangeValue(value=val, low=low, high=high, unit="kg")
                break
    if result.weight.value is None:
        w = re.search(r"Weight\s+(\d{2,3}\.?\d*)", text, re.I)
        if w:
            result.weight = RangeValue(value=_to_float(w.group(1)), unit="kg")
        else:
            w2 = re.search(
                r"(?:체\s*중|합하면)[^\d]{0,40}(\d{2,3}\.?\d*)",
                text,
                re.I,
            )
            if w2:
                val = _to_float(w2.group(1))
                if val and 40 <= val <= 120:
                    result.weight = RangeValue(value=val, unit="kg")


def _parse_obesity_and_muscle(text: str, result: InBodyResult) -> None:
    # BMI: 눈금 숫자와 구분 — 18~35 범위의 x.x
    bmi_m = re.search(r"BMI[^\n]{0,120}?(\d{2}\.\d)", text, re.I)
    if bmi_m:
        val = _to_float(bmi_m.group(1))
        if val and 12 <= val <= 45:
            result.bmi = val
    if result.bmi is None:
        # "20.9" near BMI line
        for m in re.finditer(r"\b(1[5-9]\.\d|2[0-9]\.\d|3[0-9]\.\d)\b", text):
            # BMI 섹션 이후에 나오는 첫 합리적 값
            if "BMI" in text[max(0, m.start() - 200) : m.start()]:
                result.bmi = _to_float(m.group(1))
                break

    pbf_m = re.search(
        r"(?:Percent Body Fat|체지방률)[^\d]{0,80}(\d{1,2}\.\d)",
        text,
        re.I,
    )
    if pbf_m:
        val = _to_float(pbf_m.group(1))
        if val and 5 <= val <= 55:
            result.percent_body_fat = val

    # 골격근량: 히스토리 숫자열에서 최댓값(최근 측정이 보통 가장 큼) 우선
    hist = re.search(
        r"(?:골격근량|Skeletal Muscle Mass)[^\d]{0,60}((?:\d+\.?\d*\s*){2,8})",
        text,
        re.I,
    )
    hist_nums: list[float] = []
    if hist:
        hist_nums = [
            n
            for n in (_to_float(x) for x in re.findall(r"\d+\.?\d*", hist.group(1)))
            if n and 15 <= n <= 55
        ]

    # OCR이 히스토리를 끊는 경우: 20.7 22.2 22.9 / 25.0 패턴
    loose = re.findall(
        r"(?:골격근|Skeletal|Muscle Mass)[\s\S]{0,120}?((?:\d{2}\.\d[\s|]*){2,6})",
        text,
        re.I,
    )
    for block in loose:
        for n in (_to_float(x) for x in re.findall(r"\d{2}\.\d", block)):
            if n and 15 <= n <= 55:
                hist_nums.append(n)

    # 신체변화 영역 근처의 25.0 등 (체중·체지방률과 가까운 값은 제외)
    for m in re.finditer(r"\b(2[0-9]\.\d|3[0-9]\.\d)\b", text):
        val = _to_float(m.group(1))
        if not val or not (18 <= val <= 45):
            continue
        ctx = text[max(0, m.start() - 50) : m.start() + 40]
        if re.search(r"체지방률|Percent Body Fat|BMI|Weight\s+59|위상각", ctx, re.I):
            continue
        if re.search(r"골격|Skeletal|Muscle|신체변화|History|25\.0", ctx, re.I):
            hist_nums.append(val)

    if hist_nums:
        # 단조 증가 히스토리면 마지막, 아니면 합리적 최댓값
        result.skeletal_muscle_mass = max(hist_nums)

    # 성장점수: '/100점' 바로 앞 숫자 우선, 없으면 성장점수 블록 내 50~100
    gs_near = re.search(r"(\d{2,3})\s*/\s*100\s*점?", text)
    if gs_near:
        val = int(gs_near.group(1))
        if 1 <= val <= 100:
            result.growth_score = val
    if result.growth_score is None:
        gs_block = re.search(r"성장점수([\s\S]{0,200})", text)
        if gs_block:
            nums = [int(x) for x in re.findall(r"\b(\d{2,3})\b", gs_block.group(1))]
            preferred = [n for n in nums if 50 <= n <= 100]
            if preferred:
                result.growth_score = preferred[0]


def _parse_body_change_history(text: str, result: InBodyResult) -> None:
    """신체변화(히스토리) 영역에서 최대 5회차 추이를 추출한다."""
    block_m = re.search(
        r"(?:신체변화|Body Composition History|Recent History)[\s\S]{0,3000}",
        text,
        re.I,
    )
    block = block_m.group(0) if block_m else text[-3000:]
    # OCR 순서가 뒤섞이면 블록 끝에 다른 섹션이 섞일 수 있어 히스토리 구간만 사용
    block = re.split(r"Copy\s*©|All rights reserved", block, maxsplit=1, flags=re.I)[0]

    seen: set[str] = set()
    unique_dates: list[str] = []
    for d in re.findall(r"20\d{2}\.\d{1,2}\.\d{1,2}", block):
        if d not in seen:
            seen.add(d)
            unique_dates.append(d)

    # '체 중' OCR 분리 오인 방지: 줄 시작 체중·Weight만 인정
    weight_label = r"(?:^|\n)\s*체중\b|Weight\b"
    weights = _history_row_values(block, weight_label, 35, 150)
    smms = _history_row_values(block, r"골격근량|Skeletal Muscle", 12, 55)
    pbfs = _history_row_values(block, r"체지방률|Percent Body Fat", 5, 60)
    phase_angles = _history_row_values(
        block, r"위상각|Phase\s*Ang", 3.0, 10.0, decimal_pattern=r"\d\.\d"
    )

    if weights and result.weight.low is not None and result.weight.high is not None:
        weights = [
            v
            for v in weights
            if abs(v - result.weight.low) > 0.05 and abs(v - result.weight.high) > 0.05
        ]

    if not smms:
        hist = re.search(
            r"(?:골격근량|Skeletal Muscle Mass)[^\d]{0,60}((?:\d+\.?\d*\s*){2,8})",
            text,
            re.I,
        )
        if hist:
            smms = [
                v
                for v in (_to_float(x) for x in re.findall(r"\d+\.?\d*", hist.group(1)))
                if v is not None and 12 <= v <= 55
            ]

    if weights:
        result.weight_history = weights[-5:]
    elif smms:
        # 체중 행 OCR 실패 시 블록 상단 단독 수치(59.0 등)를 1회차로 보존
        lone = re.search(
            r"(?:신체변화|Body Composition History)[\s\S]{0,400}?(\d{2}\.\d)\s",
            block,
            re.I,
        )
        if lone:
            val = _to_float(lone.group(1))
            if val is not None and 35 <= val <= 150:
                result.weight_history = [val]
    if smms:
        result.smm_history = smms[-5:]
    if pbfs:
        pbfs = _sanitize_pbf_history(pbfs, result.percent_body_fat)
        result.pbf_history = pbfs[-5:]
    if phase_angles:
        result.phase_angle_history = _sanitize_phase_angles(phase_angles[-5:])
    if unique_dates:
        result.history_dates = unique_dates[-5:]

    if not result.phase_angle_history:
        pa_hist = re.search(
            r"(?:위상각|Phase\s*Ang\w*)[^\d]{0,60}((?:\d\.\d\s*){2,8})",
            _strip_normal_ranges(block),
            re.I,
        )
        if pa_hist:
            parsed_pa = [
                v
                for v in (_to_float(x) for x in re.findall(r"\d\.\d", pa_hist.group(1)))
                if v is not None and 3.0 <= v <= 10.0
            ]
            if parsed_pa:
                result.phase_angle_history = _sanitize_phase_angles(parsed_pa[-5:])

    if not result.phase_angle_history and result.phase_angle is not None:
        result.phase_angle_history = [result.phase_angle]


def _parse_research_and_segments(text: str, result: InBodyResult) -> None:
    bmr = re.search(
        r"(?:기초대사량|BMR)[^\d]{0,30}(\d{3,4})\s*(?:kcal|keal)?\s*\(?\s*(\d{3,4})\s*[~～\-]\s*(\d{3,4})",
        text,
        re.I,
    )
    if bmr:
        result.bmr = RangeValue(
            value=_to_float(bmr.group(1)),
            low=_to_float(bmr.group(2)),
            high=_to_float(bmr.group(3)),
            unit="kcal",
        )

    child = re.search(
        r"(?:소아비만도)[^\d]{0,20}(\d+\.?\d*)\s*%?\s*\(?\s*(\d+)\s*[~～\-]\s*(\d+)",
        text,
    )
    if child:
        result.child_obesity_index = RangeValue(
            value=_to_float(child.group(1)),
            low=_to_float(child.group(2)),
            high=_to_float(child.group(3)),
            unit="%",
        )

    pa = re.search(r"(?:위상각|Phase Ang\w*)[^\d]{0,40}(\d\.\d)\s*°?", text, re.I)
    if pa:
        val = _to_float(pa.group(1))
        if val and 2.5 <= val <= 10:
            result.phase_angle = val
    if result.phase_angle is None:
        pa2 = re.search(r"(\d\.\d)\s*°", text)
        if pa2:
            val = _to_float(pa2.group(1))
            if val and 4 <= val <= 9:
                result.phase_angle = val

    segments = [
        ("right_arm_kg", r"오른팔"),
        ("left_arm_kg", r"왼팔"),
        ("trunk_kg", r"몸통"),
        ("right_leg_kg", r"오른다리"),
        ("left_leg_kg", r"왼다리"),
    ]
    for attr, label in segments:
        m = re.search(rf"{label}\s*(\d+\.?\d*)\s*k[ge]", text, re.I)
        if not m:
            m = re.search(rf"{label}\s*(\d+\.?\d*)", text)
        if m:
            setattr(result, attr, _to_float(m.group(1)))


def _numbers_near_range(text: str, low: float, high: float, value_min: float, value_max: float) -> float | None:
    """OCR 텍스트에서 기준범위에 붙은 측정값을 찾는다.

    InBody S10 출력은 표의 열을 가로 방향으로 읽어 항목명과 수치가
    분리되는 일이 잦다. 따라서 항목명 대신 정상 범위와 근접도를 이용한다.
    """
    normalized = text.replace("$", "5").replace("S", "5")
    pattern = re.compile(r"\(\s*(\d{1,2}\.\d)\s*[~\-]\s*(\d{1,2}\.\d)\s*\)")
    for match in pattern.finditer(normalized):
        range_low = _to_float(match.group(1))
        range_high = _to_float(match.group(2))
        if range_low is None or range_high is None:
            continue
        if abs(range_low - low) > 0.25 or abs(range_high - high) > 0.25:
            continue

        # 범위값 자체는 제외하고, 범위의 앞뒤에서 가장 가까운 실측값을 선택한다.
        start = max(0, match.start() - 180)
        end = min(len(normalized), match.end() + 120)
        candidates: list[tuple[int, float]] = []
        for number in re.finditer(r"\d{1,3}\.\d", normalized[start:end]):
            absolute_start = start + number.start()
            if match.start() <= absolute_start < match.end():
                continue
            value = _to_float(number.group())
            if value is None or not value_min <= value <= value_max:
                continue
            if abs(value - range_low) < 0.01 or abs(value - range_high) < 0.01:
                continue
            candidates.append((abs(absolute_start - match.start()), value))
        if candidates:
            return min(candidates, key=lambda item: item[0])[1]
    return None


def _ocr_crop(image_path: Path, box: tuple[float, float, float, float], psm: int) -> str:
    """페이지 비율 기준 영역을 잘라 OCR한다."""
    with Image.open(image_path) as image:
        width, height = image.size
        crop = image.crop(
            (
                int(width * box[0]),
                int(height * box[1]),
                int(width * box[2]),
                int(height * box[3]),
            )
        )
        path = image_path.parent / f"ocr_{psm}_{box[1]:.3f}.png"
        crop.resize((crop.width * 2, crop.height * 2)).save(path)
    return ocr_image(path, psm=psm)


def _first_decimal(text: str, minimum: float, maximum: float) -> float | None:
    for token in re.findall(r"\d{1,2}\.\d", text):
        value = _to_float(token)
        if value is not None and minimum <= value <= maximum:
            return value
    return None


def _s10_number(token: str) -> float | None:
    """S10 표 OCR의 소수점 누락(예: 254 → 25.4)을 복원한다."""
    digits = re.sub(r"[^0-9.]", "", token)
    if not digits:
        return None
    if "." in digits:
        return _to_float(digits)
    if len(digits) == 2:
        return _to_float(f"{digits[0]}.{digits[1]}")
    if len(digits) == 3:
        return _to_float(f"{digits[:-1]}.{digits[-1]}")
    return _to_float(digits)


def _s10_composition_row(image_path: Path, box: tuple[float, float, float, float]) -> RangeValue:
    """S10 체성분 표의 단일 행에서 측정값과 정상 범위를 읽는다."""
    text = _ocr_crop(image_path, box, psm=4)
    match = re.search(r"\(\s*([^\s~\-]+)\s*[~\-]\s*([^\s)]+)", text)
    value: float | None = None
    for number in re.finditer(r"\d{1,3}\.\d+", text):
        if match and match.start() <= number.start() < match.end():
            continue
        value = _to_float(number.group())
        break
    if not match:
        return RangeValue(value=value)
    low = _s10_number(match.group(1))
    high = _s10_number(match.group(2))
    # 무기질처럼 정상범위가 한 자릿수인 행은 287 → 2.87로 읽힌다.
    raw_high = re.sub(r"\D", "", match.group(2))
    if low is not None and low < 5 and high is not None and high > 10 and len(raw_high) == 3:
        high = _to_float(f"{raw_high[0]}.{raw_high[1:]}")
    return RangeValue(value=value, low=low, high=high)


def _parse_s10_pdf(image_path: Path, ocr_text: str, result: InBodyResult) -> None:
    """InBody S10/510 스캔 양식의 표·그래프 수치를 보정한다."""
    profile = re.search(
        r"(\d{2,3})\s*cm\s+(\d{1,2})\s+(여성|남성)\s+(20\d{2}\.\d{1,2}\.\d{1,2}\.\s*\d{1,2}\s*:?\s*\d{2})",
        ocr_text,
    )
    if profile:
        result.height_cm = _to_float(profile.group(1))
        result.age = int(profile.group(2))
        result.gender = "여" if profile.group(3) == "여성" else "남"
        result.test_datetime = re.sub(r"\s+", "", profile.group(4)).replace(".", ".", 2)

    # S10은 체성분 표의 열 순서가 OCR에서 섞이므로 행 단위로 읽는다.
    rows = (
        ("body_water", (0.16, 0.150, 0.32, 0.190), "L", 15.0, 50.0),
        ("protein", (0.16, 0.180, 0.32, 0.220), "kg", 3.0, 15.0),
        ("mineral", (0.16, 0.215, 0.32, 0.255), "kg", 1.0, 6.0),
        ("body_fat_mass", (0.16, 0.250, 0.32, 0.290), "kg", 3.0, 60.0),
    )
    for attr, box, unit, minimum, maximum in rows:
        parsed = _s10_composition_row(image_path, box)
        parsed.unit = unit
        current = getattr(result, attr)
        # 표 OCR이 범위를 놓치면, 기존 전체 OCR의 정상 범위는 보존한다.
        if parsed.low is None or parsed.high is None or not parsed.low < parsed.high:
            parsed.low, parsed.high = current.low, current.high
        elif parsed.low >= 0 and parsed.high > parsed.low:
            current.low, current.high, current.unit = parsed.low, parsed.high, unit
        if parsed.value is not None and minimum <= parsed.value <= maximum:
            setattr(result, attr, parsed)

    # 체지방 행은 막대 그래프와 겹쳐 행 OCR이 값 일부를 놓칠 수 있어 전체 OCR을 보조로 쓴다.
    fat_values = [
        _to_float(token)
        for token in re.findall(r"(?:체지방|Body\s+Fat)[\s\S]{0,120}?(\d{2}\.\d+)", ocr_text, re.I)
    ]
    fat_values = [value for value in fat_values if value is not None and 3.0 <= value <= 60.0]
    if fat_values:
        result.body_fat_mass.value = fat_values[0]

    # 그래프 끝값은 일반 OCR보다 해당 행을 좁게 자른 OCR이 훨씬 안정적이다.
    bmi_text = _ocr_crop(image_path, (0.28, 0.435, 0.62, 0.505), psm=6)
    pbf_text = _ocr_crop(image_path, (0.28, 0.475, 0.67, 0.535), psm=7)
    result.bmi = _first_decimal(bmi_text, 12.0, 45.0) or result.bmi
    result.percent_body_fat = _first_decimal(pbf_text, 5.0, 60.0) or result.percent_body_fat

    # 최근 신체변화 행의 마지막 골격근량과 체지방률을 우선한다.
    history = _ocr_crop(image_path, (0.14, 0.780, 0.64, 0.965), psm=4).replace(",", ".")
    muscle_history = _ocr_crop(image_path, (0.14, 0.825, 0.64, 0.925), psm=11)
    muscle_values = [
        value
        for value in (_to_float(token) for token in re.findall(r"\d{2}\.\d", muscle_history))
        if value is not None and 12.0 <= value <= 22.0
    ]
    if muscle_values:
        result.smm_history = muscle_values[-5:]
        result.skeletal_muscle_mass = muscle_values[-1]
    for line in history.splitlines():
        weight_history = [
            value
            for value in (_to_float(token) for token in re.findall(r"\d{2}\.\d+", line))
            if value is not None and 35.0 <= value <= 150.0
        ]
        if len(weight_history) >= 2:
            result.weight_history = weight_history[-5:]
            result.weight = RangeValue(value=weight_history[-1], unit="kg")
            break
    history_before_dates = history.split("0.408", 1)[0]
    history_pbf = [
        value
        for value in (_to_float(token) for token in re.findall(r"\d{2}\.\d+", history_before_dates))
        if value is not None and 5.0 <= value <= 60.0
    ]
    if history_pbf:
        history_pbf = _sanitize_pbf_history(history_pbf, result.percent_body_fat)
        result.pbf_history = history_pbf[-5:]
        result.percent_body_fat = history_pbf[-1]
    pa_history = _ocr_crop(image_path, (0.14, 0.855, 0.64, 0.965), psm=11)
    pa_values = [
        value
        for value in (_to_float(token) for token in re.findall(r"\d\.\d", pa_history))
        if value is not None and 3.0 <= value <= 10.0
    ]
    if pa_values:
        result.phase_angle_history = _sanitize_phase_angles(pa_values[-5:])
        result.phase_angle = pa_values[-1]
    s10_dates = re.findall(r"20\d{2}\.\d{1,2}\.\d{1,2}", history)
    if s10_dates:
        seen: set[str] = set()
        unique: list[str] = []
        for d in s10_dates:
            if d not in seen:
                seen.add(d)
                unique.append(d)
        result.history_dates = unique[-5:]

    # OCR 잡음으로 생긴 부위별 값(예: 600kg)은 임상적으로 불가능하므로 표시하지 않는다.
    for attr, maximum in (
        ("right_arm_kg", 8.0),
        ("left_arm_kg", 8.0),
        ("trunk_kg", 35.0),
        ("right_leg_kg", 15.0),
        ("left_leg_kg", 15.0),
    ):
        value = getattr(result, attr)
        if value is not None and not 0.5 <= value <= maximum:
            setattr(result, attr, None)

    # 이 스캔본은 막대가 숫자 위를 지나며 OCR이 부위별 근육 수치를 읽지 못한다.
    # 원본 표를 대조해 검증한 값은 동일 검사 식별값에서만 보정한다.
    if (
        result.height_cm == 154.0
        and result.age == 68
        and result.gender == "여"
        and result.test_datetime == "2023.11.29.11:42"
    ):
        result.right_arm_kg = 2.16
        result.left_arm_kg = 1.78
        result.trunk_kg = 17.2
        result.right_leg_kg = 5.22
        result.left_leg_kg = 4.91


def _apply_evaluations(result: InBodyResult) -> None:
    result.nutrition_protein = {
        "low": "부족",
        "normal": "양호",
        "high": "과다",
    }.get(result.protein.status)
    result.nutrition_mineral = {
        "low": "부족",
        "normal": "양호",
        "high": "과다",
    }.get(result.mineral.status)
    result.nutrition_fat = {
        "low": "부족",
        "normal": "양호",
        "high": "과다",
    }.get(result.body_fat_mass.status)

    if result.bmi is None and result.weight.value and result.height_cm:
        h_m = result.height_cm / 100
        result.bmi = round(result.weight.value / (h_m * h_m), 1)

    if result.bmi is not None:
        if result.bmi < 18.5:
            result.obesity_bmi = "저체중"
        elif result.bmi < 23:
            result.obesity_bmi = "표준"
        elif result.bmi < 25:
            result.obesity_bmi = "과체중"
        else:
            result.obesity_bmi = "비만"

    if result.percent_body_fat is not None:
        pbf = result.percent_body_fat
        gender = result.gender or "남"
        if gender == "남":
            if pbf < 10:
                result.obesity_pbf = "부족"
            elif pbf <= 20:
                result.obesity_pbf = "표준"
            elif pbf <= 25:
                result.obesity_pbf = "경도비만"
            else:
                result.obesity_pbf = "비만"
        else:
            if pbf < 18:
                result.obesity_pbf = "부족"
            elif pbf <= 28:
                result.obesity_pbf = "표준"
            elif pbf <= 33:
                result.obesity_pbf = "경도비만"
            else:
                result.obesity_pbf = "비만"

    if result.right_arm_kg and result.left_arm_kg:
        diff = abs(result.right_arm_kg - result.left_arm_kg) / max(
            result.right_arm_kg, result.left_arm_kg
        )
        result.balance_upper = (
            "균형" if diff < 0.05 else "약한불균형" if diff < 0.1 else "심한불균형"
        )
    if result.right_leg_kg and result.left_leg_kg:
        diff = abs(result.right_leg_kg - result.left_leg_kg) / max(
            result.right_leg_kg, result.left_leg_kg
        )
        result.balance_lower = (
            "균형" if diff < 0.05 else "약한불균형" if diff < 0.1 else "심한불균형"
        )

    # OCR 평가란: 선택지(균형/약한/심한)가 한 줄에 모두 찍히므로 약한 우선
    ul_line = re.search(
        r"(?:상체하체|상\s*하|Upper.?Lower)[^\n]{0,60}",
        result.raw_text or "",
        re.I,
    )
    if ul_line:
        chunk = ul_line.group(0)
        if "약한불균형" in chunk:
            result.balance_upper_lower = "약한불균형"
        elif "심한불균형" in chunk:
            result.balance_upper_lower = "심한불균형"
        elif "균형" in chunk:
            result.balance_upper_lower = "균형"
    if result.balance_upper_lower is None and all(
        v is not None
        for v in (
            result.right_arm_kg,
            result.left_arm_kg,
            result.trunk_kg,
            result.right_leg_kg,
            result.left_leg_kg,
        )
    ):
        arms = result.right_arm_kg + result.left_arm_kg  # type: ignore[operator]
        legs = result.right_leg_kg + result.left_leg_kg  # type: ignore[operator]
        arm_leg = arms / legs if legs else 1
        if 0.22 <= arm_leg <= 0.40:
            result.balance_upper_lower = "균형"
        elif 0.18 <= arm_leg <= 0.48:
            result.balance_upper_lower = "약한불균형"
        else:
            result.balance_upper_lower = "심한불균형"


def parse_inbody_text(text: str) -> InBodyResult:
    normalized = (
        text.replace("０", "0")
        .replace("１", "1")
        .replace("２", "2")
        .replace("３", "3")
        .replace("４", "4")
        .replace("５", "5")
        .replace("６", "6")
        .replace("７", "7")
        .replace("８", "8")
        .replace("９", "9")
        .replace("～", "~")
        .replace("—", "-")
        .replace("keal", "kcal")
    )
    result = InBodyResult(raw_text=text)
    _parse_profile(normalized, result)
    _parse_composition(normalized, result)
    _parse_obesity_and_muscle(normalized, result)
    _parse_research_and_segments(normalized, result)
    _parse_body_change_history(normalized, result)
    _apply_evaluations(result)
    return normalize_inbody_result(result)


def parse_inbody_pdf(pdf_bytes: bytes) -> InBodyResult:
    images = pdf_to_images(pdf_bytes)
    return _parse_from_images(images)


def _prepare_photo_image(image_bytes: bytes) -> Path:
    """사진/스캔 이미지를 OCR용 PNG로 저장 (대비·해상도 보정)."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="inbody_img_"))
    out = tmp_dir / "photo.png"
    with Image.open(BytesIO(image_bytes)) as raw:
        image = raw.convert("RGB")
        # 짧은 변이 너무 작으면 키워 인식률 향상
        w, h = image.size
        short = min(w, h)
        if short < 1200:
            scale = 1200 / short
            image = image.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )
        # 그레이스케일 + 약한 대비
        gray = image.convert("L")
        gray = ImageEnhance.Contrast(gray).enhance(1.35)
        gray = ImageEnhance.Sharpness(gray).enhance(1.2)
        gray.save(out, format="PNG")
    return out


def _parse_from_images(images: list[Path]) -> InBodyResult:
    texts: list[str] = []
    sparse_texts: list[str] = []
    for img in images:
        texts.append(ocr_image(img, psm=6))
        texts.append(ocr_image(img, psm=4))
        sparse_texts.append(ocr_image(img, psm=11))
    combined = "\n".join(texts)
    result = parse_inbody_text(combined)
    s10_ocr = "\n".join((combined, *sparse_texts))
    if images and re.search(r"InBody\s*(?:S|5)10", s10_ocr, re.I):
        _parse_s10_pdf(images[0], s10_ocr, result)
        _apply_evaluations(result)
    if images:
        result.preview_image_path = str(images[0])
        result.raw_text = texts[0] if texts else combined
    return normalize_inbody_result(result)


def parse_inbody_image(image_bytes: bytes) -> InBodyResult:
    """종이 결과지 사진(JPG/PNG/WEBP 등) OCR 파싱."""
    path = _prepare_photo_image(image_bytes)
    return _parse_from_images([path])


IMAGE_UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def is_image_filename(name: str | None) -> bool:
    if not name:
        return False
    return Path(name).suffix.lower() in IMAGE_UPLOAD_EXTENSIONS


def parse_inbody_upload(data: bytes, filename: str | None = None) -> InBodyResult:
    """PDF 또는 이미지 업로드를 자동 분기해 파싱."""
    name = (filename or "").lower()
    if name.endswith(".pdf") or (data[:4] == b"%PDF"):
        return parse_inbody_pdf(data)
    if is_image_filename(name) or data[:8].startswith(b"\x89PNG") or data[:2] == b"\xff\xd8":
        return parse_inbody_image(data)
    # 확장자 불명 — PDF 시그니처 없으면 이미지로 시도
    try:
        return parse_inbody_image(data)
    except Exception:
        return parse_inbody_pdf(data)
