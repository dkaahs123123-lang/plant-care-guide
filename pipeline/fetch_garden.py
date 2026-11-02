"""2단계: 한국수목원정원관리원 '백두대간 정원식물정보' API에서 정원식물 전체를 내려받는다.

사용법:
    python -I pipeline/fetch_garden.py data/raw/garden

.env 의 DATA_GO_KR_KEY (공공데이터포털 일반 인증키, Decoding)가 필요하다.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://apis.data.go.kr/B554620/gardenPrntInfoService/getGardenPrntInfoList"
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
        data = json.loads(res.read().decode("utf-8", "ignore"))["response"]
    if data["header"]["resultCode"] not in ("0", "00"):
        raise RuntimeError(data["header"])
    return data["body"]


def main(out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = load_key()
    items, page = [], 1
    while True:
        body = call(key, page)
        batch = (body.get("items") or {}).get("item") or []
        if isinstance(batch, dict):
            batch = [batch]
        items += batch
        total = int(body.get("totalCount") or 0)
        print(f"{len(items)}/{total}", flush=True)
        if not batch or len(items) >= total:
            break
        page += 1
        time.sleep(0.3)
    (out / "list.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "fetched.json").write_text(
        json.dumps({"fetched": time.strftime("%Y-%m-%d"), "source": "한국수목원정원관리원 백두대간 정원식물정보 (공공데이터포털)"}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"완료: 정원식물 {len(items)}종")


if __name__ == "__main__":
    main(sys.argv[1])
