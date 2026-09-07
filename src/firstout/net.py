"""접속 주소 찾기와 QR 코드.

선생님 기기에 주소를 알려주는 일이 설치 과정에서 제일 자주 막힌다.
그래서 서버가 자기 주소를 스스로 찾아 화면과 콘솔에 보여준다.
"""

from __future__ import annotations

import socket


def local_ips() -> list[str]:
    """이 PC 가 원내망에서 갖는 주소들.

    유선·무선을 함께 쓰면 주소가 여러 개다. 어느 것이 맞는지 모르니 전부 보여준다.
    """
    found: list[str] = []

    # 바깥으로 나가는 경로에 쓰이는 주소가 대개 정답이다 (실제로 접속하지는 않는다)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        found.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in found and not ip.startswith("127."):
                found.append(ip)
    except OSError:
        pass

    return found or ["127.0.0.1"]


def primary_url(port: int) -> str:
    return f"http://{local_ips()[0]}:{port}"


def all_urls(port: int) -> list[str]:
    return [f"http://{ip}:{port}" for ip in local_ips()]


# ── QR 코드 ─────────────────────────────────────────────

def qr_svg(text: str, box: int = 8, quiet: int = 2) -> str:
    """접속 주소를 QR 로 그린다.

    선생님이 휴대폰 카메라로 찍으면 주소를 옮겨 적을 필요가 없다.
    이미지 라이브러리 없이 SVG 로 그리므로 원내망에서도 그대로 뜬다.
    """
    try:
        import qrcode
    except ImportError:  # 라이브러리가 없어도 화면은 떠야 한다
        return ""

    qr = qrcode.QRCode(border=quiet, box_size=1)
    qr.add_data(text)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    size = n * box

    rects = []
    for y, row in enumerate(m):
        x = 0
        while x < n:
            if row[x]:
                run = 1
                while x + run < n and row[x + run]:
                    run += 1
                rects.append(
                    f'<rect x="{x * box}" y="{y * box}" width="{run * box}" height="{box}"/>'
                )
                x += run
            else:
                x += 1

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}" role="img" aria-label="접속 주소 QR 코드">'
        f'<rect width="{size}" height="{size}" fill="#fff"/>'
        f'<g fill="#0D1613">{"".join(rects)}</g></svg>'
    )
