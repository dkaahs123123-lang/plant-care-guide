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
from privacy import is_private  # noqa: E402

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
FOODRAW_SOURCE = "식품의약품안전처 수입식품 원료정보 (공공데이터포털)"
FOODRAW_URL = "https://www.data.go.kr/data/15111777/openapi.do"
NUTRI_SOURCE = "농촌진흥청 국립식량과학원 국가표준식품성분 DB 10.4 (공공데이터포털)"
NUTRI_URL = "https://www.data.go.kr/data/15143598/openapi.do"
NUTRI_LICENSE = "공공누리 제4유형 (출처표시, 상업적 이용금지, 변경금지)"
CASES_SOURCE = "농촌진흥청 농사로 현장기술지원 사례"
CASES_URL = "https://www.nongsaro.go.kr/portal/ps/psz/psza/contentSub.ps?menuId=PS00077&cntntsNo="
CASES_LICENSE = "공공누리 제4유형 (출처표시, 상업적 이용금지, 변경금지)"
# 품목명 앞에 붙는 작형·재배 방식 말. 떼어 낸 뒤 작물 이름으로 찾는다 (예: 가을배추 -> 배추, 시설오이 -> 오이)
# 사례의 '재배작물 : 토마토' 같은 줄. 값이 사례 품목과 다르면 원문에 다른 사례 내용이 섞인 것이다
CROP_LINE = re.compile(r"^\s*(?:재\s*배\s*)?작\s*물\s*명?\s*[:：]\s*(.+)")
FARM_HEADS = ("경종개요", "영농현황", "재배현황", "일반현황", "농가현황")
CASE_PREFIXES = ("고랭지", "시설", "노지", "하우스", "터널", "가을", "봄", "여름", "겨울", "월동", "조생", "만생",
                 "반촉성", "촉성", "억제", "수경", "양액", "유기농", "친환경", "포트", "육묘", "재배", "작형")
KFS_SOURCE = "산림청 표준식물종정보 (공공데이터포털)"
KFS_URL = "https://www.data.go.kr/data/15092915/fileData.do"

# NCPMS 작물 코드 앞 두 글자 -> 사이트 분류
NCPMS_CATS = {"VC": "veg", "FT": "fruit", "FL": "flower", "FC": "grain", "IC": "herbal", "WP": "tree"}
# 한국어 대표 이름을 고를 때의 순서: 표준 국명 > 정원식물 > 실내식물 > 작물명
# kfs_loose: 변종·품종이 종으로 합쳐져 들어온 국명(예: 보은대추나무 -> 대추나무 종). 대표 이름으로는 마지막에만 쓴다
# 농사로(ns) 이름은 식약처 이름 뒤에 둔다. 농사로 실내식물 이름에는 '금목서', '황금세덤'처럼 품종·유통명이 종 이름으로 적힌 것이 있다
NAME_PRIORITY = ("kfs", "garden", "air", "ncpms", "cases", "kfs_loose", "food", "food_syn", "ns")
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


# 병해충 사진: 묶음마다 [묶음 이름, [[사진 주소, 설명], ...]]. 쪽이 무거워지지 않게 묶음마다 앞의 12장만 싣는다
PHOTO_LIMIT = 12


def ncpms_photos(groups):
    out = []
    for title, lst, url_key, caption_keys in groups:
        photos = []
        for item in pylist(lst):
            url = item.get(url_key) if isinstance(item, dict) else None
            if url and len(photos) < PHOTO_LIMIT:
                caption = " · ".join(dict.fromkeys(clean(str(item.get(k))) for k in caption_keys if clean(str(item.get(k) or ""))))
                photos.append([url.replace("http://", "https://", 1), caption])
        if photos:
            out.append([title, photos, len(pylist(lst))])
    return out


def read_tsv(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            rows.append([p.strip() for p in line.split("\t")] + ["", ""])
    return rows


def author_key(author):
    """저자명 비교용: 'Siebold & Zucc.' 와 'Siebold&Zucc' 를 같게 본다."""
    return re.sub(r"[\s.]", "", author or "").lower()


def author_names(author):
    """저자명에서 성만 모은다: '(Regel) H. Hara' -> {'regel', 'hara'}"""
    return {w.lower() for w in re.findall(r"[A-Za-z][a-z]{2,}", author or "") if w not in ("ex", "and")}


class Resolver:
    """학명을 WFO의 받아들여진 이름으로 바꾼다. 결과는 (키, 속, 나머지 이름, 단위) 또는 None."""

    def __init__(self, db_path, fixes_path):
        self.con = sqlite3.connect(db_path)
        self.fixes = {r[0]: r[1] for r in read_tsv(fixes_path)}

    def __call__(self, sci, author=""):
        fixed = self.fixes.get(sci.strip())
        sci = fixed or sci.strip()
        con = self.con
        if " " not in sci:
            row = con.execute("SELECT id FROM taxa WHERE name = ? AND rank = 'genus'", (sci,)).fetchone()
            return (f"g:{sci}", sci, "", "genus") if row else None
        row = con.execute(
            "SELECT id, name, genus, author FROM taxa WHERE name = ? AND rank IN ('species','subspecies','variety','form')", (sci,)
        ).fetchone()
        # 같은 학명을 다른 저자가 다른 식물에 붙인 경우(예: Scirpus mucronatus L. / Pollich)가 있어 저자명이 맞는 이명을 고른다
        syns = con.execute("SELECT accepted_id, author FROM synonyms WHERE name = ?", (sci,)).fetchall()
        want = author_key(author) if not fixed else ""
        same = [a for a, au in syns if want and author_key(au) == want]
        if len({a for a, au in syns if want and author_names(au) == author_names(author)}) > 1:
            same = []  # 같은 저자의 이명이 서로 다른 식물로 이어지면 고를 근거가 없어 예전처럼 첫 번째를 쓴다
        # 'Maxim.' 과 'Maxim. ex Regel' 처럼 표기만 다른 저자는 같은 이름으로 본다
        if same and not (row and author_names(row[3]) and (author_names(row[3]) <= author_names(author)
                                                          or author_names(author) <= author_names(row[3]))):
            row = None
        if not row and syns:
            row = con.execute("SELECT id, name, genus, author FROM taxa WHERE id = ?", ((same or [syns[0][0]])[0],)).fetchone()
        if not row:
            return None
        tid, name, genus, _ = row
        return (tid[4:], genus, name[len(genus):].strip(), "species")

    def from_full_name(self, full):
        """'Actaea asiatica H. Hara' 처럼 저자명이 붙은 학명에서 이름만 골라 찾는다."""
        full = self.fixes.get(full.strip(), full.strip())
        toks = full.split()
        ranks = [i for i, t in enumerate(toks) if t in RANK_WORDS and i + 1 < len(toks)]
        candidates = []
        for n, i in enumerate(ranks):
            end = ranks[n + 1] if n + 1 < len(ranks) else len(toks)
            candidates.append((" ".join(toks[:2] + [toks[i], toks[i + 1]]), " ".join(toks[i + 2:end])))
        candidates.append((" ".join(toks[:2]), " ".join(toks[2:ranks[0] if ranks else len(toks)])))
        for c, author in candidates:
            hit = self(c, author)
            if hit:
                return hit, c
        return None, candidates[0][0]


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
        "photos": ncpms_photos([("증상 사진", d.get("imageList"), "image", ("imageTitle", "iemSpchcknNm")),
                                ("병원체 사진", d.get("virusImgList"), "image", ("imageTitle",))]),
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
        "photos": ncpms_photos([("피해 사진", d.get("imageList"), "image", ("imageTitle", "iemSpchcknCodeNm")),
                                ("해충 사진", d.get("spcsPhotoData"), "image", ("priyClNm", "photoSj")),
                                ("천적 곤충", d.get("enemyInsectList"), "enemyImage", ("enemyInsectSpeciesKor", "enemyInsectFamily"))]),
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
            "diseases": [], "insects": [], "grow": [], "air": [], "notes": [], "air_notes": [], "food": [], "nutri": [], "food_ko": [],
            "ns": {"garden": [], "dry": [], "herb": [], "fild": []}}


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
    for key in ("Resistance To Challenges", "Problems"):
        if f.get(key):
            notes.append([ncsu_ko.LABELS[key], ", ".join(ncsu_ko.ko(v) for v in f[key])])
    # 독성은 '쓰임과 효능' 칸의 조심할 점으로 모은다. 옮기지 못한 값이 있으면 칸 이름에 (영문)을 붙인다
    caution = []
    for key in ("Poison Severity", "Poison Part"):
        if f.get(key):
            caution.append([ncsu_ko.LABELS[key], ", ".join(ncsu_ko.ko(v) for v in f[key])])
    if f.get("Poison Toxic Principle"):
        got = [ncsu_ko.toxin(v) for v in f["Poison Toxic Principle"]]
        label = ncsu_ko.LABELS["Poison Toxic Principle"] + ("" if all(ok for _, ok in got) else " (영문)")
        caution.append([label, ", ".join(v for v, _ in got)])
    if "Yes" in f.get("Causes Contact Dermatitis", []):
        caution.append(["만졌을 때", "피부에 염증이 생길 수 있습니다"])
    if f.get("Country Or Region Of Origin"):
        got = [(ncsu_ko.origin(v), v) for v in f["Country Or Region Of Origin"]]
        label = ncsu_ko.LABELS["Country Or Region Of Origin"] + ("" if all(ko for ko, _ in got) else " (영문)")
        notes.append([label, ", ".join(ko or v for ko, v in got)])
    pests = [v for k, vals in f.items() if k.endswith("has some common insect problems") for v in vals]
    if pests:
        got = [ncsu_ko.pest(v) for v in pests]
        label = "잘 생기는 해충" + ("" if all(ok for _, ok in got) else " (영문)")
        notes.append([label, ", ".join(dict.fromkeys(v for v, _ in got))])
    tags = " ".join(f.get("Tags", []))
    tag_list = [t.strip().lower() for t in tags.split("#") if t.strip()]
    pets = [ko for tag, ko in (("#problem for cats", "고양이"), ("#problem for dogs", "개"), ("#problem for horses", "말")) if tag in tags]
    if not caution and any(t.startswith("poisonous") for t in tag_list):
        caution.append(["독성", "독이 있다고 표시되어 있습니다 (정도와 부위는 원문 참고)"])
    attracts = [ncsu_ko.ATTRACTS.get(v, v) for v in f.get("Attracts", [])]
    if "butterfly caterpillar host" in tag_list:
        attracts.append("나비 애벌레 (잎을 먹고 자람)")
    edible = [ncsu_ko.EDIBLE_TAGS[t] for t in tag_list if t in ncsu_ko.EDIBLE_TAGS]
    uses = {}
    if attracts:
        uses["attracts"] = list(dict.fromkeys(attracts))
    if edible:
        uses["edible"] = list(dict.fromkeys(p for p in edible if p))
    if caution or pets:
        uses["caution"] = caution
        uses["pets"] = pets
    zmin = None if annual else ncsu_ko.zone_min(f.get("USDA Plant Hardiness Zone", []))
    return {"name": page["name"], "url": f"{NCSU_SITE}/plants/{page['slug']}/", "facts": facts, "notes": notes, "uses": uses,
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


def add_cases(data_dir, targets, problems, resolve, meta):
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
            target = extra[crop]
            if target == "-":
                return None
            if re.search(r"[A-Za-z]", target):  # 학명으로 적은 경우
                hit = resolve(target)
                if not hit:
                    problems.append(f"[사례] 연결표의 학명을 찾을 수 없음: {crop} -> {target}")
                    return None
                key, genus, rest, unit = hit
                meta.setdefault(key, (genus, rest, unit))
                if crop not in targets[key]["names"]["cases"]:
                    targets[key]["names"]["cases"].append(crop)
                    targets[key]["ko"].append(crop)
                return key
            return by_name.get(target)
        name = crop
        for _ in range(3):
            if name in by_name:
                return by_name[name]
            name = next((name[len(p):] for p in CASE_PREFIXES if name.startswith(p) and len(name) > len(p)), name)
        return by_name.get(name)

    case_fix = {r[0]: r[1:] for r in read_tsv(data_dir / "case_fix.tsv")} if (data_dir / "case_fix.tsv").exists() else {}

    def case_fix_keys(case):
        target = case_fix[case["no"]][0]
        if target == "=":
            key = find(case["crop"])
            return [key] if key else []
        keys = []
        for sci in filter(None, (t.strip() for t in target.split(";"))):
            if sci == "-":
                continue
            hit = resolve(sci)
            if not hit:
                problems.append(f"[사례] case_fix.tsv 의 학명을 찾을 수 없음: {case['no']} -> {sci}")
                continue
            meta.setdefault(hit[0], hit[1:])
            keys.append(hit[0])
        return keys

    def crop_keys(value):
        """'가지, 토마토(품종 : 대프니스)' 같은 값에서 도감 식물들을 찾는다. 품종 이름 등 모르는 이름은 건너뛴다."""
        keys = set()
        for part in re.split(r"[,·/및]", re.sub(r"\(.*?\)|\(.*$|\[.*?\]", "", value)):
            part = part.strip()
            for _ in range(3):
                if len(part) >= 2 and part in by_name:
                    keys.add(by_name[part])
                    break
                part = next((part[len(p):] for p in CASE_PREFIXES if part.startswith(p) and len(part) > len(p)), part)
        return keys

    linked, missing, dropped, linked_pairs, mixed_cases = 0, defaultdict(int), 0, defaultdict(int), []
    for path in raw.glob("*.json"):
        case = json.loads(path.read_text(encoding="utf-8"))
        if case.get("error") or not case.get("sections"):
            continue
        sections = []
        for head, items in case["sections"]:
            kept = [i for i in items if not is_private(i)]
            dropped += len(items) - len(kept)
            if is_private(head):
                # 칸 제목에 출장자·농가 이름이 들어간 경우: 출장자 칸은 통째로 빼고, 농가별 칸은 이름 없는 제목으로 싣는다
                if re.search(r"출\s?장\s?자|보\s?고\s?자|입\s?회\s?자", head):
                    dropped += len(kept)
                    continue
                head = "농가별 조사 내용"
            if kept:
                sections.append([head, kept])
        # 개인정보 때문에 뺀 줄 수(다른 작물이 섞여 뺀 부분은 따로 안내한다)
        case["omitted"] = sum(len(i) for _, i in case["sections"]) - sum(len(i) for _, i in sections)
        case["sections"] = sections
        keys = case_fix_keys(case) if case["no"] in case_fix else [k for k in [find(case["crop"])] if k]
        if not keys:
            missing[case["crop"]] += 1
            continue
        if case["no"] in case_fix and len(case_fix[case["no"]]) > 1:
            case["note"] = case_fix[case["no"]][1]
        key = keys[0]
        # 원문에 다른 사례의 작물 정보가 잘못 섞여 들어간 경우(예: 배추 사례에 '재배작물 : 토마토')를 찾아 그 부분을 뺀다.
        # 품종 이름이나 '논벼/벼' 같은 다른 표기는 넘기고, 도감에 있는 '다른 식물' 이름이 적힌 경우만 본다
        title = case["title"].replace(" ", "")
        names_of = lambda k: {w.replace(" ", "") for w in [*targets[k]["crops"], *targets[k]["ko"]] if len(w) >= 2}
        mixed, cleaned = [], []
        for head, items in case["sections"]:
            keep = []
            for line in items:
                m = CROP_LINE.match(line)
                found = crop_keys(m.group(1)) if m else set()
                value = m.group(1).replace(" ", "") if m else ""
                # 적힌 작물 중에 이 사례 품목이 하나도 없고, 제목에도 그 작물이 없을 때만 섞인 것으로 본다
                same_genus = any(meta.get(k, ("",))[0] == meta.get(o, ("?",))[0] for k in found for o in keys)  # 호박(속) - 쥬키니호박
                own_named = any(w in value for o in keys for w in names_of(o) | {case["crop"]})
                other_in_title = any(w in title for k in found for w in names_of(k))
                if found and not found & set(keys) and not same_genus and not own_named and not other_in_title:
                    mixed.append(m.group(1).strip())
                    if head.replace(" ", "").startswith(FARM_HEADS):
                        keep = None  # 작물 개요 칸은 면적·시기도 그 작물 것이라 칸째 뺀다
                        break
                    continue
                keep.append(line)
            if keep:
                cleaned.append([head, keep])
        if mixed:
            case["mixed"] = mixed
            case["sections"] = cleaned
            mixed_cases.append(f"{case['no']}	{case['crop']}	{case['title']}	다른 작물: {', '.join(mixed)}")

        for k in keys:
            targets[k]["cases"].append(case)
            linked_pairs[(case["crop"], k)] += 1
        linked += 1
    # 어떤 품목이 어느 식물에 붙었는지 사람이 검토할 수 있게 남긴다
    (data_dir / "cases_linked.txt").write_text(
        "\n".join(f"{crop}\t{targets[k]['names']['kfs'][:1] or targets[k]['crops'][:1] or targets[k]['ko'][:1]}\t{meta.get(k, ('', ''))[0]} {meta.get(k, ('', ''))[1]}\t{n}"
                  for (crop, k), n in sorted(linked_pairs.items(), key=lambda x: -x[1])), encoding="utf-8")
    (data_dir / "cases_mixed.txt").write_text("\n".join(sorted(mixed_cases)), encoding="utf-8")
    (data_dir / "cases_unmatched.txt").write_text(
        "\n".join(f"{c}\t{n}" for c, n in sorted(missing.items(), key=lambda x: -x[1])), encoding="utf-8")
    print(f"현장 진단 사례: {linked}건 연결, 품목이 안 맞은 {sum(missing.values())}건은 data/cases_unmatched.txt, 개인정보가 의심되어 뺀 줄 {dropped}개, 다른 작물 정보가 섞인 사례 {len(mixed_cases)}건은 data/cases_mixed.txt")
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
        elif part == "산림청" and action.startswith("크기:"):
            hit = [x for x in t["kfs"] if x.get("name") == item]
            if not hit:
                problems.append(f"[고침표] 산림청 항목을 찾을 수 없음: {target} {item}")
                continue
            for x in hit:
                x["size"] = action[len("크기:"):].strip()
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


def foodraw_names(sci):
    """'Malus pumila Mill. / Malus domestica Bor' 처럼 여러 학명이 붙은 칸을 하나씩 나눈다. 한글 설명이 섞인 조각은 뺀다."""
    for piece in re.split(r"\s*/\s*|\s+또는\s+", sci or ""):
        piece = piece.replace("ssp.", "subsp.").strip()
        if re.match(r"[A-Z][a-z]+ [a-z]", piece) and not re.search(r"[가-힣]", piece):
            yield piece


def add_foodraw(data_dir, resolve, targets, problems):
    """식약처 식품 원료 목록을 학명으로 도감의 식물에 붙인다. 이름 -> 식물 키 묶음(영양성분 연결에 씀)을 돌려준다."""
    raw = data_dir / "raw" / "foodraw"
    names = {"main": defaultdict(set), "other": defaultdict(set)}
    if not (raw / "items.json").exists():
        return None, names
    fetched = json.loads((raw / "fetched.json").read_text(encoding="utf-8"))["fetched"]
    linked = 0
    for it in json.loads((raw / "items.json").read_text(encoding="utf-8")):
        if it.get("ANML_INFO") != "식물성":
            continue
        keys = {}  # 식물 키 -> 식약처 학명이 그 식물과 같은 종 이름인지 (변종 차이는 같다고 보고, 옛 학명으로 이어진 것은 False)
        # 학명 칸에 이름이 여럿이면, 처음 찾아지는 이름과 속(屬)이 같은 이름만 쓴다. 다른 속의 이름은 다른 식물이 잘못
        # 적힌 경우가 있다 (예: 주목 'Taxus cuspidata / Hornemannia bicolor', 가시비름 'Amaranthus spinosus / Rubus schizostylus')
        ref = None
        for name in foodraw_names(it.get("SCNNM_NM")):
            hit, used = resolve.from_full_name(name)
            if not hit:
                continue
            ref = ref or name.split()[0]
            # 도감에 이미 있는 식물에만 붙인다. 식품 원료 이름만으로 새 식물을 만들지 않는다
            if name.split()[0] == ref and hit[0] in targets:
                keys[hit[0]] = keys.get(hit[0], False) or used.split()[:2] == f"{hit[1]} {hit[2]}".split()[:2]
        dash = lambda v: "" if clean(v) in ("", "-") else clean(v)
        for key, exact in keys.items():
            # 한국어 이름이 없는 식물은 식약처 원료 이름을 대표 이름으로 쓸 수 있게 한다 (NAME_PRIORITY 맨 끝).
            # 영어 이름이거나, 한 원료에 여러 식물이 묶여 있으면(예: 설탕단풍 = 두 종) 쓰지 않는다
            # 옛 학명으로만 이어진 원료 이름은 다른 이름이 하나도 없을 때만 쓴다 (food_syn, 맨 끝)
            if len(keys) == 1 and re.search(r"[가-힣]", it.get("INGD_NM") or ""):
                targets[key]["names"]["food" if exact else "food_syn"].append(clean(it.get("INGD_NM")))
            # 같은 종의 한국어 원료 이름은 검색에도 쓴다 (예: 환삼덩굴을 '한삼덩굴'로 찾기)
            if len(keys) == 1 and re.search(r"[가-힣]", it.get("INGD_NM") or ""):
                targets[key]["food_ko"].append(clean(it.get("INGD_NM")))
            targets[key]["food"].append({
                "name": clean(it.get("INGD_NM")), "other": dash(it.get("NKNM_NM")), "sci": clean(it.get("SCNNM_NM")),
                "edible": clean(it.get("EDIBLE_INFO")), "parts": dash(it.get("EDIBLE_USE_CONT")), "cond": dash(it.get("CHRTR_INFO_CONT")),
                "herbal": dash(it.get("DRNM")), "exact": exact,
            })
            # 영양성분 연결용 이름은 옛 학명으로 이어진 원료도 쓴다 (완두 = Pisum sativum -> Lathyrus oleraceus)
            names["main"][clean(it.get("INGD_NM"))].add(key)
            for n in (it.get("NKNM_NM") or "").split(","):
                if clean(n) and re.search(r"[가-힣]", n):
                    names["other"][clean(n)].add(key)
        linked += bool(keys)
    print(f"식품 원료(식약처): 식물성 원료 {linked}개를 도감 식물에 연결")
    return fetched, names


# 화면에 보여 줄 영양성분 (원문 성분 이름, 화면 이름). 원문 값은 바꾸지 않는다
NUTRIENTS = [("에너지", "열량"), ("수분", "수분"), ("단백질", "단백질"), ("지방", "지방"), ("탄수화물", "탄수화물"), ("당류", "당류"),
             ("총 식이섬유", "식이섬유"), ("칼슘", "칼슘"), ("철", "철"), ("칼륨", "칼륨"), ("나트륨", "나트륨"),
             ("비타민A", "비타민 A"), ("베타카로틴", "베타카로틴"), ("비타민 C", "비타민 C"), ("비타민 E", "비타민 E"), ("엽산-엽산당량", "엽산"), ("비타민 K", "비타민 K")]


NUTRI_TREE_GROUPS = ("견과 및 종실류", "채소류", "과일류")
# 식품 이름이 식물 이름과 다른 것: 멥쌀·찹쌀은 벼의 쌀
NUTRI_ALIAS = {"멥쌀": "벼", "찹쌀": "벼"}
# 이름은 맞지만 다른 식물인 식품: 머스캣베일리에이는 머루가 아닌 포도 품종
# 미역취·일당귀는 도감에 없는 다른 식물이라 앞 이름(취나물, 당귀)의 식물에 붙이지 않는다
# 땅두릅은 두릅나무가 아닌 독활(Aralia cordata)이다
NUTRI_SKIP = {"머루, 머스켓베일리에이, 생것", "취나물, 미역취, 생것", "당귀, 일당귀, 잎, 생것",
              "두릅, 땅두릅, 생것", "두릅, 땅두릅, 잎, 생것", "두릅, 땅두릅, 줄기, 생것"}


def add_foodnutri(data_dir, targets, food_names, problems):
    """국가표준식품성분의 '생것' 식품을 이름으로 식물에 붙인다. '감, 단감, 생것' -> '감' 또는 '감나무'."""
    raw = data_dir / "raw" / "foodnutri"
    if not (raw / "details.json").exists():
        return None
    fetched = json.loads((raw / "fetched.json").read_text(encoding="utf-8"))["fetched"]
    details = json.loads((raw / "details.json").read_text(encoding="utf-8"))
    find = name_finder(targets, food_names)
    linked = 0
    for f in json.loads((raw / "list.json").read_text(encoding="utf-8")):
        if f["food_Code"] not in details:
            continue
        head, *rest = [x.strip() for x in f["food_Nm"].split(",")]
        head = NUTRI_ALIAS.get(head, head)
        if f["food_Nm"] in NUTRI_SKIP:
            continue
        # '두릅, 땅두릅'처럼 뒤에 따로 있는 식물 이름이 오면 그 식물에 붙인다
        # 앞 이름이 식물 이름일 때만 본다 ('수제비면, 감자', '잡곡, 현미'처럼 가공식품은 붙이지 않는다)
        keys = next((k for k in map(find, rest) if len(k) == 1), set()) if find(head) else set()
        # '감' -> '감나무'는 과일·채소·견과에만 쓴다 (곡류의 '국수'가 국수나무로 가지 않게)
        keys = keys or find(head) or (find(head + "나무") if f["food_Grupp"] in NUTRI_TREE_GROUPS else set())
        if len(keys) > 1:
            problems.append(f"[식품성분] 이름이 여러 식물에 맞아 연결하지 않음: {f['food_Nm']}")
            continue
        if not keys:
            continue
        rows = {n: (v, u) for _, n, v, u in details[f["food_Code"]]}
        values = [[label, *rows[n]] for n, label in NUTRIENTS if n in rows and rows[n][0] not in ("", "-")]
        if values:
            targets[next(iter(keys))]["nutri"].append({"name": f["food_Nm"], "group": f["food_Grupp"], "year": f["examin_Year"],
                                                       "origin": f["origin_Nm"], "values": values})
            linked += 1
    print(f"영양성분(국가표준식품성분): 생것 식품 {linked}개를 식물에 연결")
    return fetched


# 농사로 Open API (pipeline/fetch_nongsaro.py 로 받은 자료). 공공누리 유형은 농사로 공공데이터 목록에 적힌 대로다.
NS_URL = "https://www.nongsaro.go.kr/portal/ps/psn/psnj/openApiLst.ps?menuId=PS65428"
NS_SOURCES = {
    "garden": ("농촌진흥청 농사로 실내정원용 식물", "공공누리 제3유형 (출처표시, 변경금지)"),
    "dry": ("농촌진흥청 농사로 건조에 강한 실내식물", "공공누리 제4유형 (출처표시, 상업적 이용금지, 변경금지)"),
    "herb": ("농촌진흥청 농사로 약초정보(민간약초)", "공공누리 제3유형 (출처표시, 변경금지)"),
    "fild": ("농촌진흥청 농사로 텃밭가꾸기 정보", "공공누리 제4유형 (출처표시, 상업적 이용금지, 변경금지)"),
    "week": ("농촌진흥청 농사로 주간농사정보", "공공누리 제1유형 (출처표시)"),
}
# 실내정원용 식물 '독성' 칸에서 독이 없다는 뜻인 값. 정보가 없는 값(N/A, unknown)과 독성과 상관없는 값(해독작용)은 화면에서도 뺀다
NS_NOT_TOXIC = {"없음", "n/a", "unknown", "알려져 있지 않음", "해독작용"}
NS_HIDE_TOXIC = {"n/a", "unknown", "해독작용"}
# 실내정원용 식물: (원문 항목, 화면 이름). 값은 원문 그대로 싣는다
NS_GARDEN_FIELDS = [
    ("distbNm", "유통명"), ("orgplceInfo", "원산지"), ("clCodeNm", "분류"), ("grwhstleCodeNm", "자라는 모양"),
    ("growthHgInfo", "키 (cm)"), ("growthAraInfo", "폭 (cm)"), ("lighttdemanddoCodeNm", "빛"), ("postngplaceCodeNm", "두면 좋은 곳"),
    ("grwhTpCodeNm", "잘 자라는 온도"), ("winterLwetTpCodeNm", "겨울 최저 온도"), ("hdCodeNm", "습도"),
    ("watercycleSprngCodeNm", "물주기 (봄)"), ("watercycleSummerCodeNm", "물주기 (여름)"), ("watercycleAutumnCodeNm", "물주기 (가을)"),
    ("watercycleWinterCodeNm", "물주기 (겨울)"), ("frtlzrInfo", "비료"), ("soilInfo", "흙"), ("managelevelCodeNm", "관리 수준"),
    ("managedemanddoCodeNm", "관리 요구도"), ("grwtveCodeNm", "자라는 속도"), ("prpgtmthCodeNm", "번식 방법"), ("prpgtEraInfo", "번식 시기"),
    ("dlthtsCodeNm", "잘 생기는 병해충"), ("dlthtsManageInfo", "병해충 관리"), ("speclmanageInfo", "특별 관리"), ("etcEraInfo", "그 밖에"),
    ("fncltyInfo", "특징"), ("flclrCodeNm", "꽃 색"), ("ignSeasonCodeNm", "꽃 피는 때"), ("lefcolrCodeNm", "잎 색"),
    ("lefmrkCodeNm", "잎 무늬"), ("lefStleInfo", "잎 모양"), ("smellCodeNm", "향기"), ("adviseInfo", "용도"), ("toxctyInfo", "독성"),
]
NS_DRY_FIELDS = [
    ("distbNm", "유통명"), ("clNm", "분류"), ("orgplce", "원산지"), ("chartrInfo", "생김새"), ("stleSeNm", "모양"), ("rdxStleNm", "뿌리"),
    ("flwrInfo", "꽃"), ("lfclChngeInfo", "잎 색 변화"), ("grwtInfo", "자라는 때"), ("grwtseVeNm", "자라는 속도"), ("lighttInfo", "빛"),
    ("batchPlaceInfo", "두면 좋은 곳"), ("waterCycleInfo", "물주기"), ("grwhTpInfo", "잘 자라는 온도"), ("pswntrTpInfo", "겨울 최저 온도"),
    ("frtlzrInfo", "비료"), ("prpgtInfo", "번식"), ("dlthtsInfo", "병해충"), ("hgtmMhmrInfo", "여름철 주의"), ("tipInfo", "관리 요령"),
    ("manageLevelNm", "관리 수준"), ("manageDemandNm", "관리 요구도"), ("clCodeDc", "속 설명"),
]


def ns_text(value):
    """원문 값의 <br />, <i> 같은 표시만 줄바꿈·글자로 바꾼다. 문장은 고치지 않고, 담당자·연락처가 든 줄만 뺀다."""
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = html.unescape(re.sub(r"<[^>]+>", "", value))
    lines = (l.strip() for l in value.replace("\r", "").split("\n"))
    return "\n".join(l for l in lines if l and not is_private(l) and "담당자" not in l)


def ns_sci(value):
    """'<i>Peperomia graveolens</i>, 후추과', 'Potentilla kleiniana (장미과)', 'Ailanthus altissima for. altissima' -> 학명"""
    m = re.search(r"<i>(.*?)</i>", value or "")
    sci = m.group(1) if m else re.split(r"[(,]", value or "")[0]
    # 품종 이름('Variegata'), spp., hybrid 를 떼면 속 이름만 남는 것은 속 전체에 붙인다
    sci = re.sub(r"['‘’].*?['‘’]", "", sci)
    sci = re.sub(r"\b(?:spp|ssp|sp)\.\s*$|\bhybrids?\b|\bhybridum\b", "", sci.strip()).replace(" X ", " × ")
    return re.sub(r"\bfor\.", "f.", re.sub(r"\s+", " ", sci)).strip()


def add_nongsaro(data_dir, resolve, targets, meta, problems):
    raw = data_dir / "raw" / "nongsaro"
    if not (raw / "fetched.json").exists():
        return None
    fetched = json.loads((raw / "fetched.json").read_text(encoding="utf-8"))["fetched"]
    load = lambda name: json.loads((raw / name).read_text(encoding="utf-8")) if (raw / name).exists() else {}

    def link(kind, sci, name, item):
        hit, _ = resolve.from_full_name(sci) if sci else (None, "")
        if not hit:
            problems.append(f"[농사로 {NS_SOURCES[kind][0][10:]}] WFO에서 찾을 수 없는 학명: {name} -> {sci}")
            return None
        key, genus, rest, unit = hit
        t = targets[key]
        t["ns"][kind].append(item)
        t["ko"].append(name)
        # 품종 이름('마리안느', ‘탱고’)이나 속 전체에 붙은 이름은 검색에만 쓰고 대표 이름으로 쓰지 않는다
        if unit != "genus" and not re.search(r"['‘’“”]", name + item.get("sci", "")):
            t["names"]["ns"].append(name)
        meta[key] = (genus, rest, unit)
        return t

    names = {x["cntntsNo"]: x.get("cntntsSj", "") for x in load("garden_list.json")}
    counts = defaultdict(int)
    for no, d in load("garden_detail.json").items():
        name = clean(names.get(no, ""))
        fields = [[label, ns_text(d.get(k))] for k, label in NS_GARDEN_FIELDS if ns_text(d.get(k))]
        fields = [[k, v] for k, v in fields if not (k == "독성" and v.strip().lower() in NS_HIDE_TOXIC)]
        item = {"no": no, "name": name, "sci": d.get("plntbneNm", ""), "fields": fields}
        t = link("garden", ns_sci(d.get("plntbneNm", "")), name, item)
        if t is not None:
            t["cats"].add("indoor")
            counts["garden"] += 1
    for no, d in load("dryGarden_detail.json").items():
        name = clean(d.get("cntntsSj"))
        item = {"no": no, "name": name, "sci": ns_sci(d.get("scnm")), "img": d.get("mainImgUrl1", "").replace("http://", "https://", 1),
                "fields": [[label, ns_text(d.get(k))] for k, label in NS_DRY_FIELDS if ns_text(d.get(k))]}
        t = link("dry", ns_sci(d.get("scnm")), name, item)
        if t is not None:
            t["cats"].add("indoor")
            counts["dry"] += 1
    for no, d in load("prvateTherpy_detail.json").items():
        name = clean(d.get("cntntsSj"))
        item = {"no": no, "name": name, "sci": d.get("bneNm", ""), "herbal": ns_text(d.get("hbdcNm")), "part": ns_text(d.get("useeRegn")),
                "form": ns_text(d.get("stle")), "folk": ns_text(d.get("prvateTherpy")), "img": d.get("imgUrl1", "").replace("http://", "https://", 1)}
        if link("herb", ns_sci(d.get("bneNm")), name, item) is not None:
            counts["herb"] += 1
    print(f"농사로: 실내정원용 식물 {counts['garden']}종, 건조에 강한 실내식물 {counts['dry']}종, 민간약초 {counts['herb']}종 연결")
    return fetched


# 텃밭가꾸기 글 제목에서 작물 이름만 뽑는다. 작물 이름이 없는 글(캘린더, 농자재 등)은 붙이지 않는다
FILD_TITLE = [r"^주요 열대 아열대 과수 소개 _(.+)$", r"^가정에서 (.+?) (?:기르기|키우기)$", r"^(.+?)[을를] 이용한 텃밭가꾸기$",
              r"^(.+?) 텃밭가꾸기$", r"^(.+?) 종자 생산 기술$", r"^([가-힣]+)$"]
# 글 제목의 작물 이름이 도감 이름과 다른 것
# None 은 붙이지 않는다 (쪽파는 대파와 다른 식물)
FILD_ALIAS = {"참다래": "참다래(키위,다래)", "양앵두": "체리", "잎들깨": "들깨", "적환무": "무", "엔디브": "앤디브", "스피아민트": "녹양박하",
              "금감": "금귤", "온주밀감": "감귤", "한라봉": "감귤", "쪽파": None}


def fild_title(title):
    title = re.sub(r"\s+", " ", title).strip()
    for pat in FILD_TITLE:
        m = re.match(pat, title)
        if m:
            name = m.group(1).strip()
            return FILD_ALIAS.get(name, name)
    return None


def name_finder(targets, food_names):
    """한국어 이름으로 식물 키를 찾는다. 이름이 여러 식물에 맞으면 더 믿을 만한 이름부터 본다:
    작물 이름 > 대표 이름 > 다른 한국어 이름 > 식약처 원료 이름 > 식약처 다른 이름"""
    tiers = [defaultdict(set) for _ in range(3)]
    own = [s for s in NAME_PRIORITY if not s.startswith("food")]
    for key, t in targets.items():
        for n in t["crops"]:
            tiers[0][n].add(key)
        main = t.get("override_name") or next((n for s in own for n in t["names"][s]), "")
        if main:
            tiers[1][main].add(key)
        for n in t["ko"] + [n for s in own for n in t["names"][s]]:
            tiers[2][n].add(key)
    tiers += [food_names["main"], food_names["other"]]

    def find(name):
        for tier in tiers:
            if tier.get(name):
                return tier[name]
        return set()
    return find


def ns_html_lines(cn):
    parser = HtmlLines()
    parser.feed(cn or "")
    return parser.lines()


def add_fild(data_dir, targets, food_names, problems):
    raw = data_dir / "raw" / "nongsaro"
    find = name_finder(targets, food_names)
    linked = 0
    for code in ("335001", "335002", "335003"):
        path = raw / f"fildMnfct_{code}_list.json"
        if not path.exists():
            continue
        for it in json.loads(path.read_text(encoding="utf-8")):
            crop = fild_title(it.get("cntntsSj", ""))
            if not crop:
                continue
            keys = find(crop)
            if len(keys) != 1:
                if keys:
                    problems.append(f"[농사로 텃밭] 이름이 여러 식물에 맞아 연결하지 않음: {it['cntntsSj']}")
                continue
            lines = ns_html_lines(it.get("cn"))
            # 첫 줄은 글 제목과 같아 뺀다
            if lines and re.sub(r"\s", "", lines[0]) in re.sub(r"\s", "", it["cntntsSj"]):
                lines = lines[1:]
            # 담당자 이름·연락처가 든 줄은 싣지 않는다 (변경금지 자료라 문장은 고치지 않고 줄만 뺀다)
            kept = [l for l in lines if not is_private(l) and not re.search(r"담당자|작성자", l)]
            targets[next(iter(keys))]["ns"]["fild"].append({"no": it["cntntsNo"], "title": it["cntntsSj"].strip(), "lines": kept,
                                                            "omitted": len(lines) - len(kept)})
            linked += 1
    print(f"농사로 텃밭가꾸기: 작물 글 {linked}개 연결")


def write_week(data_dir, out_path):
    path = data_dir / "raw" / "nongsaro" / "weekFarmInfo_list.json"
    if not path.exists():
        return
    weeks = []
    for w in json.loads(path.read_text(encoding="utf-8")):
        files = list(zip(w.get("fileName", "").split("|"), w.get("downUrlList", "").split("|")))
        pdf = next((u for n, u in files if n.lower().endswith(".pdf")), w.get("downUrl", ""))
        weeks.append({"title": clean(w.get("subject")), "date": w.get("regDt", ""), "pdf": pdf})
    source, license_ = NS_SOURCES["week"]
    out_path.write_text(json.dumps({"source": source, "license": license_, "url": NS_URL, "weeks": weeks}, ensure_ascii=False), encoding="utf-8")


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
        # 속만 옮겨진 학명(예: 수크령 Pennisetum alopecuroides -> Cenchrus alopecuroides)도 종소명이 같으면 정확히 맞는 것으로 본다.
        # 다른 종에 합쳐진 이름(예: 섬나무딸기 -> 산딸기 종)은 그대로 뒤로 미룬다. 'var. japonica' 같은 기준 변종은 종으로 친다
        ranks = lambda s: sum(w in RANK_WORDS for w in s.split())
        stem = lambda e: re.sub(r"(um|us|a|is|e|os|on)$", "", e.lower())
        toks = f"{genus} {rest}".split()
        accepted_ranks = 0 if len(toks) == 4 and toks[3] == toks[1] else ranks(" ".join(toks))
        same_epithet = stem(used.split()[-1]) == stem((toks[:2] if accepted_ranks == 0 else toks)[-1])
        exact = ranks(used) == ranks(r["학명"]) == accepted_ranks and same_epithet
        if name:
            t["names"]["kfs" if exact else "kfs_loose"].append(name)
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


# 쓰임과 효능: 정원식물 설명에서 약재·먹는 법·꿀벌·독에 관한 문장을 원문 그대로 골라 낸다.
# 한 문장은 한 번만 싣고, 독에 관한 문장은 먹는 법으로 세지 않는다.
GARDEN_USES = [
    ("caution", re.compile(r"유독|중독|독성|독이 있")),
    ("med", re.compile(r"한방|약용|약재|약으로|생약")),
    ("food", re.compile(r"(?<![군장])식용|나물[로이을]|산나물|쌈[으이]|차로|먹는다|먹고|먹을 ?수|날 ?것으로 먹|절여")),
    ("bee", re.compile(r"밀원|벌들이")),
]
AIR_GRADE = re.compile(r"([가-힣]+?)(제거량|발생량)\s*[:(]\s*(?:등급\s*:\s*)?(최상|중상|중하|최소|최하|상|중|하)")
FOOD_KINDS = {"veg": "채소", "fruit": "과일", "grain": "곡식·콩·감자"}
BEE_WORDS = ("벌", "나비", "꽃가루", "나방", "이 식물만")


def garden_uses(items):
    out = []
    for it in items:
        for text in (it["feature"], it["garden"], it["care"]):
            for s in re.split(r"(?<=다\.)\s*", text or ""):
                s = s.strip()
                # 시나 책 제목을 옮긴 문장, 학명 줄임표에서 끊긴 조각은 뺀다
                if not s.endswith("다.") or re.search(r"[“”『』]|정약용", s):
                    continue
                kinds = [k for k, pat in GARDEN_USES if pat.search(s)]
                if "caution" in kinds:
                    kinds = [k for k in kinds if k != "food"]
                if kinds and not any(s == x[1] for x in out):
                    out.append([it["name"], s, kinds])
    return out


def use_info(t, dates):
    uses, cats = {}, set()
    grades = []
    for it in t["air"]:
        for name, kind, grade in AIR_GRADE.findall(" ".join(it["effects"])):
            label = f"{name} {kind}"
            if label not in (g[0] for g in grades):
                grades.append([label, grade])
    if t["air"]:
        uses["air"] = {"grades": grades, "source": AIR_SOURCE, "url": AIR_URL, "license": AIR_LICENSE, "retrieved": dates["air"]}
        cats.add("use-air")
    found = garden_uses(t["grow"])
    if found:
        uses["garden"] = {"items": found, "source": GARDEN_SOURCE, "url": GARDEN_URL, "retrieved": dates["garden"]}
        kinds = {k for _, _, ks in found for k in ks}
        cats |= {f"use-{k}" for k in kinds if k != "caution"} | ({"use-toxic"} if "caution" in kinds else set())
    food = [FOOD_KINDS[c] for c in sorted(t["cats"]) if c in FOOD_KINDS]
    if food:
        uses["crop"] = {"kinds": food, "crops": t["crops"], "source": NCPMS_SOURCE, "url": NCPMS_URL}
        cats.add("use-food")
    if t["food"]:
        uses["mfds"] = {"items": t["food"], "source": FOODRAW_SOURCE, "url": FOODRAW_URL, "retrieved": dates["food"]}
        cats.add("use-food")
    if t["nutri"]:
        # 이름이 짧은 식품(예: '감자, 생것')을 먼저 보여 준다
        items = sorted(t["nutri"], key=lambda x: (x["name"].count(","), x["name"]))
        uses["nutri"] = {"items": items, "source": NUTRI_SOURCE, "url": NUTRI_URL, "license": NUTRI_LICENSE, "retrieved": dates["nutri"]}
        cats.add("use-food")
    if t["ns"]["herb"]:
        uses["herb"] = {"items": t["ns"]["herb"], "source": NS_SOURCES["herb"][0], "license": NS_SOURCES["herb"][1], "url": NS_URL,
                        "retrieved": dates["ns"]}
        cats.add("use-med")
    # 실내정원용 식물의 '용도'와 '독성' 칸 (농촌진흥청)
    ns_use = [(it["name"], dict(it["fields"])) for it in t["ns"]["garden"]]
    advise = [[n, f["용도"]] for n, f in ns_use if f.get("용도")]
    # 독성 칸은 값이 제각각이라("복용시 치명적 독성", "강함 (…)", 영어 문장 등) 독이 없다는 값만 골라 내고 나머지는 독이 있다고 본다
    toxic = [[n, f["독성"], f["독성"].strip().lower() not in NS_NOT_TOXIC] for n, f in ns_use if f.get("독성")]
    if advise or toxic:
        uses["nsgarden"] = {"advise": advise, "toxic": toxic, "source": NS_SOURCES["garden"][0], "license": NS_SOURCES["garden"][1],
                            "url": NS_URL, "retrieved": dates["ns"]}
        words = " ".join(v for _, v in advise)
        cats |= ({"use-med"} if "약용" in words else set()) | ({"use-food"} if "식용" in words else set())
        if any(flag for _, _, flag in toxic):
            cats.add("use-toxic")
        if any("애완동물" in v for _, v, _ in toxic):
            cats.add("use-pet")
    web = (t["web"] or {}).get("uses")
    if web:
        uses["web"] = {**web, "source": NCSU_SOURCE, "url": t["web"]["url"], "retrieved": dates["ncsu"]}
        # 먹을 수 있다는 표시와 독성이 함께 적힌 식물(예: 동의나물)은 손질법·양에 조건이 붙어 있어 '먹을 수 있는 식물' 목록에 넣지 않는다
        if "edible" in web and not web.get("caution") and "use-toxic" not in cats:
            cats.add("use-food")
        if any(w in a for a in web.get("attracts", []) for w in BEE_WORDS):
            cats.add("use-bee")
        if web.get("caution"):
            cats.add("use-toxic")
        if web.get("pets"):
            cats.add("use-pet")
    return uses, cats


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
    ns_date = add_nongsaro(data_dir, resolve, targets, meta, problems)
    cases_date = add_cases(data_dir, targets, problems, resolve, meta)
    food_date, food_names = add_foodraw(data_dir, resolve, targets, problems)
    nutri_date = add_foodnutri(data_dir, targets, food_names, problems)
    add_fild(data_dir, targets, food_names, problems)
    corrections = apply_corrections(data_dir, resolve, targets, problems)
    for key in [k for k, t in targets.items() if t.get("hidden")]:
        del targets[key]

    out = Path(out_dir)
    # 폴더째 지우면 Windows에서 다른 프로그램이 잡고 있을 때 실패할 수 있어, 안의 파일만 지운다
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()
    index = {}
    # 식약처 원료 이름은 다른 식물이 이미 쓰는 이름이면 대표 이름으로 쓰지 않는다 (같은 이름 두 식물이 생기지 않게)
    own_name = lambda t: t.get("override_name") or next((n for s in NAME_PRIORITY if not s.startswith("food") for n in t["names"][s]), "")
    taken = {own_name(t) for t in targets.values()}
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
            doc["web"] = {"source": NCSU_SOURCE, "retrieved": ncsu_date, **{k: v for k, v in t["web"].items() if k != "uses"}}
        if t["smart"]:
            doc["smart"] = {"source": SMART_SOURCE, "url": SMART_URL, "retrieved": smart_date, **t["smart"]}
        if t["cases"]:
            doc["cases"] = {"source": CASES_SOURCE, "url": CASES_URL, "license": CASES_LICENSE, "retrieved": cases_date,
                            "items": sorted(t["cases"], key=lambda c: c.get("date", ""), reverse=True)}
        for kind, items in t["ns"].items():
            if items and kind != "herb":
                doc.setdefault("ns", {})[kind] = {"source": NS_SOURCES[kind][0], "license": NS_SOURCES[kind][1], "url": NS_URL,
                                                  "retrieved": ns_date, "items": items}
        uses, use_cats = use_info(t, {"air": air_date, "garden": garden_date, "ncsu": ncsu_date, "food": food_date, "nutri": nutri_date,
                                      "ns": ns_date})
        if uses:
            doc["uses"] = uses
            t["cats"] |= use_cats
        (out / f"{key.replace(':', '-')}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        name = t.get("override_name") or next((n for s in NAME_PRIORITY for n in t["names"][s]
                                                  if not s.startswith("food") or n not in taken), "")
        index[key] = {
            "g": genus, "r": rest, "name": name, "crops": t["crops"], "ko": list(dict.fromkeys(t["ko"] + t["food_ko"])),
            "cats": sorted(t["cats"]), "nd": len(t["diseases"]), "ni": len(t["insects"]),
            "grow": bool(t["grow"] or t["air"] or t["ns"]["garden"] or t["ns"]["dry"] or t["ns"]["fild"]), "web": bool(t["web"]), "smart": bool(t["smart"]), "nc": len(t["cases"]),
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
    write_week(data_dir, out.parent / "week.json")
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
