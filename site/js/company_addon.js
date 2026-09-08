// ==============================
// 📱 820px 이하에서 Business 슬라이드 전환 (세로형 유지 + 개별 슬라이드)
// ==============================
document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ company_addon.js loaded");

  // 820px 이하일 때만 동작
  if (window.innerWidth > 820) {
    console.log("💻 Desktop/tablet - Swiper disabled");
    return;
  }

  // business-grid 가져오기
  const grid = document.querySelector(".business-grid");
  if (!grid) {
    console.warn("⚠️ .business-grid not found");
    return;
  }

  // ✅ Swiper 기본 구조 생성
  const swiperContainer = document.createElement("div");
  swiperContainer.classList.add("business-slider", "swiper");

  const swiperWrapper = document.createElement("div");
  swiperWrapper.classList.add("swiper-wrapper");

  // ✅ 각 카드들을 개별 슬라이드로 감싸기
  const cards = grid.querySelectorAll(".business-card");
  cards.forEach((card, i) => {
    const slide = document.createElement("div");
    slide.classList.add("swiper-slide");

    // 카드 복제해서 슬라이드에 추가
    const clone = card.cloneNode(true);
    slide.appendChild(clone);

    swiperWrapper.appendChild(slide);
    console.log(`🧩 Added slide ${i + 1}`);
  });

  // ✅ 페이지네이션 추가
  const pagination = document.createElement("div");
  pagination.classList.add("swiper-pagination");

  // ✅ Swiper 전체 구조 완성
  swiperContainer.appendChild(swiperWrapper);
  swiperContainer.appendChild(pagination);

  // ✅ 기존 business-grid 뒤에 삽입
  grid.insertAdjacentElement("afterend", swiperContainer);

  // ✅ 기존 3열 그리드 숨기기
  grid.style.display = "none";

  // ✅ Swiper 초기화
  new Swiper(".business-slider", {
    slidesPerView: 1,
    spaceBetween: 24,
    loop: true,
    pagination: {
      el: ".swiper-pagination",
      clickable: true,
    },
    autoplay: {
      delay: 3500,
      disableOnInteraction: false,
    },
  });

  console.log("📱 Swiper initialized (1 slide per card)");
});
