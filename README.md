# FirstOut by Lee

## 요구 사항

- Python 3.10 이상 (3.13 권장)

## 개발 환경 준비

```powershell
# 1) 가상환경 생성
python -m venv .venv

# 2) 가상환경 활성화 (PowerShell)
.\.venv\Scripts\Activate.ps1

# 3) 프로젝트를 편집 가능 모드로 설치 + 개발 도구 설치
pip install -e .
pip install -r requirements-dev.txt
```

> 활성화가 막히면 한 번만 실행:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

## 실행

```powershell
python -m firstout.main
# 또는 설치된 명령어로
firstout
```

## 테스트 · 린트

```powershell
pytest
ruff check .
ruff format .
```

## 폴더 구조

```
.
├── src/firstout/      # 소스 코드
│   ├── __init__.py
│   └── main.py
├── tests/             # 테스트
├── pyproject.toml     # 프로젝트 · 도구 설정
└── requirements-dev.txt
```
