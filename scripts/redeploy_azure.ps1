# Re-deploy de SOP Prosagro Export a Azure Container Apps.
# Uso: clic derecho > "Ejecutar con PowerShell", o desde una terminal:
#   powershell -ExecutionPolicy Bypass -File scripts\redeploy_azure.ps1
#
# Qué hace: reconstruye la imagen en ACR con el código actual del repo y
# actualiza la Container App a la nueva imagen. ~3-5 min.

$ErrorActionPreference = "Stop"
$az = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

$RG       = "prosagro-rg"
$ACR      = "prosagrocr"
$APP      = "prosagro-sop"
$IMAGE    = "prosagrocr.azurecr.io/prosagro-sop:latest"

# Ir a la raíz del repo (este script vive en scripts\)
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Construyendo imagen en ACR (cloud build)..." -ForegroundColor Cyan
& $az acr build --registry $ACR --image "prosagro-sop:latest" --file Dockerfile .

Write-Host "==> Actualizando Container App a la nueva imagen..." -ForegroundColor Cyan
& $az containerapp update --name $APP --resource-group $RG --image $IMAGE | Out-Null

$fqdn = & $az containerapp show --name $APP --resource-group $RG --query "properties.configuration.ingress.fqdn" -o tsv
Write-Host "==> Listo. App actualizada en: https://$fqdn/" -ForegroundColor Green
