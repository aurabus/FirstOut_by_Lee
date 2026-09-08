# 손잡고 마중 — 시놀로지 NAS(Container Manager)에서 도는 모습
#
# 옛 맥미니에 파이썬을 올리는 대신 통째로 담아 옮긴다. 어느 장비에 올려도
# 같은 파이썬, 같은 꾸러미, 같은 시각으로 돈다.
#
#     docker compose up -d --build
#
# 자료(data/)는 이미지 안에 넣지 않는다 — 바깥 폴더를 붙여서 쓴다.
# 그래야 새 버전을 올려도 원아 자료가 그대로 남는다.

FROM python:3.12-slim

# 시각을 반드시 한국으로 맞춘다.
# 귀가 시각·출결·서명 시각이 모두 이 시계로 적힌다. 그냥 두면 UTC 라
# 「3시 20분에 귀가」가 자료에는 아침 6시 20분으로 남는다.
ENV TZ=Asia/Seoul \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MAJUNG_DATA=/data

RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

# 뿌리 권한으로 돌리지 않는다. 자료 폴더의 주인을 이 번호로 맞춰야 한다.
#
# 시놀로지 계정의 번호를 그대로 받아 쓰는데, 그 번호가 이미 이미지 안에 있을 수 있다.
# 데비안에는 GID 100 이 `users` 로 이미 들어 있어서 — 그리고 시놀로지 계정의 기본
# 그룹이 흔히 100(users) 이라서 — 그냥 만들면 「이미 있다」며 빌드가 멈춘다.
# 있으면 있는 것을 쓰고, 없을 때만 만든다.
ARG UID=1000
ARG GID=1000
RUN set -eu; \
    if ! getent group "$GID" >/dev/null; then groupadd -g "$GID" majung; fi; \
    if ! getent passwd "$UID" >/dev/null; then \
        useradd -u "$UID" -g "$GID" -M -s /usr/sbin/nologin majung; \
    fi

WORKDIR /app

# 꾸러미 목록이 바뀌지 않으면 이 층은 다시 만들지 않는다 — 올리는 시간이 짧아진다
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN mkdir -p /data && chown -R "$UID:$GID" /data /app

# 이름이 아니라 번호로 지정한다 — 위에서 사용자를 새로 안 만들었을 수도 있다
USER ${UID}:${GID}
# 이름 없는 사용자로 돌 때 파이썬이 집 폴더를 찾다 놀라지 않게
ENV HOME=/tmp

EXPOSE 8000

# 살아 있는지 스스로 알린다. 죽어서 멈추면 restart 규칙이 다시 띄우고,
# 살아는 있는데 응답을 못 하는 상태는 여기서 unhealthy 로 드러난다.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request as u,sys; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)"

CMD ["firstout", "--host", "0.0.0.0", "--port", "8000"]
