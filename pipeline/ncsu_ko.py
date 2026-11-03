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
    # 그 밖에 표에 빠져 있던 값
    "Bulb": "알뿌리 식물",
    "Heavy Shade": "짙은 그늘",
    "Foot Traffic": "밟힘",
    "Allelopathic": "주변 식물이 자라는 것을 막는 물질을 냄",
    "Weak Wood": "가지가 잘 부러짐",
}

# 독성 성분: 자주 나오는 값만 옮긴다. 표에 없는 값은 영어 그대로 두고 칸 이름에 (영문)을 붙인다.
TOXINS = {
    "unknown": "알려지지 않음",
    "unidentified": "밝혀지지 않음",
    "toxicity unknown, but caution because of its relationship with known toxic plant": "알려지지 않았지만 독성 식물과 가까운 종류라 주의",
    "unidentified, possibly a glycoside": "밝혀지지 않음 (배당체로 추정)",
    "saponins": "사포닌", "saponin": "사포닌", "triterpenoid saponins": "트리테르페노이드 사포닌",
    "grayanotoxins": "그레이아노톡신", "grayanotoxin": "그레이아노톡신", "andromedotoxin": "안드로메도톡신(그레이아노톡신)",
    "calcium oxalate crystals": "옥살산칼슘 결정", "calcium oxalate": "옥살산칼슘", "calcium oxalates": "옥살산칼슘",
    "soluble calcium oxalates": "녹는 옥살산염", "soluble calcium oxylates": "녹는 옥살산염", "soluble oxalates": "녹는 옥살산염",
    "insoluble calcium oxalate crystals": "녹지 않는 옥살산칼슘 결정", "oxalic acid": "옥살산",
    "diterpene esters in milky latex": "흰 즙 속의 디테르펜 에스터",
    "berberine, a benzylisoquinoline alkaloid": "베르베린 (알칼로이드)",
    "alkaloids": "알칼로이드", "alkaloid": "알칼로이드", "isoquinoline alkaloids": "아이소퀴놀린 알칼로이드",
    "pyrrolizidine alkaloids": "피롤리지딘 알칼로이드", "lycorine and other alkaloids": "리코린 등 알칼로이드", "lycorine": "리코린",
    "protoanemonin": "프로토아네모닌", "ranunculin": "라눈쿨린",
    "sulfides": "황화물", "cyanogenic glycosides": "시안 배당체", "cyanogenic glycoside": "시안 배당체",
    "cardiac glycoside": "강심 배당체", "cardiac glycosides": "강심 배당체", "cardiac glycosides and resinoids": "강심 배당체와 수지 성분",
    "sesquiterpene lactones": "세스퀴테르펜 락톤", "aristolochic acid": "아리스톨로크산",
    "furanocoumarins": "푸라노쿠마린", "gallotannins, quercitrin, and quercitin": "갈로탄닌, 퀘르시트린, 퀘르세틴",
    "tannins": "탄닌", "taxine": "탁신", "taxines": "탁신", "solanine": "솔라닌", "glycoalkaloids": "글리코알칼로이드",
    "phototoxic thiophene derivatives": "빛에 반응하는 티오펜 화합물", "daphnetoxin and mezerein": "다프네톡신, 메제레인",
    "baptisin and cytisine": "밥티신, 시티신", "cytisine": "시티신", "nicotine": "니코틴", "colchicine": "콜히친",
    "glycosides": "배당체", "glycoside": "배당체", "terpenes": "테르펜", "essential oils": "정유 성분", "volatile oils": "정유 성분",
    "anthraquinones": "안트라퀴논", "anthraquinone glycosides": "안트라퀴논 배당체", "nitrates": "질산염", "resins": "수지 성분",
    "latex": "흰 즙(라텍스)", "milky sap": "흰 즙", "ricin": "리신", "abrin": "아브린", "lectins": "렉틴",
    "andromedotoxins": "안드로메도톡신(그레이아노톡신)", "hydrocyanic acid": "시안화수소산", "amygdalin": "아미그달린",
}


# 잘 생기는 해충: NC State 해충 안내문 제목. 자주 나오는 것만 해충 이름으로 옮긴다.
PESTS = {
    "Pests of Conifers": "침엽수 해충", "Aphids on Ornamental Landscape Plants": "진딧물",
    "Aphids Found on Flowers and Foliage": "진딧물", "Slugs and Snails Found on Flowers and Foliage": "민달팽이·달팽이",
    "Slugs & Snails on Ornamental Plants": "민달팽이·달팽이", "Common Insect Pests of Oak in North Carolina": "참나무 해충",
    "Common Insect Pests of Maple in North Carolina": "단풍나무 해충", "Common Insect Pests of Ash in North Carolina": "물푸레나무 해충",
    "Bulb Mites": "뿌리응애", "Mealybugs": "깍지벌레(가루깍지벌레)", "Mealybugs Found on Flowers and Foliage": "깍지벌레(가루깍지벌레)",
    "Root Mealybugs": "뿌리가루깍지벌레", "Banded Greenhouse Thrips": "총채벌레", "Greenhouse Thrips": "총채벌레",
    "Thrips Found on Flowers and Foliage": "총채벌레", "Insect and Related Pests of Vegetables": "채소 해충",
    "Magnolia Scale": "깍지벌레(목련깍지벌레)", "Whiteflies Found on Flowers and Foliage": "가루이",
    "Bandedwinged Whitefly on Ornamentals": "가루이", "Florida Fern Caterpillar": "고사리 애벌레(나방 유충)",
    "Azalea Lace Bug": "방패벌레(진달래방패벌레)", "Lace Bugs": "방패벌레", "Cherry Lace Bug": "방패벌레",
    "Hawthorn Lace Bug": "방패벌레", "Alder Lace Bug/Birch Lace Bug": "방패벌레", "Narcissus Bulb Fly": "수선화구근파리",
    "Japanese Beetle": "왜콩풍뎅이", "Japanese Beetles on Ornamental Landscape Plants": "왜콩풍뎅이",
    "Milkweed Bug": "노린재(박주가리노린재)", "Twospotted Spider Mites on Landscape Plants": "점박이응애",
    "Twospotted Spider Mite": "점박이응애", "Southern Red Mite and Spruce Spider Mite": "응애", "Boxwood Mite": "응애",
    "Cyclamen Mites in Strawberries": "시클라멘먼지응애", "Fern Scale Insect": "깍지벌레",
    "Scale Insects Found on Flowers and Foliage": "깍지벌레", "Armored Scale Identification and Management on Ornamental Plants": "깍지벌레",
    "Soft Scale Identification and Management on Ornamental Plants": "깍지벌레", "Boisduval Scale": "깍지벌레",
    "Cottony Camellia Scale Insect": "깍지벌레", "Hemispherical Scale": "깍지벌레", "Euonymus Scale": "깍지벌레(사철깍지벌레)",
    "Palmetto Scale": "깍지벌레", "Indian Wax Scale Insect": "깍지벌레(밀깍지벌레)", "Japanese Maple Scale": "깍지벌레",
    "Phlox Plant Bug and Other Lopidea Plant Bugs": "장님노린재", "Yucca Plant Bug": "노린재", "Rednecked Cane Borer": "줄기를 파먹는 하늘소·비단벌레류",
    "Raspberry Cane Borer": "줄기를 파먹는 하늘소류", "Wireworms in Turf": "방아벌레 애벌레", "Pests of Cucurbits": "박과 작물 해충",
    "Pests of Holly": "호랑가시나무 해충", "Pests of Rose": "장미 해충", "Pests of Beans and Peas": "콩·완두 해충",
    "Pests of Crucifers": "배추과 작물 해충", "Pests of Lettuce": "상추 해충", "Pests of Dogwood": "층층나무 해충",
    "Arthropod Pests of Azalea": "진달래 해충", "Bagworms in Ornamental Landscapes": "주머니나방",
    "Dogwood Borer": "줄기를 파먹는 나방 애벌레", "Rhododendron Gall Midge": "혹파리", "Imported Willow Leaf Beetle": "잎벌레",
    "Emerald Ash Borer": "에메랄드물푸레나무좀(비단벌레)", "Caterpillars Found on Flowers and Foliage": "나방·나비 애벌레",
    "Granulate (Asian) Ambrosia Beetle": "나무좀", "Leafminers of Hollies": "굴파리", "Crapemyrtle Aphid": "진딧물",
    "Balsam Woolly Adelgid": "솜벌레(아델지드)", "Hemlock Woolly Adelgid": "솜벌레(아델지드)", "Eastern Tent Caterpillar": "천막벌레나방 애벌레",
    "Plum Curculio": "바구미", "Yellow Poplar Weevil": "바구미", "Smaller European Elm Bark Beetle": "나무좀",
    "Bronze Birch Borer": "비단벌레", "Twolined Chestnut Borer": "비단벌레", "Locust Borer": "하늘소",
    "Dogwood Sawfly": "잎벌", "Orange-Shouldered Sherbet Moth": "나방 애벌레", "Tersa Sphinx": "박각시 애벌레",
}


def pest(value):
    """해충 안내문 제목 -> (한국어, 옮겼는지)"""
    v = value.strip().rstrip(",")
    return (PESTS[v], True) if v in PESTS else (value, False)


def toxin(value):
    """독성 성분 값 -> (한국어, 옮겼는지)"""
    k = value.strip().rstrip(".").lower()
    return (TOXINS[k], True) if k in TOXINS else (value, False)


# 원산지: 지명과 방향 낱말을 한국어로 옮긴다. 낱말 하나라도 모르면 영어 그대로 둔다.
PLACES = {
    "north america": "북아메리카", "northern america": "북아메리카", "south america": "남아메리카", "central america": "중앙아메리카",
    "tropical america": "열대 아메리카", "tropical americas": "열대 아메리카", "subtropical america": "아열대 아메리카",
    "subtropical americas": "아열대 아메리카", "subarctic america": "아북극 아메리카", "new world": "아메리카 대륙",
    "america": "아메리카", "americas": "아메리카", "west indies": "서인도 제도", "caribbean": "카리브해 지역",
    "usa": "미국", "us": "미국", "united states": "미국", "canada": "캐나다", "mexico": "멕시코",
    "europe": "유럽", "eurasia": "유라시아", "asia": "아시아", "africa": "아프리카", "australia": "오스트레일리아",
    "southeast asia": "동남아시아", "south east asia": "동남아시아", "se asia": "동남아시아", "east asia": "동아시아",
    "eastern asia": "동아시아", "central asia": "중앙아시아", "western asia": "서아시아", "west asia": "서아시아",
    "southwest asia": "남서아시아", "southwestern asia": "남서아시아", "south asia": "남아시아", "asia minor": "소아시아",
    "north africa": "북아프리카", "northern africa": "북아프리카", "south africa": "남아프리카공화국", "southern africa": "아프리카 남부",
    "tropical africa": "열대 아프리카", "middle east": "중동", "mediterranean": "지중해 연안", "medit": "지중해 연안",
    "northern hemisphere": "북반구", "indian subcontinent": "인도 아대륙", "arabian peninsula": "아라비아반도",
    "china": "중국", "japan": "일본", "korea": "한국", "south korea": "한국", "north korea": "북한", "taiwan": "대만",
    "mongolia": "몽골", "manchuria": "만주", "tibet": "티베트", "hainan": "하이난섬", "himalaya": "히말라야", "himalayas": "히말라야",
    "siberia": "시베리아", "russia": "러시아", "russian far east": "러시아 극동", "european russia": "러시아 유럽 지역",
    "sakhalin": "사할린", "kuril islands": "쿠릴 열도", "south kuril islands": "남쿠릴 열도", "nansei-shoto": "난세이 제도",
    "india": "인도", "nepal": "네팔", "pakistan": "파키스탄", "afghanistan": "아프가니스탄", "bangladesh": "방글라데시",
    "sri lanka": "스리랑카", "assam": "아삼", "myanmar": "미얀마", "burma": "미얀마", "thailand": "태국", "laos": "라오스",
    "vietnam": "베트남", "viet nam": "베트남", "indo-china": "인도차이나", "malaysia": "말레이시아", "malesia": "말레시아",
    "philippines": "필리핀", "phillipines": "필리핀", "sumatra": "수마트라섬", "jawa": "자와섬", "java": "자와섬",
    "new guinea": "뉴기니", "kazakhstan": "카자흐스탄", "iran": "이란", "iraq": "이라크", "syria": "시리아", "lebanon": "레바논",
    "turkey": "튀르키예", "caucasus": "캅카스", "transcaucasus": "자캅카스", "cyprus": "키프로스", "crete": "크레타섬",
    "greece": "그리스", "bulgaria": "불가리아", "balkans": "발칸반도", "yugoslavia": "옛 유고슬라비아", "italy": "이탈리아",
    "spain": "스페인", "portugal": "포르투갈", "france": "프랑스", "pyrenees": "피레네산맥", "ukraine": "우크라이나",
    "baltic states": "발트 3국", "european mountains": "유럽 산지", "macaronesia": "마카로네시아", "macronesia": "마카로네시아",
    "canary islands": "카나리아 제도", "azores": "아조레스 제도", "morocco": "모로코", "algeria": "알제리", "sudan": "수단",
    "ethiopia": "에티오피아", "kenya": "케냐", "tanzania": "탄자니아", "mozambique": "모잠비크", "zimbabwe": "짐바브웨",
    "eswatini": "에스와티니", "madagascar": "마다가스카르", "kwazulu-natal": "콰줄루나탈", "cape provinces": "케이프 지방",
    "cape province": "케이프 지방", "cape province of south africa": "남아프리카공화국 케이프 지방",
    "new zealand": "뉴질랜드", "new zeland": "뉴질랜드", "norfolk island": "노퍽섬", "fiji": "피지", "new caledonia": "뉴칼레도니아",
    "polynesia": "폴리네시아", "greenland": "그린란드", "alaska": "알래스카",
    "brazil": "브라질", "argentina": "아르헨티나", "bolivia": "볼리비아", "peru": "페루", "chile": "칠레", "ecuador": "에콰도르",
    "colombia": "콜롬비아", "venezuela": "베네수엘라", "paraguay": "파라과이", "uruguay": "우루과이", "guatemala": "과테말라",
    "honduras": "온두라스", "nicaragua": "니카라과", "costa rica": "코스타리카", "panama": "파나마", "belize": "벨리즈",
    "cuba": "쿠바", "jamaica": "자메이카", "haiti": "아이티", "dominican republic": "도미니카공화국", "bahamas": "바하마",
    "bermuda": "버뮤다", "cayman islands": "케이맨 제도", "veracruz": "베라크루스", "puebla": "푸에블라",
    "ontario": "온타리오", "quebec": "퀘벡", "british columbia": "브리티시컬럼비아", "nova scotia": "노바스코샤",
    "appalachian mountains": "애팔래치아산맥", "appalachians": "애팔래치아산맥",
    "nc": "노스캐롤라이나", "north carolina": "노스캐롤라이나", "sc": "사우스캐롤라이나", "south carolina": "사우스캐롤라이나",
    "florida": "플로리다", "fl": "플로리다", "texas": "텍사스", "tx": "텍사스", "california": "캘리포니아", "ca": "캘리포니아",
    "georgia": "조지아", "ga": "조지아", "alabama": "앨라배마", "al": "앨라배마", "louisiana": "루이지애나", "la": "루이지애나",
    "arkansas": "아칸소", "ar": "아칸소", "virginia": "버지니아", "west virginia": "웨스트버지니아", "pennsylvania": "펜실베이니아",
    "new jersey": "뉴저지", "new york": "뉴욕", "ohio": "오하이오", "oklahoma": "오클라호마", "oregon": "오리건", "arizona": "애리조나",
    "new mexico": "뉴멕시코", "nevada": "네바다", "utah": "유타", "vermont": "버몬트", "tennessee": "테네시", "kentucky": "켄터키",
    "missouri": "미주리", "illinois": "일리노이", "indiana": "인디애나", "mississippi": "미시시피", "maryland": "메릴랜드",
    "colorado": "콜로라도", "kansas": "캔자스", "nebraska": "네브래스카", "minnesota": "미네소타", "wisconsin": "위스콘신",
    "michigan": "미시간", "iowa": "아이오와", "maine": "메인",
    "asia-temperate": "온대 아시아", "asia-tropical": "열대 아시아", "worldwide": "전 세계", "turkistan": "투르키스탄",
    "phillippines": "필리핀", "melanesia": "멜라네시아", "australasia": "오스트랄라시아", "sub-saharan africa": "사하라 이남 아프리카",
    "south pacific islands": "남태평양 섬", "albania": "알바니아", "mediterranean basin": "지중해 연안", "newfoundland": "뉴펀들랜드",
    "cape provinces of south africa": "남아프리카공화국 케이프 지방",
}
DIRS = {
    "north": "북부", "northern": "북부", "n": "북부", "south": "남부", "southern": "남부", "s": "남부",
    "east": "동부", "eastern": "동부", "e": "동부", "west": "서부", "western": "서부", "w": "서부", "central": "중부", "c": "중부",
    "northeast": "북동부", "northeastern": "북동부", "north east": "북동부", "north-east": "북동부", "north eastern": "북동부", "ne": "북동부",
    "northwest": "북서부", "northwestern": "북서부", "north west": "북서부", "north-west": "북서부", "north western": "북서부", "nw": "북서부",
    "southeast": "남동부", "southeastern": "남동부", "south east": "남동부", "south-east": "남동부", "south eastern": "남동부", "se": "남동부",
    "southwest": "남서부", "southwestern": "남서부", "south west": "남서부", "south-west": "남서부", "south western": "남서부", "sw": "남서부",
    "north central": "중북부", "north-central": "중북부", "northern central": "중북부", "n central": "중북부",
    "south central": "중남부", "south-central": "중남부", "s central": "중남부",
    "midwestern": "중서부", "east central": "중동부", "eastern central": "중동부", "e central": "중동부", "west central": "중서부", "w central": "중서부",
}
CLIMATE = {"tropical": "열대", "subtropical": "아열대", "temperate": "온대", "temp": "온대", "subarctic": "아북극", "arctic": "북극"}


def _segment(words):
    """['Eastern', 'North', 'America'] -> ('북아메리카', '동부', '') / 지명이 없으면 (None, 방향, 기후)"""
    low = [w.lower() for w in words]

    def modifiers(part):
        dirs, clim, j = [], [], 0
        while j < len(part):
            two = " ".join(part[j:j + 2])
            if len(part) > j + 1 and two in DIRS:
                dirs.append(DIRS[two]); j += 2
            elif part[j] in DIRS:
                dirs.append(DIRS[part[j]]); j += 1
            elif part[j] in CLIMATE:
                clim.append(CLIMATE[part[j]]); j += 1
            else:
                return None
        return dirs, clim

    for size in range(len(low), 0, -1):
        for i in range(len(low) - size + 1):
            place = " ".join(low[i:i + size])
            if place in PLACES:
                before, after = modifiers(low[:i]), modifiers(low[i + size:])
                if before is None or after is None:
                    return False
                return PLACES[place], "·".join(before[0] + after[0]), "·".join(before[1] + after[1])
    mods = modifiers(low)
    if low and mods:
        return None, "·".join(mods[0]), "·".join(mods[1])
    return False


def origin(value):
    """원산지 값 -> 한국어. 옮기지 못하면 None."""
    text = re.sub(r"\bU\.?\s?S\.?\s?A\.?|\bU\.S\.", "USA", value)
    text = re.sub(r"\bUS native\b", "USA", text)
    text = re.sub(r"\b(the|Native to|native to|native|Native|regions?|region of)\b", " ", text)
    # 'N. & Central America' = 북아메리카와 중앙아메리카
    text = re.sub(r"\b(North|South|Central|N|S)\.?\s*(?:&|and)\s*(North|South|Central) America",
                  lambda m: f"{ {'N': 'North', 'S': 'South'}.get(m.group(1), m.group(1))} America, {m.group(2)} America", text)
    text = text.replace("Temp.", "Temperate").replace("--", ",").replace("&", ",").replace("/", ",").replace(";", ",")
    text = re.sub(r"\b([NSEWC]{1,2})\.", r"\1", text)
    # 조각과 구분자(',' 또는 '~')를 차례로 늘어놓는다
    seq = []
    for chunk in re.split(r",|\band\b", text):
        rng = [r for r in re.split(r"\bto\b", chunk) if r.strip(" .")]
        for n, r in enumerate(rng):
            got = _segment(re.findall(r"[A-Za-z][A-Za-z'\-]*", r))
            if got is False:
                return None
            seq.append(("~" if n else ",", got))
    # 'Central & Eastern USA' 처럼 지명 없이 방향만 있는 조각은 다음 조각의 지명에 붙인다
    out, pend, pend_sep = [], [], None
    for sep, (place, d, clim) in seq:
        if place is None:
            if not pend:
                pend_sep = sep
            pend.append((d, clim))
            continue
        if pend:
            # 'western and central Asia': 중앙아시아가 아니라 아시아 서부·중부
            split = next(((PLACES[base], DIRS[w]) for w in DIRS for base in PLACES
                          if PLACES.get(f"{w} {base}") == place and " " not in w), None)
            if split and not d:
                place, d = split
            d = "·".join([x for x, _ in pend if x] + ([d] if d else []))
            clim = "·".join([c for _, c in pend if c] + ([clim] if clim else []))
            sep, pend = pend_sep, []
        out.append((sep, " ".join(x for x in (clim, place, d) if x)))
    if pend or not out:
        return None
    return "".join((", " if sep == "," else "~") + t if i else t for i, (sep, t) in enumerate(out))


SPACE = {
    "Less than 12 inches": "약 30cm 미만",
    "12 inches-3 feet": "약 30cm~0.9m",
    "3 feet-6 feet": "약 0.9~1.8m",
    "6-feet-12 feet": "약 1.8~3.7m",
    "12-24 feet": "약 3.7~7.3m",
    "24-60 feet": "약 7.3~18m",
    "more than 60 feet": "약 18m 이상",
}


# 'Attracts' 항목: 이 식물이 불러 모으는 동물
ATTRACTS = {
    "Bees": "벌",
    "Butterflies": "나비",
    "Pollinators": "꽃가루를 옮기는 곤충",
    "Songbirds": "작은 새",
    "Small Mammals": "작은 포유류",
    "Moths": "나방",
    "Hummingbirds": "벌새 (아메리카 대륙에만 사는 새)",
    "Frogs": "개구리",
    "Reptiles": "파충류",
    "Specialized Bees": "이 식물만 찾는 벌",
    "Bats": "박쥐",
}

# 태그 중 먹을 수 있는 부위를 알려 주는 것. 빈 문자열은 부위를 밝히지 않은 태그
EDIBLE_TAGS = {
    "edible fruits": "열매", "edible fruit": "열매", "edible flowers": "꽃", "edible leaves": "잎", "edible seeds": "씨",
    "edible roots": "뿌리", "edible nuts": "견과", "edible stems": "줄기", "edible bulbs": "알뿌리", "edible buds": "눈(싹)",
    "edible spice": "향신료", "edible": "", "edible garden": "", "easy edibles": "", "edible weed": "", "edible tree": "",
    "edible shrub": "", "native edible": "", "edible landscaping": "",
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
