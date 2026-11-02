@echo off
cd /d "%~dp0"
rem 출처 기관이 고친 내용을 따라가기 위해 공식 자료를 새로 받아 사이트를 갱신한다.
rem 예전 자료는 data\raw_old 로 옮겨 두고 새로 받는다. 몇 시간 걸릴 수 있다.
echo 공식 자료를 새로 받습니다. 몇 시간 걸릴 수 있어요.
if exist data\raw_old rmdir /s /q data\raw_old
move data\raw data\raw_old >nul
mkdir data\raw
move data\raw_old\kfs data\raw\kfs >nul
move data\raw_old\wfo-2026-06 data\raw\wfo-2026-06 >nul
python -I pipeline\fetch_ncpms.py data\raw\ncpms
python -I pipeline\fetch_garden.py data\raw\garden
python -I pipeline\fetch_airplants.py data\raw\airplant
python -I pipeline\fetch_smartfarm.py data\raw\smartfarm
python -I pipeline\fetch_nongsaro_cases.py data\raw\cases
python -I pipeline\fetch_ncsu.py data\plants.db data\raw\ncsu
move data\raw_old\climate data\raw\climate >nul
call "사이트 올리기.bat"
