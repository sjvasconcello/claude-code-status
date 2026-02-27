@echo off
:: Claude Usage Monitor - Lanzador para Windows
:: Doble clic aquí para iniciar el monitor

title Claude Monitor

:: Verificar que Python esté instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo Python no está instalado.
    echo Descárgalo desde: https://www.python.org/downloads/
    echo Asegúrate de marcar "Add Python to PATH" al instalar.
    pause
    exit /b 1
)

:: Verificar/instalar dependencias (solo la primera vez, opcional)
echo Verificando dependencias...
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo Instalando requests...
    pip install requests --quiet
)

:: Lanzar la app en segundo plano (sin ventana de consola)
start /B pythonw claude_status.py

echo Claude Monitor iniciado.
echo Para cerrarlo, haz clic derecho en el widget y selecciona "Cerrar".
timeout /t 2 >nul
