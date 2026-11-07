@echo off
cd /d "%~dp0"
rem 매일 자동 실행: 전국 공영도매시장 시세(최근 며칠)를 받아 점검 후 공개 사이트를 갱신한다. 기록은 logs 폴더에 남는다.
python -I pipeline\weekly_update.py --daily
