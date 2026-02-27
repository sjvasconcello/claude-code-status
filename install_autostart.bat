@echo off
:: Agrega Claude Monitor al inicio de Windows (Task Scheduler)
:: Ejecutar como Administrador si da error

title Configurar inicio automático - Claude Monitor

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_PATH=%SCRIPT_DIR%claude_status.py"
set "TASK_NAME=ClaudeUsageMonitor"

:: Obtener ruta de pythonw.exe
for /f "delims=" %%i in ('where pythonw 2^>nul') do set "PYTHONW=%%i"
if "%PYTHONW%"=="" (
    for /f "delims=" %%i in ('where python 2^>nul') do set "PYTHONW=%%i"
)

if "%PYTHONW%"=="" (
    echo ERROR: Python no encontrado en PATH.
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
