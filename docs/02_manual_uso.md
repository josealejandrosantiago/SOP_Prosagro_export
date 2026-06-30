# Manual de uso (en construcción)

> Estado actual: Fase 0. Solo está la pantalla de inicio + login + esqueleto de
> módulos. Este manual se va llenando con cada fase.

## Primer arranque
1. `scripts/crear_db.sh` — crea el usuario `prosagro` y la base.
2. Copiar `.env.example` → `.env` y rellenar.
3. `scripts/aplicar_migraciones.sh` (o el `.bat`).
4. Doble clic a `iniciar_app.bat`. Abre `http://localhost:8502`.
5. Login: el usuario por defecto está en el `.env` (`APP_USER` / `APP_PASSWORD_HASH`).

## Atajos
- **Cerrar sesión**: botón abajo en la barra lateral.
- **Cambiar de módulo**: radio en la barra lateral.

## Roadmap visible en la app
- ✅ **Fase 0** — Esquema BD + app base.
- 🚧 **Fase 1** — Ingreso de fruta.
- ⏳ **Fase 2** — Liquidación productores + Twilio + PyA.
- ⏳ **Fase 3** — Causales + contenedor + GGN.
- ⏳ **Fase 4** — Simulación + Proyección + Tableros Power BI.
- ⏳ **Fase 5** — SOP / Costos / Distribución / Packing list / Ventas.
- ⏳ **Fase 6** — Bandeja correo + cruce auto facturas.
- ⏳ **Fase 7** — Monetizaciones + Cash flow + PyG.
