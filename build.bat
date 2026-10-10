@echo off
REM Double-click on Windows: install packages and build a single exe into the dist folder
cd /d %~dp0
set PY=python
where python >nul 2>nul || set PY=py
%PY% --version
if errorlevel 1 goto nopy
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Retrying with Tsinghua mirror...
  %PY% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  if errorlevel 1 goto fail
)
%PY% -m PyInstaller --noconfirm --onefile --windowed --name EnvQualityWorkbench --collect-submodules fontTools.ttLib.tables --add-data "tools;tools" app.py
if errorlevel 1 goto fail
echo.
echo Done: dist\EnvQualityWorkbench.exe
start "" "%~dp0dist"
pause
exit /b 0
:nopy
echo [ERROR] Python not found. Install Python 3.10+ from python.org and tick "Add python.exe to PATH".
pause
exit /b 1
:fail
echo [ERROR] Install or build failed. Please send a screenshot of this window.
pause
exit /b 1
