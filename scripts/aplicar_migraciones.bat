@echo off
REM Aplica todas las migraciones SQL del directorio db\ en orden alfabético.
REM Doble clic o desde cmd. Lee DATABASE_URL del .env.
cd /d "%~dp0\.."

if not exist .env (
    echo Falta el archivo .env. Copia .env.example y rellena DATABASE_URL.
    pause
    exit /b 1
)

REM Cargar variables del .env
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if not "%%a"=="" if not "%%a:~0,1%"=="#" set %%a=%%b
)

set PSQL="C:\Program Files\PostgreSQL\17\bin\psql.exe"

echo Aplicando migraciones a %PGDATABASE%@%PGHOST%...
for %%f in (db\*.sql) do (
    echo   - %%f
    %PSQL% "%DATABASE_URL%" -v ON_ERROR_STOP=1 -q -f "%%f"
    if errorlevel 1 (
        echo ERROR en %%f
        pause
        exit /b 1
    )
)
echo OK
pause
