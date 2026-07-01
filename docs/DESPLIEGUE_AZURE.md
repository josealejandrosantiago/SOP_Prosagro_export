# Despliegue a Azure — SOP Prosagro Export

## ✅ Estado: DESPLEGADO (01/07/2026)

La app corre en **Azure Container Apps** (no App Service, ver nota más abajo).

- **URL pública**: https://prosagro-sop.nicebeach-1971bea0.eastus2.azurecontainerapps.io/
- **Login**: `analistadedatos@gruposanjose.com.co` / `Prosagro2026`

### ¿Por qué Container Apps y no App Service?
El plan original era App Service (patrón NexFresh), pero la suscripción nueva del
Grupo San José tiene la **cuota de VMs en 0** (restricción anti-fraude estándar de
Azure para suscripciones recién creadas). App Service requiere pedir aumento de
cuota (minutos a 48h). Azure Container Apps usa una cuota serverless distinta que
**sí estaba disponible**, así que desplegamos ahí. Ventajas: escala a cero (más
barato, ~10-15 USD/mes real), HTTPS automático, misma imagen Docker desde el mismo
ACR. Si algún día se quiere unificar con NexFresh en App Service, la imagen es la
misma y migrar es directo (basta con crear el plan cuando haya cuota).

## Recursos creados (resource group `prosagro-rg`, región `eastus2`)

| Recurso | Nombre | Tipo | Notas |
| --- | --- | --- | --- |
| Container App | `prosagro-sop` | Microsoft.App/containerApps | La app. 0.5 vCPU / 1 GB, 1-2 réplicas. |
| Container Apps Env | `prosagro-env` | Microsoft.App/managedEnvironments | Entorno serverless. |
| Container Registry | `prosagrocr` | Microsoft.ContainerRegistry | Basic, admin-enabled. Imagen `prosagro-sop:latest`. |
| PostgreSQL Flexible | `prosagro-pg-prod` | Microsoft.DBforPostgreSQL | B1ms Burstable, 32 GB, PG16. BD `prosagro`. |
| Log Analytics | `workspace-prosagrorg…` | Microsoft.OperationalInsights | Auto-creado por Container Apps. Free tier. |

## Datos restaurados a Azure (01/07/2026)
Dump del Postgres local (`prosagro`) restaurado al servidor Azure:
- 181 productores · 844 ingresos · 5.511 fruta_export · 843 fruta_nacional
- 169 kg_consolidado · 2 contenedores · 314 pallets_detalle · 1 usuario

## Configuración
- **DATABASE_URL**: secret en la Container App apuntando a
  `prosagro-pg-prod.postgres.database.azure.com` con `sslmode=require`.
- **Extensiones Postgres permitidas**: `PGCRYPTO, UNACCENT, PG_TRGM`
  (via `az postgres flexible-server parameter set --name azure.extensions`).
- **Firewall Postgres**: IP del usuario (`167.0.171.8`) + `AllowAzureServices`
  (0.0.0.0) para que la Container App conecte.
- **Secretos locales** (NO en git): `C:\Users\LENOVO\.azure-prosagro-secrets\`
  contiene la clave admin de Postgres, la IP pública y el dump.

## Re-deploy (subir cambios de código)
Después de editar el código, para actualizar la app en Azure:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\redeploy_azure.ps1
```
Reconstruye la imagen en ACR y actualiza la Container App (~3-5 min).

## Comandos útiles
```powershell
$az = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

# Ver logs de la app
& $az containerapp logs show --name prosagro-sop --resource-group prosagro-rg --tail 50 --type console

# Reiniciar la app (nueva revisión)
& $az containerapp revision restart --name prosagro-sop --resource-group prosagro-rg

# Escalar (si va lenta con varios usuarios)
& $az containerapp update --name prosagro-sop --resource-group prosagro-rg --min-replicas 1 --max-replicas 3 --cpu 1.0 --memory 2.0Gi
```

## ⚠ Pendientes de seguridad
1. **La app es públicamente accesible** (protegida solo por el login bcrypt).
   Falta implementar **Entra ID (Azure AD)** como auth real — igual que
   NexFresh. Mientras tanto, el login placeholder protege el acceso, pero
   cualquiera con la URL ve la pantalla de login.
2. **Firewall Postgres** usa `AllowAzureServices` (0.0.0.0) que permite
   cualquier servicio de Azure, no solo nuestra Container App. Para endurecer:
   restringir a la static IP del entorno + private endpoint (~15 USD/mes extra).
3. **Rotar** la clave admin de Postgres y el password de ACR periódicamente.

## Costo estimado
~15-30 USD/mes: Container Apps escala a cero (pagás por uso real) + PostgreSQL
B1ms (~12 USD fijo) + ACR Basic (~5 USD) + Log Analytics (free tier).
Más barato que App Service porque Container Apps no cobra compute cuando no hay
tráfico.
