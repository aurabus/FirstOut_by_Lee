# 아우라버스 홈페이지가 들어올 자리

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

**하나. `../images/main-heroback.png`**

어느 CSS 가 웹 폴더 **바깥**의 그림을 가리키고 있습니다. 지금 서버에서는 어쩌다
보이고 있을 수 있지만 정상은 아닙니다. 그 그림을 `images/` 안으로 옮기고
경로에서 `../` 를 빼야 합니다.

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
