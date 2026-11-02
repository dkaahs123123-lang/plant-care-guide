"""생리장해·이상증상: 농사로 '현장기술지원 사례'(농촌진흥청이 농가 현장을 진단한 기록)를 내려받는다.

사용법:
    python -I pipeline/fetch_nongsaro_cases.py data/raw/cases

- 공공누리 제4유형(출처표시, 상업적 이용금지, 변경금지) 자료라 문장은 원문 그대로 저장한다.
- 담당자·출장자·농가 이름과 주소가 들어 있는 '현장기술지원 개요'와 '영농현황'의 이름 줄은 저장하지 않는다.
  지역은 시·군까지만, 영농현황은 작물명·재배방식 줄만 남긴다.
- robots.txt 가 허용하는 /portal/ps/psz/ 경로만 쓰고, 요청 사이에 쉰다. 이미 받은 사례는 건너뛴다.
"""
import html
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
KEEP_FARM_LINES = ("작 물 명", "작물명", "재배방식", "재배 방식", "품 종", "품종")


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
    for m in re.finditer(r'<p class="tit_2depth_right_away">(.*?)</p>\s*<ul class="right_away_list">(.*?)</ul>', page, re.S):
        head = text(m.group(1))
        if any(head.startswith(s) for s in SKIP_SECTIONS):
            continue
        items = [text(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", m.group(2), re.S)]
        if head.startswith("영농현황"):
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

    todo = [n for n in ids if not (out / "case" / f"{n}.json").exists()]
    for i, no in enumerate(todo, 1):
        try:
            case = parse(get(f"{SITE}/contentSub.ps?menuId=PS00077&cntntsNo={no}"), no)
        except Exception as err:
            case = {"no": no, "error": str(err)}
        (out / "case" / f"{no}.json").write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}", flush=True)

    (out / "fetched.json").write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d")}), encoding="utf-8")
    print("완료")


if __name__ == "__main__":
    main(sys.argv[1], refresh="--refresh" in sys.argv)
