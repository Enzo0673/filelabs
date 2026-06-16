@echo off
:: ============================================================
:: FileLabs — Script de lancement
:: Double-cliquez sur ce fichier pour démarrer l'application
:: ============================================================

title FileLabs

:: Le script est dans scripts/, on cd au root du projet
cd /d "%~dp0\.."

echo.
echo  =============================================
echo   FileLabs - Installation des dependances
echo  =============================================
echo.

:: Vérifier Python
C:\Windows\py.exe --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERREUR : Python n'est pas installe.
    echo  Telechargez-le sur : https://python.org
    pause
    exit /b 1
)

:: Installer les dépendances si nécessaire
C:\Windows\py.exe -m pip install -r requirements.txt --quiet --disable-pip-version-check

if %errorlevel% neq 0 (
    echo.
    echo  ERREUR lors de l'installation des dependances.
    echo  Essayez : py -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo  =============================================
echo   Demarrage de FileLabs...
echo   Le navigateur va s'ouvrir automatiquement.
echo  =============================================
echo.

:: Lancer le serveur (ouvre le navigateur automatiquement)
C:\Windows\py.exe main.py

pause
