#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lista las memorias que guardan cifras sin decir a qué fecha corresponden.

Una cifra sin fecha de corte envejece en silencio: se cita meses después como si
siguiera vigente y nadie nota la diferencia porque suena bien. El 27-ago-2026 dos
cifras vencidas de UN día viajaron entre dos sesiones sin que ninguna lo detectara.

Uso:
    python3 audit_memoria.py            # solo el resumen
    python3 audit_memoria.py --detalle  # con las cifras de cada archivo

La regla está en la memoria `feedback_memoria_caduca`.
"""
import re
import sys
from pathlib import Path

MEM = Path.home() / '.claude/projects/-Users-danielyanezalbuja/memory'

# Marcas de que el archivo sí sitúa sus números en el tiempo.
FECHA = re.compile(
    r'\b\d{1,2}-(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-20\d\d\b'
    r'|\b20\d\d-\d\d-\d\d\b'
    r'|\bal?\s\d{1,2}\s?de\s?(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|'
    r'septiembre|octubre|noviembre|diciembre)\b'
    r'|\b(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[–-]\w{3}\b'
    r'|\bcorte\b', re.I)

# Cifras "duras": plata, miles, porcentajes con decimal, unidades. Un "2" suelto no.
CIFRA = re.compile(
    r'(?<![\w.])(?:\$\s?[\d.,]{3,}'
    r'|\d{1,3}(?:\.\d{3})+'
    r'|\b\d+,\d+\s?%'
    r'|\b\d{2,}\s?%'
    r'|\b\d{2,4}\s?(?:uds|unidades))')


def auditar():
    con, sin = [], []
    for p in sorted(MEM.glob('*.md')):
        if p.name == 'MEMORY.md':
            continue
        txt = p.read_text(encoding='utf-8')
        cifras = CIFRA.findall(txt)
        if not cifras:
            continue
        (con if FECHA.search(txt) else sin).append((p.stem, len(cifras), cifras))
    return con, sin


if __name__ == '__main__':
    con, sin = auditar()
    tot = len(con) + len(sin)
    print(f'memorias con cifras duras: {tot}')
    print(f'   con fecha de corte : {len(con)}')
    print(f'   SIN fecha de corte : {len(sin)}')
    if sin:
        print('\nArreglar poniendo la fecha, o mejor: cambiar el número por el puntero'
              ' a donde se mira vivo.\n')
        for nombre, n, cifras in sorted(sin, key=lambda x: -x[1]):
            print(f'   {nombre:46} {n:>3} cifras')
            if '--detalle' in sys.argv:
                print(f'      {", ".join(cifras[:10])}')
    sys.exit(1 if sin else 0)
