@echo off
cd /d "%~dp0"
set "LOG=%~dp0launch-error.log"
del "%LOG%" >nul 2>&1

set "PY="
if exist "D:\WorkBuddyData\venvs\py313\Scripts\python.exe" set "PY=D:\WorkBuddyData\venvs\py313\Scripts\python.exe"
if not defined PY if exist "D:\WorkBuddyData\venvs\gate\Scripts\python.exe" set "PY=D:\WorkBuddyData\venvs\gate\Scripts\python.exe"
if not defined PY goto :try_path
goto :have_py

:try_path
where py >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%I"
)
if defined PY goto :have_py
where python >nul 2>&1
if errorlevel 1 goto :no_python
for /f "delims=" %%I in ('where python') do (
  echo %%I | find /i "WindowsApps" >nul
  if errorlevel 1 (
    set "PY=%%I"
    goto :have_py
  )
)
goto :no_python

:have_py
echo Using: %PY%
"%PY%" -c "import pypinyin" >nul 2>&1
if errorlevel 1 (
  echo Installing pypinyin from local vendor ...
  "%PY%" -m pip install -q --no-index --find-links=vendor pypinyin 1>>"%LOG%" 2>>&1
  if errorlevel 1 (
    echo Offline vendor install failed, trying Tsinghua mirror ...
    "%PY%" -m pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple pypinyin 1>>"%LOG%" 2>>&1
    if errorlevel 1 (
      echo [ERROR] pip install pypinyin failed. See launch-error.log
      echo [ERROR] pip install pypinyin failed. >> "%LOG%"
      pause
      exit /b 1
    )
  )
)

echo Starting browser UI (no tkinter needed) ...
"%PY%" run.py gui
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo [ERROR] run.py gui exited with code %RC%
  echo [ERROR] run.py gui exited with code %RC% >> "%LOG%"
  echo Check launch-error.log in this folder.
  pause
  exit /b %RC%
)
exit /b 0

:no_python
echo [ERROR] Python not found. > "%LOG%"
echo Expected: D:\WorkBuddyData\venvs\py313\Scripts\python.exe >> "%LOG%"
echo.
echo [ERROR] Python not found.
echo Expected: D:\WorkBuddyData\venvs\py313\Scripts\python.exe
echo Or install Python 3 and tick Add to PATH.
echo Details: launch-error.log
echo.
pause
exit /b 1
