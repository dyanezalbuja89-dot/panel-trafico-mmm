#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lista las memorias que guardan cifras sin decir a qué fecha corresponden.

Una cifra sin fecha de corte envejece en silencio: se cita meses después como si
siguiera vigente y nadie nota la diferencia porque suena bien. El 27-ago-2026 dos
cifras vencidas de UN día viajaron entre dos sesiones sin que ninguna lo detectara.

Uso:
    python3 audit_memoria.py            # solo el resumen
    python3 audit_memoria.py --detalle  # con las cifras de cada archivo

Sale con código 1 si alguna memoria guarda cifras sin situarlas en el tiempo, para
poder encadenarlo en un chequeo.

⚠ Dos cosas que le costaron falsos positivos y ya están cubiertas: el `modified:`
del frontmatter NO es contenido, y una fecha vale escrita de muchas formas —
`25-ago-2026`, `ago-2026`, `05-ago`, `ene–jul`, `Q3-2026`, `1 de septiembre de
2026`. Si aparece una forma nueva, agregarla a FECHA antes de "arreglar" el
archivo: puede que ya esté fechado.

La regla está en la memoria `feedback_memoria_caduca`.
"""
import re
import sys
from pathlib import Path

MEM = Path.home() / '.claude/projects/-Users-danielyanezalbuja/memory'

# Marcas de que el archivo sí sitúa sus números en el tiempo.
_MES = r'(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)'
_MESL = (r'(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|'
         r'octubre|noviembre|diciembre)')
FECHA = re.compile(
    rf'\b\d{{1,2}}-{_MES}\w*-20\d\d\b'          # 25-ago-2026
    rf'|\b{_MES}\w*[-/ ]20\d\d\b'                 # ago-2026 · julio 2026
    r'|\b20\d\d-\d\d-\d\d\b'                   # 2026-08-25
    rf'|\bal?\s\d{{1,2}}\s?de\s?{_MESL}\b'       # al 25 de agosto
    rf'|\b{_MES}[–-]{_MES}\b'                      # ene–jul
    rf'|\b\d{{1,2}}-{_MES}\b'                       # 05-ago (día-mes, sin año)
    rf'|\b\d{{1,2}}\s?de\s?{_MESL}\s?(?:de\s?)?20\d\d\b'   # 1 de septiembre de 2026
    r'|\bQ[1-4][ -]?20\d\d\b'                   # Q3-2026
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
        # El frontmatter no es contenido: su `modified: 2026-07-23T15:38:...` se
        # contaba como cifra y marcaba archivos que no guardan ningún número.
        partes = txt.split('---')
        cuerpo = '---'.join(partes[2:]) if txt.lstrip().startswith('---') and len(partes) > 2 else txt
        cifras = CIFRA.findall(cuerpo)
        if not cifras:
            continue
        (con if FECHA.search(cuerpo) else sin).append((p.stem, len(cifras), cifras))
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
