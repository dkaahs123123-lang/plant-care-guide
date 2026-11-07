"""한국농수산식품유통공사 '전국 공영도매시장 정산정보'에서 날마다 채소·과일 경매 정산 가격을 받는다.

사용법:
    python -I pipeline/fetch_market.py data/raw/market [--days=60]

.env 의 DATA_GO_KR_KEY 가 필요하다 (공공데이터포털 활용신청: 정산정보 15141809, 표준코드 15141818).
하루치를 data/raw/market/YYYY-MM-DD.json 으로 저장한다. 한 줄 = 품목·품종·시장·등급·단위별 묶음:
    [대분류, 품목(중분류), 품종(소분류), 시장, 등급, 단위, 총가격 합, 총물량 합, 단위당 가격 10% 지점, 90% 지점(거래량 기준), 거래 건수, 가장 많은 산지,
     많이 쓴 포장 [[한 포장의 양, 포장 이름, 건수], ...]]
단위당 가격은 상자 크기(예: 19kg 상자)가 달라도 비교할 수 있게 1kg(또는 1개·1단)당으로 바꾼 값이다.
이미 받은 날은 건너뛰되, 정산이 늦게 들어올 수 있어 최근 3일은 다시 받는다.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

API = "https://apis.data.go.kr/B552845"
PAGE = 1000


def load_key():
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATA_GO_KR_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    sys.exit(".env 에 DATA_GO_KR_KEY 가 없습니다.")


def call(key, path, **params):
    query = urllib.parse.urlencode({"serviceKey": key, "returnType": "json", **params})
    req = urllib.request.Request(f"{API}/{path}?{query}", headers={"User-Agent": "plant-care-guide (non-commercial)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                body = json.loads(res.read().decode("utf-8"))["response"]["body"]
            time.sleep(0.1)
            return body
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def weighted_pct(points, q):
    """(가격, 물량) 목록에서 물량 기준 q 위치의 가격 (q=0.1 이면 거래량의 아래 10% 지점)"""
    points = sorted(points)
    total = sum(w for _, w in points)
    acc = 0.0
    for price, w in points:
        acc += w
        if acc >= total * q:
            return price
    return points[-1][0] if points else 0


def fetch_market_day(key, day, code):
    rows, page = [], 1
    while True:
        body = call(key, "katSale/trades", pageNo=page, numOfRows=PAGE, **{"cond[trd_clcln_ymd::EQ]": day, "cond[whsl_mrkt_cd::EQ]": code})
        items = (body.get("items") or {}).get("item") or []
        rows += items
        if page * PAGE >= int(body.get("totalCount") or 0) or not items:
            return rows
        page += 1


def fetch_day(key, day, markets):
    # 거래 건마다 1단위(1kg 등)당 평균가와 물량을 모아, 묶음마다 거래량 기준 가운데 80% 가격 범위(10%~90% 지점)를 낸다.
    # 맨 끝 값(최저가·최고가)은 포장이 특이한 몇 건 때문에 튀는 일이 많아(배추 1kg 18,333원 등) 쓰지 않는다
    groups = defaultdict(lambda: [0.0, 0.0, [], 0, Counter(), Counter()])
    with ThreadPoolExecutor(4) as pool:
        for items in pool.map(lambda code: fetch_market_day(key, day, code), markets):
            for it in items:
                qty, total, tot_qty = num(it.get("unit_qty")), num(it.get("totprc")), num(it.get("unit_tot_qty"))
                if qty <= 0 or tot_qty <= 0 or total <= 0:
                    continue
                txt = lambda k: (it.get(k) or "").strip()  # 빈 칸(null)이 오는 줄이 있다
                g = groups[(txt("gds_lclsf_nm"), txt("gds_mclsf_nm"), txt("gds_sclsf_nm"), txt("whsl_mrkt_nm"), txt("grd_nm"), txt("unit_nm"))]
                g[0] += total
                g[1] += tot_qty
                g[2].append((total / tot_qty, tot_qty))
                g[3] += 1
                origin = (it.get("plor_nm") or "").split()
                if origin:
                    g[4][origin[0]] += tot_qty
                # 포장 단위(예: 10kg 상자)별 거래 건수. 품목마다 가장 많이 쓰는 포장으로 가격을 보여 줄 때 쓴다
                pkg = txt("pkg_nm")
                g[5][(round(qty, 2), "" if pkg in ("", ".") else pkg)] += 1
    return [[*k, round(g[0]), round(g[1], 1), round(weighted_pct(g[2], 0.1)), round(weighted_pct(g[2], 0.9)), g[3],
             g[4].most_common(1)[0][0] if g[4] else "", [[q, pk, n] for (q, pk), n in g[5].most_common(3)]] for k, g in groups.items()]


def main(out_dir, days=60):
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    key = load_key()
    markets = [m["whsl_mrkt_cd"] for m in call(key, "katCode/wholesaleMarkets", pageNo=1, numOfRows=200)["items"]["item"]]
    today = date.today()
    got = 0
    for i in range(1, days + 1):
        day = (today - timedelta(days=i)).isoformat()
        path = out / f"{day}.json"
        if path.exists() and i > 3:
            continue
        rows = fetch_day(key, day, markets)
        path.write_text(json.dumps({"date": day, "rows": rows}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        got += 1
        print(f"  {day}: 묶음 {len(rows)}개", flush=True)
    (out / "fetched.json").write_text(json.dumps({"fetched": today.isoformat(), "source": "한국농수산식품유통공사 전국 공영도매시장 정산정보"},
                                                 ensure_ascii=False), encoding="utf-8")
    print(f"완료: {got}일치 받음")


if __name__ == "__main__":
    arg = next((a for a in sys.argv[2:] if a.startswith("--days=")), "--days=60")
    main(sys.argv[1], int(arg.split("=")[1]))
