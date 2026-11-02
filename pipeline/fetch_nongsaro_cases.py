"""생리장해·이상증상: 농사로 '현장기술지원 사례'(농촌진흥청이 농가 현장을 진단한 기록)를 내려받는다.

사용법:
    python -I pipeline/fetch_nongsaro_cases.py data/raw/cases

- 공공누리 제4유형(출처표시, 상업적 이용금지, 변경금지) 자료라 문장은 원문 그대로 저장한다.
- 담당자·출장자·농가 이름과 주소가 들어 있는 '현장기술지원 개요'와 '영농현황'의 이름 줄은 저장하지 않는다.
  지역은 시·군까지만, 영농현황·경종개요는 작물·재배 방법 줄만 남긴다. 받은 원문(html)은 내 컴퓨터에만 둔다.
- robots.txt 가 허용하는 /portal/ps/psz/ 경로만 쓰고, 요청 사이에 쉰다. 이미 받은 사례는 건너뛴다.
"""
import html
from html.parser import HTMLParser
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

SITE = "https://www.nongsaro.go.kr/portal/ps/psz/psza"
UA = "plant-care-guide (non-commercial Korean plant guide)"
DELAY = 1.0
SKIP_SECTIONS = ("현장기술지원 개요", "관련 사진", "관련사진")
# 영농현황·경종개요에는 농가 이름이 섞일 수 있어 작물·재배 방법에 관한 줄만 남긴다
FARM_SECTIONS = ("영농현황", "경종개요")
KEEP_FARM_LINES = ("작물명", "재배작물", "재배방식", "재배양식", "재배형태", "재배면적", "정식시기", "파종시기", "품종")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                body = res.read().decode("utf-8", "ignore")
            time.sleep(DELAY)
            return body
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))


def text(fragment):
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    return re.sub(r"[ \t ]+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


class OldFormat(HTMLParser):
    """첫 번째 형식(tit_2depth/tit_3depth 제목 + right_away_list 목록)을 문서 순서대로 읽는다.
    큰 제목 아래 작은 제목이 여러 개 오거나, 목록 안에 목록이 들어 있는 경우(예: 개요 안의 '농가의견')도 놓치지 않는다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events, self.mode, self.buf, self.li, self.divs = [], None, [], [], []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        if tag == "div":
            self.divs.append("table_area" in cls)  # 표는 원문 링크로 보게 하고 건너뛴다
            return
        if any(self.divs) or tag == "table":
            return
        if tag == "p" and "tit_2depth" in cls:
            self.mode, self.buf = "h2", []
        elif tag == "p" and "tit_3depth" in cls:
            self.mode, self.buf = "h3", []
        elif tag == "li":
            if self.li and not self.li[-1]["label"]:
                # 하위 목록이 시작되면 바깥 항목의 글을 먼저 내보낸다. 짧은 이름(예: '농가의견')만 소제목으로 쓰고,
                # 문장이나 '재배면적 : …' 같은 줄은 그냥 한 줄로 둔다
                parent = self.li[-1]
                parent["label"] = True
                first = text("".join(parent["buf"]))
                is_label = first and len(first) <= 25 and not re.search(r"[:：]|[.。]$|함$|음$|됨$", first)
                self.events.append(("label" if is_label else "li", first))
                if not is_label:
                    parent["label"] = "line"
                parent["buf"] = []
            self.li.append({"buf": [], "label": False, "depth": len(self.li) + 1})
        elif tag == "br":
            self.handle_data("\n")

    def handle_endtag(self, tag):
        if tag == "div":
            if self.divs:
                self.divs.pop()
            return
        if any(self.divs):
            return
        if tag == "p" and self.mode:
            self.events.append((self.mode, text("".join(self.buf))))
            self.mode = None
        elif tag == "li" and self.li:
            item = self.li.pop()
            rest = text("".join(item["buf"]))
            if rest:
                self.events.append(("li", rest))
            if item["label"] is True:
                self.events.append(("end_label", ""))
        elif tag == "ul" and not self.li:
            self.events.append(("end_list", ""))

    def handle_data(self, data):
        if any(self.divs):
            return
        if self.mode:
            self.buf.append(data)
        elif self.li:
            self.li[-1]["buf"].append(data)


def old_format_sections(fragment):
    parser = OldFormat()
    parser.feed(fragment)
    sections, h2, h3, label = [], "", "", ""
    for kind, value in parser.events:
        if kind == "h2":
            h2, h3, label = value, "", ""
        elif kind == "h3":
            h3, label = value, ""
        elif kind == "label":
            label = value
        elif kind == "end_label":
            label = ""
        elif kind == "li":
            head = label or h3 or h2
            # 개요(담당자·장소)는 빼되, 그 안의 '농가의견' 같은 소제목 아래 글은 살린다
            if not head or (not label and any(h2.startswith(s) for s in SKIP_SECTIONS)):
                continue
            if sections and sections[-1][0] == head:
                sections[-1][1].append(value)
            else:
                sections.append([head, [value]])
    return sections


def parse(page, no):
    meta = re.search(r'<meta name="description" content="([^"]*)"', page)
    desc = html.unescape(meta.group(1)) if meta else ""
    field = lambda k: (re.search(rf"{k}\s*:\s*([^,]+)", desc) or [None, ""])[1].strip()
    place = field("장소")
    title = re.search(r'<meta name="title" content="([^"]*)"', page)
    case = {
        "no": no,
        "title": html.unescape(title.group(1)).strip() if title else "",
        "crop": field("품목"),
        "region": " ".join(place.split()[:2]),  # 시·도와 시·군까지만
        "date": field("기술지원일"),
        "sections": [],
    }
    # 사례 페이지는 두 가지 형식이 있다: (1) tit_2depth/tit_3depth 제목 + right_away_list, (2) pszaContents 칸
    sections = []
    area = re.search(r'id="pszaContArea"(.*?)<!-- E://contsBox -->', page, re.S)
    if area and "tit_2depth_right_away" in area.group(1):
        sections = old_format_sections(area.group(1))
    for head_html, body in re.findall(r'<div class="pszaContents">\s*<p class="title">(.*?)</p>(.*?)</div>', page, re.S):
        head = text(head_html)
        if any(head.startswith(s) for s in SKIP_SECTIONS):
            continue
        items = [text(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", body, re.S)]
        if not items:
            items = [text(p) for p in re.findall(r"<p(?:\s[^>]*)?>(.*?)</p>", body, re.S)]
        sections.append([head, items])
    for head, items in sections:
        if head.startswith(FARM_SECTIONS):
            items = [i for i in items if i.replace(" ", "").startswith(tuple(k.replace(" ", "") for k in KEEP_FARM_LINES))]
        items = [i for i in items if i]
        if items:
            case["sections"].append([head, items])
    return case


def main(out_dir, refresh=False):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    (out / "case").mkdir(parents=True, exist_ok=True)

    ids_path = out / "ids.json"
    if refresh:
        ids_path.unlink(missing_ok=True)
    if ids_path.exists():
        ids = json.loads(ids_path.read_text(encoding="utf-8"))
    else:
        ids, page_no = [], 1
        while True:
            body = get(f"{SITE}/contentMain.ps?menuId=PS00077&pageIndex={page_no}")
            found = [n for n in re.findall(r"fncContentSub\('(\d+)'\)", body) if n not in ids]
            if not found:
                break
            ids += found
            if page_no % 20 == 0:
                print(f"목록 {page_no}쪽, {len(ids)}건", flush=True)
            page_no += 1
        ids_path.write_text(json.dumps(ids), encoding="utf-8")
    print(f"사례 {len(ids)}건", flush=True)

    (out / "html").mkdir(exist_ok=True)
    # 원문을 아직 받지 않은 사례만 내려받고, 받아 둔 원문은 매번 다시 읽는다(읽는 방법을 고쳐도 바로 반영됨)
    todo = [n for n in ids if not (out / "html" / f"{n}.html").exists()]
    print(f"새로 받을 사례 {len(todo)}건", flush=True)
    for i, no in enumerate(todo, 1):
        try:
            (out / "html" / f"{no}.html").write_text(get(f"{SITE}/contentSub.ps?menuId=PS00077&cntntsNo={no}"), encoding="utf-8")
        except Exception as err:
            (out / "case" / f"{no}.json").write_text(json.dumps({"no": no, "error": str(err)}), encoding="utf-8")
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}", flush=True)
    for no in ids:
        page = out / "html" / f"{no}.html"
        if not page.exists():
            continue
        case = parse(page.read_text(encoding="utf-8"), no)
        (out / "case" / f"{no}.json").write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")

    (out / "fetched.json").write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d")}), encoding="utf-8")
    print("완료")


if __name__ == "__main__":
    main(sys.argv[1], refresh="--refresh" in sys.argv)
