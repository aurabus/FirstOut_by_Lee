"""개선 요청에 답을 단다 — 아우라버스가 승낙한 초안만.

읽는 것은 tools/suggestions.py, 쓰는 것은 여기다. 나눠 둔 까닭은 **선생님께
나가는 말**이기 때문이다. 읽기는 언제든 해도 되지만, 쓰기는 사람이 한 번 보고
「그렇게 보내라」 한 뒤에만 일어나야 한다.

    python tools/reply.py 3 "차수 시각을 바꿀 수 있게 했습니다." --상태 반영됨
    python tools/reply.py 3 --파일 draft.txt

원래는 운영자가 /suggest 화면에서 단다. 여기서 자료를 직접 고치는 것은 운영자
계정의 비밀번호를 이 PC 에 두지 않기 위해서다. 그 계정은 **모든 유치원**을 볼 수
있어서, 파일로 남겨 두는 것이 답을 다는 편함보다 비싸다.

자료를 직접 고치므로 감사 로그에는 남지 않는다. 대신 답 끝에 누가 언제 썼는지
꼬리를 붙이지 않는다 — 화면이 「답한 때」를 따로 보여준다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

뿌리 = Path(__file__).resolve().parent.parent
상태들 = ["받음", "확인함", "만드는 중", "반영됨", "보류"]


def 어디로() -> tuple[str, str]:
    p = 뿌리 / ".nas"
    if not p.exists():
        raise SystemExit("  .nas 가 없습니다.")
    줄 = [x.strip() for x in p.read_text(encoding="utf-8").splitlines()
          if x.strip() and not x.startswith("#")]
    return 줄[0], (줄[1] if len(줄) > 1 else "9292")


def 쓰는글(번호: int, 답: str, 상태: str, 자리: str = "/data/majung.db") -> str:
    """서버에서 돌 짧은 글. 값은 JSON 으로 박아 넣는다 — 따옴표로 씨름하지 않으려고."""
    짐 = json.dumps({"id": 번호, "reply": 답, "status": 상태, "db": 자리},
                   ensure_ascii=True)
    return f'''
import datetime as dt, json, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
짐 = json.loads({짐!r})

c = sqlite3.connect(짐["db"])
r = c.execute("select id, user_name, kinder_name, body, reply from suggestion where id = ?",
              (짐["id"],)).fetchone()
if r is None:
    print("그런 번호의 요청이 없습니다:", 짐["id"])
    raise SystemExit(1)

print("요청 #%s · %s · %s" % (r[0], r[1] or "?", r[2] or "?"))
print("  보내신 말:", (r[3] or "")[:200])
if r[4]:
    print("  이미 답이 달려 있습니다:", r[4][:200])
    print("  덮어씁니다.")

cur = c.execute(
    "update suggestion set reply = ?, replied_at = ?, status = ? where id = ?",
    (짐["reply"], dt.datetime.now().isoformat(sep=" ", timespec="seconds"),
     짐["status"], 짐["id"]))
if cur.rowcount != 1:
    c.rollback()
    print("한 줄이 아니어서 되돌렸습니다.")
    raise SystemExit(1)
c.commit()

r2 = c.execute("select status, reply, replied_at from suggestion where id = ?",
               (짐["id"],)).fetchone()
print()
print("답을 달았습니다")
print("  상태  :", r2[0])
print("  답한 때:", str(r2[2])[:19])
print("  답    :", r2[1])
c.close()
'''


def main() -> int:
    ap = argparse.ArgumentParser(description="개선 요청에 답을 단다")
    ap.add_argument("번호", type=int, help="요청 번호 (tools/suggestions.py 에 나오는 #숫자)")
    ap.add_argument("답", nargs="?", default="", help="선생님께 드릴 말")
    ap.add_argument("--파일", help="답을 파일에서 읽는다 (긴 글일 때)")
    ap.add_argument("--상태", default="확인함", choices=상태들)
    args = ap.parse_args()

    답 = args.답
    if args.파일:
        답 = Path(args.파일).read_text(encoding="utf-8").strip()
    답 = 답.strip()
    if not 답:
        raise SystemExit("  답을 적어주세요 (또는 --파일 로 주세요).")

    나스, 포트 = 어디로()
    안 = ("export PATH=$PATH:/usr/local/bin:"
          "/var/packages/ContainerManager/target/usr/bin; "
          "docker exec -i majung python -")
    난 = subprocess.run(
        ["ssh", "-p", 포트, "-o", "BatchMode=yes", 나스, 안],
        input=쓰는글(args.번호, 답, args.상태), capture_output=True, text=True,
        encoding="utf-8", errors="replace")

    print()
    for 줄 in (난.stdout or "").splitlines():
        print("  " + 줄)
    if 난.returncode != 0:
        for 줄 in (난.stderr or "").splitlines():
            if 줄.strip() and "post-quantum" not in 줄 and "store now" not in 줄 \
                    and not 줄.startswith("**") and "may need to be upgraded" not in 줄:
                print("  " + 줄)
        return 1
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
