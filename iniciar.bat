@echo off
setlocal enabledelayedexpansion
title Mapa Municipal
cd /d "%~dp0"

echo ============================================================
echo   Mapa Municipal
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
echo [2/3] Verificando bibliotecas Python (flask, flask-cors, openpyxl, dotenv)...
python -c "import flask, flask_cors, openpyxl, dotenv" >nul 2>nul
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
REM 3. Arquivo .env configurado?
REM ============================================================
echo [3/3] Verificando arquivo .env (caminhos da planilha e das pastas)...
if not exist "%~dp0.env" (
    echo.
    echo   [AVISO] Arquivo .env nao encontrado.
    echo   Esses caminhos sao especificos da empresa/computador e por isso
    echo   nao vem prontos no projeto.
    echo.
    if exist "%~dp0.env.example" (
        copy /y "%~dp0.env.example" "%~dp0.env" >nul
        echo   Criei o arquivo .env a partir de .env.example.
        echo   Abrindo no Bloco de Notas para voce preencher os caminhos reais...
        start "" notepad "%~dp0.env"
        echo.
        echo   Preencha os caminhos, salve o arquivo, feche e execute o
        echo   iniciar.bat novamente.
    ) else (
        echo   [ERRO] .env.example tambem nao foi encontrado. Peca este
        echo   arquivo para quem administra o projeto.
    )
    echo.
    pause
    exit /b 1
) else (
    echo   OK - Arquivo .env encontrado.
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
