@echo off
chcp 65001 >nul
cd /d "C:\AI\GPT-SoVITS-v2pro-20250604"
if not exist "C:\AI\tmp" mkdir "C:\AI\tmp"
set "TEMP=C:\AI\tmp"
set "TMP=C:\AI\tmp"
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"
set "PATH=C:\AI\GPT-SoVITS-v2pro-20250604\runtime;%PATH%"
echo GPT-SoVITS 실행 중입니다. 이 창은 닫지 마세요. (로그: C:\AI\webui-log.txt)
runtime\python.exe -I -u webui.py zh_CN > "C:\AI\webui-log.txt" 2>&1
pause
