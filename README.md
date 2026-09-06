# 손잡고 마중

유치원 귀가 관리 — 아이를 안전하게, 집으로.

원무실 PC 한 대가 서버가 되고, 선생님들은 태블릿·휴대폰·PC 브라우저로 접속합니다.
기기마다 설치할 것이 없고, 원내 WiFi만 살아 있으면 인터넷 없이도 동작합니다.

## 무엇을 하는가

| 화면 | 내용 |
|---|---|
| 오늘 현황 | 반별 총원·결석·조퇴·귀가·현원, 차수별 진행, 지연 경고 |
| 귀가 명단 | 차수별 명단 — 지금 쓰는 구글시트 세 탭을 대신함 |
| 원아 명부 | 아이 한 명이 한 줄인 주간 귀가 계획 |
| 설정 | 반·차량·차수·시각·학원 (관리자) |

핵심은 **주간 계획 한 장에서 매일 명단이 자동으로 만들어진다**는 점입니다.
같은 이름을 요일마다 탭마다 다시 적을 필요가 없습니다.

## 개발 환경

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install -r requirements-dev.txt
```

## 실행

```powershell
# 시연용 예시 원아 95명을 함께 넣고 실행 (처음 한 번)
python -m firstout.main --demo

# 평소 실행
python -m firstout.main

# 코드 고치면서 개발할 때
python -m firstout.main --reload
```

실행하면 접속 주소가 표시됩니다.

```
  이 PC        http://127.0.0.1:8000
  선생님 기기   http://192.168.0.10:8000
```

처음 PIN 은 모든 계정 **0000** 입니다.

## 테스트

```powershell
pytest          # 업무 규칙 검증
ruff check .    # 코드 점검
```

## 데이터와 개인정보

- 모든 자료는 `data/majung.db` 파일 하나에 들어갑니다. 백업은 이 파일 복사로 끝납니다.
- `data/`, `*.db`, `*.xlsx` 는 **`.gitignore` 로 커밋이 차단**되어 있습니다.
  원아 이름과 보호자 정보가 저장소에 올라가지 않습니다.
- 저장소는 **비공개**로 유지해야 합니다.

## 구조

```
src/firstout/
├── main.py          서버 진입점 · 공통 화면 값
├── models.py        데이터 구조
├── service.py       업무 규칙 (차수별 명단 계산)
├── seed.py          기본 자료 · 시연용 원아
├── security.py      PIN 해시 · 로그인 토큰
├── web/             화면별 경로
├── templates/       Jinja2 화면
└── static/          CSS · JS
```

`service.py` 가 이 프로그램의 핵심입니다. "주간 계획 + 오늘 출결" 에서
"오늘 차수별 명단" 을 만들어냅니다.
