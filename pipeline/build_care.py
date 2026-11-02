"""2·3단계: 내려받은 공식 자료를 식물별 파일(site/data/care/)로 만든다.
원문 문장은 고치지 않고 줄바꿈만 정리한다.

    병해충  NCPMS (data/raw/ncpms)      작물명 -> 학명은 data/crop_map.tsv 로 연결
    재배    정원식물정보 (data/raw/garden)  자료에 있는 학명으로 연결
    재배    공기정화식물 (data/raw/airplant) 자료 번호 -> 학명은 data/airplant_map.tsv 로 연결
    국명    산림청 표준식물종정보 (data/raw/kfs) 자료에 있는 학명으로 연결
    인터넷  NC State Extension Plant Toolbox (data/raw/ncsu) 정리된 항목 값만 한국어로 옮겨 연결
    스마트팜 농촌진흥청 스마트팜 생산성 향상 모델 (data/raw/smartfarm) 생육상태별 최적 환경 설정값
    현장사례 농사로 현장기술지원 사례 (data/raw/cases) 품목명 -> 위 자료들의 한국어 이름으로 연결
식물마다 한국어 대표 이름과 분류(실내식물, 채소 등)를 정하고, 과 이름의 한국어 표기(family_ko.json)도 만든다.
학명 표기 차이는 data/name_fixes.tsv 로 맞춘다.

사용법:
    python -I pipeline/build_care.py data site/data/care
"""
import ast
import csv
import html
import io
import json
import re
import sqlite3
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ncsu_ko  # noqa: E402

NCPMS_SOURCE = "농촌진흥청 국가농작물병해충관리시스템(NCPMS)"
NCPMS_URL = "https://ncpms.rda.go.kr"
GARDEN_SOURCE = "한국수목원정원관리원 백두대간 정원식물정보 (공공데이터포털)"
GARDEN_URL = "https://www.data.go.kr/data/15108511/openapi.do"
AIR_SOURCE = "농촌진흥청 국립원예특작과학원 공기정화식물 (공공데이터포털)"
AIR_URL = "https://www.data.go.kr/data/15063505/openapi.do"
AIR_LICENSE = "공공누리 제2유형 (출처표시, 상업적 이용금지)"
NCSU_SOURCE = "NC State Extension Gardener Plant Toolbox (미국 노스캐롤라이나 주립대)"
NCSU_SITE = "https://plants.ces.ncsu.edu"
SMART_SOURCE = "농촌진흥청 스마트팜 생산성 향상 모델 (공공데이터포털)"
SMART_URL = "https://www.data.go.kr/data/15125691/openapi.do"
# 항목 이름과 단위는 농촌진흥청 농업기술 데이터 플랫폼의 같은 표 머리글을 따랐다. 단위가 없는 항목은 원문에도 없다.
SMART_FIELDS = [
    ("accmltSolradQy", "누적일사량(J/㎠/day)"), ("opairTp", "외기기온(℃)"), ("odrOuttrn", "생산량(㎏/3.3㎡)"),
    ("deAvrgTp", "일일 평균온도(℃)"), ("dtimeAvrgTp", "주간 평균온도(℃)"), ("nightAvrgTp", "야간 평균온도(℃)"),
    ("dawnTp", "새벽온도(℃)"), ("dtimeAvrgHd", "주간 평균습도(%)"), ("remndrCo2", "잔존CO₂(ppm)"), ("grtm", "배지온도(℃)"),
    ("suplyEc", "급액 EC(dS/m)"), ("suplyPh", "급액 pH"), ("suplyCunt", "급액횟수(회)"), ("otmSuplyQy", "1회 급액량(㏄)"),
    ("deSuplyQy", "1일 급액량(㏄/day)"), ("grwtLt", "생장길이"), ("stemThck", "줄기굵기"), ("fcluHg", "화방높이"),
    ("plln", "초장"), ("flgYld", "엽수"), ("crownDnt", "관부직경"), ("day1s", "1화방 출뢰일수"),
]
CASES_SOURCE = "농촌진흥청 농사로 현장기술지원 사례"
CASES_URL = "https://www.nongsaro.go.kr/portal/ps/psz/psza/contentSub.ps?menuId=PS00077&cntntsNo="
CASES_LICENSE = "공공누리 제4유형 (출처표시, 상업적 이용금지, 변경금지)"
# 품목명 앞에 붙는 작형·재배 방식 말. 떼어 낸 뒤 작물 이름으로 찾는다 (예: 가을배추 -> 배추, 시설오이 -> 오이)
# 사례 문장 중 사람 이름(직함), 전화번호, 번지·도로명 주소가 들어 있는 줄은 싣지 않는다
PRIVATE_LINE = re.compile(
    r"\d{2,3}-\d{3,4}-\d{4}"
    r"|[가-힣]{2,4}\s?(팀장|계장|과장|소장|센터장|지도사|지도관|연구사|연구관|기술위원|위원|주무관|서기관|사무관|박사|교수|대표|이장|농가주)"
    r"|[가-힣]+길\s?\d+|[가-힣]+로\s?\d+번?길|\d+\s?번지|[가-힣]+(읍|면)\s[가-힣]+리\s?\d"
    r"|농\s?가\s?명|성\s?명\s?:|연\s?락\s?처"
)
CASE_PREFIXES = ("고랭지", "시설", "노지", "하우스", "터널", "가을", "봄", "여름", "겨울", "월동", "조생", "만생",
                 "반촉성", "촉성", "억제", "수경", "양액", "유기농", "친환경", "포트", "육묘", "재배", "작형")
KFS_SOURCE = "산림청 표준식물종정보 (공공데이터포털)"
KFS_URL = "https://www.data.go.kr/data/15092915/fileData.do"

# NCPMS 작물 코드 앞 두 글자 -> 사이트 분류
NCPMS_CATS = {"VC": "veg", "FT": "fruit", "FL": "flower", "FC": "grain", "IC": "herbal", "WP": "tree"}
# 한국어 대표 이름을 고를 때의 순서: 표준 국명 > 정원식물 > 실내식물 > 작물명
NAME_PRIORITY = ("kfs", "garden", "air", "ncpms")
ALT_FAMILIES = {"Compositae": "Asteraceae", "Leguminosae": "Fabaceae", "Cruciferae": "Brassicaceae", "Labiatae": "Lamiaceae",
                "Umbelliferae": "Apiaceae", "Gramineae": "Poaceae", "Palmae": "Arecaceae", "Guttiferae": "Clusiaceae"}
RANK_WORDS = ("var.", "subsp.", "f.")

# 공기정화식물 본문의 항목 이름 -> 화면에 쓸 이름
AIR_CARE = {"빛": "빛", "온도": "온도", "습도": "습도", "관수": "물주기", "관리": "관리", "유지관리": "관리",
            "용토": "흙", "토": "흙", "시비": "비료", "비료": "비료", "병해충": "병해충", "주의": "주의"}
AIR_INFO = {"분류": "분류", "원산지": "원산지", "일반적 특징": "특징", "형태적 특성": "생김새"}
AIR_LABEL = re.compile(r"^[-·•]?\s*(유지관리|일반적 특징|형태적 특성|빛|온도|습도|관수|관리|용토|토|시비|비료|병해충|주의|분류|원산지)\s*(?::\s*(.*))?$")
AIR_BLOCK = {"p", "li", "div", "tr", "td", "th", "br", "table", "ul", "ol", "h1", "h2", "h3", "h4"}


def clean(text):
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", str(text), flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def pylist(value):
    if not value or value == "[]":
        return []
    if isinstance(value, list):
        return value
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return []


def first_image(*lists):
    for lst in lists:
        for item in pylist(lst):
            url = item.get("image") if isinstance(item, dict) else None
            if url:
                return url.replace("http://", "https://", 1)
    return ""


def read_tsv(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            rows.append([p.strip() for p in line.split("\t")] + ["", ""])
    return rows


class Resolver:
    """학명을 WFO의 받아들여진 이름으로 바꾼다. 결과는 (키, 속, 나머지 이름, 단위) 또는 None."""

    def __init__(self, db_path, fixes_path):
        self.con = sqlite3.connect(db_path)
        self.fixes = {r[0]: r[1] for r in read_tsv(fixes_path)}

    def __call__(self, sci):
        sci = self.fixes.get(sci.strip(), sci.strip())
        con = self.con
        if " " not in sci:
            row = con.execute("SELECT id FROM taxa WHERE name = ? AND rank = 'genus'", (sci,)).fetchone()
            return (f"g:{sci}", sci, "", "genus") if row else None
        row = con.execute(
            "SELECT id, name, genus FROM taxa WHERE name = ? AND rank IN ('species','subspecies','variety','form')", (sci,)
        ).fetchone()
        if not row:
            syn = con.execute("SELECT accepted_id FROM synonyms WHERE name = ?", (sci,)).fetchone()
            if syn:
                row = con.execute("SELECT id, name, genus FROM taxa WHERE id = ?", (syn[0],)).fetchone()
        if not row:
            return None
        tid, name, genus = row
        return (tid[4:], genus, name[len(genus):].strip(), "species")

    def from_full_name(self, full):
        """'Actaea asiatica H. Hara' 처럼 저자명이 붙은 학명에서 이름만 골라 찾는다."""
        full = self.fixes.get(full.strip(), full.strip())
        toks = full.split()
        candidates = []
        for i, t in enumerate(toks):
            if t in RANK_WORDS and i + 1 < len(toks):
                candidates.append(" ".join(toks[:2] + [t, toks[i + 1]]))
        candidates.append(" ".join(toks[:2]))
        for c in candidates:
            hit = self(c)
            if hit:
                return hit, c
        return None, candidates[0]


def ncpms_disease(d, crop):
    return {
        "crop": crop,
        "name": clean(d.get("sickNameKor")),
        "eng": clean(d.get("sickNameEng")),
        "symptoms": clean(d.get("symptoms")),
        "condition": clean(d.get("developmentCondition")),
        "prevention": clean(d.get("preventionMethod")),
        "chemical": clean(d.get("chemicalPrvnbeMth")),
        "biology": clean(d.get("biologyPrvnbeMth")),
        "pathogen": "; ".join(v.get("virusName", "") for v in pylist(d.get("virusList")) if isinstance(v, dict) and v.get("virusName")),
        "img": first_image(d.get("imageList")),
    }


def ncpms_insect(d, crop):
    sci = " ".join(x for x in (clean(d.get("insectGenus")), clean(d.get("insectSpecies"))) if x)
    return {
        "crop": crop,
        "name": clean(d.get("insectSpeciesKor")),
        "sci": sci if " " in sci else "",
        "family": clean(d.get("insectFamily")),
        "damage": clean(d.get("damageInfo")),
        "form": clean(d.get("stleInfo")),
        "ecology": clean(d.get("ecologyInfo")),
        "prevention": clean(d.get("preventMethod")),
        "chemical": clean(d.get("chemicalPrvnbeMth")),
        "biology": clean(d.get("biologyPrvnbeMth")),
        "distrib": clean(d.get("distrbInfo")),
        "img": first_image(d.get("imageList"), d.get("spcsPhotoData")),
    }


class HtmlLines(HTMLParser):
    """HTML 본문을 줄 단위 글과 이미지 목록으로 바꾼다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.imgs, self.skip = [[]], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "caption"):
            self.skip += 1
        if tag == "img" and a.get("src"):
            self.imgs.append((a["src"], a.get("alt") or ""))
        if tag in AIR_BLOCK:
            self.parts.append([])

    def handle_endtag(self, tag):
        if tag in ("script", "style", "caption"):
            self.skip -= 1
        if tag in AIR_BLOCK:
            self.parts.append([])

    def handle_data(self, data):
        if not self.skip:
            self.parts[-1].append(data)

    def lines(self):
        return [s for s in (re.sub(r"\s+", " ", "".join(p)).strip() for p in self.parts) if s]


def air_item(xml):
    def field(tag):
        m = re.search(rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", xml, re.S)
        return html.unescape(m.group(1)) if m else ""

    title = re.sub(r"\s+", " ", field("title")).strip()
    quoted = re.search(r"[‘'](.+?)[’']", title)
    name = quoted.group(1) if quoted and not title.startswith(quoted.group(0)[0]) and "(" not in title.split(quoted.group(0))[0] else title.split("(")[0].strip()
    item = {"name": name, "title": title, "img": "", "effects": [], "place": "", "placeText": "", "use": "", "care": [], "info": [], "desc": ""}

    body = field("htmlContent")
    if len(body) < 200:
        text = clean(field("content"))
        item["desc"] = text[len(title):].strip() if text.startswith(title) else text
        return item

    parser = HtmlLines()
    parser.feed(body)
    imgs = [(src, alt) for src, alt in parser.imgs if src.startswith("http")]
    if imgs:
        item["img"] = imgs[0][0].replace("http://", "https://", 1)
    item["effects"] = [alt.replace(" ", "") for _, alt in imgs if re.search(r"제거량|발생량", alt)]

    current, values = None, {}
    for line in parser.lines():
        if "일러스트" in line:
            break
        if "배치 추천" in line:
            item["place"] = line.split(":", 1)[1].strip() if ":" in line else ""
            current = "placeText"
            continue
        if re.search(r"식물의 이용\s*$", line):
            current = "use"
            continue
        if re.search(r"(재배 및 유지관리|식물학적 특성|공기정화 효과)\s*$", line) or line.startswith("※"):
            current = None
            continue
        m = AIR_LABEL.match(line)
        if m and (m.group(2) is not None or m.group(1) in ("일반적 특징", "형태적 특성")):
            current = m.group(1)
            values.setdefault(current, [])
            if m.group(2):
                values[current].append(m.group(2))
            continue
        if current:
            values.setdefault(current, []).append(line)

    def join(lines):
        # 예전 본문은 단어 중간에서 줄을 바꿔 둔 곳이 있어, 한글끼리 이어지는 줄바꿈은 붙인다.
        text = lines[0]
        for nxt in lines[1:]:
            text += ("" if re.search(r"[가-힣]$", text) and re.match(r"[가-힣]", nxt) else "\n") + nxt
        return text.strip()

    joined = {k: join(v) for k, v in values.items() if v}
    item["placeText"] = joined.pop("placeText", "")
    item["use"] = joined.pop("use", "")
    for key, text in joined.items():
        if key in AIR_CARE:
            item["care"].append([AIR_CARE[key], text])
        elif key in AIR_INFO:
            item["info"].append([AIR_INFO[key], text])
    return item


def new_target():
    return {"crops": [], "ko": [], "names": {s: [] for s in NAME_PRIORITY}, "cats": set(), "kfs": [], "web": None, "smart": None, "cases": [],
            "diseases": [], "insects": [], "grow": [], "air": [], "notes": [], "air_notes": []}


def add_ncpms(data_dir, resolve, targets, meta, problems):
    raw = data_dir / "raw" / "ncpms"
    if not (raw / "fetched.json").exists():
        return None
    fetched = json.loads((raw / "fetched.json").read_text(encoding="utf-8"))["fetched"]
    by_crop = defaultdict(lambda: {"diseases": [], "insects": []})
    crop_cat = {}
    sick_list = json.loads((raw / "SVC01_list.json").read_text(encoding="utf-8"))
    insect_list = json.loads((raw / "SVC03_list.json").read_text(encoding="utf-8"))
    for s in sick_list + insect_list:
        if s.get("cropCode", "")[:2] in NCPMS_CATS:
            crop_cat[s["cropName"]] = NCPMS_CATS[s["cropCode"][:2]]
    for s in sick_list:
        f = raw / "sick" / f"{s['sickKey']}.json"
        if f.exists():
            by_crop[s["cropName"]]["diseases"].append(ncpms_disease(json.loads(f.read_text(encoding="utf-8")), s["cropName"]))
    for s in insect_list:
        f = raw / "insect" / f"{s['insectKey']}.json"
        if f.exists():
            by_crop[s["cropName"]]["insects"].append(ncpms_insect(json.loads(f.read_text(encoding="utf-8")), s["cropName"]))

    mapping = {r[0]: (r[1], r[2]) for r in read_tsv(data_dir / "crop_map.tsv")}
    linked = 0
    for crop in sorted(by_crop):
        if crop not in mapping:
            problems.append(f"[NCPMS] 연결표에 없음: {crop}")
            continue
        sci, note = mapping[crop]
        if sci == "-":
            continue
        hit = resolve(sci)
        if not hit:
            problems.append(f"[NCPMS] WFO에서 찾을 수 없는 학명: {crop} -> {sci}")
            continue
        key, genus, rest, unit = hit
        t = targets[key]
        t["crops"].append(crop)
        t["names"]["ncpms"].append(crop)
        if crop in crop_cat:
            t["cats"].add(crop_cat[crop])
        t["diseases"] += by_crop[crop]["diseases"]
        t["insects"] += by_crop[crop]["insects"]
        accepted = f"{genus} {rest}".strip()
        t["notes"].append(f"‘{crop}’ → {sci}" + (f" (현재 학명 {accepted})" if accepted != sci else "") + (f", {note}" if note else ""))
        meta[key] = (genus, rest, unit)
        linked += 1
    print(f"병해충: 작물 {len(by_crop)}종 중 {linked}종 연결")
    return fetched


def add_garden(data_dir, resolve, targets, meta, problems, families):
    raw = data_dir / "raw" / "garden"
    if not (raw / "fetched.json").exists():
        return None
    fetched = json.loads((raw / "fetched.json").read_text(encoding="utf-8"))["fetched"]
    items = json.loads((raw / "list.json").read_text(encoding="utf-8"))
    linked = 0
    for it in items:
        (hit, used) = resolve.from_full_name(it.get("scnm", ""))
        if not hit:
            problems.append(f"[정원식물] WFO에서 찾을 수 없는 학명: {it.get('krnm')} -> {it.get('scnm')}")
            continue
        key, genus, rest, unit = hit
        t = targets[key]
        t["ko"].append(clean(it.get("krnm")))
        t["names"]["garden"].append(clean(it.get("krnm")))
        t["cats"].add("garden")
        families[clean(it.get("famlNm"))] = clean(it.get("kornFamlNm"))
        t["grow"].append({
            "name": clean(it.get("krnm")),
            "sci": clean(it.get("scnm")),
            "care": clean(it.get("cltvaMngInfoCn")),
            "garden": clean(it.get("gardenAplcInfoCn")),
            "feature": clean(it.get("fturCn")),
            "bloom": clean(it.get("bloomPeriodCn")),
            "fruit": clean(it.get("frtnPeriodCn")),
            "leaf": clean(it.get("lfunPeriodCn")),
            "color": clean(it.get("flwrClorCn")),
        })
        meta[key] = (genus, rest, unit)
        linked += 1
    print(f"재배 정보(정원식물): {len(items)}종 중 {linked}종 연결")
    return fetched


def add_airplants(data_dir, resolve, targets, meta, problems):
    raw = data_dir / "raw" / "airplant"
    if not (raw / "fetched.json").exists():
        return None
    fetched = json.loads((raw / "fetched.json").read_text(encoding="utf-8"))["fetched"]
    mapping = {r[0]: (r[1], r[2]) for r in read_tsv(data_dir / "airplant_map.tsv")}
    files = sorted((raw / "view").glob("*.xml"), key=lambda p: int(p.stem))
    linked = 0
    for path in files:
        if path.stem not in mapping:
            problems.append(f"[공기정화식물] 연결표에 없음: {path.stem}")
            continue
        sci, note = mapping[path.stem]
        hit = resolve(sci)
        if not hit:
            problems.append(f"[공기정화식물] WFO에서 찾을 수 없는 학명: {path.stem} -> {sci}")
            continue
        item = air_item(path.read_text(encoding="utf-8"))
        key, genus, rest, unit = hit
        t = targets[key]
        t["ko"].append(item["name"])
        t["names"]["air"].append(item["name"])
        t["cats"].add("indoor")
        t["air"].append(item)
        accepted = f"{genus} {rest}".strip()
        t["air_notes"].append(f"‘{item['name']}’ → {sci}" + (f" (현재 학명 {accepted})" if accepted != sci else "") + (f", {note}" if note else ""))
        meta[key] = (genus, rest, unit)
        linked += 1
    print(f"재배 정보(공기정화식물): {len(files)}종 중 {linked}종 연결")
    return fetched


def ncsu_item(page):
    f = page["fields"]
    facts, notes = [], []
    for key in ("Light", "Soil Drainage", "Soil Texture", "Soil pH", "Maintenance", "Growth Rate", "Life Cycle", "Recommended Propagation Strategy"):
        if f.get(key):
            facts.append([ncsu_ko.LABELS[key], ", ".join(ncsu_ko.ko(v) for v in f[key])])
    # 한해살이로만 분류된 식물은 USDA 구역이 '그 지역에서 키울 수 있다'는 뜻이라 추위를 견딘다는 뜻으로 쓰지 않는다
    annual = set(f.get("Life Cycle", [])) == {"Annual"}
    zone = None if annual else ncsu_ko.zone_min_c(f.get("USDA Plant Hardiness Zone", []))
    if zone:
        facts.append(["견디는 추위", zone])
    elif annual:
        facts.append(["겨울나기", "한해살이라 겨울 전에 한살이를 마칩니다"])
    for dim in f.get("Dimensions", []):
        hw = ncsu_ko.feet_in_to_m(dim)
        if hw:
            facts.append(list(hw))
    if not any(k == "다 자란 폭" for k, _ in facts) and f.get("Available Space To Plant"):
        facts.append(["심을 자리 폭", ", ".join(ncsu_ko.SPACE.get(v, v) for v in f["Available Space To Plant"])])
    for key in ("Resistance To Challenges", "Problems", "Poison Severity", "Poison Part", "Poison Toxic Principle", "Country Or Region Of Origin"):
        if f.get(key):
            notes.append([ncsu_ko.LABELS[key], ", ".join(ncsu_ko.ko(v) for v in f[key])])
    pests = [v for k, vals in f.items() if k.endswith("has some common insect problems") for v in vals]
    if pests:
        notes.append(["잘 생기는 해충 (영문)", ", ".join(pests)])
    tags = " ".join(f.get("Tags", []))
    pets = [ko for tag, ko in (("#problem for cats", "고양이"), ("#problem for dogs", "개"), ("#problem for horses", "말")) if tag in tags]
    zmin = None if annual else ncsu_ko.zone_min(f.get("USDA Plant Hardiness Zone", []))
    return {"name": page["name"], "url": f"{NCSU_SITE}/plants/{page['slug']}/", "facts": facts, "notes": notes, "pets": pets,
            "zone": zmin[0] if zmin else None, "zoneC": zmin[1] if zmin else None}


def add_ncsu(data_dir, resolve, targets, meta, problems):
    raw = data_dir / "raw" / "ncsu" / "pages"
    if not raw.exists():
        return None
    linked = 0
    for path in sorted(raw.glob("*.json")):
        page = json.loads(path.read_text(encoding="utf-8"))
        if page.get("error") or not page.get("fields"):
            continue
        hit = resolve(page["name"])
        if not hit:
            continue
        key, genus, rest, unit = hit
        t = targets[key]
        if t["web"]:
            continue
        t["web"] = ncsu_item(page)
        meta[key] = (genus, rest, unit)
        linked += 1
    fetched = data_dir / "raw" / "ncsu" / "fetched.json"
    date = json.loads(fetched.read_text(encoding="utf-8"))["fetched"] if fetched.exists() else "수집 중"
    print(f"인터넷 재배 정보(NC State): 식물 {linked}종 연결")
    return date


def add_smartfarm(data_dir, resolve, targets, meta, problems):
    raw = data_dir / "raw" / "smartfarm"
    if not (raw / "grwt.json").exists():
        return None
    fetched = json.loads((raw / "fetched.json").read_text(encoding="utf-8"))["fetched"]
    for crop in json.loads((raw / "grwt.json").read_text(encoding="utf-8")).values():
        hit = resolve(crop["sci"])
        if not hit:
            problems.append(f"[스마트팜] WFO에서 찾을 수 없는 학명: {crop['name']} -> {crop['sci']}")
            continue
        key, genus, rest, unit = hit
        facilities = []
        for t in crop["tables"]:
            used = [(k, label) for k, label in SMART_FIELDS if any(str(r.get(k, "")).strip() for r in t["rows"])]
            table = {"step": t["step"], "columns": [label for _, label in used],
                     "rows": [[str(r.get(k, "")).strip() or "-" for k, _ in used] for r in t["rows"]]}
            fac = next((f for f in facilities if f["label"] == t["facility"]), None)
            if not fac:
                fac = {"label": t["facility"], "steps": []}
                facilities.append(fac)
            fac["steps"].append(table)
        targets[key]["smart"] = {"crop": crop["name"], "facilities": facilities}
        meta[key] = (genus, rest, unit)
    print("스마트팜: 완숙토마토, 딸기, 파프리카 연결")
    return fetched


def add_cases(data_dir, targets, problems):
    """현장기술지원 사례를 이미 연결된 식물에 붙인다. 품목명은 작물명·국명과 맞추고, 안 맞으면 data/case_crop_map.tsv 를 본다."""
    raw = data_dir / "raw" / "cases" / "case"
    if not raw.exists():
        return None
    by_name = {}
    for key, t in targets.items():
        for n in [*t["crops"], *t["ko"]]:
            for variant in {n, re.sub(r"\(.*?\)", "", n).strip(), *re.findall(r"\((.*?)\)", n)}:
                for part in variant.split(","):
                    by_name.setdefault(part.strip(), key)
    extra = {r[0]: r[1] for r in read_tsv(data_dir / "case_crop_map.tsv")} if (data_dir / "case_crop_map.tsv").exists() else {}

    def find(crop):
        crop = crop.strip()
        if crop in extra:
            return by_name.get(extra[crop]) if extra[crop] != "-" else None
        name = crop
        for _ in range(3):
            if name in by_name:
                return by_name[name]
            name = next((name[len(p):] for p in CASE_PREFIXES if name.startswith(p) and len(name) > len(p)), name)
        return by_name.get(name)

    linked, missing, dropped = 0, defaultdict(int), 0
    for path in raw.glob("*.json"):
        case = json.loads(path.read_text(encoding="utf-8"))
        if case.get("error") or not case.get("sections"):
            continue
        sections = []
        for head, items in case["sections"]:
            kept = [i for i in items if not PRIVATE_LINE.search(i)]
            dropped += len(items) - len(kept)
            if kept:
                sections.append([head, kept])
        case["sections"] = sections
        case["omitted"] = sum(len(i) for _, i in json.loads(path.read_text(encoding="utf-8"))["sections"]) - sum(len(i) for _, i in sections)
        key = find(case["crop"])
        if not key:
            missing[case["crop"]] += 1
            continue
        targets[key]["cases"].append(case)
        linked += 1
    (data_dir / "cases_unmatched.txt").write_text(
        "\n".join(f"{c}\t{n}" for c, n in sorted(missing.items(), key=lambda x: -x[1])), encoding="utf-8")
    print(f"현장 진단 사례: {linked}건 연결, 품목이 안 맞은 {sum(missing.values())}건은 data/cases_unmatched.txt, 개인정보가 의심되어 뺀 줄 {dropped}개")
    fetched = data_dir / "raw" / "cases" / "fetched.json"
    return json.loads(fetched.read_text(encoding="utf-8"))["fetched"] if fetched.exists() else "수집 중"


CORRECTION_PARTS = {"실내": "air", "정원": "grow", "인터넷": "web", "스마트팜": "smart", "병해충": "pests",
                    "현장사례": "cases", "산림청": "kfs"}


def apply_corrections(data_dir, resolve, targets, problems):
    """data/corrections.tsv 의 고침을 적용하고, 공개할 고친 내역을 돌려준다."""
    path = data_dir / "corrections.tsv"
    if not path.exists():
        return []
    log = []
    for target, part, item, action, reason, *_ in read_tsv(path):
        key = target if target.isdigit() or target.startswith("g:") else (resolve(target) or [None])[0]
        t = targets.get(key) if key else None
        if t is None:
            problems.append(f"[고침표] 대상을 찾을 수 없음: {target}")
            continue
        if part == "이름":
            t["override_name"] = action
        elif part == "전체" and action == "숨김":
            t["hidden"] = True
        elif part in CORRECTION_PARTS and action == "숨김":
            field = CORRECTION_PARTS[part]
            if field == "pests":
                if item == "*":
                    t["diseases"], t["insects"] = [], []
                else:
                    t["diseases"] = [d for d in t["diseases"] if d["name"] != item]
                    t["insects"] = [d for d in t["insects"] if d["name"] != item]
            elif field == "cases":
                t["cases"] = [] if item == "*" else [c for c in t["cases"] if c["no"] != item]
            elif field in ("air", "grow", "kfs"):
                t[field] = [] if item == "*" else [x for x in t[field] if x.get("name") != item]
            else:
                t[field] = None
        else:
            problems.append(f"[고침표] 알 수 없는 처리: {part} {action}")
            continue
        log.append({"target": target, "key": key, "part": part, "item": item, "action": action, "reason": reason})
    print(f"고침표: {len(log)}건 적용")
    return log


def write_climate(data_dir, out_path):
    """관측소별 겨울 최저기온 30년 평균. 20번 이상의 겨울 기록이 있는 관측소만 쓴다."""
    raw = data_dir / "raw" / "climate"
    if not (raw / "winter_min.json").exists():
        return
    names = json.loads((raw / "stations.json").read_text(encoding="utf-8"))
    mins = json.loads((raw / "winter_min.json").read_text(encoding="utf-8"))
    stations = []
    for stn, years in mins.items():
        vals = [v for v in years.values() if v is not None]
        if len(vals) >= 20:
            avg = round(sum(vals) / len(vals), 1)
            stations.append([stn, names.get(stn, stn), avg, len(vals), ncsu_ko.zone_of_c(avg)])
    stations.sort(key=lambda s: s[1])
    fetched = raw / "fetched.json"
    doc = {
        "source": "기상청 지상(종관, ASOS) 일자료 (공공데이터포털)", "url": "https://www.data.go.kr/data/15059093/openapi.do",
        "basis": "1991/92~2020/21년 겨울(11~3월) 30번 중 기록이 20번 이상인 관측소",
        "retrieved": json.loads(fetched.read_text(encoding="utf-8"))["fetched"] if fetched.exists() else "수집 중",
        "stations": stations,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"기후: 관측소 {len(stations)}곳")


def add_kfs(data_dir, resolve, targets, meta, problems, families):
    path = data_dir / "raw" / "kfs" / "standard_plants.csv"
    if not path.exists():
        return None
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig") if raw.startswith(b"\xef\xbb\xbf") else raw.decode("cp949")
    rows = list(csv.DictReader(io.StringIO(text)))
    linked, missed = 0, []
    for r in rows:
        families[r["과명"].strip()] = r["과국명"].strip()
        hit, used = resolve.from_full_name(r["학명"])
        if not hit:
            missed.append(f"{r['국명']} ({r['학명']})")
            continue
        key, genus, rest, unit = hit
        t = targets[key]
        name = r["국명"].strip()
        # 변종·품종이 종으로 합쳐진 경우(예: 남복송 -> 소나무)보다 이름이 정확히 맞는 경우를 대표 이름으로 앞에 둔다
        has_rank = lambda s: any(w in s.split() for w in RANK_WORDS)
        exact = f"{genus} {rest}".strip() == used and has_rank(used) == has_rank(r["학명"])
        if name:
            t["names"]["kfs"].insert(0 if exact else len(t["names"]["kfs"]), name)
            t["ko"].append(name)
        t["cats"].add("native")
        t["kfs"].append({
            "name": name, "sci": r["학명"].strip(), "family": r["과국명"].strip(),
            "bloom": r["개화기시작(월)"].strip(), "fruit": r["결실기(월)"].strip(),
            "protected": r["보호식물여부"].strip() == "Y", "endemic": r["특산식물여부"].strip() == "Y",
            "size": r["크기"].strip(),
        })
        meta[key] = (genus, rest, unit)
        linked += 1
    print(f"국명(산림청 표준식물종): {len(rows)}종 중 {linked}종 연결, 학명이 맞지 않은 {len(missed)}종은 data/kfs_unmatched.txt")
    (data_dir / "kfs_unmatched.txt").write_text("\n".join(missed), encoding="utf-8")
    return "2021-10-20"  # 공공데이터포털에 표시된 자료 기준일


def main(data_dir, out_dir):
    sys.stdout.reconfigure(encoding="utf-8")
    data_dir = Path(data_dir)
    resolve = Resolver(data_dir / "plants.db", data_dir / "name_fixes.tsv")
    targets, meta, problems, families = defaultdict(new_target), {}, [], {}
    ncpms_date = add_ncpms(data_dir, resolve, targets, meta, problems)
    garden_date = add_garden(data_dir, resolve, targets, meta, problems, families)
    air_date = add_airplants(data_dir, resolve, targets, meta, problems)
    kfs_date = add_kfs(data_dir, resolve, targets, meta, problems, families)
    ncsu_date = add_ncsu(data_dir, resolve, targets, meta, problems)
    smart_date = add_smartfarm(data_dir, resolve, targets, meta, problems)
    cases_date = add_cases(data_dir, targets, problems)
    corrections = apply_corrections(data_dir, resolve, targets, problems)
    for key in [k for k, t in targets.items() if t.get("hidden")]:
        del targets[key]

    out = Path(out_dir)
    # 폴더째 지우면 Windows에서 다른 프로그램이 잡고 있을 때 실패할 수 있어, 안의 파일만 지운다
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()
    index = {}
    for key, t in targets.items():
        genus, rest, unit = meta[key]
        doc = {"unit": unit}
        if t["diseases"] or t["insects"]:
            doc["pests"] = {
                "source": NCPMS_SOURCE, "url": NCPMS_URL, "retrieved": ncpms_date, "crops": t["crops"],
                "diseases": sorted(t["diseases"], key=lambda x: x["name"]),
                "insects": sorted(t["insects"], key=lambda x: x["name"]),
            }
            doc["mapping"] = "; ".join(t["notes"]) + ". 작물명과 학명은 이 사이트에서 연결했고, 학명은 WFO 목록으로 확인했습니다."
        if t["grow"]:
            doc["grow"] = {"source": GARDEN_SOURCE, "url": GARDEN_URL, "retrieved": garden_date, "items": t["grow"]}
        if t["air"]:
            doc["air"] = {
                "source": AIR_SOURCE, "url": AIR_URL, "license": AIR_LICENSE, "retrieved": air_date, "items": t["air"],
                "mapping": "; ".join(t["air_notes"]) + ". 자료와 학명은 이 사이트에서 연결했고, 학명은 WFO 목록으로 확인했습니다.",
            }
        if t["kfs"]:
            doc["kfs"] = {"source": KFS_SOURCE, "url": KFS_URL, "basis": kfs_date, "items": t["kfs"]}
        if t["web"]:
            doc["web"] = {"source": NCSU_SOURCE, "retrieved": ncsu_date, **t["web"]}
        if t["smart"]:
            doc["smart"] = {"source": SMART_SOURCE, "url": SMART_URL, "retrieved": smart_date, **t["smart"]}
        if t["cases"]:
            doc["cases"] = {"source": CASES_SOURCE, "url": CASES_URL, "license": CASES_LICENSE, "retrieved": cases_date,
                            "items": sorted(t["cases"], key=lambda c: c.get("date", ""), reverse=True)}
        (out / f"{key.replace(':', '-')}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        name = t.get("override_name") or next((n for s in NAME_PRIORITY for n in t["names"][s]), "")
        index[key] = {
            "g": genus, "r": rest, "name": name, "crops": t["crops"], "ko": list(dict.fromkeys(t["ko"])),
            "cats": sorted(t["cats"]), "nd": len(t["diseases"]), "ni": len(t["insects"]),
            "grow": bool(t["grow"] or t["air"]), "web": bool(t["web"]), "smart": bool(t["smart"]), "nc": len(t["cases"]),
        }
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # 증상으로 병해충 찾기: [식물 키, 작물명, 병/해충, 이름, 증상(병) 또는 피해(해충) 원문]
    symptoms = []
    for key, t in targets.items():
        for d in t["diseases"]:
            if d["symptoms"]:
                symptoms.append([key, d["crop"], "병", d["name"], d["symptoms"]])
        for d in t["insects"]:
            if d["damage"]:
                symptoms.append([key, d["crop"], "해충", d["name"], d["damage"]])
        # 현장 사례는 제목, 농가의견, 종합 검토의견으로 찾는다. 이름 자리에는 사례 번호를 붙여 화면에서 그 사례를 펼친다
        for c in t["cases"]:
            body = " ".join(i for h, items in c["sections"] if h.startswith(("농가의견", "종합")) for i in items)
            symptoms.append([key, c["crop"], "현장 사례", c["title"], f"{c['title']} {body}", c["no"]])
    (out.parent / "symptoms.json").write_text(json.dumps(symptoms, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_climate(data_dir, out.parent / "climate.json")
    (out.parent / "corrections.json").write_text(json.dumps(corrections, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # 국제식물명명규약이 같은 과로 인정하는 옛 이름(Compositae 등)은 현재 이름에도 같은 한국어 과명을 붙인다
    for old, new in ALT_FAMILIES.items():
        if old in families and new not in families:
            families[new] = families[old]
    (out.parent / "family_ko.json").write_text(json.dumps(families, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"식물 {len(targets)}개에 자료 연결 (병해충 {sum(1 for v in index.values() if v['nd'] or v['ni'])}, 재배 {sum(1 for v in index.values() if v['grow'])})")
    for p in problems:
        print(" -", p)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
