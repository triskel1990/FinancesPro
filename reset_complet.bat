@echo off
title Reset FinancesPro
color 0C
cls

echo.
echo  ========================================
echo   RESET FINANCESPRO — Suppression donnees
echo  ========================================
echo.
echo  Ce script va supprimer :
echo   - Les donnees sur le serveur Railway (PostgreSQL)
echo   - La base de donnees locale (SQLite)
echo   - Les donnees du navigateur (localStorage)
echo.
echo  ATTENTION : Cette action est IRREVERSIBLE !
echo.

set /p confirm="Continuer ? (oui/non) : "
if /i not "%confirm%"=="oui" (
    echo Annule.
    pause
    exit /b 0
)

cd /d "%~dp0"

echo.
echo [1/2] Reset serveur + SQLite...
python reset_tout.py
if errorlevel 1 (
    echo [ERREUR] Le script Python a echoue.
    pause
    exit /b 1
)

echo.
echo [2/2] Ouverture de la page reset navigateur...
start "" "%~dp0reset_local.html"

echo.
echo  Done. Relancez l'app avec lancer_financespro.bat
echo.
pause
