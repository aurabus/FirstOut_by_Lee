// =============================
// 📄 NOTICE.JS
// 목록 + 필터 + 검색 + 페이징 + 상세 + 이전/다음글
// =============================

// 1. 데이터
const notices = [
  {
    id: 5,
    category: "공지",
    title: "AURABUS 연말 휴무 안내",
    date: "2025.12.24",
    content: `
      안녕하세요. AURABUS입니다.<br><br>
      연말 휴무 일정은 다음과 같습니다.<br><br>
      📅 <strong>휴무일</strong>: 2025년 12월 31일 ~ 2026년 1월 2일<br>
      정상근무는 2026년 1월 5일부터 시작됩니다.<br><br>
      고객 여러분의 한 해 성원에 감사드립니다.
    `,
  },
  {
    id: 4,
    category: "업데이트",
    title: "AURA LLM v2.3 기능 개선 안내",
    date: "2025.11.20",
    content: `
      AURA LLM이 아래와 같이 개선되었습니다.<br><br>
      - 답변 정확도 향상<br>
      - 생성 속도 평균 22% 향상<br>
      - 모델 관리 UI 개편<br><br>
      지속적으로 개선하겠습니다.
    `,
  },
  {
    id: 3,
    category: "점검",
    title: "AURA LLM 시스템 점검 안내 (11/05)",
    date: "2025.11.05",
    content: `
      안정적인 서비스 제공을 위한 시스템 점검이 진행됩니다.<br><br>
      📅 2025년 11월 5일 22:00 ~ 23:30<br>
      점검 중에는 서비스가 일시 중단될 수 있습니다.
    `,
  },
  {
    id: 2,
    category: "업데이트",
    title: "AURA FARM 신규 기능 업데이트",
    date: "2025.10.12",
    content: `
      AURA FARM 플랫폼에 새로운 기능이 추가되었습니다.<br><br>
      - AI 작물 건강 모니터링 강화<br>
      - 자동 리포트 주간 발행<br><br>
      관리자 페이지에서 자세히 확인하세요.
    `,
  },
  {
    id: 1,
    category: "공지",
    title: "AURABUS 공식 홈페이지 오픈",
    date: "2025.09.30",
    content: `
      AURABUS 공식 홈페이지가 오픈되었습니다.<br>
      앞으로 다양한 소식과 업데이트를 안내드리겠습니다.
    `,
  },
];

// 2. 상태
let currentPage = 1;
const itemsPerPage = 5;
let filteredNotices = [...notices];
let currentCategory = "전체";

// 3. 목록 렌더링
function renderNotices() {
  const listContainer = document.getElementById("notice-list");
  if (!listContainer) return;

  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginated = filteredNotices.slice(startIndex, startIndex + itemsPerPage);

  listContainer.innerHTML = paginated
    .map(
      (n) => `
      <tr>
        <td>${n.id}</td>
        <td><a href="notice-detail.html?id=${n.id}">${n.title}</a></td>
        <td>${n.category}</td>
        <td>${n.date}</td>
      </tr>
    `
    )
    .join("");

  renderPagination();
}

// 4. 페이지네이션
function renderPagination() {
  const container = document.getElementById("notice-pagination");
  if (!container) return;

  const totalPages = Math.ceil(filteredNotices.length / itemsPerPage);
  let html = "";

  for (let i = 1; i <= totalPages; i++) {
    html += `<button class="page-btn ${i === currentPage ? "active" : ""}" data-page="${i}">${i}</button>`;
  }

  container.innerHTML = html;

  container.querySelectorAll(".page-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentPage = parseInt(btn.dataset.page);
      renderNotices();
    });
  });
}

// 5. 검색
function setupSearch() {
  const input = document.getElementById("notice-search");
  if (!input) return;

  input.addEventListener("input", (e) => {
    const keyword = e.target.value.toLowerCase();
    filteredNotices = notices.filter(
      (n) =>
        n.title.toLowerCase().includes(keyword) ||
        n.content.toLowerCase().includes(keyword)
    );
    currentPage = 1;
    renderNotices();
  });
}

// 6. 카테고리
function setupCategoryFilter() {
  const buttons = document.querySelectorAll(".notice-category button");
  if (!buttons.length) return;

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      currentCategory = btn.dataset.category;
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      filteredNotices =
        currentCategory === "전체"
          ? [...notices]
          : notices.filter((n) => n.category === currentCategory);

      currentPage = 1;
      renderNotices();
    });
  });
}

// 7. 상세 페이지 + 이전/다음글
function loadNoticeDetail() {
  const detailBox = document.getElementById("notice-detail");
  if (!detailBox) return;

  const params = new URLSearchParams(window.location.search);
  const id = parseInt(params.get("id"), 10);
  const notice = notices.find((n) => n.id === id);

  if (!notice) {
    detailBox.innerHTML = "<p>해당 공지를 찾을 수 없습니다.</p>";
    return;
  }

  const idx = notices.findIndex((n) => n.id === id);
  const prev = notices[idx + 1];
  const next = notices[idx - 1];

detailBox.innerHTML = `
  <div class="notice-detail-card">
    <div class="notice-detail-header">
      <h2>${notice.title}</h2>
      <p class="notice-date">${notice.date}</p>
    </div>

    <div class="notice-detail-content">${notice.content}</div>

    <!-- ✅ 이전글 / 다음글 -->
    <div class="notice-nav">
      ${
        prev
          ? `<a href="notice-detail.html?id=${prev.id}" class="prev">← 이전글: ${prev.title}</a>`
          : "<span></span>"
      }
      ${
        next
          ? `<a href="notice-detail.html?id=${next.id}" class="next">다음글: ${next.title} →</a>`
          : "<span></span>"
      }
    </div>
  </div>

  <!-- ✅ 박스 밖에 독립된 버튼 -->
  <div class="notice-list-outside">
    <a href="notice.html" class="btn-list">목록</a>
  </div>
`;

}

// 8. 초기화
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("notice-list")) {
    renderNotices();
    setupSearch();
    setupCategoryFilter();
  }
  if (document.getElementById("notice-detail")) {
    loadNoticeDetail();
  }
});
