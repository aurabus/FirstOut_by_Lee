"""홈페이지 파일을 제대로 옮겼는지 본다.

옮기다 보면 한 겹 더 들어가거나(site/소스/index.html), 그림 폴더를 빠뜨리거나,
CSS 하나가 안 따라온다. 그런 것은 올리고 나서 화면이 깨져야 알게 된다.
그러지 말고 옮긴 자리에서 바로 확인한다.

돌리는 법::

    python tools/site_check.py

하는 일:
    - 「/」 로 들어왔을 때 열릴 index.html 이 있는가
    - 화면이 부르는 파일이 모두 있는가 (없으면 그 자리가 깨진다)
    - 한 겹 더 들어가지는 않았는가
    - 너무 무거운 그림은 없는가 (NAS 회선으로 내보낼 것들이다)
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

SITE = Path(__file__).resolve().parent.parent / "site"

# 이 파일들 안에서 「무엇을 부르는지」를 찾는다
읽을것 = (".html", ".htm", ".css")

# 무겁다고 볼 기준 — 첫 화면에서 이만큼을 내려받게 하면 안 된다
무거움 = 500 * 1024
아주무거움 = 2 * 1024 * 1024


def 부르는것(글: str) -> set[str]:
    """그 파일이 부르는 우리 쪽 파일들."""
    나온것: set[str] = set()
    나온것 |= set(re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', 글))
    나온것 |= {u.strip("\"' ") for u in re.findall(r"url\(([^)]+)\)", 글)}
    쓸것 = set()
    for u in 나온것:
        u = u.split("#")[0].split("?")[0].strip()
        바깥 = ("http:", "https:", "//", "mailto:", "tel:", "data:", "javascript:")
        if not u or u.startswith(바깥):
            continue
        쓸것.add(unquote(urlparse(u).path))
    return 쓸것


def 살펴보기(뿌리: Path) -> tuple[list[str], list[str]]:
    """(막아야 할 것, 알아두면 좋은 것)."""
    막을것: list[str] = []
    참고: list[str] = []

    if not 뿌리.exists():
        return [f"{뿌리} 폴더가 없습니다"], []

    파일들 = [f for f in 뿌리.rglob("*") if f.is_file()]
    이름들 = {f.relative_to(뿌리).as_posix() for f in 파일들}

    # ── 「/」 로 들어왔을 때 열릴 것 ──
    # 이 홈페이지는 첫 화면이 index.html 이 아니라 main.html 이다 (맥 아파치가 그랬다).
    # nginx 도 그렇게 보도록 맞춰 두었으므로 둘 중 하나만 있으면 된다.
    첫화면 = [n for n in ("index.html", "main.html") if n in 이름들]
    if not 첫화면:
        막을것.append(
            "site/main.html 도 index.html 도 없습니다 — 「/」 로 들어오면 아무것도 안 나옵니다")

    # ── 자리표가 남아 있는가 ──
    # 자리표 index.html 이 남아 있으면 진짜 첫 화면(main.html)을 가려 버린다.
    자리표 = 뿌리 / "index.html"
    if 자리표.exists() and "main.html" in 이름들:
        글 = 자리표.read_text(encoding="utf-8", errors="replace")
        if "홈페이지 파일이 아직 없습니다" in 글:
            막을것.append(
                "자리표 site/index.html 이 남아 있습니다 — 지우세요. "
                "그대로 두면 진짜 첫 화면(main.html)을 가립니다")

    # ── 한 겹 더 들어갔는가 ──
    안쪽 = sorted({n for n in 이름들
                  if n.count("/") >= 1 and n.rsplit("/", 1)[-1] in ("index.html", "main.html")})
    if not 첫화면 and 안쪽:
        막을것.append(
            f"한 겹 더 들어간 것 같습니다 — {안쪽[0]} 이 아니라 site/{안쪽[0].rsplit('/', 1)[-1]} "
            "이어야 합니다")

    # ── 부르는 파일이 다 있는가 ──
    없는것: dict[str, set[str]] = {}
    for f in 파일들:
        if f.suffix.lower() not in 읽을것:
            continue
        글 = f.read_text(encoding="utf-8", errors="replace")
        for u in 부르는것(글):
            대상 = (뿌리 / u.lstrip("/")).resolve() if u.startswith("/") \
                else (f.parent / u).resolve()
            try:
                대상.relative_to(뿌리.resolve())
            except ValueError:
                누가 = f.relative_to(뿌리).as_posix()
                막을것.append(f"{누가} 이 site 폴더 바깥을 가리킵니다: {u}")
                continue
            if not 대상.exists():
                없는것.setdefault(대상.relative_to(뿌리.resolve()).as_posix(),
                                 set()).add(f.relative_to(뿌리).as_posix())
    for 빠진, 부른곳 in sorted(없는것.items()):
        막을것.append(f"없는 파일을 부릅니다: {빠진}  (부르는 곳: {', '.join(sorted(부른곳))})")

    # ── 무게 ──
    총 = sum(f.stat().st_size for f in 파일들)
    참고.append(f"파일 {len(파일들)}개 · 합계 {총 / 1024 / 1024:.1f} MB")
    무거운것 = sorted(((f.stat().st_size, f.relative_to(뿌리).as_posix()) for f in 파일들),
                    reverse=True)
    큰것 = [(n, p) for n, p in 무거운것 if n >= 무거움]
    if 큰것:
        참고.append(f"{무거움 // 1024}KB 넘는 파일 {len(큰것)}개 — "
                   "줄이면 화면이 눈에 띄게 빨라집니다:")
        for n, p in 큰것[:10]:
            표 = "  ← 아주 무겁습니다" if n >= 아주무거움 else ""
            참고.append(f"    {n / 1024 / 1024:6.2f} MB  {p}{표}")

    # ── 맥에서 딸려온 찌꺼기 ──
    # 서버까지 따라가지는 않는다 (.gitignore 가 막고, nginx 도 내주지 않는다).
    # 그래도 남겨두면 나중에 헷갈리므로 맨 끝에 알려는 준다.
    찌꺼기 = sorted(n for n in 이름들
                  if n.rsplit("/", 1)[-1].startswith("._") or n.endswith(".DS_Store"))
    if 찌꺼기:
        참고.append("")
        참고.append(f"맥에서 딸려온 찌꺼기가 {len(찌꺼기)}개 있습니다 (._ 로 시작하는 것들).")
        참고.append("  서버에는 따라가지 않습니다. 지워두면 깔끔합니다 — PowerShell 에서:")
        참고.append(r'    Get-ChildItem .\site -Recurse -Force -File '
                    r'-Filter "._*" | Remove-Item -Force')

    return 막을것, 참고


def main() -> int:
    막을것, 참고 = 살펴보기(SITE)
    for s in 참고:
        print(s)
    if not 막을것:
        print()
        print("옮기기 끝 — 걸리는 것 없습니다.")
        return 0
    print()
    print(f"고쳐야 할 것 {len(막을것)}개")
    for s in 막을것:
        print(" ·", s)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
