"""스마트팜: 농촌진흥청 '스마트팜 생산성 향상 모델' API에서 작물별 생육상태별 최적 환경 설정값을 내려받는다.

사용법:
    python -I pipeline/fetch_smartfarm.py data/raw/smartfarm

.env 의 DATA_GO_KR_KEY 가 필요하다.

코드의 뜻은 농촌진흥청 농업기술 데이터 플랫폼(adp.rda.go.kr)의 '최적 환경 서비스' 화면과 대조해 확인했다.
- 토마토: 화면의 비닐(1)/유리(2)를 화면 스크립트가 FS_BD/FS_UY 로 바꿔 보낸다.
- 파프리카: 화면의 여름(평창)/여름(철원)/겨울을 p/c/w 로 보내며, API 코드는 FS_P/FS_C/FS_W 이다.
- 딸기: API에는 FS_SI 만 자료가 있고, 단계별 건수가 화면의 '단동형' 자료와 똑같아 단동형으로 확인했다.
'일사량별' 기능은 2026-11-02 현재 API 서버 오류로 받지 못해 '생육상태별' 기능만 쓴다.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://apis.data.go.kr/1390000/SmartFarmMdl"

CROPS = {
    "tomato": {
        "name": "완숙토마토", "sci": "Solanum lycopersicum", "op": "tmtGrwtrqst",
        "facilities": [["FS_BD", "비닐 온실"], ["FS_UY", "유리 온실"]],
        "steps": [[1, "생육초기"], [21, "생육중기(9~10월)"], [22, "생육중기(11~12월)"], [23, "생육중기(1~2월)"],
                  [24, "생육중기(3~6월)"], [3, "생육말기(7~8월)"]],
    },
    "strawberry": {
        "name": "딸기", "sci": "Fragaria × ananassa", "op": "stbGrwtrqst",
        "facilities": [["FS_SI", "단동형 온실"]],
        "steps": [[1, "1화방 출뢰기"], [2, "1화방 첫 수확기"], [3, "첫수확기(12월)"], [4, "생육중기(1월)"],
                  [5, "생육중기(2월)"], [6, "생육중기(3월)"], [7, "생육말기(4~5월)"]],
    },
    "paprika": {
        "name": "파프리카", "sci": "Capsicum annuum", "op": "ppkGrwrqst",
        "facilities": [["FS_P", "여름 재배(평창)"], ["FS_C", "여름 재배(철원)"], ["FS_W", "겨울 재배"]],
        "steps": [[1, "생육초기"], [2, "생육중기(4월)"], [3, "생육중기(5~6월)"], [4, "생육중기(6~7월)"],
                  [5, "생육중기(8월)"], [6, "생육중기(9월)"], [7, "생육말기(10월~)"]],
    },
}


def load_key():
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATA_GO_KR_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit(".env 에 DATA_GO_KR_KEY 가 없습니다.")


def call(key, op, **params):
    query = urllib.parse.urlencode({"serviceKey": key, "pageSize": 100, "pageNo": 1, "returnType": "json", **params})
    req = urllib.request.Request(f"{API}/{op}?{query}", headers={"User-Agent": "plant-care-guide (non-commercial)"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                body = json.loads(res.read().decode("utf-8", "ignore"))["response"]["body"]
            items = (body.get("items") or {})
            items = items.get("item", []) if isinstance(items, dict) else items
            return items if isinstance(items, list) else [items]
        except Exception as err:
            if attempt == 3:
                raise
            print(f"  다시 시도 ({err})", flush=True)
            time.sleep(3 * (attempt + 1))


def main(out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = load_key()
    result = {}
    for crop, cfg in CROPS.items():
        tables = []
        for fcode, flabel in cfg["facilities"]:
            for scode, slabel in cfg["steps"]:
                rows = call(key, cfg["op"], fcltyTyCode=fcode, grwhStepCode=scode)
                time.sleep(0.3)
                if rows:
                    tables.append({"facility": flabel, "step": slabel, "rows": rows})
        result[crop] = {**cfg, "tables": tables}
        print(f"{cfg['name']}: 표 {len(tables)}개, 행 {sum(len(t['rows']) for t in tables)}개", flush=True)
    (out / "grwt.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "fetched.json").write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d")}), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
