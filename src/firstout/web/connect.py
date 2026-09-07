"""접속 안내 — 선생님 기기에 주소를 알려주는 화면.

설치하고 나서 제일 먼저 막히는 곳이 "선생님들이 어떻게 들어가요?" 다.
QR 로 찍게 하고, 문자로 보낼 문구까지 만들어 둔다.

**QR 에는 주소만 담는다. 로그인은 담지 않는다.**
화면에 띄운 QR 은 지나가는 사람도 찍을 수 있고 단톡방으로 퍼진다. 로그인이 그 안에
있으면 누가 귀가 처리를 했는지 구분이 사라져, 서명과 감사 로그가 증빙 구실을 하지
못한다. 주소는 비밀이 아니므로 마음껏 나눠도 된다 — 지키는 것은 로그인이다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import net
from ..config import PUBLIC_URL
from ..db import get_db

router = APIRouter()

HOSTED_TEXT = """[손잡고 마중] 유치원 귀가 관리 접속 주소입니다.
{url}
휴대폰에서 열고 「홈 화면에 추가」 해두시면 앱처럼 한 번에 들어갑니다.
아이디와 비밀번호는 따로 안내드립니다."""

LOCAL_TEXT = """[손잡고 마중] 유치원 귀가 관리 접속 주소입니다.
{url}
휴대폰이나 태블릿 브라우저에서 열고 즐겨찾기 해두세요. 원내 WiFi 에 연결되어 있어야 합니다."""


@router.get("/connect")
def connect(request: Request, db: Session = Depends(get_db)):
    """로그인 전에도 볼 수 있다. 설치한 사람이 바로 열어 확인하는 화면이기 때문이다."""
    from ..main import RUN_PORT, current_user, page

    port = RUN_PORT or (request.url.port or 8000)
    hosted = bool(PUBLIC_URL)          # 서브도메인으로 서비스하는 중인가

    if hosted:
        main_url, other_urls = PUBLIC_URL, []
        share_text = HOSTED_TEXT.format(url=main_url)
    else:
        urls = net.all_urls(port)
        main_url, other_urls = urls[0], urls[1:]
        share_text = LOCAL_TEXT.format(url=main_url)

    return page(
        request, "connect.html", db, current_user(request, db),
        main_url=main_url,
        other_urls=other_urls,
        hosted=hosted,
        qr=net.qr_svg(main_url),
        share_text=share_text,
        port=port,
    )
