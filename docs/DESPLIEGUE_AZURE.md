# Despliegue a Azure (pendiente)

Misma receta que `nexfresh-sop/docs/DESPLIEGUE_AZURE.md`. Se activa cuando el
tenant de Azure de San José esté listo (jue-vie).

## Recursos esperados
- **Azure Database for PostgreSQL Flexible Server** (`prosagro-pg-prod`).
- **Azure Container Registry** (`prosagrocr`).
- **Azure App Service for Containers** (`prosagro-sop`) con
  `WEBSITES_PORT=8501`.
- **Azure Blob Storage** (`prosagroblob`) contenedor `reportes`.
- **Entra ID** para auth (mismo grupo que NexFresh).
- **Key Vault** para `PYA_*`, `TWILIO_*`, `DATABASE_URL`.

## CI/CD
- GitHub Actions con `az acr build` en push a `main`.
- Trigger de deploy automático.
- Migraciones SQL se aplican como paso del workflow contra la BD de Azure.

## Notas
- El Dockerfile ya está listo (raíz del repo).
- `iniciar_servidor.bat` no se sube a la imagen (está en `.dockerignore`).
- El `.env` de producción se monta como app setting en App Service, no se sube
  a la imagen.
