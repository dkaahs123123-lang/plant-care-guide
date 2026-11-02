"use strict";

const app = document.getElementById("app");
const input = document.getElementById("q");
const GBIF = "https://api.gbif.org/v1";
const RESULT_LIMIT = 60;
const QUICK = ["몬스테라", "스킨답서스", "호야", "고추", "토마토", "상추", "딸기", "장미", "무궁화", "소나무"];

// 둘러보기 분류. 채소·과일 등은 NCPMS 작물 분류 코드, 실내식물·정원식물·우리나라 식물은 각 자료 목록을 따른다.
const CATS = {
  indoor: ["실내식물", "집 안에서 키우는 관엽식물과 꽃입니다. 키우는 방법은 국립원예특작과학원 자료입니다."],
  veg: ["채소", "텃밭과 베란다에서 키우는 채소입니다. 농촌진흥청 NCPMS의 채소 분류를 따랐습니다."],
  fruit: ["과일나무", "열매를 먹는 나무와 덩굴입니다. 농촌진흥청 NCPMS의 과수 분류를 따랐습니다."],
  flower: ["꽃·관상식물", "꽃과 잎을 보려고 키우는 식물입니다. 농촌진흥청 NCPMS의 화훼 분류를 따랐습니다."],
  herbal: ["약초·특용작물", "약재, 기름, 섬유 등으로 쓰는 작물입니다. 농촌진흥청 NCPMS의 특용작물 분류를 따랐습니다."],
  grain: ["곡식·콩·감자", "벼, 보리, 콩, 감자, 고구마 같은 식량 작물입니다. 농촌진흥청 NCPMS의 식량작물 분류를 따랐습니다."],
  garden: ["우리 꽃 정원식물", "정원에 심기 좋은 우리 자생식물입니다. 한국수목원정원관리원 자료입니다."],
  native: ["우리나라 식물", "산림청 표준식물종 목록에 있는 식물입니다. 꽃 피는 달, 크기, 보호식물 여부를 볼 수 있습니다."],
  tree: ["나무", "농촌진흥청 NCPMS의 나무 분류입니다."],
};
const TILE_ORDER = ["indoor", "veg", "fruit", "flower", "herbal", "grain", "garden", "native"];

// 틀린 내용 신고: 어떤 식물의 어느 칸인지 채운 GitHub 이슈 작성 화면을 연다 (GitHub 계정 필요)
const ISSUES = "https://github.com/dkaahs123123-lang/plant-care-guide/issues/new";
const reportBtn = card => `<button type="button" class="report" data-card="${esc(card)}">틀린 내용 신고</button>`;
document.addEventListener("click", e => {
  const b = e.target.closest("button.report");
  if (!b) return;
  const plant = [document.querySelector(".sheet-head h1")?.textContent, document.querySelector(".sci-line i")?.textContent].filter(Boolean).join(" / ");
  const title = `[틀린 내용] ${plant || "도감"} - ${b.dataset.card}`;
  const body = [
    `식물: ${plant}`, `칸: ${b.dataset.card}`, `페이지: ${location.href}`, "",
    "무엇이 틀렸나요?", "", "", "올바른 내용과 근거(출처 링크나 자료 이름):", "", "",
  ].join("\n");
  window.open(`${ISSUES}?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`, "_blank", "noopener");
});

// 정보 칸마다 어느 나라, 어떤 환경을 기준으로 한 자료인지 보여 준다.
const KMA_CLIMATE = "https://www.weather.go.kr/w/climate/statistics/region.do";
const REGION = {
  air: ["한국", "실내", "국립원예특작과학원이 우리나라 집 안 환경을 기준으로 정리한 자료입니다."],
  grow: ["한국", "야외 정원", "한국수목원정원관리원이 우리나라 정원에 심는 것을 기준으로 정리한 자료입니다."],
  pests: ["한국", "농가·텃밭", "우리나라 농작물에서 생기는 병해충을 정리한 자료입니다."],
  kfs: ["한국", "자생지", "꽃 피는 달 등은 우리나라 산과 들에서 자랄 때를 기준으로 합니다."],
  cases: ["한국", "농가 현장", "실제 농가에서 생긴 문제를 그 현장의 날씨·흙·재배 방법과 함께 진단한 기록이라, 같은 증상이라도 원인이 다를 수 있습니다."],
  smart: ["한국", "스마트팜(온실)", "농촌진흥청이 우리나라 스마트팜 우수 농가의 환경 설정을 바탕으로 정리한 값입니다."],
  web: ["미국 노스캐롤라이나", "야외",
    `노스캐롤라이나는 대부분 여름이 덥고 습하며 겨울이 온화한 기후(쾨펜 Cfa)이고, 미국 농무부 추위 구역으로 산지 5b부터 해안 9a까지입니다 (<a href="https://planthardiness.ars.usda.gov" target="_blank" rel="noopener">USDA 내한성 지도</a>). ` +
    `우리나라는 지역마다 겨울 추위가 크게 다르니 <a href="${KMA_CLIMATE}" target="_blank" rel="noopener">기상청 지역별 기후통계</a>에서 사는 곳의 겨울 최저기온과 비교해 보세요.`],
};
function regionLine(kind) {
  const [country, env, desc] = REGION[kind];
  return `<div class="region"><span class="badge region-badge${country === "한국" ? "" : " abroad"}">${country} · ${env} 기준</span><span class="small muted">${desc}</span></div>`;
}

// ---------- 데이터 읽기 ----------
const cache = new Map();
function getJSON(url) {
  if (!cache.has(url)) {
    cache.set(url, fetch(url, { cache: "no-cache" }).then(r => {
      if (!r.ok) throw new Error(`${r.status} ${url}`);
      return r.json();
    }).catch(err => { cache.delete(url); throw err; }));
  }
  return cache.get(url);
}
const optional = p => p.catch(() => null);

let generaMap = null;
async function genera() {
  const list = await getJSON("data/genera.json");
  if (!generaMap) generaMap = new Map(list.map(g => [g[0], g]));
  return list;
}
// 한국어 이름과 공식 자료가 있는 식물 목록: {id 또는 "g:속": {g, r, name, crops, ko, cats, nd, ni, grow}}
let CI = {};
// 과 이름의 한국어 표기: {Araceae: "천남성과"}
let FK = {};
const ready = Promise.all([
  genera(),
  optional(getJSON("data/care/index.json")).then(x => { CI = x || {}; }),
  optional(getJSON("data/family_ko.json")).then(x => { FK = x || {}; }),
]);

const keyFor = s => (s.toLowerCase().replace(/[^a-z]/g, "").slice(0, 2) || "__").padEnd(2, "_");
const spBucket = genus => optional(getJSON(`data/sp/${keyFor(genus)}.json`)).then(b => b || {});
const synBucket = name => optional(getJSON(`data/syn/${keyFor(name)}.json`)).then(b => b || []);

// ---------- 글자 다루기 ----------
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const norm = s => s.toLowerCase().replace(/[××]/g, "").replace(/\s+/g, " ").trim();
const bare = s => norm(s).replace(/ (subsp|ssp|var|f|forma|nothosubsp|nothovar)\. /g, " ").replace(/\s+/g, " ");
const isHangul = s => /[ㄱ-ㆎ가-힣]/.test(s);
const fmt = n => n.toLocaleString("ko-KR");
const taxonHref = (genus, id) => `#/t/${encodeURIComponent(genus)}/${id}`;
const fullName = (genus, rest) => rest ? `${genus} ${rest}` : genus;
const careHref = (key, v) => key.startsWith("g:") ? `#/g/${encodeURIComponent(v.g)}` : taxonHref(v.g, key);
const famLabel = f => FK[f] ? `${FK[f]} <span class="muted">${esc(f)}</span>` : esc(f);
const byKo = (a, b) => a.localeCompare(b, "ko");

// 초성 검색: "ㅁㅅㅌㄹ" -> 몬스테라
const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
const chosung = s => [...s].map(ch => {
  const c = ch.charCodeAt(0) - 0xAC00;
  return c >= 0 && c < 11172 ? CHO[Math.floor(c / 588)] : ch;
}).join("");
const isChoOnly = s => /^[ㄱ-ㅎ]+$/.test(s);

function badges(v) {
  return [
    v.grow && `<span class="badge">키우는 방법</span>`,
    !v.grow && v.web && `<span class="badge web">인터넷 재배 정보</span>`,
    (v.nd || v.ni) && `<span class="badge amber">병해충 ${fmt(v.nd + v.ni)}</span>`,
    v.nc && `<span class="badge web">현장 사례 ${fmt(v.nc)}</span>`,
  ].filter(Boolean).join(" ");
}

function plantRow(key, v, note = "") {
  const sci = fullName(v.g, v.r);
  return `<a class="row" href="${careHref(key, v)}">
    <span class="title">${v.name ? `<b class="ko">${esc(v.name)}</b> <i class="sci-s">${esc(sci)}</i>` : `<i>${esc(sci)}</i>`}${key.startsWith("g:") ? ` <span class="badge">속 전체</span>` : ""}</span>
    <span class="side">${badges(v)}</span>
    ${note ? `<span class="note">${note}</span>` : ""}
  </a>`;
}

// ---------- 라우팅 ----------
async function route() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  const [view, a, b] = parts;
  window.scrollTo(0, 0);
  // 처음 여는 식물은 자료를 받는 데 몇 초 걸릴 수 있어, 이전 화면 대신 불러오는 중임을 보여 준다.
  if (view === "t" || view === "g" || view === "f") app.innerHTML = `<p class="loading">식물 정보를 불러오는 중…</p>`;
  try {
    await ready;
    if (view === "s" && a) { input.value = a; await renderSearch(a); }
    else if (view === "t" && a && b) { OPEN_PEST = parts[3] || ""; await renderTaxon(a, b); }
    else if (view === "g" && a) await renderGenus(a);
    else if (view === "f" && a) await renderFamily(a);
    else if (view === "c" && CATS[a]) renderCategory(a);
    else if (view === "symptom") await renderSymptom(a || "");
    else if (view === "fixes") await renderFixes();
    else if (view === "families") await renderFamilies();
    else { input.value = ""; await renderHome(); }
  } catch (err) {
    console.error(err);
    app.innerHTML = `<div class="empty">데이터를 불러오지 못했습니다. 인터넷 연결을 확인하고 새로고침해 주세요.<br><span class="small">${esc(err.message)}</span></div>`;
  }
}
window.addEventListener("hashchange", route);

let timer;
input.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    const q = input.value.trim();
    if (!q || (q.length < 2 && !isHangul(q))) return;
    const target = `#/s/${encodeURIComponent(q)}`;
    if (location.hash.startsWith("#/s/")) { history.replaceState(null, "", target); route(); }
    else location.hash = target;
  }, 300);
});
document.getElementById("search-form").addEventListener("submit", e => {
  e.preventDefault();
  const q = input.value.trim();
  if (q) location.hash = `#/s/${encodeURIComponent(q)}`;
});

// ---------- 홈 ----------
async function renderHome() {
  const meta = await getJSON("data/meta.json");
  const c = meta.counts;
  const all = Object.values(CI);
  const count = cat => all.filter(v => v.cats.includes(cat)).length;
  app.innerHTML = `
    <section class="hero">
      <h1>어떤 식물을 키우세요?</h1>
      <p>식물 이름을 검색하거나 아래에서 골라 보세요. 키우는 방법과 병해충 정보는 모두 공공기관 자료이고, 어디서 온 정보인지 함께 보여 드립니다.</p>
      <div class="quick">${QUICK.map(q => `<a href="#/s/${encodeURIComponent(q)}">${esc(q)}</a>`).join("")}</div>
    </section>
    <div class="tiles">
      ${TILE_ORDER.map(cat => `
        <a class="tile" href="#/c/${cat}">
          <b>${CATS[cat][0]}</b>
          <span class="n">${fmt(count(cat))}종</span>
        </a>`).join("")}
    </div>
    <a class="card feature" href="#/symptom">
      <h2>식물이 아파요</h2>
      <p>잎이 노래지거나 흰 가루가 생겼나요? 증상을 고르면 어떤 병이나 해충인지 찾아 드립니다.</p>
      <span class="btn-link">증상으로 병해충 찾기 →</span>
    </a>
    <section class="card">
      <h2>이렇게 찾을 수 있어요</h2>
      <ul class="tips">
        <li><b>한글 이름</b>으로 찾기: 몬스테라, 고추, 소나무</li>
        <li><b>첫소리(초성)</b>만으로 찾기: ㅁㅅㅌㄹ → 몬스테라</li>
        <li><b>학명</b>으로 찾기: Monstera, Capsicum annuum</li>
        <li>판매처에서 쓰는 <b>예전 학명</b>도 찾을 수 있어요: Sansevieria → 지금 이름으로 안내</li>
      </ul>
      <p class="small muted">모든 정보에는 <span class="badge region-badge">한국 · 실내 기준</span> <span class="badge region-badge abroad">미국 노스캐롤라이나 · 야외 기준</span>처럼 어느 나라, 어떤 환경을 기준으로 한 자료인지 표시합니다.</p>
    </section>
    <section class="card">
      <h2>이 도감에 들어 있는 것</h2>
      <div class="stats">
        <div class="stat"><div class="n">${fmt(c.species)}</div><div class="k">전 세계 식물 종</div></div>
        <div class="stat"><div class="n">${fmt(all.filter(v => v.name).length)}</div><div class="k">한국어 이름이 있는 식물</div></div>
        <div class="stat"><div class="n">${fmt(all.filter(v => v.grow).length)}</div><div class="k">공공기관 재배 정보가 있는 식물</div></div>
        <div class="stat"><div class="n">${fmt(all.filter(v => v.web).length)}</div><div class="k">인터넷 재배 정보가 있는 식물</div></div>
        <div class="stat"><div class="n">${fmt(all.filter(v => v.nd || v.ni).length)}</div><div class="k">병해충 정보가 있는 식물</div></div>
      </div>
      <p class="small muted">학명과 분류: World Flora Online · 한국어 이름: 산림청, 한국수목원정원관리원, 농촌진흥청 · 키우는 방법: 국립원예특작과학원, 한국수목원정원관리원 · 병해충: 농촌진흥청 NCPMS · <a href="#/families">모든 과 보기</a></p>
    </section>`;
}

// ---------- 증상으로 병해충 찾기 ----------
// 증상 버튼마다 NCPMS 증상 설명에 실제로 쓰이는 표현을 묶었다. 입력한 말도 이 묶음에 맞으면 같은 뜻으로 찾는다.
const SYMPTOM_GROUPS = [
  ["노랗게 변해요", ["황화", "노랗", "누렇", "황색", "노란", "노래"]],
  ["갈색 점이 생겨요", ["갈색", "암갈색", "적갈색", "흑갈색"]],
  ["검게 변하거나 그을음이 생겨요", ["검은", "검게", "흑색", "그을음"]],
  ["흰 가루나 곰팡이가 보여요", ["흰가루", "흰색", "백색", "균사", "곰팡이"]],
  ["시들거나 말라 죽어요", ["시들", "시듦", "위조", "말라", "고사"]],
  ["썩거나 물러져요", ["썩", "무름", "물러", "부패", "수침상"]],
  ["구멍이 나거나 갉아먹혀요", ["구멍", "갉아", "먹어", "식해", "식흔"]],
  ["오그라들거나 뒤틀려요", ["오그라", "말리", "위축", "기형", "뒤틀", "쭈글"]],
  ["얼룩덜룩해요", ["모자이크", "얼룩", "퇴색", "괴저"]],
  ["끈적거려요", ["감로", "끈적"]],
  ["혹이 생겨요", ["혹이", "혹을", "혹 모양", "암종"]],
  ["벌레가 보여요", ["유충", "성충", "애벌레", "약충"]],
  // 아래는 병해충이 아닌 생리장해(환경·양분 문제)를 현장 진단 사례에서 찾기 위한 묶음
  ["속이 차지 않아요", ["결구", "속이 차", "속이 비", "속잎"]],
  ["잎끝이나 가장자리가 타요", ["잎끝", "팁번", "가장자리", "엽소", "갈변"]],
  ["열매가 갈라지거나 모양이 이상해요", ["열과", "갈라", "기형과", "기형"]],
  ["꽃·열매가 떨어지거나 안 맺혀요", ["낙화", "낙과", "착과", "결실", "수정"]],
  ["잘 안 자라요", ["생육부진", "생육 부진", "생육이 불량", "생육불량", "왜화", "자라지"]],
  ["비료·양분 문제 같아요", ["결핍", "과잉", "양분", "비료", "시비", "염류"]],
  ["약을 친 뒤에 생겼어요", ["약해", "농약", "제초제", "살포"]],
  ["추위·더위 피해 같아요", ["저온", "고온", "동해", "냉해", "서리", "일소"]],
];
const SYMPTOM_PARTS = [["잎", ["잎"]], ["줄기", ["줄기", "가지"]], ["열매", ["과실", "열매", "과일"]], ["뿌리", ["뿌리", "지제부"]], ["꽃", ["꽃"]]];
let OPEN_PEST = "";

// "잎이 노랗게 변해요" -> ["잎", "노랗", "변"] : 조사와 흔한 어미를 떼어 낸다
const stem = w => w.replace(/(에서|으로|해요|했어요|어요|아요|져요|졌어요|이에요|예요|이|가|은|는|을|를|에|의|도|로|요|게|고|져|짐|해|함|음)$/, "");
function symptomTerms(text, groups, parts) {
  const terms = [];
  for (const g of groups) terms.push({ label: SYMPTOM_GROUPS[g][0], words: SYMPTOM_GROUPS[g][1] });
  for (const p of parts) terms.push({ label: SYMPTOM_PARTS[p][0], words: SYMPTOM_PARTS[p][1], part: true });
  for (const raw of text.split(/\s+/).filter(Boolean)) {
    const w = stem(raw);
    if (w.length < 1) continue;
    const g = SYMPTOM_GROUPS.find(([, ws]) => ws.some(s => s.includes(w) || w.includes(s)));
    const p = SYMPTOM_PARTS.find(([, ws]) => ws.includes(w));
    if (g) terms.push({ label: g[0], words: g[1] });
    else if (p) terms.push({ label: p[0], words: p[1], part: true });
    else if (w.length >= 2) terms.push({ label: `‘${w}’`, words: [w] });
  }
  return terms.filter((t, i) => terms.findIndex(x => x.label === t.label) === i);
}

function snippet(text, words) {
  const idx = Math.min(...words.map(w => { const i = text.indexOf(w); return i < 0 ? Infinity : i; }));
  const start = Number.isFinite(idx) ? Math.max(0, idx - 40) : 0;
  let s = esc((start ? "…" : "") + text.slice(start, start + 140) + (text.length > start + 140 ? "…" : ""));
  for (const w of words) s = s.split(esc(w)).join(`<mark>${esc(w)}</mark>`);
  return s;
}

async function renderSymptom(crop) {
  const list = await getJSON("data/symptoms.json");
  // 작물은 식물 단위로 묶는다 (가을배추·봄배추 사례도 '배추'로)
  const plantName = k => CI[k]?.name || CI[k]?.crops?.[0] || list.find(r => r[0] === k)[1];
  const plants = [...new Set(list.map(r => r[0]))].map(k => [k, plantName(k)]).sort((a, b) => byKo(a[1], b[1]));
  const chosen = crop && (plants.find(([k, n]) => n === crop || CI[k]?.crops?.includes(crop)) || [])[0];
  app.innerHTML = `
    <nav class="crumbs"><a href="#/">처음으로</a></nav>
    <section class="sheet-head"><h1 class="ko-title">증상으로 병해충 찾기</h1>
      <div class="author">보이는 증상을 고르거나 적으면 맞는 병해충과, 비슷한 문제를 농촌진흥청이 현장에서 진단한 사례를 찾아 드립니다. 병이 아니라 양분·날씨·약 때문에 생긴 문제(생리장해)도 사례에서 찾을 수 있어요.</div></section>
    <section class="card symptom-form">
      <label class="field">어떤 작물인가요?
        <select id="sym-crop"><option value="">모든 작물</option>${plants.map(([k, n]) => `<option value="${esc(k)}"${k === chosen ? " selected" : ""}>${esc(n)}</option>`).join("")}</select></label>
      <div class="field">어디에 생겼나요?<div class="chips" id="sym-parts">${SYMPTOM_PARTS.map(([l], i) => `<button type="button" class="chip" data-part="${i}" aria-pressed="false">${l}</button>`).join("")}</div></div>
      <div class="field">어떤 모습인가요?<div class="chips" id="sym-groups">${SYMPTOM_GROUPS.map(([l], i) => `<button type="button" class="chip" data-group="${i}" aria-pressed="false">${l}</button>`).join("")}</div></div>
      <label class="field">직접 적어도 돼요<input id="sym-text" class="filter" type="search" placeholder="예: 잎 뒷면에 흰 가루"></label>
    </section>
    <div id="sym-results"><p class="muted small">증상을 고르면 결과가 여기에 나옵니다.</p></div>
    <p class="note small muted">증상만으로는 정확히 알 수 없습니다. 비슷한 증상의 병이 여럿일 수 있으니 결과의 설명과 사진을 비교해 보고, 확실하지 않으면 가까운 농업기술센터에 문의하세요.</p>`;

  const groups = new Set(), parts = new Set();
  const run = () => {
    const c = document.getElementById("sym-crop").value;
    const terms = symptomTerms(document.getElementById("sym-text").value.trim(), [...groups], [...parts]);
    const box = document.getElementById("sym-results");
    if (!terms.length) { box.innerHTML = `<p class="muted small">증상을 고르면 결과가 여기에 나옵니다.</p>`; return; }
    // 일부만 맞는 결과는 '잎'처럼 부위만 맞은 것은 빼고, 모습(증상)이 하나라도 맞은 것만 보여 준다
    const looks = terms.filter(t => !t.part);
    const scored = list.filter(r => !c || r[0] === c).map(r => {
      const hit = terms.filter(t => t.words.some(w => r[4].includes(w)));
      return { r, hit, all: hit.length === terms.length };
    }).filter(x => x.hit.length && (x.all || !looks.length || x.hit.some(t => !t.part)));
    // 순서: 맞은 조건 수 > 병해충 이름에 증상 표현이 들어 있음 > 설명에 증상 표현이 많이 나옴
    const words = terms.flatMap(t => t.words);
    const rank = x => x.hit.length * 100 + (words.some(w => x.r[3].includes(w)) ? 50 : 0)
      + words.reduce((n, w) => n + x.r[4].split(w).length - 1, 0);
    scored.sort((a, b) => rank(b) - rank(a));
    const full = scored.filter(x => x.all);
    const shown = (full.length ? full : scored).slice(0, 50);
    box.innerHTML = `
      <div class="section-title"><h2>${full.length ? `모든 조건에 맞는 ${fmt(full.length)}건` : `일부 조건만 맞는 결과`}</h2>
        <span class="muted small">찾은 조건: ${terms.map(t => esc(t.label)).join(", ")}${full.length > 50 ? " · 처음 50건" : ""}</span></div>
      ${shown.length ? `<div class="list">${shown.map(({ r, hit }) => {
        const v = CI[r[0]] || {};
        const open = r[5] ? `case-${r[5]}` : r[3];
        const href = r[0].startsWith("g:") ? `#/g/${encodeURIComponent(v.g)}` : `${taxonHref(v.g, r[0])}/${encodeURIComponent(open)}`;
        const badge = r[2] === "병" ? "amber" : r[2] === "현장 사례" ? "web" : "";
        return `<a class="row" href="${href}">
          <span class="title"><span class="badge ${badge}">${r[2]}</span> <b class="ko">${esc(r[3])}</b> <span class="sci-s">${esc(r[1])}</span></span>
          <span class="side small">${full.length ? "" : `${hit.length}/${terms.length} 조건`}</span>
          <span class="note">${snippet(r[4], words)}</span></a>`;
      }).join("")}</div>` : `<div class="empty">맞는 병해충을 찾지 못했습니다. 조건을 줄이거나 다른 말로 적어 보세요.</div>`}
      <p class="src">출처: 병·해충 증상은 농촌진흥청 국가농작물병해충관리시스템(NCPMS), 현장 사례는 농촌진흥청 농사로 현장기술지원 사례 · 모두 원문 그대로</p>`;
  };
  document.getElementById("sym-crop").addEventListener("change", run);
  let t;
  document.getElementById("sym-text").addEventListener("input", () => { clearTimeout(t); t = setTimeout(run, 250); });
  app.querySelector(".symptom-form").addEventListener("click", e => {
    const b = e.target.closest(".chip");
    if (!b) return;
    const set = b.dataset.group != null ? groups : parts;
    const i = +(b.dataset.group ?? b.dataset.part);
    set.has(i) ? set.delete(i) : set.add(i);
    b.setAttribute("aria-pressed", set.has(i));
    run();
  });
}

// ---------- 고친 내역 ----------
async function renderFixes() {
  const list = (await optional(getJSON("data/corrections.json"))) || [];
  app.innerHTML = `
    <nav class="crumbs"><a href="#/">처음으로</a></nav>
    <section class="sheet-head"><h1 class="ko-title">고친 내역</h1>
      <div class="author">신고나 점검으로 틀린 것이 확인되어 감추거나 고친 정보입니다. 출처 자료 자체가 틀린 경우에는 그 기관에도 알리고 있습니다.</div></section>
    ${list.length ? `<div class="list">${list.map(f => {
      const v = CI[f.key];
      const href = v ? careHref(f.key, v) : "#/";
      return `<a class="row" href="${href}"><span class="title"><b class="ko">${esc(v?.name || f.target)}</b> <span class="sci-s">${esc(f.part)}${f.item !== "*" ? ` · ${esc(f.item)}` : ""}</span></span>
        <span class="side small">${esc(f.action)}</span><span class="note">${esc(f.reason)}</span></a>`;
    }).join("")}</div>` : `<div class="empty">아직 고친 내역이 없습니다.</div>`}
    <section class="card"><h2>틀린 내용을 발견하셨나요?</h2>
      <p>식물 화면의 각 정보 칸 아래에 있는 <b>틀린 내용 신고</b> 버튼을 눌러 주세요. 확인되면 바로 감추거나 고치고, 이 페이지에 이유와 함께 남깁니다. 신고하려면 GitHub 계정이 필요합니다.</p></section>`;
}

// ---------- 분류별 둘러보기 ----------
function renderCategory(cat) {
  const [label, desc] = CATS[cat];
  const items = Object.entries(CI).filter(([, v]) => v.cats.includes(cat))
    .sort((a, b) => byKo(a[1].name || a[1].g, b[1].name || b[1].g));
  app.innerHTML = `
    <nav class="crumbs"><a href="#/">처음으로</a></nav>
    <section class="sheet-head"><h1 class="ko-title">${label}</h1><div class="author">${desc}</div></section>
    <input class="filter" id="cat-filter" type="search" placeholder="이 목록에서 찾기 (초성도 됩니다)" aria-label="${label} 목록에서 찾기">
    <div class="list" id="cat-list"></div>`;
  const list = document.getElementById("cat-list");
  const draw = q => {
    const qq = q.replace(/\s+/g, "");
    const cho = isChoOnly(qq);
    const shown = !qq ? items : items.filter(([, v]) => [v.name, ...v.ko, ...v.crops, fullName(v.g, v.r)].some(n => {
      const nn = (n || "").replace(/\s+/g, "").toLowerCase();
      return (cho ? chosung(nn) : nn).includes(qq.toLowerCase());
    }));
    list.innerHTML = shown.length ? shown.map(([k, v]) => plantRow(k, v)).join("") : `<div class="empty">찾는 식물이 이 목록에 없습니다.</div>`;
  };
  draw("");
  document.getElementById("cat-filter").addEventListener("input", e => draw(e.target.value.trim()));
}

// ---------- 검색 ----------
async function renderSearch(q) {
  app.innerHTML = `<p class="loading">“${esc(q)}” 찾는 중…</p>`;
  if (!isHangul(q)) {
    const html = await searchLatin(q);
    if (input.value.trim() === q) app.innerHTML = html;
    return;
  }
  const local = searchKoreanLocal(q);
  if (input.value.trim() !== q) return;
  app.innerHTML = (local || "") + `<div id="more"><p class="loading">다른 이름으로 더 찾는 중…</p></div>`;
  if (isChoOnly(q.replace(/\s+/g, ""))) { document.getElementById("more").innerHTML = local ? "" : `<div class="empty">“${esc(q)}”와 첫소리가 맞는 식물이 없습니다.</div>`; return; }
  const more = await searchKoreanGbif(q, new Set(Object.keys(CI).filter(k => app.innerHTML.includes(k))));
  const box = document.getElementById("more");
  if (box && input.value.trim() === q) {
    box.innerHTML = more || (local ? "" : `<div class="empty">“${esc(q)}”에 해당하는 식물을 찾지 못했습니다. 다른 이름이나 학명으로 검색해 보세요.</div>`);
  }
}

// 이 도감의 한국어 이름(산림청, 정원식물, 실내식물, NCPMS 작물명)에서 찾는다.
function searchKoreanLocal(q) {
  const qq = q.replace(/\s+/g, "");
  const cho = isChoOnly(qq);
  const hits = [];
  for (const [key, v] of Object.entries(CI)) {
    let best = -1, matched = "";
    for (const n of new Set([v.name, ...v.ko, ...v.crops].filter(Boolean))) {
      const t = cho ? chosung(n.replace(/\s+/g, "")) : n.replace(/\s+/g, "");
      const score = t === qq ? 3 : t.startsWith(qq) ? 2 : t.includes(qq) ? 1 : -1;
      if (score > best) { best = score; matched = n; }
    }
    if (best >= 0) hits.push({ key, v, best, matched });
  }
  if (!hits.length) return "";
  const useful = v => (v.grow ? 2 : 0) + (v.nd || v.ni ? 1 : 0);
  hits.sort((a, b) => b.best - a.best || useful(b.v) - useful(a.v) || byKo(a.v.name || "", b.v.name || ""));
  const shown = hits.slice(0, RESULT_LIMIT);
  return `<div class="section-title"><h2>“${esc(q)}” 검색 결과</h2><span class="muted small">${hits.length > RESULT_LIMIT ? `${fmt(hits.length)}개 중 ${RESULT_LIMIT}개` : `${hits.length}개`}</span></div>
    <div class="list">${shown.map(({ key, v, matched }) => plantRow(key, v, matched !== v.name ? `검색어와 맞는 이름: ‘${esc(matched)}’` : "")).join("")}</div>`;
}

// GBIF에 등록된 한국어 일반명으로 더 찾는다. 이미 보여 준 식물은 뺀다.
async function searchKoreanGbif(q, shownIds) {
  let data;
  try {
    data = await (await fetch(`${GBIF}/species/search?q=${encodeURIComponent(q)}&qField=VERNACULAR&limit=40`)).json();
  } catch {
    return "";
  }
  const ranks = new Set(["SPECIES", "SUBSPECIES", "VARIETY", "FORM"]);
  const byName = new Map();
  for (const r of data.results || []) {
    if (!r.canonicalName || !ranks.has(r.rank) || r.kingdom !== "Plantae") continue;
    const ko = (r.vernacularNames || []).filter(v => /kor|ko/.test(v.language || "") || isHangul(v.vernacularName)).map(v => v.vernacularName);
    const entry = byName.get(r.canonicalName) || new Set();
    ko.forEach(k => entry.add(k));
    byName.set(r.canonicalName, entry);
  }
  const resolved = [];
  for (const [name, ko] of byName) {
    const hit = await resolveName(name);
    if (hit && !shownIds.has(hit.row[0]) && !resolved.some(x => x.row[0] === hit.row[0])) resolved.push({ ...hit, ko: [...ko] });
  }
  if (!resolved.length) return "";
  resolved.sort((a, b) => b.ko.includes(q) - a.ko.includes(q));
  return `<div class="section-title"><h2>다른 이름으로 더 찾은 식물</h2><span class="muted small">한국어 이름 출처: GBIF</span></div>
    <div class="list">${resolved.map(({ genus, row, ko }) => speciesRow(genus, row, ko.length ? esc(ko.slice(0, 4).join(", ")) : "")).join("")}</div>`;
}

async function searchLatin(raw) {
  const q = norm(raw);
  if (q.length < 2) return `<div class="empty">두 글자 이상 입력해 주세요.</div>`;
  const first = q.split(" ")[0];
  const [gl, sp, syn] = await Promise.all([genera(), spBucket(q), synBucket(q)]);

  const genusHits = q.includes(" ") ? [] : gl.filter(g => norm(g[0]).startsWith(q)).slice(0, 12);
  const spHits = [];
  for (const genus of Object.keys(sp)) {
    const ng = norm(genus);
    if (!ng.startsWith(first) && !q.startsWith(ng)) continue;
    for (const row of sp[genus]) {
      if (bare(fullName(genus, row[1])).startsWith(bare(q))) spHits.push([genus, row]);
      if (spHits.length >= RESULT_LIMIT) break;
    }
    if (spHits.length >= RESULT_LIMIT) break;
  }
  // 한국어 이름이 있는 식물을 앞으로
  spHits.sort((a, b) => !!CI[b[1][0]]?.name - !!CI[a[1][0]]?.name);
  const synHits = q.length >= 4 ? syn.filter(s => bare(s[0]).startsWith(bare(q))).slice(0, 30) : [];

  if (!genusHits.length && !spHits.length && !synHits.length) {
    return `<div class="empty">“${esc(raw)}”로 시작하는 학명이 없습니다. 철자를 확인하거나 한글 이름으로 검색해 보세요.</div>`;
  }
  let html = "";
  if (synHits.length) {
    html += `<div class="section-title"><h2>예전 학명으로 찾은 결과</h2></div>
      <p class="small muted">판매처나 오래된 책에서 쓰는 이름입니다. 지금은 아래의 새 이름으로 부릅니다.</p>
      <div class="list">${synHits.map(s => {
        const v = CI[s[2]];
        return `<a class="row" href="${taxonHref(s[3].split(" ")[0], s[2])}">
          <span class="title"><i>${esc(s[0])}</i> <span class="author">${esc(s[1])}</span></span>
          <span class="side"><span class="badge amber">예전 이름</span></span>
          <span class="note">지금 이름: ${v?.name ? `<b>${esc(v.name)}</b> ` : ""}<i>${esc(s[3])}</i></span>
        </a>`;
      }).join("")}</div>`;
  }
  if (spHits.length) {
    html += `<div class="section-title"><h2>종</h2><span class="muted small">${spHits.length >= RESULT_LIMIT ? `처음 ${RESULT_LIMIT}개` : `${spHits.length}개`}</span></div>
      <div class="list">${spHits.map(([g, r]) => speciesRow(g, r)).join("")}</div>`;
  }
  if (genusHits.length) {
    html += `<div class="section-title"><h2>속 (비슷한 식물 묶음)</h2></div><div class="list">${genusHits.map(g => `
      <a class="row" href="#/g/${encodeURIComponent(g[0])}"><span class="title"><i>${esc(g[0])}</i></span>
      <span class="side">${famLabel(g[1])} · ${fmt(g[2])}종</span></a>`).join("")}</div>`;
  }
  return html;
}

function speciesRow(genus, row, note = "") {
  const v = CI[row[0]];
  if (v) return plantRow(row[0], v, note);
  const fam = generaMap?.get(genus)?.[1] || "";
  return `<a class="row" href="${taxonHref(genus, row[0])}">
    <span class="title"><i>${esc(fullName(genus, row[1]))}</i> <span class="author">${esc(row[2])}</span></span>
    <span class="side">${famLabel(fam)}</span>
    ${note ? `<span class="note">${note}</span>` : ""}</a>`;
}

async function resolveName(name) {
  const genus = name.split(" ")[0];
  const sp = await spBucket(genus);
  const row = (sp[genus] || []).find(r => bare(fullName(genus, r[1])) === bare(name));
  if (row) return { genus, row };
  const syn = (await synBucket(name)).find(s => bare(s[0]) === bare(name));
  if (!syn) return null;
  return findById(syn[3].split(" ")[0], syn[2]);
}

async function findById(genus, id) {
  const sp = await spBucket(genus);
  const row = (sp[genus] || []).find(r => r[0] === id);
  return row ? { genus, row } : null;
}

// ---------- 식물 상세 ----------
async function renderTaxon(genus, id) {
  const hit = await findById(genus, id);
  if (!hit) { app.innerHTML = `<div class="empty">이 식물을 찾을 수 없습니다.</div>`; return; }
  const { row } = hit;
  const meta = await getJSON("data/meta.json");
  const src = meta.sources[0];
  const name = fullName(genus, row[1]);
  const fam = generaMap.get(genus)?.[1] || "";
  const wfoUrl = `https://list.worldfloraonline.org/wfo-${row[0]}`;
  const v = CI[id];
  const cats = (v?.cats || []).filter(c => CATS[c]);

  app.innerHTML = `
    <nav class="crumbs"><a href="#/f/${encodeURIComponent(fam)}">${famLabel(fam)}</a><span>›</span><a href="#/g/${encodeURIComponent(genus)}"><i>${esc(genus)}</i></a></nav>
    <section class="sheet-head">
      ${v?.name ? `<h1 class="ko-title">${esc(v.name)}</h1><div class="sci-line"><i>${esc(name)}</i> <span class="author">${esc(row[2])}</span></div>`
        : `<h1>${esc(name)}</h1><div class="author">${esc(row[2])}</div>`}
      ${cats.length ? `<div class="tags">${cats.map(c => `<a class="badge" href="#/c/${c}">${CATS[c][0]}</a>`).join("")}</div>` : ""}
      <div class="vern" id="vern"><span class="loading">다른 이름 불러오는 중…</span></div>
    </section>
    <div id="care"><p class="loading">키우는 방법과 병해충 정보를 불러오는 중…</p></div>
    <section class="card" id="photos-card"><h2>사진</h2><div id="photos" class="loading">사진 찾는 중…</div></section>
    ${row[4].length ? `<section class="card"><h2>예전 학명</h2><p class="small muted">예전에 쓰였거나 다른 연구자가 붙인 이름입니다. 판매처나 오래된 책에서 이 이름으로 나올 수 있습니다.</p><ul class="syns">${[...new Set(row[4])].map(s => `<li><i>${esc(s)}</i></li>`).join("")}</ul></section>` : ""}
    <section class="card">
      <h2>학명과 분류</h2>
      <div class="facts">
        <div class="fact"><span class="k">과</span><span class="v">${famLabel(fam)}</span></div>
        <div class="fact"><span class="k">속</span><span class="v"><i>${esc(genus)}</i></span></div>
        <div class="fact"><span class="k">학명이 발표된 해</span><span class="v mono">${esc(row[3] || "기록 없음")}</span></div>
      </div>
    </section>
    <section class="card">
      <h2>출처</h2>
      <ul class="small">
        <li>학명과 분류: ${esc(src.citation)}. 라이선스 ${esc(src.license)}. <a href="${wfoUrl}" target="_blank" rel="noopener">WFO에서 보기 (wfo-${esc(row[0])})</a></li>
        <li id="gbif-src">다른 이름과 사진: GBIF (자료마다 라이선스 표시)</li>
        <li><a href="https://powo.science.kew.org/results?q=${encodeURIComponent(name)}" target="_blank" rel="noopener">POWO(큐 왕립식물원)에서 자라는 지역 확인</a> · <a href="https://scholar.google.com/scholar?q=%22${encodeURIComponent(name)}%22" target="_blank" rel="noopener">관련 논문 검색</a></li>
      </ul>
      <p class="small">이름이나 분류가 틀렸나요? ${reportBtn("이름·분류")}</p>
    </section>`;

  renderCare(row[0], genus);
  loadGbif(name, id);
}

// 2·3단계 자료(재배, 병해충, 산림청 정보)는 data/care/<id>.json에 있다. 원문은 고치지 않고 보여 준다.
const DISEASE_FIELDS = [["symptoms", "증상"], ["condition", "잘 생기는 조건"], ["prevention", "예방과 방제"], ["chemical", "약제 방제"], ["biology", "천적·미생물 방제"], ["pathogen", "병원체"]];
const INSECT_FIELDS = [["damage", "피해"], ["form", "생김새"], ["ecology", "생활사"], ["prevention", "방제 방법"], ["chemical", "약제 방제"], ["biology", "천적·미생물 방제"], ["distrib", "분포"]];

function pestItem(p, fields, sub) {
  return `<details class="pest">
    <summary><b>${esc(p.name)}</b>${sub ? ` <span class="muted small">${sub}</span>` : ""}</summary>
    <div class="pest-body">
      ${p.img ? `<img src="${esc(p.img)}" alt="${esc(p.name)}" loading="lazy" referrerpolicy="no-referrer">` : ""}
      <dl>${fields.filter(([k]) => p[k]).map(([k, label]) => `<dt>${label}</dt><dd>${esc(p[k])}</dd>`).join("")}</dl>
      ${p.prevention || p.chemical || p.biology ? "" : `<p class="small muted">이 항목에는 NCPMS에 방제 방법이 등록되어 있지 않습니다.</p>`}
    </div>
  </details>`;
}

function gardenCard(g) {
  return `
    <section class="card">
      <h2>키우는 방법</h2>
      ${regionLine("grow")}
      ${g.items.map(it => `
        ${g.items.length > 1 ? `<h3 class="sub">${esc(it.name)} <i class="muted small">${esc(it.sci)}</i></h3>` : ""}
        <div class="facts">
          ${[["꽃 피는 때", it.bloom], ["열매 맺는 때", it.fruit], ["잎 나는 때", it.leaf], ["꽃 색", it.color]].filter(([, v]) => v).map(([k, v]) => `<div class="fact"><span class="k">${k}</span><span class="v">${esc(v)}</span></div>`).join("")}
        </div>
        <dl class="prose">
          ${[["기르는 법", it.care], ["정원에 심는 법", it.garden], ["특징", it.feature]].filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}
        </dl>`).join("")}
      <div class="src">출처: ${esc(g.source)} · 확인일 ${esc(g.retrieved)} · 원문을 고치지 않고 실었습니다 · <a href="${esc(g.url)}" target="_blank" rel="noopener">자료 안내</a> ${reportBtn("키우는 방법(정원식물)")}</div>
    </section>`;
}

const AIR_SHORT = ["빛", "온도", "습도", "물주기", "흙", "비료"];
function airCard(a) {
  return `
    <section class="card">
      <h2>실내에서 키우는 방법</h2>
      ${regionLine("air")}
      ${a.items.map(it => `
        ${a.items.length > 1 ? `<h3 class="sub">${esc(it.name)}</h3>` : ""}
        ${it.img ? `<img class="air-img" src="${esc(it.img)}" alt="${esc(it.name)}" loading="lazy" referrerpolicy="no-referrer">` : ""}
        ${it.care.some(([k]) => AIR_SHORT.includes(k)) ? `<div class="facts">${it.care.filter(([k]) => AIR_SHORT.includes(k)).map(([k, v]) => `<div class="fact"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("")}</div>` : ""}
        <dl class="prose">
          ${it.care.filter(([k]) => !AIR_SHORT.includes(k)).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}
          ${it.place ? `<dt>두면 좋은 곳</dt><dd>${esc(it.place)}${it.placeText ? `\n${esc(it.placeText)}` : ""}</dd>` : ""}
          ${it.use ? `<dt>이렇게 키워 보세요</dt><dd>${esc(it.use)}</dd>` : ""}
          ${it.info.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}
          ${it.desc ? `<dt>설명</dt><dd>${esc(it.desc)}</dd>` : ""}
          ${it.effects.length ? `<dt>공기정화 실험 등급</dt><dd>${esc(it.effects.join(" · "))}</dd>` : ""}
        </dl>`).join("")}
      <p class="small genus-note">공기정화 효과는 밀폐된 실험 공간에서 잰 값입니다. 실제 집에서는 화분 몇 개의 효과가 환기에 비해 매우 작다는 연구가 있습니다 (Cummings &amp; Waring, 2020, <a href="https://doi.org/10.1038/s41370-019-0175-9" target="_blank" rel="noopener">doi:10.1038/s41370-019-0175-9</a>).</p>
      <div class="src">출처: ${esc(a.source)} · ${esc(a.license)} · 확인일 ${esc(a.retrieved)} · 원문을 고치지 않고 항목별로 나눠 실었습니다 · <a href="${esc(a.url)}" target="_blank" rel="noopener">자료 안내</a><br>자료와 학명의 연결: ${esc(a.mapping)} ${reportBtn("실내에서 키우는 방법")}</div>
    </section>`;
}

function kfsItem(it, withName) {
  return `
    ${withName ? `<h3 class="sub">${esc(it.name)} <i class="muted small">${esc(it.sci)}</i></h3>` : ""}
    ${it.protected || it.endemic ? `<div class="tags">${it.protected ? `<span class="badge amber">보호식물</span>` : ""}${it.endemic ? `<span class="badge">한국 특산식물</span>` : ""}</div>` : ""}
    <div class="facts">
      ${[["꽃 피기 시작하는 달", it.bloom && `${it.bloom}월`], ["결실기", it.fruit && `${it.fruit}월`], ["과", it.family]].filter(([, v]) => v).map(([k, v]) => `<div class="fact"><span class="k">${k}</span><span class="v">${esc(v)}</span></div>`).join("")}
    </div>
    ${it.size ? `<dl class="prose"><dt>크기</dt><dd>${esc(it.size)}</dd></dl>` : ""}`;
}

// 대표 이름과 같은 항목을 먼저 보여 주고, 함께 연결된 품종·변종은 접어 둔다.
function kfsCard(k, mainName) {
  const main = k.items.find(it => it.name === mainName) || k.items[0];
  const rest = k.items.filter(it => it !== main);
  return `
    <section class="card">
      <h2>우리나라 식물 정보</h2>
      ${regionLine("kfs")}
      ${kfsItem(main, false)}
      ${rest.length ? `<details class="more-items"><summary>함께 연결된 품종·변종 ${rest.length}개 더 보기</summary>${rest.map(it => kfsItem(it, true)).join("")}</details>` : ""}
      <div class="src">출처: ${esc(k.source)} · 자료 기준일 ${esc(k.basis)} · <a href="${esc(k.url)}" target="_blank" rel="noopener">자료 안내</a> ${reportBtn("우리나라 식물 정보")}</div>
    </section>`;
}

// 우리 동네 겨울나기: 식물이 견디는 추위(USDA 구역)와 기상청 관측소의 겨울 최저기온 30년 평균을 비교한다.
let CLIMATE = null, WINTER = null;
const getRegion = () => { try { return localStorage.getItem("region") || "108"; } catch { return "108"; } };
function winterVerdict(st) {
  const diff = st[2] - WINTER.zoneC;
  if (diff >= 2.8) return ["ok", "밖에서 겨울을 날 수 있는 추위입니다"];
  if (diff >= 0) return ["edge", "견딜 수 있는 한계에 가깝습니다. 추운 해에는 피해가 날 수 있어요"];
  return ["no", "밖에서 겨울을 나기 어렵습니다. 겨울에는 실내로 들이거나 보온해 주세요"];
}
function winterBody() {
  const st = CLIMATE.stations.find(s => s[0] === getRegion()) || CLIMATE.stations[0];
  const [cls, text] = winterVerdict(st);
  const okList = CLIMATE.stations.filter(s => s[2] - WINTER.zoneC >= 0).map(s => s[1]);
  return `
    <div class="verdict ${cls}"><b>${esc(st[1])}</b>: ${text}</div>
    <div class="facts">
      <div class="fact"><span class="k">${esc(st[1])}의 겨울 최저기온 (30년 평균)</span><span class="v mono">${st[2]}°C · USDA ${esc(st[4])} 구역</span></div>
      <div class="fact"><span class="k">이 식물이 견디는 추위</span><span class="v mono">약 ${WINTER.zoneC}°C · USDA ${esc(WINTER.zone)} 구역</span></div>
    </div>
    <p class="small">${okList.length ? `관측소 ${CLIMATE.stations.length}곳 중 ${okList.length}곳에서 견딜 수 있는 추위입니다: ${esc(okList.slice(0, 30).join(", "))}${okList.length > 30 ? " 등" : ""}` : `우리나라 관측소 ${CLIMATE.stations.length}곳 모두 이 식물이 견디기 어려운 추위가 옵니다.`}</p>`;
}
async function winterCard(web) {
  if (web?.zoneC == null) return "";
  CLIMATE = CLIMATE || await optional(getJSON("data/climate.json"));
  if (!CLIMATE?.stations?.length) return "";
  WINTER = web;
  const region = getRegion();
  return `
    <section class="card">
      <h2>우리 동네에서 겨울나기</h2>
      <label class="field small">사는 곳과 가까운 관측소
        <select id="winter-region">${CLIMATE.stations.map(s => `<option value="${s[0]}"${s[0] === region ? " selected" : ""}>${esc(s[1])}</option>`).join("")}</select></label>
      <div id="winter-body">${winterBody()}</div>
      <p class="small muted">미국 농무부(USDA) 추위 구역과 같은 방식으로 비교했습니다. 해마다 가장 추웠던 날 기온의 평균이라 유난히 추운 해에는 더 내려갈 수 있고, 바람·눈·화분에 심었는지에 따라서도 달라집니다.</p>
      <div class="src">식물 쪽: NC State Plant Toolbox의 USDA 내한성 구역 · 동네 쪽: ${esc(CLIMATE.source)}, ${esc(CLIMATE.basis)} · <a href="${esc(CLIMATE.url)}" target="_blank" rel="noopener">자료 안내</a> ${reportBtn("우리 동네에서 겨울나기")}</div>
    </section>`;
}
document.addEventListener("change", e => {
  if (e.target.id !== "winter-region") return;
  try { localStorage.setItem("region", e.target.value); } catch { /* 저장소를 쓸 수 없으면 무시 */ }
  document.getElementById("winter-body").innerHTML = winterBody();
});

// 공공기관 자료가 아닌 대학 원예 자료. 정해진 항목 값만 한국어로 옮겼다.
function webCard(w, name) {
  const q = encodeURIComponent(w.name || name);
  return `
    <section class="card web">
      <h2>인터넷 재배 정보</h2>
      ${regionLine("web")}
      <p class="small web-note">공공기관 자료가 아닌 미국 대학의 원예 자료입니다. 야외에 심는 것을 기준으로 해서 우리나라 환경, 특히 실내와는 다를 수 있습니다.</p>
      ${w.pets?.length ? `<div class="tags"><span class="badge amber">${w.pets.join("·")}에게 해로움</span></div>` : ""}
      ${w.facts.length ? `<div class="facts">${w.facts.map(([k, v]) => `<div class="fact"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("")}</div>` : ""}
      ${w.notes.length ? `<dl class="prose">${w.notes.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>` : ""}
      <div class="src">출처: ${esc(w.source)} · 확인일 ${esc(w.retrieved)} · 정해진 항목 값만 한국어로 옮겼고, 목록에 없는 값은 영어 원문 그대로 두었습니다 · <a href="${esc(w.url)}" target="_blank" rel="noopener">원문 보기 (영어)</a><br>
      다른 곳에서도 확인해 보세요: <a href="https://www.rhs.org.uk/plants/search-results?query=${q}" target="_blank" rel="noopener">영국왕립원예협회(RHS)</a> ${reportBtn("인터넷 재배 정보")}</div>
    </section>`;
}

// 농사로 현장기술지원 사례: 공공누리 제4유형(변경금지)이라 문장을 고치지 않고 그대로 보여 준다.
function casesCard(c) {
  const method = it => (it.sections.find(([h]) => /^(영농현황|경종개요)/.test(h))?.[1] || []).find(l => /재배\s*(방식|형태|양식)/.test(l))?.split(":").pop().trim();
  return `
    <section class="card">
      <h2>현장 진단 사례</h2>
      ${regionLine("cases")}
      <p class="small muted">농가에서 "왜 이러는지 모르겠다"고 문의한 문제를 농촌진흥청이 현장에서 조사하고 진단한 기록입니다. 병해충뿐 아니라 양분 부족, 날씨, 약해 같은 생리장해도 들어 있어요. 이름을 누르면 진단 내용이 원문 그대로 나옵니다.</p>
      <div class="pests">${c.items.map(it => `
        <details class="pest case-item" data-no="${esc(it.no)}">
          <summary><b>${esc(it.title)}</b> <span class="muted small">${esc(it.date)} · ${esc(it.region)}${method(it) ? ` · ${esc(method(it))}` : ""}</span></summary>
          <div class="pest-body">
          ${it.note ? `<p class="small genus-note">${esc(it.note)}</p>` : ""}
          ${it.mixed ? `<p class="small genus-note">원문에 이 사례와 다른 작물(${it.mixed.map(esc).join(", ")})의 정보가 잘못 섞여 있어 그 부분은 싣지 않았어요.</p>` : ""}
          <dl>
            ${it.sections.map(([h, items]) => `<dt>${esc(h)}</dt><dd>${items.map(esc).join("\n")}</dd>`).join("")}
          </dl>
          ${it.omitted ? `<p class="small muted">이름·연락처·주소가 들어 있을 수 있는 줄 ${it.omitted}개는 싣지 않았습니다.</p>` : ""}
          <a class="small" href="${esc(c.url + it.no)}" target="_blank" rel="noopener">농사로 원문과 사진 보기</a></div>
        </details>`).join("")}
      </div>
      <div class="src">출처: ${esc(c.source)} · ${esc(c.license)} · 확인일 ${esc(c.retrieved)} · 문장은 고치지 않았고, 담당자·농가 정보가 담긴 '개요'와 개인정보가 의심되는 줄, 사진은 싣지 않았습니다. 전체는 원문에서 볼 수 있습니다 ${reportBtn("현장 진단 사례")}</div>
    </section>`;
}

function pestCard(care, genus, id) {
  const pests = care.pests;
  const genusNote = care.unit === "genus"
    ? `<p class="small genus-note">이 자료는 <i>${esc(genus)}</i> 속 전체에 해당하는 작물 자료입니다.${id ? " 이 종에만 해당하지 않을 수 있습니다." : ""}</p>` : "";
  return `
    <section class="card">
      <h2>조심해야 할 병해충</h2>
      ${regionLine("pests")}
      ${genusNote}
      <p class="small muted">농촌진흥청 국가농작물병해충관리시스템의 ${pests.crops.map(c => `‘${esc(c)}’`).join(", ")} 자료입니다. 이름을 누르면 증상과 방제 방법이 나옵니다. 약은 그 작물에 등록된 제품을 라벨에 적힌 대로 쓰세요.</p>
      <a class="btn-link" href="#/symptom/${encodeURIComponent(pests.crops[0])}">어떤 병인지 모르겠다면: 증상으로 찾기 →</a>
      ${pests.diseases.length ? `<h3 class="sub">병 <span class="muted small">${pests.diseases.length}가지</span></h3>
        <div class="pests">${pests.diseases.map(p => pestItem(p, DISEASE_FIELDS, [p.eng, pests.crops.length > 1 ? p.crop : ""].filter(Boolean).map(esc).join(" · "))).join("")}</div>` : ""}
      ${pests.insects.length ? `<h3 class="sub">해충 <span class="muted small">${pests.insects.length}가지</span></h3>
        <div class="pests">${pests.insects.map(p => pestItem(p, INSECT_FIELDS, [p.sci ? `<i>${esc(p.sci)}</i>` : "", esc(p.family || ""), pests.crops.length > 1 ? esc(p.crop) : ""].filter(Boolean).join(" · "))).join("")}</div>` : ""}
      <div class="src">출처: ${esc(pests.source)} · 확인일 ${esc(pests.retrieved)} · 원문을 고치지 않고 실었습니다 · <a href="${esc(pests.url)}" target="_blank" rel="noopener">NCPMS 바로가기</a><br>작물명과 학명의 연결: ${esc(care.mapping)} ${reportBtn("병해충")}</div>
    </section>`;
}

// id가 없으면 속 페이지. 종에 자료가 없고 속 전체 자료가 있으면 그것을 보여 준다.
async function renderCare(id, genus) {
  const box = document.getElementById("care");
  const own = id && CI[id] ? await optional(getJSON(`data/care/${id}.json`)) : null;
  const forGenus = CI[`g:${genus}`] ? await optional(getJSON(`data/care/g-${genus}.json`)) : null;
  if (!box || !decodeURIComponent(location.hash).includes(id || genus)) return;

  // 종 자체의 재배 자료가 없으면 속 전체에 연결된 재배 자료를 안내와 함께 보여 준다.
  const useGenus = !(own?.grow || own?.air) && (forGenus?.grow || forGenus?.air);
  const src = useGenus ? forGenus : own;
  const genusNote = useGenus && id
    ? `<p class="small genus-note">이 종만의 재배 자료는 없어, <a href="#/g/${encodeURIComponent(genus)}"><i>${esc(genus)}</i> 속</a> 전체에 연결된 자료를 보여 드립니다. 이 종에 꼭 맞지 않을 수 있습니다.</p>` : "";
  const webHtml = own?.web ? webCard(own.web, CI[id] ? fullName(CI[id].g, CI[id].r) : genus) + await winterCard(own.web) : "";
  const methods = [
    ["indoor", "실내·화분", src?.air ? genusNote + airCard(src.air) : ""],
    ["field", "노지·정원", (src?.grow ? genusNote + gardenCard(src.grow) : "") + webHtml],
    ["house", "시설·온실", ""],
    ["smart", "스마트팜", own?.smart ? smartCard(own.smart) : ""],
  ];
  const pestSrc = own?.pests ? own : forGenus?.pests ? forGenus : null;
  box.innerHTML = [
    methods.some(m => m[2]) || isCrop(CI[id]) ? methodTabs(methods, CI[id]) : (id ? `<section class="card pending"><h2>키우는 방법</h2><p>이 식물은 아직 재배 자료가 없습니다. 확인되지 않은 정보는 싣지 않습니다.</p></section>` : ""),
    pestSrc ? pestCard(pestSrc, genus, id) : (id && methods.some(m => m[2]) ? `<section class="card pending"><h2>병해충</h2><p>이 식물은 아직 공공기관의 병해충 자료가 없습니다.</p></section>` : ""),
    own?.cases ? casesCard(own.cases) : "",
    own?.kfs ? kfsCard(own.kfs, CI[id]?.name) : "",
  ].join("");

  // 증상 검색 결과에서 들어왔으면 그 병해충이나 사례를 펼쳐서 보여 준다
  if (OPEN_PEST) {
    const d = OPEN_PEST.startsWith("case-")
      ? box.querySelector(`details.case-item[data-no="${CSS.escape(OPEN_PEST.slice(5))}"]`)
      : [...box.querySelectorAll("details.pest")].find(x => x.querySelector("summary b")?.textContent === OPEN_PEST);
    OPEN_PEST = "";
    if (d) { d.open = true; d.scrollIntoView({ block: "start" }); }
  }
}

// 재배 방식별 탭. 자료가 없는 방식도 탭은 보여 주고, 왜 없는지 알려 준다.
const SMART_CROPS = ["토마토", "딸기", "파프리카"];
const isCrop = v => (v?.cats || []).some(c => ["veg", "fruit", "grain", "herbal"].includes(c));
function methodEmpty(key, v) {
  const crop = isCrop(v);
  if (key === "smart") return "공개된 공식 스마트팜 재배 기준은 지금 완숙토마토, 딸기, 파프리카 세 가지뿐입니다.";
  if (key === "house") {
    return crop
      ? "농촌진흥청 농사로의 시설재배 자료를 연결하는 중입니다."
      : "이 식물의 시설·온실 재배 공식 자료는 아직 없습니다.";
  }
  if (key === "field" && crop) return "농촌진흥청 농사로의 텃밭 재배 자료를 연결하는 중입니다.";
  return "이 재배 방식의 자료는 아직 없습니다. 확인되지 않은 정보는 싣지 않습니다.";
}

function methodTabs(methods, v) {
  let saved = null;
  try { saved = localStorage.getItem("method"); } catch { /* 저장소를 쓸 수 없으면 무시 */ }
  const active = methods.find(m => m[0] === saved && m[2]) || methods.find(m => m[2])
    || methods.find(m => m[0] === (SMART_CROPS.some(c => v?.crops?.includes(c)) ? "smart" : "field"));
  return `
    <section class="methods">
      <div class="methods-head"><h2>키우는 방법</h2><span class="small muted">재배 방식을 골라 보세요</span></div>
      <div class="method-tabs" role="tablist">
        ${methods.map(([key, label, html]) => `<button role="tab" data-method="${key}" aria-selected="${key === active[0]}" class="${html ? "" : "empty"}">${label}${html ? "" : `<span class="dot" aria-label="자료 없음">–</span>`}</button>`).join("")}
      </div>
      ${methods.map(([key, , html]) => `<div class="method-panel" data-panel="${key}"${key === active[0] ? "" : " hidden"}>${html || `<div class="card pending"><p>${methodEmpty(key, v)}</p></div>`}</div>`).join("")}
    </section>`;
}

document.addEventListener("click", e => {
  const tab = e.target.closest(".method-tabs button");
  if (!tab) return;
  const box = tab.closest(".methods");
  box.querySelectorAll(".method-tabs button").forEach(b => b.setAttribute("aria-selected", b === tab));
  box.querySelectorAll(".method-panel").forEach(p => { p.hidden = p.dataset.panel !== tab.dataset.method; });
  try { localStorage.setItem("method", tab.dataset.method); } catch { /* 무시 */ }
});

// 스마트팜 최적 환경 자료 (농촌진흥청). 시설 종류와 생육 단계를 고르면 그 표만 보여 준다.
let SMART = null;
function smartTable(fi, si) {
  const t = SMART.facilities[fi].steps[si];
  return `<div class="table-wrap"><table>
    <thead><tr>${t.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${t.rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody>
  </table></div><p class="small muted">${t.rows.length}가지 환경 조합</p>`;
}
function smartCard(s) {
  SMART = s;
  const opts = (list, f) => list.map((x, i) => `<option value="${i}">${esc(f(x))}</option>`).join("");
  return `
    <section class="card">
      <h2>스마트팜 최적 환경 (${esc(s.crop)})</h2>
      ${regionLine("smart")}
      <p class="small">우수 농가의 자료로 만든 생산성 향상 모델입니다. 그날의 누적일사량과 바깥 기온에 맞는 줄을 찾아, 온실 안 온도·습도·CO₂·양액을 맞추는 기준으로 쓰세요.</p>
      <div class="smart-pick">
        <label>시설 종류 <select id="smart-fac">${opts(s.facilities, f => f.label)}</select></label>
        <label>생육 단계 <select id="smart-step">${opts(s.facilities[0].steps, t => t.step)}</select></label>
      </div>
      <div id="smart-table">${smartTable(0, 0)}</div>
      <div class="src">출처: ${esc(s.source)} · 확인일 ${esc(s.retrieved)} · 시설·단계 이름과 단위는 농촌진흥청 농업기술 데이터 플랫폼 화면을 따랐습니다 · <a href="${esc(s.url)}" target="_blank" rel="noopener">자료 안내</a> ${reportBtn("스마트팜")}</div>
    </section>`;
}
document.addEventListener("change", e => {
  if (!SMART || !["smart-fac", "smart-step"].includes(e.target.id)) return;
  const fac = document.getElementById("smart-fac"), step = document.getElementById("smart-step");
  if (e.target.id === "smart-fac") {
    step.innerHTML = SMART.facilities[fac.value].steps.map((t, i) => `<option value="${i}">${esc(t.step)}</option>`).join("");
  }
  document.getElementById("smart-table").innerHTML = smartTable(+fac.value, +step.value);
});

// GBIF가 주는 영어 나라 이름 중 자주 나오는 것만 한국어로 바꾸고, 나머지는 그대로 둔다.
const COUNTRY_KO = {
  "Korea, Republic of": "대한민국", "Republic of Korea": "대한민국", "Japan": "일본", "China": "중국", "Taiwan": "대만",
  "United States of America": "미국", "United States": "미국", "Canada": "캐나다", "Mexico": "멕시코",
  "United Kingdom of Great Britain and Northern Ireland": "영국", "United Kingdom": "영국", "France": "프랑스", "Germany": "독일",
  "Netherlands": "네덜란드", "Belgium": "벨기에", "Spain": "스페인", "Portugal": "포르투갈", "Italy": "이탈리아", "Russian Federation": "러시아",
  "Australia": "오스트레일리아", "New Zealand": "뉴질랜드", "India": "인도", "Thailand": "태국", "Viet Nam": "베트남", "Brazil": "브라질",
  "Argentina": "아르헨티나", "Colombia": "콜롬비아", "Costa Rica": "코스타리카", "South Africa": "남아프리카공화국", "Philippines": "필리핀",
  "Indonesia": "인도네시아", "Malaysia": "말레이시아", "Sweden": "스웨덴", "Norway": "노르웨이", "Finland": "핀란드", "Denmark": "덴마크",
  "Austria": "오스트리아", "Switzerland": "스위스", "Poland": "폴란드", "Ecuador": "에콰도르", "Peru": "페루", "Chile": "칠레",
};
const countryKo = c => COUNTRY_KO[c] || c;

const OPEN_LICENSE = /publicdomain|creativecommons\.org\/licenses\/by(-nc)?\/|^CC0|^CC_BY|^CC BY/i;
function licenseLabel(l) {
  if (!l) return "";
  if (/publicdomain|CC0/i.test(l)) return "CC0";
  const m = l.match(/licenses\/(by(?:-nc)?(?:-sa)?)\/([\d.]+)/i);
  return m ? `CC ${m[1].toUpperCase()} ${m[2]}` : l.replace(/_/g, " ");
}

async function loadGbif(name, id) {
  const vern = document.getElementById("vern");
  const photos = document.getElementById("photos");
  const still = () => location.hash.includes(id);
  const known = new Set([CI[id]?.name, ...(CI[id]?.ko || []), ...(CI[id]?.crops || [])].filter(Boolean));
  try {
    const match = await (await fetch(`${GBIF}/species/match?name=${encodeURIComponent(name)}&kingdom=Plantae&strict=true`)).json();
    // 이름이 정확히 맞을 때만 쓴다. GBIF가 이 이름을 더 넓은 종의 다른 이름으로 묶어 두었더라도(예: 배추 -> Brassica rapa 전체)
    // 상위 종으로 넘어가지 않고 이 이름으로 기록된 사진과 일반 이름만 가져온다.
    const key = match.matchType === "EXACT" ? match.usageKey : null;
    if (!key) throw new Error("no exact match");
    document.getElementById("gbif-src").innerHTML = `다른 이름과 사진: <a href="https://www.gbif.org/species/${key}" target="_blank" rel="noopener">GBIF 종 정보 ${key}</a> (자료마다 라이선스 표시)`;

    const [vn, occ] = await Promise.all([
      fetch(`${GBIF}/species/${key}/vernacularNames?limit=300`).then(r => r.json()),
      fetch(`${GBIF}/occurrence/search?taxonKey=${key}&mediaType=StillImage&limit=40`).then(r => r.json()),
    ]);
    if (!still()) return;

    const seen = new Set();
    const names = (vn.results || [])
      .filter(v => v.language === "kor" || isHangul(v.vernacularName) || (v.language === "eng" && !/[^\u0000-ɏ\s'’.-]/.test(v.vernacularName)))
      .filter(v => { const k = v.vernacularName.toLowerCase(); if (seen.has(k) || known.has(v.vernacularName)) return false; seen.add(k); return true; })
      .sort((a, b) => isHangul(b.vernacularName) - isHangul(a.vernacularName));
    const otherKo = [...known].filter(n => n !== CI[id]?.name);
    vern.innerHTML = (otherKo.length ? `<span class="muted small">함께 연결된 이름·품종</span>${otherKo.map(n => `<span>${esc(n)}</span>`).join("")}` : "")
      + (names.length ? `<span class="muted small">다른 이름 (GBIF)</span>${names.slice(0, 8).map(v => `<span title="출처: ${esc(v.source || "GBIF")}">${esc(v.vernacularName)}</span>`).join("")}` : "");

    const pics = [];
    // 자라는 모습을 찍은 관찰 사진을 앞에, 말린 식물 표본 사진을 뒤에 둔다
    const isSpecimen = o => /SPECIMEN/.test(o.basisOfRecord || "");
    const ordered = (occ.results || []).slice().sort((a, b) => isSpecimen(a) - isSpecimen(b));
    for (const o of ordered) {
      for (const m of o.media || []) {
        const lic = m.license || o.license || "";
        if (m.type !== "StillImage" || !m.identifier || !OPEN_LICENSE.test(lic)) continue;
        pics.push({ url: m.identifier, lic, who: m.rightsHolder || m.creator || o.recordedBy || "", occ: o.key, where: o.country || "", specimen: isSpecimen(o) });
        break;
      }
      if (pics.length >= 6) break;
    }
    photos.className = "photos";
    photos.innerHTML = pics.length ? pics.map(p => `
      <figure class="photo">
        <a href="https://www.gbif.org/occurrence/${encodeURIComponent(p.occ)}" target="_blank" rel="noopener"><img src="${esc(p.url)}" alt="${esc(CI[id]?.name || name)} 관찰 사진" loading="lazy" referrerpolicy="no-referrer"></a>
        <figcaption>${p.specimen ? `<b>말린 표본</b> · ` : ""}${p.where ? `<b>${esc(countryKo(p.where))}</b>에서 ${p.specimen ? "채집" : "촬영"} · ` : ""}${esc(p.who)} · ${esc(licenseLabel(p.lic))}</figcaption>
      </figure>`).join("")
      : `<p class="small muted">이 이름으로 기록된, 자유롭게 쓸 수 있는 관찰 사진이 아직 없습니다.</p>`;
    photos.insertAdjacentHTML("afterend", pics.length ? `<p class="src">사진은 여러 나라 사람들이 GBIF에 올린 관찰 기록입니다. 찍은 나라의 기후에 따라 모습이 다를 수 있고, 식물을 잘못 알아본 사진이 섞여 있을 수 있습니다. 사진을 누르면 원본 기록으로 갑니다.</p>` : "");
  } catch (err) {
    if (!still()) return;
    const otherKo = [...known].filter(n => n !== CI[id]?.name);
    vern.innerHTML = otherKo.length ? `<span class="muted small">함께 연결된 이름·품종</span>${otherKo.map(n => `<span>${esc(n)}</span>`).join("")}` : "";
    photos.className = "small muted";
    photos.textContent = err.message === "no exact match"
      ? "GBIF에 이 학명과 정확히 같은 기록이 없어 사진을 싣지 않았습니다. 비슷한 다른 식물의 사진이 섞이지 않게 하기 위해서입니다."
      : "이 식물의 사진을 찾지 못했습니다 (인터넷 연결이 필요합니다).";
  }
}

// ---------- 속, 과 목록 ----------
async function renderGenus(genus) {
  const g = generaMap.get(genus);
  const sp = await spBucket(genus);
  const rows = (sp[genus] || []).slice().sort((a, b) => !!CI[b[0]]?.name - !!CI[a[0]]?.name);
  const named = rows.filter(r => CI[r[0]]?.name).length;
  app.innerHTML = `
    <nav class="crumbs">${g ? `<a href="#/f/${encodeURIComponent(g[1])}">${famLabel(g[1])}</a>` : ""}</nav>
    <section class="sheet-head"><h1>${esc(genus)}</h1><div class="author">속 · ${fmt(rows.length)}종류${named ? ` · 한국어 이름이 있는 식물 ${fmt(named)}종을 위에 보여 드립니다` : ""}</div></section>
    <div id="care"></div>
    ${rows.length ? `<div class="list">${rows.map(r => speciesRow(genus, r)).join("")}</div>` : `<div class="empty">이 속에 등록된 종이 없습니다.</div>`}`;
  renderCare(null, genus);
}

async function renderFamily(family) {
  const gl = (await genera()).filter(g => g[1] === family);
  const total = gl.reduce((s, g) => s + g[2], 0);
  app.innerHTML = `
    <nav class="crumbs"><a href="#/families">모든 과</a></nav>
    <section class="sheet-head"><h1 class="ko-title">${FK[family] ? esc(FK[family]) : esc(family)}</h1><div class="author">${FK[family] ? `${esc(family)} · ` : ""}${fmt(gl.length)}속 · ${fmt(total)}종</div></section>
    <div class="list">${gl.map(g => `<a class="row" href="#/g/${encodeURIComponent(g[0])}"><span class="title"><i>${esc(g[0])}</i></span><span class="side">${fmt(g[2])}종</span></a>`).join("")}</div>`;
}

async function renderFamilies() {
  const fl = await getJSON("data/families.json");
  const sorted = fl.slice().sort((a, b) => (FK[a[0]] ? 0 : 1) - (FK[b[0]] ? 0 : 1) || (FK[a[0]] && FK[b[0]] ? byKo(FK[a[0]], FK[b[0]]) : a[0].localeCompare(b[0])));
  app.innerHTML = `
    <nav class="crumbs"><a href="#/">처음으로</a></nav>
    <section class="sheet-head"><h1 class="ko-title">모든 과</h1><div class="author">${fmt(fl.length)}개 과 · 한국어 이름이 있는 과를 가나다순으로 먼저 보여 드립니다</div></section>
    <div class="list">${sorted.map(f => `<a class="row" href="#/f/${encodeURIComponent(f[0])}"><span class="title">${FK[f[0]] ? `<b class="ko">${esc(FK[f[0]])}</b> <span class="sci-s">${esc(f[0])}</span>` : esc(f[0])}</span><span class="side">${fmt(f[1])}속 · ${fmt(f[2])}종</span></a>`).join("")}</div>`;
}

// ---------- 시작 ----------
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
route();
