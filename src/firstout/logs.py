"""기술 로그 — 문제가 났을 때 되짚는 자리.

감사 로그(audit.py)와는 다른 것이다. 감사 로그는 **유치원이 보는 기록**이다 —
누가 언제 어느 아이를 귀가 처리했나. 이쪽은 **우리가 보는 기록**이다 —
어제 세 시에 무엇이 터졌나.

고칠 때 로그만 보고 알아낼 수 있어야 하므로 세 가지를 지킨다.

    시각    「어제 세 시쯤 이상했어요」를 찾을 수 있어야 한다.
            uvicorn 이 기본으로 찍는 줄에는 날짜도 시각도 없다.
    번호    오류 자국 하나를 놓고 「누가 무엇을 하다 그랬나」로 이어져야 한다.
            요청마다 짧은 번호를 붙여 화면·기술 로그·감사 로그 셋에 같이 남긴다.
    조용함  /health 는 몇 초마다 찍힌다. 그대로 두면 로그의 절반이 그것이고,
            정작 봐야 할 사건이 회전으로 밀려난다.
"""

from __future__ import annotations

import logging
import secrets
import sys

MARK = "%(asctime)s  %(levelname)-5s  %(message)s"
WHEN = "%Y-%m-%d %H:%M:%S"

# 이 이름으로 우리 로그를 남긴다. 우리가 적은 줄과 uvicorn 이 적은 줄을 가르는 표.
log = logging.getLogger("majung")


def new_id() -> str:
    """요청 하나에 붙이는 짧은 번호.

    선생님이 화면에서 읽어 불러 주실 수 있어야 하므로 짧고 또렷해야 한다.
    헷갈리는 글자(0·O·1·l)는 빼고 여섯 자리만 쓴다. 남의 것을 맞혀도
    얻을 것이 없는 값이라 이 정도면 충분하다.
    """
    글자 = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(글자) for _ in range(6))


class 조용히(logging.Filter):
    """건강 확인처럼 몇 초마다 오는 것은 남기지 않는다."""

    조용한길 = {"/health"}

    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn 접속 기록의 args 는 (접속지, 방법, 길, 판, 상태) 다.
        길 = ""
        if record.args and len(record.args) >= 3:
            길 = str(record.args[2])
        # 앞글자만 맞춰 보면 /healthy 같은 **다른 길**까지 함께 삼킨다.
        # 조용히 시킨 것만 정확히 조용히 시킨다.
        return 길.split("?")[0] not in self.조용한길


def setup(level: str = "INFO") -> None:
    """로그가 나가는 모양을 정한다.

    uvicorn 이 제 손으로 먼저 꾸며 두므로, 뒤늦게 그 위에 덮는다. 그래야
    `firstout` 으로 띄우든 `uvicorn firstout.main:app` 으로 띄우든 같은 모양이 된다.

    파일로 모으지 않고 화면 밖으로만 내보낸다 — 도커가 받아서 돌려가며 보관한다
    (json-file · 10MB 씩 5장). 컨테이너 안에 파일로 쌓으면 컨테이너를 갈아 끼울
    때마다 사라지고, 용량도 아무도 안 본다.
    """
    바탕 = logging.Formatter(MARK, datefmt=WHEN)

    손 = logging.StreamHandler(sys.stdout)
    손.setFormatter(바탕)

    뿌리 = logging.getLogger()
    뿌리.handlers = [손]
    뿌리.setLevel(level)

    for 이름 in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        것 = logging.getLogger(이름)
        것.handlers = []          # uvicorn 이 달아 둔 것을 떼고 뿌리로 흘려보낸다
        것.propagate = True

    logging.getLogger("uvicorn.access").addFilter(조용히())


def 오류(req_id: str, 방법: str, 길: str, 접속지: str) -> None:
    """서버가 터졌을 때 **무슨 요청이었는지**를 한 줄로 남긴다.

    바로 뒤에 uvicorn 이 파이썬 자국(traceback)을 찍는다. 그 자국만으로는
    무엇을 하다 그랬는지 알 수 없어서, 그 앞에 이 줄을 둔다.

    누가 했는지는 여기서 캐지 않는다 — 그러려면 터진 자리에서 또 DB 를 열어야
    한다. 사람 이름은 곧바로 쓰이는 감사 로그가 **같은 번호로** 들고 있다.
    """
    log.error("[%s] 서버 오류 · %s %s · 접속지 %s", req_id, 방법, 길, 접속지 or "?")


def 삼킴(무엇: str, 왜: BaseException) -> None:
    """서비스를 멈추지 않으려고 넘어간 일 — 넘어가되 **말은 남긴다**.

    조용히 넘어가면 몇 달째 안 되고 있어도 아무도 모른다.
    """
    log.warning("%s — %s: %s", 무엇, type(왜).__name__, 왜)
