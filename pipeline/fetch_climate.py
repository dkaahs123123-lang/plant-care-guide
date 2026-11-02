"""우리 동네 겨울나기: 기상청 지상(ASOS) 일자료로 관측소별 '겨울 최저기온의 30년 평균'을 계산한다.

미국 농무부(USDA) 내한성 구역과 같은 방식이다. 해마다 가장 추웠던 날의 최저기온을 구하고 그 평균을 낸다.
여기서는 1991~2020년 기후평년과 같은 기간이 되도록 1991/92 ~ 2020/21년 겨울(11월~3월) 30번을 쓴다.

사용법:
    python -I pipeline/fetch_climate.py data/raw/climate

.env 의 DATA_GO_KR_KEY 가 필요하고, 공공데이터포털에서 '기상청_지상(종관, ASOS) 일자료 조회서비스'를 활용신청해야 한다.
받은 겨울별 최저기온은 그대로 저장하므로 중간에 멈춰도 다시 실행하면 이어서 받는다.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
WINTERS = range(1991, 2021)  # 1991년 11월 ~ 1992년 3월 ... 2020년 11월 ~ 2021년 3월
STATION_RANGE = range(90, 300)  # 종관기상관측(ASOS) 지점 번호가 들어 있는 범위
DELAY = 0.2


def load_key():
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATA_GO_KR_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit(".env 에 DATA_GO_KR_KEY 가 없습니다.")


def call(key, stn, start, end):
    query = urllib.parse.urlencode({
        "serviceKey": key, "pageNo": 1, "numOfRows": 999, "dataType": "JSON",
        "dataCd": "ASOS", "dateCd": "DAY", "startDt": start, "endDt": end, "stnIds": stn,
    })
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": "plant-care-guide (non-commercial)"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                data = json.loads(res.read().decode("utf-8", "ignore"))["response"]
            code = data["header"]["resultCode"]
            if code == "03":  # 자료 없음
                return []
            if code != "00":
                raise RuntimeError(data["header"])
            items = data["body"]["items"]["item"]
            time.sleep(DELAY)
            return items if isinstance(items, list) else [items]
        except Exception as err:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def main(out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = load_key()

    stations_path = out / "stations.json"
    if stations_path.exists():
        stations = json.loads(stations_path.read_text(encoding="utf-8"))
    else:
        # 지점 번호 범위를 훑어 2020/21년 겨울에 자료가 있는 관측소만 고른다
        stations = {}
        for stn in STATION_RANGE:
            items = call(key, stn, "20210101", "20210103")
            if items:
                stations[str(stn)] = items[0].get("stnNm", "")
        stations_path.write_text(json.dumps(stations, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"관측소 {len(stations)}곳", flush=True)

    mins_path = out / "winter_min.json"
    mins = json.loads(mins_path.read_text(encoding="utf-8")) if mins_path.exists() else {}
    for i, stn in enumerate(stations, 1):
        got = mins.setdefault(stn, {})
        for year in WINTERS:
            if str(year) in got:
                continue
            items = call(key, stn, f"{year}1101", f"{year + 1}0331")
            vals = [float(it["minTa"]) for it in items if str(it.get("minTa", "")).strip() not in ("", "None")]
            # 겨울 151일 중 120일 이상 기록이 있을 때만 그 해 겨울 최저기온으로 쓴다
            got[str(year)] = min(vals) if len(vals) >= 120 else None
        mins_path.write_text(json.dumps(mins, ensure_ascii=False), encoding="utf-8")
        print(f"  {i}/{len(stations)} {stations[stn]}", flush=True)

    (out / "fetched.json").write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d"), "winters": "1991/92~2020/21"}), encoding="utf-8")
    print("완료")


if __name__ == "__main__":
    main(sys.argv[1])
