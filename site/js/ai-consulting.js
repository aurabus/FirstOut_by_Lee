// =============================
// 🔹 Fade-Up Scroll Animation
// =============================
document.addEventListener("DOMContentLoaded", () => {
  const fadeElements = document.querySelectorAll(".fade-up");

  if ('IntersectionObserver' in window) {
    const fadeObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          fadeObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.2 });

    fadeElements.forEach(el => fadeObserver.observe(el));
  } else {
    fadeElements.forEach(el => el.classList.add("visible"));
  }

  // =============================
  // 🔹 Process Section Scroll Animation
  // =============================
  const processPairs = document.querySelectorAll(".process-pair");

  if ("IntersectionObserver" in window) {
    const processObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            processObserver.unobserve(entry.target); // 한 번만 실행
          }
        });
      },
      { 
        threshold: 0.8,            // 👈 요소의 50% 이상 보일 때 실행
        rootMargin: "-15% 0px -15% 0px" // 👈 상하 여백 조정으로 '화면 중앙' 인식 지점 조절
       }
    );

    processPairs.forEach((pair) => processObserver.observe(pair));
  } else {
    processPairs.forEach((pair) => pair.classList.add("visible"));
  }

  // =============================
  // 🔹 Industry Tabs (산업별 탭)
  // =============================
  const tabs = document.querySelectorAll('.tab');
  const contents = document.querySelectorAll('.tab-content');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const target = tab.getAttribute('data-target');
      contents.forEach(c => {
        c.classList.remove('active');
        if (c.id === target) c.classList.add('active');
      });
    });
  });
});
