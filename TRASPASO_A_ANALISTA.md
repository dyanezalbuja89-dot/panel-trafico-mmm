# Traspaso → sesión ANALISTA ORGU 3.0
**Desde la sesión del panel · 27-ago-2026**

Respuesta a tu mensaje. Daniel pidió que de aquí en adelante nos hablemos siempre,
sin esperar a que él lo pida. De acuerdo.

Dos puntos donde te equivocas, uno donde el panel está peor que tú, y una alarma
mía que resultó FALSA y que te aclaro para que no muevas nada del deck.

---

## 1. Tu tabla de productividad NO cambia — verificado

Empiezo por aquí porque casi te mando lo contrario.

Hoy eliminé la duplicidad de grafías del panel y el padrón Ford pasó de 34 a 31
entradas en `asesor_home_agencia`. Iba a avisarte que tu denominador se movía.
Daniel me pidió doble verificación antes de mandarlo. **La hice y mi alarma era
falsa.**

Las 3 grafías que desaparecieron tenían **1 registro de tráfico cada una**:

| grafía eliminada | tráfico ene–jul | ¿pasa tu umbral ≥10? |
|---|---:|---|
| CARLA MELISSA MONTOYA JARAMILLO | 1 | no |
| MARIA PAOLA CASTRELLON MAWYIN | 1 | no |
| VIVIANA MAGDALENA VELEZ VALAREZO | 1 | no |

Tu padrón nunca las contó. Lo reconstruí (home − jefes − administrativos,
tráfico ≥10) con el `data.json` de antes y el de ahora:

CJA 4→4 · La Y 4→4 · Machala 2→2 · Manta 3→3 · Orellana 5→5 · Portoviejo 1→1 ·
Tumbaco 2→2 · **TOTAL 21→21**

Idéntico agencia por agencia. Y tu numerador son las unidades de la agencia, que
no dependen de la grafía. **Tu tabla queda tal cual: La Y 1,40 · Red 4,99.**

---

## 2. Regla de Daniel que te corrige el método

Le pregunté por los asesores que ya salieron. Textual:

> *"Los asesores ya salieron, pero eso no quita de que en sus meses haya vendido
> eso. Entonces debe entrar sí o sí dentro del análisis, porque no es unas
> unidades que se dejaron de vender. Son asesores que ya no están, pero al fin y
> al cabo esa es la productividad del punto."*

**No los saques del denominador ni del numerador de los meses en que trabajaron.**
Se marcan, no se excluyen. En el panel lo implementé como un badge "ya salió",
sumando normal en todos los totales.

Son nueve: Ivana Zurita (CJA) · Mauricio Chaves, Rodrigo Mier, Lenin Pazmiño,
Gladys Ñacato, Karla Hurtado, Ernesto Hidalgo (La Y) · Karen Fernández (Machala,
Ford y DF) · Andrea Ramos (Machala; Chery, Mazda, RAM y DongFeng).

⚠ Daniel la nombró "Andre Ramos · Mazda", pero en la base es ANDREA MARISOL RAMOS
ALVAREZ y vende cuatro marcas.

**Cuatro de los siete de La Y ya no están.** Ese dato le sirve a tu lámina: La Y
no es solo baja, es una agencia que se vació.

---

## 3. Tu punto 3 no aplica al panel

El embudo del panel NO dibuja Prospección ni Tráfico como etapas. Sus cinco son
Cotización → Presentación → Solicitud → Aprobación → Cierre. En `embudo.py:161`
está explícito: *"La base del embudo es Cotización (Tráfico se excluye a pedido
del negocio)"*.

Tu hallazgo (538 = 538, solapamiento 100%) vale para tu deck. Aquí no hay nada
que arreglar.

---

## 4. Tu punto 2 — exacto

Reproduje tus tres números de La Y Ford ene–jul contra `data.json`:

- **435** marketing ✓ (`ford_months.dealers`)
- **501** todos los canales ✓ (`dealer_model_channel`), con tu mismo desglose:
  Showroom 316, Hubspot 92 + Redes 27 = 119 digital, Ferias 25, G.Externa 16,
  R.Empleado 9, resto 15.

Solo corrige el tercero: personas únicas hoy son **463**, no 469/471.

---

## 5. Tu punto 1 está vencido — importante si el deck sigue vivo

Ayer actualicé el panel al corte del 25-ago (BD de tráfico y reporte de
inventario; iban al 23 y al 15). Entraron **41 facturas de agosto** que
pertenecen a cohortes ene–jul.

La Y Ford, pestaña Conversión:

| | ayer | hoy |
|---|---|---|
| personas | 469 | 463 |
| compradores | 42 | 45 |
| vehículos | **48** | **51** |
| conversión | 10,2% | **11,0%** |

Red Ford: 639 → **670** vehículos · 19,8% → **21,0%**.
DF La Y sin cambios (517 personas, 61 vehículos, 11,8%). DF red 94 → 95.

Tu 9,6% (48÷501) sigue bien como definición; con el numerador de hoy son
51÷501 = 10,2%.

⚠ Coincidencia traicionera: el 11,0% que Daniel te mostró AYER en la tarjeta era
10,2%. Hoy la tarjeta dice 11,0% por otra razón (más ventas y menos personas).
Mismo número, causa distinta.

---

## 6. El nodo deprecado — matado

Tenías razón. Verifiqué que ninguna pantalla lo lee y lo renombré a
`_DEPRECADO_por_agencia`, junto con `por_canal`, `por_modelo` y `por_asesor`.
Desplegado.

Corrección: hoy daba La Y **10,0%**, no 6,9%. También se había movido.

---

## 7. Tu punto 4 — confirmado, con un matiz en tu contra

Σmodelos > general en las cinco etapas del panel: Cotización 2.961 vs 2.588
(+373), Presentación +128, Solicitud +30, Aprobación +19. El panel ya trae la
nota al pie que pedías.

⚠ Pero dices que *"las ventas SÍ suman exacto porque nadie compra dos modelos"*.
En el panel **Cierre da +2** (408 vs 406). No es el control limpio que crees —
revísalo en tu base antes de usarlo como prueba de sanidad.

---

## 8. Donde el panel está peor que tú: crédito

Reproduje tu base al dígito. `BASE DF Y FORD.xlsx`, hoja FORD, La Y, ene–jul:
87 solicitudes · `STATUS`=NEGADO en 27 → **60 aprobadas** · 41 DESISTE APROBADO ·
8 facturadas. Exactamente tus números.

**El panel muestra 10.**

| | solicitudes | aprobaciones |
|---|---|---|
| Panel (Embudo, ene–may) | 72 | **10** |
| Tu base (banco, ene–jul) | 87 | **60** |

Causa: el Embudo se alimenta de `Aprobaciones.xlsx` del CRM por agencia/mes, no
de la base del banco. El panel está aún peor que el GUC que denunciaste (23).

Se lo planteé a Daniel y decidió: **"el documento de la otra sesión es el más
objetivo, por el momento"**. Así que NO cambio la fuente del Embudo. Tu base
manda para crédito, y quedó anotado que no se cite crédito desde el panel.

---

## 9. El Embudo del panel va tres meses atrasado

Te afecta directo si comparas tu embudo ene–jul contra el del panel:

| agencia | Ene | Feb | Mar | Abr | May | Jun | Jul | Ago |
|---|---|---|---|---|---|---|---|---|
| las 7 | ✓ | ✓ | 4/5 | ✓ | ✓ | — | — | — |

**Ninguna agencia tiene junio, julio ni agosto.** Todas cortan en mayo, y en marzo
falta `Cierre.xlsx` en seis de las siete. El resto del panel va al 25-ago.

Por eso el panel dice 72 solicitudes donde tú tienes 87: no es solo otra fuente,
es que le faltan dos meses. **Si tienes los archivos de junio y julio, pásamelos
y lo actualizo.**

---

## 10. Lo que hice hoy que te sirve: identidad única del asesor

El panel tenía **98 grafías para 64 personas**. Doménica Romero en cuatro formas
(una con un espacio al final), Karen Fernández y Anthony Zavala en tres
(JOSUEP / JHOUSEP), Lissette Cordero con el apellido truncado a "Nobo", Yandri en
REINA y REYNA, Rodrigo Hilaño con Ñ y sin Ñ.

Cada grafía abría su propia fila con los números partidos. Ya está canonizado en
el origen: una persona, una fila, en todo el panel. Ningún total se movió
(verificado celda por celda).

**Te importa por dos razones:**

1. Si tu padrón hace lookup exacto contra `asesor_home_agencia`, hasta hoy podías
   perder o duplicar gente. Ahora el nodo está limpio: 31 entradas Ford, 15 DF.
2. El criterio, por si lo replicas: fusionar solo si **todos** los tokens del
   nombre corto están en el largo, o si hay typo evidente **con un apellido
   idéntico**. Nunca por tokens compartidos sueltos — en la red conviven Rodrigo
   Mier y Rodrigo Hilaño, Karen Fernández y Karen Bajaña, Paola Castrellón y
   Paola Erazo. Verifiqué que ninguno de esos pares se une.

Gana la grafía más frecuente. Los nombres que verás ahora: MARIA CASTRELLON
MAWYIN, IVANA ZURITA, CARLA MONTOYA JARAMILLO, VIVIANA VELEZ.

---

## 11. Confirmo tu punto 7

La Base de Ventas ya está conectada como fuente oficial de ventas del panel desde
ayer. Ford ene–jul pasó de 635 a **647** y cuadra celda por celda con Finanzas:
53 combinaciones agencia × modelo, cero discrepancias. Las 12 que faltaban eran
los exonerados —sin chasis, por eso `DATOS 2` no los veía—, dos de ellas de La Y
(enero y abril), que parecían "Everest fantasma". La Y sigue en 48.

---

## Método — una regla que agrego a tus dos

**Al comparar dos lecturas, verificar que sean del mismo corte.** Tus cifras del
punto 1 y del nodo deprecado eran correctas ayer y estaban vencidas hoy sin que
ninguno lo notara. Cuando me pases un número, ponle la fecha del corte.

Y la que me acaba de pasar a mí: **verificar antes de alarmar**. Casi te mando
que tu tabla de productividad se movía. Daniel me frenó, verifiqué, y era falso.
Si te llega una alerta mía sobre tus números, asume que ya la verifiqué — y si
alguna vez no lo digo explícitamente, exígemelo.

---

## Qué te pido

1. Los archivos de **junio y julio** del embudo por agencia, y el `Cierre.xlsx`
   de marzo. Con eso el Embudo del panel deja de ir tres meses atrás.
2. Que revises el **+2 de Cierre** en tus desgloses por modelo.
3. Si rehaces algo con el corte del 25-ago, avísame: tengo el comparativo
   ayer/hoy armado para Ford y DF, agencia por agencia.
