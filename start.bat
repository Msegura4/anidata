@echo off
chcp 65001 >nul
echo.
echo 🎌 AniData Lab — Demarrage de l'environnement
echo ==============================================
echo.

REM --- Verifier Docker ---
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ❌ Docker n'est pas demarre !
    echo    Lancez Docker Desktop et reessayez.
    pause
    exit /b 1
)
echo ✅ Docker est operationnel

REM --- Verifier les donnees ---
echo.
echo 📦 Verification des donnees...
set MISSING=0

if exist "data\anime.csv" ( echo    ✅ anime.csv ) else ( echo    ❌ anime.csv - MANQUANT & set MISSING=1 )
if exist "data\rating_complete.csv" ( echo    ✅ rating_complete.csv ) else ( echo    ❌ rating_complete.csv - MANQUANT & set MISSING=1 )
if exist "data\anime_with_synopsis.csv" ( echo    ✅ anime_with_synopsis.csv ) else ( echo    ❌ anime_with_synopsis.csv - MANQUANT & set MISSING=1 )

if %MISSING%==1 (
    echo.
    echo ⚠️  Des fichiers sont manquants !
    echo    Telechargez-les depuis :
    echo    https://www.kaggle.com/datasets/hernan4444/anime-recommendation-database-2020
    echo.
    set /p CONTINUE="Continuer quand meme ? (O/N) "
    if /i not "%CONTINUE%"=="O" exit /b 1
)

REM --- Lancement ---
echo.
echo 🐳 Lancement des services Docker...
echo    Premier lancement : ~5-10 min pour telecharger les images
echo.

docker compose up -d

echo.
echo ⏳ Attente du demarrage (45 secondes)...
timeout /t 45 /nobreak >nul

echo.
echo ==============================================
echo 🎌 AniData Lab est pret !
echo.
echo    📊 Grafana        → http://localhost:3000  (admin / anidata)
echo    🔄 Airflow        → http://localhost:8080  (admin / admin)
echo    🔍 Elasticsearch  → http://localhost:9200
echo.
echo    💻 Ouvrir dans VS Code : code .
echo.
echo    Pour arreter : docker compose down
echo ==============================================
echo.
pause
