@echo off
REM Auto-arranque del servidor SOP Prosagro Export (Streamlit) para toda la red local (puerto 8502).
REM Se ejecuta con Tarea programada "ProsagroSOP" al iniciar sesion.
REM Nota: puerto 8502 para no chocar con NexFresh (8501) si conviven en la misma maquina.
cd /d "%~dp0"
".venv\Scripts\streamlit.exe" run "app\app.py" --server.headless=true --server.port=8502
