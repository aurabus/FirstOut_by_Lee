# 시놀로지 NAS 에 올리기

사무실 NAS 한 대에서 서비스를 돌리고, 자료도 같은 자리에 쌓인다. 옛 맥미니에
파이썬을 올리는 것보다 손이 훨씬 적게 간다 — 역방향 프록시와 HTTPS 인증서가
DSM 에 이미 들어 있기 때문이다.

들어가기 전에 확인할 것:

- **DSM 7.0 이상**, 패키지 센터에 **Container Manager** 가 있을 것
  (DSM 6 이면 이름이 `Docker` 다. 그것도 된다)
- 저가형(DS220j 같은 ARM 모델)은 도커를 아예 못 쓰는 것도 있다.
  패키지 센터에 Container Manager 가 보이지 않으면 그 경우다.

---

## 1. 자료가 쌓일 폴더를 만든다

File Station 에서 `docker` 공유 폴더 아래에 `majung` 폴더를 만든다.

```
/volume1/docker/majung/
```

폴더의 **주인 번호**를 알아야 한다. DSM 제어판 → 터미널 및 SNMP 에서 SSH 를 켜고
NAS 에 들어가 확인한다.

```bash
ssh 관리자이름@NAS주소
id 관리자이름          # uid=1026(...) gid=100(users) 처럼 나온다
```

이 번호를 뒤에서 `.env` 의 `MAJUNG_UID` · `MAJUNG_GID` 에 적는다. 맞지 않으면
컨테이너가 자료 폴더에 쓰지 못하고 시작하자마자 죽는다.

## 2. 코드를 NAS 로 옮긴다

NAS 에 SSH 로 들어가 저장소를 받는다. **이 방법이 뒤에 새 버전을 올릴 때도
가장 편하다** — 파일을 다시 올릴 필요 없이 `git pull` 한 줄이면 된다.

```bash
cd /volume1/docker/majung
git clone https://github.com/aurabus/FirstOut_by_Lee.git app
cd app
```

NAS 에 git 이 없으면 패키지 센터에서 **Git Server** 를 설치하면 딸려 온다.
그것도 어려우면 File Station 으로 폴더째 올려도 된다 (다만 새 버전마다 다시 올려야 한다).

## 3. 비밀 값을 넣는다

```bash
cp .env.example .env
vi .env
```

`MAJUNG_SECRET` 은 반드시 채운다. 만드는 법은 `.env.example` 에 적혀 있다.
이 값을 아는 사람은 **남의 로그인 세션을 만들어낼 수 있다.** 기본값 그대로
바깥에 열면 서버가 아예 시작되지 않는다.

`MAJUNG_UID` · `MAJUNG_GID` 는 1번에서 확인한 번호를 적는다.

## 4. 띄운다

```bash
docker compose up -d --build
```

처음 한 번은 이미지를 만드느라 몇 분 걸린다 (ARM 모델은 더 오래 걸린다).
잘 떴는지 본다.

```bash
docker compose ps          # majung 이 healthy 로 보여야 한다
docker compose logs -f     # 시작 배너가 보인다
curl http://127.0.0.1:8765/health
```

## 5. 운영자 계정을 한 번 만든다

유치원의 가입 신청을 승인하는 계정이다. 서버를 세울 때 **한 번만** 만든다.

```bash
docker compose run --rm majung firstout --operator 아이디:비밀번호 --host 127.0.0.1
```

`운영자 계정 생성: 아이디` 가 뜨면 **Ctrl+C 로 빠져나온다.** 계정은 이미 만들어졌다.

## 6. 밖에서 접속하게 한다 — 역방향 프록시와 HTTPS

**HTTPS 는 필수다.** 없으면 비밀번호와 세션이 평문으로 오간다.

DSM **제어판 → 로그인 포털 → 고급 → 역방향 프록시** 에서 규칙을 만든다.

| 칸 | 값 |
|---|---|
| 원본 프로토콜 · 호스트 · 포트 | HTTPS · `majung.aurabus.co.kr` · 443 |
| 대상 프로토콜 · 호스트 · 포트 | HTTP · `localhost` · **8765** |

**사용자 지정 헤더** 탭에서 `WebSocket` 을 눌러 기본값을 넣고, 아래 둘을 확인한다.

| 헤더 | 값 |
|---|---|
| `X-Forwarded-Proto` | `$scheme` |
| `X-Forwarded-For` | `$proxy_add_x_forwarded_for` |

`X-Forwarded-Proto` 가 없으면 세션 쿠키에 `Secure` 가 붙지 않는다.
`X-Forwarded-For` 가 없으면 감사 로그의 접속지가 전부 NAS 주소로 뭉갠다.

그다음 **제어판 → 보안 → 인증서** 에서 Let's Encrypt 인증서를 발급받아
이 도메인에 붙인다. DSM 이 만료 전에 알아서 갱신한다.

마지막으로 공유기에서 **443 포트만** NAS 로 넘긴다. 8765 는 열지 않는다 —
`docker-compose.yml` 이 `127.0.0.1` 에만 묶어 두어 밖에서 닿지 않는다.

## 7. 백업 — 한 벌은 반드시 바깥으로

서버가 매일 자기 사본을 `data/backup/` 에 떨궈 둔다 (30일치). 그런데
**서버와 백업이 같은 NAS 에 있다.** 그 장비가 죽으면 둘 다 없어진다.

**Hyper Backup** 으로 `/volume1/docker/majung/data` 를 다른 곳으로 한 벌 더
보낸다 — 다른 NAS, 외장 디스크, 클라우드 중 아무거나. 하루 한 번이면 넉넉하다.

원아 이름과 보호자 연락처가 든 자료이므로 **백업에도 암호를 건다.**

## 8. 새 버전 올리기

```bash
cd /volume1/docker/majung/app
git pull
docker compose up -d --build
```

자료는 `data/` 폴더에 있고 이미지 밖이므로 그대로 남는다.
잘못 올렸으면 되돌린다.

```bash
git log --oneline -5
git checkout <되돌릴 커밋>
docker compose up -d --build
```

## 9. 평소 관리

| 하는 일 | 명령 |
|---|---|
| 상태 보기 | `docker compose ps` |
| 기록 보기 | `docker compose logs -f --tail=100` |
| 다시 띄우기 | `docker compose restart` |
| 멈추기 | `docker compose down` |

Container Manager 화면에서도 같은 일을 눌러서 할 수 있다.

---

## 올리고 나서 확인할 것

- [ ] `https://주소/` 가 열리고 자물쇠가 보인다
- [ ] 로그인이 되고, 로그아웃 후 뒤로 가기로 되돌아가지지 않는다
- [ ] 감사 로그의 **접속지가 NAS 주소가 아니라 실제 접속자 주소**로 남는다
      (아니면 6번의 `X-Forwarded-For` 를 다시 본다)
- [ ] 귀가 처리 시각이 **한국 시각**으로 적힌다 (아니면 `TZ` 를 다시 본다)
- [ ] `data/backup/` 에 다음 날 사본이 생긴다
- [ ] Hyper Backup 이 그 폴더를 바깥으로 가져간다
- [ ] NAS 를 껐다 켜도 저절로 올라온다 (`restart: unless-stopped`)

## 옛 맥미니는

공개 서버로는 두지 않는 편이 좋다. 보안 업데이트가 끊긴 OS 를 인터넷에 여는 일이고,
아이들 이름과 보호자 연락처가 든 서버다. 사내망 안에서 시험용으로만 쓰거나,
쓰지 않는 것이 낫다.
