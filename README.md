# SOP Prosagro Export

Sistema de gestión, costeo y rentabilidad por contenedor para exportación de
fruta de **Prosagro Export S.A.S.** (gulupa, uchuva y otros exóticos).

Migra el modelo que hoy corre en dos macros VBA + Excel a una app web con base de
datos y vista única.

## 📚 Documentación
- **[El proceso de negocio](docs/01_proceso_negocio.md)** — flujo de punta a punta: maquila → ingreso → liquidación → contenedor → cliente.
- **[Manual de uso](docs/02_manual_uso.md)** — cómo usar la app, sección por sección.
- **[Anexo técnico](docs/03_tecnico.md)** — modelo de datos, cómo levantar, respaldar y migrar.

## Stack
- **Python 3.13+** + **Streamlit** (app web — entras por navegador)
- **PostgreSQL 17** (base de datos central)
- **pandas** (motor de cálculo del SOP y conciliaciones)
- **openpyxl / pdfplumber** (lectura de reportes Excel y PDFs)
- **PyA / SAG ERP** (vía API REST — emisión de DR, factura electrónica y carga de costos)
- **Twilio** (envío de reportes a productores)
- **Plotly** (gráficos que replican el tablero Power BI dentro de la app)
- Despliegue futuro: Docker + Azure App Service + Azure Database for PostgreSQL Flexible.

## Estructura
- `db/`       — esquema SQL (migraciones aditivas) y scripts de carga inicial.
- `ingesta/`  — parsers de reportes de maquila, packing lists, facturas y liquidaciones.
- `app/`      — interfaz Streamlit (`app.py` + páginas en `app/pages/`).
- `data/`     — archivos de trabajo locales (NO se versiona).
- `docs/`     — documentación.
- `scripts/`  — utilidades CLI (carga inicial desde Excel histórico, backups, etc.).

## Flujo
```
Maquila (Excel)  ─┐
Packing list     ─┤
Reportes calidad ─┼─►  Postgres  ─►  motor SOP (pandas)  ─►  PyA (API)
Facturas (XML)   ─┤                                       ─►  Twilio (PDF al productor)
Captura manual   ─┘                                       ─►  Power BI replicado en Streamlit
```

## Arranque local
1. Instalar PostgreSQL 17 (ya está) y crear la base:
   ```bash
   psql -U postgres -c "CREATE USER prosagro WITH PASSWORD 'prosagro';"
   psql -U postgres -c "CREATE DATABASE prosagro OWNER prosagro;"
   ```
2. Crear el `.env` a partir de `.env.example`.
3. Aplicar el esquema:
   ```bash
   ./scripts/aplicar_migraciones.sh
   ```
4. Crear y activar el entorno:
   ```bash
   python -m venv .venv
   .venv/Scripts/python -m pip install -r requirements.txt
   ```
5. Doble clic a `iniciar_app.bat` o:
   ```bash
   .venv/Scripts/streamlit run app/app.py
   ```

## Estado
🚧 **Fase 0** — esquema + Streamlit base + carga inicial desde Excel histórico.
Roadmap completo en `docs/03_tecnico.md`.

## Repos relacionados
- `nexfresh-sop` — gemelo para NexFresh (aguacate). Mismo stack, modelo análogo.
  Reutilizamos patrones de ahí cuando aplica (PyA, Twilio, dashboards).
