@echo off
REM Inicia la app web SOP Prosagro Export. Doble clic para abrir.
cd /d "%~dp0"
".venv\Scripts\streamlit.exe" run "app\app.py"
pause
