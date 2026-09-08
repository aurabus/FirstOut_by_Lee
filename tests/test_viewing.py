"""운영자가 유치원 화면을 둘러본다.

「지금 그 원이 어떤 상태인가」를 알려고 매번 계정을 물어보면 원에도 번거롭고 우리도 느리다.
대신 들어가서 본다. 다만 **보기만 한다** — 남의 원 자료를 우리가 고칠 수 있으면
「누가 고쳤나」가 흐려지고, 무엇보다 그럴 이유가 없다.
"""

from __future__ import annotations

from firstout import viewing


class _Res:
    """쿠키만 받아 적는 가짜 응답."""

    def __init__(self):
        self.cookies = {}
        self.deleted = []

    def set_cookie(self, name, value, **kw):
        self.cookies[name] = (value, kw)

    def delete_cookie(self, name):
        self.deleted.append(name)


def test_들어가고_나온다():
    res = _Res()
    viewing.start(res, 7, secure=True)
    raw, kw = res.cookies[viewing.COOKIE]

    assert viewing.which(raw) == 7
    assert kw["httponly"] and kw["secure"]
    assert kw["max_age"] == viewing.MAX_AGE

    out = _Res()
    viewing.stop(out)
    assert viewing.COOKIE in out.deleted


def test_꾸며낸_값으로는_들어갈_수_없다():
    """쿠키를 손으로 만들어 남의 원에 들어갈 수 없어야 한다."""
    assert viewing.which(None) is None
    assert viewing.which("") is None
    assert viewing.which("7") is None
    assert viewing.which("eyJrIjo3fQ.fake.signature") is None

    res = _Res()
    viewing.start(res, 7, secure=False)
    raw = res.cookies[viewing.COOKIE][0]
    assert viewing.which(raw[:-4] + "aaaa") is None      # 한 글자만 바꿔도 무효


def test_두_시간이_지나면_저절로_풀린다():
    """켜둔 채 잊어버려도 오래 남지 않는다."""
    assert viewing.MAX_AGE == 2 * 60 * 60


def test_바꾸는_길은_모두_막는다():
    """막지 않으면 우리가 남의 원 자료를 고칠 수 있게 된다."""
    for path in ("/attend/3", "/list/i1/3/check", "/list/i1/3/sign", "/child/3/save",
                 "/child/3/leave", "/settings/class/1/rename", "/roster/add",
                 "/users/add", "/upload/apply", "/suggest"):
        assert viewing.blocked(path), path


def test_나가는_길은_열어둔다():
    """전부 막으면 둘러보기를 끝낼 수조차 없다."""
    for path in ("/view/stop", "/signout", "/operator", "/operator/3/approve",
                 "/reauth", "/me/password"):
        assert not viewing.blocked(path), path


def test_지킴이가_미들웨어에_걸려_있다():
    """화면마다 검사하면 언젠가 빠뜨린다 — 한 곳에서 막는다."""
    from pathlib import Path

    import firstout

    main = (Path(firstout.__file__).parent / "main.py").read_text(encoding="utf-8")
    assert "app.add_middleware(ViewOnly)" in main


def test_운영자_소속이_저장되지_않는다():
    """둘러볼 때 운영자에게 그 원의 번호를 붙이는데, 표에 붙어 있는 채로 바꾸면
    다음 commit 때 운영자가 그 유치원 소속으로 저장되어 버린다."""
    from pathlib import Path

    import firstout

    main = (Path(firstout.__file__).parent / "main.py").read_text(encoding="utf-8")
    i = main.index("if u.is_operator:")
    j = main.index("return u", i)
    block = main[i:j]
    assert "db.expunge(u)" in block
    assert block.index("db.expunge(u)") < block.index("u.kinder_id = k.id")
