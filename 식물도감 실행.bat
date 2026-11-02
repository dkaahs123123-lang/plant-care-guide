@echo off
chcp 65001 >nul
cd /d "%~dp0site"
echo 식물 돌봄 도감을 실행합니다. 이 창을 닫으면 프로그램이 종료됩니다.
start "" http://localhost:8790/
python -m http.server 8790 --bind 127.0.0.1
