@echo off
title PTZ Control
cd /d "%~dp0"

set "PY_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto :found
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_EXE=python"
    goto :found
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_EXE=py"
    goto :found
)

echo [ERRO] Python nao foi encontrado no sistema.
echo Por favor, instale o Python 3.10 ou superior.
pause
exit /b 1

:found
echo Iniciando o aplicativo PTZ Control...
"%PY_EXE%" main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo O aplicativo encerrou com codigo %ERRORLEVEL%.
    pause
)
