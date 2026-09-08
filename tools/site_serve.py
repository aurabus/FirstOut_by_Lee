"""홈페이지를 내 PC 에서 열어 본다 — NAS 에 올리기 전에.

파일을 두 번 눌러 여는 것(file:///...)과는 다르다. 그렇게 열면 주소가 달라서
공통 머리글을 불러오는 자바스크립트가 막히고, 화면이 실제와 다르게 보인다.
그래서 **진짜 웹서버와 같은 방식**으로 열어 준다.

NAS 에서 돌 nginx(deploy/site-nginx.conf)와 같은 규칙을 지킨다.
    - 「/」 로 들어오면 index.html, 없으면 main.html 을 연다
    - 맥에서 딸려온 ._ 찌꺼기는 내주지 않는다

돌리는 법 — site-preview.bat 을 두 번 누르거나::

    python tools/site_serve.py
"""

from __future__ import annotations

import functools
import http.server
import socket
import socketserver
import threading
import webbrowser
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
첫화면 = ("index.html", "main.html")     # nginx 의 index 규칙과 같은 순서
시작포트 = 8080


class 손님맞이(http.server.SimpleHTTPRequestHandler):
    """nginx 가 하는 것과 같은 일만 한다."""

    def _고쳐쓰기(self, 길: str) -> str:
        바탕, 물음, 뒤 = 길.partition("?")
        if 바탕.endswith("/"):
            폴더 = SITE / 바탕.strip("/")
            for 이름 in 첫화면:
                if (폴더 / 이름).is_file():
                    return 바탕 + 이름 + 물음 + 뒤
        return 길

    def _찌꺼기인가(self) -> bool:
        return any(조각.startswith(".") for 조각 in self.path.split("?")[0].split("/") if 조각)

    def do_GET(self) -> None:          # noqa: N802  (표준 이름이다)
        if self._찌꺼기인가():
            self.send_error(404)
            return
        self.path = self._고쳐쓰기(self.path)
        super().do_GET()

    def do_HEAD(self) -> None:         # noqa: N802
        if self._찌꺼기인가():
            self.send_error(404)
            return
        self.path = self._고쳐쓰기(self.path)
        super().do_HEAD()

    def log_message(self, fmt: str, *args) -> None:
        """무엇을 못 찾았는지만 알려준다 — 잘 나온 것까지 다 찍으면 안 보인다."""
        말 = fmt % args
        if " 404 " in 말 or " 403 " in 말:
            print("   못 찾음:", 말.split('"')[1] if '"' in 말 else 말)


def 빈포트(부터: int) -> int:
    for p in range(부터, 부터 + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 부터


def main() -> int:
    if not SITE.exists():
        print(f"{SITE} 폴더가 없습니다.")
        return 1
    있는것 = [n for n in 첫화면 if (SITE / n).is_file()]
    if not 있는것:
        print("site 폴더에 main.html 도 index.html 도 없습니다 — 먼저 옮겨주세요.")
        return 1

    포트 = 빈포트(시작포트)
    주소 = f"http://127.0.0.1:{포트}/"
    처리 = functools.partial(손님맞이, directory=str(SITE))

    print()
    print("  아우라버스 홈페이지 미리보기")
    print(f"    {주소}")
    print(f"    첫 화면: {있는것[0]}")
    print()
    print("  브라우저가 저절로 열립니다. 안 열리면 위 주소를 직접 넣어보세요.")
    print("  끝내려면 이 창에서 Ctrl+C 를 누르거나 창을 닫으세요.")
    print()

    threading.Timer(1.0, lambda: webbrowser.open(주소)).start()
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("127.0.0.1", 포트), 처리) as 서버:
            서버.serve_forever()
    except KeyboardInterrupt:
        print("\n  미리보기를 닫았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
