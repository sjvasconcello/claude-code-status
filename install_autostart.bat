@echo off
:: Agrega Claude Monitor al inicio de Windows (Task Scheduler)
:: Ejecutar como Administrador si da error

title Configurar inicio automático - Claude Monitor

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_PATH=%SCRIPT_DIR%claude_status.py"
set "TASK_NAME=ClaudeUsageMonitor"

:: Verificar que uv esté instalado
uv --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: uv no está instalado.
    echo Instálalo desde: https://docs.astral.sh/uv/getting-started/installation/
    echo O con PowerShell: irm https://astral.sh/uv/install.ps1 ^| iex
    pause
    exit /b 1
)

:: Sincronizar dependencias para asegurar que el entorno virtual existe
echo Sincronizando dependencias...
uv sync --quiet

:: Usar pythonw del entorno virtual creado por uv
set "PYTHONW=%SCRIPT_DIR%.venv\Scripts\pythonw.exe"
if not exist "%PYTHONW%" (
    echo ERROR: No se encontró pythonw.exe en el entorno virtual.
    echo Asegúrate de haber ejecutado start.bat al menos una vez.
    pause
    exit /b 1
)

echo Configurando inicio automático...
echo   Script:  %SCRIPT_PATH%
echo   Python:  %PYTHONW%
echo   Tarea:   %TASK_NAME%
echo.

:: Crear tarea programada que se ejecuta al iniciar sesión
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHONW%\" \"%SCRIPT_PATH%\"" /sc onlogon /delay 0000:30 /f

if errorlevel 1 (
    echo.
    echo No se pudo crear la tarea. Intenta ejecutar este archivo como Administrador.
) else (
    echo.
    echo Inicio automático configurado correctamente.
    echo Claude Monitor se iniciará 30 segundos después de iniciar sesión.
    echo.
    echo Para desactivar el inicio automático, ejecuta:
    echo   schtasks /delete /tn "%TASK_NAME%" /f
)

pause
