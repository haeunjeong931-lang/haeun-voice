@echo off
chcp 65001 >nul
title 보이스 스튜디오 (이 창을 닫으면 꺼져요)
cd /d "C:\AI\GPT-SoVITS-v2pro-20250604"
if not exist "C:\AI\tmp" mkdir "C:\AI\tmp"
set "TEMP=C:\AI\tmp"
set "TMP=C:\AI\tmp"
set "PYTHONIOENCODING=utf-8"
set "PATH=C:\AI\GPT-SoVITS-v2pro-20250604\runtime;%PATH%"
echo 보이스 스튜디오를 켜는 중이에요. 잠시 뒤 브라우저가 열려요.
echo 쓰는 동안 이 창은 닫지 말고 최소화만 해 주세요.
start "" /b cmd /c "timeout /t 6 >nul & start http://localhost:9880"
runtime\python.exe -I -u "C:\AI\haeun-voice\server.py" > "C:\AI\haeun-voice\server-log.txt" 2>&1
echo.
echo 보이스 스튜디오가 멈췄어요. C:\AI\haeun-voice\server-log.txt 를 Claude에게 보여 주세요.
pause
