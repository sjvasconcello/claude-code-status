# Claude Usage Monitor

Widget flotante para Windows que muestra tu uso de Claude y cuándo se renueva tu plan, posicionado en la esquina superior derecha de la pantalla.

```
┌─────────────────────────────────┐
│ ● Claude Monitor          ◐ ⚙  │
│ Tokens: 142.3k / 200.0k  71.2% │
│ ████████████░░░░░░░░░░░░        │
│ Plan PRO  ·  Renueva 1 Mar (3d) │
│ 📁 local  ·  14:35:20           │
└─────────────────────────────────┘
```

## Características

- **Siempre visible** sobre todas las ventanas (toggleable con clic derecho)
- **Transparencia** configurable (30% – 100%)
- **Auto-refresco** cada N segundos (configurable)
- **Refresco manual** con el botón ⟳
- **Draggable** – arrastra con clic izquierdo para reposicionar
- **Dos fuentes de datos**: archivos locales de Claude Code o API de Anthropic
- **Tema oscuro/claro**
- **Menú contextual** con clic derecho (siempre visible, refrescar, configuración, cerrar…)
- **Inicio automático** con Windows (opcional, script incluido)

---

## Requisitos

| Requisito | Versión mínima |
|-----------|---------------|
| Windows   | 10 / 11       |
| Python    | 3.8+          |

> **¿Por qué Python y no un .exe?**
> Distribuir como script `.py` evita completamente los falsos positivos de antivirus.
> Los ejecutables compilados con PyInstaller suelen ser marcados como sospechosos
> aunque el código sea 100% legítimo. Ejecutar el script directamente es la forma
> más limpia y segura.

---

## Instalación paso a paso

### 1. Instalar Python

1. Ve a <https://www.python.org/downloads/>
2. Descarga Python 3.11 o superior (recomendado)
3. **Importante:** durante la instalación, marca la casilla **"Add Python to PATH"**
4. Completa la instalación

Verifica que funciona abriendo `cmd` y escribiendo:
```cmd
python --version
```
Deberías ver algo como `Python 3.11.x`.

### 2. Descargar el proyecto

**Opción A – Con Git:**
```cmd
git clone https://github.com/TU_USUARIO/claude-code-status.git
cd claude-code-status
```

**Opción B – Sin Git:**
Descarga el ZIP desde GitHub → "Code" → "Download ZIP" → extrae la carpeta.

### 3. Instalar dependencias

Abre `cmd` en la carpeta del proyecto y ejecuta:
```cmd
pip install -r requirements.txt
```

> `requests` es la única dependencia. tkinter ya viene incluido con Python.

### 4. Ejecutar

**Forma simple (con ventana de consola visible para ver errores):**
```cmd
python claude_status.py
```

**Forma silenciosa (sin consola, recomendado para uso diario):**
```cmd
pythonw claude_status.py
```
O simplemente haz **doble clic en `start.bat`**.

---

## Configuración

Al iniciar, la app crea un archivo de configuración en:
```
C:\Users\TU_USUARIO\.claude_monitor\config.json
```

La forma más fácil de configurarla es **haciendo clic derecho → ⚙ Configuración** en el widget.

### Opciones disponibles

| Opción | Descripción | Por defecto |
|--------|-------------|-------------|
| Plan | `free` / `pro` / `max` / `api` | `pro` |
| API Key | Tu Anthropic API key (opcional) | vacío |
| Día de renovación | Día del mes en que se renueva tu plan | `1` |
| Límite de tokens | Tokens máximos del mes (0 = auto) | `0` |
| Transparencia | De 0.3 (casi invisible) a 1.0 (opaco) | `0.88` |
| Refresco auto | Segundos entre actualizaciones automáticas | `60` |
| Tema | `dark` / `light` | `dark` |

---

## Cómo se obtienen los datos de uso

La app intenta obtener datos en este orden:

### 1. API de Anthropic (más preciso)

Si configuras tu API key en ⚙ Configuración, la app consulta directamente
a `api.anthropic.com` y obtiene los tokens reales usados este mes.

Obtén tu API key en: <https://console.anthropic.com/settings/api-keys>

> **Nota:** Esto funciona para usuarios de la API. Si usas Claude.ai (web/app),
> sigue el paso siguiente.

### 2. Archivos locales de Claude Code

Si tienes **Claude Code** (el CLI) instalado, la app lee automáticamente los
archivos de sesión en `~/.claude/projects/` y suma los tokens de este mes.

### 3. Botón "Abrir consola Anthropic"

Si ninguna de las anteriores funciona, usa el menú contextual →
**🌐 Abrir consola Anthropic** para ver tu uso real en el navegador.

---

## Controles

| Acción | Resultado |
|--------|-----------|
| Clic izquierdo + arrastrar | Mover la ventana |
| Clic en ⟳ | Refrescar datos ahora |
| Clic en ⚙ | Abrir configuración |
| Clic derecho | Menú contextual |
| Menú → "Siempre visible" | Toggle sobre/bajo otras ventanas |
| Menú → "Esquina superior derecha" | Volver a posición original |

---

## Inicio automático con Windows (opcional)

Para que el monitor se inicie solo cuando enciendas el PC:

1. Haz **clic derecho** en `install_autostart.bat`
2. Selecciona **"Ejecutar como administrador"**
3. Listo. El monitor iniciará 30 segundos después de iniciar sesión.

Para **desactivar** el inicio automático:
```cmd
schtasks /delete /tn "ClaudeUsageMonitor" /f
```

---

## Solución de problemas

### La ventana no aparece
- Ejecuta `start_visible.bat` para ver errores en la consola
- Verifica que Python esté en PATH: `python --version`

### "tkinter no disponible"
- En Windows esto no debería ocurrir, pero si pasa:
  - Desinstala Python y reinstala marcando todas las opciones
  - O instala: `pip install tk`

### El antivirus bloquea el script
- Los archivos `.py` no deberían ser bloqueados
- Si el antivirus bloquea `python.exe`, agrégalo a las excepciones
- Esto es un falso positivo — el código fuente es completamente visible y auditable

### Los datos de tokens muestran 0
- Configura tu API key en ⚙ Configuración para obtener datos reales
- O revisa que tengas Claude Code instalado y hayas usado sesiones este mes

### Error de API: HTTP 401
- La API key es incorrecta o expiró
- Genera una nueva en: <https://console.anthropic.com/settings/api-keys>

---

## Estructura del proyecto

```
claude-code-status/
├── claude_status.py        # Aplicación principal
├── start.bat               # Lanzador silencioso (doble clic)
├── start_visible.bat       # Lanzador con consola (para debug)
├── install_autostart.bat   # Configura inicio automático
├── requirements.txt        # Dependencias pip
└── README.md               # Este archivo
```

---

## Privacidad y seguridad

- **El código es 100% auditable** — es un script Python legible
- La API key se guarda localmente en `~/.claude_monitor/config.json`
- No se envía ningún dato a servidores externos (excepto a `api.anthropic.com` si configuras API key)
- No hay telemetría, no hay analytics, no hay conexiones ocultas

---

## Licencia

MIT — Úsalo, modifícalo, distribúyelo libremente.
