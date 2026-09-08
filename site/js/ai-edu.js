<script>
document.addEventListener("DOMContentLoaded", () => {
  // 자동 스크롤을 적용할 컨테이너들
  const autoScrollContainers = document.querySelectorAll(".ai-stage-container, .course-grid");

  autoScrollContainers.forEach(container => {
    let scrollStep = 1.5;       // 이동 속도 (px 단위)
    let direction = 1;          // 1 = 오른쪽, -1 = 왼쪽

    function autoScroll() {
      if (!container) return;

      container.scrollLeft += scrollStep * direction;

      // 맨 오른쪽 도달 시 반대 방향으로 전환
      if (container.scrollLeft + container.clientWidth >= container.scrollWidth - 2) {
        direction = -1;
      }

      // 맨 왼쪽 도달 시 다시 오른쪽으로 전환
      if (container.scrollLeft <= 0) {
        direction = 1;
      }
    }

    // 매 16ms (약 60fps)마다 실행 → 매우 부드러운 이동
    setInterval(autoScroll, 16);
  });
});
</script>
