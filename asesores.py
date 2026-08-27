#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identidad única del asesor comercial.

Regla de Daniel (26-ago-2026): *"sea Karen Fernández Bravo o Karen Johanna
Fernández Bravo, es exactamente la misma asesora; no puede haber duplicidad de
asesores"*. Una persona = una fila, en todo el panel.

El problema es real y grande: en `data.json` conviven 99 grafías para bastantes
menos personas. Doménica Romero aparece de cuatro formas (una con un espacio al
final), Karen Fernández de tres, Anthony Zavala de tres —dos de ellas con el
segundo nombre escrito distinto—, y hay nombres truncados a mitad de palabra.

Sin canonizar, cada grafía abre su propia fila: los números de la persona salen
partidos y las filas chicas aparecen con resultados absurdos (0 ventas, 0,0% en
rojo) mientras sus unidades se acreditan a la otra fila.

## Cómo se decide que dos grafías son la misma persona

Dos reglas, ambas conservadoras — unir a dos personas distintas es peor que
dejar una duplicada:

1. **Subconjunto de tokens.** Todos los tokens del nombre corto están en el
   largo: "KAREN FERNANDEZ BRAVO" ⊂ "KAREN JOHANNA FERNANDEZ BRAVO". Nunca por
   tokens compartidos sueltos: en la red conviven RODRIGO MIER y RODRIGO HILAÑO,
   KAREN FERNÁNDEZ y KAREN BAJAÑA, PAOLA CASTRELLÓN y PAOLA ERAZO.

2. **Typo, con guarda.** Alta similitud del nombre completo Y al menos un
   apellido idéntico: IVANA/IVANNA, JOSUEP/JHOUSEP, REINA/REYNA, y un
   "Nobo" que quedó truncado de "Noboa".

La tilde de la Ñ desaparece al normalizar, así que HILAÑO=HILANO y
PEÑAFIEL=PENAFIEL se resuelven solos, sin fuzzy.

## Cuál grafía gana

La **más frecuente** en `data.json` — la que la red usa a diario. Es el mismo
criterio que ya usaban el ranking de Conversión y el Embudo, así que canonizar
no mueve ningún nombre que el panel ya mostraba.

⚠ Esto NO saca a nadie del análisis. Un asesor que ya salió sigue sumando sus
unidades: son ventas que ocurrieron y son productividad del punto. Marcarlo es
otra cosa — eso lo hace [asesores_salidos.py].
"""
import re
import unicodedata
from difflib import SequenceMatcher

# No son personas: son categorías del panel. Nunca se fusionan ni se renombran.
NO_PERSONAS = {
    'OTROS', 'SIN ASESOR', '(SIN ASESOR)', 'SIN ASIGNAR', '_JEFE', 'JEFE',
    'NAN', 'NONE', 'TOTAL', 'SIN CATEGORIA', 'SIN CATEGORÍA',
}

_UMBRAL_TYPO = 0.90     # similitud del nombre completo normalizado


def norm(s):
    """Mayúsculas, sin tildes, sin dobles espacios. La Ñ cae en N."""
    s = unicodedata.normalize('NFD', str(s or '').upper())
    return ' '.join(re.sub(r'[^A-Z ]', ' ', s).split())


def es_persona(nombre):
    n = norm(nombre)
    return bool(n) and len(n) > 3 and n not in NO_PERSONAS


def _subconjunto(corto, largo):
    a, b = set(corto.split()), set(largo.split())
    return 2 <= len(a) < len(b) and a <= b


def _mismo_por_typo(a, b):
    """Alta similitud + un apellido idéntico. La guarda evita unir homónimos."""
    ta, tb = a.split(), b.split()
    if abs(len(ta) - len(tb)) > 1:
        return False
    if not (set(ta) & set(tb)):
        return False
    if SequenceMatcher(None, a, b).ratio() < _UMBRAL_TYPO:
        return False
    # al menos un token largo (≥4) idéntico: el apellido, no un "DE"/"LA"
    return any(len(t) >= 4 for t in set(ta) & set(tb))


def construir_mapa(freq):
    """{grafía: grafía_canónica} a partir de {grafía: nº de apariciones}.

    Solo incluye las grafías que cambian. Las personas con una sola forma no
    aparecen en el mapa.
    """
    nombres = [n for n in freq if es_persona(n)]
    nn = {n: norm(n) for n in nombres}

    padre = {n: n for n in nombres}

    def raiz(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    def unir(x, y):
        rx, ry = raiz(x), raiz(y)
        if rx != ry:
            padre[ry] = rx

    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            na, nb = nn[a], nn[b]
            if na == nb or _subconjunto(na, nb) or _subconjunto(nb, na) \
               or _mismo_por_typo(na, nb):
                unir(a, b)

    grupos = {}
    for n in nombres:
        grupos.setdefault(raiz(n), []).append(n)

    mapa = {}
    for miembros in grupos.values():
        if len(miembros) < 2:
            continue
        # gana la más frecuente; desempata la que tiene más tokens
        canon = max(miembros, key=lambda n: (freq.get(n, 0), len(norm(n).split())))
        for n in miembros:
            if n != canon:
                mapa[n] = canon
    return mapa


def clusters(freq):
    """{canónica: [alias...]} — para auditar la lista a ojo."""
    mapa = construir_mapa(freq)
    out = {}
    for alias, canon in mapa.items():
        out.setdefault(canon, []).append(alias)
    return {k: sorted(v) for k, v in sorted(out.items())}


# ── Aplicación sobre el data.json ya armado ──────────────────────────────────

def _es_campo_asesor(k):
    k = str(k).lower()
    return 'asesor' in k or 'ase_' in k


def _sumar(dst, src):
    """Funde `src` dentro de `dst` respetando la profundidad (n, {k:n}, {k:{k:n}})."""
    for k, v in src.items():
        if isinstance(v, dict):
            _sumar(dst.setdefault(k, {}), v)
        elif isinstance(v, (int, float)) and isinstance(dst.get(k), (int, float)):
            dst[k] = dst[k] + v
        else:
            dst.setdefault(k, v)     # texto (agencia-hogar): gana el canónico


def frecuencias(obj):
    """{grafía: nº de apariciones} recorriendo todo el árbol."""
    freq = {}

    def rec(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if _es_campo_asesor(k):
                    if isinstance(v, str):
                        freq[v] = freq.get(v, 0) + 1
                    elif isinstance(v, dict):
                        for x in v:
                            if isinstance(x, str):
                                freq[x] = freq.get(x, 0) + 1
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)

    rec(obj)
    return freq


def aplicar(obj, mapa):
    """Reescribe en sitio toda grafía alias por su canónica.

    Cubre las dos formas en que el nombre vive en el árbol: como VALOR de un
    campo (`clientes_flat[].asesor`) y como CLAVE de un dict (`by_asesor`,
    `asesor_home_agencia`). Al fusionar dos claves sus valores se suman, para
    que ningún total se mueva.
    """
    if not mapa:
        return 0
    n = [0]

    def rec(o):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if _es_campo_asesor(k):
                    if isinstance(v, str) and v in mapa:
                        o[k] = mapa[v]
                        n[0] += 1
                    elif isinstance(v, dict):
                        for viejo in [x for x in v if x in mapa]:
                            nuevo = mapa[viejo]
                            val = v.pop(viejo)
                            n[0] += 1
                            if nuevo not in v:
                                v[nuevo] = val
                            elif isinstance(val, dict) and isinstance(v[nuevo], dict):
                                _sumar(v[nuevo], val)
                            elif isinstance(val, (int, float)) and isinstance(v[nuevo], (int, float)):
                                v[nuevo] += val
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)

    rec(obj)
    return n[0]


def canonizar(obj):
    """Un solo paso: mide, agrupa y reescribe. Devuelve (personas, alias, celdas)."""
    freq = frecuencias(obj)
    mapa = construir_mapa(freq)
    celdas = aplicar(obj, mapa)
    personas = len({n for n in freq if es_persona(n)}) - len(mapa)
    return personas, len(mapa), celdas
