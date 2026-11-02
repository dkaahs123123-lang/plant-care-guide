"""NC State Plant Toolbox 항목 값 -> 한국어. 표에 없는 값은 영어 원문을 그대로 쓴다."""
import re

LABELS = {
    "Light": "빛",
    "Soil Drainage": "흙의 물 빠짐",
    "Soil Texture": "알맞은 흙",
    "Soil pH": "흙의 산도",
    "Maintenance": "관리 난이도",
    "Growth Rate": "자라는 속도",
    "Life Cycle": "한해·여러해살이",
    "Recommended Propagation Strategy": "번식 방법",
    "Resistance To Challenges": "잘 견디는 것",
    "Problems": "주의할 점",
    "Poison Severity": "독성 정도",
    "Poison Part": "독이 있는 부분",
    "Poison Toxic Principle": "독성 성분",
    "Country Or Region Of Origin": "원산지",
}

VALUES = {
    # 빛
    "Full sun (6 or more hours of direct sunlight a day)": "햇빛 많이 (직사광선 하루 6시간 이상)",
    "Partial Shade (Direct sunlight only part of the day, 2-6 hours)": "반그늘 (직사광선 하루 2~6시간)",
    "Dappled Sunlight (Shade through upper canopy all day)": "나뭇잎 사이로 드는 빛 (하루 종일 그늘진 밝은 곳)",
    "Deep shade (Less than 2 hours to no direct sunlight)": "그늘 (직사광선 2시간 미만)",
    # 물 빠짐
    "Good Drainage": "물이 잘 빠지는 흙",
    "Moist": "늘 촉촉한 흙",
    "Occasionally Dry": "가끔 마르는 흙",
    "Occasionally Wet": "가끔 젖는 흙",
    "Very Dry": "아주 마른 흙",
    "Excessively Dry": "매우 건조한 흙",
    "Frequent Standing Water": "물이 자주 고이는 곳",
    "Occasional Flooding": "가끔 물에 잠기는 곳",
    "Poorly Drained": "물 빠짐이 나쁜 흙",
    # 흙
    "Clay": "점토(찰흙)",
    "High Organic Matter": "유기물이 많은 흙",
    "Loam (Silt)": "양토(고운 흙)",
    "Sand": "모래흙",
    "Shallow Rocky": "얕은 돌흙",
    # 산도
    "Acid (<6.0)": "산성 (pH 6.0 미만)",
    "Neutral (6.0-8.0)": "중성 (pH 6.0~8.0)",
    "Alkaline (>8.0)": "알칼리성 (pH 8.0 초과)",
    # 관리, 속도
    "Low": "낮음",
    "Medium": "보통",
    "High": "높음",
    "Slow": "느림",
    "Rapid": "빠름",
    # 생활형
    "Annual": "한해살이",
    "Biennial": "두해살이",
    "Perennial": "여러해살이",
    "Woody": "나무(목본)",
    # 번식
    "Seed": "씨앗",
    "Stem Cutting": "줄기꽂이",
    "Root Cutting": "뿌리꽂이",
    "Leaf Cutting": "잎꽂이",
    "Division": "포기나누기",
    "Layering": "휘묻이",
    "Air Layering": "공중 휘묻이",
    "Grafting": "접붙이기",
    "Offsets": "새끼 포기",
    "Spores": "포자",
    "Bulbs": "알뿌리",
    "Tissue culture": "조직배양",
    "Tissue Culture": "조직배양",
    # 잘 견디는 것
    "Deer": "사슴 피해",
    "Drought": "가뭄",
    "Heat": "더위",
    "Humidity": "높은 습도",
    "Rabbits": "토끼 피해",
    "Salt": "염분",
    "Wet Soil": "젖은 흙",
    "Dry Soil": "마른 흙",
    "Poor Soil": "척박한 흙",
    "Compaction": "다져진 흙",
    "Pollution": "공해",
    "Diseases": "병",
    "Insect Pests": "해충",
    "Wind": "바람",
    "Fire": "불",
    "Storm damage": "폭풍 피해",
    "Erosion": "흙 깎임",
    "Black Walnut": "흑호두나무 독성(주글론)",
    "Urban Conditions": "도시 환경",
    # 주의할 점
    "Contact Dermatitis": "피부에 닿으면 염증",
    "Poisonous to Humans": "사람에게 독성",
    "Problem for Cats": "고양이에게 해로움",
    "Problem for Dogs": "개에게 해로움",
    "Problem for Horses": "말에게 해로움",
    "Problem for Children": "어린이 주의",
    "Invasive Species": "침입 외래종",
    "Weedy": "잡초처럼 퍼짐",
    "Spines/Thorns": "가시",
    "Allergenic": "알레르기 유발",
    "Frequent Disease Problems": "병이 자주 생김",
    "Frequent Insect Problems": "해충이 자주 생김",
    "Malodorous": "냄새가 남",
    "Messy": "떨어지는 것이 많음",
    "Remove Spent Flowers": "시든 꽃 따 주기",
    "Short-lived": "수명이 짧음",
    "Needs Wind Protection": "바람막이 필요",
    "Problem for Pets": "반려동물에게 해로움",
    # 독이 있는 부분
    "Bark": "껍질",
    "Flowers": "꽃",
    "Fruits": "열매",
    "Leaves": "잎",
    "Roots": "뿌리",
    "Sap/Juice": "수액",
    "Seeds": "씨앗",
    "Stems": "줄기",
    "Pollen": "꽃가루",
    "All parts": "모든 부분",
}

SPACE = {
    "Less than 12 inches": "약 30cm 미만",
    "12 inches-3 feet": "약 30cm~0.9m",
    "3 feet-6 feet": "약 0.9~1.8m",
    "6-feet-12 feet": "약 1.8~3.7m",
    "12-24 feet": "약 3.7~7.3m",
    "24-60 feet": "약 7.3~18m",
    "more than 60 feet": "약 18m 이상",
}


def ko(value):
    return VALUES.get(value, value)


def feet_in_to_m(text):
    """'Height: 3 ft. 0 in. - 5 ft. 0 in.' -> ('높이', '약 0.9~1.5m')"""
    m = re.match(r"(Height|Width):\s*(\d+) ft\. (\d+) in\.\s*-\s*(\d+) ft\. (\d+) in\.", text)
    if not m:
        return None
    lo = int(m.group(2)) * 0.3048 + int(m.group(3)) * 0.0254
    hi = int(m.group(4)) * 0.3048 + int(m.group(5)) * 0.0254
    fmt = lambda x: f"{x:.1f}".rstrip("0").rstrip(".") if x < 10 else f"{x:.0f}"
    return ("다 자란 높이" if m.group(1) == "Height" else "다 자란 폭"), f"약 {fmt(lo)}~{fmt(hi)}m"


def zone_min(zones):
    """USDA 내한성 구역 목록에서 가장 추운 구역과 그 최저기온 하한(섭씨)을 돌려준다.
    USDA 정의: 1a 구역이 -60°F 이상이고, 반 구역(a/b)마다 5°F씩 올라간다."""
    best = None
    for z in zones:
        for n, half in re.findall(r"(\d{1,2})([ab])", z):
            f = -60 + (int(n) - 1) * 10 + (5 if half == "b" else 0)
            if best is None or f < best[0]:
                best = (f, f"{n}{half}")
    if not best:
        return None
    return best[1], round((best[0] - 32) * 5 / 9, 1)


def zone_of_c(c):
    """섭씨 최저기온이 들어가는 USDA 구역 이름 (예: -15.2 -> '7a')"""
    f = c * 9 / 5 + 32
    step = int((f + 60) // 5)
    return f"{step // 2 + 1}{'ab'[step % 2]}"


def zone_min_c(zones):
    z = zone_min(zones)
    if not z:
        return None
    return f"약 {round(z[1])}°C까지 (USDA {z[0]} 구역, 야외 기준)"
