# Panel de Tráfico ORGU

Dashboard de tráfico, ventas y conversión de ORGU (Ford + marcas). Generador Python que
produce un `index.html` autocontenido y lo publica en Vercel.

**URL:** https://panel-trafico.vercel.app · **Repo:** `github.com/dyanezalbuja89-dot/panel-trafico-mmm`

> Este archivo es la fuente de verdad operativa del panel. Se actualiza **en el mismo commit
> que el código**. Si una regla de aquí contradice una nota guardada en otro lado, manda esta.

---

## Dónde vive cada cosa

| Qué | Ruta |
|---|---|
| Código | `~/dev/panel-trafico/` (fuera de OneDrive, desde 28-jul-2026) |
| Caché local de datos | `~/dev/panel-datos/` — `bd/`, `inv/`, `metas/`, `embudo/`, `cache/` |
| BD de tráfico (origen) | OneDrive `Marketing/2026/Análisis de tráfico/2026/<Mes>/BD_<MES>/` |
| Metas Ford | `.../<Mes>/METAS/<MES>_NUEVO_AI_FORD.xlsx`, hoja `METAS_FORD` |
| Metas otras marcas | `.../<Mes>/METAS/<MES>_NUEVO_AI_MARCAS.xlsx` |
| Inventario | OneDrive `Marketing/2026/Inventrario/REPORTE INVENTARIO <fecha>.xlsm` |

El aggregate lee del caché local **primero** y usa OneDrive como fallback.
La data corporativa se comparte con el equipo Ford y no se puede sacar de OneDrive.

---

## Actualizar el tráfico

Cuando llega una BD nueva:

```bash
cp "/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Agosto/BD_AGOSTO/BD_AGO_XX_08_26.xlsx" ~/dev/panel-datos/bd/
```

Editar `aggregate.py` → `MONTHS_CONFIG`, entrada del mes en curso (buscar `"key": "agosto_2026"`):

- `cut_day` = día del corte (del nombre del archivo)
- `curr_file` = la BD nueva
- `prev_file` = la que era `curr_file`
- `prev_date` = fecha del anterior en `DD/MM/AAAA`

```bash
cd ~/dev/panel-trafico && ./deploy.sh
```

`deploy.sh` corre aggregate → `checks_asesores.py` → `verificar.py --strict` → build →
push → deploy → y **compara el md5 del `data.json` en vivo contra el local**. Si Vercel
sirvió una versión cacheada, reintenta con `--force`.

`./deploy.sh --skip-aggregate` salta el recálculo cuando `data.json` ya está fresco.

---

## Reglas duras

**1. Commitear antes de publicar.** `digital_hourly.sh` corre por launchd cada hora y hace
`git reset --hard origin/main`. Todo cambio sin commitear se pierde. `deploy.sh` ya hace el
push antes de publicar, pero si editás código fuera de ese flujo, commiteá primero.

**2. Nunca `python3 build.py` a secas** para publicar: usar `./safe_build.sh` o `deploy.sh`,
que verifican la integridad de las pestañas.

**3. No tocar `tab-digital`** en `build.py` — el Seguimiento Digital lo maneja otra sesión.
El pipeline de datos de esa pestaña sí es de este repo.

**4. Al cambiar cualquier criterio de cálculo, subir la versión de la llave de caché**
(`aggregate.py`, hoy `v5-reingreso-60d`). Si no, los meses viejos se sirven con el criterio
anterior y solo cambia el mes en curso — ya pasó y el antes/después salió mal.
Para invalidar todo: `rm -f ~/dev/panel-datos/cache/months_cache.json`.

**5. Correr `verificar.py` antes de entregar cualquier cifra.** Está enganchado a
`deploy.sh` con `--strict`, así que corta el deploy si algo se rompió.

---

## Definiciones canónicas

### Tráfico (fijado 17-ago-2026)

1. Dentro del mismo mes, un cliente cuenta **una vez**.
2. Vuelve a contar **a los 60 días de su última visita contada**, no desde la primera.
3. **Por marca**: un Ford y un Dongfeng son dos tráficos distintos.
4. **Identidad = cédula.** El celular no agrupa (es del hogar y fusiona personas).
   Los registros sin cédula se cuentan igual.

Implementación: `DIAS_REINGRESO = 60`, `_build_reingreso_index()`, `_filter_reingreso()`.

**La conversión NO usa esta regla:** ahí la cohorte va por primer toque, porque mide
"de los que entraron en marzo, cuántos compraron".

### Metas: dos cuadros distintos

| Cuadro | Sección en `METAS_FORD` | Para qué |
|---|---|---|
| **VERDE** | `PRESUPUESTO DE TRÁFICO POR CONCESIONARIO MARKETING` | meta de **tráfico** (80% del total; el 20% restante es del asesor) |
| **AZUL** | `PRESUPUESTO NACIONAL - FORD` | meta de **venta** |

Las hojas por agencia copian la matriz **por posición fija**, así que se corren cuando
alguien reordena columnas en `METAS_FORD` — en agosto 2026 movieron Machala del puesto 6 al 3.
Por eso `_load_ford_metas_marketing()` lee **por nombre de columna**.

**Las metas se revisan durante el año.** Los archivos de la carpeta del propio mes tienen la
meta inicial; las copias en carpetas posteriores tienen la revisada. Para la meta vigente de
un mes pasado, leer **la copia más reciente**.

### Ventas: la venta cuenta donde se hizo (22-ago-2026)

`by_agencia` = **vitrina que emitió la factura**. Es la cifra oficial y cuadra con finanzas.

`by_agencia_equipo` = agencia del equipo del asesor (su "casa"). Existe por el efecto placa:
el cliente prefiere placa de Pichincha, así que ventas originadas en Machala o Manta se
facturan vía La Y o Tumbaco. Sirve para medir al equipo comercial, **no** para cuadrar con
finanzas, y **no se cruza contra tráfico**.

`by_agencia_fact` es alias de `by_agencia`, por compatibilidad.

**Para cruzar ventas con tráfico, usar siempre la vitrina:** el tráfico se registra donde
entró la persona.

El nodo hermano `ventas_mensual_doc` documenta las tres claves. **No meter notas dentro de
`ventas_mensual`**: el panel hace `Object.keys()` y las trataría como una marca.

### Los snapshots de inventario son fotos, no un log

Cuando una factura se anula, la fila **desaparece de la foto siguiente** sin dejar nota de
crédito. Unir todos los snapshots conserva ventas revertidas para siempre.

**Regla: para cada mes manda el snapshot más reciente que lo cubre.**

La lógica está **duplicada en tres archivos** — si algo descuadra, revisar los tres:
`ventas.py` (`load_ventas_completo`), `aggregate.py` (`_compute_ventas_mensual`, que descarta
el df que recibe y vuelve a leer `DATOS 2` por su cuenta) y `checks_asesores.py`.

### La pauta se cuenta a costo FACTURADO (24-ago-2026)

El Excel de presupuesto trae el **consumido en plataforma**. Eso no es lo que ORGU paga.
Encima van:

| Recargo | % | Sobre qué |
|---|---|---|
| Representante de medios (Cisneros) | 10% | neto |
| ISD | 5% | neto |
| Comisión de agencia XIY | 7,5% | **PVP** |
| Comisión de agencia BBA | 7,5% | **PVP** |

```
PVP        = neto × (1 + 0,10 + 0,05)      = neto × 1,15
a facturar = PVP  × (1 + 0,075 + 0,075)    = PVP  × 1,15
factor total                                = 1,3225
```

⚠ **No es 1,30.** Las comisiones de agencia se calculan sobre el PVP, no sobre el neto.
Verificado contra la liquidación Meta: $11.944,58 → $15.796,71, exacto.

2026 pasa de **$92.711 netos a $122.611 facturados**. Todo lo derivado se mueve con él:
costo por persona, brecha Sierra/Costa, ranking de eficiencia por modelo. Como el factor es
uniforme, **las proporciones y el ranking no cambian** — solo la escala.

Vive en `pauta.py` (`RECARGOS`, `FACTOR_COSTO`). El neto queda en `total_neto` y
`por_mes_neto` para poder auditar; el nodo `costo` publica el factor y sus componentes.
`verificar.py` comprueba las dos cosas.

⚠ **El CPL y los leads presupuestados NO llevan recargo**: vienen del Excel calculados
sobre el neto.

⚠ El factor sale de una liquidación de **Meta**. Se aplica a todos los canales mientras no
haya evidencia de otra estructura para Google, TikTok o influencers.

### Escala de color del cumplimiento (24-ago-2026)

**≥90% verde · 75–89% amarillo · <75% rojo.** Vale para todo el panel, en las 14 pestañas.

Definición única en `build.py`, junto al helper de anomalías:

```js
const CUMPL_VERDE = 90, CUMPL_AMARILLO = 75;
cumplNivel(p)  // 'green' | 'yellow' | 'red' | null
cumplClass(p)  // clase CSS: green/yellow/red
cumplHex(p)    // #16a34a / #eab308 / #dc2626
cumplBg(p, a)  // fondo suave para celdas de tabla
```

Cualquier vista nueva que coloree cumplimiento usa estos helpers. **No escribir el
umbral a mano**: antes cada pestaña tenía el suyo (≥100/≥70 en tráfico, ≥100/≥80/≥50 en
las tablas de ventas, ≥85 en el cruce) y el mismo 88% salía naranja en Análisis General
y amarillo en Ventas.

**El heatmap del cruce conserva sus 5 tonos** (`level()`), pero sus cortes caen dentro
de las bandas: crítico <50 y bajo 50–74 son los dos rojos, alerta 75–89 el amarillo,
ok 90–120 y sobre meta >120 los dos verdes.

⚠ **La regla es solo para % contra meta.** Las tasas de conversión (≥30/≥15), de cierre
(≥15/≥10) y de aprobación de crédito (≥80/≥60) tienen su propia escala: no se miden
contra una meta y aplicarles esta las pintaría todas de rojo. La barra de participación
por canal es azul Ford por lo mismo — es un share, no un cumplimiento.

### 'Por definir' cuenta como Escape (24-ago-2026)

El registro Ford que llega sin modelo en la BD sale como `Por definir`. **Se pliega a
ESCAPE en todo el panel**, no en una pestaña suelta.

Se pliega **en el origen**, así todas las vistas lo ven igual y no hay que acordarse de
plegarlo en cada vista nueva:

| Archivo | Dónde |
|---|---|
| `aggregate.py` | `get_traffic_df()` — tráfico Ford |
| `conversion.py` | `compute_conversion_metrics()` — vía `_sin_mod` |
| `embudo.py` | `_split_modelos()` y el conteo por modelo |

La constante vive en `inventario.py` (`SIN_MODELO`, `SIN_MODELO_FORD`), que es el módulo
hoja que los tres importan.

⚠ **El pliegue va DESPUÉS del dedupe por cédula.** Si se renombra antes, el flag
`_has_model` da por válida una fila sin modelo y esa fila le gana a la que sí lo trae —
justo lo contrario de lo que el dedupe intenta.

⚠ **Solo Ford.** Las marcas ORGU conservan su fila `Por definir`: no tienen un Escape al
cual plegarla. `compute_conversion_metrics` corre para las cinco marcas, así que ahí el
pliegue está condicionado a `marca_filter == 'FORD'`.

⚠ **Cambia el cálculo de los meses** → hubo que subir la llave de caché a
`v6-sinmodelo-escape`. Sin eso los meses viejos se sirven con el criterio anterior y solo
cambia el mes en curso.

`verificar.py` falla el deploy si reaparece un `Por definir` bajo `ford`, `ford_months`,
`conversion_data.FORD` o `embudo`.

### Otras reglas de cálculo

- **Días laborables:** el sábado (10–14h) cuenta como día completo. Usar `working_days()`,
  no `weekday() < 5`.
- **Mes sin data:** todos los widgets del mes en 0, nunca fallback al mes anterior.
- **MAZDA y RAM no tienen Portoviejo** en `BRAND_DEALERS` (venden pero no gestionan tráfico).
- **Portoviejo factura como `1013 VEHICULOS MANTA II`.** Sin `AGENCY_INV_EXCLUDE`, "MANTA"
  captura también MANTA II.
- **`norm_asesor()`** deduplica el apellido repetido de las BD Kombat
  ("HILANO CARRILLO HILANO CARRILLO" → "HILANO CARRILLO").

---

## Alinear números con el eje de un gráfico

En la pestaña **Asignación**, las tres filas de abajo (Inversión / $ por persona / Personas
por unidad libre) tienen que caer exactamente bajo su mes.

No se puede clavar un ancho a mano: **Chart.js decide el ancho de los ejes en cada render**
según cuántos dígitos tenga la escala — dos gráficos de la misma fila terminan con ejes de
28 y 35 px. Cualquier `padding-left` fijo desalinea a la primera.

La solución es un plugin, `ASIG_ALINEA`, que en `afterLayout` lee el `chartArea` real y lo
traslada a padding de las filas de números:

```js
el.style.paddingLeft  = Math.round(c.chartArea.left) + 'px';
el.style.paddingRight = Math.round(c.width - c.chartArea.right) + 'px';
```

Con las celdas en `repeat(N, 1fr)` dentro de ese ancho, cada una queda centrada sobre su
tick (la escala de categorías las reparte en bandas iguales). `afterLayout` corre también
al redimensionar, así que aguanta el cambio de ancho de ventana.

Los **nombres de fila viven en un canalón de 118 px a la izquierda**, fuera del gráfico:
el canvas arranca en esa misma coordenada, así que etiquetas y trazado no se pisan.

Medido en producción: desvío máximo **0,36 px** en las 7 tarjetas.

### Conversión = vehículos ÷ personas de tráfico (24-ago-2026)

**No** personas-que-compraron ÷ personas únicas: esa versión dejaba fuera al cliente que se
lleva dos autos. Aplica al KPI, a las cuatro tablas, a los bullets y al gráfico.

La Y ene–ago 2026: **49 vehículos / 524 personas = 9,4%**. Red: 645 / 3.554 = 18,1%.

#### Tres cifras de tráfico para la misma agencia, y ninguna está mal

| Cifra | Qué cuenta | Dónde sale |
|---|---|---|
| 480 | visitas, sólo canales de marketing | Comparativo (filtro por defecto) |
| 561 | visitas, todos los canales | Comparativo sin filtro |
| 527 | **personas distintas** con 1er toque en 2026 | Conversión |

El tráfico cuenta **visitas** (reingreso a los 60 días); la conversión cuenta **personas**,
una vez en el año. Además la pestaña de Conversión no filtra por categoría de canal.

#### Los TOTAL no son la suma de las filas

Los buckets se solapan. La tabla de modelo sumaba 46 compradores contra los 43 del KPI, con
su propio % (8,7% vs 8,2%). Ahora `renderTable` recibe el total del KPI y avisa cuánto suman
las filas. **Nunca sumar filas de estas tablas para sacar un total.**

#### Un solo filtro para toda la pestaña

`convFiltraClientes(lista, salvo)` y `convFiltraFacturas(lista, salvo)`. **Ninguna vista
filtra por su cuenta.** `salvo` omite la dimensión que esa vista usa de eje: el gráfico de
evolución no aplica `mes`, el de modelos no aplica `modelo`.

Había cinco copias del filtro de facturas y tres del de clientes. A dos les faltaba `zona`:
con Quito filtrado el gráfico mostraba las 645 unidades de la red contra las 1.094 personas
de Quito, y enero marcaba **117%**. Los fallbacks también divergían — el canal se filtraba
con tres variantes (`'Sin canal atribuido'`, `'Gestión Externa'`, sin fallback) y el modelo
con dos, así que filtrar por un canal dejaba fuera facturas que esa misma tabla contaba en
esa fila. **Los fallbacks del filtro tienen que ser los mismos con los que la tabla agrupa.**

#### La pestaña solo cuenta meses CERRADOS

`convMesesOk()` deriva los meses de `AN_MONTHS_2026`, la misma fuente que Análisis General.
Aplica al eje del gráfico, al selector de mes, a los clientes y a las facturas — estas
últimas por su cohorte, o por su mes de factura si no tienen. Ver
[[feedback_orgu_rangos_de_fecha]].

#### El gráfico de cohortes cuadra con el total facturado

Su eje X es el **mes del primer toque**, no el de la factura: la barra de junio son los
autos que compró la gente que llegó en junio, facturados cuando haya sido. Por eso no
coincide con el calendario de ventas — La Y vendió 10 en junio pero solo 5 fueron a gente
que entró ese mes.

Los compradores **sin cohorte** (flota, gestión externa, primer contacto en 2025) no caen en
ningún mes. Antes quedaban fuera y las barras sumaban 39 de 49; ahora van en una columna
**"Sin cohorte"** al final, sin % porque no tienen denominador. Verificado: barras = KPI =
total de la tabla en las 7 agencias, en toda ORGU y en Ford/DongFeng/Chery.

Por **fecha de factura** el nodo cuadra exacto con `ventas_mensual`: La Y 4·11·8·3·3·10·9·1 = 49.

#### Conversión: la tarjeta no cuadra con la suma de las barras (y está bien)

En la pestaña **Conversión**, el KPI `% Conversión` y el gráfico de evolución mensual dan
distinto a propósito:

| | Denominador | Numerador |
|---|---|---|
| **Tarjeta** | personas únicas del filtro | **todo** el que compró |
| **Gráfico** | cohorte del mes de 1er toque | solo el que tiene cohorte |

La diferencia son los **compradores sin `cohorte_ym`**: se les facturó pero nunca
aparecieron en la BD de tráfico del año — flota, gestión externa, o primer contacto en
2025. La tarjeta los cuenta; el gráfico no puede ponerlos en ningún mes.

Ejemplo verificado (La Y, YTD 2026): tarjeta **43 / 524 = 8,2%**, barras **38 / 525 = 7,2%**.
La brecha son **5 personas y 10 vehículos** en 12 facturas sin cohorte. A nivel red son
67 compradores.

El gráfico lo dice ahora en una nota calculada (`#conv-evol-nota`), que respeta los filtros
activos. Antes no lo decía y el gráfico parecía contradecir la tarjeta.

**El gráfico lleva las tres series** desde ago-2026: barras de personas y de vehículos en el
eje izquierdo, línea de % en el derecho. Un 21,7% sobre 60 personas y un 6% sobre 83 son
historias distintas y el % solo no lo mostraba. Las barras de ventas llevan `minBarLength: 3`
— una venta contra una escala de 120 sería invisible.

## Auditoría de filtros (25-ago-2026)

Se revisaron los filtros de las 14 pestañas. **El patrón de fallo no da error**: el
selector está en el HTML, se ve normal, pero o no llega a poblarse o una de las
computaciones no lo aplica. El número que sale es plausible y viejo.

| Pestaña | Hallazgo |
|---|---|
| Conversión | a 2 de 7 filtros de facturas les faltaba `zona` → **arreglado** |
| Ventas | el selector Zona nunca se poblaba → **arreglado** |
| Inversión Digital | los 3 filtros muertos: faltaba el nodo `xiy` → **arreglado** |
| Ford · Marcas · Comparativo · Análisis General · Meta ventas · Embudo · Asignación · Seguimiento Digital | responden correctamente |

Dos causas distintas, misma consecuencia:

- **`vtBrandData()`** fusionaba `by_modelo` y `by_agencia` de varias marcas pero no
  `by_zona`. Como el default son todas las marcas, siempre entraba por esa rama.
- **`data_xiy.json`** se buscaba en `OneDrive/.../Abril/panel-trafico/`, ruta que quedó
  atrás cuando el repo salió de OneDrive. Sin el archivo no se emite el nodo `xiy` y
  `xiyInitFilters()` hace `return` — escondiendo hasta el botón Limpiar. Ahora se busca
  junto al script.

### Comportamientos por diseño (no son bugs)

- **Ford · tabla de zonas** y **Asignación · KPIs**: son vistas comparativas entre zonas;
  muestran todas y marcan la activa.
- **Ventas · `vt-mix-tbl` y `vt-bp-tbl`**: van contra presupuesto nacional, no filtran por
  zona ni agencia.
- **Ventas · `vt-meta-tbl`**: solo aparece con Ford aislado.
- **Marcas · agencia y modelo**: se pueblan al elegir una marca.

⚠ **`data_xiy.json` está congelado en abril-2026.** Los filtros ya funcionan, pero la
pestaña no tiene datos de mayo en adelante.

## Verificación

```bash
python3 verificar.py            # 19 invariantes
python3 verificar.py --strict   # exit 1 si algo falla
python3 checks_asesores.py      # ventas por asesor contra 'Usuario Vende' de DATOS 2
```

`verificar.py` cubre: ventas por vitrina contra `DATOS 2` (las cinco marcas), que las dos
bases de atribución sumen igual, el contrato de campos de `flat` y los pivotes, metas
cuadradas por modelo y por agencia contra el total, meses vacíos o con corte futuro, y la
versión del caché.

---

## Estructura de `data.json`

| Nodo | Contenido |
|---|---|
| `ford_months[mes]` | tráfico Ford: `total_curr`, `meta_total`, `models`, `dealers`, `daily`, `pace` |
| `brands_months[mes][marca]` | igual, por marca |
| `ventas_mensual[marca]` | `flat`, `by_modelo`, `by_asesor`, `by_agencia`, `by_agencia_equipo`, `by_zona`, `nc` |
| `ventas_mensual_doc` | qué significa cada base de atribución |
| `conversion_data[marca]` | `master_facturas` (fuente única de cierres), breakdowns por canal/modelo/agencia/asesor |
| `presupuesto.tipos` | BP `financiero` y `comercial` por agencia y mes |
| `inventario`, `arribos`, `embudo_data`, `competencia_data`, `digital` | resto de pestañas |

**Conversión — invariantes:** fuente única `master_facturas`; el filtro de mes es cohorte de
primer toque; numerador y denominador filtran por los mismos campos `*_lead`; los totales
del backend solo valen sin filtros finos; umbral de ≥5 leads solo sin filtros.

---

## Cifras de control · Ford ene–jul 2026

Vitrina (cuadra con finanzas, corte de inventario 15-ago):

| CJA | Orellana | Manta | Tumbaco | Machala | La Y | Portoviejo | Total |
|---|---|---|---|---|---|---|---|
| 160 | 158 | 92 | 81 | 60 | **48** | 36 | **635** |

Por equipo del asesor, la misma base da La Y 35 y Tumbaco 89. **Si ves 35 como cifra oficial
de La Y, el dato es viejo.**

---

## Seguimiento Digital

`digital.json` en la raíz lo escribe **solo** `digital_hourly.sh` (single-writer; nadie más
lo commitea). Cron `com.orgu.panel-digital-hourly` cada hora: fetch → stash → reset a origin
→ `hubspot_pull.py` → commit+push → `_merge_digital.py` → build → deploy.
Log en `~/panel_digital_hourly.log`. La pestaña Ford tiene gate de contraseña; la de DF no.

Refresco manual:

```bash
python3 hubspot_pull.py && python3 _merge_digital.py && ./deploy.sh --skip-aggregate
```

---

## Bugs resueltos que conviene no repetir

- **Ventas revertidas sobreviviendo en la unión de snapshots** (22-ago-2026): el panel daba
  639 unidades Ford ene–jul contra 635 de finanzas. Cuatro chasis facturados y luego anulados
  seguían contados. Fix en los tres archivos del concat.
- **Atribución invertida** (22-ago-2026): `by_agencia` daba el equipo del asesor en vez de la
  vitrina, y La Y salía en 35 en vez de 48.
- **Buscador de inventario cortaba en el primer directorio**: el panel mostró dos semanas el
  inventario del 1-ago. `_find_latest_inventory()` ahora ordena por la fecha **del nombre**,
  no por mtime (copiar al caché altera los mtime).
- **Columna de metas corrida**: las hojas por agencia copian por posición fija.
- **Caché sirviendo criterios viejos**: al cambiar la regla de reingreso, los meses cacheados
  seguían con el criterio anterior.
- **Fechas futuras en la BD** producían días negativos; se descartan.
- **Vercel sirviendo `data.json` viejo con `index.html` nuevo** → números fantasma. Por eso
  `deploy.sh` verifica el md5 en vivo.
