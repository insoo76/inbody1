"""메인 결과지 드롭존 업로드 테스트."""

from app import SRX_PDF_UPLOAD_KEY, SRX_UPLOAD_KEY, render_pdf_upload_zone


def test_upload_key_constant():
    assert SRX_UPLOAD_KEY == "srx_result_upload"
    assert SRX_PDF_UPLOAD_KEY == SRX_UPLOAD_KEY


def test_render_pdf_upload_zone_callable():
    assert callable(render_pdf_upload_zone)
