// ==============================
// ⚡ AURABUS Header Loader + Cache + Events
// ==============================

window.addEventListener("DOMContentLoaded", async () => {
  console.log("🔄 DOM loaded, checking header cache...");

  const container = document.getElementById("header-container");
  if (!container) {
    console.warn("⚠️ header-container 요소를 찾을 수 없습니다.");
    return;
  }

  const CACHE_KEY = "AURABUS_HEADER_HTML_v1"; // 버전 변경 시 캐시 갱신됨
  const cachedHeader = sessionStorage.getItem(CACHE_KEY);

  // ✅ 캐시가 있으면 즉시 렌더링
  if (cachedHeader) {
    container.innerHTML = cachedHeader;
    console.log("⚡ Header loaded from session cache");
    bindHeaderEvents();
    return;
  }

  // ✅ 없으면 fetch 후 캐시 저장
  try {
    const headerUrl = "./header.html";
    const res = await fetch(headerUrl, { cache: "no-cache" });
    if (!res.ok) throw new Error("❌ header.html 불러오기 실패");

    const html = await res.text();
    container.innerHTML = html;
    sessionStorage.setItem(CACHE_KEY, html);
    console.log("✅ Header fetched and cached");
    bindHeaderEvents();
  } catch (err) {
    console.error(err);
  }
});

// ==============================
// 📦 헤더 이벤트 처리 함수 (데스크탑 + 모바일 통합)
// ==============================
function bindHeaderEvents() {
  const header = document.querySelector(".header");
  const menuToggle = document.querySelector(".menu-toggle");
  const navMenu = document.querySelector(".nav-menu");

  if (!header || !menuToggle || !navMenu) {
    console.warn("⚠️ header 요소 탐색 실패");
    return;
  }

  // 🌑 메뉴 외부 클릭 시 닫기용 오버레이 생성
  let overlay = document.querySelector(".menu-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.classList.add("menu-overlay");
    document.body.appendChild(overlay);
  }

  // 🌐 햄버거 메뉴 토글
  menuToggle.addEventListener("click", () => {
    const isActive = navMenu.classList.toggle("active");
    menuToggle.classList.toggle("active");
    overlay.classList.toggle("active", isActive);
    document.body.style.overflow = isActive ? "hidden" : "";
  });

  // 🌑 오버레이 클릭 시 닫기
  overlay.addEventListener("click", () => {
    navMenu.classList.remove("active");
    menuToggle.classList.remove("active");
    overlay.classList.remove("active");
    document.body.style.overflow = "";
  });

  // 🖥️ 데스크탑 hover 드롭다운
  document.querySelectorAll(".nav-menu li.has-submenu").forEach((item) => {
    const submenu = item.querySelector(".sub-menu");
    if (!submenu) return;

    item.addEventListener("mouseenter", () => {
      if (window.innerWidth > 820) submenu.classList.add("active");
    });

    item.addEventListener("mouseleave", () => {
      if (window.innerWidth > 820) submenu.classList.remove("active");
    });
  });

  // 📱 모바일: 고객지원 클릭 시 슬라이드 아코디언
  document.querySelectorAll(".nav-menu li.has-submenu > a").forEach((link) => {
    link.addEventListener("click", (e) => {
      if (window.innerWidth <= 820) {
        e.preventDefault();
        const parent = link.parentElement;
        const submenu = parent.querySelector(".sub-menu");

        // 다른 메뉴 닫기
        document.querySelectorAll(".nav-menu li.has-submenu").forEach((el) => {
          if (el !== parent) {
            el.classList.remove("open");
            el.querySelector(".sub-menu")?.classList.remove("open");
          }
        });

        // ✅ 아코디언 토글
        parent.classList.toggle("open");
        submenu?.classList.toggle("open");

        // ✅ 부드러운 슬라이드 효과
        if (submenu) {
          if (submenu.classList.contains("open")) {
            submenu.style.maxHeight = submenu.scrollHeight + "px";
          } else {
            submenu.style.maxHeight = "0px";
          }
        }
      }
    });
  });

  // ✅ 리사이즈 시 초기화
  window.addEventListener("resize", () => {
    if (window.innerWidth > 820) {
      navMenu.classList.remove("active");
      menuToggle.classList.remove("active");
      overlay.classList.remove("active");
      document.body.style.overflow = "";
    }
  });

  console.log("✅ Header script initialized (Cached + Slide + Overlay)");
}
