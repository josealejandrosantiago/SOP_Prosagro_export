# Anexo técnico

## Stack
- **Python ≥ 3.13** (probado con 3.14).
- **Streamlit ≥ 1.40** (UI).
- **PostgreSQL 17** (BD).
- **pandas ≥ 2.2** (motor de cálculo).
- **psycopg ≥ 3.2** (driver Postgres).
- **openpyxl ≥ 3.1** (lectura xlsx maquila/packing).
- **pdfplumber ≥ 0.11** (futuro: parser liquidaciones cliente).
- **reportlab ≥ 4.2** (generación PDFs de liquidación).
- **plotly ≥ 5.24** (tableros estilo Power BI).
- **twilio ≥ 9.3** (envíos WhatsApp/SMS).
- **bcrypt ≥ 4.2** (hash de claves del login local).

## Esquema de BD

Schema único `prosagro`. Migraciones en `db/*.sql` aplicadas en orden alfabético:

| #  | Archivo                       | Contenido                                                 |
| -- | ----------------------------- | --------------------------------------------------------- |
| 00 | `00_extensiones.sql`          | Extensiones (pgcrypto, unaccent, pg_trgm), schema.        |
| 01 | `01_maestros.sql`             | zonas, frutas, monedas, calendario_pagos, trm.            |
| 02 | `02_terceros.sql`             | productores, clientes, proveedores, usuarios.             |
| 03 | `03_vigencias_precios.sql`    | precio_fruta, precio_certificacion.                       |
| 04 | `04_fruta.sql`                | ingresos, fruta_export, fruta_nacional, kg_consolidado.   |
| 05 | `05_calidad_proyeccion.sql`   | causales_rechazo, proyeccion_fruta.                       |
| 06 | `06_contenedores.sql`         | contenedores, pallets_contenedor, pallets_detalle, distribucion_contenedor, simulacion_viaje. |
| 07 | `07_comercial.sql`            | precio_estimado_venta, precio_real_venta.                 |
| 08 | `08_costos.sql`               | concepto_costo, costo_logistico_pronosticado, costo_logistico_real, insumos, inventario_insumos. |
| 09 | `09_integraciones.sql`        | pya_documento_emitido, envio_twilio, factura_recibida.    |
| 10 | `10_audit.sql`                | audit_log.                                                |
| —  | `seed_maestros.sql`           | Seed de catálogos (zonas, frutas, monedas, calendario).   |

### Diferencias clave con la macro VBA original
1. **GGN e ICA separados** — `costo_total_ggn` y `costo_total_ica` son columnas
   independientes en `kg_consolidado`. El VBA actual sobre-escribe el GGN con el
   ICA por un bug (líneas 227-245 de `frmGGN`).
2. **`fruta_export_flag` desde el ingreso** — hoy se marca a mano en Excel. En
   la app se controla en la pantalla de aprobación del informe.
3. **Trazabilidad como `UNIQUE`** — evita duplicados que en Excel solo se
   detectaban con scan.
4. **Calendario de pagos como tabla** — incluye festivos. La macro hardcodeaba
   "viernes" y restaba 1-2 días.
5. **Audit log** desde el día 1 para `kg_consolidado`, `productores`,
   `precio_fruta` y `pya_documento_emitido`.

## Carga inicial
`scripts/carga_inicial.py` tiene tres subcomandos:

```bash
# Productores + precio_fruta + precio_certificacion
python -m scripts.carga_inicial maestros --gulupa "<ruta>\Base de datos gulupa.xlsx"

# Histórico (ingresos / export / nacional)
python -m scripts.carga_inicial historico --gulupa "<ruta>\Base de datos gulupa.xlsx"

# Packing lists de una carpeta entera (formato legacy y TNLC nuevo)
python -m scripts.carga_inicial packing --carpeta "<ruta>\operaciones\2026"
```

Por defecto va en **dry-run**. Para escribir a BD pasar `--no-dry-run`.

## Convenciones de código
- Snake-case Python.
- SQL en mayúsculas para reserved words, snake-case para identificadores.
- Cada parser de `ingesta/` devuelve dataclasses; no toca la BD. La capa de
  servicio (Fase 1 en adelante) se encarga de persistir.
- `conexion.py` es el único punto que abre conexiones a BD. Devuelve psycopg
  conn directo — se usa con `with`.

## Despliegue futuro
- **Local**: como NexFresh, Tarea Programada de Windows lanza
  `iniciar_servidor.bat` al iniciar sesión. Puerto 8502 (NexFresh usa 8501).
- **Cloud** (jue-vie): Azure App Service + Azure Database for PostgreSQL
  Flexible. Dockerfile listo. CI/CD: `az acr build` + redeploy automático en
  push a main. Auth con Entra ID. Patrón documentado en `nexfresh-sop/docs/DESPLIEGUE_AZURE.md`.

## Integraciones pendientes (cuando lleguen credenciales)
- **PyA / SAG ERP** — emisión de DR, factura electrónica, factura venta y carga
  de costos. Variables de entorno: `PYA_API_BASE`, `PYA_USERNAME`,
  `PYA_PASSWORD`, `PYA_API_KEY`, `PYA_SANDBOX`. Toda la lógica detrás de un
  feature flag (`PYA_SANDBOX=true` → no envía, solo registra payload).
- **Twilio** — envío WhatsApp/SMS. Variables: `TWILIO_ACCOUNT_SID`,
  `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_WHATSAPP`, `TWILIO_FROM_SMS`. Reemplaza el
  flow Power Automate actual.
- **SharePoint / Azure Blob** — guarda los PDFs de reportes/liquidaciones.
- **Outlook / Microsoft Graph** — bandeja monitoreada para facturas recibidas
  (Fase 6).
