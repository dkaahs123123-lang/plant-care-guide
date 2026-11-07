"""농사로 Open API에서 실내정원용 식물, 건조에 강한 실내식물, 약초정보(민간약초), 텃밭가꾸기, 주간농사정보를 내려받는다.

사용법:
    python -I pipeline/fetch_nongsaro.py data/raw/nongsaro [--refresh]

.env 의 NONGSARO_API_KEY (농사로 Open API 인증키)가 필요하다.
응답은 항목 이름 -> 값(원문 그대로)으로 바꿔 저장하고, 이미 받은 상세 정보는 건너뛴다 (--refresh 면 다시 받는다).
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "http://api.nongsaro.go.kr/service"
PAGE = 50
# 서비스 이름, 목록 오퍼레이션, 상세 오퍼레이션(없으면 목록에 본문이 들어 있음), 목록에 붙일 값
SERVICES = [
    ("garden", "gardenList", "gardenDtl", {}),
    ("dryGarden", "dryGardenList", "dryGardenDtl", {}),
    ("prvateTherpy", "prvateTherpyList", "prvateTherpyDtl", {}),
    ("fildMnfct", "fildMnfctList", None, {"sSeCode": "335001"}),  # 채소
    ("fildMnfct", "fildMnfctList", None, {"sSeCode": "335002"}),  # 과수
    ("fildMnfct", "fildMnfctList", None, {"sSeCode": "335003"}),  # 약초·특용
]


def load_key():
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("NONGSARO_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit(".env 에 NONGSARO_API_KEY 가 없습니다.")


def call(key, svc, op, **params):
    query = urllib.parse.urlencode({"apiKey": key, **params})
    req = urllib.request.Request(f"{API}/{svc}/{op}?{query}", headers={"User-Agent": "plant-care-guide (non-commercial)"})
    with urllib.request.urlopen(req, timeout=60) as res:
        body = res.read().decode("utf-8", "ignore")
    if "<resultCode>00</resultCode>" not in body:
        raise RuntimeError(re.sub(r"\s+", " ", body)[:300])
    time.sleep(0.3)
    return body


def fields(item_xml):
    """<이름><![CDATA[값]]></이름> 을 {이름: 값} 으로. 값은 고치지 않는다."""
    out = {}
    for name, cdata, plain in re.findall(r"<(\w+)>(?:<!\[CDATA\[(.*?)\]\]>|([^<]*))</\1>", item_xml, re.S):
        out[name] = cdata if cdata else html.unescape(plain)
    return out


def listing(key, svc, op, extra):
    items, page = [], 1
    while True:
        xml = call(key, svc, op, numOfRows=PAGE, pageNo=page, **extra)
        got = [fields(x) for x in re.findall(r"<item>(.*?)</item>", xml, re.S)]
        items += got
        total = int((re.findall(r"<totalCount>(\d+)</totalCount>", xml) or ["0"])[0])
        if not got or len(items) >= total:
            return items
        page += 1


def main(out_dir, refresh=False):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = load_key()
    for svc, op, dtl, extra in SERVICES:
        name = svc + ("_" + extra["sSeCode"] if extra else "")
        items = listing(key, svc, op, extra)
        (out / f"{name}_list.json").write_text(json.dumps(items, ensure_ascii=False, indent=0), encoding="utf-8")
        if dtl:
            path = out / f"{name}_detail.json"
            details = {} if refresh or not path.exists() else json.loads(path.read_text(encoding="utf-8"))
            for it in items:
                no = it["cntntsNo"]
                if no not in details:
                    xml = call(key, svc, dtl, cntntsNo=no)
                    details[no] = fields((re.findall(r"<item>(.*?)</item>", xml, re.S) or [""])[0])
            path.write_text(json.dumps(details, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"{name}: {len(items)}개", flush=True)

    weeks = call(key, "weekFarmInfo", "weekFarmInfoList", numOfRows=8, pageNo=1)
    (out / "weekFarmInfo_list.json").write_text(
        json.dumps([fields(x) for x in re.findall(r"<item>(.*?)</item>", weeks, re.S)], ensure_ascii=False, indent=0), encoding="utf-8")
    (out / "fetched.json").write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d"), "source": "농촌진흥청 농사로 Open API"}, ensure_ascii=False),
                                      encoding="utf-8")
    print("완료")


if __name__ == "__main__":
    main(sys.argv[1], refresh="--refresh" in sys.argv)
