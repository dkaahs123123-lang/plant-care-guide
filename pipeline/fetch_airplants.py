"""2단계: 농촌진흥청 국립원예특작과학원 '공기정화식물 조회' API에서 전체 목록과 상세 정보를 내려받는다.

사용법:
    python -I pipeline/fetch_airplants.py data/raw/airplant

.env 의 DATA_GO_KR_KEY (공공데이터포털 일반 인증키, Decoding)가 필요하다.
응답(XML)은 그대로 저장하고, 이미 받은 상세 정보는 건너뛴다.
"""
import re
import sys
import time
import urllib.parse
import urllib.request
import json
from pathlib import Path

API = "https://apis.data.go.kr/1390804/NihhsFuriAirInfo"
PAGE = 100


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
    if "<resultCode>1</resultCode>" not in body:
        raise RuntimeError(body[:300])
    time.sleep(0.3)
    return body


def main(out_dir, refresh=False):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    (out / "view").mkdir(parents=True, exist_ok=True)
    key = load_key()

    listing = call(key, "selectPuriAirPlantList", pageNo=1, numOfRows=PAGE)
    (out / "list.xml").write_text(listing, encoding="utf-8")
    ids = re.findall(r"<idx>(\d+)</idx>", listing)
    changes = []
    print(f"목록 {len(ids)}종", flush=True)

    for i, idx in enumerate(ids, 1):
        path = out / "view" / f"{idx}.xml"
        if refresh or not path.exists():
            new = call(key, "selectPuriAirPlantView", idx=idx)
            if path.exists() and path.read_text(encoding="utf-8") != new:
                changes.append(["바뀜", idx])
            elif not path.exists():
                changes.append(["새 항목", idx])
            path.write_text(new, encoding="utf-8")
        if i % 20 == 0:
            print(f"  {i}/{len(ids)}", flush=True)

    (out / "fetched.json").write_text(
        json.dumps({"fetched": time.strftime("%Y-%m-%d"), "source": "농촌진흥청 국립원예특작과학원 공기정화식물 (공공데이터포털)"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (out / "changes.json").write_text(json.dumps(changes, ensure_ascii=False), encoding="utf-8")
    print(f"완료: 공기정화식물 {len(ids)}종, 바뀌거나 새로 생긴 항목 {len(changes)}건")


if __name__ == "__main__":
    main(sys.argv[1], refresh="--refresh" in sys.argv)
