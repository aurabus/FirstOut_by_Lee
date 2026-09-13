"""선생님이 찍을 QR 안에 무엇이 들어 있는가.

그림은 멀쩡히 떠도 그 안에 `127.0.0.1` 이 들어 있으면 선생님 휴대폰에서는
아무것도 열리지 않는다. **눈으로는 절대 못 잡는다.** 개원 첫날 선생님 대여섯
분이 문 앞에 서 있게 되는 종류의 일이라 시험으로 묶어 둔다.

그리는 쪽(net.qr_svg)과 주소를 정하는 쪽(invites.link)이 따로 있어서,
둘 중 하나만 바뀌어도 조용히 어긋난다.
"""

from __future__ import annotations

import re

import pytest

from firstout import invites, net


def 점읽기(svg: str) -> set[tuple[int, int]]:
    """그려진 그림에서 검은 칸의 자리를 도로 읽는다.

    qr_svg 는 가로로 이어진 칸을 하나의 <rect> 로 묶으므로, 모든 네모의
    높이가 곧 한 칸이다. 그 값으로 되돌린다.
    """
    네모 = [tuple(int(v) for v in m.groups()) for m in re.finditer(
        r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg)]
    상자 = min(h for _x, _y, _w, h in 네모)
    return {(x // 상자 + i, y // 상자)
            for x, y, w, _h in 네모 for i in range(w // 상자)}


def 기대값(글: str, quiet: int = 2) -> set[tuple[int, int]]:
    qrcode = pytest.importorskip("qrcode")
    qr = qrcode.QRCode(border=quiet, box_size=1)
    qr.add_data(글)
    qr.make(fit=True)
    return {(x, y) for y, 줄 in enumerate(qr.get_matrix())
            for x, 켜짐 in enumerate(줄) if 켜짐}


@pytest.mark.parametrize("주소", [
    "https://majung.aurabus.com/join/abcDEF123_-xyz",
    "http://192.168.100.10:8765/join/tok",
    "https://majung.aurabus.com/connect",
])
def test_QR_은_준_주소를_그대로_담는다(주소):
    pytest.importorskip("qrcode")
    그림 = net.qr_svg(주소)
    assert 그림.startswith("<svg")
    assert 점읽기(그림) == 기대값(주소), "그림은 떴는데 안에 든 주소가 다르다"


def test_QR_은_다른_주소면_다르게_생긴다():
    """같은 그림이 나오면 위 시험이 아무것도 증명하지 못한다."""
    pytest.importorskip("qrcode")
    가 = 점읽기(net.qr_svg("https://majung.aurabus.com/join/aaa"))
    나 = 점읽기(net.qr_svg("https://majung.aurabus.com/join/bbb"))
    assert 가 != 나


def test_서비스_주소가_정해져_있으면_그것을_쓴다(monkeypatch):
    """프록시 뒤에서는 request.base_url 이 127.0.0.1:8765 로 보인다.

    그대로 QR 에 넣으면 선생님 휴대폰에서 안 열린다. 설정해 둔 바깥 주소가
    있으면 반드시 그쪽이 이긴다.
    """
    class 가짜요청:
        base_url = "http://127.0.0.1:8765/"

    monkeypatch.setattr(invites, "PUBLIC_URL", "https://majung.aurabus.com")
    assert invites.link("tok", 가짜요청()) == "https://majung.aurabus.com/join/tok"


def test_서비스_주소가_없으면_지금_열고_있는_주소를_쓴다(monkeypatch):
    """원내망에서 PC 한 대로 돌릴 때 — 그때는 그 주소가 맞는 주소다."""
    class 가짜요청:
        base_url = "http://192.168.0.10:8000/"

    monkeypatch.setattr(invites, "PUBLIC_URL", "")
    assert invites.link("tok", 가짜요청()) == "http://192.168.0.10:8000/join/tok"


def test_초대_원문은_어디에도_저장되지_않는다():
    """표에 남는 것은 대조용 표식뿐이다 — 새어 나가도 쓸 수 없어야 한다."""
    표식 = invites.fingerprint("sesame")
    assert 표식 != "sesame"
    assert len(표식) == 64
    assert invites.fingerprint("sesame") == 표식, "같은 값은 같은 표식이어야 대조가 된다"
