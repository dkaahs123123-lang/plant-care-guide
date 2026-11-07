"""매주 갱신: 공식 자료를 다시 받아 바뀐 것을 반영하고, 점검을 통과하면 공개 사이트에 올린다.

사용법 (프로젝트 폴더에서):
    python -I pipeline/weekly_update.py

- 공공기관 자료(NCPMS 병해충, 실내식물, 정원식물, 스마트팜, 현장 사례 새 글)는 매주 전부 다시 받는다.
- NC State 자료는 상대 서버 부담을 줄이려고 매주 4분의 1씩 돌아가며 다시 받는다 (4주마다 전체 갱신).
- 공개 전 점검(check_site.py)에서 문제가 나오면 공개하지 않는다.
- 기록은 logs/weekly-날짜.log 에 남는다.
- --daily 로 실행하면 도매시장 시세(최근 며칠)만 받아 사이트를 다시 만들고 올린다. 기록은 logs/daily-날짜.log
"""
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = [sys.executable, "-I"]
SITE_URL = "https://dkaahs123123-lang.github.io/plant-care-guide/"


def main(daily=False):
    today = datetime.date.today()
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log = open(log_dir / f"{'daily' if daily else 'weekly'}-{today}.log", "a", encoding="utf-8")

    def say(msg):
        line = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    def run(args, what):
        say(f"시작: {what}")
        res = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        log.write(res.stdout[-4000:] + res.stderr[-2000:])
        say(f"{'끝' if res.returncode == 0 else '실패'}: {what}")
        return res.returncode == 0

    part = today.isocalendar()[1] % 4
    steps = [
        (PY + ["pipeline/fetch_ncpms.py", "data/raw/ncpms", "--refresh"], "병해충(NCPMS)"),
        (PY + ["pipeline/fetch_airplants.py", "data/raw/airplant", "--refresh"], "실내식물"),
        (PY + ["pipeline/fetch_garden.py", "data/raw/garden"], "정원식물"),
        (PY + ["pipeline/fetch_smartfarm.py", "data/raw/smartfarm"], "스마트팜"),
        (PY + ["pipeline/fetch_nongsaro_cases.py", "data/raw/cases", "--refresh"], "현장 진단 사례(새 글)"),
        (PY + ["pipeline/fetch_ncsu.py", "data/plants.db", "data/raw/ncsu", f"--part={part}/4"], f"NC State ({part + 1}/4 묶음)"),
        (PY + ["pipeline/fetch_nongsaro.py", "data/raw/nongsaro"], "농사로(실내정원·건조 실내식물·민간약초·텃밭·주간농사정보)"),
        (PY + ["pipeline/fetch_commons.py", "data/commons_wanted.json", "data/raw/commons"], "병해충 참고 사진(위키미디어 공용)"),
        (PY + ["pipeline/fetch_flowerprice.py", "data/raw/flowerprice"], "화훼 경매 시세(새 파일이 있을 때만)"),
        (PY + ["pipeline/fetch_foodraw.py", "data/raw/foodraw"], "식품 원료(식약처)"),
        (PY + ["pipeline/fetch_foodnutri.py", "data/raw/foodnutri"], "영양성분(국가표준식품성분)"),
        (PY + ["pipeline/fetch_market.py", "data/raw/market", "--days=10"], "도매시장 시세"),
    ]
    if daily:
        # 정산이 늦게 들어오는 날이 있어 최근 5일을 다시 받는다
        steps = [(PY + ["pipeline/fetch_market.py", "data/raw/market", "--days=5"], "도매시장 시세(매일)")]
    failed = [what for args, what in steps if not run(args, what)]
    if failed:
        say(f"자료를 받지 못한 곳: {', '.join(failed)} (예전 자료로 계속합니다)")

    for name in ("ncpms", "airplant"):
        f = ROOT / "data/raw" / name / "changes.json"
        if f.exists():
            changes = json.loads(f.read_text(encoding="utf-8"))
            say(f"{name}: 바뀌거나 새로 생긴 항목 {len(changes)}건")

    if not run(PY + ["pipeline/build_care.py", "data", "site/data/care"], "사이트 파일 만들기"):
        say("사이트 파일을 만들지 못해 공개하지 않았습니다.")
        return 1
    if not run(PY + ["pipeline/check_site.py", "site"], "공개 전 점검"):
        say("점검에서 문제가 나와 공개하지 않았습니다. 기록을 확인하세요.")
        return 1

    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    git("add", "-A")
    if git("diff", "--cached", "--quiet").returncode == 0:
        say("바뀐 내용이 없어 공개 사이트는 그대로 둡니다.")
        return 0
    git("commit", "-m", f"{'매일 시세' if daily else '주간 자료'} 갱신 {today}")
    push = git("push", "origin", "main")
    split = git("subtree", "split", "--prefix", "site", "main").stdout.strip()
    pages = git("push", "-f", "origin", f"{split}:gh-pages")
    if push.returncode or pages.returncode:
        say("GitHub에 올리지 못했습니다: " + (push.stderr + pages.stderr)[-500:])
        return 1
    say(f"공개 사이트를 갱신했습니다: {SITE_URL}")
    return 0


if __name__ == "__main__":
    sys.exit(main(daily="--daily" in sys.argv))
