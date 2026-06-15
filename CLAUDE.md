# Panel Tráfico ORGU — instrucciones para sesiones de Claude

## Múltiples sesiones simultáneas

Más de una sesión de Claude puede estar editando este repo a la vez. Para evitar
que la última sesión que hace `python3 build.py + git push` borre el trabajo
in-disk de otra sesión, **NUNCA ejecutes `python3 build.py` directo**.

Usa siempre:

```bash
./safe_build.sh           # build + integridad-check
./safe_build.sh --deploy  # build + deploy a Vercel prod
./safe_build.sh --check   # solo verifica (no toca nada)
```

El script:
1. `git fetch origin` y aborta si remote está adelante de local (fuerza pull).
2. Verifica que tabs críticas siguen en build.py antes de rebuild.
3. Re-verifica que index.html post-build mantiene esas tabs.

## Pre-commit hook

`.git/hooks/pre-commit` aborta el commit si:
- Remote está adelante de local (otra sesión pusheó).
- Alguna tab crítica (`tab-digital`, `tab-inv`, `tab-ford`, `tab-embudo`,
  `TAB DIGITAL · HubSpot`) desapareció de build.py o index.html.

Bypass: `git commit --no-verify` (solo cuando el wipe fue coordinado con Daniel).

## Tab "Seguimiento Digital"

NO modificar `<section id="tab-digital">` ni el bloque JS `TAB DIGITAL · HubSpot`
salvo que Daniel lo pida explícitamente en la sesión actual. Otra sesión paralela
maneja UX/UI de esa pestaña. Más detalle en la memoria
[Hands-off Seguimiento Digital](file:///Users/danielyanezalbuja/.claude/projects/-Users-danielyanezalbuja/memory/feedback_seguimiento_digital_hands_off.md).
