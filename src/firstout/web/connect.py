"""접속 안내 — 선생님 기기에 주소를 알려주는 화면.

설치하고 나서 제일 먼저 막히는 곳이 "선생님들이 어떻게 들어가요?" 다.
QR 코드로 찍게 하고, 문자로 보낼 문구까지 만들어 둔다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import net
from ..db import get_db

router = APIRouter()


@router.get("/connect")
def connect(request: Request, db: Session = Depends(get_db)):
    """로그인 전에도 볼 수 있다. 설치한 사람이 바로 열어 확인하는 화면이기 때문이다."""
    from ..main import RUN_PORT, current_teacher, page

    port = RUN_PORT or (request.url.port or 8000)
    urls = net.all_urls(port)
    main_url = urls[0]

    return page(
        request, "connect.html", db, current_teacher(request, db),
        main_url=main_url,
        other_urls=urls[1:],
        qr=net.qr_svg(main_url),
        share_text=(
            f"[손잡고 마중] 유치원 귀가 관리 접속 주소입니다.\n{main_url}\n"
            "휴대폰이나 태블릿 브라우저에서 열고 즐겨찾기 해두세요. "
            "원내 WiFi 에 연결되어 있어야 합니다."
        ),
        port=port,
    )
