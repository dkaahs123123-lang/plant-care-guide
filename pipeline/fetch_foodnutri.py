"""농촌진흥청 '국가표준식품성분' API에서 식물성 식품의 영양성분을 내려받는다.

사용법:
    python -I pipeline/fetch_foodnutri.py data/raw/foodnutri

.env 의 DATA_GO_KR_KEY (공공데이터포털 일반 인증키, Decoding)가 필요하다.
곡류(A), 감자 및 전분류(B), 두류(D), 견과 및 종실류(E), 채소류(F), 과일류(H)의 목록을 받고,
그중 '생것'(익히거나 말리지 않은 것)만 영양성분을 받아 둔다. 이미 받은 식품은 건너뛴다.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://apis.data.go.kr/1390803/AgriFood/NationStdFood1"
GROUPS = "ABDEFH"
PAGE = 20  # 이 API는 한 번에 20개까지만 준다


def load_key():
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATA_GO_KR_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit(".env 에 DATA_GO_KR_KEY 가 없습니다.")


def call(key, op, **params):
    query = urllib.parse.urlencode({"serviceKey": key, **params})
    req = urllib.request.Request(f"{API}/{op}?{query}", headers={"User-Agent": "plant-care-guide (non-commercial)"})
    with urllib.request.urlopen(req, timeout=60) as res:
        body = res.read().decode("utf-8", "ignore")
    if "<result_Msg>OK</result_Msg>" not in body:
        raise RuntimeError(body[:300])
    time.sleep(0.3)
    return body


def tag(xml, name):
    return [v.strip() for v in re.findall(rf"<{name}>(.*?)</{name}>", xml, re.S)]


def parse_detail(xml):
    """영양성분을 [분류, 성분명, 함량, 단위] 목록으로 바꾼다. 함량은 원문 글자 그대로 둔다."""
    rows = []
    for block in re.findall(r"<irdnt>(.*?)</irdnt>", xml, re.S):
        group = (tag(block, "irdnt_Se_Nm") or [""])[0]
        for t in re.findall(r"<irdnttcket>(.*?)</irdnttcket>", block, re.S):
            rows.append([group, (tag(t, "irdnt_Nm") or [""])[0], (tag(t, "cont_Info") or [""])[0], (tag(t, "irdnt_Unit_Nm") or [""])[0]])
    return rows


def main(out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = load_key()
    foods = []
    for g in GROUPS:
        page = 1
        while True:
            xml = call(key, "getKoreanFoodNationStdList1", page_No=page, Page_Size=PAGE, fd_Grupp=g)
            items = re.findall(r"<item>(.*?)</item>", xml, re.S)
            for it in items:
                foods.append({k: (tag(it, k) or [""])[0] for k in ("food_Code", "food_Grupp", "food_Nm", "food_Eng_Nm", "origin_Nm", "examin_Year")})
            total = int((tag(xml, "total_Count") or ["0"])[0])
            if page * PAGE >= total or not items:
                break
            page += 1
        print(f"식품군 {g}: 누적 {len(foods)}개", flush=True)
    (out / "list.json").write_text(json.dumps(foods, ensure_ascii=False, indent=0), encoding="utf-8")

    path = out / "details.json"
    details = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    raw = [f for f in foods if f["food_Nm"].endswith("생것")]
    for i, f in enumerate(raw, 1):
        if f["food_Code"] not in details:
            details[f["food_Code"]] = parse_detail(call(key, "getKoreanFoodNationStdIdntList1", food_Code=f["food_Code"]))
        if i % 50 == 0:
            print(f"  영양성분 {i}/{len(raw)}", flush=True)
            path.write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
    path.write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
    (out / "fetched.json").write_text(
        json.dumps({"fetched": time.strftime("%Y-%m-%d"), "source": "농촌진흥청 국립식량과학원 국가표준식품성분 DB 10.4 (공공데이터포털)"}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"완료: 식물성 식품 {len(foods)}개 중 생것 {len(raw)}개의 영양성분")


if __name__ == "__main__":
    main(sys.argv[1])
