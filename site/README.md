# 아우라버스 홈페이지가 들어올 자리

> 파일을 넣으신 뒤 **`python tools/site_check.py`** 를 돌려보세요.
> 빠진 파일이 있으면 화면이 깨지기 전에 알려줍니다.

이 폴더의 내용이 그대로 `www.aurabus.com` 이 됩니다. 지금은 자리만 잡아둔
`index.html` 하나가 들어 있습니다 — 진짜 홈페이지 파일을 가져와 **덮어쓰면** 됩니다.

정적 HTML 이라 만드는 과정(빌드)이 없습니다. 파일을 넣으면 그게 곧 홈페이지입니다.

## 무엇을 어디로 옮기나

맥에서 가져온 폴더 안의 **`Documents/Source/`** 가 그 홈페이지의 뿌리입니다.
그 안의 파일이 곧 `www.aurabus.com/...` 이 됩니다 (`Source` 라는 이름은 주소에
나오지 않습니다). **`Source` 폴더 자체가 아니라 그 안의 내용물**을 옮깁니다.

```
Documents/
├── index.html.en      ← 옮기지 않습니다 (아파치가 깔릴 때 딸려오는 기본 페이지)
└── Source/            ← 이 폴더 안의 것들을
    ├── css/               전부 site/ 로
    ├── images/
    ├── js/
    ├── main.html
    ├── company.html
    ├── ai-consulting.html
    ├── ai-edu.html
    ├── aurafarm.html
    ├── aurallm.html
    ├── notice.html
    ├── notice-detail.html
    ├── contact.html
    ├── header.html
    ├── footer.html
    └── ._로 시작하는 것들  ← 옮기지 않습니다 (맥이 만든 찌꺼기)
```

옮기고 나면 이렇게 되어야 합니다.

```
site/
├── main.html          ← 「/」 로 들어오면 이게 열립니다
├── company.html · ai-consulting.html · ai-edu.html · aurafarm.html
├── aurallm.html · notice.html · notice-detail.html · contact.html
├── header.html · footer.html
├── css/ · images/ · js/
└── README.md          ← 원래 있던 것, 그대로 두세요
```

### 잊지 마세요 — 자리표 `index.html` 은 지웁니다

`site/index.html` 은 제가 자리만 잡아둔 안내 화면입니다. 그대로 두면
**진짜 첫 화면(`main.html`)을 가려 버립니다.** 파일을 옮긴 뒤 지우세요.

### 이 홈페이지는 첫 화면이 `index.html` 이 아닙니다

`Source` 안에 `index.html` 이 없습니다. 맥의 아파치가 `/` 로 들어온 손님에게
`main.html` 을 내주도록 설정되어 있었습니다. 그래서 nginx 도 같은 규칙을 쓰도록
맞춰 두었습니다 (`deploy/site-nginx.conf`). **`main.html` 을 `index.html` 로
이름을 바꾸지 마세요** — 다른 화면들이 `main.html` 을 링크로 걸고 있어서 깨집니다.

### 옮기지 말아야 할 것

- **`._` 로 시작하는 파일 전부** — 맥이 USB 에 복사할 때 만드는 찌꺼기입니다.
  탐색기에서 이름 순으로 정렬하면 위쪽에 몰려 있습니다
- `.DS_Store`
- `index.html.en` — 아파치 기본 페이지입니다
- `백업` · `이전버전` 같은 폴더가 있다면 그것도

### 다 옮겼으면

```powershell
python tools/site_check.py
```

빠진 파일, 남은 찌꺼기, 지우지 않은 자리표를 모두 짚어줍니다.

## 옮기고 나서 살펴볼 것 셋

**하나. 그림이 너무 무겁습니다 — 이게 제일 급합니다**

지금 홈페이지가 부르는 그림을 전부 재어보니 **83개, 합쳐서 33.9MB** 입니다.
그중 첫 화면 배경 하나가 **16.4MB** 입니다.

| 그림 | 크기 |
|---|---|
| `images/main-heroback.png` | **16.4 MB** |
| `images/llm-section02-1.png` | 2.5 MB |
| `images/main_section03-card.png` | 2.3 MB |
| `images/llm-section02-3.png` | 1.9 MB |
| `images/llm-section02-2.png` | 1.8 MB |
| `images/main_section01-card.png` | 1.4 MB |

첫 화면을 여는 데만 20MB 가까이 내려받게 됩니다. 휴대폰으로 들어온 사람은
한참 기다리고 데이터도 그만큼 씁니다. **NAS 로 옮기면 사무실 회선의 업로드 속도가
그대로 손님이 기다리는 시간이 되므로** 지금보다 더 느려집니다.

사진 성격의 그림은 PNG 가 아니라 JPG(또는 WebP)로 바꾸면 **크기가 수십 분의 일**로
줄어듭니다. 16.4MB 짜리 배경은 300KB 안쪽으로 만들 수 있습니다. 눈으로는 차이를
못 느낍니다. 아이콘처럼 색이 단순한 것만 PNG 로 두면 됩니다.

> `css/style_main.css` 의 `url("../images/...")` 는 **정상입니다.** CSS 가 `css/`
> 안에 있으니 `../images/` 가 곧 `/images/` 입니다. 앞서 이 부분을 문제로 적었는데
> 확인해 보니 제 착각이었습니다.

**둘. 공통 머리글을 자바스크립트로 끼워 넣는 방식**

`header_fast.js` 가 `header.html` 을 따로 불러와 화면에 넣습니다. 그래서 페이지가
열릴 때 **머리글 자리가 잠깐 비었다가 나타납니다.** 검색엔진도 머리글의 메뉴를
잘 못 읽습니다. 각 페이지에 머리글을 직접 써넣는 편이 빠르고 안전합니다.

**셋. 바깥에서 가져오는 것 세 가지**

| 무엇 | 어디서 | 어떻게 할까 |
|---|---|---|
| Noto Sans KR 글꼴 | Google Fonts | 담아오면 인터넷이 느려도 글자가 안 깨집니다 |
| Font Awesome 아이콘 | cdnjs | 쓰는 아이콘만 골라 담으면 훨씬 가벼워집니다 |
| 구글 지도 (회사 위치) | Google Maps | 지도는 그대로 두는 편이 낫습니다 |

손잡고 마중은 인터넷이 끊겨도 열리도록 글꼴을 서버에 담아두었습니다.
홈페이지도 같은 방식으로 맞출 수 있습니다.

**글꼴과 아이콘을 담아오면 방문자 정보가 밖으로 나가지 않습니다.** 지금은 페이지를
열 때마다 방문자의 접속 주소가 구글과 cdnjs 로 함께 전달됩니다. 서비스를 국내에
두기로 하신 뜻과 결이 맞으려면 이 둘도 담아오는 편이 낫습니다.
지도는 기능상 어쩔 수 없으니 그대로 두시면 됩니다.
