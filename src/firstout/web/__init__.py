"""화면 라우터 묶음."""

from __future__ import annotations

from urllib.parse import quote

from fastapi.responses import Response

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def xlsx(data: bytes, korean_name: str, ascii_name: str) -> Response:
    """엑셀 파일을 내려보낸다.

    헤더에는 latin-1 만 담을 수 있어 한글 파일 이름을 그대로 넣으면 500 이 난다.
    옛 브라우저용 ASCII 이름과 UTF-8 이름을 함께 보낸다 (RFC 5987).
    """
    return Response(
        content=data,
        media_type=XLSX,
        headers={
            "Content-Disposition":
                f'attachment; filename="{ascii_name}"; '
                f"filename*=UTF-8''{quote(korean_name)}"
        },
    )
