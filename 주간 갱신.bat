@echo off
cd /d "%~dp0"
rem 매주 자동 실행: 공식 자료를 다시 받아 점검 후 공개 사이트를 갱신한다. 기록은 logs 폴더에 남는다.
python -I pipeline\weekly_update.py
