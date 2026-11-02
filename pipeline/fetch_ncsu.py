"""인터넷 재배 정보: 미국 노스캐롤라이나 주립대 'Extension Gardener Plant Toolbox'에서
종 단위 식물 페이지의 정리된 항목(빛, 흙, 관리 난이도 등)만 내려받는다. 설명 글은 가져오지 않는다.

사용법:
    python -I pipeline/fetch_ncsu.py data/plants.db data/raw/ncsu

- 사이트맵에서 '속-종명' 형태의 페이지 중 WFO 목록에 있는 학명만 고른다.
- 서버에 부담을 주지 않게 요청 사이에 쉬고, 이미 받은 페이지는 건너뛴다.
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_care import Resolver  # noqa: E402

SITE = "https://plants.ces.ncsu.edu"
UA = "plant-care-guide (non-commercial Korean plant guide)"
DELAY = 1.5


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.read().decode("utf-8", "ignore")
        except Exception as err:
            if getattr(err, "code", None) == 404 or attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))


def fields(page):
    out = {}
    for m in re.finditer(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", page, re.S):
        key = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(1)))).strip().rstrip(":")
        vals = [re.sub(r"\s+", " ", html.unescape(v)).strip() for v in re.split(r"<[^>]+>", m.group(2))]
        vals = [v for v in vals if v]
        if key and vals and key not in out:
            out[key] = vals
    return out


def main(db_path, out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    resolve = Resolver(db_path, Path(db_path).parent / "name_fixes.tsv")

    sitemap = get(f"{SITE}/sitemap.xml")
    slugs = re.findall(rf"<loc>{re.escape(SITE)}/plants/([^/<]+)/</loc>", sitemap)
    wanted = {}
    for slug in slugs:
        t = slug.split("-")
        if len(t) == 2:
            name = f"{t[0].capitalize()} {t[1]}"
        elif len(t) == 3 and t[1] == "x":
            name = f"{t[0].capitalize()} × {t[2]}"
        else:
            continue
        if resolve(name):
            wanted[slug] = name
    (out / "wanted.json").write_text(json.dumps(wanted, ensure_ascii=False, indent=1), encoding="utf-8")
    todo = [s for s in wanted if not (out / "pages" / f"{s}.json").exists()]
    print(f"종 단위 페이지 {len(wanted)}개 중 {len(todo)}개 받기", flush=True)

    for i, slug in enumerate(todo, 1):
        try:
            page = get(f"{SITE}/plants/{slug}/")
            data = {"slug": slug, "name": wanted[slug], "fields": fields(page)}
        except Exception as err:
            data = {"slug": slug, "name": wanted[slug], "error": str(err)}
        (out / "pages" / f"{slug}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}", flush=True)
        time.sleep(DELAY)

    (out / "fetched.json").write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d")}), encoding="utf-8")
    print("완료")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
