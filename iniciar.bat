@echo off
setlocal enabledelayedexpansion
title Mapa Municipal - SATEL
cd /d "%~dp0"

echo ============================================================
echo   Mapa Municipal - SATEL
echo   Verificacao de ambiente
echo ============================================================
echo.

set "ERRO_FATAL=0"

REM ============================================================
REM 1. Python instalado?
REM ============================================================
echo [1/3] Verificando Python...
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo   [ERRO] Python nao foi encontrado neste computador.
    echo   Abrindo a Microsoft Store para instalacao...
    start ms-windows-store://pdp/?productid=9PNRBTZXMB4Z
    echo.
    echo   Instale o "Python 3.13" pela Store, feche esta janela
    echo   e execute o iniciar.bat novamente.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo   OK - Python !PYVER! encontrado.
echo.

REM ============================================================
REM 2. Dependencias instaladas?
REM ============================================================
echo [2/3] Verificando bibliotecas Python (flask, flask-cors, openpyxl)...
python -c "import flask, flask_cors, openpyxl" >nul 2>nul
if errorlevel 1 (
    echo.
    echo   [AVISO] Faltam bibliotecas necessarias para rodar o sistema.
    choice /C SN /N /M "  Deseja instalar agora? (S = Sim / N = Nao): "
    if errorlevel 2 (
        echo.
        echo   Instalacao cancelada. O sistema provavelmente nao vai funcionar.
        set "ERRO_FATAL=1"
    ) else (
        echo.
        echo   Instalando dependencias, aguarde...
        python -m pip install -r "%~dp0backend\requirements.txt"
        if errorlevel 1 (
            echo.
            echo   [ERRO] Falha ao instalar as dependencias.
            echo   Verifique sua conexao com a internet ou rode manualmente:
            echo     pip install -r backend\requirements.txt
            pause
            exit /b 1
        )
        echo.
        echo   OK - Dependencias instaladas com sucesso.
    )
) else (
    echo   OK - Bibliotecas ja instaladas.
)
echo.

if "!ERRO_FATAL!"=="1" (
    pause
    exit /b 1
)

REM ============================================================
REM 3. Portal Censo IP sincronizado no OneDrive?
REM ============================================================
echo [3/3] Verificando pasta "Portal - Censo IP" no OneDrive...
set "PORTAL_PATH=%USERPROFILE%\OneDrive - SATEL\Portal - Censo IP"
if not exist "%PORTAL_PATH%" (
    echo.
    echo   [AVISO] Pasta nao encontrada em:
    echo     %PORTAL_PATH%
    echo.
    echo   Isso normalmente significa que a pasta "Portal - Censo IP" ainda
    echo   nao foi adicionada como atalho no seu OneDrive, ou a sincronizacao
    echo   ainda nao terminou.
    echo.
    echo   Como resolver:
    echo     1. Abra o link do Portal Censo IP no SharePoint/OneDrive
    echo     2. Clique com o botao direito na pasta "Portal - Censo IP"
    echo     3. Selecione "Adicionar atalho ao OneDrive"
    echo     4. Aguarde o OneDrive terminar de sincronizar
    echo.
    echo   Veja o LEIA-ME.md para o link exato.
    echo.
    choice /C SN /N /M "  Deseja continuar mesmo assim? (S = Sim / N = Nao): "
    if errorlevel 2 (
        exit /b 1
    )
) else (
    echo   OK - Pasta do Portal encontrada.
)
echo.

REM ============================================================
REM 4. Iniciar servidor
REM ============================================================
echo ============================================================
echo   Tudo certo. Iniciando o servidor...
echo ============================================================
echo.

start "" /min cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:5000"

cd /d "%~dp0backend"
python server.py

echo.
echo Servidor encerrado.
pause
