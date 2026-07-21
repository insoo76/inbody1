"""parser.py 회귀 테스트."""

from __future__ import annotations

from parser import (
    INBODY_RESULT_SCHEMA_VERSION,
    InBodyResult,
    RangeValue,
    normalize_inbody_result,
    parse_inbody_text,
)

from tests.fixtures import FIXTURE_MEMBER_ROW, FIXTURE_TEEN_HISTORY, FIXTURE_WEIGHT_RANGE_TRAP


def test_teen_history_parsing():
    result = parse_inbody_text(FIXTURE_TEEN_HISTORY)
    assert result.name == "John Doe C"
    assert result.age == 17
    assert result.bmr.value == 1339.0
    assert result.phase_angle == 6.1
    assert result.phase_angle_history == [5.5, 5.8, 6.1]
    assert result.weight_history == [56.2, 57.1, 58.0]
    assert 52.0 not in result.weight_history
    assert 70.4 not in result.weight_history


def test_weight_range_not_treated_as_history():
    result = parse_inbody_text(FIXTURE_WEIGHT_RANGE_TRAP)
    assert 52.0 not in result.weight_history
    assert 70.4 not in result.weight_history


def test_member_row_name_fallback():
    result = parse_inbody_text(FIXTURE_MEMBER_ROW)
    assert result.name == "회원 1234"
    assert result.gender == "여"
    assert result.age == 68


def test_normalize_legacy_cached_object():
    legacy = InBodyResult(name="legacy", weight=RangeValue(value=60.0))
    object.__setattr__(legacy, "phase_angle_history", None)
    fixed = normalize_inbody_result(legacy)
    assert fixed.phase_angle_history == []


def test_schema_version_is_positive():
    assert INBODY_RESULT_SCHEMA_VERSION >= 1


def test_is_image_filename():
    from parser import is_image_filename

    assert is_image_filename("scan.JPG")
    assert is_image_filename("a.webp")
    assert not is_image_filename("report.pdf")
    assert not is_image_filename(None)


def test_prepare_and_parse_photo_image():
    from io import BytesIO

    from PIL import Image

    from parser import _prepare_photo_image, parse_inbody_image, parse_inbody_upload

    buf = BytesIO()
    Image.new("RGB", (800, 1100), color=(255, 255, 255)).save(buf, format="PNG")
    data = buf.getvalue()

    path = _prepare_photo_image(data)
    assert path.exists()
    assert path.suffix == ".png"
    with Image.open(path) as saved:
        assert min(saved.size) >= 1200

    result = parse_inbody_image(data)
    assert isinstance(result, InBodyResult)
    assert result.preview_image_path

    routed = parse_inbody_upload(data, "paper.jpg")
    assert isinstance(routed, InBodyResult)
