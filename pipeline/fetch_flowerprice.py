"""한국농수산식품유통공사 '화훼 경매 시세' 파일(공공데이터포털 파일데이터 15052544)을 내려받는다.

사용법:
    python -I pipeline/fetch_flowerprice.py data/raw/flowerprice

1년에 한 번 새 파일이 올라오므로, 포털의 수정일이 지난번에 받은 날과 같으면 받지 않는다.
포털이 자동입력 방지(CAPTCHA)를 요구하면 우회하지 않고 멈춘다. 그때는 사람이 포털에서 직접 받아 같은 이름으로 넣는다.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PAGE = "https://www.data.go.kr/data/15052544/fileData.do"
BASE = "https://www.data.go.kr"
UA = {"User-Agent": "plant-care-guide (non-commercial)"}


def get(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=120) as res:
        return res.read()


def main(out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    page = get(PAGE).decode("utf-8", "replace")
    modified = (re.findall(r'"dateModified":"([\d-]+)"', page) or [""])[0]
    info = out / "fetched.json"
    old = json.loads(info.read_text(encoding="utf-8")) if info.exists() else {}
    if modified and old.get("modified") == modified and (out / "flower_auction.csv").exists():
        print(f"새 파일 없음 (포털 수정일 {modified})")
        return
    m = re.search(r"fn_fileDataDown\('(\d+)',\s*'([^']+)',\s*'([^']*)',\s*'(\d+)'", page)
    if not m:
        sys.exit("내려받기 정보를 찾지 못했습니다. 포털 화면이 바뀌었는지 확인하세요.")
    pk, detail, _, sn = m.groups()
    meta = json.loads(get(f"{BASE}/tcs/dss/selectFileDataDownload.do",
                          {"publicDataDetailPk": detail, "publicDataPk": pk, "atchFileId": "", "fileDetailSn": sn, "publicDataTyCode": "PR0051"}))
    atch = meta.get("atchFileId")
    limit = json.loads(get(f"{BASE}/cmm/cmm/check-limit.json", {"atchFileId": atch, "fileDetailSn": meta.get("fileDetailSn", sn)}))
    if limit.get("needCaptcha"):
        sys.exit("포털이 자동입력 방지(CAPTCHA)를 요구해 받지 않았습니다. 포털에서 직접 받아 flower_auction.csv 로 넣어 주세요.")
    data = get(f"{BASE}/cmm/cmm/fileDownload.do?atchFileId={atch}&fileDetailSn={meta.get('fileDetailSn', sn)}&dataNm=flower")
    if not data.startswith("정산일자".encode("cp949")):
        sys.exit("받은 파일이 화훼 경매 시세 CSV가 아닙니다. 저장하지 않았습니다.")
    (out / "flower_auction.csv").write_bytes(data)
    info.write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d"), "modified": modified, "source": "한국농수산식품유통공사 화훼 경매 시세"},
                               ensure_ascii=False), encoding="utf-8")
    print(f"완료: {len(data) // 1024 // 1024}MB, 포털 수정일 {modified}")


if __name__ == "__main__":
    main(sys.argv[1])
