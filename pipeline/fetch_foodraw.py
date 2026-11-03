"""식약처 '수입식품 원료정보' API에서 식품 원료 목록 전체를 내려받는다.

사용법:
    python -I pipeline/fetch_foodraw.py data/raw/foodraw

.env 의 DATA_GO_KR_KEY (공공데이터포털 일반 인증키, Decoding)가 필요하다.
원료마다 이름, 학명, 식품 원료로 쓸 수 있는지(가능/제한/불가), 쓸 수 있는 부위가 들어 있다.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://apis.data.go.kr/1471000/IprtFoodIngdInfoService/getIprtFoodIngdInfoService"
PAGE = 100


def load_key():
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATA_GO_KR_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit(".env 에 DATA_GO_KR_KEY 가 없습니다.")


def call(key, page):
    query = urllib.parse.urlencode({"serviceKey": key, "pageNo": page, "numOfRows": PAGE, "type": "json"})
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": "plant-care-guide (non-commercial)"})
    with urllib.request.urlopen(req, timeout=60) as res:
        body = json.loads(res.read().decode("utf-8", "ignore"))
    if body.get("header", {}).get("resultCode") != "00":
        raise RuntimeError(str(body)[:300])
    time.sleep(0.3)
    return body["body"]


def main(out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = load_key()
    first = call(key, 1)
    total = int(first["totalCount"])
    items = list(first["items"])
    for page in range(2, (total + PAGE - 1) // PAGE + 1):
        items += call(key, page)["items"]
        if page % 10 == 0:
            print(f"  {len(items)}/{total}", flush=True)
    if len(items) != total:
        sys.exit(f"받은 수({len(items)})가 전체 수({total})와 달라 저장하지 않았습니다.")
    (out / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=0), encoding="utf-8")
    (out / "fetched.json").write_text(
        json.dumps({"fetched": time.strftime("%Y-%m-%d"), "source": "식품의약품안전처 수입식품 원료정보 (공공데이터포털)"}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"완료: 식품 원료 {len(items)}개")


if __name__ == "__main__":
    main(sys.argv[1])
