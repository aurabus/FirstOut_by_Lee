"""올린 뒤 밖에서 확인한다 — HTTPS 가 제대로 됐는지, 숨겨야 할 것이 숨었는지.

사무실 안에서는 잘 보이는데 밖에서는 안 되는 일이 흔하다. 이 검사기는
**바깥 손님과 같은 방식**으로 두들겨 본다. 되도록 사무실 밖(휴대폰 테더링 등)에서
돌리는 편이 정확하다.

돌리는 법::

    python tools/live_check.py
    python tools/live_check.py aurabus.com

보는 것:
    - 세 주소가 https 로 열리는가
    - 인증서가 그 주소의 것인가, 언제까지인가
    - http:// 로 들어가면 https 로 넘어가는가
    - DSM 관리 화면이 밖에서 안 보이는가  ← 가장 중요하다
"""

from __future__ import annotations

import datetime as dt
import http.client
import socket
import ssl
import sys
import urllib.error
import urllib.request

바탕 = "aurabus.com"
숨어야할포트 = (5000, 5001, 8033, 8043)      # DSM 관리 화면
좋음, 나쁨, 참고 = "  ○", "  ✗", "  ·"


def 인증서(호스트: str, 포트: int = 443, 시간: float = 8.0) -> dict | None:
    바탕맥락 = ssl.create_default_context()
    try:
        with socket.create_connection((호스트, 포트), timeout=시간) as s:
            with 바탕맥락.wrap_socket(s, server_hostname=호스트) as ss:
                return ss.getpeercert()
    except (OSError, ssl.SSLError):
        return None


def 열기(주소: str, 따라가기: bool = True) -> tuple[int, str, str]:
    """(응답 번호, 최종 주소, 앞부분). 못 열면 (0, '', '')."""
    class 안따라감(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    문 = urllib.request.build_opener() if 따라가기 \
        else urllib.request.build_opener(안따라감)
    try:
        r = 문.open(주소, timeout=10)
        return r.status, r.url, r.read(3000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location", 주소), ""
    except (urllib.error.URLError, OSError, http.client.HTTPException):
        return 0, "", ""


def 포트열렸나(호스트: str, 포트: int, 시간: float = 5.0) -> bool:
    try:
        with socket.create_connection((호스트, 포트), timeout=시간):
            return True
    except OSError:
        return False


def main() -> int:
    도메인 = sys.argv[1] if len(sys.argv) > 1 else 바탕
    www = f"www.{도메인}"
    마중 = f"majung.{도메인}"
    걸린것 = 0

    print()
    print(f"  {도메인} 을 바깥에서 두들겨 봅니다")
    print()

    # ── 인증서 ────────────────────────────────────────────
    print("  인증서")
    for 이름 in (도메인, www, 마중):
        c = 인증서(이름)
        if c is None:
            print(f"{나쁨} {이름:24} 인증서를 확인하지 못했습니다 "
                  "(443 이 막혔거나 이름이 다릅니다)")
            걸린것 += 1
            continue
        이름들 = {v for k, v in c.get("subjectAltName", ()) if k == "DNS"}
        맞나 = 이름 in 이름들 or any(
            n.startswith("*.") and 이름.endswith(n[1:]) for n in 이름들)
        끝 = c.get("notAfter", "")
        남은 = ""
        try:
            d = dt.datetime.strptime(끝, "%b %d %H:%M:%S %Y %Z")
            남은 = f"{(d - dt.datetime.utcnow()).days}일 남음"
        except ValueError:
            남은 = 끝
        if 맞나:
            print(f"{좋음} {이름:24} 인증서 맞음 · {남은}")
        else:
            print(f"{나쁨} {이름:24} 인증서가 다른 이름의 것입니다: {sorted(이름들)[:3]}")
            걸린것 += 1
    print()

    # ── 화면이 열리는가 ────────────────────────────────────
    print("  화면")
    for 이름, 무엇 in ((www, "홈페이지"), (도메인, "홈페이지"), (마중, "손잡고 마중")):
        코드, 최종, 몸 = 열기(f"https://{이름}/")
        if 코드 != 200:
            print(f"{나쁨} https://{이름:22} {코드 or '연결 안 됨'}")
            걸린것 += 1
            continue
        낌새 = ("Synology" in 몸 or "SYNO" in 몸)
        if 낌새:
            print(f"{나쁨} https://{이름:22} DSM 화면이 나옵니다 — 역방향 프록시 규칙이 없습니다")
            걸린것 += 1
        else:
            print(f"{좋음} https://{이름:22} 열림 ({무엇})")
    print()

    # ── http 로 들어오면 ───────────────────────────────────
    print("  http:// 로 들어왔을 때")
    코드, 어디로, _ = 열기(f"http://{www}/", 따라가기=False)
    if 코드 in (301, 302, 307, 308) and 어디로.startswith("https://"):
        앞 = 어디로.split("//", 1)[1].split("/")[0]
        꼬리 = "  (포트가 붙어 있습니다)" if ":" in 앞 else ""
        print(f"{좋음} https 로 넘어갑니다 → {어디로}{꼬리}")
    elif 코드 == 200:
        print(f"{참고} http 로도 그냥 열립니다 — https 로 넘기도록 하는 편이 좋습니다 (7-4장)")
    else:
        왜 = 코드 or "연결 안 됨"
        print(f"{참고} http:// 는 열리지 않습니다 ({왜}) — 옛 즐겨찾기가 막힙니다")
    print()

    # ── 숨어야 할 것 ──────────────────────────────────────
    print("  숨어야 할 것 (DSM 관리 화면)")
    보임 = [p for p in 숨어야할포트 if 포트열렸나(도메인, p)]
    if 보임:
        print(f"{나쁨} 포트 {보임} 이 밖에서 열려 있습니다 — 공유기 포트포워딩을 지우세요")
        걸린것 += 1
    else:
        print(f"{좋음} {list(숨어야할포트)} 모두 막혀 있습니다")
    print()

    if 걸린것 >= 6 and 밖으로_나가지나():
        print("  ── 잠깐 ──")
        print("  바깥 인터넷은 되는데 이 주소만 전부 안 열립니다.")
        print("  **사무실 안에서 돌리고 계신 것 같습니다.**")
        print("  공유기 안에서는 우리 공인 주소로 자기 자신을 부르지 못하는 경우가 많습니다")
        print("  (NAT 되돌림이 안 되는 공유기). 밖에서는 멀쩡할 수 있습니다.")
        print()
        print("  휴대폰 테더링이나 사무실 밖 인터넷에서 다시 돌려보세요.")
        print()
        return 2

    if 걸린것:
        print(f"  걸린 것 {걸린것}개 — deploy/README.md 의 해당 장을 보세요.")
        return 1
    print("  다 좋습니다.")
    return 0


def 밖으로_나가지나() -> bool:
    """인터넷 자체가 되는지 — 안 되면 「다 막혔다」는 말이 뜻이 없다."""
    for 곳 in (("1.1.1.1", 443), ("8.8.8.8", 443)):
        try:
            with socket.create_connection(곳, timeout=5):
                return True
        except OSError:
            continue
    return False


if __name__ == "__main__":
    raise SystemExit(main())
