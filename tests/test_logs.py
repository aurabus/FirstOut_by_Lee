"""기술 로그 — 문제가 났을 때 되짚을 수 있는가.

여기 있는 것들은 모두 **실제로 못 찾아서** 넣은 것이다.

    - 서버가 터졌는데 감사 로그에는 상태가 0 으로 남아, 화면에는 평범한
      「열어봄」으로 떴다. 「서버 오류」 딱지가 코드에 있는데도 영영 뜨지 않았다.
    - uvicorn 이 찍는 줄에는 날짜도 시각도 없어 「어제 세 시쯤」을 못 찾았다.
    - /health 가 몇 초마다 찍혀 로그의 절반을 차지했다.
"""

from __future__ import annotations

import logging

from firstout import logs


def test_번호는_헷갈리는_글자를_안_쓴다():
    """선생님이 화면에서 읽어 불러 주시는 값이다. 0·O·1·l 이 섞이면 못 받아 적는다."""
    본것 = {logs.new_id() for _ in range(300)}
    assert len(본것) > 290, "같은 번호가 자꾸 나오면 이어 붙일 수가 없다"
    for 하나 in 본것:
        assert len(하나) == 6
        assert not (set(하나) & set("01OIl")), f"헷갈리는 글자가 섞였다: {하나}"


def test_건강_확인은_로그에_안_남는다():
    """몇 초마다 오는 것이 쌓이면 정작 봐야 할 사건이 회전으로 밀려난다."""
    거르개 = logs.조용히()

    def 줄(길: str) -> logging.LogRecord:
        return logging.LogRecord(
            "uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
            ("1.2.3.4:5", "GET", 길, "1.1", 200), None)

    assert not 거르개.filter(줄("/health"))
    assert 거르개.filter(줄("/board")), "진짜 화면은 남아야 한다"
    assert not 거르개.filter(줄("/health?x=1")), "물음표가 붙어도 같은 길이다"
    assert 거르개.filter(줄("/healthy")), "앞글자만 같은 다른 길까지 삼키면 안 된다"


def test_로그에_시각이_붙는다():
    assert "%(asctime)s" in logs.MARK
    assert "%Y-%m-%d %H:%M:%S" == logs.WHEN, "날짜까지 있어야 한다 — 시각만으로는 어제를 못 찾는다"


def test_넘어간_일도_말은_남긴다(caplog):
    """조용히 넘어가면 몇 달째 안 되고 있어도 아무도 모른다."""
    with caplog.at_level(logging.WARNING, logger="majung"):
        logs.삼킴("감사 로그를 남기지 못했습니다", OSError("디스크가 꽉 찼습니다"))
    글 = caplog.text
    assert "감사 로그를 남기지 못했습니다" in 글
    assert "디스크가 꽉 찼습니다" in 글


def test_오류_줄에_번호가_들어간다(caplog):
    """이 번호 하나가 화면·기술 로그·감사 로그를 잇는 유일한 끈이다."""
    with caplog.at_level(logging.ERROR, logger="majung"):
        logs.오류("2MRY7U", "POST", "/list/i1/12/sign", "1.2.3.4")
    글 = caplog.text
    assert "2MRY7U" in 글
    assert "/list/i1/12/sign" in 글
    assert "1.2.3.4" in 글


def test_터진_요청은_감사_로그에_500_으로_남는다():
    """0 으로 남으면 outcome() 이 「열어봄」이라고 말한다 — 정상 조회와 구분이 안 된다."""
    from firstout import audit

    assert audit.outcome("GET", 500, True)[0] == "서버 오류"
    assert audit.outcome("GET", 0, True)[0] != "서버 오류", (
        "0 은 서버 오류로 읽히지 않는다. 그래서 미들웨어가 500 을 채워 넣어야 한다")


def test_미들웨어가_터졌을_때_500_을_채운다():
    """코드를 눈으로 보는 대신, 그 자리가 정말 있는지 본다."""
    import inspect

    from firstout.csrf import AuditMiddleware

    글 = inspect.getsource(AuditMiddleware)
    assert "except Exception" in 글, "터진 것을 잡지 않으면 상태가 0 으로 남는다"
    assert 'status["code"] = 500' in 글


def test_터진_화면에_번호가_보인다():
    """「안 돼요」 만으로는 아무것도 못 찾는다. 여섯 글자를 읽어 주실 수 있어야 한다."""
    import inspect

    from firstout import main

    글 = inspect.getsource(main.error_page)
    assert "req_id" in 글
    assert "번호" in 글
    # 터진 자리에서 또 터지면 안 된다 — 화면 틀(Jinja)도 DB 도 쓰지 않는다
    for 위험한것 in ("TemplateResponse", "SessionLocal", "get_db", "Depends"):
        assert 위험한것 not in 글, f"오류 화면이 {위험한것} 에 기대고 있다"


def test_감사_로그에_번호_칸이_있다():
    """쓰던 자료에도 칸이 붙어야 한다 — create_all 은 있는 표를 건드리지 않는다."""
    import inspect

    from firstout import db
    from firstout.models import AuditLog

    assert "req_id" in AuditLog.__table__.columns
    assert '("audit_log", "req_id")' in inspect.getsource(db._add_columns)
