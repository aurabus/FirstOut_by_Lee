/* 손잡고 마중 — 화면 보조 스크립트
   외부 라이브러리를 쓰지 않는다. 원내망만으로도 완전히 동작해야 하기 때문이다. */

(function () {
  "use strict";

  /* 시계 */
  var DAY = ["일", "월", "화", "수", "목", "금", "토"];
  var clock = document.getElementById("clock");
  function tick() {
    if (!clock) return;
    var d = new Date();
    var p = function (n) { return String(n).padStart(2, "0"); };
    clock.innerHTML =
      d.getMonth() + 1 + "월 " + d.getDate() + "일 (" + DAY[d.getDay()] + ") <b>" +
      p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds()) + "</b>";
  }
  tick();
  setInterval(tick, 1000);

  /* 서버 연결 표시 — 끊기면 선생님이 즉시 알아야 한다 */
  var live = document.getElementById("live");
  function ping() {
    if (!live) return;
    fetch("/health", { cache: "no-store" })
      .then(function (r) {
        var ok = r.ok;
        live.classList.toggle("off", !ok);
        live.title = ok ? "서버 연결됨" : "서버 연결 끊김";
      })
      .catch(function () {
        live.classList.add("off");
        live.title = "서버 연결 끊김 — 종이 명단을 사용하세요";
      });
  }
  ping();
  setInterval(ping, 10000);

  /* 대기 시간 자동 갱신 (data-since 에 ISO 시각) */
  function elapsed() {
    var now = Date.now();
    document.querySelectorAll("[data-since]").forEach(function (el) {
      var t = Date.parse(el.dataset.since);
      if (isNaN(t)) return;
      var s = Math.max(0, Math.round((now - t) / 1000));
      var p = function (n) { return String(n).padStart(2, "0"); };
      el.textContent = p(Math.floor(s / 60)) + ":" + p(s % 60);
      var row = el.closest("[data-late-row]");
      if (row) row.classList.toggle("late", s >= 300);
    });
  }
  elapsed();
  setInterval(elapsed, 1000);
})();
