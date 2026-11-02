@echo off
cd /d "%~dp0"
echo [1/3] 고침표와 자료를 반영해 사이트 파일을 다시 만듭니다.
python -I pipeline\build_care.py data site\data\care || goto :fail
echo [2/3] 공개 전 점검을 합니다. 문제가 있으면 여기서 멈춥니다.
python -I pipeline\check_site.py site || goto :fail
echo [3/3] GitHub에 올리고 공개 사이트를 갱신합니다.
git add -A
git commit -m "사이트 갱신"
git push origin main
for /f %%i in ('git subtree split --prefix site main') do set SPLIT=%%i
git push -f origin %SPLIT%:gh-pages
echo.
echo 1~3분 뒤 https://dkaahs123123-lang.github.io/plant-care-guide/ 에 반영됩니다.
pause
exit /b 0

:fail
echo.
echo 문제가 있어 공개하지 않았습니다. 위의 내용을 확인해 주세요.
pause
exit /b 1
