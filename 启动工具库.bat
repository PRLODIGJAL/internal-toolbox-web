@echo off
rem ============================================================
rem  Internal tool library - start the local helper, open the page
rem
rem  Order of business:
rem    1. open the page right away (it carries the last scan inside it,
rem       so it paints in a second or two) - no more staring at a black
rem       window for ten seconds
rem    2. start the helper in the foreground; the page probes
rem       /__ping and swaps itself over to http://127.0.0.1:port/
rem       as soon as the helper answers
rem
rem  Three ways to find a Python, in this order:
rem    1. runtime\python.exe   shipped with this folder, nothing to install
rem    2. py -3 / python       whatever is already on this computer
rem    3. none of them         just open the web page directly
rem
rem  Why runtime first: it is the only way a machine with no Python can
rem  run the helper, and it also starts faster than a system Python
rem  (no site-packages to scan).
rem
rem  Chinese path is written in GBK and the codepage is forced to 936
rem  right away, so cmd.exe reads it correctly on any Windows.
rem  All user-facing Chinese text comes from serve.py / the html.
rem ============================================================
chcp 936 >nul
setlocal
pushd "%~dp0"

set "PYCMD="

rem ---- 1) bundled runtime ----
if exist "%~dp0runtime\python.exe" (
    set PYCMD="%~dp0runtime\python.exe"
    goto RUN
)

rem ---- 2) Python already installed on this computer ----
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3"
if defined PYCMD goto RUN

python -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto RUN

rem ---- 3) no Python at all ----
rem  This used to print "install Python 3" and quit, which threw away a
rem  perfectly usable path: a browser alone can still read the folder
rem  (it asks for permission once) and can list, search and download.
rem  Only "copy to clipboard" and "open folder" need the helper, and the
rem  page turns those two into "copy the path" automatically.
goto PLAIN

:RUN
title Internal Tool Library
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

rem ---- the page goes up first, the helper catches up ----
rem  Python needs 8-11 s from this network share. Measured 2026-11-09 on
rem  the P: drive with the bundled runtime: even "-c pass" costs 6.8-8.4 s,
rem  and importing the modules the helper needs costs 10.6-10.8 s. Opening
rem  the page first hides that whole wait - the list is already baked into
rem  the page, so the user sees the tools immediately.
rem  --no-open stops serve.py from opening a second tab on top of this one.
start "" "%~dp0admin\Èí¼þ¿âÍøÕ¾.html"
%PYCMD% "%~dp0admin\serve.py" --no-open %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
popd
exit /b %RC%

:PLAIN
title Internal Tool Library
echo.
echo   ==========================================================
echo     Internal Tool Library - plain web page mode
echo   ==========================================================
echo.
echo   No Python found on this computer, so the helper cannot start.
echo   Opening the page directly instead.
echo.
echo     works     : browse, search, download
echo     not works : copy-to-clipboard, open-folder
echo                 (those two buttons copy the file path instead;
echo                  paste it into the Explorer address bar)
echo.
echo   Put the "runtime" folder back next to this file for full mode.
echo.
echo   ==========================================================
start "" "%~dp0admin\Èí¼þ¿âÍøÕ¾.html"
timeout /t 6 >nul
popd
exit /b 0
