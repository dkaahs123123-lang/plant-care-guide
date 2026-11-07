"use strict";

// 화면 키보드: 검색창 옆 키보드 단추를 누르면 마우스로 누르는 한글·영문 자판이 열린다.
// 입력창의 글자를 자모로 풀었다가 누른 글자를 붙여 다시 조합하므로, 실제 키보드로 친 글자와 섞여도 어긋나지 않는다.
(() => {
  const input = document.getElementById("q");
  const form = document.getElementById("search-form");
  if (!input || !form) return;

  // ---------- 한글 조합 ----------
  const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
  const JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ";
  const JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
  const VOWEL_PAIRS = { "ㅗㅏ": "ㅘ", "ㅗㅐ": "ㅙ", "ㅗㅣ": "ㅚ", "ㅜㅓ": "ㅝ", "ㅜㅔ": "ㅞ", "ㅜㅣ": "ㅟ", "ㅡㅣ": "ㅢ" };
  const FINAL_PAIRS = { "ㄱㅅ": "ㄳ", "ㄴㅈ": "ㄵ", "ㄴㅎ": "ㄶ", "ㄹㄱ": "ㄺ", "ㄹㅁ": "ㄻ", "ㄹㅂ": "ㄼ", "ㄹㅅ": "ㄽ", "ㄹㅌ": "ㄾ", "ㄹㅍ": "ㄿ", "ㄹㅎ": "ㅀ", "ㅂㅅ": "ㅄ" };
  const SPLIT = {};
  for (const [pair, one] of Object.entries({ ...VOWEL_PAIRS, ...FINAL_PAIRS })) SPLIT[one] = [...pair];
  const isVowel = c => !!c && JUNG.includes(c);

  // 글자를 자모로 푼다: '감' -> ㄱ ㅏ ㅁ, '닭' -> ㄷ ㅏ ㄹ ㄱ, 'ㅘ' -> ㅗ ㅏ
  function decompose(text) {
    const out = [];
    for (const ch of text) {
      const code = ch.charCodeAt(0) - 0xAC00;
      if (code >= 0 && code < 11172) {
        out.push(CHO[Math.floor(code / 588)]);
        out.push(...(SPLIT[JUNG[Math.floor(code / 28) % 21]] || [JUNG[Math.floor(code / 28) % 21]]));
        const jong = JONG[code % 28];
        if (jong) out.push(...(SPLIT[jong] || [jong]));
      } else {
        out.push(...(SPLIT[ch] || [ch]));
      }
    }
    return out;
  }

  // 자모를 글자로 묶는다. 받침 뒤에 모음이 오면 받침을 다음 글자의 첫소리로 넘긴다 (ㄱㅏㅁㅏ -> 가마)
  function assemble(js) {
    let out = "", i = 0;
    while (i < js.length) {
      const c = js[i];
      if (CHO.includes(c) && isVowel(js[i + 1])) {
        let v = js[i + 1];
        i += 2;
        if (VOWEL_PAIRS[v + js[i]]) v = VOWEL_PAIRS[v + js[i++]];
        let jong = "";
        if (JONG.includes(js[i]) && js[i] !== undefined && !isVowel(js[i + 1])) {
          jong = js[i++];
          if (FINAL_PAIRS[jong + js[i]] && !isVowel(js[i + 1])) jong = FINAL_PAIRS[jong + js[i++]];
        }
        out += String.fromCharCode(0xAC00 + (CHO.indexOf(c) * 21 + JUNG.indexOf(v)) * 28 + JONG.indexOf(jong));
      } else if (isVowel(c)) {
        let v = c;
        i++;
        if (VOWEL_PAIRS[v + js[i]]) v = VOWEL_PAIRS[v + js[i++]];
        out += v;
      } else {
        out += c;
        i++;
      }
    }
    return out;
  }

  // ---------- 자판 ----------
  // [보통, Shift] 두벌식 자판 배열
  const KO = [
    [["ㅂ", "ㅃ"], ["ㅈ", "ㅉ"], ["ㄷ", "ㄸ"], ["ㄱ", "ㄲ"], ["ㅅ", "ㅆ"], ["ㅛ"], ["ㅕ"], ["ㅑ"], ["ㅐ", "ㅒ"], ["ㅔ", "ㅖ"]],
    [["ㅁ"], ["ㄴ"], ["ㅇ"], ["ㄹ"], ["ㅎ"], ["ㅗ"], ["ㅓ"], ["ㅏ"], ["ㅣ"]],
    [["ㅋ"], ["ㅌ"], ["ㅊ"], ["ㅍ"], ["ㅠ"], ["ㅜ"], ["ㅡ"]],
  ];
  const EN = ["qwertyuiop", "asdfghjkl", "zxcvbnm"].map(row => [...row].map(c => [c, c.toUpperCase()]));
  let lang = "ko", shift = false;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "kbd-toggle";
  btn.title = "화면 키보드";
  btn.setAttribute("aria-label", "화면 키보드 열기");
  btn.setAttribute("aria-expanded", "false");
  btn.innerHTML = `<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><rect x="2" y="6" width="20" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6 10h1M9.5 10h1M13 10h1M16.5 10h1M6 13h1M9.5 13h1M13 13h1M16.5 13h1M8 16h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`;
  form.appendChild(btn);

  const panel = document.createElement("div");
  panel.className = "kbd";
  panel.hidden = true;
  panel.setAttribute("role", "group");
  panel.setAttribute("aria-label", "화면 키보드");
  form.appendChild(panel);

  const key = (label, data, cls = "") => `<button type="button" class="kbd-key ${cls}" data-k="${data}">${label}</button>`;
  function draw() {
    const rows = lang === "ko" ? KO : EN;
    panel.innerHTML = `
      <div class="kbd-head"><b>${lang === "ko" ? "한글" : "English"}</b>${key("✕", "close", "kbd-close")}</div>
      ${rows.map((row, r) => `<div class="kbd-row">${r === 2 ? key("Shift", "shift", "wide" + (shift ? " on" : "")) : ""}${row.map(([a, b]) => {
        const c = shift && b ? b : a;
        return key(c, c);
      }).join("")}${r === 0 ? key("⌫", "back", "wide") : ""}</div>`).join("")}
      <div class="kbd-row">${key(lang === "ko" ? "한/영" : "영/한", "lang", "wide")}${key("띄어쓰기", "space", "space")}${key("초기화", "clear", "wide")}${key("검색", "go", "wide go")}</div>`;
  }

  function type(k) {
    if (k === "close") return toggle(false);
    if (k === "shift") { shift = !shift; return draw(); }
    if (k === "lang") { lang = lang === "ko" ? "en" : "ko"; shift = false; return draw(); }
    if (k === "go") { toggle(false); return form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true })); }
    let js = decompose(input.value);
    if (k === "back") js.pop();
    else if (k === "clear") js = [];
    else if (k === "space") js.push(" ");
    else {
      js.push(k);
      // 쌍자음·ㅒ·ㅖ를 한 번 넣으면 Shift를 푼다 (일반 키보드와 같게)
      if (shift) { shift = false; draw(); }
    }
    input.value = assemble(js);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function toggle(open = panel.hidden) {
    panel.hidden = !open;
    btn.setAttribute("aria-expanded", String(open));
    btn.setAttribute("aria-label", open ? "화면 키보드 닫기" : "화면 키보드 열기");
    if (open) draw();
  }

  btn.addEventListener("click", () => toggle());
  // 누를 때 입력창의 커서(포커스)를 빼앗지 않게 한다. 휴대폰에서 기기 키보드가 같이 뜨지 않게도 한다
  panel.addEventListener("pointerdown", e => { if (e.target.closest(".kbd-key")) e.preventDefault(); });
  panel.addEventListener("click", e => {
    const b = e.target.closest(".kbd-key");
    if (b) type(b.dataset.k);
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !panel.hidden) toggle(false); });
  document.addEventListener("pointerdown", e => { if (!panel.hidden && !form.contains(e.target)) toggle(false); });
})();
