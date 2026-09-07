/* 서비스 워커 — 일부러 아무것도 저장하지 않는다.
 *
 * 홈 화면에 앱으로 설치되려면 이 파일이 있어야 한다. 다만 귀가 명단은
 * 1분 사이에도 바뀌므로, 저장해 두었다가 보여주면 이미 집에 간 아이가
 * 명단에 남아 있는 사고가 난다. 그래서 그냥 서버로 흘려보내기만 한다.
 */
self.addEventListener("install", function () {
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function () {
  /* 그대로 둔다 — 브라우저가 알아서 서버에 묻는다 */
});
