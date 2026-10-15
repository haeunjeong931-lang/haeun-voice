@echo off
chcp 65001 >nul
echo GPT-SoVITS 설치를 시작합니다. 창을 닫지 마세요.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0GPT-SoVITS-install.ps1"
echo.
pause
