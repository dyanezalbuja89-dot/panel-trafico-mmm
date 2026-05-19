# Ticket para IT — App Registration en Azure AD

**Solicitante:** Daniel Yanez Albuja (dyanez@orgu.com.ec)
**Asunto:** Crear App Registration para automatización del Panel de Tráfico (lectura de email)

## Contexto

Estoy automatizando la actualización diaria de un dashboard interno de tráfico/inventario.
El proceso necesita leer **un solo correo específico** (el reporte diario de inventario que envían
Génesis Pincay, Axel Cedeño o Diego Quinde) desde mi propia bandeja de entrada y descargar
el adjunto Excel.

Probamos:
- **IMAP con App Password**: bloqueado (`LOGIN failed`).
- **OAuth con client_ids públicos de Microsoft** (Microsoft Office, Azure CLI): bloqueado con
  error `AADSTS65002` — el tenant no permite apps first-party sin pre-autorización.

La solución correcta es crear una App Registration interna en nuestro Azure AD.

## Lo que necesito que hagan

### 1. Crear App Registration

`Azure Portal → Azure Active Directory → App registrations → New registration`

| Campo | Valor |
|---|---|
| **Name** | Panel Tráfico DY — Mail Reader |
| **Supported account types** | Accounts in this organizational directory only (single tenant) |
| **Redirect URI** | Dejar vacío (se configura en paso 3) |

### 2. Configurar permisos (API permissions)

`API permissions → Add a permission → Microsoft Graph → Delegated permissions`

Agregar los siguientes scopes:
- ✅ **`Mail.Read`** — leer los correos del usuario que se autentica
- ✅ **`User.Read`** — sign in básico (suele venir por default)
- ✅ **`offline_access`** — refresh token (para no tener que reautenticar cada hora)

**IMPORTANTE:** Después de agregar los permisos, hacer click en **"Grant admin consent for [Maresa/Corporación Maresa]"** — este botón solo lo puede usar un Global Admin / Application Admin.

### 3. Habilitar device code flow

`Authentication → Advanced settings → Allow public client flows = Yes`

(Esto permite usar device code flow desde un script local sin necesitar un secret.)

### 4. Compartirme dos IDs

Después de crear la app, en la pestaña **Overview** copiar:
- **Application (client) ID** — formato GUID, e.g. `12345678-abcd-...`
- **Directory (tenant) ID** — formato GUID, e.g. `87654321-fedc-...`

Ambos son **públicos** (no son secrets) y pueden compartirse por correo o Teams sin riesgo.

## Notas de seguridad

- La app solo lee correos **del usuario que se autentica con ella** (yo, dyanez@orgu.com.ec). No accede a correos de otros usuarios.
- No usa contraseñas: usa OAuth 2.0 con tokens que expiran y se refrescan, todo auditable en Azure AD sign-in logs.
- El alcance es de solo lectura (`Mail.Read`), no puede enviar correos ni borrar nada.
- Los tokens se almacenan localmente en mi Mac con permisos 600 (solo mi usuario los puede leer).

## Tiempo estimado

Si tienen acceso al Azure Portal: **10-15 minutos** de trabajo.

## ¿Por qué no se puede hacer con la opción default?

Microsoft 365 deprecó Basic Auth para IMAP en 2022. Y Corporación Maresa tiene configurada
una política que requiere que cada app que acceda a Microsoft Graph esté pre-autorizada
explícitamente — es buena práctica de seguridad, no es un bug.

---

Si necesitan referencia técnica para Azure AD App Registration:
<https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app>

Gracias!
