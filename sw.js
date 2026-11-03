// 항상 최신 파일을 먼저 받고, 인터넷이 끊겼을 때만 저장해 둔 파일을 쓴다.
// 사이트를 고칠 때마다 이 값을 바꾸면 방문자 기기의 예전 저장본이 지워진다.
const VERSION = "v19-uses";
const SHELL = ["./", "index.html", "style.css", "app.js", "manifest.webmanifest", "icon.svg", "data/meta.json", "data/genera.json", "data/care/index.json", "data/family_ko.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request, { cache: "no-cache" })
      .then(res => {
        if (res.ok) caches.open(VERSION).then(c => c.put(e.request, res.clone()));
        return res;
      })
      .catch(() => caches.match(e.request).then(hit => hit || Response.error()))
  );
});
