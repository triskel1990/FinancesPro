@echo off
title FinancesPro — Démarrage
color 0A
cls

echo.
echo  ========================================
echo   FinancesPro - Démarrage automatique
echo  ========================================
echo.

:: Aller dans le bon dossier
cd /d "%~dp0"

:: Vérifier que Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo  Installez Python depuis https://www.python.org
    pause
    exit /b 1
)

:: Vérifier que app.py existe
if not exist "app.py" (
    echo  [ERREUR] app.py introuvable dans ce dossier.
    echo  Placez ce .bat dans le meme dossier que app.py
    pause
    exit /b 1
)

:: Installer les dépendances si besoin
if not exist ".deps_installed" (
    echo  Installation des dependances...
    python -m pip install -r requirements.txt --quiet
    echo. > .deps_installed
    echo  Dependances installees.
)

:: Lancer Flask en arrière-plan
echo  Lancement de FinancesPro...
echo  Ouverture du navigateur dans 3 secondes...
echo.

:: Démarrer Flask dans une nouvelle fenêtre minimisée
start /min cmd /c "python app.py 2>&1 | findstr /V \"^$\""

:: Attendre que Flask soit prêt
timeout /t 3 /nobreak >nul

:: Ouvrir le navigateur
start "" "http://localhost:5000"

echo  FinancesPro est en cours d'execution.
echo  Fermez cette fenetre pour ARRETER l'application.
echo.
echo  URL : http://localhost:5000
echo  ----------------------------------------
echo  Appuyez sur une touche pour arreter...
echo.
pause >nul

:: Arrêter Flask
taskkill /f /im python.exe /fi "WINDOWTITLE eq FinancesPro*" >nul 2>&1
echo  Application arretee.
