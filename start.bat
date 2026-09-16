@echo off
title ML Insights

echo.
echo  ============================================
echo   ML Insights - Iniciando servidor...
echo  ============================================
echo.

REM Verificar si existe .env
if not exist .env (
    echo  [!] No encontre el archivo .env
    echo      Copia .env.example a .env y completalo con tus credenciales.
    echo.
    pause
    exit /b 1
)

REM Instalar dependencias si no estan instaladas
python -m pip show flask >nul 2>&1
if errorlevel 1 (
    echo  Instalando dependencias...
    python -m pip install -r requirements.txt
    echo.
)

echo  Servidor disponible en: http://localhost:5050
echo  Presiona Ctrl+C para detener.
echo.

python app.py

pause
