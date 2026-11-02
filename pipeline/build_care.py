"""2·3단계: 내려받은 공식 자료를 식물별 파일(site/data/care/)로 만든다.
원문 문장은 고치지 않고 줄바꿈만 정리한다.

    병해충  NCPMS (data/raw/ncpms)      작물명 -> 학명은 data/crop_map.tsv 로 연결
    재배    정원식물정보 (data/raw/garden)  자료에 있는 학명으로 연결
    재배    공기정화식물 (data/raw/airplant) 자료 번호 -> 학명은 data/airplant_map.tsv 로 연결
    국명    산림청 표준식물종정보 (data/raw/kfs) 자료에 있는 학명으로 연결
    인터넷  NC State Extension Plant Toolbox (data/raw/ncsu) 정리된 항목 값만 한국어로 옮겨 연결
    스마트팜 농촌진흥청 스마트팜 생산성 향상 모델 (data/raw/smartfarm) 생육상태별 최적 환경 설정값
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
import shutil
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
    return {"crops": [], "ko": [], "names": {s: [] for s in NAME_PRIORITY}, "cats": set(), "kfs": [], "web": None, "smart": None,
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
    zone = ncsu_ko.zone_min_c(f.get("USDA Plant Hardiness Zone", []))
    if zone:
        facts.append(["견디는 추위", zone])
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
    return {"name": page["name"], "url": f"{NCSU_SITE}/plants/{page['slug']}/", "facts": facts, "notes": notes, "pets": pets}


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

    out = Path(out_dir)
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
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
        (out / f"{key.replace(':', '-')}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        name = next((n for s in NAME_PRIORITY for n in t["names"][s]), "")
        index[key] = {
            "g": genus, "r": rest, "name": name, "crops": t["crops"], "ko": list(dict.fromkeys(t["ko"])),
            "cats": sorted(t["cats"]), "nd": len(t["diseases"]), "ni": len(t["insects"]),
            "grow": bool(t["grow"] or t["air"]), "web": bool(t["web"]), "smart": bool(t["smart"]),
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
    (out.parent / "symptoms.json").write_text(json.dumps(symptoms, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
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
