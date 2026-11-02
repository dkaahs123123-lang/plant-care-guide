"""3단계: 국가농작물병해충관리시스템(NCPMS) Open API에서 작물별 병·해충 정보를 내려받는다.

사용법:
    python -I pipeline/fetch_ncpms.py data/raw/ncpms

.env 의 NCPMS_API_KEY 가 필요하다. 받은 응답은 그대로 저장하므로
중간에 멈춰도 다시 실행하면 이미 받은 것은 건너뛴다.

서비스 코드
    SVC01 작물별 병 목록      SVC05 병 상세 (sickKey)
    SVC03 작물별 해충 목록    SVC07 해충 상세 (insectKey)
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "http://ncpms.rda.go.kr/npmsAPI/service"
PAGE = 50  # API가 한 번에 최대 50건만 돌려준다
DELAY = 0.3


def load_key():
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("NCPMS_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit(".env 에 NCPMS_API_KEY 가 없습니다.")


def call(key, **params):
    query = urllib.parse.urlencode({"apiKey": key, "serviceType": "AA003", **params})
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": "plant-care-guide (non-commercial)"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                data = json.loads(res.read().decode("utf-8", "ignore"))["service"]
            if data.get("errorCode"):
                raise RuntimeError(f"{data['errorCode']} {data.get('errorMsg')}")
            time.sleep(DELAY)
            return data
        except Exception as err:
            if attempt == 3:
                raise
            print(f"  다시 시도 ({err})", flush=True)
            time.sleep(3 * (attempt + 1))


def fetch_list(key, code, out):
    path = out / f"{code}_list.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    items, start = [], 1
    while True:
        data = call(key, serviceCode=code, cropName="%", displayCount=PAGE, startPoint=start)
        page = data.get("list") or []
        items += page
        total = int(data.get("totalCount") or 0)
        print(f"{code}: {len(items)}/{total}", flush=True)
        if not page or len(items) >= total:
            break
        start += PAGE
    path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    return items


def fetch_details(key, code, param, keys, folder):
    folder.mkdir(parents=True, exist_ok=True)
    todo = [k for k in keys if not (folder / f"{k}.json").exists()]
    print(f"{code}: 상세 {len(keys)}건 중 {len(todo)}건 받기", flush=True)
    for i, k in enumerate(todo, 1):
        data = call(key, serviceCode=code, **{param: k})
        (folder / f"{k}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if i % 50 == 0:
            print(f"  {i}/{len(todo)}", flush=True)


def main(out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = load_key()

    sick = fetch_list(key, "SVC01", out)
    insect = fetch_list(key, "SVC03", out)
    fetch_details(key, "SVC05", "sickKey", sorted({s["sickKey"] for s in sick if s.get("sickKey")}), out / "sick")
    fetch_details(key, "SVC07", "insectKey", sorted({s["insectKey"] for s in insect if s.get("insectKey")}), out / "insect")

    (out / "fetched.json").write_text(
        json.dumps({"fetched": time.strftime("%Y-%m-%d"), "source": "농촌진흥청 국가농작물병해충관리시스템(NCPMS) Open API"}, ensure_ascii=False),
        encoding="utf-8",
    )
    crops = sorted({s["cropName"] for s in sick + insect if s.get("cropName")})
    print(f"완료: 병 {len(sick)}건, 해충 {len(insect)}건, 작물 {len(crops)}종")


if __name__ == "__main__":
    main(sys.argv[1])
