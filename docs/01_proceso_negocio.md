# Proceso de negocio — SOP Prosagro Export

## El ciclo completo, semana por semana

```
Lunes-martes        : la maquila (Binlab) recibe los cargues de los productores.
Miércoles           : la maquila envía 'Informe de proceso semana N.xlsx' al usuario.
Miércoles-jueves    : usuario revisa, parametriza, aprueba y carga a la BD.
Viernes             : se generan reportes individuales y se envían por WhatsApp/SMS.
Viernes             : se generan los planos PyA (CxC y fact. electrónica) y se cargan.
Viernes             : se gira el pago a productores.
```

## 1. Ingreso de fruta

La maquila entrega un xlsx crudo con 3 hojas:

| Hoja                  | Contenido                                                 |
| --------------------- | ---------------------------------------------------------- |
| `Informe de Ingreso` | Cargues: fecha, no_cargue, consec (zona+lote), canastillas, peso_neto, conductor, placa. |
| `export`              | Para cada cargue: cant_cajas y kg por calibre (EUR26..50). |
| `Nal`                 | Para cada cargue: lote, merma, cant_kilos_descarte.        |

### Normalización (el script `procesar_informe_proceso.py` que el usuario corre hoy)
- `consec_int` "122 6" → "02 06". Mapeo: 122→02 (Urrao), 123→01 (San José), 124→03 (Oriente).
- Se agrega la **trazabilidad** `2026 00M cargue zona lote`.
- El **calibre 26** (EUR26) sale de export y va a una hoja **Simulación**.
- En la hoja `Nal` aparece la columna `simulación` (VLOOKUP sobre Simulación) y
  `total_nacional = cant_kilos_descarte + simulación`.

### Regla del ajuste administrativo
Cuando una fila de export tiene `calibre = N/A`, es un **ajuste** (no fruta
física). Se compensa **manualmente** restando esos kg de la fruta nacional para
que el balance cuadre.

## 2. Carga a `Base de datos gulupa.xlsx`
El xlsx procesado se copia/pega en 3 hojas del libro central:
`ingreso gulupa`, `fruta export`, `fruta nacional`. El usuario añade
manualmente: año y bandera `fruta export = Si/No`.

## 3. Consolidación en `Kg consolidado` (CommandButton1_Click)
Por cada trazabilidad nueva:
- Calcula `Kg Total`, `Kg Export` (categoría C1), `Kg Categoría 2`, `Kg Merma`.
- Lookup productor vigente: nombre, propietario, doc, plantas, ubicación, teléfono.
- Lookup precio vigente: `precio_expo`, `precio_nal`, `precio_desh`, `días_pago`.
- Calcula costos totales, `Ashofrucol = 1% de costo total`, **fecha de pago** (siempre se ajusta a viernes).
- Calcula **Rete fuente** agrupando por `fecha_ingreso + propietario` y prorrateando.

## 4. Liquidación al productor (`frmLiquidarproductores`)
- Filtra Kg consolidado por semana + año, agrupa por propietario.
- Genera PDF por productor (plantilla `Liquidación productor`).
- Sube el PDF a SharePoint y dispara un flow Power Automate → **Twilio** → WhatsApp/SMS.

## 5. Archivos planos PyA (`frmCuentasyfacturacion`)
- `CommandButton2`: cuentas de cobro (cuando productor NO tiene fact. electrónica).
- `CommandButton4`: fact. electrónica de compra.
- Por productor único + fecha de proceso, dos filas posibles: una de
  **exportación**, una de **nacional**.
- Artículos PyA: `FGU1001` (Gulupa) / `FUC1003` (Uchuva).
  Bodegas: `EXGULUPA`/`EXUC` (export), `NLGU`/`NLUC` (nacional).
- **Precio unitario expo = (costo_expo + costo_deshidratación) / kg_expo** (la
  deshidratación se mete dentro del unitario, no se cobra aparte).

## 6. Causales de rechazo (`frmInicio.CommandButton21`)
- Lee los xlsx de "Evaluación de Calidad" Binlab.
- Por la fila R5C18 saca el `no_cargue` y busca la traza en Kg consolidado.
- Solo procesa filas con `fruta_export = Si` y que no estén ya cargadas.
- 3 bloques: defectos **menores** (filas 19-20), **mayores** (19-30),
  **críticos** (19-21).
- Calcula `kg_con_causal = % × kg_nal` por causal.

## 7. Validación armado de contenedor (`frmInicio.CommandButton20`)
- Lee el **packing list** de la maquila.
- Para cada fila de fruta_export sin contenedor asignado, busca un pallet con
  mismo `no_cargue` y `calibre`.
- Si las cajas exportadas > cajas del pallet → **divide la fila**.
- Si iguales → cruce directo. Si menores → la diferencia queda como saldo.
- Llena: pallet, contenedor, predio, GGN, ICA. Marca el pallet `cruzado`.

## 8. Liquidación GGN (`frmGGN`)
- Por contenedor en rango, calcula el costo de certificación que debe cobrarse
  al productor que **no tiene su propio GGN/ICA**.
- **Bug actual**: el costo ICA sobre-escribe el costo GGN — en la nueva app van
  como dos columnas que se suman.
- Quiere PDF por productor + envío Twilio "todo a un click".

## 9. Macro 2 — Consolidación costos y ventas
Esta macro arma el SOP por contenedor:

- **SOP presupuestal** (`CommandButton2`): por cada OP-xxx, mezcla:
  - fruta export (cant cajas, calibres, kg, costo expo)
  - certificaciones (GGN/ICA por productor)
  - costos logísticos pronosticados
  - cronograma de llegada y simulación de viaje
- **Insumos** (`frmInsumos`): inventario y consumo. Pendiente de redefinir.
- **Costos pronosticados** (`frmCostos`): tarifas por contenedor o mensuales.
  Pendiente de migrarlo al patrón de NexFresh donde se basa en los últimos N
  contenedores.
- **Distribución a clientes** (`frmDistribucionContenedor`): drag/drop de
  pallets a clientes.
- **Packing list** (`frmPackingList`): genera el packing list con formato TNLC
  (nuevo) — incluye sello GRASP para los predios certificados.
- **Precio estimado** (`frmPrecioEstimado`): precio meta y fecha de recogida.
- **Precio real** (`frmAsignarPrecios`): cuando llega la liquidación del
  cliente. Se guarda el PDF original.
- **Plano facturación venta** (`frmArchivosPlanoFacturacion`): plano para
  cargar la factura final a PyA.

## 10. Lo que falta
- **Monetizaciones** (en ceros, planificado para fase final).
- **Flujo de caja proyectado** y **PyG automatizado** (referenciado en la
  conversación "2026 sales projection replication").
- **Cruce automático de facturas** recibidas por correo.

## Identidades clave
- **Trazabilidad**: identificador natural de un cargue, único en el negocio.
- **Productor**: dueño del lote en una vigencia. Cambia en el tiempo —
  por eso `productores` tiene `fecha_vigencia_desde/hasta`.
- **Predio**: la finca física. A veces tiene un nombre comercial distinto al
  del propietario (`nombre_finca` vs `propietario` en VBA).
- **Contenedor**: una operación de exportación (`OP-326`).
- **Pallet**: la unidad mínima de armado de un contenedor.

## Reglas duras (no se negocian)
1. **Solo viernes se paga al productor.** El calendario corrige sábado→viernes
   anterior, domingo→viernes anterior, otros días→siguiente viernes.
2. **El precio expo de PyA incluye la deshidratación** en el unitario.
3. **Calibre N/A = ajuste administrativo.** No es fruta física.
4. **Categoría 2 (no-C1) no es export** — se descuenta y suma a nacional.
5. **El consecutivo PyA se asigna por productor + fecha de proceso**, no por
   trazabilidad individual.
