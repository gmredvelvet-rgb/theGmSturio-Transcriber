# 🎙️ Whisperer

Transcriptor de sesiones de rol grabadas con [Craig Bot](https://craig.chat/) en Discord.

Usa **faster-whisper** optimizado para CPU — diseñado para funcionar sin GPU NVIDIA.

**Incluye interfaz gráfica y modo CLI.**

## Hardware Probado

| Componente | Especificación |
|------------|---------------|
| CPU | AMD Ryzen 5 5500 |
| RAM | 24 GB |
| GPU | AMD RX 6650 XT (no se usa, sin CUDA) |
| OS | Windows 11 |

## Requisitos Previos

1. **Python 3.11+**
2. **FFmpeg** instalado y disponible en PATH
   ```
   winget install FFmpeg
   ```
   O descargarlo de https://ffmpeg.org/download.html y agregar al PATH.

## Instalación

```bash
cd whisperer

# Crear entorno virtual
python -m venv venv
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

## Uso — Interfaz Gráfica (recomendado)

```bash
python main.py
```

Esto abre la ventana de Whisperer donde puedes:

1. **Agregar archivos** o **abrir una carpeta** de Craig Bot
2. Seleccionar modelo, idioma, formato de salida
3. Hacer clic en **Iniciar Transcripción**
4. Ver el progreso y log en tiempo real
5. Abrir el archivo generado directamente desde la app

## Uso — Línea de Comandos

```bash
python main.py --cli transcribe ./craig_session/ [OPCIONES]
```

### Opciones CLI

```
  -o, --output DIR        Directorio de salida (default: output/)
  -m, --model TEXT        Modelo: small, medium, large-v3 (default: medium)
  -l, --language TEXT     Idioma: es, en, etc. (default: auto-detectar)
  -f, --format TEXT       Formato: txt, markdown, json (default: txt)
  -t, --threads INT       Threads de CPU (default: 6)
  --filename TEXT         Nombre del archivo de salida (default: transcript)
  --no-merge             No fusionar segmentos consecutivos
  -v, --verbose          Logs detallados
```

## Empaquetar como .exe (software local)

Para generar un ejecutable standalone que no necesita Python instalado:

```bash
python build.py
```

Esto genera `dist/Whisperer/Whisperer.exe`. Puedes mover esa carpeta a cualquier
lugar de tu PC y ejecutar directamente.

> **Nota:** FFmpeg sigue siendo necesario en el PATH del sistema.

## Formato de Salida

### TXT
```
[00:00] GM: Bienvenidos a la sesión.

[00:05] Jugador1: Entro a la taberna.

[00:10] Jugador2: Busco al tabernero.
```

### Markdown
```markdown
# Transcripción de Sesión

**[00:00] GM**
Bienvenidos a la sesión.

**[00:05] Jugador1**
Entro a la taberna.
```

### JSON
```json
{
  "metadata": {
    "transcription_date": "2026-04-06T...",
    "total_segments": 150,
    "speakers": ["GM", "Jugador1", "Jugador2"]
  },
  "segments": [
    {
      "speaker": "GM",
      "start": 0.0,
      "end": 3.5,
      "timestamp": "00:00",
      "text": "Bienvenidos a la sesión."
    }
  ]
}
```

## Rendimiento Estimado

| Modelo | RAM Aprox. | Velocidad Relativa |
|--------|-----------|-------------------|
| small | ~2 GB | Rápido |
| medium | ~5 GB | Moderado |
| large-v3 | ~10 GB | Lento |

Con `compute_type=int8` el consumo de memoria se reduce significativamente.

## Estructura del Proyecto

```
whisperer/
├── transcriber/
│   ├── __init__.py      # Versión del paquete
│   ├── gui.py           # Interfaz gráfica (CustomTkinter)
│   ├── cli.py           # Interfaz de línea de comandos (Typer)
│   ├── transcribe.py    # Motor de transcripción (faster-whisper)
│   ├── audio.py         # Procesamiento de audio (ffmpeg)
│   ├── formatter.py     # Formateadores de salida
│   ├── merger.py        # Fusión y ordenamiento de segmentos
│   └── config.py        # Configuración central
├── models/              # Cache de modelos (auto-generado)
├── output/              # Transcripciones generadas
├── main.py              # Punto de entrada (GUI por defecto)
├── build.py             # Script de empaquetado PyInstaller
├── requirements.txt
└── README.md
```

## Extensibilidad Futura

El proyecto está diseñado para ser extendido con:

- **Resumen automático con IA** — Agregar un módulo `summarizer.py`
- **Detección de NPCs** — Analizar patrones de habla del GM
- **Log de campaña** — Generar narrativa a partir de la transcripción
