@echo off
setlocal
set MODE=%1
if "%MODE%"=="" set MODE=heuristic
powershell -ExecutionPolicy Bypass -File "%~dp0run_daily.ps1" -Mode %MODE%
