# 아우라버스 홈페이지가 들어올 자리

> 파일을 넣으신 뒤 **`python tools/site_check.py`** 를 돌려보세요.
> 빠진 파일이 있으면 화면이 깨지기 전에 알려줍니다.

이 폴더의 내용이 그대로 `www.aurabus.com` 이 됩니다. 지금은 자리만 잡아둔
`index.html` 하나가 들어 있습니다 — 진짜 홈페이지 파일을 가져와 **덮어쓰면** 됩니다.

정적 HTML 이라 만드는 과정(빌드)이 없습니다. 파일을 넣으면 그게 곧 홈페이지입니다.

## 지금 돌고 있는 홈페이지에서 가져와야 할 것

맥미니의 웹 폴더(아파치의 `DocumentRoot`, 보통 `/Library/WebServer/Documents`
또는 사용자 폴더의 `Sites`)를 통째로 가져오시면 됩니다. 빠뜨리기 쉬운 것을
적어두니 대조해 보세요.

```
site/
├── index.html              ← 「/」 로 들어왔을 때 열리는 화면. 없으면 안 됩니다
├── main.html               (index.html 과 같은 내용으로 보입니다)
├── company.html
├── ai-consulting.html
├── ai-edu.html
├── aurafarm.html
├── aurallm.html
├── notice.html
├── contact.html
├── header.html             ← 공통 머리글. js 가 불러와 끼워 넣습니다
├── css/
│   ├── style.css
│   ├── style_main.css
│   ├── style_sub.css
│   ├── contact.css
│   ├── notice.css
│   ├── style-ai-consulting.css
│   └── style-ai-edu.css
├── js/
│   ├── header_fast.js
│   ├── ai-consulting.js
│   └── notice.js
└── images/                 ← 그림 90여 개. 폴더째 가져오세요
```

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
