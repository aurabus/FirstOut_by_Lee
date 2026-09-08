# NAS 한 대로 홈페이지와 손잡고 마중 올리기

처음 해보시는 분을 앞에 두고 쓴 문서입니다. **위에서부터 순서대로** 따라가시면 됩니다.
중간에 막히면 맨 아래 「문제가 생기면」을 보세요.

시간은 넉넉히 **두세 시간** 잡으시면 됩니다. 대부분은 기다리는 시간입니다.

---

## 0. 무엇을 만드는 것인가

지금은 이렇습니다.

```
   http (80)  ──→  맥미니 아파치  ──→  홈페이지
   https(443) ──→  NAS          ──→  DSM 로그인 화면 (밖에 보이면 안 되는 것)
```

이렇게 바꿉니다.

```
                    인터넷
                      │           들어오는 구멍이 없습니다
                 Cloudflare       인증서·속도·막이를 대신해 줍니다
                      ↑
                      │  NAS 가 바깥으로 걸어 나가는 연결 하나
        ┌─────────────┴──────────────────┐
        │  NAS                            │
        │    site     홈페이지             │
        │    majung   손잡고 마중          │
        │    tunnel   바깥과 잇는 통로      │
        └─────────────────────────────────┘
```

| 주소 | 가는 곳 |
|---|---|
| `aurabus.com` · `www.aurabus.com` | 홈페이지 |
| `majung.aurabus.com` | 손잡고 마중 |
| DSM 관리 화면 | **밖에 내지 않습니다** — 테일스케일로만 |

### 왜 이렇게 하나

- **공유기에 구멍을 안 뚫습니다.** 지금 DSM 로그인 창이 인터넷에 떠 있는 문제가
  설정이 아니라 구조로 사라집니다
- **학교에서 받은 고정 IP 에 매이지 않습니다.** IP 가 바뀌어도, 회수당해도 그대로 돕니다
- **인증서를 신경 쓸 일이 없습니다.** Cloudflare 가 붙이고 갱신합니다
- **홈페이지가 빨라집니다.** 정적 사이트라 Cloudflare 가 통째로 대신 내어줍니다

### 낱말 몇 개

| 말 | 뜻 |
|---|---|
| **컨테이너** | 프로그램 한 벌을 상자에 담아 통째로 돌리는 것. 이 상자 셋이 NAS 에서 돕니다 |
| **도커 / Container Manager** | 그 상자를 돌리는 프로그램. 시놀로지에서는 이름이 Container Manager 입니다 |
| **터널** | NAS 가 Cloudflare 로 걸어 나가는 전화선. 이 선으로 손님이 들어옵니다 |
| **네임서버** | 「aurabus.com 이 어디냐」를 답해주는 곳. 이것을 Cloudflare 로 옮깁니다 |
| **SSH** | 검은 화면으로 NAS 에 명령을 넣는 것. 무섭지 않습니다, 그냥 글자입니다 |

---

## 1. 준비물

- [ ] 시놀로지 NAS, **DSM 7.0 이상**
- [ ] 패키지 센터에 **Container Manager** 가 보일 것
      (DSM 6 이면 이름이 `Docker` 입니다. 그것도 됩니다.
       아예 안 보이면 그 NAS 모델은 도커를 못 씁니다 — 저에게 알려주세요)
- [ ] `aurabus.com` 도메인 관리 화면에 들어갈 수 있을 것 (네임서버를 바꿔야 합니다)
- [ ] 맥미니에 있는 홈페이지 파일
- [ ] Cloudflare 계정 (없으면 만듭니다. 무료입니다)

**지금 돌고 있는 홈페이지는 건드리지 않습니다.** 마지막 11장에서 갈아타기 전까지
지금 그대로 돌아가므로, 중간에 잘못돼도 서비스가 끊기지 않습니다.

---

## 2. 홈페이지 파일을 `site/` 에 넣는다

맥미니의 웹 폴더를 통째로 가져와 이 저장소의 `site/` 폴더에 넣습니다.
무엇을 가져와야 하는지는 **[site/README.md](../site/README.md)** 에 목록으로 적어두었습니다.

가장 중요한 것 하나 — **`index.html` 이 있어야 합니다.** 이 파일이 없으면
`www.aurabus.com` 으로 들어왔을 때 아무것도 안 나옵니다.

넣으셨으면 윈도우에서 저장소에 올려둡니다.

```powershell
git add site
git commit -m "홈페이지 파일을 가져옴"
git push
```

---

## 3. NAS 준비

### 3-1. Container Manager 를 설치한다

DSM 에서 **패키지 센터** → `Container Manager` 검색 → 설치.

### 3-2. 자료가 쌓일 폴더를 만든다

**File Station** 에서 `docker` 공유 폴더 안에 `majung` 폴더를 만듭니다.

```
/volume1/docker/majung/
```

### 3-3. SSH 를 켠다

**제어판 → 터미널 및 SNMP → SSH 서비스 활성화** 체크 → 적용.

> 다 끝나고 나면 이 체크를 다시 꺼두셔도 됩니다. 켜두시려면 포트를 22 에서
> 다른 번호로 바꿔두시는 편이 좋습니다. 어차피 밖에서는 안 들어오지만요.

### 3-4. NAS 에 들어가 본다

윈도우 **PowerShell** 을 열고 (시작 → `powershell` 입력):

```powershell
ssh 관리자아이디@NAS주소
```

`NAS주소` 는 사무실 안에서라면 `192.168.x.x` 같은 것입니다. DSM 로그인할 때
쓰는 주소와 같습니다. 처음 들어가면 「계속하시겠습니까」를 묻는데 `yes` 를 칩니다.
비밀번호를 칠 때 **아무것도 안 보이는 게 정상**입니다. 그냥 치고 엔터를 누르세요.

### 3-5. 내 번호를 확인한다

들어가셨으면 이걸 칩니다.

```bash
id
```

```
uid=1026(aurabus) gid=100(users) ...
```

이렇게 나오면 **1026 과 100** 을 적어두세요. 뒤에서 씁니다.
이 번호가 안 맞으면 손잡고 마중이 자료를 못 쓰고 죽습니다.

---

## 4. 코드를 NAS 로 받는다

NAS 에 들어간 그 검은 화면에서 이어서 칩니다.

```bash
cd /volume1/docker/majung
git clone https://github.com/aurabus/FirstOut_by_Lee.git app
cd app
```

`git: command not found` 라고 나오면 DSM 패키지 센터에서 **Git Server** 를
설치하고 다시 해보세요.

받아졌는지 봅니다.

```bash
ls
```

`Dockerfile`, `docker-compose.yml`, `site`, `src` 같은 것들이 보이면 된 것입니다.

---

## 5. 비밀 값을 채운다

### 5-1. 세션 서명 키를 만든다

**윈도우 PowerShell 을 하나 더 열어서** (NAS 말고 내 PC 에서) 칩니다.

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

길쭉한 글자가 나옵니다. 이걸 복사해 둡니다.

> 이 값을 아는 사람은 남의 로그인을 만들어낼 수 있습니다. 카카오톡이나 메일로
> 보내지 마시고, 여기서 복사해 바로 붙여 넣으세요.

### 5-2. `.env` 파일을 만든다

NAS 화면으로 돌아와서:

```bash
cp .env.example .env
vi .env
```

`vi` 는 처음이면 낯섭니다. 이렇게 쓰시면 됩니다.

| 하고 싶은 것 | 누를 것 |
|---|---|
| 글자를 고치기 시작 | `i` (왼쪽 아래에 `-- INSERT --` 가 뜹니다) |
| 다 고쳤다 | `Esc` |
| 저장하고 나가기 | `Esc` 누른 뒤 `:wq` 치고 엔터 |
| 저장 안 하고 나가기 | `Esc` 누른 뒤 `:q!` 치고 엔터 |

채울 것은 이 넷입니다.

```
MAJUNG_SECRET=아까_복사한_긴_글자
MAJUNG_PUBLIC_URL=https://majung.aurabus.com
MAJUNG_UID=1026        ← 3-5 에서 본 번호
MAJUNG_GID=100         ← 3-5 에서 본 번호
```

`CF_TUNNEL_TOKEN` 은 아직 비워둡니다. 8장에서 받아옵니다.

---

## 6. 터널 없이 먼저 띄워본다

밖과 잇기 전에 **NAS 안에서만** 잘 도는지 봅니다. 여기서 확인하고 넘어가면
뒤에서 문제가 생겨도 원인이 절반으로 줄어듭니다.

```bash
docker compose up -d --build site majung
```

맨 뒤에 `site majung` 을 붙였습니다 — **터널은 빼고 둘만** 띄우라는 뜻입니다.

처음에는 손잡고 마중을 만드느라 몇 분 걸립니다. 화면에 글자가 죽 흐르는 것이 정상입니다.
`docker: command not found` 라고 나오면 `sudo docker compose ...` 로 다시 해보세요.

### 잘 떴는지 본다

```bash
docker compose ps
```

`site` 와 `majung` 이 `Up` 으로 보여야 합니다. 그다음:

```bash
curl -s -o /dev/null -w "홈페이지 %{http_code}\n" http://127.0.0.1:8080/
curl -s http://127.0.0.1:8765/health
```

`홈페이지 200` 과 `{"status":"ok", ...}` 가 나오면 성공입니다.

### 운영자 계정을 한 번 만든다

유치원의 가입 신청을 승인하는 계정입니다. **딱 한 번만** 만듭니다.

```bash
docker compose run --rm majung firstout --operator 아이디:비밀번호 --host 127.0.0.1
```

`아이디:비밀번호` 자리에 원하는 값을 넣으세요 (예: `aurabus:긴비밀번호`).
`운영자 계정 생성: ...` 이라고 뜨면 **`Ctrl` + `C`** 를 눌러 빠져나옵니다.
계정은 이미 만들어졌습니다.

---

## 7. 도메인을 Cloudflare 로 옮긴다

여기가 유일하게 「되돌리기 번거로운」 단계입니다. 다만 **홈페이지가 멈추지는 않습니다** —
Cloudflare 가 지금 설정을 그대로 읽어가기 때문입니다.

1. [dash.cloudflare.com](https://dash.cloudflare.com) 에서 계정을 만듭니다 (무료)
2. **Add a site** → `aurabus.com` 입력
3. 요금제는 **Free** 를 고릅니다
4. Cloudflare 가 지금 DNS 설정을 읽어와 보여줍니다.
   **여기서 목록을 사진으로 찍어두세요.** 나중에 대조할 때 씁니다
5. 화면에 **네임서버 두 개**가 나옵니다 (예: `dana.ns.cloudflare.com`)
6. `aurabus.com` 을 산 곳(가비아·후이즈 등)에 로그인해서
   **네임서버를 그 두 개로 바꿉니다**. 지금은 데이콤(LG U+) 것으로 되어 있습니다

바뀌는 데 보통 몇 분에서 몇 시간 걸립니다. Cloudflare 화면이 **Active** 가 되면 끝입니다.

> **중요 — 이 단계에서는 아직 아무것도 안 바뀝니다.** 도메인이 여전히 학교 IP 를
> 가리키고 있어서 홈페이지는 지금처럼 돌아갑니다. 갈아타는 건 9장입니다.

---

## 8. 터널을 만들고 토큰을 받는다

1. Cloudflare 화면 왼쪽에서 **Zero Trust** 로 들어갑니다
   (처음 들어가면 팀 이름을 정하라고 합니다. 아무거나, 무료 요금제를 고르세요.
    카드 번호를 물어볼 수 있는데 무료 요금제는 돈이 나가지 않습니다)
2. **Networks → Tunnels** → **Create a tunnel**
3. **Cloudflared** 를 고릅니다
4. 터널 이름을 정합니다 — `aurabus-nas` 정도가 좋습니다
5. 다음 화면에 설치 명령이 뜨는데 **그건 쓰지 않습니다.** 그 명령 안에 있는
   **아주 긴 글자(토큰)** 만 복사합니다. `eyJhIjoi...` 로 시작하는 것입니다

> 화면 생김새는 Cloudflare 가 가끔 바꿉니다. 이름이 조금 달라도
> **「터널 만들기 → cloudflared → 토큰 복사」** 라는 흐름은 같습니다.

### 토큰을 `.env` 에 넣는다

NAS 화면에서:

```bash
cd /volume1/docker/majung/app
vi .env
```

```
CF_TUNNEL_TOKEN=eyJhIjoi...아주긴글자...
```

`Esc` → `:wq` → 엔터.

---

## 9. 어느 주소를 어디로 보낼지 정한다

Cloudflare 의 터널 화면에서 **Public Hostname** 탭으로 갑니다.
**Add a public hostname** 을 눌러 **세 개**를 만듭니다.

**첫째 — 홈페이지 (www)**

| 칸 | 넣을 값 |
|---|---|
| Subdomain | `www` |
| Domain | `aurabus.com` |
| Type | `HTTP` |
| URL | `site:80` |

**둘째 — 홈페이지 (www 없이)**

| 칸 | 넣을 값 |
|---|---|
| Subdomain | (비워둡니다) |
| Domain | `aurabus.com` |
| Type | `HTTP` |
| URL | `site:80` |

**셋째 — 손잡고 마중**

| 칸 | 넣을 값 |
|---|---|
| Subdomain | `majung` |
| Domain | `aurabus.com` |
| Type | `HTTP` |
| URL | `majung:8000` |

> `site:80` 처럼 이름으로 적는 것이 맞습니다. 컨테이너끼리는 이름으로 통합니다.
> `localhost` 나 IP 를 적으면 안 됩니다.
>
> `HTTP` 인데 괜찮냐고요? 괜찮습니다. 손님과 Cloudflare 사이는 HTTPS 이고,
> Cloudflare 와 NAS 사이는 터널 안이라 이미 암호화되어 있습니다.

---

## 10. 터널을 켜고 확인한다

NAS 화면에서 이번엔 셋을 다 띄웁니다.

```bash
cd /volume1/docker/majung/app
docker compose up -d
docker compose logs -f tunnel
```

로그에 `Registered tunnel connection` 같은 줄이 **네 개쯤** 뜨면 연결된 것입니다.
`Ctrl` + `C` 로 로그 보기를 빠져나옵니다 (컨테이너는 계속 돕니다).

### 밖에서 확인한다

**휴대폰에서 와이파이를 끄고** (사무실 밖에서 보는 것과 같게 만들려는 것입니다)
주소를 쳐봅니다.

- `https://www.aurabus.com` → 홈페이지가 뜨고 **자물쇠가 보여야** 합니다
- `https://majung.aurabus.com` → 손잡고 마중 로그인 화면
- `https://aurabus.com` → 홈페이지

셋 다 되면 갈아타기 끝입니다.

---

## 11. 공유기의 구멍을 막는다

이제 **이 단계가 오늘의 진짜 목적**입니다.

공유기 관리 화면에 들어가 **포트포워딩** 설정을 찾습니다.

- **80 포트** → 맥미니로 가던 것 → **지웁니다**
- **443 포트** → NAS 로 가던 것 → **지웁니다**
- 다른 포트가 열려 있으면 그것도 필요한지 살펴보세요

지우고 나서 다시 확인합니다. 휴대폰(와이파이 끈 상태)에서:

- `https://www.aurabus.com` → **여전히 열려야 합니다** (터널로 들어가므로)
- `https://aurabus.com:8043` → **안 열려야 합니다** (DSM 로그인 창이 사라져야 합니다)

DSM 로그인 창이 아직 보이면 포워딩이 덜 지워진 것입니다.

### 그럼 NAS 관리는 어떻게 하나

**테일스케일**로 들어가시면 됩니다. 이미 쓰고 계시니 NAS 에도 설치해 두세요
(패키지 센터에 없으면 시놀로지 커뮤니티 패키지로 있습니다). 그러면 어디서든
테일스케일 주소로 DSM 에 들어갈 수 있고, 인터넷에는 아무것도 열리지 않습니다.

---

## 12. 자료를 지킨다

NAS 한 대로 돌리기로 하셨으니, 이 장은 **건너뛰지 마세요.** 한 대가 멈추면 둘 다 멈춥니다.

### 12-1. 백업 한 벌은 반드시 바깥으로

손잡고 마중은 매일 자기 사본을 `data/backup/` 에 떨궈 둡니다 (30일치).
그런데 **서버와 백업이 같은 NAS 에 있습니다.** 그 장비가 죽으면 둘 다 없어집니다.

**Hyper Backup** 으로 `/volume1/docker/majung/data` 를 다른 곳으로 한 벌 더 보냅니다.
다른 NAS, 외장 디스크, 클라우드 중 아무거나 좋습니다. 하루 한 번이면 넉넉합니다.

원아 이름과 보호자 연락처가 든 자료이므로 **백업에도 암호를 겁니다.**

### 12-2. UPS 를 답니다

정전으로 NAS 가 갑자기 꺼지면 데이터베이스가 깨질 수 있습니다.
UPS 를 USB 로 물리면 **제어판 → 하드웨어 및 전원 → UPS** 에서 인식하고,
정전 때 NAS 가 스스로 안전하게 내려갑니다. 10만 원대면 충분합니다.

가장 값싼 보험입니다.

---

## 13. 평소 관리

### 새 버전 올리기

```bash
cd /volume1/docker/majung/app
git pull
docker compose up -d --build
```

**홈페이지와 손잡고 마중이 함께 갱신됩니다.** 자료(`data/`)는 그대로 남습니다.

### 홈페이지만 고칠 때

`site/` 안의 파일만 바꾸면 됩니다. 다시 띄울 필요도 없습니다 — 새로고침하면 바뀝니다.

```bash
cd /volume1/docker/majung/app
git pull        # 윈도우에서 고쳐 push 했다면
```

### 자주 쓰는 것

| 하는 일 | 명령 |
|---|---|
| 상태 보기 | `docker compose ps` |
| 기록 보기 | `docker compose logs -f --tail=100 majung` |
| 다시 띄우기 | `docker compose restart` |
| 멈추기 | `docker compose down` |

Container Manager 화면에서도 같은 일을 눌러서 할 수 있습니다.

### 잘못 올렸을 때 되돌리기

```bash
git log --oneline -5          # 최근 다섯 개를 봅니다
git checkout <되돌릴 것의 번호>
docker compose up -d --build
```

---

## 14. 문제가 생기면

**홈페이지 자리에 「홈페이지 파일이 아직 없습니다」가 뜬다**
→ `site/` 에 진짜 파일을 안 넣으신 것입니다. 2장으로.

**`https://www.aurabus.com` 이 안 열린다**
→ `docker compose logs tunnel` 을 봅니다. `Registered tunnel connection` 이 없으면
   토큰이 잘못된 것입니다. 8장에서 다시 복사하세요.

**손잡고 마중이 계속 죽는다 (`Restarting` 이 반복된다)**
→ `docker compose logs majung` 을 봅니다.
   - `Permission denied` → 3-5 의 번호가 안 맞습니다. `.env` 의 UID/GID 를 고치고
     `docker compose up -d --build majung`
   - `MAJUNG_SECRET` 이야기가 나오면 → `.env` 에 키를 안 넣으신 것입니다

**감사 로그의 접속지가 전부 같은 주소로 나온다**
→ `.env` 의 `MAJUNG_PROXY_HOPS` 가 `1` 인지 봅니다.

**귀가 시각이 9시간 어긋난다**
→ `docker compose exec majung date` 를 쳐서 한국 시각이 나오는지 봅니다.
   아니면 저에게 알려주세요.

**DSM 로그인 창이 아직 인터넷에 보인다**
→ 공유기 포트포워딩이 덜 지워진 것입니다. 11장으로.

---

## 다 하고 나서 확인할 목록

- [ ] `https://www.aurabus.com` 이 열리고 자물쇠가 보인다
- [ ] `https://aurabus.com` (www 없이) 도 열린다
- [ ] `https://majung.aurabus.com` 에서 로그인이 된다
- [ ] `https://aurabus.com:8043` 이 **안** 열린다 (DSM 이 숨겨졌다)
- [ ] 공유기 포트포워딩에 80·443 이 없다
- [ ] 테일스케일로 DSM 에 들어갈 수 있다
- [ ] 감사 로그의 접속지가 **실제 접속자 주소**로 남는다
- [ ] 귀가 처리 시각이 **한국 시각**으로 적힌다
- [ ] 다음 날 `data/backup/` 에 사본이 생긴다
- [ ] Hyper Backup 이 그 폴더를 바깥으로 가져간다
- [ ] UPS 가 물려 있다
- [ ] NAS 를 껐다 켜도 셋 다 저절로 올라온다

---

## 나중에 — 유치원이 늘면

NAS 한 대라 그 한 대가 멈추면 둘 다 멈춥니다. **돈을 받는 유치원이 붙거나
대여섯 곳을 넘으면** 손잡고 마중만 작은 VPS 로 옮기시는 것을 권합니다.

지금 만든 도커 묶음이 그대로 올라가므로 옮기는 데 하루면 됩니다.
그때는 홈페이지만 NAS 에 남기거나, 홈페이지도 Cloudflare Pages 로 올리면 됩니다.
