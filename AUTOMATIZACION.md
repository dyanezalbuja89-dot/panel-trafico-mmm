# Automatización diaria del panel — Setup

Pipeline que corre todos los días a las 10:00 AM:
1. Descarga el último adjunto "Reporte de Inventario" de Outlook (de Génesis Pincay, Axel Cedeño o Diego Quinde).
2. Si es distinto al actual, regenera `data.json` con `aggregate.py`.
3. Construye `index.html` con `build.py`.
4. Hace deploy a Vercel.

## Pasos de instalación (una sola vez)

### 1. Generar App Password en Microsoft 365

Microsoft bloquea logins IMAP con tu password normal. Necesitas un App Password:

1. Abre <https://account.microsoft.com/security>
2. Sección **Opciones de seguridad avanzadas** → **Contraseñas de aplicación**
3. Click **Crear una nueva contraseña de aplicación**
4. Copia la cadena de 16 caracteres (e.g. `abcd efgh ijkl mnop` — sin espacios al usar).
5. Guárdala temporalmente; el siguiente paso la pone en el archivo de entorno.

> **Si no ves la opción**: Maresa tiene políticas de seguridad que bloquean app passwords.
> Avísame y migramos a OAuth (toma 1 hora más de setup).

### 2. Crear archivo `.panel_trafico_env` con credenciales

En tu home, crea `~/.panel_trafico_env`:

```bash
cat > ~/.panel_trafico_env <<'EOF'
OUTLOOK_EMAIL=dyanez@orgu.com.ec
OUTLOOK_APP_PASSWORD=abcdefghijklmnop
EOF
chmod 600 ~/.panel_trafico_env
```

Reemplaza `abcdefghijklmnop` con los 16 caracteres del App Password generado en el paso 1.

`chmod 600` deja el archivo legible solo por tu usuario.

### 3. Probar manualmente que descarga funciona

```bash
cd "/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Abril/panel-trafico"
set -a; source ~/.panel_trafico_env; set +a
python3 fetch_inventario.py
```

Esperado: encuentra el último mail con adjunto y lo guarda en `~/Downloads/REPORTE DE INVENTARIO.xlsm`.

Si dice "no se encontró", revisa:
- ¿El correo está en la bandeja de entrada (no en otra carpeta)?
- ¿El asunto o nombre del archivo contiene "inventario" o "reporte"?

### 4. Probar el pipeline completo manualmente

```bash
./auto_update.sh
```

Esperado: descarga → genera → build → deploy. Mira `~/panel_trafico_auto.log` para el detalle.

### 5. Instalar el cron job de macOS (launchd)

```bash
# Copia el plist a la carpeta de LaunchAgents
cp "/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Abril/panel-trafico/com.daniel.paneltrafico.plist" \
   ~/Library/LaunchAgents/

# Cargar el job
launchctl load ~/Library/LaunchAgents/com.daniel.paneltrafico.plist

# Verificar que está cargado
launchctl list | grep paneltrafico
```

Deberías ver una línea con `com.daniel.paneltrafico`.

### 6. Probar disparo ahora (sin esperar a las 10 AM)

```bash
launchctl start com.daniel.paneltrafico
# Espera ~30 seg y mira el log:
tail -f ~/panel_trafico_auto.log
```

## Operación diaria

A las 10:00 AM cada día, si la Mac está prendida y con conexión:
- El job corre automáticamente
- Logs en `~/panel_trafico_auto.log`
- Vercel se actualiza solo
- Si no hay archivo nuevo en el correo, no hace nada (no genera trabajo innecesario)

Si la Mac está apagada/dormida a las 10 AM, launchd ejecuta el job apenas se despierta (siempre que esté antes de las 10 AM del día siguiente).

## Para detener la automatización

```bash
launchctl unload ~/Library/LaunchAgents/com.daniel.paneltrafico.plist
rm ~/Library/LaunchAgents/com.daniel.paneltrafico.plist
```

## Troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| `ERROR autenticación` | App password incorrecto o IMAP deshabilitado | Regenera App Password; verifica con IT que IMAP esté habilitado |
| `No se encontró ningún adjunto` | Correo no llegó o asunto/nombre no contiene "inventario/reporte" | Revisa el correo manualmente; ajusta `ATTACHMENT_KEYWORDS` en `fetch_inventario.py` |
| `npx vercel` falla | Token de Vercel expiró | Re-loguea con `npx vercel login` |
| El job no corre a las 10 AM | Mac estaba apagada / launchd no se cargó | `launchctl list \| grep paneltrafico` para verificar |

## Logs

- `~/panel_trafico_auto.log` — log principal con timestamps
- `/tmp/paneltrafico.log` — stdout del launchd
- `/tmp/paneltrafico.err.log` — stderr del launchd
