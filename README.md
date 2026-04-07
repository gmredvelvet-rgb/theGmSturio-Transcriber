# TheGmStudio Transcriber

A desktop app for transcribing tabletop RPG sessions recorded with [Craig Bot](https://craig.chat/) on Discord. Built with **faster-whisper** optimized for CPU — no NVIDIA GPU required.

Features a modern GUI with campaign management, AI-powered session summaries via **Ollama**, and Discord webhook integration.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Automatic transcription** of multi-track audio from Craig Bot recordings
- **Campaign system** — organize sessions by campaign, track transcripts over time
- **AI session summaries** — generate narrative recaps using local LLMs through Ollama
- **Discord integration** — send summaries directly to a channel via webhook
- **Multiple output formats** — TXT, Markdown, JSON
- **Multi-language support** — Spanish, English, Portuguese, French, German, or auto-detect
- **CPU optimized** — runs with `int8` quantization, no GPU needed
- **Standalone .exe** — package as a portable Windows executable

## Prerequisites

1. **Python 3.11+**
2. **FFmpeg** in your system PATH
   ```
   winget install FFmpeg
   ```
   Or download from https://ffmpeg.org/download.html and add to PATH.

## Installation

```bash
git clone https://github.com/gmredvelvet-rgb/theGmSturio-Transcriber.git
cd theGmSturio-Transcriber

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

This opens the GUI where you can:

1. **Add files** or **open a folder** with Craig Bot recordings
2. Pick a whisper model, language, and output format
3. Click **Start Transcription** and watch progress in real time
4. Browse and manage campaigns with per-session transcripts
5. Generate AI summaries and send them to Discord

## Setting Up Ollama (AI Summaries)

The app uses [Ollama](https://ollama.com) to run local language models for generating narrative session summaries.

### 1. Install Ollama

Download and install from https://ollama.com/download.

### 2. Pull a model

Open a terminal and pull one of the recommended models:

```bash
# Lightweight and fast (recommended to start)
ollama pull mistral

# Higher quality alternatives
ollama pull llama3.2
ollama pull llama3.1:8b
ollama pull gemma2:9b
```

### 3. Keep Ollama running

Ollama runs as a local server on `http://localhost:11434`. Just make sure it's running before generating summaries. The app will auto-detect available models.

### 4. Generate a summary

In the app's **Summary** tab:
1. Select a transcript
2. Pick a model from the dropdown (auto-populated from Ollama)
3. Click **Generate Summary**
4. Optionally send it to Discord via webhook

> **RAM usage:** `mistral` needs ~4 GB, `llama3.1:8b` needs ~8 GB. With 16+ GB of RAM you're good.

## Whisper Models

| Model | RAM | Speed |
|-------|-----|-------|
| `small` | ~2 GB | Fast |
| `medium` | ~5 GB | Balanced |
| `large-v3` | ~10 GB | Best quality |

All models use `int8` compute type to reduce memory usage.

## Download & Run (No Installation Required)

Go to the [Releases](../../releases) page and download the latest `.zip`. Extract it anywhere and double-click `TheGmstudioTranscriber2.exe` — everything is included (FFmpeg, Python runtime, all dependencies).

No Python, no FFmpeg install, no terminal commands needed.

## Building a Standalone Executable (for developers)

```bash
python build.py
```

Generates `dist/TheGmstudioTranscriber2/`. To include FFmpeg, place `ffmpeg.exe` and `ffprobe.exe` inside a `ffmpeg/` subfolder next to the executable.

The GitHub Actions workflow handles this automatically when you publish a Release.

## Project Structure

```
├── main.py                # Entry point (launches GUI)
├── build.py               # PyInstaller build script
├── requirements.txt
├── transcriber/
│   ├── __init__.py        # Package version
│   ├── gui.py             # GUI (CustomTkinter)
│   ├── cli.py             # CLI interface (Typer)
│   ├── transcribe.py      # Transcription engine (faster-whisper)
│   ├── audio.py           # Audio processing (FFmpeg)
│   ├── formatter.py       # Output formatters (TXT/MD/JSON)
│   ├── merger.py          # Segment merging and sorting
│   ├── summarizer.py      # AI summary generation (Ollama)
│   ├── campaigns.py       # Campaign management
│   ├── discord_hook.py    # Discord webhook integration
│   └── config.py          # Central configuration
├── campaigns/             # Campaign data and transcripts
├── models/                # Whisper model cache (auto-downloaded)
└── output/                # Generated transcriptions
```
