"""공개 전 점검: 사이트 자료에 문제가 없는지 확인한다. 문제가 하나라도 있으면 종료 코드 1을 돌려준다.

사용법:
    python -I pipeline/check_site.py site

점검 항목
  1. 출처: 모든 정보 칸에 출처와 확인일(또는 기준일)이 있는가
  2. 개인정보·비밀: 사이트 파일에 전화번호, 이메일, .env 의 API 키가 없는가
  3. 연결: 목록(index, 증상 검색)이 가리키는 식물 파일이 모두 있는가
  4. 값의 범위: 기온, 추위 구역 등이 말이 되는 범위인가
  5. 오해 방지: 한해살이 식물에 추위 비교가 붙지 않았는가
  6. 크기: 한 파일이 너무 크지 않은가 (공개 호스팅 제한)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from privacy import is_private  # noqa: E402

PHONE = re.compile(r"(?<![\d.])0\d{1,2}-\d{3,4}-\d{4}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.(com|net|kr|org|co\.kr)\b")
SOURCED = {"grow": ("source", "retrieved"), "air": ("source", "retrieved"), "pests": ("source", "retrieved"),
           "web": ("source", "retrieved"), "smart": ("source", "retrieved"), "cases": ("source", "retrieved"),
           "kfs": ("source", "basis")}


def main(site):
    sys.stdout.reconfigure(encoding="utf-8")
    site = Path(site)
    problems = []
    keys = []
    env = Path(".env")
    if env.exists():
        keys = [l.split("=", 1)[1].strip() for l in env.read_text(encoding="utf-8").splitlines()
                if "=" in l and not l.startswith("#") and len(l.split("=", 1)[1].strip()) >= 20]

    # 2·6. 모든 파일: 비밀, 개인정보, 크기
    for f in site.rglob("*"):
        if not f.is_file():
            continue
        if f.stat().st_size > 20_000_000:
            problems.append(f"[크기] {f} 가 20MB를 넘음")
        if f.suffix not in (".json", ".js", ".html", ".css", ".webmanifest"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for k in keys:
            if k in text:
                problems.append(f"[비밀] {f} 에 API 키가 들어 있음")
        if f.parent.name in ("care",) or f.name in ("symptoms.json",):
            for m in PHONE.finditer(text):
                problems.append(f"[개인정보] {f.name}: 전화번호 모양 '{m.group(0)}'")
            for m in EMAIL.finditer(text):
                problems.append(f"[개인정보] {f.name}: 이메일 모양 '{m.group(0)}'")

    # 1·3·4·5. 식물별 자료
    index = json.loads((site / "data/care/index.json").read_text(encoding="utf-8"))
    for key in index:
        f = site / "data/care" / f"{key.replace(':', '-')}.json"
        if not f.exists():
            problems.append(f"[연결] 목록에 있지만 파일이 없음: {key}")
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        # 현장 진단 사례: 칸 제목과 글 모두 개인정보 기준(privacy.py)을 다시 통과해야 한다
        for case in (doc.get("cases") or {}).get("items", []):
            for head, lines in case.get("sections", []):
                for line in [head, *lines]:
                    if is_private(line):
                        problems.append(f"[개인정보] 사례 {case.get('no')}: '{line[:40]}'")
        for part, fields in SOURCED.items():
            if part in doc:
                for field in fields:
                    if not doc[part].get(field):
                        problems.append(f"[출처] {key} 의 {part} 에 {field} 가 없음")
        web = doc.get("web")
        if web and web.get("zoneC") is not None:
            if not -52 <= web["zoneC"] <= 20:  # 1a 구역(-51.1°C)이 가장 추운 구역
                problems.append(f"[범위] {key} 견디는 추위 {web['zoneC']}°C")
            if any(k == "겨울나기" for k, _ in web.get("facts", [])):
                problems.append(f"[오해] {key} 한해살이인데 추위 비교 값이 있음")
        if "pests" in doc and not (doc["pests"]["diseases"] or doc["pests"]["insects"]):
            problems.append(f"[연결] {key} 병해충 칸이 비어 있음")

    symptoms = json.loads((site / "data/symptoms.json").read_text(encoding="utf-8"))
    for row in symptoms:
        if row[0] not in index:
            problems.append(f"[연결] 증상 검색이 없는 식물을 가리킴: {row[0]} {row[3]}")
            break

    climate = site / "data/climate.json"
    if climate.exists():
        for stn in json.loads(climate.read_text(encoding="utf-8"))["stations"]:
            if not -35 <= stn[2] <= 5:
                problems.append(f"[범위] 관측소 {stn[1]} 겨울 최저기온 평균 {stn[2]}°C")

    print(f"식물 {len(index)}개, 증상 검색 {len(symptoms)}건 점검")
    if problems:
        print(f"문제 {len(problems)}건")
        for p in problems[:100]:
            print(" -", p)
        sys.exit(1)
    print("문제 없음")


if __name__ == "__main__":
    main(sys.argv[1])
