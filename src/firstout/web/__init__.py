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


def clip(text: str, limit: int) -> str:
    """저장 전에 길이를 자른다.

    모델에 String(40) 이라고 적어두어도 **SQLite 는 그 길이를 강제하지 않는다.**
    화면에서 막아도 폼은 얼마든지 직접 보낼 수 있으므로 서버에서 자른다.
    """
    return text.strip()[:limit]
