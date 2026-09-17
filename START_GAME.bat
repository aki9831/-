@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo Python не найден.
    echo Установите Python 3.10 или новее с сайта:
    echo https://www.python.org/downloads/windows/
    echo При установке включите Add Python to PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Первый запуск: подготавливаю игру...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Не удалось создать окружение игры.
        pause
        exit /b 1
    )
)

set "GAME_PY=.venv\Scripts\python.exe"
%GAME_PY% -m pip install --disable-pip-version-check --quiet pygame
if errorlevel 1 (
    echo Не удалось установить pygame. Проверьте интернет-соединение.
    pause
    exit /b 1
)

start "Shadow Parkour" /wait "%GAME_PY%" main.py
endlocal
