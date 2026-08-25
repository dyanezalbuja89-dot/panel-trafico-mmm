# BRIEF · Auditoría del Panel de Tráfico ORGU antes de presentarlo a un CEO

## Qué es esto

Dashboard comercial de ORGU (red de concesionarios Ford + Dongfeng + Chery + Mazda + RAM
de Corporación Maresa, Ecuador). Lo va a ver un **CEO**: cualquier cifra que no cuadre
entre pestañas, etiqueta que mienta o total que no sume destruye la credibilidad del
presentador. Tu trabajo es encontrar ESO antes de que lo encuentre él.

## Arquitectura (todo local, sin red)

- **Código:** `/Users/danielyanezalbuja/dev/panel-trafico/`
- Pipeline: generadores Python (`aggregate.py`, `conversion.py`, `ventas.py`, `embudo.py`,
  `inventario.py`, `pauta.py`) → `data.json` → `build.py` (un solo archivo: CSS + HTML +
  JS de las 14 pestañas) → `index.html` autocontenido.
- **`README.md` del repo = documentación operativa.** Léelo primero.
- **`verificar.py` = 24 invariantes ya cubiertos.** Léelo para NO repetir lo que ya se
  chequea. Tu valor está en lo que ese archivo NO cubre.
- `data.json` (~4 MB) es la fuente de datos del panel. Audita contra él con Python
  (`/usr/bin/python3`, pandas disponible). El JS de cada pestaña vive en `build.py`
  (~18.000 líneas): localiza secciones con grep (`tab-ford`, `renderConv`, etc.).

## Definiciones canónicas (violarlas = hallazgo)

1. **Tráfico** = visitas: 1 por mes por persona (cédula), reingresa a los 60 días de su
   última visita contada, por marca. Canales "marketing" (Showroom, Hubspot, Feria/Eventos,
   Llamada In, Mailing, Ferias…) vs "todos" (suma Gestión Externa, Referidos, etc.).
2. **Meta de tráfico** = cuadro MARKETING (80% de la total). Meta de ventas = otra fuente
   (`ford_meta_breakdown`). No mezclarlas.
3. **Ventas por agencia** = donde se HIZO la venta (vitrina), cuadra con finanzas.
   Existe también `by_agencia_equipo` (por asesor-hogar) como vista secundaria.
4. **Conversión** = VEHÍCULOS facturados ÷ personas únicas de tráfico. No personas÷personas.
5. **Escala de cumplimiento** = verde ≥90% · amarillo 75–89% · rojo <75%, en TODO el panel
   (constantes `CUMPL_VERDE`/`CUMPL_AMARILLO` en build.py). NO aplica a tasas de conversión,
   cierre ni crédito, que tienen escala propia.
6. **'Por definir'** (tráfico Ford sin modelo) se pliega a **ESCAPE** en todo el panel.
   Las marcas ORGU lo conservan como fila.
7. **Acumulados = solo meses CERRADOS** (corte en el último día del mes). El mes en curso
   no entra en YTD ni promedios. Los rangos de fecha se derivan del dato, jamás a mano.
8. **Pauta** = costo FACTURADO: neto de plataforma × 1,3225 (10% rep. medios + 5% ISD
   sobre neto; dos comisiones de agencia de 7,5% sobre el PVP). `total_neto` conserva el neto.
9. **Snapshots de inventario son fotos**, no un log: por mes se usa el MÁS RECIENTE, nunca
   se unen (una factura anulada desaparece sin NC).
10. Los compradores **sin cohorte** (flota/gestión externa/1er toque 2025) van al mes de
    su FACTURA en el gráfico de conversión, y suben el % sin sumar al denominador.

## Cifras de control (verificadas hoy, 25-ago-2026)

- Ford YTD cerrado (ene–jul): tráfico marketing 2.578 vs meta 2.898 (89,0%).
- Ventas Ford 2026 ene–ago: 645 netos · La Y = 49 (48 a julio).
- Conversión (meses cerrados): red 639 veh / 3.221 personas; La Y 49/524.
- Tres números de tráfico de La Y que NO son errores: 480 (visitas marketing) / 561
  (visitas todos los canales) / 527 (personas únicas del año).
- Pauta 2026: $122.611 facturados = $92.711 netos × 1,3225.
- Ciclo 1er toque→factura: mediana 16d excluyendo el 21% registrado el mismo día que compró.

## Patrones de bug ya cazados aquí (busca más de la misma especie)

- **Filtros que mueren callados**: selector sin poblar, o una de varias copias del filtro
  que no aplica una dimensión. Hoy Conversión tiene UN solo filtro (`convFiltraClientes` /
  `convFiltraFacturas`); si ves un `.filter(` manual sobre clientes o facturas en esa
  pestaña, es sospechoso.
- **Rangos congelados**: listas de meses escritas a mano que se quedan viejas.
- **Totales que suman filas solapadas** (persona en 2 canales cuenta doble).
- **Etiquetas que mienten**: "Vehículos facturados" cuando el eje es cohorte; "0,0%" rojo
  para un canal sin denominador.
- **`NaN or 0` en Python** devuelve NaN y envenena sumas sin error.
- **Fechas 1900-01-01** = nulos disfrazados.

## Qué debe entregar cada auditor

Hallazgos CONCRETOS y verificables, no opiniones de estilo. Por cada uno: qué está mal,
dónde (archivo + función o id de elemento), la cifra que lo prueba (recalculada por ti
desde data.json), y qué le diría un CEO si lo ve. Severidad:
- **alta**: cifra incorrecta o dos pestañas que se contradicen.
- **media**: etiqueta/definición engañosa, total que no es la suma visible sin explicación.
- **baja**: fragilidad (se romperá con el próximo mes), inconsistencia menor.

NO reportes: estilo de código, rendimiento, cosas que `verificar.py` ya chequea (salvo que
el chequeo esté mal), ni las pestañas Inventario (`tab-inv`), Inversión Digital (`tab-xiy`)
y Competencia (`tab-comp-imp`), que están fuera del alcance.

⚠ La pestaña Seguimiento Digital (`tab-digital`) es intocable por regla del dueño: se
audita y reporta, pero NO propongas ediciones de código sobre ella.
