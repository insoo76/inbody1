"""배포 전 OCR·의존성 점검. Docker HEALTHCHECK 및 CI에서 사용."""

from __future__ import annotations

import sys


def main() -> int:
    errors: list[str] = []

    try:
        import streamlit  # noqa: F401
        import pymupdf  # noqa: F401
        import PIL  # noqa: F401
        import plotly  # noqa: F401
    except ImportError as exc:
        errors.append(f"Python 패키지 누락: {exc}")

    from parser import check_ocr_ready, find_tesseract

    ok, message = check_ocr_ready()
    if not ok:
        errors.append(message)
    else:
        cmd = find_tesseract()
        print(f"OCR OK: {cmd}")

    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1

    print("Deploy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
