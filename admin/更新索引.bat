@echo off
chcp 936 >nul
rem ============================================================
rem  Internal tool library - rebuild the library page
rem
rem  This file is deliberately pure ASCII.
rem  cmd.exe decodes .bat files with the console codepage, which
rem  differs from machine to machine, so any Chinese text written
rem  here would show up as garbage on somebody else's PC.
rem  All Chinese output comes from build_index.py, where the
rem  encoding is guaranteed.
rem
rem  No parenthesised blocks on purpose: "if errorlevel" inside a
rem  block is a classic source of surprises.
rem ============================================================
setlocal
pushd "%~dp0"

set "PYEXE="

rem ---- 0) bundled runtime: works on a machine with no Python at all ----
if not exist "%~dp0..\runtime\python.exe" goto NORT
set PYEXE="%~dp0..\runtime\python.exe"
goto RUN
:NORT

rem ---- 1) prefer the official "py" launcher from python.org ----
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYEXE=py -3"
if defined PYEXE goto RUN

rem ---- 2) then "python" on PATH ----
python -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYEXE=python"
if defined PYEXE goto RUN

echo.
echo   [!] Python 3 was not found on this computer.
echo.
echo       Install it from:
echo         https://www.python.org/downloads/windows/
echo.
echo       During setup, TICK this box:
echo         [x] Add python.exe to PATH
echo.
echo       Then double-click this file again.
echo.
pause
popd
exit /b 1

:RUN
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
%PYEXE% "%~dp0build_index.py" %*
set "RC=%ERRORLEVEL%"

if "%RC%"=="0" goto DONE
echo.
echo   [!] Stopped with exit code %RC%. See the messages above.
echo.
pause
popd
exit /b %RC%

:DONE
rem 扫完顺手把网页打开，双击一次就够
start "" "%~dp0软件库网站.html"
popd
exit /b 0
