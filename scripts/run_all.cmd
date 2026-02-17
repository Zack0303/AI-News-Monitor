@echo off
setlocal
set MODE=%1
if "%MODE%"=="" set MODE=llm
powershell -ExecutionPolicy Bypass -File "%~dp0run_all.ps1" -Mode %MODE%

