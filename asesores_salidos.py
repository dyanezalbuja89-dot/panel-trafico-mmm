#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Asesores que ya no están en la red.

NO se sacan del panel: sus ventas y su tráfico siguen sumando en todos los
agregados. Solo se marcan, para que al leer un ranking individual se sepa que
ese resultado no es de alguien a quien se le pueda pedir un plan de acción.

Para agregar a alguien: una entrada más en SALIDOS. `agencia` es informativa
(sirve para auditar la lista, no para el match).

⚠ El match NO puede ser por un token suelto. En la base conviven personas que
comparten nombre o apellido —RODRIGO MIER vs RODRIGO HILAÑO, KAREN FERNANDEZ vs
KAREN BAJAÑA, y MAURICIO CHAVES *FERNANDEZ* que comparte apellido con Karen—.
Por eso cada persona exige su apellido Y su nombre de pila.

⚠ Y una misma persona vive con varias grafías: KAREN FERNANDEZ / KAREN FERNANDEZ
BRAVO / KAREN JOHANNA FERNANDEZ BRAVO, e IVANA con el typo IVANNA. Por eso el
nombre de pila admite variantes.
"""
import re
import unicodedata

# El match NO mira la marca a propósito: un asesor multimarca queda marcado en todas
# donde vendió. Andrea Ramos vende Chery, Mazda, RAM y DongFeng desde Machala, y Karen
# Fernández aparece en Ford y en DongFeng. `agencia` y `marcas` son informativos.
SALIDOS = [
    {'label': 'Ivana Zurita',    'agencia': 'CJA',     'marcas': 'Ford',
     'apellido': ['ZURITA'],    'pila': ['IVANA', 'IVANNA']},
    {'label': 'Mauricio Chaves', 'agencia': 'La Y',    'marcas': 'Ford',
     'apellido': ['CHAVES'],    'pila': ['MAURICIO']},
    {'label': 'Rodrigo Mier',    'agencia': 'La Y',    'marcas': 'Ford',
     'apellido': ['MIER'],      'pila': ['RODRIGO']},
    {'label': 'Lenin Pazmiño',   'agencia': 'La Y',    'marcas': 'Ford',
     'apellido': ['PAZMINO'],   'pila': ['LENIN']},
    {'label': 'Karen Fernández', 'agencia': 'Machala', 'marcas': 'Ford · DongFeng',
     'apellido': ['FERNANDEZ'], 'pila': ['KAREN']},
    {'label': 'Gladys Ñacato',   'agencia': 'La Y',    'marcas': 'DongFeng',
     'apellido': ['NACATO'],    'pila': ['GLADYS']},
    {'label': 'Karla Hurtado',   'agencia': 'La Y',    'marcas': 'DongFeng',
     'apellido': ['HURTADO'],   'pila': ['KARLA']},
    {'label': 'Ernesto Hidalgo', 'agencia': 'La Y',    'marcas': 'DongFeng',
     'apellido': ['HIDALGO'],   'pila': ['ERNESTO']},
    # Daniel la nombró "Andre Ramos · Mazda"; en la base es ANDREA y vende cuatro marcas.
    {'label': 'Andrea Ramos',    'agencia': 'Machala', 'marcas': 'Chery · Mazda · RAM · DongFeng',
     'apellido': ['RAMOS'],     'pila': ['ANDREA', 'ANDRE']},
]


def _norm(s):
    """Mayúsculas sin tildes: 'Pazmiño' y 'PAZMINO' tienen que caer en lo mismo."""
    s = unicodedata.normalize('NFD', str(s or '').upper())
    return re.sub(r'[^A-Z ]', ' ', s)


def quien_es(nombre):
    """La entrada de SALIDOS que corresponde a este nombre, o None."""
    toks = set(_norm(nombre).split())
    if not toks:
        return None
    for s in SALIDOS:
        if all(a in toks for a in s['apellido']) and any(p in toks for p in s['pila']):
            return s
    return None


def resolver(nombres):
    """{nombre_tal_como_aparece: label} para los nombres que son de alguien que salió.

    Se resuelve aquí, contra los nombres que de verdad quedaron en data.json, para
    que el navegador solo tenga que hacer un lookup exacto — sin lógica de match
    en el panel, donde una grafía nueva pasaría desapercibida.
    """
    out = {}
    for n in nombres:
        s = quien_es(n)
        if s:
            out[n] = s['label']
    return out


if __name__ == '__main__':
    import json
    from pathlib import Path
    d = json.loads((Path(__file__).parent / 'data.json').read_text(encoding='utf-8'))
    vistos = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if 'asesor' in k.lower():
                    if isinstance(v, str):
                        vistos.add(v)
                    elif isinstance(v, dict):
                        vistos.update(x for x in v if isinstance(x, str))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    vistos = {v for v in vistos if v and len(v) > 3}
    res = resolver(vistos)
    print(f'nombres de asesor en data.json: {len(vistos)}')
    for s in SALIDOS:
        gs = sorted(n for n, lb in res.items() if lb == s['label'])
        print(f"\n{s['label']} · {s['agencia']} · {s['marcas']} → {len(gs)} grafías")
        for g in gs:
            print(f'    {g}')
        if not gs:
            print('    ⚠ ninguna — revisar la grafía en la base')
