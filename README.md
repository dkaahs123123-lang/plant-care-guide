# 식물 돌봄 도감

전 세계 식물의 학명, 분류, 다른 이름을 찾아보고, 공식 출처가 있는 재배 정보와 병해충 정보를 보여 주는 웹사이트입니다. 컴퓨터, 핸드폰, 공개 웹사이트에서 같은 파일로 동작합니다.

## 실행하기 (내 컴퓨터)

`식물도감 실행.bat`을 더블클릭하면 브라우저에 http://localhost:8790 이 열립니다. 검은 창을 닫으면 종료됩니다.

## 공개 사이트

https://dkaahs123123-lang.github.io/plant-care-guide/

`site/` 폴더를 `gh-pages` 가지로 올려 GitHub Pages에서 보여 줍니다. 사이트를 고친 뒤 `사이트 올리기.bat`을 실행하면 1~3분 뒤 반영됩니다. 고칠 때는 `site/sw.js`의 `VERSION` 값을 바꿔야 방문자 기기에 저장된 예전 파일이 지워집니다.

## 틀린 정보를 바로 고치는 법

1. 사이트의 각 정보 칸에 있는 **틀린 내용 신고** 버튼으로 신고가 GitHub 이슈로 들어온다.
2. 확인되면 [data/corrections.tsv](data/corrections.tsv)에 한 줄을 적는다 (항목 감추기, 대표 이름 바꾸기 등). 작물·학명 연결이 틀렸으면 `data/crop_map.tsv`, `data/airplant_map.tsv`, `data/name_fixes.tsv` 를 고친다.
3. `사이트 올리기.bat`을 실행한다. 다시 만들기 → 공개 전 점검(`pipeline/check_site.py`) → 공개 순서로 진행되고, 점검에서 문제가 나오면 공개하지 않는다.
4. 고친 내역은 사이트의 **고친 내역** 페이지에 이유와 함께 공개된다. 출처 기관의 자료 자체가 틀렸으면 그 기관에도 알린다.

출처 기관이 고친 내용을 따라가려면 `자료 갱신.bat`으로 공식 자료를 새로 받는다.

## 원칙

- 모든 정보에는 출처를 표시합니다.
- 공식 자료가 없는 내용은 만들어 넣지 않고 "아직 연결되지 않음"으로 표시합니다.
- 일부 자료가 비영리 조건(공공누리 제2유형 등)이므로 광고나 유료 운영을 하지 않습니다.

## 단계별 데이터

| 단계 | 내용 | 출처 | 상태 |
|---|---|---|---|
| 1 | 모든 식물의 학명, 과, 속, 이명 | WFO Plant List 2026-06 (CC0) | 완료 |
| 1 | 한국어·영어 일반 이름, 관찰 사진 | GBIF API (실시간, 자료별 라이선스) | 완료 |
| 2 | 재배 정보: 정원식물 104종 | 한국수목원정원관리원 백두대간 정원식물정보 (공공데이터포털, 이용 제한 없음) | 연결됨 |
| 2 | 재배 정보: 실내식물 64종 | 농촌진흥청 국립원예특작과학원 공기정화식물 (공공데이터포털, 공공누리 제2유형: 출처표시·비영리) | 연결됨 |
| 2 | 재배 정보: 실내정원용 식물(217종 중 206), 건조에 강한 실내식물(97종 중 74) | 농촌진흥청 농사로 Open API (실내정원용 식물 공공누리 제3유형, 건조에 강한 실내식물 제4유형: 변경금지). 학명으로 연결, 품종·교배종만 적힌 것은 속 전체에 연결 | 연결됨 |
| 2 | 텃밭가꾸기 (작물 글 77개) | 농촌진흥청 농사로 Open API (공공누리 제4유형). 글 제목의 작물 이름으로 연결, 담당자 이름·연락처 줄과 그림은 뺌 | 연결됨 |
| + | 쓰임과 효능: 민간약초 (178종 중 177) | 농촌진흥청 농사로 약초정보 (공공누리 제3유형). 민간요법은 검증되지 않은 기록이라는 안내와 함께 접어서 보여 줌 | 연결됨 |
| + | 첫 화면: 이번 주 농사 정보 | 농촌진흥청 농사로 주간농사정보 (공공누리 제1유형) | 연결됨 |
| 2 | 스마트팜 최적 환경 (완숙토마토, 딸기, 파프리카) | 농촌진흥청 스마트팜 생산성 향상 모델 (공공데이터포털, 이용 제한 없음). 생육상태별 기능만 사용 (일사량별 기능은 API 서버 오류) | 연결됨 |
| + | 인터넷 재배 정보 (빛, 흙, 관리 난이도, 견디는 추위, 독성 등) | NC State Extension Gardener Plant Toolbox (미국 노스캐롤라이나 주립대). 정해진 항목 값만 한국어로 옮기고 설명 글은 가져오지 않음. 공공기관 자료와 구분해 표시 | 연결됨 |
| - | 한국어 이름, 과 국명, 꽃 피는 달, 보호·특산 여부 (2,962종) | 산림청 표준식물종정보 (공공데이터포털 파일, 이용 제한 없음) | 연결됨 (2,811종). 학명이 맞지 않은 151종은 `data/kfs_unmatched.txt` |
| 3 | 병해충 정보 (작물 215종) | NCPMS Open API (농촌진흥청, 비영리·출처 표시) | 연결됨 |
| + | 쓰임과 효능: 식품 원료로 쓸 수 있는지, 쓸 수 있는 부위 | 식품의약품안전처 수입식품 원료정보 (공공데이터포털, 이용 제한 없음). 학명으로 연결. 한국어 이름이 없는 식물은 원료 이름을 대표 이름으로 씀 | 연결됨 |
| + | 쓰임과 효능: 영양성분 (먹는 부분 100g당) | 농촌진흥청 국립식량과학원 국가표준식품성분 DB 10.4 (공공데이터포털, 공공누리 제4유형: 출처표시·비영리·변경금지). '생것'만, 식품 이름으로 연결하고 값은 바꾸지 않음 | 연결됨 |
| + | 쓰임과 효능: 약재·먹는 법·꿀벌·독에 관한 문장, 공기정화 등급, 찾아오는 동물, 독성 | 위 정원식물·공기정화식물·NC State 자료에서 골라 모음 | 연결됨 |

## 데이터 다시 만들기

```
python -I pipeline/build_wfo_db.py data/raw/wfo-2026-06/wfo_plantlist_2026-06.zip data/plants.db
python -I pipeline/export_site_data.py data/plants.db site/data
```

재배·병해충 자료 (`.env`에 키 필요):

```
python -I pipeline/fetch_ncpms.py data/raw/ncpms
python -I pipeline/fetch_garden.py data/raw/garden
python -I pipeline/fetch_airplants.py data/raw/airplant
python -I pipeline/fetch_ncsu.py data/plants.db data/raw/ncsu
python -I pipeline/fetch_smartfarm.py data/raw/smartfarm
python -I pipeline/fetch_climate.py data/raw/climate
python -I pipeline/build_care.py data site/data/care
```

인터넷 재배 정보는 자동 수집을 허락하는 곳만 씁니다. 미주리 식물원(robots.txt에서 Plant Finder 수집 금지)과 RHS(자료 수집 금지 약관)는 수집하지 않고 링크만 겁니다. NC State 항목 값의 한국어 번역표는 [pipeline/ncsu_ko.py](pipeline/ncsu_ko.py)에 있습니다.

산림청 표준식물종정보는 [공공데이터포털](https://www.data.go.kr/data/15092915/fileData.do)에서 CSV를 받아 `data/raw/kfs/standard_plants.csv`로 저장합니다.

- 공기정화식물 자료 번호와 학명의 연결은 [data/airplant_map.tsv](data/airplant_map.tsv)에 있습니다. 원문 학명의 오타를 바로잡거나 학명이 없는 경우 이름으로 정한 내용은 메모 칸에 적어 두었습니다.

- NCPMS 작물명과 학명의 연결은 [data/crop_map.tsv](data/crop_map.tsv)에 있습니다. 여러 종을 묶은 작물명(장미, 백합 등)은 속에 연결합니다.
- 출처 학명과 WFO 표기가 다른 경우는 [data/name_fixes.tsv](data/name_fixes.tsv)로 맞춥니다.
- 현장 진단 사례는 품목명으로 [data/case_crop_map.tsv](data/case_crop_map.tsv)를 거쳐 연결하고, 원문 품목·제목이 내용과 다른 사례는 [data/case_fix.tsv](data/case_fix.tsv)로 하나씩 바로잡습니다(사이트에 이유를 안내). 원문 '재배작물' 칸에 다른 식물이 적힌 부분은 자동으로 빼고 `data/cases_mixed.txt`에 남깁니다.
- 사례의 개인정보 기준은 [pipeline/privacy.py](pipeline/privacy.py) 한 곳에 있고, 자료 만들기와 올리기 전 점검이 같은 기준을 씁니다.
- 표를 고친 뒤에는 마지막 줄만 다시 실행하면 됩니다.

WFO는 매년 6월과 12월에 새 판을 냅니다. 새 판을 내려받아 위 두 줄을 다시 실행하고, `site/sw.js`의 `VERSION` 값을 바꾸면 됩니다.

## 폴더 구조

- `pipeline/` 데이터를 내려받고 변환하는 스크립트
- `data/raw/` 내려받은 원본 (용량이 커서 Git에 올리지 않음)
- `data/plants.db` 변환한 데이터베이스 (Git에 올리지 않음)
- `site/` 웹사이트 전체. 이 폴더만 호스팅에 올리면 공개됩니다.
- `site/data/care/<WFO 번호>.json` 2·3단계 재배·병해충 정보가 들어갈 자리

## API 키

`.env.example`을 복사해 `.env`를 만들고 발급받은 키를 넣으세요. `.env`는 Git에 올라가지 않습니다.
