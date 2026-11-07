"""NCPMS에 사진이 없는 병의 참고 사진을 위키미디어 공용(Wikimedia Commons)에서 병원체 학명으로 찾는다.

사용법:
    python -I pipeline/fetch_commons.py data/commons_wanted.json data/raw/commons

찾을 병원체 목록(data/commons_wanted.json)은 build_care.py 가 만든다.
자유 이용 허락(CC0, CC BY, CC BY-SA, 퍼블릭 도메인)이고, 제목이나 분류에 병원체 학명이 들어 있는 사진만 고른다.
지도·도표·화학 구조 그림과 논문 그림은 뺀다. 병원체마다 4장까지.
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
# 위키미디어는 연락할 수 있는 주소를 User-Agent 에 적도록 요청한다
UA = "plant-care-guide/1.0 (https://dkaahs123123-lang.github.io/plant-care-guide/; non-commercial plant care guide)"
PER = 4
LICENSE_OK = re.compile(r"^(CC0|CC BY(-SA)? [\d.]+|CC BY(-SA)?|Public domain|PD)", re.I)
SKIP_TITLE = re.compile(r"map|distribution|diagram|structure|chemical|formula|logo|range|chart|phylogen|\.svg$|\.tiff?$|\.pdf$", re.I)
# 논문 그림(도표·계통도)은 병 사진이 아니라 뺀다: 'Fmicb-10-01490-g013.jpg', 'DOI.10.5772.F3.png', 'PDB 1cgm', 'F78-07-978…'
PAPER_FIG = re.compile(r"^File:(Fmicb|Fpls|Fvets|Viruses|Plants|Ijms|Pathogens|DOI|PDB|F\d+-\d+|\d{5,}-PPT)|-g\d{3}\b", re.I)


def strip(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text or ""))).strip()


def search(name):
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f'"{name}"', "gsrnamespace": 6, "gsrlimit": 20,
        "prop": "imageinfo|categories", "iiprop": "url|mime|extmetadata", "iiurlwidth": 480, "cllimit": 20,
    }
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as res:
        data = json.loads(res.read().decode("utf-8"))
    time.sleep(1)
    pages = sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    out = []
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = strip((meta.get("LicenseShortName") or {}).get("value"))
        title = p.get("title", "")
        # 검색은 본문 어디든 맞으면 나오므로, 제목이나 분류에 학명이 있는 사진만 쓴다 (설명에만 있으면 다른 생물 사진일 수 있다)
        text = " ".join([title, " ".join(c.get("title", "") for c in p.get("categories", []))]).lower()
        if info.get("mime") not in ("image/jpeg", "image/png") or not LICENSE_OK.match(lic) or SKIP_TITLE.search(title) or PAPER_FIG.search(title):
            continue
        if name.lower() not in text:
            continue
        artist = strip((meta.get("Artist") or {}).get("value"))[:80] or "작성자 표시 없음"
        out.append({"thumb": info.get("thumburl") or info.get("url"), "page": info.get("descriptionurl"), "license": lic,
                    "license_url": (meta.get("LicenseUrl") or {}).get("value", ""), "artist": artist, "title": title})
        if len(out) >= PER:
            break
    return out


def main(wanted_path, out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "results.json"
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    wanted = json.loads(Path(wanted_path).read_text(encoding="utf-8"))
    for i, name in enumerate(wanted, 1):
        if name in results:
            continue
        try:
            results[name] = search(name)
        except Exception as e:  # 한 병원체가 실패해도 나머지는 계속 받는다
            print(f"  실패: {name} ({e})", flush=True)
            continue
        if i % 10 == 0:
            print(f"  {i}/{len(wanted)}", flush=True)
            path.write_text(json.dumps(results, ensure_ascii=False, indent=0), encoding="utf-8")
    path.write_text(json.dumps(results, ensure_ascii=False, indent=0), encoding="utf-8")
    (out / "fetched.json").write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d"), "source": "Wikimedia Commons"}, ensure_ascii=False),
                                      encoding="utf-8")
    print(f"완료: 병원체 {len(wanted)}개 중 사진을 찾은 것 {sum(1 for n in wanted if results.get(n))}개")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
