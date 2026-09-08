// ==============================
// ⚡ AURABUS Header Loader (Fast Optimized)
// ==============================
(async () => {
  console.log("🚀 header_fast.js initializing...");

  const container = document.getElementById("header-container");
  if (!container) {
    console.warn("⚠️ header-container 요소를 찾을 수 없습니다.");
    return;
  }

  const cacheKey = "aurabus_header_cache";

  // ✅ 개발·테스트 환경 자동 인식
  const hostname = location.hostname;
  const isDevEnv =
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname.endsWith(".local") ||
    hostname.includes("dev.") ||
    hostname.includes("staging.") ||
    location.protocol === "file:"; // file:/// 경로로 열릴 때

  // ✅ 개발/테스트 환경에서는 캐시 무시
  if (isDevEnv) {
    sessionStorage.removeItem(cacheKey);
    console.log(`🧹 개발/테스트 환경(${hostname}): header 캐시 무시 중`);
  }

  let headerHTML = sessionStorage.getItem(cacheKey);

  // ==============================
  // 🧠 세션 캐시 우선 사용 (단, dev 환경은 제외)
  // ==============================
  if (headerHTML && !isDevEnv) {
    container.innerHTML = headerHTML;
    bindHeaderEvents();
    console.log("✅ Header loaded from sessionStorage");
  } else {
    try {
      // ✅ 개발/테스트에서는 무조건 최신 버전 로드
      const fetchURL = isDevEnv
        ? `./header.html?v=${Date.now()}`
        : "./header.html";

      const res = await fetch(fetchURL, { cache: "no-store" });
      if (!res.ok) throw new Error("❌ header.html 불러오기 실패");

      headerHTML = await res.text();
      container.innerHTML = headerHTML;

      // 운영 환경에서만 캐싱
      if (!isDevEnv) sessionStorage.setItem(cacheKey, headerHTML);

      bindHeaderEvents();
      console.log(
        `✅ Header loaded via fetch (${isDevEnv ? "DEV/TEST Mode" : "CACHED Mode"})`
      );
    } catch (err) {
      console.error(err);
    }
  }
})();

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
    header.classList.toggle("shadow", isActive);
    document.body.style.overflow = isActive ? "hidden" : "";
  });

  // 🌑 오버레이 클릭 시 닫기
  overlay.addEventListener("click", () => {
    navMenu.classList.remove("active");
    menuToggle.classList.remove("active");
    overlay.classList.remove("active");
    header.classList.remove("shadow");
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

  // 📱 모바일: 고객지원 클릭 시 아코디언 슬라이드
  document.querySelectorAll(".nav-menu li.has-submenu > a").forEach((link) => {
  link.addEventListener("click", (e) => {
    if (window.innerWidth <= 820) {
      const text = link.textContent.trim();
      const parent = link.parentElement;

      // ✅ 아코디언 적용 대상: "고객지원"만
      if (text !== "고객지원") {
        // 다른 메뉴는 기본 링크 동작 그대로 → 페이지 이동
        return;
      }

      // ✅ 고객지원 클릭 시: 기본 이동 막고 아코디언 동작
      e.preventDefault();
      e.stopPropagation();

      const submenu = parent.querySelector(".sub-menu");

      // 다른 아코디언 닫기
      document.querySelectorAll(".nav-menu li.has-submenu").forEach((el) => {
        if (el !== parent) {
          el.classList.remove("open");
          const sm = el.querySelector(".sub-menu");
          if (sm) sm.style.maxHeight = "0px";
        }
      });

      const isOpen = parent.classList.toggle("open");
      if (submenu) {
        submenu.style.maxHeight = isOpen ? submenu.scrollHeight + "px" : "0px";
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
      header.classList.remove("shadow");
      document.body.style.overflow = "";
    }
  });

  console.log("✅ Header script initialized (FAST MODE)");
}
