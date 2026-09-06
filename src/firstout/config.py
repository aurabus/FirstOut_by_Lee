"""경로와 기본값."""

from __future__ import annotations

import os
from pathlib import Path

# 데이터는 저장소 밖이 아니라 프로젝트 안 data/ 에 둔다.
# .gitignore 로 커밋이 차단되어 있으므로 원아 정보가 저장소에 올라가지 않는다.
BASE_DIR = Path(__file__).resolve().parent
PKG_DIR = BASE_DIR
PROJECT_DIR = BASE_DIR.parent.parent

DATA_DIR = Path(os.environ.get("MAJUNG_DATA", PROJECT_DIR / "data"))
BACKUP_DIR = DATA_DIR / "backup"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "majung.db"

TEMPLATE_DIR = PKG_DIR / "templates"
STATIC_DIR = PKG_DIR / "static"

APP_NAME = "손잡고 마중"
APP_TAGLINE = "아이를 안전하게, 집으로"

# 세션 서명 키 — 운영 시 환경변수로 덮어쓴다
SECRET_KEY = os.environ.get("MAJUNG_SECRET", "majung-dev-secret-change-me")

WEEKDAYS = ["월", "화", "수", "목", "금"]


def ensure_dirs() -> None:
    for d in (DATA_DIR, BACKUP_DIR, UPLOAD_DIR):
        d.mkdir(parents=True, exist_ok=True)
