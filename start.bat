@echo off
:: Claude Usage Monitor - Lanzador para Windows (usa uv)
:: Doble clic aquí para iniciar el monitor

title Claude Monitor

:: Verificar que uv esté instalado
uv --version >nul 2>&1
if errorlevel 1 (
    echo uv no está instalado.
    echo Instálalo desde: https://docs.astral.sh/uv/getting-started/installation/
    echo O con PowerShell: irm https://astral.sh/uv/install.ps1 ^| iex
    pause
    exit /b 1
)

:: Sincronizar dependencias (crea el entorno virtual si es necesario)
echo Sincronizando dependencias...
uv sync --quiet

:: Lanzar la app en segundo plano (sin ventana de consola)
start /B .venv\Scripts\pythonw.exe claude_status.py

echo Claude Monitor iniciado.
echo Para cerrarlo, haz clic derecho en el widget y selecciona "Cerrar".
timeout /t 2 >nul
